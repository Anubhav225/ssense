#!/usr/bin/env python3
"""
redis_limiter.py – Distributed Sliding-Window Rate Limiter (Redis-backed)

memory_orchestrator.SlidingWindowRateLimiter is correct but PER-PROCESS: since
Dockerfile.gpu/.cpu both run `uvicorn ... --workers 1` (a vLLM PagedAttention
requirement, not a choice), this is fine for a single instance. It stops being
fine the moment you run more than one slm-server replica behind Nginx, or
restart the container mid-traffic and want limits to survive the restart —
each process/restart would reset every client back to a fresh quota.

This module keeps the exact same semantics (per-key sliding window, atomic
check-and-increment) but backs them with Redis so the limit is shared and
durable across:
  - multiple slm-server replicas behind the same Nginx upstream
  - container restarts (Redis persists independently)
  - the Nginx layer itself, which can query the same Redis instance in future
    (e.g. via lua-resty or an auth_request subrequest) for one shared source
    of truth instead of two independently-configured limiters drifting apart.

Falls back to the existing in-memory limiter automatically if SSENSE_REDIS_URL
is unset or Redis is unreachable at boot, so this is a strict upgrade with no
new hard dependency for local/dev use.
"""

import os
import time
from typing import Tuple, Optional

try:
    import redis.asyncio as aioredis
    _REDIS_LIB_AVAILABLE = True
except ImportError:
    _REDIS_LIB_AVAILABLE = False


# Lua script: atomic sliding-window check-and-increment in a single round trip.
# ZSET per identifier, member = unique per-request token, score = timestamp.
# Avoids TOCTOU races that a separate GET-then-SET would allow under load.
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local count = redis.call('ZCARD', key)

if count >= limit then
    return {1, 0}
end

redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, window + 1)
return {0, limit - count - 1}
"""


class RedisSlidingWindowRateLimiter:
    """Drop-in replacement for memory_orchestrator.SlidingWindowRateLimiter."""

    def __init__(self, redis_url: str, limit: int = 60, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._redis = aioredis.from_url(redis_url, decode_responses=True)
        self._script = self._redis.register_script(_SLIDING_WINDOW_LUA)
        self._counter = 0

    async def check_rate_limit(self, identifier: str) -> Tuple[bool, int]:
        """Returns (is_rate_limited, remaining_requests). Matches the in-memory API."""
        now = time.time()
        # Unique member per call so retried/duplicate timestamps never collide
        # inside the ZSET (which would otherwise undercount distinct requests).
        self._counter += 1
        member = f"{now}:{self._counter}"
        key = f"ratelimit:{identifier}"
        is_limited, remaining = await self._script(
            keys=[key],
            args=[now, self.window_seconds, self.limit, member],
        )
        return bool(is_limited), int(remaining)

    async def ping(self) -> bool:
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False

    async def close(self):
        await self._redis.close()


def build_rate_limiter(limit: int = 60, window_seconds: int = 60):
    """
    Returns a RedisSlidingWindowRateLimiter if SSENSE_REDIS_URL is configured
    and the redis library is installed, else None (caller should fall back to
    the in-memory limiter in memory_orchestrator.py).

    NOTE: does not block on the connection here — connectivity is verified
    once via `await limiter.ping()` during the FastAPI lifespan startup in
    main.py, so a Redis outage at boot is detected loudly instead of failing
    silently on the first request.
    """
    redis_url = os.getenv("SSENSE_REDIS_URL", "").strip()
    if not redis_url:
        return None
    if not _REDIS_LIB_AVAILABLE:
        print("⚠️  [RateLimiter] SSENSE_REDIS_URL is set but the 'redis' package "
              "is not installed — falling back to in-memory rate limiting. "
              "Add `redis>=5.0` to requirements.txt to enable it.")
        return None
    return RedisSlidingWindowRateLimiter(redis_url, limit=limit, window_seconds=window_seconds)
