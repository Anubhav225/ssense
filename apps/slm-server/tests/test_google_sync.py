"""Tests for verified Google sign-in and per-account sync (no GPU/model deps)."""
import asyncio
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

import google_auth
from google_auth import GoogleAuthError, verify_google_token
from sync_store import SyncStore, MAX_RECORD_BYTES

TOKEN = "ya29." + "a" * 40
CLIENT_ID = "1234-abc.apps.googleusercontent.com"


def _client(tokeninfo: dict, status=200, userinfo=None):
    def handler(req: httpx.Request):
        if "tokeninfo" in str(req.url):
            return httpx.Response(status, json=tokeninfo)
        return httpx.Response(200, json=userinfo or {"name": "Ada Lovelace", "picture": "https://x/y.png"})
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class TestGoogleVerify(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        p = patch.dict(os.environ, {"SSENSE_GOOGLE_CLIENT_IDS": CLIENT_ID}, clear=False)
        p.start()
        self.addCleanup(p.stop)

    async def test_valid_access_token(self):
        c = _client({"aud": CLIENT_ID, "email": "Ada@Gmail.com", "email_verified": "true", "sub": "42"})
        ident = await verify_google_token(TOKEN, client=c)
        self.assertEqual(ident.email, "ada@gmail.com")
        self.assertEqual(ident.sub, "42")
        self.assertEqual(ident.name, "Ada Lovelace")

    async def test_wrong_audience_rejected(self):
        c = _client({"aud": "someone-else", "email": "a@b.com", "email_verified": "true", "sub": "1"})
        with self.assertRaises(GoogleAuthError) as cm:
            await verify_google_token(TOKEN, client=c)
        self.assertEqual(cm.exception.status_code, 401)

    async def test_unverified_email_rejected(self):
        c = _client({"aud": CLIENT_ID, "email": "a@b.com", "email_verified": "false", "sub": "1"})
        with self.assertRaises(GoogleAuthError):
            await verify_google_token(TOKEN, client=c)

    async def test_google_rejects_token(self):
        c = _client({"error": "invalid_token"}, status=400)
        with self.assertRaises(GoogleAuthError):
            await verify_google_token(TOKEN, client=c)

    async def test_unconfigured_server_refuses(self):
        with patch.dict(os.environ, {"SSENSE_GOOGLE_CLIENT_IDS": "", "SSENSE_GOOGLE_SKIP_AUD_CHECK": ""}):
            with self.assertRaises(GoogleAuthError) as cm:
                await verify_google_token(TOKEN, client=_client({}))
            self.assertEqual(cm.exception.status_code, 503)

    async def test_malformed_token(self):
        with self.assertRaises(GoogleAuthError) as cm:
            await verify_google_token("short")
        self.assertEqual(cm.exception.status_code, 400)


class TestSyncStore(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dir = tempfile.mkdtemp(prefix="ssense_sync_")
        self.store = SyncStore(Path(self.dir) / "s.db")
        await self.store.initialize()

    async def asyncTearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def rec(self, d, at, score=50):
        return {"domain": d, "updated_at": at, "data": {"lastScore": score}}

    async def test_roundtrip_and_cursor(self):
        r = await self.store.push("u1", [self.rec("a.com", 100), self.rec("b.com", 101)], {"updated_at": 5, "data": {"autoScan": True}})
        self.assertEqual(r["accepted"], 2)
        out = await self.store.pull("u1", 0)
        self.assertEqual({s["domain"] for s in out["sites"]}, {"a.com", "b.com"})
        self.assertEqual(out["prefs"]["data"], {"autoScan": True})
        again = await self.store.pull("u1", out["cursor"])
        self.assertEqual(again["sites"], [])
        self.assertIsNone(again["prefs"])

    async def test_last_writer_wins(self):
        await self.store.push("u1", [self.rec("a.com", 200, score=90)])
        r = await self.store.push("u1", [self.rec("a.com", 100, score=10)])  # stale
        self.assertEqual(r["accepted"], 0)
        out = await self.store.pull("u1", 0)
        self.assertEqual(out["sites"][0]["data"]["lastScore"], 90)

    async def test_users_are_isolated(self):
        await self.store.push("u1", [self.rec("a.com", 1)])
        self.assertEqual((await self.store.pull("u2", 0))["sites"], [])

    async def test_oversize_and_invalid_rejected(self):
        big = {"domain": "x.com", "updated_at": 1, "data": {"blob": "z" * (MAX_RECORD_BYTES + 10)}}
        bad = {"domain": "", "updated_at": 1, "data": {}}
        r = await self.store.push("u1", [big, bad])
        self.assertEqual(r["rejected"], 2)

    async def test_pagination(self):
        await self.store.push("u1", [self.rec(f"s{i}.com", 10 + i) for i in range(5)])
        p1 = await self.store.pull("u1", 0, limit=3)
        self.assertTrue(p1["has_more"])
        p2 = await self.store.pull("u1", p1["cursor"], limit=3)
        self.assertFalse(p2["has_more"])
        self.assertEqual(len(p1["sites"]) + len(p2["sites"]), 5)

    async def test_delete_all(self):
        await self.store.push("u1", [self.rec("a.com", 1)])
        self.assertEqual(await self.store.delete_all("u1"), 1)
        self.assertEqual(await self.store.count("u1"), 0)


if __name__ == "__main__":
    unittest.main()
