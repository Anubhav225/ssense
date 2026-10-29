import sqlite3
import json

conn = sqlite3.connect('apps/slm-server/data/db/ssense_audit_cache.db')
c = conn.cursor()
c.execute("SELECT domain_key, domain_raw, trust_score, policy_url, report_json, chat_context FROM audit_cache WHERE domain_key='paytm.com'")
row = c.fetchone()
if row:
    print('domain_key:', row[0])
    print('domain_raw:', row[1])
    print('trust_score:', row[2])
    print('policy_url:', row[3])
    print('chat_context:', row[5])
    print('report_json:', json.dumps(json.loads(row[4]), indent=2))
else:
    print('No row found')

