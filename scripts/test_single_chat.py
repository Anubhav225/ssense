#!/usr/bin/env python3
import urllib.request
import json
import time
import hmac
import hashlib
import uuid
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

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

def test_chat(domain: str, prompt: str, mode: str):
    print(f"\n" + "="*70)
    print(f"TESTING CHAT: domain={domain} | mode={mode}")
    print(f"PROMPT: {prompt}")
    print("="*70, flush=True)

    path = "/v1/chat/stream"
    payload = json.dumps({
        "domain": domain,
        "userPrompt": prompt,
        "responseMode": mode
    }).encode("utf-8")

    req = urllib.request.Request(f"{BASE_URL}{path}", data=payload, headers=gen_headers(path), method="POST")

    t0 = time.perf_counter()
    ttft = None
    first_token_time = None
    tokens = []
    citations = []

    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
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
                    citations = p.get("data", [])
                    print(f"📚 Citations received ({len(citations)}):", flush=True)
                    for c in citations:
                        print(f"   - [{c.get('section')}] {c.get('title')}", flush=True)
                elif event == "token":
                    now = time.perf_counter()
                    if ttft is None:
                        ttft = (now - t0) * 1000.0
                        first_token_time = now
                        print(f"⚡ TTFT: {ttft:.1f}ms | Streaming response:", flush=True)
                    tok = p.get("data", "")
                    tokens.append(tok)
                    print(tok, end="", flush=True)
                elif event == "done":
                    print("\n[DONE]", flush=True)
                    break

        total_dur = time.perf_counter() - t0
        gen_dur = (time.perf_counter() - first_token_time) if first_token_time else total_dur
        tps = len(tokens) / gen_dur if gen_dur > 0 else 0
        print(f"\n📊 Summary: Total={total_dur:.2f}s | TTFT={ttft:.1f}ms | Tokens={len(tokens)} | Speed={tps:.2f} tok/s")
    except Exception as exc:
        print(f"\n❌ Error: {exc}", flush=True)

if __name__ == "__main__":
    # 1. Concise Mode on amazon.in
    test_chat(
        domain="amazon.in",
        prompt="How does Amazon process my personal shopping data and what is the exact legal procedure to withdraw my consent under Section 6 of the DPDP Act?",
        mode="concise"
    )
