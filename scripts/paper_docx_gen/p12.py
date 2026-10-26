p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(8)
r=p.add_run("APPENDIX: AUDIT OUTPUT CONTRACT SCHEMA AND RISK CLASSIFICATION")
r.bold=True; r.font.size=Pt(10); r.font.name="Times New Roman"
BP("The auditor emits JSON conforming to the following schema. Findings with omission_check=true are mechanically dropped before response emission. Violation types outside the 26-node enumeration and evidence quotes under 20 characters are removed by the post-processor.")
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.LEFT
p.paragraph_format.space_before=Pt(4); p.paragraph_format.space_after=Pt(4)
p.paragraph_format.left_indent=Pt(14)
schema_txt = (
    '{\n'
    '  "global_legal_reasoning": "Step-by-step statutory analysis with deductive chain...",\n'
    '  "violations": [{\n'
    '    "type": "<26-enum e.g., NOTICE_INADEQUATE>",\n'
    '    "step_1_active_claim_analysis": "Verbatim claim extraction from policy text...",\n'
    '    "step_2_statute_match": "S.5(1), Rule 3 TreeLookup result...",\n'
    '    "omission_check": false,\n'
    '    "step_3_semantic_justification": "Deontic breach rationale with statutory citation...",\n'
    '    "evidence_quote": "Verbatim policy text (>=20 chars, source-verified)...",\n'
    '    "offending_entities": ["data_controller_name"],\n'
    '    "severity": "CRITICAL | HIGH | MEDIUM | LOW",\n'
    '    "statutory_risk_assessment": "Penalty citing Schedule 1 ceiling and Section"\n'
    '  }],\n'
    '  "dpdp_trust_score": 65,\n'
    '  "subtlety_score": 78\n'
    '}'
)
r=p.add_run(schema_txt); r.font.name="Courier New"; r.font.size=Pt(7.5)
TC("TABLE XV: Statutory Severity Classification and Regulatory Risk Tiers")
t=doc.add_table(rows=1,cols=4); t.style="Table Grid"; t.alignment=WD_TABLE_ALIGNMENT.CENTER
TH(t,["Risk Tier","Governing DPDP Sections","Violation Examples","Schedule 1 Penalty Ceiling"])
TR(t,[
    ["Critical (omega=30)","S.9[Rule 10], S.16[Rule 13(4)], S.3(b), S.10(2)(b)","CHILD_CONSENT_VIOLATION, CROSS_BORDER_TRANSFER_VIOLATION, SCOPE_APPLICATION_EVASION, SDF_DATA_LOCALIZATION_VIOLATION","Up to Rs.250 crore; Priority Regulatory Escalation"],
    ["High (omega=20)","S.6(1), S.7, S.8(6)[Rule 7], S.8(7)[Rule 8, Sched.3], S.10","CONSENT_NOT_FREE_OR_SPECIFIC, LEGITIMATE_USES_ABUSE, DATA_RETENTION_LIMIT_EXCEEDED, BREACH_NOTIFICATION_FAILURE","Up to Rs.200 crore; Substantive Non-Compliance Citation"],
    ["Medium (omega=10)","S.5(1)[Rule 3], S.6(4)[Rule 4], S.8(2), S.8(5)[Rule 6], S.13","NOTICE_INADEQUATE, CONSENT_MECHANICS_VIOLATION, GRIEVANCE_REDRESSAL_INADEQUATE, SECURITY_SAFEGUARDS_MISSING","Up to Rs.50 crore; Formal Compliance Warning"],
    ["Low (omega=5)","S.5(3)[Rule 3(2)], S.8(3)[Rule 6], S.13(3)[Rule 12]","LANGUAGE_ACCESSIBILITY, DATA_ACCURACY_COMPLETENESS_VIOLATION, APPEAL_PROCESS_VIOLATION","Administrative penalty; Technical Advisory Notice"],
])
FT(t)
TC("TABLE XVI: Threat Vectors, Impact, and Security Controls")
t=doc.add_table(rows=1,cols=3); t.style="Table Grid"; t.alignment=WD_TABLE_ALIGNMENT.CENTER
TH(t,["Threat Vector","Potential Impact","Security Control"])
TR(t,[
    ["Indirect Prompt Injection [44][45]","Policy text hijacks LLM to emit false compliance verdicts","NFKC normalization, entropy filter (>=5.5 bits/char), XGrammar CFG logit masking [21]"],
    ["SSRF / Malicious Policy URL","Policy fetch targets internal IPs or cloud metadata","IP blocklist: RFC1918, loopback, link-local, 169.254.169.254 ranges blocked"],
    ["Request Replay / HMAC Forgery","Unauthorized inference invocation or result injection","HMAC-SHA256 over timestamp+nonce; 5-minute replay window enforced"],
    ["Syntactic Output Corruption","Malformed model output disrupts downstream pipeline","XGrammar pushdown CFG guarantees 100% schema validity [21]"],
    ["Legal Citation Confabulation","Fictitious section numbers causing false verdicts","T_statute deterministic lookup; model restricted to 26 validated enum keys"],
])
FT(t)
print("appendix ok")
