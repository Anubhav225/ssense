import urllib.request
import json
import time
import hmac
import hashlib
import uuid

API_KEY = "CYnzcaH4_CISSO_RlsH_K2s83xLEGAIMzKysD30UY2w"
HMAC_SECRET = "enEabpIITGIbuqoeWbgJoCA2GsbSUsmHsCJDG4Eka-3k8yMaIkjmL1aZK3AXlSBZ"
BASE_URL = "http://localhost:8000"

def gen_headers(method, path):
    ts = str(int(time.time() * 1000))
    nonce = uuid.uuid4().hex
    sig = hmac.new(HMAC_SECRET.encode(), f"{method}:{path}:{ts}:{nonce}".encode(), hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Ssense-API-Key": API_KEY,
        "X-Ssense-Timestamp": ts,
        "X-Ssense-Nonce": nonce,
        "X-Ssense-Signature": sig
    }

def test_endpoint(name, method, path, payload=None):
    headers = gen_headers(method, path)
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=5) as resp:
        t1 = time.perf_counter()
        dt = (t1 - t0) * 1000
        res = json.loads(resp.read().decode())
        score = res.get("data", {}).get("dpdp_trust_score", "N/A")
        src = res.get("source", "unknown")
        print(f"[{name}] status={resp.status} latency={dt:.2f}ms score={score} source={src}")

print("Testing different endpoints for Swiggy & Zomato:")
test_endpoint("swiggy /v1/audit/by-url", "POST", "/v1/audit/by-url", {"domain": "swiggy.com", "policyUrl": "https://www.swiggy.com/privacy-policy"})
test_endpoint("zomato /v1/audit/by-url", "POST", "/v1/audit/by-url", {"domain": "zomato.com", "policyUrl": "https://www.zomato.com/privacy"})
test_endpoint("swiggy /v1/audit (text)", "POST", "/v1/audit", {"domain": "swiggy.com", "policyText": "Sample policy excerpt text"})
test_endpoint("zomato /v1/audit (text)", "POST", "/v1/audit", {"domain": "zomato.com", "policyText": "Sample policy excerpt text"})
test_endpoint("swiggy GET /v1/audit/{domain}", "GET", "/v1/audit/swiggy.com")
test_endpoint("zomato GET /v1/audit/{domain}", "GET", "/v1/audit/zomato.com")
