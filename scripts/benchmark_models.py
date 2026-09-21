#!/usr/bin/env python3
"""
benchmark_models.py — Production Verification & Latency/Accuracy Benchmark

Tests both models:
  1. Audit Model (audit-model-final-adapter) via /v1/audit/by-url
  2. Chatbot Co-Pilot Model (chatbot-model-final-adapter) via /v1/chat/stream
Across real-world target sites: amazon.in, claude.ai, google.com
Tests concise vs thinking modes, RAG citations, and context ablation.
"""

import sys
import os
import json
import time
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
import uuid
import hmac
import hashlib
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

API_KEY = "CYnzcaH4_CISSO_RlsH_K2s83xLEGAIMzKysD30UY2w"
HMAC_SECRET = "enEabpIITGIbuqoeWbgJoCA2GsbSUsmHsCJDG4Eka-3k8yMaIkjmL1aZK3AXlSBZ"
BASE_URL = "http://localhost:8000"

def generate_hmac_headers(method: str, path: str) -> Dict[str, str]:
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

def post_json(path: str, data: Dict[str, Any], timeout: int = 600) -> Tuple[int, Dict[str, Any], float]:
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode("utf-8")
    headers = generate_hmac_headers("POST", path)
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            t1 = time.perf_counter()
            resp_body = resp.read().decode("utf-8")
            return resp.status, json.loads(resp_body), t1 - t0
    except urllib.error.HTTPError as exc:
        t1 = time.perf_counter()
        err_body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = {"raw": err_body}
        return exc.code, parsed, t1 - t0

def stream_chat(
    domain: str,
    user_prompt: str,
    response_mode: str = "concise",
    timeout: int = 600
) -> Dict[str, Any]:
    path = "/v1/chat/stream"
    url = f"{BASE_URL}{path}"
    data = {
        "domain": domain,
        "userPrompt": user_prompt,
        "responseMode": response_mode,
    }
    body = json.dumps(data).encode("utf-8")
    headers = generate_hmac_headers("POST", path)
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    
    t0 = time.perf_counter()
    ttft: Optional[float] = None
    first_token_time: Optional[float] = None
    tokens: List[str] = []
    citations: List[Dict[str, Any]] = []
    events_received: List[str] = []
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if not data_str:
                    continue
                try:
                    payload = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                
                event = payload.get("event")
                events_received.append(event)
                
                if event == "citations":
                    citations = payload.get("data", [])
                elif event == "token":
                    now = time.perf_counter()
                    if ttft is None:
                        ttft = (now - t0) * 1000.0  # ms
                        first_token_time = now
                    tok = payload.get("data", "")
                    tokens.append(tok)
                elif event == "done":
                    break
                elif event == "error":
                    print(f"  [STREAM ERROR] {payload.get('data')}")
                    
        total_time = time.perf_counter() - t0
        gen_time = (time.perf_counter() - first_token_time) if first_token_time else total_time
        full_text = "".join(tokens)
        token_count = len(tokens)
        tok_per_sec = (token_count / gen_time) if (gen_time > 0 and token_count > 0) else 0.0
        
        return {
            "success": True,
            "ttft_ms": ttft or 0.0,
            "total_time_s": total_time,
            "gen_time_s": gen_time,
            "token_count": token_count,
            "tokens_per_sec": tok_per_sec,
            "full_text": full_text,
            "citations": citations,
            "events": events_received,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "total_time_s": time.perf_counter() - t0,
            "full_text": "".join(tokens),
        }

def run_benchmarks():
    print("=" * 80)
    print("SSENSE AI ENGINE BENCHMARK: AUDIT MODEL & CHATBOT CO-PILOT")
    print("=" * 80)
    
    # 1. Health Verification
    print("\n--- 1. Checking Health Endpoint ---")
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health") as resp:
            health_data = json.loads(resp.read().decode("utf-8"))
            print(f"Health Status: {health_data.get('status')}")
            print(f"Backend: {health_data.get('backend')}")
            print(f"Engine Ready: {health_data.get('engine_ready')}")
            print(f"RAG Ready: {health_data.get('rag_ready')}")
    except Exception as exc:
        print(f"CRITICAL: Failed to reach health endpoint: {exc}")
        sys.exit(1)

    # 2. Audit Model Benchmarks
    print("\n" + "=" * 80)
    print("PHASE 1: AUDIT MODEL BENCHMARKS (POST /v1/audit/by-url)")
    print("=" * 80)
    
    target_domains = [
        {
            "domain": "amazon.in",
            "policy_url": "https://www.amazon.in/gp/help/customer/display.html?nodeId=200534380",
            "sector": "E-Commerce / Retail"
        },
        {
            "domain": "claude.ai",
            "policy_url": "https://www.anthropic.com/legal/privacy",
            "sector": "Frontier AI Platform"
        },
        {
            "domain": "google.com",
            "policy_url": "https://policies.google.com/privacy",
            "sector": "Search / Big Tech Ecosystem"
        },
    ]
    
    audit_results = {}
    
    for target in target_domains:
        d = target["domain"]
        u = target["policy_url"]
        s = target["sector"]
        print(f"\n[Audit Benchmark] Target: {d} ({s})")
        print(f"  Policy URL: {u}")
        
        status, resp, duration = post_json("/v1/audit/by-url", {
            "domain": d,
            "policyUrl": u,
            "force_refresh": True  # Force fresh inference to test model latency
        }, timeout=600)
        
        print(f"  HTTP Status: {status} | Latency: {duration:.2f}s")
        if status == 200:
            data = resp.get("data", {})
            source = resp.get("source", "")
            trust_score = data.get("dpdp_trust_score", "N/A")
            subtlety_score = data.get("subtlety_score", "N/A")
            violations = data.get("violations", [])
            reasoning = data.get("global_legal_reasoning", "")
            
            print(f"  Source: {source}")
            print(f"  DPDP Trust Score: {trust_score}/100")
            print(f"  Subtlety Score: {subtlety_score}/100")
            print(f"  Violations Found: {len(violations)}")
            for i, v in enumerate(violations[:3], 1):
                vt = v.get("violation_type", "")
                sr = v.get("statute_reference", "")
                ev = v.get("evidence_quote", "")[:80]
                na = v.get("network_action", "")
                print(f"    {i}. {vt} [{sr}] -> {na} | Evidence: \"{ev}...\"")
            if len(violations) > 3:
                print(f"    ... and {len(violations) - 3} more violations.")
            print(f"  Legal Reasoning: {reasoning[:200]}...")
            
            audit_results[d] = {
                "status": status,
                "duration_s": duration,
                "trust_score": trust_score,
                "subtlety_score": subtlety_score,
                "violations_count": len(violations),
                "violations": violations,
                "legal_reasoning": reasoning,
            }
        else:
            print(f"  FAILED: {resp}")
            audit_results[d] = {"status": status, "error": resp, "duration_s": duration}

        # Test cache retrieval speed on the same domain
        print(f"  Testing Cache Retrieval Speed for {d}...")
        c_status, c_resp, c_duration = post_json("/v1/audit/by-url", {
            "domain": d,
            "policyUrl": u,
            "force_refresh": False
        }, timeout=30)
        print(f"  Cached Request Status: {c_status} | Cache Hit Latency: {c_duration*1000.0:.2f}ms | Source: {c_resp.get('source')}")

    # 3. Chatbot Co-Pilot Model Benchmarks
    print("\n" + "=" * 80)
    print("PHASE 2: CHATBOT CO-PILOT MODEL BENCHMARKS (POST /v1/chat/stream)")
    print("=" * 80)
    
    chat_test_matrix = [
        {
            "id": "AMZ_CONCISE",
            "domain": "amazon.in",
            "mode": "concise",
            "prompt": "How does Amazon process my personal shopping data and what is the exact legal procedure to withdraw my consent under Section 6 of the DPDP Act?",
            "desc": "Audited Context + Concise Mode (Consent Withdrawal Probe)"
        },
        {
            "id": "AMZ_THINKING",
            "domain": "amazon.in",
            "mode": "thinking",
            "prompt": "Analyze Amazon's compliance with DPDP Act 2023 regarding data retention limits and sharing with third-party advertising partners under Section 8.",
            "desc": "Audited Context + Thinking Mode (Data Retention & 3rd Party Sharing Analysis)"
        },
        {
            "id": "CLAUDE_CONCISE",
            "domain": "claude.ai",
            "mode": "concise",
            "prompt": "Does Anthropic track behavioral data or process personal data of children, and does this comply with Section 9 of the DPDP Act 2023?",
            "desc": "Audited Context + Concise Mode (Children Data & Profiling Probe)"
        },
        {
            "id": "GOOGLE_THINKING",
            "domain": "google.com",
            "mode": "thinking",
            "prompt": "What are my rights to correction, completion, and erasure of personal data held by Google under Section 12 of the DPDP Act 2023?",
            "desc": "Audited Context + Thinking Mode (Data Principal Rights Probe)"
        },
        {
            "id": "STATUTORY_RAG",
            "domain": "google.com",
            "mode": "concise",
            "prompt": "What are the financial penalties specified under the DPDP Act 2023 for failure to take reasonable security safeguards to prevent a personal data breach?",
            "desc": "Audited Site + Statutory RAG Probe (Penalty Schedule / Section 33)"
        },
        {
            "id": "CONTEXT_ABLATION",
            "domain": "github.com",
            "mode": "concise",
            "prompt": "How does GitHub protect developer telemetry data?",
            "desc": "Unaudited Site (Context Ablation & Audit Gatekeeper Test)"
        }
    ]
    
    chat_results = {}
    
    for test in chat_test_matrix:
        tid = test["id"]
        d = test["domain"]
        m = test["mode"]
        q = test["prompt"]
        desc = test["desc"]
        
        print(f"\n[Chat Benchmark] Test {tid}: {desc}")
        print(f"  Domain: {d} | Mode: {m}")
        print(f"  Question: \"{q}\"")
        
        res = stream_chat(d, q, response_mode=m, timeout=600)
        
        if res.get("success"):
            ttft = res["ttft_ms"]
            total_time = res["total_time_s"]
            tok_count = res["token_count"]
            tps = res["tokens_per_sec"]
            text = res["full_text"]
            cits = res.get("citations", [])
            
            print(f"  TTFT: {ttft:.1f}ms | Total Duration: {total_time:.2f}s | Tokens: {tok_count} | Throughput: {tps:.2f} tok/s")
            print(f"  RAG Citations Injected: {len(cits)}")
            for c in cits[:2]:
                print(f"    - [{c.get('section', 'Statute')}] {c.get('title', '')}")
            print(f"  Generated Answer:\n    \"\"\"{text.strip()}\"\"\"")
            
            chat_results[tid] = {
                "success": True,
                "ttft_ms": ttft,
                "total_time_s": total_time,
                "token_count": tok_count,
                "tokens_per_sec": tps,
                "citations_count": len(cits),
                "full_text": text,
            }
        else:
            print(f"  FAILED: {res.get('error')}")
            chat_results[tid] = {"success": False, "error": res.get("error")}

    # 4. Summary Table
    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY & METRICS REPORT")
    print("=" * 80)
    
    print("\n--- AUDIT MODEL BENCHMARKS ---")
    print(f"{'Domain':<15} | {'Status':<8} | {'Latency (s)':<12} | {'DPDP Score':<10} | {'Subtlety':<9} | {'Violations':<10}")
    print("-" * 75)
    for d, r in audit_results.items():
        if r.get("status") == 200:
            print(f"{d:<15} | {'OK':<8} | {r['duration_s']:<12.2f} | {r['trust_score']:<10} | {r['subtlety_score']:<9} | {r['violations_count']:<10}")
        else:
            print(f"{d:<15} | {'ERR':<8} | {r.get('duration_s', 0):<12.2f} | {'-':<10} | {'-':<9} | {'-':<10}")
            
    print("\n--- CHATBOT CO-PILOT BENCHMARKS ---")
    print(f"{'Test ID':<18} | {'Mode':<9} | {'TTFT (ms)':<10} | {'Total (s)':<9} | {'Tokens':<7} | {'Tok/s':<7} | {'Citations'}")
    print("-" * 75)
    for test in chat_test_matrix:
        tid = test["id"]
        r = chat_results.get(tid, {})
        if r.get("success"):
            print(f"{tid:<18} | {test['mode']:<9} | {r['ttft_ms']:<10.1f} | {r['total_time_s']:<9.2f} | {r['token_count']:<7} | {r['tokens_per_sec']:<7.2f} | {r['citations_count']}")
        else:
            print(f"{tid:<18} | {test['mode']:<9} | {'ERR':<10} | {'-':<9} | {'-':<7} | {'-':<7} | -")

    # Save benchmark report json
    report_file = "benchmark_results.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.time(),
            "audit_results": audit_results,
            "chat_results": chat_results,
        }, f, indent=2)
    print(f"\n✅ Full benchmark results saved to {report_file}")

if __name__ == "__main__":
    run_benchmarks()
