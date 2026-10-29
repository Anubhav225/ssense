import json

with open('ml/evals/holdout_policies/ground_truth.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("Total policies:", len(data))
print("Sample item keys:", data[0].keys() if len(data) > 0 else [])
for item in data:
    d = item.get('domain', '') or item.get('policy_id', '') or item.get('name', '')
    if any(x in str(d).lower() for x in ['swiggy', 'zomato', 'flipkart', 'blinkit', 'paytm', 'amazon', 'ola']):
        print(f"Domain: {d} | Score: {item.get('dpdp_trust_score')} | Violations: {len(item.get('violations', []))}")

