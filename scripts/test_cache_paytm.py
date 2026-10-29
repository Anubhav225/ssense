import urllib.request
import json
import time
import hmac
import hashlib
import uuid

API_KEY = "CYnzcaH4_CISSO_RlsH_K2s83xLEGAIMzKysD30UY2w"
HMAC_SECRET = "enEabpIITGIbuqoeWbgJoCA2GsbSUsmHsCJDG4Eka-3k8yMaIkjmL1aZK3AXlSBZ"
BASE_URL = "http://localhost:8000"

def gen_headers(path):
    ts = str(int(time.time() * 1000))
    nonce = uuid.uuid4().hex
    sig = hmac.new(HMAC_SECRET.encode(), f"POST:{path}:{ts}:{nonce}".encode(), hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Ssense-API-Key": API_KEY,
        "X-Ssense-Timestamp": ts,
        "X-Ssense-Nonce": nonce,
        "X-Ssense-Signature": sig
    }

path = "/v1/audit/by-url"
data = json.dumps({
    "domain": "phonepe.com",
    "policyUrl": "https://www.phonepe.com/privacy-policy/",
    "force_refresh": False
}).encode()

req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=gen_headers(path), method="POST")
t0 = time.perf_counter()
try:
    with urllib.request.urlopen(req, timeout=5) as resp:
        t1 = time.perf_counter()
        res = json.loads(resp.read().decode())
        print(f"Status: {resp.status} | Latency: {(t1-t0)*1000:.2f}ms")
        print(json.dumps(res, indent=2))
except Exception as e:
    print(f"Error: {e}")
