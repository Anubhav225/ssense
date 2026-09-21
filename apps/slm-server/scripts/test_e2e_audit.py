import httpx
import json

API_KEY = "CYnzcaH4_CISSO_RlsH_K2s83xLEGAIMzKysD30UY2w"
URL = "http://127.0.0.1:8000/v1/audit/by-url"

payload = {
    "domain": "wikimedia.org",
    "policyUrl": "https://foundation.wikimedia.org/wiki/Special:MyLanguage/Policy:Privacy_policy",
    "force_refresh": True
}

headers = {
    "X-Ssense-API-Key": API_KEY,
    "Content-Type": "application/json"
}

print(f"Sending audit request to {URL}...")
with httpx.Client(timeout=180.0) as client:
    resp = client.post(URL, json=payload, headers=headers)
    print(f"Status: {resp.status_code}")
    try:
        data = resp.json()
        print("Response structure:")
        print(f"  Source: {data.get('source')}")
        print(f"  Policy URL: {data.get('policy_url')}")
        audit_data = data.get("data", {})
        print(f"  DPDP Trust Score: {audit_data.get('dpdp_trust_score')}/100")
        print(f"  Subtlety Score: {audit_data.get('subtlety_score')}")
        print(f"  Reasoning: {audit_data.get('global_legal_reasoning')}")
        violations = audit_data.get("violations", [])
        print(f"  Violations ({len(violations)}):")
        for i, v in enumerate(violations, 1):
            print(f"    {i}. {v.get('violation_type')} ({v.get('statute_reference')}): {v.get('evidence_quote', '')[:100]}...")
    except Exception as e:
        print("Raw response:", resp.text[:500])
        print("Error parsing:", e)
