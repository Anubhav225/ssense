#!/usr/bin/env python3
"""
user_store.py — Persistent SQLite User, Device & IP Registry for Ssense SLM Server

Provides:
  - Dynamic user registration on lab/on-premise servers (no domain required).
  - Cryptographically secure API key and HMAC secret provisioning.
  - Active client IP tracking across DHCP and WiFi roaming.
  - Device registry and access audit trails.
  - Fast O(1) in-memory cache for API key validation with zero DB overhead on hot paths.
  - SQLite WAL mode + 5000ms busy timeout for safe concurrent operation.
"""

import asyncio
import os
import secrets
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class UserStore:
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            data_dir = Path(os.getenv("SSENSE_DATA_DIR", str(Path(__file__).resolve().parent / "data")))
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = data_dir / "ssense_users.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = asyncio.Lock()
        # In-memory hot lookup cache: api_key -> user dict
        self._key_cache: Dict[str, Dict[str, Any]] = {}
        # In-memory email lookup: email -> user_id
        self._email_to_user_id: Dict[str, str] = {}
        self._initialized = False

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=5.0,
            check_same_thread=False,
            isolation_level=None,  # autocommit mode
        )
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.row_factory = sqlite3.Row
        return conn

    async def initialize(self) -> None:
        """Create tables if not existing and populate in-memory key cache."""
        async with self._lock:
            if self._initialized:
                return

            def _init_db():
                with self._get_connection() as conn:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            user_id TEXT PRIMARY KEY,
                            email TEXT UNIQUE NOT NULL,
                            display_name TEXT NOT NULL,
                            google_id TEXT,
                            avatar_url TEXT,
                            role TEXT DEFAULT 'user',
                            api_key TEXT UNIQUE NOT NULL,
                            hmac_secret TEXT NOT NULL,
                            status TEXT DEFAULT 'active',
                            created_at INTEGER NOT NULL,
                            last_seen_at INTEGER NOT NULL,
                            last_ip TEXT NOT NULL,
                            audit_count INTEGER DEFAULT 0,
                            chat_count INTEGER DEFAULT 0
                        );
                    """)
                    # Safe migrations for existing databases
                    for col_def in ("google_id TEXT", "avatar_url TEXT"):
                        try:
                            conn.execute(f"ALTER TABLE users ADD COLUMN {col_def};")
                        except Exception:
                            pass

                    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);")

                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS user_devices (
                            device_id TEXT PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            device_name TEXT,
                            client_ip TEXT NOT NULL,
                            user_agent TEXT,
                            registered_at INTEGER NOT NULL,
                            last_active_at INTEGER NOT NULL,
                            FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                        );
                    """)
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_devices_user ON user_devices(user_id);")

                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS user_ip_history (
                            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id TEXT NOT NULL,
                            ip_address TEXT NOT NULL,
                            timestamp INTEGER NOT NULL,
                            endpoint TEXT,
                            FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                        );
                    """)
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_ip_history_user ON user_ip_history(user_id);")

                    # Read all active users into memory cache
                    cursor = conn.execute("SELECT * FROM users WHERE status = 'active';")
                    rows = cursor.fetchall()
                    return [dict(r) for r in rows]

            loop = asyncio.get_running_loop()
            active_users = await loop.run_in_executor(None, _init_db)

            self._key_cache.clear()
            self._email_to_user_id.clear()
            for u in active_users:
                self._key_cache[u["api_key"]] = u
                self._email_to_user_id[u["email"].lower()] = u["user_id"]

            self._initialized = True
            print(f"✅ [UserStore] User database initialized ({len(self._key_cache)} active users) → {self.db_path}")

    async def register_user(
        self,
        email: str,
        display_name: str,
        client_ip: str,
        device_id: Optional[str] = None,
        device_name: Optional[str] = None,
        user_agent: Optional[str] = None,
        role: str = "user",
        google_id: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Register a new user or update an existing user's device/IP and Google identity.
        Returns credentials dict with apiKey and hmacSecret.
        """
        dev_id = device_id.strip() if device_id else str(uuid.uuid4())
        dev_name = device_name.strip() if device_name else "Unknown Device"
        ua = user_agent.strip() if user_agent else ""

        if not email or not email.strip():
            dev_slug = dev_id[:8]
            norm_email = f"reviewer_{dev_slug}@ssense.local"
            if not display_name or not display_name.strip():
                display_name = f"Guest Reviewer ({dev_slug})"
        else:
            norm_email = email.strip().lower()
            if not display_name or not display_name.strip():
                display_name = norm_email.split("@")[0].title()

        now = int(time.time())

        async with self._lock:
            def _sync_register():
                with self._get_connection() as conn:
                    # Check if user already exists
                    cursor = conn.execute("SELECT * FROM users WHERE email = ?;", (norm_email,))
                    row = cursor.fetchone()

                    if row:
                        user = dict(row)
                        user_id = user["user_id"]
                        api_key = user["api_key"]
                        hmac_secret = user["hmac_secret"]
                        g_id = google_id.strip() if google_id and google_id.strip() else user.get("google_id")
                        av_url = avatar_url.strip() if avatar_url and avatar_url.strip() else user.get("avatar_url")

                        # Update last seen, last IP, and Google identity
                        conn.execute("""
                            UPDATE users 
                            SET last_seen_at = ?, last_ip = ?, display_name = ?,
                                google_id = COALESCE(?, google_id),
                                avatar_url = COALESCE(?, avatar_url)
                            WHERE user_id = ?;
                        """, (now, client_ip, display_name or user["display_name"], g_id, av_url, user_id))

                        # Upsert device record
                        conn.execute("""
                            INSERT INTO user_devices (device_id, user_id, device_name, client_ip, user_agent, registered_at, last_active_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(device_id) DO UPDATE SET
                                client_ip = excluded.client_ip,
                                user_agent = excluded.user_agent,
                                last_active_at = excluded.last_active_at;
                        """, (dev_id, user_id, dev_name, client_ip, ua, now, now))

                        # Record IP history if changed
                        if user["last_ip"] != client_ip:
                            conn.execute("""
                                INSERT INTO user_ip_history (user_id, ip_address, timestamp, endpoint)
                                VALUES (?, ?, ?, 'register/re-handshake');
                            """, (user_id, client_ip, now))

                        user["display_name"] = display_name or user["display_name"]
                        user["last_seen_at"] = now
                        user["last_ip"] = client_ip
                        user["google_id"] = g_id
                        user["avatar_url"] = av_url
                        is_new = False
                    else:
                        # Create new user
                        user_id = f"usr_{uuid.uuid4().hex[:16]}"
                        api_key = f"ssk_live_{secrets.token_urlsafe(28)}"
                        hmac_secret = secrets.token_urlsafe(48)
                        g_id = google_id.strip() if google_id and google_id.strip() else None
                        av_url = avatar_url.strip() if avatar_url and avatar_url.strip() else None

                        conn.execute("""
                            INSERT INTO users (
                                user_id, email, display_name, google_id, avatar_url, role, api_key, hmac_secret,
                                status, created_at, last_seen_at, last_ip, audit_count, chat_count
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, 0, 0);
                        """, (user_id, norm_email, display_name, g_id, av_url, role, api_key, hmac_secret, now, now, client_ip))

                        conn.execute("""
                            INSERT INTO user_devices (
                                device_id, user_id, device_name, client_ip, user_agent, registered_at, last_active_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(device_id) DO UPDATE SET
                                user_id = excluded.user_id,
                                device_name = excluded.device_name,
                                client_ip = excluded.client_ip,
                                user_agent = excluded.user_agent,
                                last_active_at = excluded.last_active_at;
                        """, (dev_id, user_id, dev_name, client_ip, ua, now, now))

                        conn.execute("""
                            INSERT INTO user_ip_history (user_id, ip_address, timestamp, endpoint)
                            VALUES (?, ?, ?, 'register/new');
                        """, (user_id, client_ip, now))

                        user = {
                            "user_id": user_id,
                            "email": norm_email,
                            "display_name": display_name,
                            "google_id": g_id,
                            "avatar_url": av_url,
                            "role": role,
                            "api_key": api_key,
                            "hmac_secret": hmac_secret,
                            "status": "active",
                            "created_at": now,
                            "last_seen_at": now,
                            "last_ip": client_ip,
                            "audit_count": 0,
                            "chat_count": 0,
                        }
                        is_new = True

                    return user, is_new

            loop = asyncio.get_running_loop()
            user, is_new = await loop.run_in_executor(None, _sync_register)

            # Update in-memory caches
            self._key_cache[user["api_key"]] = user
            self._email_to_user_id[user["email"]] = user["user_id"]

            return {
                "is_new": is_new,
                "user_id": user["user_id"],
                "email": user["email"],
                "display_name": user["display_name"],
                "google_id": user.get("google_id"),
                "avatar_url": user.get("avatar_url"),
                "role": user["role"],
                "api_key": user["api_key"],
                "hmac_secret": user["hmac_secret"],
                "device_id": dev_id,
                "client_ip": client_ip,
                "created_at": user["created_at"],
            }

    def is_valid_api_key(self, api_key: str) -> bool:
        """Fast O(1) in-memory check if api_key is valid and active."""
        if not api_key:
            return False
        return api_key in self._key_cache

    def get_user_by_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Fast O(1) lookup of user profile from in-memory cache."""
        return self._key_cache.get(api_key)

    def get_hmac_secret_for_key(self, api_key: str) -> Optional[str]:
        """Returns the specific user's HMAC secret, or None if unknown."""
        user = self._key_cache.get(api_key)
        if user:
            return user.get("hmac_secret")
        return None

    async def record_activity(
        self,
        api_key: str,
        client_ip: str,
        endpoint: str = "",
        is_audit: bool = False,
        is_chat: bool = False,
    ) -> None:
        """
        Record request activity, update last_seen_at and last_ip.
        Detects laptop IP changes and logs to user_ip_history.
        """
        user = self._key_cache.get(api_key)
        if not user:
            return

        now = int(time.time())
        old_ip = user.get("last_ip", "")
        ip_changed = old_ip and old_ip != client_ip

        # Fast in-memory update
        user["last_seen_at"] = now
        if ip_changed:
            user["last_ip"] = client_ip

        if is_audit or "audit" in endpoint.lower():
            user["audit_count"] = user.get("audit_count", 0) + 1
        elif is_chat or "chat" in endpoint.lower():
            user["chat_count"] = user.get("chat_count", 0) + 1

        # Non-blocking async DB write
        def _update_db():
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE users 
                    SET last_seen_at = ?, last_ip = ?, audit_count = ?, chat_count = ?
                    WHERE api_key = ?;
                """, (now, client_ip, user.get("audit_count", 0), user.get("chat_count", 0), api_key))

                if ip_changed:
                    conn.execute("""
                        INSERT INTO user_ip_history (user_id, ip_address, timestamp, endpoint)
                        VALUES (?, ?, ?, ?);
                    """, (user["user_id"], client_ip, now, endpoint))

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _update_db)

    async def update_device_ip(
        self,
        api_key: str,
        client_ip: str,
        device_id: Optional[str] = None,
        device_name: Optional[str] = None,
    ) -> bool:
        """
        Update the current client IP for a registered user and device.
        Automatically logs to user_ip_history if changed.
        """
        user = self._key_cache.get(api_key)
        if not user:
            return False

        now = int(time.time())
        old_ip = user.get("last_ip", "")
        ip_changed = old_ip and old_ip != client_ip
        user["last_seen_at"] = now
        user["last_ip"] = client_ip
        user_id = user["user_id"]

        def _update():
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE users SET last_seen_at = ?, last_ip = ? WHERE user_id = ?;
                """, (now, client_ip, user_id))

                if device_id:
                    conn.execute("""
                        INSERT INTO user_devices (device_id, user_id, device_name, client_ip, user_agent, registered_at, last_active_at)
                        VALUES (?, ?, ?, ?, '', ?, ?)
                        ON CONFLICT(device_id) DO UPDATE SET
                            client_ip = excluded.client_ip,
                            last_active_at = excluded.last_active_at;
                    """, (device_id, user_id, device_name or "Active Device", client_ip, now, now))

                if ip_changed:
                    conn.execute("""
                        INSERT INTO user_ip_history (user_id, ip_address, timestamp, endpoint)
                        VALUES (?, ?, ?, 'roaming/ip_update');
                    """, (user_id, client_ip, now))
            return True

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _update)

    async def get_user_profile(
        self,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve complete user profile with associated devices and recent IP history."""
        target_user = None
        if api_key and api_key in self._key_cache:
            target_user = dict(self._key_cache[api_key])
        elif user_id:
            for u in self._key_cache.values():
                if u["user_id"] == user_id:
                    target_user = dict(u)
                    break

        if not target_user:
            def _find():
                with self._get_connection() as conn:
                    if user_id:
                        cur = conn.execute("SELECT * FROM users WHERE user_id = ?;", (user_id,))
                    elif api_key:
                        cur = conn.execute("SELECT * FROM users WHERE api_key = ?;", (api_key,))
                    else:
                        return None
                    row = cur.fetchone()
                    return dict(row) if row else None
            loop = asyncio.get_running_loop()
            target_user = await loop.run_in_executor(None, _find)

        if not target_user:
            return None

        uid = target_user["user_id"]
        devices = await self.get_user_devices(uid)

        def _get_history():
            with self._get_connection() as conn:
                cur = conn.execute("""
                    SELECT ip_address, timestamp, endpoint
                    FROM user_ip_history
                    WHERE user_id = ?
                    ORDER BY timestamp DESC
                    LIMIT 20;
                """, (uid,))
                return [dict(r) for r in cur.fetchall()]

        loop = asyncio.get_running_loop()
        history = await loop.run_in_executor(None, _get_history)

        return {
            "user": target_user,
            "devices": devices,
            "recent_ips": history,
        }

    async def list_users(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List registered users and their devices (for admin inspection)."""
        def _query():
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT user_id, email, display_name, role, status, created_at, last_seen_at, last_ip, audit_count, chat_count
                    FROM users
                    ORDER BY last_seen_at DESC
                    LIMIT ?;
                """, (limit,))
                return [dict(r) for r in cursor.fetchall()]

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _query)

    async def list_all_users(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Alias for list_users."""
        return await self.list_users(limit=limit)

    async def get_user_devices(self, user_id: str) -> List[Dict[str, Any]]:
        """List devices associated with a specific user."""
        def _query():
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT device_id, device_name, client_ip, user_agent, registered_at, last_active_at
                    FROM user_devices
                    WHERE user_id = ?
                    ORDER BY last_active_at DESC;
                """, (user_id,))
                return [dict(r) for r in cursor.fetchall()]

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _query)

    async def export_users_data(self) -> Dict[str, Any]:
        """
        Export all user records, registered devices, and IP audit trails
        as a structured dictionary for JSON backup and cross-instance migrations.
        """
        def _export():
            with self._get_connection() as conn:
                users = [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY created_at ASC;").fetchall()]
                devices = [dict(r) for r in conn.execute("SELECT * FROM user_devices ORDER BY registered_at ASC;").fetchall()]
                history = [dict(r) for r in conn.execute("SELECT * FROM user_ip_history ORDER BY timestamp ASC;").fetchall()]
                return {
                    "version": "1.0",
                    "exported_at": int(time.time()),
                    "total_users": len(users),
                    "total_devices": len(devices),
                    "total_ip_logs": len(history),
                    "users": users,
                    "devices": devices,
                    "ip_history": history,
                }

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _export)

    async def import_users_data(self, data: Dict[str, Any]) -> int:
        """
        Import users, devices, and IP history from a backup dictionary.
        Returns the number of user records imported or merged.
        """
        users = data.get("users", [])
        devices = data.get("devices", [])
        history = data.get("ip_history", [])

        async with self._lock:
            def _import():
                imported_count = 0
                with self._get_connection() as conn:
                    for u in users:
                        conn.execute("""
                            INSERT INTO users (
                                user_id, email, display_name, google_id, avatar_url, role,
                                api_key, hmac_secret, status, created_at, last_seen_at,
                                last_ip, audit_count, chat_count
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(user_id) DO UPDATE SET
                                email = excluded.email,
                                display_name = excluded.display_name,
                                google_id = COALESCE(excluded.google_id, users.google_id),
                                avatar_url = COALESCE(excluded.avatar_url, users.avatar_url),
                                last_seen_at = MAX(users.last_seen_at, excluded.last_seen_at),
                                audit_count = MAX(users.audit_count, excluded.audit_count),
                                chat_count = MAX(users.chat_count, excluded.chat_count);
                        """, (
                            u["user_id"], u["email"], u["display_name"],
                            u.get("google_id"), u.get("avatar_url"), u.get("role", "user"),
                            u["api_key"], u["hmac_secret"], u.get("status", "active"),
                            u.get("created_at", int(time.time())), u.get("last_seen_at", int(time.time())),
                            u.get("last_ip", "127.0.0.1"), u.get("audit_count", 0), u.get("chat_count", 0),
                        ))
                        imported_count += 1

                    for d in devices:
                        conn.execute("""
                            INSERT INTO user_devices (
                                device_id, user_id, device_name, client_ip, user_agent, registered_at, last_active_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(device_id) DO UPDATE SET
                                last_active_at = MAX(user_devices.last_active_at, excluded.last_active_at);
                        """, (
                            d["device_id"], d["user_id"], d.get("device_name", ""),
                            d.get("client_ip", ""), d.get("user_agent", ""),
                            d.get("registered_at", int(time.time())), d.get("last_active_at", int(time.time())),
                        ))

                    for h in history:
                        conn.execute("""
                            INSERT INTO user_ip_history (user_id, ip_address, timestamp, endpoint)
                            VALUES (?, ?, ?, ?);
                        """, (
                            h["user_id"], h["ip_address"], h.get("timestamp", int(time.time())), h.get("endpoint", "")
                        ))

                    cursor = conn.execute("SELECT * FROM users WHERE status = 'active';")
                    return imported_count, [dict(r) for r in cursor.fetchall()]

            loop = asyncio.get_running_loop()
            imported_count, active_users = await loop.run_in_executor(None, _import)

            self._key_cache.clear()
            self._email_to_user_id.clear()
            for u in active_users:
                self._key_cache[u["api_key"]] = u
                self._email_to_user_id[u["email"].lower()] = u["user_id"]

            return imported_count

    async def stats(self) -> Dict[str, Any]:
        """Aggregate statistics for health and monitoring probes."""
        def _query():
            with self._get_connection() as conn:
                cur_users = conn.execute("SELECT COUNT(*) FROM users;").fetchone()[0]
                cur_active = conn.execute("SELECT COUNT(*) FROM users WHERE status = 'active';").fetchone()[0]
                cur_devices = conn.execute("SELECT COUNT(*) FROM user_devices;").fetchone()[0]
                return {
                    "total_users": cur_users,
                    "active_users": cur_active,
                    "registered_devices": cur_devices,
                    "cached_keys_in_memory": len(self._key_cache),
                }

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _query)

    async def close(self) -> None:
        """Gracefully release user store resources."""
        self._key_cache.clear()
        self._email_to_user_id.clear()
        self._initialized = False


# Global singleton instance
user_store = UserStore()

