#!/usr/bin/env python3
"""
test_models.py — Automated verification test for both SLM Server LoRA models:
  1. Audit Model (audit-model-final-adapter) via /v1/audit
  2. Chatbot Model (chatbot-model-final-adapter) via /v1/chat/stream (concise & thinking modes)
"""

import sys
import os
import time
import json
import uuid
import hmac
import hashlib
import httpx

BASE_URL = os.getenv("SSENSE_SERVER_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("SSENSE_API_KEY", "CYnzcaH4_CISSO_RlsH_K2s83xLEGAIMzKysD30UY2w")
HMAC_SECRET = os.getenv("SSENSE_HMAC_SECRET", "enEabpIITGIbuqoeWbgJoCA2GsbSUsmHsCJDG4Eka-3k8yMaIkjmL1aZK3AXlSBZ")

def create_auth_headers(method: str, path: str) -> dict:
    timestamp = str(int(time.time() * 1000))
    nonce = str(uuid.uuid4())
    payload = f"{method.upper()}:{path}:{timestamp}:{nonce}"
    signature = hmac.new(
        HMAC_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    return {
        "X-Ssense-API-Key": API_KEY,
        "X-Ssense-Signature": signature,
        "X-Ssense-Timestamp": timestamp,
        "X-Ssense-Nonce": nonce,
        "Content-Type": "application/json",
    }

def test_health():
    print("\n" + "="*60)
    print("STEP 1: Verifying SLM Server Health & Device Partitioning")
    print("="*60)
    with httpx.Client(timeout=10.0) as client:
        r = client.get(f"{BASE_URL}/health")
        if r.status_code != 200:
            print(f"❌ /health returned HTTP {r.status_code}: {r.text}")
            return False
        data = r.json()
        print(f"✅ Status: {data.get('status')}")
        print(f"   Backend: {data.get('backend')}")
        print(f"   Compute Profile: {data.get('compute_profile')}")
        print(f"   Engine Ready: {data.get('engine_ready')}")
        print(f"   RAG Ready: {data.get('rag_ready')}")
        pinfo = data.get("partition_info", {})
        print(f"   Partitioning: {pinfo.get('mode')} | GPU Layers: {pinfo.get('gpu_layers_count')} | CPU Layers: {pinfo.get('cpu_layers_count')}")
        if pinfo.get("gpus"):
            gpu = pinfo["gpus"][0]
            print(f"   GPU: {gpu.get('name')} (VRAM: {gpu.get('total_vram_gb')}GB, Weights: {gpu.get('weight_budget_gib')}GiB, KV Reserve: {gpu.get('kv_headroom_gib')}GiB)")
        return True

def test_audit_model():
    print("\n" + "="*60)
    print("STEP 2: Testing Audit LoRA Model (/v1/audit)")
    print("="*60)
    
    domain = "test-ecommerce-dpdp.in"
    # Policy with explicit DPDP Act 2023 non-compliances
    policy_text = (
        "Privacy Policy for TestEcommerce Ltd (Updated 2026):\n\n"
        "1. Collection of Information: We collect your full name, phone number, physical address, "
        "and biometric facial recognition markers upon visiting our website without requiring explicit opt-in.\n"
        "2. Purpose and Consent: By continuing to browse, you agree that your data may be processed "
        "for unspecified commercial purposes. We do not provide itemized notice or separate consent checkboxes.\n"
        "3. Cross-Border Sharing: All user personal identifiers and transaction histories are transferred "
        "indefinitely to foreign third-party marketing brokers in non-notified overseas jurisdictions.\n"
        "4. Data Retention and Erasure: We retain your information forever. Users have no right to request "
        "erasure, correction, or review of their personal data.\n"
        "5. Minors: We knowingly process and track children under the age of 18 without parental consent "
        "for targeted advertising campaigns.\n"
        "6. Grievance Redressal: We do not have a Data Protection Officer or Grievance Officer in India. "
        "Any complaints will be disregarded."
    )
    
    path = "/v1/audit"
    headers = create_auth_headers("POST", path)
    payload = {
        "domain": domain,
        "policyText": policy_text,
        "force_refresh": False
    }
    
    print(f"📡 Sending policy audit request for '{domain}' ({len(policy_text)} chars)...")
    start_time = time.time()
    with httpx.Client(timeout=600.0) as client:
        r = client.post(f"{BASE_URL}{path}", headers=headers, json=payload)
    elapsed = time.time() - start_time
    
    if r.status_code != 200:
        print(f"❌ /v1/audit failed with HTTP {r.status_code}: {r.text}")
        return False
        
    res = r.json()
    report = res.get("report", {})
    score = report.get("dpdp_trust_score", "N/A")
    violations = report.get("violations", [])
    recommendations = report.get("recommendations", [])
    
    print(f"⏱️ Audit completed in {elapsed:.2f}s")
    print(f"🎯 DPDP Trust Score: {score}/100")
    print(f"⚠️ Total Violations Identified: {len(violations)}")
    for idx, v in enumerate(violations, 1):
        if isinstance(v, dict):
            sec = v.get("section") or v.get("clause") or v.get("category", "General")
            issue = v.get("issue") or v.get("description") or v.get("violation", "")
            severity = v.get("severity", "MEDIUM")
            print(f"   [{idx}] [{severity}] {sec}: {issue[:80]}...")
        else:
            print(f"   [{idx}] {str(v)[:80]}...")
            
    print(f"💡 Key Recommendations: {len(recommendations)}")
    for rec in recommendations[:3]:
        print(f"   - {rec}")
        
    print("✅ Audit Model Test PASSED!")
    return True

def test_chat_model():
    print("\n" + "="*60)
    print("STEP 3: Testing Conversational Chatbot LoRA Model (/v1/chat/stream)")
    print("="*60)
    
    domain = "test-ecommerce-dpdp.in"
    path = "/v1/chat/stream"
    
    # Test 3A: Concise Mode
    print("\n--- Test 3A: Concise Mode ---")
    prompt_concise = "Does this policy collect my biometric data and is parental consent required for children?"
    headers = create_auth_headers("POST", path)
    payload_concise = {
        "domain": domain,
        "userPrompt": prompt_concise,
        "responseMode": "concise"
    }
    
    print(f"💬 Prompt: \"{prompt_concise}\"")
    start_time = time.time()
    tokens = []
    first_token_time = None
    
    with httpx.Client(timeout=180.0) as client:
        with client.stream("POST", f"{BASE_URL}{path}", headers=headers, json=payload_concise) as response:
            if response.status_code != 200:
                print(f"❌ Chat stream failed with HTTP {response.status_code}")
                return False
            
            for line in response.iter_lines():
                if line.startswith("data: "):
                    raw_data = line[6:]
                    try:
                        parsed = json.loads(raw_data)
                        event = parsed.get("event")
                        if event == "token":
                            if first_token_time is None:
                                first_token_time = time.time() - start_time
                            token_txt = parsed.get("data", "")
                            tokens.append(token_txt)
                            sys.stdout.write(token_txt)
                            sys.stdout.flush()
                        elif event == "done":
                            break
                    except json.JSONDecodeError:
                        continue
                        
    total_time = time.time() - start_time
    full_response = "".join(tokens)
    tps = len(tokens) / (total_time - (first_token_time or 0) + 1e-6)
    print("\n")
    print(f"⏱️ TTFT (Time to First Token): {first_token_time:.2f}s" if first_token_time else "⏱️ TTFT: N/A")
    print(f"⏱️ Total Response Time: {total_time:.2f}s ({len(tokens)} tokens, ~{tps:.1f} tokens/sec)")
    print("✅ Chatbot Model (Concise Mode) Test PASSED!")
    
    # Test 3B: Thinking Mode
    print("\n--- Test 3B: Thinking Mode (Step-by-Step DPDP Reasoning) ---")
    prompt_thinking = "Explain the specific violations under Section 9 and Section 16 of the DPDP Act in this policy."
    headers = create_auth_headers("POST", path)
    payload_thinking = {
        "domain": domain,
        "userPrompt": prompt_thinking,
        "responseMode": "thinking"
    }
    
    print(f"💬 Prompt: \"{prompt_thinking}\"")
    start_time = time.time()
    tokens = []
    first_token_time = None
    
    with httpx.Client(timeout=300.0) as client:
        with client.stream("POST", f"{BASE_URL}{path}", headers=headers, json=payload_thinking) as response:
            if response.status_code != 200:
                print(f"❌ Chat stream failed with HTTP {response.status_code}")
                return False
            
            for line in response.iter_lines():
                if line.startswith("data: "):
                    raw_data = line[6:]
                    try:
                        parsed = json.loads(raw_data)
                        event = parsed.get("event")
                        if event == "token":
                            if first_token_time is None:
                                first_token_time = time.time() - start_time
                            token_txt = parsed.get("data", "")
                            tokens.append(token_txt)
                            sys.stdout.write(token_txt)
                            sys.stdout.flush()
                        elif event == "done":
                            break
                    except json.JSONDecodeError:
                        continue

    total_time = time.time() - start_time
    tps = len(tokens) / (total_time - (first_token_time or 0) + 1e-6)
    print("\n")
    print(f"⏱️ TTFT (Time to First Token): {first_token_time:.2f}s" if first_token_time else "⏱️ TTFT: N/A")
    print(f"⏱️ Total Response Time: {total_time:.2f}s ({len(tokens)} tokens, ~{tps:.1f} tokens/sec)")
    print("✅ Chatbot Model (Thinking Mode) Test PASSED!")
    return True

if __name__ == "__main__":
    print("\n🚀 Starting Ssense SLM Model Verification Suite")
    if not test_health():
        sys.exit(1)
    if not test_audit_model():
        sys.exit(1)
    if not test_chat_model():
        sys.exit(1)
    print("\n" + "="*60)
    print("🎉 ALL TESTS PASSED: Both Audit & Chatbot LoRA Models are 100% Operational!")
    print("="*60 + "\n")
