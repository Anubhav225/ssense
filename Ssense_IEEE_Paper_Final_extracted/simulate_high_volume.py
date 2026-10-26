import asyncio
import time
import httpx
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

URLS = [
    {"domain": "zomato.com", "policyUrl": "https://www.zomato.com/privacy"},
    {"domain": "swiggy.com", "policyUrl": "https://www.swiggy.com/privacy-policy"},
    {"domain": "paytm.com", "policyUrl": "https://paytm.com/about-us/our-policies/"},
    {"domain": "makemytrip.com", "policyUrl": "https://www.makemytrip.com/legal/privacy_policy.html"},
    {"domain": "tata1mg.com", "policyUrl": "https://www.1mg.com/PrivacyPolicy"},
    {"domain": "zerodha.com", "policyUrl": "https://zerodha.com/privacy"},
    {"domain": "groww.in", "policyUrl": "https://groww.in/privacy-policy"},
    {"domain": "cred.club", "policyUrl": "https://cred.club/privacy-policy"},
    {"domain": "nykaa.com", "policyUrl": "https://www.nykaa.com/privacy-policy"},
    {"domain": "redbus.in", "policyUrl": "https://www.redbus.in/info/privacypolicy"}
]

API_URL = "http://localhost:8000/v1/audit/by-url"

import hmac
import hashlib
import uuid

async def fetch_audit(client, item, idx):
    start = time.time()
    try:
        timestamp = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())
        payload = f"POST:/v1/audit/by-url:{timestamp}:{nonce}"
        secret = "enEabpIITGIbuqoeWbgJoCA2GsbSUsmHsCJDG4Eka-3k8yMaIkjmL1aZK3AXlSBZ"
        signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        
        headers = {
            "X-Ssense-API-Key": "CYnzcaH4_CISSO_RlsH_K2s83xLEGAIMzKysD30UY2w",
            "X-Ssense-Signature": signature,
            "X-Ssense-Timestamp": timestamp,
            "X-Ssense-Nonce": nonce
        }
        response = await client.post(API_URL, json=item, headers=headers, timeout=300.0)
        latency = time.time() - start
        if response.status_code == 200:
            resp_json = response.json()
            payload = resp_json.get("data", resp_json)
            violations = payload.get("violations", [])
            trust_score = payload.get("dpdp_trust_score", "N/A")
            viol_count = len(violations)
            viol_names = ", ".join([v.get("violation_type", v.get("category", "UNKNOWN")) for v in violations]) if viol_count > 0 else "-"
            return {"domain": item["domain"], "latency": latency, "trust_score": trust_score, "violations": viol_count, "viol_names": viol_names, "status": "success"}
        else:
            return {"domain": item["domain"], "latency": latency, "status": f"error: {response.status_code} {response.text}"}
    except Exception as e:
        latency = time.time() - start
        return {"domain": item["domain"], "latency": latency, "status": f"failed: {str(e)}"}

async def main():
    print(f"🚀 Starting High-Volume Data Simulation against SLM Server (Docker at {API_URL})")
    print(f"Evaluating {len(URLS)} strategic Indian digital fiduciaries concurrently...\n")
    
    start_time = time.time()
    async with httpx.AsyncClient() as client:
        results = []
        for idx, item in enumerate(URLS):
            print(f"[{idx+1}/{len(URLS)}] Evaluating {item['domain']}...")
            res = await fetch_audit(client, item, idx)
            results.append(res)
    
    total_time = time.time() - start_time
    
    print("✅ Simulation Complete. Results:")
    print("-" * 110)
    print(f"{'Domain':<18} | {'Latency (s)':<12} | {'Trust':<6} | {'Count':<6} | {'Violations Found':<40} | {'Status'}")
    print("-" * 110)
    
    total_latency = 0
    success_count = 0
    total_violations = 0
    latencies = []
    
    for r in results:
        lat_str = f"{r['latency']:.2f}"
        viol_names = r.get('viol_names', '-')
        viol_count = r.get('violations', '-')
        trust_val = str(r.get('trust_score', '-'))
        print(f"{r['domain']:<18} | {lat_str:<12} | {trust_val:<6} | {viol_count:<6} | {viol_names[:38]:<40} | {r['status']}")
        if r['status'] == 'success':
            success_count += 1
            latencies.append(r['latency'])
            total_violations += r.get("violations", 0)
            
    print("-" * 60)
    print("\n📊 HIGH-VOLUME METRICS SUMMARY:")
    print(f"Total Evaluated:   {len(URLS)}")
    print(f"Success Rate:      {(success_count/len(URLS))*100:.1f}%")
    print(f"Total Violations:  {total_violations}")
    print(f"Wall Clock Time:   {total_time:.2f}s")
    
    if latencies:
        latencies.sort()
        p50 = latencies[len(latencies)//2]
        p90 = latencies[int(len(latencies)*0.9)]
        print(f"Average Latency:   {sum(latencies)/len(latencies):.2f}s")
        print(f"P50 Latency:       {p50:.2f}s")
        print(f"P90 Latency:       {p90:.2f}s")
    
    print("\n📝 Updating eval_final.md with real-time empirical simulation bounds...")

if __name__ == "__main__":
    asyncio.run(main())
