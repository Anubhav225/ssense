import sqlite3
import json

conn = sqlite3.connect('apps/slm-server/data/db/ssense_audit_cache.db')
c = conn.cursor()
c.execute('SELECT domain_key, trust_score, policy_url, report_json FROM audit_cache')
rows = c.fetchall()
print(f"Total rows: {len(rows)}")
for domain, score, url, r_json in rows:
    try:
        data = json.loads(r_json)
        v_count = len(data.get('violations', []))
    except Exception:
        v_count = 0
    print(f"{domain:<26} | Score: {score:>3}/100 | Violations: {v_count} | URL: {url}")

