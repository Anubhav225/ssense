#!/usr/bin/env python3
"""
audit_store.py — Persistent SQLite Audit Cache  (v2)

Changes from v1:
  - Raw policy text is NEVER stored here. It is fetched server-side, used for
    inference, and immediately discarded after the report is written.
  - Added `chat_context` column: the pre-computed natural-language audit summary
    (output of translate_audit_for_prompt). Stored once, read on every chat
    request — avoids re-parsing the JSON report on the hot chat path.
  - `policy_hash` is now supplied by the caller (policy_fetcher computes it from
    the fetched text). On a cache-hit with a matching hash the full inference run
    is skipped even if the TTL hasn't expired yet.
  - `get()` signature simplified: takes only domain + optional policy_hash.
  - `set()` signature: (domain, policy_hash, report_dict, chat_context).

Schema (single table):
  audit_cache
    domain_key    TEXT PK  — normalised domain
    domain_raw    TEXT     — last submitted form
    report_json   TEXT     — validated DpdpAuditReport JSON
    chat_context  TEXT     — pre-computed natural-language audit summary
    trust_score   INTEGER  — denormalised for fast GET /v1/audit/{domain}
    policy_hash   TEXT     — SHA-256 of extracted policy text (change detection)
    policy_url    TEXT     — URL the policy was actually fetched from
    created_at    INTEGER  — first audit Unix timestamp
    updated_at    INTEGER  — last re-audit Unix timestamp
    audit_count   INTEGER  — total inferences run for this domain
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import aiosqlite

AUDIT_TTL_SECONDS   = 90 * 24 * 60 * 60   # 90 days
PRUNE_INTERVAL_S    = 6 * 60 * 60           # 6 hours


def _normalise(domain: str) -> str:
    low = domain.strip().lower()
    for prefix in ("https://", "http://"):
        if low.startswith(prefix):
            low = low[len(prefix):]
    low = low.split("/")[0].split("?")[0].split(":")[0]
    for prefix in ("www.", "en.", "m.", "app."):
        if low.startswith(prefix):
            low = low[len(prefix):]
    return low


def _now() -> int:
    return int(time.time())


class AuditStore:
    def __init__(self, db_path: Path):
        self._db_path   = Path(db_path)
        self._db: Optional[aiosqlite.Connection] = None
        self._prune_task: Optional[asyncio.Task] = None
        self._write_lock = asyncio.Lock()
        # In-memory hot cache for get_chat_context: domain -> (context, cached_timestamp)
        self._chat_context_cache: Dict[str, Tuple[str, float]] = {}

    async def find_audited_domain_by_name(self, name: str) -> Optional[str]:
        """Finds if a brand name or prefix matches an audited domain (e.g. 'zomato' -> 'zomato.com')."""
        name_clean = name.strip().lower()
        if not name_clean or len(name_clean) < 3:
            return None
        # Check direct common TLDs first
        for tld in (".com", ".in", ".org", ".co.in", ".io", ".net", ".ai"):
            candidate = f"{name_clean}{tld}"
            row = await self._fetch_row(candidate)
            if row:
                return candidate
        # Check prefix match in SQLite
        await self._ensure_db()
        if self._db:
            cur = await self._db.execute(
                "SELECT domain_key FROM audit_cache WHERE domain_key LIKE ? LIMIT 1",
                (f"{name_clean}.%",)
            )
            row = await cur.fetchone()
            if row:
                return row["domain_key"]
        return None

    async def _ensure_db(self) -> None:
        if self._db is None:
            await self.initialize()

    # ── Lifecycle ─────────────────────────────────────────────────────────
    async def initialize(self) -> None:
        if self._db is not None:
            return
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row

        await self._db.executescript("""
            PRAGMA journal_mode = WAL;
            PRAGMA synchronous  = NORMAL;
            PRAGMA busy_timeout = 5000;
            PRAGMA cache_size   = -16000;

            CREATE TABLE IF NOT EXISTS audit_cache (
                domain_key   TEXT    PRIMARY KEY,
                domain_raw   TEXT    NOT NULL,
                report_json  TEXT    NOT NULL,
                chat_context TEXT    NOT NULL DEFAULT '',
                trust_score  INTEGER NOT NULL DEFAULT 50,
                policy_hash  TEXT    NOT NULL DEFAULT '',
                policy_url   TEXT    NOT NULL DEFAULT '',
                created_at   INTEGER NOT NULL,
                updated_at   INTEGER NOT NULL,
                audit_count  INTEGER NOT NULL DEFAULT 1
            );

            -- Migrate: add columns that might not exist in an older DB
            -- (SQLite ignores "duplicate column" errors via IF NOT EXISTS)
            CREATE INDEX IF NOT EXISTS idx_updated_at ON audit_cache (updated_at);
        """)

        # Best-effort column migrations for existing databases
        for col, definition in [
            ("chat_context", "TEXT NOT NULL DEFAULT ''"),
            ("policy_url",   "TEXT NOT NULL DEFAULT ''"),
        ]:
            try:
                await self._db.execute(f"ALTER TABLE audit_cache ADD COLUMN {col} {definition}")
            except Exception:
                pass   # column already exists

        await self._db.commit()
        self._prune_task = asyncio.create_task(self._background_pruner())
        print(f"✅ [AuditStore] Persistent cache initialised → {self._db_path}")

    async def close(self) -> None:
        if self._prune_task:
            self._prune_task.cancel()
        if self._db:
            await self._db.close()

    # ── Public read (Lock-free concurrent readers under WAL mode) ─────────
    async def get(
        self,
        domain: str,
        policy_hash: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """
        Returns (report_dict, meta_dict) or None.

        Cache hit rules (in priority order):
          1. force_refresh=True  → always miss, caller must run inference.
          2. policy_hash supplied AND stored hash matches → hit regardless of age
             (same policy text → same result; no inference needed).
          3. Within 90-day TTL window → hit.
          4. Expired + hash mismatch → miss.
        """
        if force_refresh:
            return None

        key = _normalise(domain)
        row = await self._fetch_row(key)
        if row is None:
            return None

        age = _now() - row["updated_at"]
        hash_match = policy_hash and row["policy_hash"] and policy_hash == row["policy_hash"]

        if not hash_match and age > AUDIT_TTL_SECONDS:
            return None

        try:
            report = json.loads(row["report_json"])
        except json.JSONDecodeError:
            async with self._write_lock:
                await self._delete_row(key)
            return None

        meta = {
            "source":       "persistent_cache" + (":hash_match" if hash_match else ""),
            "cached_at":    row["updated_at"],
            "age_days":     round(age / 86400, 1),
            "audit_count":  row["audit_count"],
            "policy_url":   row["policy_url"],
            "chat_context": row["chat_context"],
        }
        return report, meta

    async def get_chat_context(self, domain: str) -> Optional[str]:
        """Fast path used by the chat endpoint — checks memory LRU cache first,
        then SQLite without reader locks under WAL mode."""
        key = _normalise(domain)
        now = _now()

        # 1. Hot memory check (5-minute TTL)
        cached = self._chat_context_cache.get(key)
        if cached is not None:
            ctx, ts = cached
            if now - ts <= 300:
                return ctx
            self._chat_context_cache.pop(key, None)

        # 2. SQLite fetch (lock-free)
        row = await self._fetch_row(key)
        if row is None:
            return None
        age = now - row["updated_at"]
        if age > AUDIT_TTL_SECONDS:
            return None
        ctx = row["chat_context"]
        if not ctx:
            return None

        # 3. Store in hot memory cache (bounded to 500 entries)
        if len(self._chat_context_cache) >= 500:
            oldest_key = min(self._chat_context_cache.keys(), key=lambda k: self._chat_context_cache[k][1])
            self._chat_context_cache.pop(oldest_key, None)
        self._chat_context_cache[key] = (ctx, now)

        return ctx

    # ── Public write (Protected by write_lock) ────────────────────────────
    async def set(
        self,
        domain: str,
        policy_hash: str,
        report: Dict[str, Any],
        chat_context: str,
        policy_url: str = "",
    ) -> None:
        """Upsert an audit result. Raw policy text is NOT a parameter here."""
        key         = _normalise(domain)
        trust_score = int(report.get("dpdp_trust_score", 50))
        report_json = json.dumps(report)
        now         = _now()

        async with self._write_lock:
            existing = await self._fetch_row(key)
            if existing:
                await self._db.execute(
                    """UPDATE audit_cache
                          SET domain_raw   = ?,
                              report_json  = ?,
                              chat_context = ?,
                              trust_score  = ?,
                              policy_hash  = ?,
                              policy_url   = ?,
                              updated_at   = ?,
                              audit_count  = audit_count + 1
                        WHERE domain_key  = ?""",
                    (domain, report_json, chat_context, trust_score,
                     policy_hash, policy_url, now, key),
                )
            else:
                await self._db.execute(
                    """INSERT INTO audit_cache
                           (domain_key, domain_raw, report_json, chat_context,
                            trust_score, policy_hash, policy_url,
                            created_at, updated_at, audit_count)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                    (key, domain, report_json, chat_context, trust_score,
                     policy_hash, policy_url, now, now),
                )
            await self._db.commit()

        # Update hot memory cache
        if chat_context:
            self._chat_context_cache[key] = (chat_context, now)

        print(f"💾 [AuditStore] Saved audit for {key} (score={trust_score})")

    async def delete(self, domain: str) -> bool:
        await self._ensure_db()
        key = _normalise(domain)
        self._chat_context_cache.pop(key, None)
        async with self._write_lock:
            cur = await self._db.execute(
                "DELETE FROM audit_cache WHERE domain_key = ?", (key,)
            )
            await self._db.commit()
        return cur.rowcount > 0

    async def stats(self) -> Dict[str, Any]:
        await self._ensure_db()
        cur  = await self._db.execute("SELECT COUNT(*) AS n FROM audit_cache")
        r1   = await cur.fetchone()
        cur2 = await self._db.execute(
            "SELECT COUNT(*) AS n FROM audit_cache WHERE updated_at <= ?",
            (_now() - AUDIT_TTL_SECONDS,),
        )
        r2 = await cur2.fetchone()
        return {
            "total_cached_domains":  r1["n"] if r1 else 0,
            "expired_pending_prune": r2["n"] if r2 else 0,
            "ttl_days": 90,
            "db_path": str(self._db_path),
        }

    # ── Internal ──────────────────────────────────────────────────────────
    async def _fetch_row(self, key: str):
        await self._ensure_db()
        cur = await self._db.execute(
            "SELECT * FROM audit_cache WHERE domain_key = ?", (key,)
        )
        return await cur.fetchone()

    async def _delete_row(self, key: str) -> None:
        await self._db.execute(
            "DELETE FROM audit_cache WHERE domain_key = ?", (key,)
        )
        await self._db.commit()

    async def _background_pruner(self) -> None:
        while True:
            await asyncio.sleep(PRUNE_INTERVAL_S)
            try:
                threshold = _now() - AUDIT_TTL_SECONDS
                async with self._write_lock:
                    cur = await self._db.execute(
                        "DELETE FROM audit_cache WHERE updated_at <= ?", (threshold,)
                    )
                    await self._db.commit()
                if cur.rowcount:
                    print(f"🧹 [AuditStore] Pruned {cur.rowcount} expired record(s)")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠️  [AuditStore] Pruner error: {e}")


# ── Module-level singleton ─────────────────────────────────────────────────────
import os
_default_path = Path(__file__).resolve().parent / "data" / "ssense_audit_cache.db"
audit_store   = AuditStore(
    db_path=Path(os.getenv("SSENSE_AUDIT_DB_PATH", str(_default_path)))
)
