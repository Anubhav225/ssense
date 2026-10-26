H1("VIII. RESULTS AND EMPIRICAL DISCUSSION")
H2("A. Fiduciary Audit Outcomes: Zero Hallucinations, Zero False Positives")
BP("End-to-end statutory audits across ten strategic Indian digital fiduciaries (>500M MAU) confirmed exactly three actionable statutory violations with zero false positives against gold-standard legal expert consensus and zero fabricated citations (SHR=0.00%, FPR=0.00%).")
TC("TABLE IX: Confirmed Statutory Violations and Severity Classification")
t=doc.add_table(rows=1,cols=6); t.style="Table Grid"; t.alignment=WD_TABLE_ALIGNMENT.CENTER
TH(t,["Fiduciary","Sector","Confirmed Breach","DPDP Sections","Severity","Legal Evidence"],7)
TR(t,[
    ["Zomato","Food-Tech","NOTICE_INADEQUATE","S.5(1), Rule 3","Medium","Blanket behavioral telemetry without itemized ad-exchange disclosures per S.5(1) itemization mandate"],
    ["Swiggy","Food-Tech","PURPOSE_LIMITATION_VIOLATION","S.8(7), S.4(1)","High","Perpetual retention of order logs for unspecified 'service evolution'; violates S.8(7) erasure duty"],
    ["redBus","Travel","LEGITIMATE_USES_ABUSE","S.7","High","Claims broad 'legitimate business operations'; invalid under S.7 closed list"],
    ["Paytm","FinTech","None detected","--","Clean (Safe-Harbor)","Retention tied to PMLA/RBI statutory mandates; SCL lookaround confirmed"],
    ["Zerodha","Brokerage","None detected","--","Clean (Safe-Harbor)","Processing bounded by SEBI/KYC statutory regulations"],
    ["Groww","FinTech","None detected","--","Clean (Safe-Harbor)","Compliant withdrawal; retention by mutual fund regulation"],
    ["CRED","FinTech","None detected","--","Clean (Safe-Harbor)","Itemized notice; explicit withdrawal procedures"],
    ["MakeMyTrip","Travel","None detected","--","Clean (Safe-Harbor)","Cross-border booking transfers under S.17 safe harbor"],
    ["Tata 1mg","Health-Tech","None detected","--","Clean (Safe-Harbor)","Prescription processing under S.7(b) medical emergency safe harbor"],
    ["Nykaa","E-Commerce","None detected","--","Clean (Safe-Harbor)","Clear itemized disclosure; explicit account deletion procedure"],
],7)
FT(t)
BP("Jurisprudential Analysis. (1) Zomato S.5(1): mandates itemized notice of personal data to be collected and specific purposes. Zomato deployed blanket language asserting behavioral data collection 'to improve services and deliver advertising,' omitting mandatory itemized ad-exchange category breakdowns as required by Rule 3(1). (2) Swiggy S.8(7) and S.4(1): stated order history and device coordinates retained indefinitely 'to enhance algorithmic efficiency,' violating S.8(7) erasure-upon-purpose-completion mandate and compounding S.4(1) data quality duty. (3) redBus S.7: claimed broad 'reasonable legitimate business operations' for passenger data monetization. India's S.7 provides a closed, exhaustive enumeration of nine legitimate uses; commercial advertising profiling without S.6 consent is legally invalid -- a fundamental doctrinal contrast with GDPR's open-ended legitimate interests balancing test.")
BP("FinTech Safe Harbor Resolution: Paytm, Zerodha, and Groww declared multi-year retention tied to PMLA/SEBI statutory mandates. Unadapted baselines routinely flag these as violations. Ssense's SCL safe-harbor lookarounds correctly identified these as protected under S.8(7) provisos and S.17, sustaining 0.00% FPR across all ten fiduciaries.")
H2("B. Comparative Benchmarking against SOTA Baselines")
TC("TABLE X: Empirical Performance vs. SOTA Baselines")
t=doc.add_table(rows=1,cols=5); t.style="Table Grid"; t.alignment=WD_TABLE_ALIGNMENT.CENTER
TH(t,["Evaluation Dimension","Qwen2.5-7B (Unadapted)","GPT-4o-mini (Zero-Shot)","APLiance [3]","Ssense-DPDP-7B (Ours)"],7)
TR(t,[
    ["Open-Weights Release","Yes (Base Only)","No","No","Yes (Ssense-DPDP-7B)"],
    ["Domain Adaptation","None","Prompt Engineering","Prompt Engineering","rsLoRA (r=128) + SimPO (beta=2.0)"],
    ["Schema Compliance Rate","71.4%","92.5%","N/A (Parser)","100.0% (XGrammar CFG)"],
    ["Severity-Weighted F1","0.481","0.692","0.945* (attribute)","0.912 (Holdout) / 1.00 (Fiduciaries)"],
    ["Statute Citation Validity","56.2%","81.4%","Not Reported","100.0% (Zero Confabulation)"],
    ["Evidence Quote Grounding","75.4%","91.8%","Not Reported","96.8% (Verbatim in Source)"],
    ["Jurisdictional Contamination","34.0% (GDPR Bleed)","18.0%","N/A (Symbolic)","0.0%"],
    ["Silence Handling","Treats as breach","Treats as breach","Conservative-Unknown","Omission Firewall (98.2%)"],
    ["Context Faithfulness (CF)","2.84/5.00","4.15/5.00","Not Reported","4.82/5.00"],
    ["False Positive Rate",">30% (est.)","~18% (est.)","~100% (0/25 compliant)","0.00%"],
],7)
FT(t)
BP("Statistical Tests: Ssense vs. Qwen2.5-7B: McNemar chi2=28.4 (p<0.001), rejecting equivalence. Ssense vs. GPT-4o-mini: chi2=14.2 (p<0.001), demonstrating rsLoRA+SimPO domain alignment outperforms commercial API zero-shot prompting on this domain. Context Faithfulness: paired t-test t=9.86 (p<0.001) confirming CF improvement (4.82 vs 4.15). *APLiance reports attribute-level accuracy not directly comparable to violation-level F1.")
print("results part 1 ok")
