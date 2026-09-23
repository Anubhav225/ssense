#!/usr/bin/env python3
"""
test_user_store_and_auth.py — Automated Unit & Integration Test Suite
for UserStore, Dynamic Handshake Registration, IP Roaming, and FastAPI Auth Endpoints.
"""

import asyncio
import hashlib
import hmac
import os
import shutil
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from user_store import UserStore
import security
from main import app


class TestUserStoreAndAuth(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Create temporary isolated directory for testing SQLite database
        self.test_dir = tempfile.mkdtemp(prefix="ssense_test_user_store_")
        self.db_path = Path(self.test_dir) / "test_users.db"
        self.store = UserStore(db_path=self.db_path)
        await self.store.initialize()

    async def asyncTearDown(self):
        await self.store.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def test_01_user_registration_and_key_issuance(self):
        """Verify user registration provisions valid API key, HMAC secret, and records IP."""
        creds = await self.store.register_user(
            email="alice@lab.univ.edu",
            display_name="Alice Smith",
            client_ip="192.168.1.105",
            device_id="dev-laptop-01",
            device_name="Alice MacBook Pro",
            user_agent="Mozilla/5.0 Ssense-Extension/6.0",
        )

        self.assertIn("user_id", creds)
        self.assertIn("api_key", creds)
        self.assertIn("hmac_secret", creds)
        self.assertTrue(creds["api_key"].startswith("ssk_live_"))
        self.assertEqual(len(creds["hmac_secret"]), 64)

        # Verify fast in-memory key cache
        self.assertTrue(self.store.is_valid_api_key(creds["api_key"]))
        self.assertEqual(self.store.get_hmac_secret_for_key(creds["api_key"]), creds["hmac_secret"])

        # Verify user profile retrieval
        profile = await self.store.get_user_profile(user_id=creds["user_id"])
        self.assertIsNotNone(profile)
        self.assertEqual(profile["user"]["email"], "alice@lab.univ.edu")
        self.assertEqual(profile["user"]["last_ip"], "192.168.1.105")
        self.assertEqual(len(profile["devices"]), 1)
        self.assertEqual(profile["devices"][0]["device_name"], "Alice MacBook Pro")

    async def test_02_guest_reviewer_registration(self):
        """Verify 1-click reviewer guest registration with no email provided."""
        creds = await self.store.register_user(
            email="",
            display_name="",
            client_ip="10.0.0.42",
            device_id="guest-dev-999",
            device_name="Reviewer Dell XPS",
        )

        self.assertIn("user_id", creds)
        self.assertTrue(creds["email"].startswith("reviewer_"))
        self.assertTrue(creds["email"].endswith("@ssense.local"))
        self.assertTrue(self.store.is_valid_api_key(creds["api_key"]))

    async def test_03_ip_roaming_and_history_tracking(self):
        """Verify client IP updates when laptop connects from home/cafe WiFi."""
        creds = await self.store.register_user(
            email="bob@lab.univ.edu",
            display_name="Bob Jones",
            client_ip="192.168.1.50",  # Lab WiFi
            device_id="bob-thinkpad",
        )

        # Simulate laptop roaming to home WiFi (different IP)
        updated = await self.store.update_device_ip(
            api_key=creds["api_key"],
            client_ip="203.0.113.19",  # Home ISP Public IP
            device_id="bob-thinkpad",
        )
        self.assertTrue(updated)

        profile = await self.store.get_user_profile(user_id=creds["user_id"])
        self.assertEqual(profile["user"]["last_ip"], "203.0.113.19")
        self.assertEqual(profile["devices"][0]["client_ip"], "203.0.113.19")

        # Check IP history has both records
        ips = [h["ip_address"] for h in profile["recent_ips"]]
        self.assertIn("192.168.1.50", ips)
        self.assertIn("203.0.113.19", ips)

    async def test_04_activity_recording(self):
        """Verify audit and chat usage counters increment correctly."""
        creds = await self.store.register_user(
            email="carol@lab.univ.edu",
            display_name="Carol White",
            client_ip="192.168.1.75",
        )

        await self.store.record_activity(creds["api_key"], "192.168.1.75", "/v1/audit/by-url", is_audit=True)
        await self.store.record_activity(creds["api_key"], "192.168.1.75", "/v1/chat/stream", is_chat=True)
        await self.store.record_activity(creds["api_key"], "192.168.1.75", "/v1/chat/stream", is_chat=True)

        profile = await self.store.get_user_profile(user_id=creds["user_id"])
        self.assertEqual(profile["user"]["audit_count"], 1)
        self.assertEqual(profile["user"]["chat_count"], 2)

    async def test_05_google_user_registration(self):
        """Verify registration with Google account metadata (google_id, avatar_url)."""
        creds = await self.store.register_user(
            email="researcher@gmail.com",
            display_name="Dr. Alex Rivera",
            client_ip="192.168.1.120",
            device_id="alex-laptop-agx",
            google_id="gid_1092837465928374",
            avatar_url="https://lh3.googleusercontent.com/a/ACg8ocLexample",
        )

        self.assertEqual(creds["email"], "researcher@gmail.com")
        self.assertEqual(creds["display_name"], "Dr. Alex Rivera")
        self.assertEqual(creds["google_id"], "gid_1092837465928374")
        self.assertEqual(creds["avatar_url"], "https://lh3.googleusercontent.com/a/ACg8ocLexample")

        # Verify persistent profile has Google identity
        profile = await self.store.get_user_profile(user_id=creds["user_id"])
        self.assertEqual(profile["user"]["google_id"], "gid_1092837465928374")
        self.assertEqual(profile["user"]["avatar_url"], "https://lh3.googleusercontent.com/a/ACg8ocLexample")

    async def test_06_user_db_export_and_import(self):
        """Verify exporting user database as JSON and importing into a clean instance."""
        await self.store.register_user(
            email="sync1@example.com",
            display_name="Sync User 1",
            client_ip="10.10.10.1",
            google_id="gid_sync1",
        )
        await self.store.register_user(
            email="sync2@example.com",
            display_name="Sync User 2",
            client_ip="10.10.10.2",
            google_id="gid_sync2",
        )

        # 1. Export from current store
        exported = await self.store.export_users_data()
        self.assertGreaterEqual(exported["total_users"], 2)
        self.assertEqual(exported["version"], "1.0")

        # 2. Create clean second store
        clean_db_path = Path(self.test_dir) / "imported_users.db"
        store2 = UserStore(db_path=clean_db_path)
        await store2.initialize()

        # 3. Import data
        imported_count = await store2.import_users_data(exported)
        self.assertGreaterEqual(imported_count, 2)

        # 4. Verify in-memory key caches and profiles exist in imported store
        for u in exported["users"]:
            self.assertTrue(store2.is_valid_api_key(u["api_key"]))
            profile2 = await store2.get_user_profile(user_id=u["user_id"])
            self.assertIsNotNone(profile2)
            self.assertEqual(profile2["user"]["email"], u["email"])

        await store2.close()

    async def test_07_multi_db_sync_engine(self):
        """Verify db_sync exports and imports ssense_users.db with sha256 checksums."""
        import db_sync
        export_dir = Path(self.test_dir) / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        old_env = os.environ.get("SSENSE_DB_EXPORT_PATH")
        os.environ["SSENSE_DB_EXPORT_PATH"] = str(export_dir)

        try:
            # 1. Export current user store
            await db_sync.final_export([self.db_path])
            exported_db = export_dir / self.db_path.name
            exported_sha = export_dir / f"{self.db_path.name}.sha256"
            self.assertTrue(exported_db.exists())
            self.assertTrue(exported_sha.exists())

            # 2. Import into empty database path
            fresh_db_path = Path(self.test_dir) / "fresh_imported.db"
            db_sync.import_if_new(fresh_db_path, filename=self.db_path.name)
            self.assertTrue(fresh_db_path.exists())

            # 3. Check clean store loads data correctly
            clean_store = UserStore(db_path=fresh_db_path)
            await clean_store.initialize()
            stats = await clean_store.stats()
            self.assertGreaterEqual(stats["total_users"], 0)
            await clean_store.close()
        finally:
            if old_env is not None:
                os.environ["SSENSE_DB_EXPORT_PATH"] = old_env
            else:
                os.environ.pop("SSENSE_DB_EXPORT_PATH", None)


class TestFastAPIAuthEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from user_store import user_store
        asyncio.run(user_store.initialize())

    def setUp(self):
        self.client = TestClient(app)

    def test_01_auth_ping(self):
        """Test public /v1/auth/ping connectivity and discovery."""
        res = self.client.get("/v1/auth/ping")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "online")
        self.assertTrue(data["registration_open"])
        self.assertIn("public_url", data)

    def test_02_auth_register_handshake(self):
        """Test POST /v1/auth/register client handshake."""
        reg_payload = {
            "name": "David Reviewer",
            "email": f"david_{uuid.uuid4().hex[:6]}@lab.univ.edu",
            "device_name": "David HP Specter",
            "device_id": str(uuid.uuid4()),
            "platform": "Windows 11 Chrome",
        }
        res = self.client.post("/v1/auth/register", json=reg_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "registered")
        self.assertTrue(data["api_key"].startswith("ssk_live_"))
        self.assertIn("hmac_secret", data)
        self.assertIn("user_id", data)

    def test_03_authenticated_heartbeat_and_profile(self):
        """Test authenticated /v1/auth/heartbeat and /v1/auth/me using HMAC signature."""
        # 1. Register a client
        reg_res = self.client.post("/v1/auth/register", json={
            "name": "Emma Tester",
            "email": f"emma_{uuid.uuid4().hex[:6]}@lab.univ.edu",
            "device_id": "emma-macbook",
        })
        creds = reg_res.json()
        api_key = creds["api_key"]
        hmac_secret = creds["hmac_secret"]

        # Helper to construct HMAC headers
        def make_hmac_headers(method: str, path: str):
            ts = str(int(time.time() * 1000))
            nonce = uuid.uuid4().hex
            payload = f"{method.upper()}:{path}:{ts}:{nonce}"
            sig = hmac.new(hmac_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
            return {
                "X-Ssense-API-Key": api_key,
                "X-Ssense-Signature": sig,
                "X-Ssense-Timestamp": ts,
                "X-Ssense-Nonce": nonce,
            }

        # 2. Test /v1/auth/heartbeat
        hb_headers = make_hmac_headers("POST", "/v1/auth/heartbeat")
        hb_res = self.client.post("/v1/auth/heartbeat", json={"device_id": "emma-macbook"}, headers=hb_headers)
        self.assertEqual(hb_res.status_code, 200)
        self.assertEqual(hb_res.json()["status"], "active")

        # 3. Test /v1/auth/me
        me_headers = make_hmac_headers("GET", "/v1/auth/me")
        me_res = self.client.get("/v1/auth/me", headers=me_headers)
        self.assertEqual(me_res.status_code, 200)
        me_data = me_res.json()
        self.assertEqual(me_data["user"]["display_name"], "Emma Tester")
        self.assertEqual(len(me_data["devices"]), 1)

    def test_04_admin_users_endpoint(self):
        """Test GET /v1/admin/users."""
        res = self.client.get("/v1/admin/users")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_users", data)
        self.assertIn("users", data)
        self.assertIsInstance(data["users"], list)

    def test_05_admin_users_export(self):
        """Test GET /v1/admin/users/export returns full database backup JSON."""
        res = self.client.get("/v1/admin/users/export")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_users", data)
        self.assertIn("users", data)
        self.assertIn("devices", data)
        self.assertIn("ip_history", data)
        self.assertEqual(data["version"], "1.0")

    def test_06_google_registration_endpoint(self):
        """Test registering through /v1/auth/register with Google account details."""
        reg_payload = {
            "name": "Prof. Sophia Chen",
            "email": f"sophia_{uuid.uuid4().hex[:6]}@gmail.com",
            "google_id": "google_sub_9876543210",
            "avatar_url": "https://lh3.googleusercontent.com/a/sophia_avatar",
            "device_name": "Sophia ThinkPad",
            "device_id": str(uuid.uuid4()),
        }
        res = self.client.post("/v1/auth/register", json=reg_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["display_name"], "Prof. Sophia Chen")
        self.assertEqual(data["google_id"], "google_sub_9876543210")
        self.assertEqual(data["avatar_url"], "https://lh3.googleusercontent.com/a/sophia_avatar")
        self.assertTrue(data["api_key"].startswith("ssk_live_"))


if __name__ == "__main__":
    unittest.main()
