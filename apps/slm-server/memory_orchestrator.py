#!/usr/bin/env python3
"""
memory_orchestrator.py — In-Memory Orchestration Layer  (v3)

Changes from v2:
  - save_audit now takes (domain, policy_hash, report, chat_context, policy_url)
    matching audit_store.set() — no policyText anywhere.
  - get_chat_context() fast path reads pre-computed context string directly
    from the hot layer or audit_store; no JSON parsing on the hot chat path.
  - All chat rate-limiting lives here; audits are unlimited.
"""

import asyncio
import hashlib
import os
import time
from collections import OrderedDict, deque
from typing import Any, Dict, List, Optional, Tuple

from audit_store import audit_store


# ── Simple LRU-TTL cache ──────────────────────────────────────────────────────
class LRUTTLCache:
    def __init__(self, maxsize: int = 512, ttl: int = 300):
        self._cache: OrderedDict[str, Tuple[float, Any]] = OrderedDict()
        self._maxsize = maxsize
        self._ttl     = ttl
        self._lock    = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self._cache:
                return None
            exp, val = self._cache[key]
            if time.time() > exp:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return val

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self._cache.pop(key, None)
            if len(self._cache) >= self._maxsize:
                self._cache.popitem(last=False)
            self._cache[key] = (time.time() + self._ttl, value)

    async def get_or_set(self, key: str, value: Any) -> bool:
        """
        Atomic check-and-set in a single critical section. Returns True if
        `key` was already present (unexpired) — i.e. a collision/replay —
        and False if this call just inserted it fresh.

        The nonce-replay check below used to be `get()` then, separately,
        `set()` — two independently-locked calls, so two requests carrying
        the identical nonce dispatched close together could both pass the
        `get` before either finished the `set`, defeating the replay guard
        under exactly the concurrent load this server now needs to handle.
        """
        async with self._lock:
            if key in self._cache:
                exp, _ = self._cache[key]
                if time.time() <= exp:
                    self._cache.move_to_end(key)
                    return True
                del self._cache[key]
            elif len(self._cache) >= self._maxsize:
                self._cache.popitem(last=False)
            self._cache[key] = (time.time() + self._ttl, value)
            return False

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._cache.pop(key, None)


# ── Sliding-window rate limiter (chat only) ───────────────────────────────────
class SlidingWindowRateLimiter:
    def __init__(self, limit: int = 60, window: int = 60):
        self._limit   = limit
        self._window  = window
        self._reqs:   Dict[str, deque] = {}
        self._lock    = asyncio.Lock()

    async def check(self, identifier: str) -> Tuple[bool, int]:
        async with self._lock:
            now = time.time()
            dq  = self._reqs.setdefault(identifier, deque())
            while dq and dq[0] < now - self._window:
                dq.popleft()
            if len(dq) >= self._limit:
                return True, 0
            dq.append(now)
            return False, self._limit - len(dq)

    # Alias expected by security.py
    async def check_rate_limit(self, identifier: str) -> Tuple[bool, int]:
        return await self.check(identifier)


# ── Broadcast multiplexer for chat request coalescing ────────────────────────
class StreamBroadcaster:
    """
    Fans one leader's SSE generation out to N coalesced followers.

    Upgraded from token-only broadcasting: previously only raw generated
    tokens were broadcast, so a follower coalesced onto someone else's
    in-flight generation never received the 'citations' event (only the
    leader's own response got it) and had no way to learn if the leader's
    generation failed (e.g. the admission queue rejected it) — the follower
    would just hang until its own subscribe-side timeout, if any. Now every
    SSE-shaped event (citations / token / error / done) goes through the
    same `emit()` path and is replayed in order to any follower that
    subscribes late, including ones that subscribe after the leader has
    already finished (`is_done`).
    """
    def __init__(self):
        self._subs:    List[asyncio.Queue] = []
        self._history: List[Tuple[str, Any]] = []
        self.is_done   = False

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=8000)
        for event, data in self._history:
            q.put_nowait((event, data))
        if self.is_done:
            q.put_nowait(None)
        else:
            self._subs.append(q)
        return q

    async def emit(self, event: str, data: Any = None) -> None:
        self._history.append((event, data))
        for q in self._subs:
            if not q.full():
                q.put_nowait((event, data))

    async def close(self) -> None:
        self.is_done = True
        for q in self._subs:
            if not q.full():
                q.put_nowait(None)
        self._subs.clear()


# ── Manual admission queue (bounded concurrency + bounded FIFO wait line) ─────
class QueueSaturatedError(Exception):
    """Raised when the request can't be admitted — either the wait line
    itself is full (fail fast), or a slot never opened up before the wait
    timeout. Carries a `retry_after` seconds hint for the 503 response."""
    def __init__(self, waiting: int, max_concurrent: int, timed_out: bool = False):
        self.waiting = waiting
        self.timed_out = timed_out
        # Rough backoff hint: assume each in-flight request finishes in a
        # few seconds and a slot frees up roughly every (few sec / concurrency)
        # — deliberately conservative so clients don't all retry in lockstep.
        self.retry_after = 2 if timed_out else max(1, min(15, waiting // max(1, max_concurrent)))
        super().__init__(f"Queue saturated: {waiting} waiting, timed_out={timed_out}")


class InferenceQueue:
    """
    Manual bounded-concurrency admission queue in front of the vLLM engine's
    own internal continuous-batching scheduler.

    Why this exists: the old `check_circuit_breaker()` was a single counter
    compared against a ceiling — accept everything right up until
    `active_jobs_count == max_queue_depth`, then reject *everything* that
    arrives after, all at once, in lockstep. At low volume that's invisible.
    At 10k+ concurrent users, that's the difference between "load smooths
    out, most requests just wait a beat" and "the instant you cross the
    line, every request in that moment gets slammed with a 503 simultaneously,
    including ones that would have fit fine a second later once a slot freed
    up." This class replaces the single counter with an actual FIFO
    admission queue: a hard concurrency ceiling (`max_concurrent`, matched to
    the vLLM engine's own `max_num_seqs` so we're not under- or
    over-admitting relative to what the GPU scheduler can batch), plus a
    *separate*, explicitly bounded wait line (`max_waiting`) so a burst queues
    briefly instead of piling up unboundedly, plus a wait timeout so a
    request that's been waiting too long fails fast with a Retry-After
    instead of holding a client connection open indefinitely.

    NOTE — single-process scope: this queue lives in this one `uvicorn`
    process's memory, same as the old counter did. vLLM's `--workers 1`
    requirement means that's inherent to a single GPU replica; scaling past
    what one queue can smooth over means running more replicas (one per
    GPU) behind Nginx, each with its own queue sized to its own GPU's real
    concurrency — see docs/UPGRADES_2026_09_SCALING.md for the multi-replica
    Nginx/compose layout this queue is designed to sit behind.
    """

    def __init__(self, max_concurrent: int, max_waiting: int, max_queue_wait_seconds: float):
        self._sem = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent
        self.max_waiting = max_waiting
        self.max_queue_wait_seconds = max_queue_wait_seconds
        self._waiting = 0
        self._in_flight = 0
        self._admit_lock = asyncio.Lock()

    @property
    def waiting(self) -> int:
        return self._waiting

    @property
    def in_flight(self) -> int:
        return self._in_flight

    async def admit(self) -> None:
        async with self._admit_lock:
            if self._waiting >= self.max_waiting:
                raise QueueSaturatedError(self._waiting, self.max_concurrent)
            self._waiting += 1
        try:
            try:
                await asyncio.wait_for(self._sem.acquire(), timeout=self.max_queue_wait_seconds)
            except asyncio.TimeoutError:
                raise QueueSaturatedError(self._waiting, self.max_concurrent, timed_out=True)
        finally:
            async with self._admit_lock:
                self._waiting -= 1
        self._in_flight += 1

    def release(self) -> None:
        self._in_flight = max(0, self._in_flight - 1)
        self._sem.release()


# ── Global orchestrator ───────────────────────────────────────────────────────
class MemoryOrchestrator:
    def __init__(self):

        # Hot layer: (report, meta) tuples — 5-min TTL, 512 entries
        self._audit_hot:   LRUTTLCache = LRUTTLCache(maxsize=512, ttl=300)
        # Hot layer: pre-computed chat_context strings — 10-min TTL
        self._context_hot: LRUTTLCache = LRUTTLCache(maxsize=512, ttl=600)
        # Nonce replay store
        self._nonce_cache: LRUTTLCache = LRUTTLCache(maxsize=50_000, ttl=120)

        # Chat rate limiter (Redis if configured, in-process otherwise)
        self.using_redis = False
        try:
            from redis_limiter import build_rate_limiter
            built = build_rate_limiter(limit=60, window_seconds=60)
            # BUG FIX: build_rate_limiter() returns None (not an exception)
            # when SSENSE_REDIS_URL is unset/the redis package is missing, so
            # the old code set using_redis=True with self._chat_limiter=None
            # in that case — a live AttributeError waiting for the first chat
            # request, only masked because verify_rate_limiter_backend() happens
            # to also self-heal it on startup. Raise here instead so the
            # except branch below is the single place that falls back.
            if built is None:
                raise RuntimeError("SSENSE_REDIS_URL not configured or redis package unavailable")
            self._chat_limiter = built
            self.using_redis    = True
        except Exception as e:
            print(f"⚠️  [Orchestrator] Redis unavailable ({e}); using in-process chat limiter.")
            self._chat_limiter = SlidingWindowRateLimiter(limit=60, window=60)

        # Request coalescing for chat
        self.active_streams: Dict[str, StreamBroadcaster] = {}
        self._lock = asyncio.Lock()

        # Manual admission queue — replaces the old binary circuit-breaker
        # counter. max_concurrent should track the vLLM engine's
        # max_num_seqs (set per compute profile in engine.py); max_waiting
        # and the wait timeout are independently tunable for how much burst
        # you want to smooth vs. fail fast on.
        self.inference_queue = InferenceQueue(
            max_concurrent=int(os.getenv("SSENSE_MAX_CONCURRENT_INFERENCE", "32")),
            max_waiting=int(os.getenv("SSENSE_MAX_QUEUE_DEPTH", "5000")),
            max_queue_wait_seconds=float(os.getenv("SSENSE_MAX_QUEUE_WAIT_SECONDS", "20")),
        )

    @staticmethod
    def _normalise(domain: str) -> str:
        low = domain.strip().lower()
        for pfx in ("www.", "en.", "m.", "app."):
            if low.startswith(pfx):
                low = low[len(pfx):]
        return low

    async def verify_rate_limiter_backend(self) -> None:
        if self.using_redis:
            try:
                ok = await self._chat_limiter.ping()
                if not ok:
                    raise RuntimeError("ping failed")
                print("✅ [Orchestrator] Redis-backed chat limiter verified.")
            except Exception as e:
                print(f"🛑 [Orchestrator] Redis check failed ({e}); falling back to in-process.")
                self._chat_limiter = SlidingWindowRateLimiter(limit=60, window=60)
                self.using_redis   = False

    def compute_sha256(self, text: str, prefix: str = "gen") -> str:
        digest = hashlib.sha256(text.strip().encode()).hexdigest()
        return f"{prefix}:{digest}"

    # ── Nonce replay ──────────────────────────────────────────────────────
    async def check_nonce(self, nonce: str) -> bool:
        """Returns True if this nonce is fresh (not seen before), False if it's a replay."""
        was_seen = await self._nonce_cache.get_or_set(f"nonce:{nonce}", 1)
        return not was_seen

    # ── Chat rate limit ───────────────────────────────────────────────────
    async def enforce_chat_rate_limit(self, identifier: str) -> Tuple[bool, int]:
        return await self._chat_limiter.check_rate_limit(identifier)

    # ── Audit cache (two-tier) ────────────────────────────────────────────
    async def get_audit_for_domain(
        self,
        domain: str,
        policy_hash: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        if not force_refresh:
            hot = await self._audit_hot.get(f"audit:{self._normalise(domain)}")
            if hot is not None:
                report, meta = hot
                return report, {**meta, "source": "hot_cache"}

        result = await audit_store.get(domain, policy_hash=policy_hash, force_refresh=force_refresh)
        if result and not force_refresh:
            await self._audit_hot.set(f"audit:{self._normalise(domain)}", result)
        return result

    async def save_audit(
        self,
        domain: str,
        policy_hash: str,
        report: Dict[str, Any],
        chat_context: str,
        policy_url: str = "",
    ) -> None:
        await audit_store.set(domain, policy_hash, report, chat_context, policy_url)
        # Warm hot layer
        meta = {"source": "persistent_cache", "cached_at": int(time.time()), "age_days": 0.0,
                "policy_url": policy_url, "chat_context": chat_context}
        await self._audit_hot.set(f"audit:{self._normalise(domain)}", (report, meta))
        await self._context_hot.set(f"ctx:{self._normalise(domain)}", chat_context)

    async def get_chat_context(self, domain: str) -> Optional[str]:
        """Sub-millisecond hot path for injecting audit context into chat prompts."""
        ctx = await self._context_hot.get(f"ctx:{self._normalise(domain)}")
        if ctx:
            return ctx
        ctx = await audit_store.get_chat_context(domain)
        if ctx:
            await self._context_hot.set(f"ctx:{self._normalise(domain)}", ctx)
        return ctx

    async def invalidate_domain(self, domain: str) -> bool:
        key = self._normalise(domain)
        await self._audit_hot.delete(f"audit:{key}")
        await self._context_hot.delete(f"ctx:{key}")
        return await audit_store.delete(domain)

    # ── Chat request coalescing ───────────────────────────────────────────
    async def acquire_execution_lease(self, task_key: str) -> Tuple[bool, StreamBroadcaster]:
        async with self._lock:
            if task_key in self.active_streams:
                return False, self.active_streams[task_key]
            b = StreamBroadcaster()
            self.active_streams[task_key] = b
            return True, b

    async def cleanup_stream(self, task_key: str, b: StreamBroadcaster) -> None:
        async with self._lock:
            await b.close()
            self.active_streams.pop(task_key, None)

    # ── Circuit breaker (legacy alias — kept so /health and any other
    # callers that still read active_jobs_count-style stats don't break;
    # new code should use inference_queue directly) ────────────────────────
    async def check_circuit_breaker(self) -> Tuple[bool, int]:
        q = self.inference_queue
        return q.waiting >= q.max_waiting, q.in_flight

    @property
    def active_jobs_count(self) -> int:
        return self.inference_queue.in_flight


memory_orchestrator = MemoryOrchestrator()
