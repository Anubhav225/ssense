import urllib.request
import json
import time
import hmac
import hashlib
import uuid
import sys

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

def test_chat(domain: str, prompt: str, mode: str = "concise"):
    print(f"\n--- Testing Chat: domain={domain} ---")
    print(f"User Prompt: {prompt}")
    path = "/v1/chat/stream"
    payload = json.dumps({
        "domain": domain,
        "userPrompt": prompt,
        "responseMode": mode
    }).encode("utf-8")

    req = urllib.request.Request(f"{BASE_URL}{path}", data=payload, headers=gen_headers(path), method="POST")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if not data_str:
                    continue
                try:
                    p = json.loads(data_str)
                except Exception:
                    continue
                event = p.get("event")
                if event == "citations":
                    print(f"Citations: {len(p.get('data', []))} references found.")
                elif event == "token":
                    print(p.get("data", ""), end="", flush=True)
                elif event == "done":
                    print("\n[STREAM COMPLETE]")
                    break
        print(f"Total stream duration: {time.perf_counter()-t0:.2f}s")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    test_chat("test-ecommerce-dpdp.in", "What violations were detected on this site and what sections of the DPDP Act do they violate?")

