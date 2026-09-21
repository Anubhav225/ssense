#!/usr/bin/env python3
import time
import json
import uuid
import hmac
import hashlib
import urllib.request
import urllib.error

API_KEY = "CYnzcaH4_CISSO_RlsH_K2s83xLEGAIMzKysD30UY2w"
HMAC_SECRET = "enEabpIITGIbuqoeWbgJoCA2GsbSUsmHsCJDG4Eka-3k8yMaIkjmL1aZK3AXlSBZ"
BASE_URL = "http://localhost:8000"

def generate_hmac_headers(method: str, path: str):
    timestamp = str(int(time.time() * 1000))
    nonce = uuid.uuid4().hex
    payload = f"{method.upper()}:{path}:{timestamp}:{nonce}"
    signature = hmac.new(
        HMAC_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Ssense-API-Key": API_KEY,
        "X-Ssense-Timestamp": timestamp,
        "X-Ssense-Nonce": nonce,
        "X-Ssense-Signature": signature,
    }

print("Testing Audit on amazon.in...", flush=True)
path = "/v1/audit/by-url"
body = json.dumps({
    "domain": "amazon.in",
    "policyUrl": "https://www.amazon.in/gp/help/customer/display.html?nodeId=200534380",
    "force_refresh": True
}).encode("utf-8")

req = urllib.request.Request(f"{BASE_URL}{path}", data=body, headers=generate_hmac_headers("POST", path), method="POST")

t0 = time.perf_counter()
try:
    with urllib.request.urlopen(req, timeout=600) as resp:
        t1 = time.perf_counter()
        data = json.loads(resp.read().decode("utf-8"))
        print(f"Status: {resp.status} | Latency: {t1-t0:.2f}s", flush=True)
        print(json.dumps(data, indent=2), flush=True)
except urllib.error.HTTPError as exc:
    print(f"HTTPError {exc.code}: {exc.read().decode('utf-8')}", flush=True)
except Exception as e:
    print(f"Error: {e}", flush=True)
