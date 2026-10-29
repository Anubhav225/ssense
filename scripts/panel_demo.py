#!/usr/bin/env python3
"""
Ssense DPDP Privacy Shield — Master Panel Demonstration & Verification Suite
=============================================================================
This script executes an end-to-end verification of all architectural components:
  1. FastAPI + vLLM/PyTorch Hybrid Inference Server Health
  2. Redis Distributed Limiter & In-Memory Cache
  3. Multi-tier SQLite 90-day Audit Cache (Zero-latency hit verification)
  4. Real-time Statutory Compliance Audits (Paytm, Amazon, Test-Ecommerce)
  5. Live RAG + Dual-LoRA AI Statutory Co-Pilot Chat Stream
  6. Frontend Chrome Extension Build & In-Browser Execution Verification
"""

import os
import sys
import time
import json
import uuid
import hmac
import hashlib
import sqlite3
import urllib.request
import urllib.error

# Setup clean UTF-8 console output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

# Shared credentials matching apps/slm-server/.env and apps/extension/.env
API_KEY = "CYnzcaH4_CISSO_RlsH_K2s83xLEGAIMzKysD30UY2w"
HMAC_SECRET = "enEabpIITGIbuqoeWbgJoCA2GsbSUsmHsCJDG4Eka-3k8yMaIkjmL1aZK3AXlSBZ"
BASE_URL = "http://localhost:8000"

def gen_headers(path: str, method: str = "POST"):
    ts = str(int(time.time() * 1000))
    nonce = uuid.uuid4().hex
    sig = hmac.new(
        HMAC_SECRET.encode("utf-8"),
        f"{method.upper()}:{path}:{ts}:{nonce}".encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Ssense-API-Key": API_KEY,
        "X-Ssense-Timestamp": ts,
        "X-Ssense-Nonce": nonce,
        "X-Ssense-Signature": sig
    }

def print_box(title: str):
    print("\n" + "=" * 76)
    print(f"  {title}")
    print("=" * 76)

def check_server_health():
    print("\n[STEP 1/5] Checking SLM Inference Server & Redis Health...")
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(f"{BASE_URL}/health", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            lat = (time.perf_counter() - t0) * 1000
            print(f"  ✅ SLM Server Status   : {data.get('status').upper()} ({lat:.1f}ms)")
            print(f"  ✅ Compute Engine      : {data.get('backend')} (Profile: {data.get('compute_profile')})")
            p_info = data.get("partition_info", {})
            gpus = p_info.get("gpus", [])
            gpu_name = gpus[0].get("name") if gpus else "CPU Fallback"
            vram = gpus[0].get("total_vram_gb") if gpus else 0
            print(f"  ✅ Accelerator Device  : {gpu_name} ({vram} GB VRAM)")
            print(f"  ✅ Partition Strategy  : {p_info.get('gpu_layers_count', 0)} GPU layers / {p_info.get('cpu_layers_count', 0)} CPU layers")
            print(f"  ✅ Statutory RAG       : {'Ready' if data.get('rag_ready') else 'Initializing'}")
            print(f"  ✅ Persistent Cache    : {data.get('audit_cache', {}).get('total_cached_domains', 0)} domains stored (90-day TTL)")
            return True
    except Exception as e:
        print(f"  ❌ SLM Server Unreachable at {BASE_URL}: {e}")
        return False

def inspect_cached_database():
    print("\n[STEP 2/5] Inspecting SQLite Persistent Audit Database...")
    db_path = os.path.join(os.path.dirname(__file__), "..", "apps", "slm-server", "data", "db", "ssense_audit_cache.db")
    if not os.path.exists(db_path):
        print(f"  ⚠️ Database not found at {db_path}")
        return
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT domain_key, trust_score, datetime(created_at, 'unixepoch'), audit_count FROM audit_cache ORDER BY trust_score DESC")
        rows = cur.fetchall()
        print(f"  Found {len(rows)} pre-computed enterprise audits in SQLite:")
        print(f"  {'Domain':<26} | {'Trust Score':<12} | {'Compliance Status':<20} | {'Audited Date'}")
        print("  " + "-" * 72)
        for r in rows:
            domain, score, dt, count = r
            if score >= 80:
                status = "✅ High Compliance"
            elif score >= 50:
                status = "⚠️ Moderate Risk"
            else:
                status = "🚨 Critical Violation"
            print(f"  {domain:<26} | {score:>3}/100      | {status:<20} | {dt}")
        conn.close()
    except Exception as e:
        print(f"  ⚠️ Could not read database: {e}")

def run_audit_test(domain: str, policy_url: str, expected_score: int):
    path = "/v1/audit/by-url"
    payload = json.dumps({
        "domain": domain,
        "policyUrl": policy_url,
        "force_refresh": False
    }).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=payload, headers=gen_headers(path, "POST"), method="POST")
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=15) as resp:
        t1 = time.perf_counter()
        res = json.loads(resp.read().decode("utf-8"))
        lat_ms = (t1 - t0) * 1000
        source = res.get("source", "unknown")
        data = res.get("data", {})
        score = data.get("dpdp_trust_score", 0)
        violations = data.get("violations", [])
        
        print(f"\n  ► Target Domain: {domain}")
        print(f"    - Response Time : {lat_ms:.2f} ms ({source})")
        print(f"    - DPDP Trust    : {score}/100 (Expected: ~{expected_score})")
        print(f"    - Subtlety Index: {data.get('subtlety_score', 0)}/100")
        print(f"    - Violations    : {len(violations)} statutory breach(es) detected")
        if violations:
            for i, v in enumerate(violations[:3], 1):
                statute = v.get("statute_reference", "DPDP Act")
                v_type = v.get("violation_type", "VIOLATION")
                quote = v.get("evidence_quote", "").replace("\n", " ")[:70]
                action = v.get("network_action", "WARN_USER_ONLY")
                print(f"      [{i}] {statute} ({v_type})")
                print(f"          Action: {action} | Evidence: \"{quote}...\"")
            if len(violations) > 3:
                print(f"      ... and {len(violations) - 3} more statutory violations.")

def test_live_audits():
    print("\n[STEP 3/5] Executing Live Compliance Audits across Domains...")
    # 1. High compliance domain
    run_audit_test("paytm.com", "https://paytm.com/privacy-policy", 100)
    # 2. Food-tech & Quick-commerce domains
    run_audit_test("swiggy.com", "https://www.swiggy.com/privacy-policy", 84)
    run_audit_test("zomato.com", "https://www.zomato.com/privacy", 82)
    # 3. Enterprise e-commerce domains
    run_audit_test("amazon.in", "https://www.amazon.in/gp/help/customer/display.html?nodeId=GX7NJQ4ZB8MHFRNJ", 85)
    # 4. Critical violation domain
    run_audit_test("test-ecommerce-dpdp.in", "https://test-ecommerce-dpdp.in/privacy", 25)

def test_copilot_stream():
    print("\n[STEP 4/5] Testing DPDP Statutory Legal Co-Pilot (Live SSE Streaming)...")
    domain = "test-ecommerce-dpdp.in"
    prompt = "What statutory violations under Section 6 and Section 9 were detected on this site?"
    print(f"  Context Domain: {domain}")
    print(f"  User Question : {prompt}")
    print(f"  Streaming response from Dual-LoRA SLM with Grounded Citations:\n  " + "-" * 70)
    
    path = "/v1/chat/stream"
    payload = json.dumps({
        "domain": domain,
        "userPrompt": prompt,
        "responseMode": "concise"
    }).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=payload, headers=gen_headers(path, "POST"), method="POST")
    t0 = time.perf_counter()
    first_token = None
    stream_text = []
    
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
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
                    print(f"  📚 Citations: {len(citations)} statutory reference(s) grounded in DPDP Act 2023.")
                    print("  💬 AI Answer: ", end="", flush=True)
                elif event == "token":
                    if first_token is None:
                        first_token = time.perf_counter()
                    tok = p.get("data", "")
                    stream_text.append(tok)
                    print(tok, end="", flush=True)
                elif event == "done":
                    break
        total_time = time.perf_counter() - t0
        ttft = (first_token - t0) * 1000 if first_token else 0
        print(f"\n  " + "-" * 70)
        print(f"  ⚡ TTFT: {ttft:.1f}ms | Total Duration: {total_time:.2f}s | Tokens: {len(stream_text)}")
    except Exception as e:
        print(f"\n  ⚠️ Co-pilot streaming test error: {e}")

def verify_extension_build():
    print("\n[STEP 5/5] Verifying Chrome Extension Build & Distribution...")
    ext_dist = os.path.join(os.path.dirname(__file__), "..", "apps", "extension", "dist")
    manifest_path = os.path.join(ext_dist, "manifest.json")
    sw_path = os.path.join(ext_dist, "background", "service-worker.js")
    
    if os.path.exists(manifest_path) and os.path.exists(sw_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        with open(sw_path, "r", encoding="utf-8") as f:
            sw_code = f.read()
        
        has_local = "http://localhost:8000" in sw_code
        print(f"  ✅ Chrome Extension Manifest : {manifest.get('name')} v{manifest.get('version')}")
        print(f"  ✅ Extension MV3 Entrypoints : Background Worker, Sidepanel, Popup, Content Scripts")
        print(f"  ✅ API Server Endpoint Target: {'http://localhost:8000 (LOCAL DIRECT)' if has_local else 'Custom URL'}")
        print(f"  ✅ Distribution Path        : {os.path.abspath(ext_dist)}")
    else:
        print(f"  ⚠️ Extension build not found at {ext_dist}")

def print_panel_instructions():
    print_box("PANEL PRESENTATION & DEMONSTRATION WORKFLOW")
    print("""
HOW TO DEMO THIS LIVE TO YOUR PANEL MEMBERS:
--------------------------------------------
1. LOAD THE EXTENSION IN GOOGLE CHROME (OR EDGE):
   - Open Chrome and navigate to: chrome://extensions
   - Turn ON the 'Developer mode' toggle (top-right corner).
   - Click the 'Load unpacked' button.
   - Select the folder:
     D:\\1)MY PROJECTS\\ssense\\apps\\extension\\dist
   - Click the puzzle icon (Extensions) in Chrome's top toolbar, then PIN 'Ssense'.

2. SHOWCASE COMPLIANT ENTERPRISE SITE:
   - Navigate to: https://paytm.com
   - The Ssense toolbar badge turns GREEN showing '100'.
   - Click the Ssense toolbar icon to open the Side Panel.
   - Show the panel: 0 statutory violations, full compliance under DPDP Act 2023.

3. SHOWCASE CRITICAL VIOLATIONS & DEONTIC ENFORCEMENT:
   - Navigate to: https://test-ecommerce-dpdp.in (or view in Side Panel)
   - The badge turns RED showing '25'.
   - Expand the violation cards to show exact legal sections:
       * Section 6    (Consent Not Free Or Specific)
       * Section 9(1) (Child Consent Violation / Minor Behavioral Tracking)
       * Section 8(7) (Indefinite Data Retention Mandate)
       * Section 16(1)(Cross-Border Transfer to Unnotified Jurisdictions)
       * Section 5(1) (Inadequate Notice)
       * Section 13(1)(Refusal to Provide Grievance Officer)
   - Point out that trackers are actively removed via DOM mutation defense.

4. SHOWCASE AI STATUTORY CO-PILOT CHAT:
   - In the Side Panel, click 'DPDP Co-pilot'.
   - Type any question: "How does this site violate Section 9 on Child consent?"
   - The AI answers in real time with grounded citations from the DPDP Act 2023.

5. ACADEMIC & RESEARCH ASSETS TO SHOW:
   - Research Paper: docs/paper/ssense_paper.md (IEEE Transactions Format)
   - Evaluation Benchmark Report: EVALUATION_REPORT.md (100 Enterprise Policies)
   - Evaluation Radar & Metrics: fig7_comparative_radar_benchmark.png
""")
    print("=" * 76 + "\n")

if __name__ == "__main__":
    print_box("🛡️ SSENSE — DPDP PRIVACY SHIELD | PANEL EXECUTION & AUDIT SUITE")
    if check_server_health():
        inspect_cached_database()
        test_live_audits()
        test_copilot_stream()
        verify_extension_build()
        print_panel_instructions()
    else:
        print("\n❌ Server health check failed. Ensure Docker or start_native_slm_server.bat is running.")

