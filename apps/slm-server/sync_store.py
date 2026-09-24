#!/usr/bin/env python3
"""
sync_store.py — Per-account cross-device sync for Ssense audit history.

Each signed-in user owns a private set of "site records" (one per domain) plus
one preferences blob.  Devices push what changed since their last sync and pull
what other devices changed.  Conflict rule: last-writer-wins per domain, judged
by the record's `updated_at` (epoch ms).  Records are opaque JSON to the server
apart from size limits, so the extension can evolve the shape freely.

Only audit *results* and usage counters are stored — never page content.
"""

import asyncio
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

MAX_RECORD_BYTES = 96 * 1024
MAX_SITES_PER_USER = 2000
MAX_PREFS_BYTES = 16 * 1024


class SyncStore:
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            data_dir = Path(os.getenv("SSENSE_DATA_DIR", str(Path(__file__).resolve().parent / "data")))
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = data_dir / "ssense_sync.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._ready = False

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.db_path), timeout=5.0, check_same_thread=False, isolation_level=None)
        c.execute("PRAGMA journal_mode=WAL;")
        c.execute("PRAGMA synchronous=NORMAL;")
        c.execute("PRAGMA busy_timeout=5000;")
        c.row_factory = sqlite3.Row
        return c

    async def initialize(self) -> None:
        async with self._lock:
            if self._ready:
                return

            def _init():
                with self._conn() as c:
                    c.execute(
                        """CREATE TABLE IF NOT EXISTS sync_sites (
                            user_id TEXT NOT NULL,
                            domain TEXT NOT NULL,
                            updated_at INTEGER NOT NULL,
                            server_seq INTEGER NOT NULL,
                            payload TEXT NOT NULL,
                            PRIMARY KEY (user_id, domain)
                        );"""
                    )
                    c.execute("CREATE INDEX IF NOT EXISTS idx_sync_seq ON sync_sites(user_id, server_seq);")
                    c.execute(
                        """CREATE TABLE IF NOT EXISTS sync_prefs (
                            user_id TEXT PRIMARY KEY,
                            updated_at INTEGER NOT NULL,
                            server_seq INTEGER NOT NULL,
                            payload TEXT NOT NULL
                        );"""
                    )

            await asyncio.get_running_loop().run_in_executor(None, _init)
            self._ready = True

    # A monotonically increasing per-write sequence lets clients pull "everything
    # after cursor N" without depending on device clocks being in agreement.
    @staticmethod
    def _next_seq(c: sqlite3.Connection, user_id: str) -> int:
        a = c.execute("SELECT COALESCE(MAX(server_seq),0) FROM sync_sites WHERE user_id=?", (user_id,)).fetchone()[0]
        b = c.execute("SELECT COALESCE(MAX(server_seq),0) FROM sync_prefs WHERE user_id=?", (user_id,)).fetchone()[0]
        return max(a, b) + 1

    async def push(
        self,
        user_id: str,
        sites: List[Dict[str, Any]],
        prefs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        await self.initialize()
        async with self._lock:

            def _do():
                accepted = rejected = 0
                with self._conn() as c:
                    c.execute("BEGIN IMMEDIATE;")
                    try:
                        seq = self._next_seq(c, user_id)
                        for s in sites:
                            domain = str(s.get("domain", "")).strip().lower()[:253]
                            updated_at = int(s.get("updated_at", 0))
                            data = s.get("data")
                            if not domain or updated_at <= 0 or not isinstance(data, dict):
                                rejected += 1
                                continue
                            blob = json.dumps(data, separators=(",", ":"))
                            if len(blob.encode("utf-8")) > MAX_RECORD_BYTES:
                                rejected += 1
                                continue
                            row = c.execute(
                                "SELECT updated_at FROM sync_sites WHERE user_id=? AND domain=?",
                                (user_id, domain),
                            ).fetchone()
                            if row and row["updated_at"] > updated_at:
                                continue  # server copy is newer; client will receive it on pull
                            c.execute(
                                """INSERT INTO sync_sites(user_id,domain,updated_at,server_seq,payload)
                                   VALUES(?,?,?,?,?)
                                   ON CONFLICT(user_id,domain) DO UPDATE SET
                                     updated_at=excluded.updated_at,
                                     server_seq=excluded.server_seq,
                                     payload=excluded.payload;""",
                                (user_id, domain, updated_at, seq, blob),
                            )
                            accepted += 1
                            seq += 1

                        if prefs and isinstance(prefs.get("data"), dict):
                            p_at = int(prefs.get("updated_at", 0))
                            p_blob = json.dumps(prefs["data"], separators=(",", ":"))
                            if p_at > 0 and len(p_blob.encode("utf-8")) <= MAX_PREFS_BYTES:
                                row = c.execute(
                                    "SELECT updated_at FROM sync_prefs WHERE user_id=?", (user_id,)
                                ).fetchone()
                                if not row or row["updated_at"] <= p_at:
                                    c.execute(
                                        """INSERT INTO sync_prefs(user_id,updated_at,server_seq,payload)
                                           VALUES(?,?,?,?)
                                           ON CONFLICT(user_id) DO UPDATE SET
                                             updated_at=excluded.updated_at,
                                             server_seq=excluded.server_seq,
                                             payload=excluded.payload;""",
                                        (user_id, p_at, seq, p_blob),
                                    )
                                    seq += 1

                        # Bound per-user storage: drop the least recently updated records.
                        count = c.execute("SELECT COUNT(*) FROM sync_sites WHERE user_id=?", (user_id,)).fetchone()[0]
                        if count > MAX_SITES_PER_USER:
                            c.execute(
                                """DELETE FROM sync_sites WHERE user_id=? AND domain IN (
                                     SELECT domain FROM sync_sites WHERE user_id=?
                                     ORDER BY updated_at ASC LIMIT ?)""",
                                (user_id, user_id, count - MAX_SITES_PER_USER),
                            )
                        c.execute("COMMIT;")
                    except Exception:
                        c.execute("ROLLBACK;")
                        raise
                return {"accepted": accepted, "rejected": rejected}

            return await asyncio.get_running_loop().run_in_executor(None, _do)

    async def pull(self, user_id: str, cursor: int = 0, limit: int = 500) -> Dict[str, Any]:
        await self.initialize()

        def _do():
            with self._conn() as c:
                rows = c.execute(
                    """SELECT domain, updated_at, server_seq, payload FROM sync_sites
                       WHERE user_id=? AND server_seq>? ORDER BY server_seq ASC LIMIT ?""",
                    (user_id, cursor, limit + 1),
                ).fetchall()
                has_more = len(rows) > limit
                rows = rows[:limit]
                sites = [
                    {"domain": r["domain"], "updated_at": r["updated_at"], "data": json.loads(r["payload"])}
                    for r in rows
                ]
                new_cursor = rows[-1]["server_seq"] if rows else cursor
                prefs = None
                if not has_more:
                    pr = c.execute(
                        "SELECT updated_at, server_seq, payload FROM sync_prefs WHERE user_id=? AND server_seq>?",
                        (user_id, cursor),
                    ).fetchone()
                    if pr:
                        prefs = {"updated_at": pr["updated_at"], "data": json.loads(pr["payload"])}
                        new_cursor = max(new_cursor, pr["server_seq"])
                return {"sites": sites, "prefs": prefs, "cursor": new_cursor, "has_more": has_more}

        return await asyncio.get_running_loop().run_in_executor(None, _do)

    async def delete_all(self, user_id: str) -> int:
        await self.initialize()
        async with self._lock:

            def _do():
                with self._conn() as c:
                    n = c.execute("DELETE FROM sync_sites WHERE user_id=?", (user_id,)).rowcount
                    c.execute("DELETE FROM sync_prefs WHERE user_id=?", (user_id,))
                    return n

            return await asyncio.get_running_loop().run_in_executor(None, _do)

    async def count(self, user_id: str) -> int:
        await self.initialize()

        def _do():
            with self._conn() as c:
                return c.execute("SELECT COUNT(*) FROM sync_sites WHERE user_id=?", (user_id,)).fetchone()[0]

        return await asyncio.get_running_loop().run_in_executor(None, _do)


sync_store = SyncStore()
