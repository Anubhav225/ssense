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
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import aiosqlite

AUDIT_TTL_SECONDS   = 90 * 24 * 60 * 60   # 90 days
PRUNE_INTERVAL_S    = 6 * 60 * 60           # 6 hours


def _normalise(domain: str) -> str:
    low = domain.strip().lower()
    for prefix in ("www.", "en.", "m.", "app."):
        if low.startswith(prefix):
            low = low[len(prefix):]
    return low


def _now() -> int:
    return int(time.time())


class AuditStore:
    def __init__(self, db_path: Path):
        self._db_path   = db_path
        self._db: Optional[aiosqlite.Connection] = None
        self._prune_task: Optional[asyncio.Task] = None
        self._lock      = asyncio.Lock()

    # ── Lifecycle ─────────────────────────────────────────────────────────
    async def initialize(self) -> None:
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

    # ── Public read ───────────────────────────────────────────────────────
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

        async with self._lock:
            row = await self._fetch_row(_normalise(domain))
        if row is None:
            return None

        age = _now() - row["updated_at"]
        hash_match = policy_hash and row["policy_hash"] and policy_hash == row["policy_hash"]

        if not hash_match and age > AUDIT_TTL_SECONDS:
            return None

        try:
            report = json.loads(row["report_json"])
        except json.JSONDecodeError:
            await self._delete_row(_normalise(domain))
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
        """Fast path used by the chat endpoint — returns only the pre-computed
        natural-language summary without loading the full report JSON."""
        async with self._lock:
            row = await self._fetch_row(_normalise(domain))
        if row is None:
            return None
        age = _now() - row["updated_at"]
        if age > AUDIT_TTL_SECONDS:
            return None
        ctx = row["chat_context"]
        return ctx if ctx else None

    # ── Public write ──────────────────────────────────────────────────────
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

        async with self._lock:
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

        print(f"💾 [AuditStore] Saved audit for {key} (score={trust_score})")

    async def delete(self, domain: str) -> bool:
        key = _normalise(domain)
        async with self._lock:
            cur = await self._db.execute(
                "DELETE FROM audit_cache WHERE domain_key = ?", (key,)
            )
            await self._db.commit()
        return cur.rowcount > 0

    async def stats(self) -> Dict[str, Any]:
        async with self._lock:
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
        cur = await self._db.execute(
            "SELECT * FROM audit_cache WHERE domain_key = ?", (key,)
        )
        return await cur.fetchone()

    async def _delete_row(self, key: str) -> None:
        async with self._lock:
            await self._db.execute(
                "DELETE FROM audit_cache WHERE domain_key = ?", (key,)
            )
            await self._db.commit()

    async def _background_pruner(self) -> None:
        while True:
            await asyncio.sleep(PRUNE_INTERVAL_S)
            try:
                threshold = _now() - AUDIT_TTL_SECONDS
                async with self._lock:
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
