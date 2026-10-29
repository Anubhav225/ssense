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

test_targets = [
    ("swiggy.com", "https://www.swiggy.com/privacy-policy"),
    ("zomato.com", "https://www.zomato.com/privacy"),
    ("blinkit.com", "https://blinkit.com/privacy"),
    ("zepto.in", "https://www.zeptonow.com/privacy-policy"),
    ("flipkart.com", "https://www.flipkart.com/pages/privacypolicy"),
    ("amazon.in", "https://www.amazon.in/privacy"),
    ("paytm.com", "https://paytm.com/policies"),
    ("phonepe.com", "https://www.phonepe.com/privacy-policy/"),
    ("cred.club", "https://cred.club/privacy"),
    ("zerodha.com", "https://zerodha.com/privacy"),
    ("groww.in", "https://groww.in/privacy-policy"),
    ("hdfcbank.com", "https://www.hdfcbank.com/privacy"),
    ("sbi.co.in", "https://sbi.co.in/privacy"),
    ("redbus.in", "https://www.redbus.in/info/privacypolicy"),
    ("makemytrip.com", "https://www.makemytrip.com/privacy"),
    ("irctc.co.in", "https://www.irctc.co.in/privacy"),
    ("uber.com", "https://www.uber.com/privacy"),
    ("jio.com", "https://www.jio.com/privacy"),
    ("google.com", "https://policies.google.com/privacy"),
    ("youtube.com", "https://policies.google.com/privacy"),
    ("instagram.com", "https://privacycenter.instagram.com/policy"),
    ("bookmyshow.com", "https://in.bookmyshow.com/privacy"),
]

print(f"{'DOMAIN':<18} | {'STATUS':<7} | {'LATENCY':<10} | {'SCORE':<6} | {'SOURCE'}")
print("-" * 65)

path = "/v1/audit/by-url"
for domain, url in test_targets:
    data = json.dumps({
        "domain": domain,
        "policyUrl": url,
        "force_refresh": False
    }).encode()
    
    headers = gen_headers(path)
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method="POST")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            t1 = time.perf_counter()
            dt = (t1 - t0) * 1000
            res = json.loads(resp.read().decode())
            score = res.get("data", {}).get("dpdp_trust_score", "N/A")
            src = res.get("source", "unknown")
            print(f"{domain:<18} | {resp.status:<7} | {dt:6.2f} ms | {score:<6} | {src}")
    except Exception as e:
        t1 = time.perf_counter()
        dt = (t1 - t0) * 1000
        print(f"{domain:<18} | ERR     | {dt:6.2f} ms | N/A    | {e}")
