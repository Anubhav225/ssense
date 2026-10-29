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

path = "/v1/chat/stream"
payload = {
    "domain": "swiggy.com",
    "userPrompt": "Does Swiggy share my phone number with delivery partners?",
    "responseMode": "concise"
}
data = json.dumps(payload).encode()
req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=gen_headers("POST", path), method="POST")

print("Sending chat stream request...")
t0 = time.perf_counter()
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        print(f"Connection opened in {(time.perf_counter()-t0)*1000:.2f}ms")
        for line in resp:
            line_str = line.decode().strip()
            if line_str.startswith("data:"):
                payload_str = line_str[5:].strip()
                if payload_str == "[DONE]":
                    print("\n[STREAM COMPLETE]")
                    break
                try:
                    p = json.loads(payload_str)
                    token = p.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if token:
                        print(token, end="", flush=True)
                except Exception:
                    pass
        print(f"\nTotal elapsed: {time.perf_counter()-t0:.2f}s")
except Exception as e:
    print(f"Error: {e}")

