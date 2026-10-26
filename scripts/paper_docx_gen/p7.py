H1("VII. EMPIRICAL EVALUATION FRAMEWORK")
H2("A. Research Questions")
RQs=[
    ("RQ1","(Statutory Detection Efficacy): Can the fine-tuned Law-LM with SCL and Omission Firewall detect DPDP breaches with high severity-weighted F1 while eliminating false positives and statutory confabulations?"),
    ("RQ2","(Component Ablations): What are the isolated empirical contributions of rsLoRA, SimPO, the Omission Firewall, the SCL backstop, and Cross-Encoder re-ranking?"),
    ("RQ3","(Hybrid Retrieval): Does hybrid BM25+Dense BGE+Cross-Encoder achieve superior statutory recall over isolated retrievers across 237 chunks?"),
    ("RQ4","(Adversarial Security): Does the aligned SLM resist prompt injection, sycophantic steering, JSON fuzzing, and Lost-in-the-Middle degradation up to 20,000 tokens?"),
    ("RQ5","(Inference Scalability): How does the serving engine scale under concurrency B=1 to 16?"),
]
for rq,txt in RQs:
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.left_indent=Pt(14); p.paragraph_format.space_after=Pt(1)
    r1=p.add_run(rq); r1.bold=True; r1.font.size=Pt(10); r1.font.name="Times New Roman"
    r2=p.add_run(" "+txt); r2.font.size=Pt(10); r2.font.name="Times New Roman"
H2("B. Stratified Evaluation Corpora")
BP("Strategic Indian Fiduciary Corpus (N=10): Ten high-traffic Indian digital platforms representing >500M MAU across six sectors -- Food-Tech (Zomato, Swiggy, Nykaa); FinTech (Paytm, Zerodha, Groww, CRED); Travel (MakeMyTrip, redBus); Health-Tech (Tata 1mg). Length disparity: Paytm 490 tokens to MakeMyTrip 16,000 tokens (33:1 ratio), stress-testing long-context stability.")
BP("Controlled Synthetic Holdout (N=60): Stratified across: Silo 1 (Baseline Literal, 30%, N=18) -- overt unambiguous statutory breaches; Silo 2 (Camouflage/Evasion, 50%, N=30) -- deceptive legalese, cross-clause contradictions; Silo 3 (Adversarial Safe-Harbor Traps, 20%, N=12) -- fully compliant policies designed to trigger superficial alarms. MinHash LSH confirmed zero contamination (max Jaccard J=0.124 < 0.85).")
TC("TABLE VI: Stratified Fiduciary Pilot Testbed Corpus")
t=doc.add_table(rows=1,cols=5); t.style="Table Grid"; t.alignment=WD_TABLE_ALIGNMENT.CENTER
TH(t,["Fiduciary","Sector","Policy Length","Est. Tokens","Primary Data Categories"])
TR(t,[
    ["Zomato","Food-Tech / Delivery","14,820 chars","~3,700 tokens","GPS, order history, device IDs"],
    ["Swiggy","Food-Tech / Quick-Commerce","18,450 chars","~4,610 tokens","Geolocation, delivery logs, payment tokens"],
    ["Nykaa","E-Commerce / Retail","12,300 chars","~3,075 tokens","Shipping addresses, beauty preferences"],
    ["Paytm","FinTech / Digital Payments","1,962 chars","~490 tokens","Transaction logs, KYC, payment hashes"],
    ["Zerodha","Brokerage / Capital Markets","8,420 chars","~2,105 tokens","PAN/Aadhaar, demat records, trading history"],
    ["Groww","FinTech / Investments","9,150 chars","~2,285 tokens","Investment profiles, KYC, MF transactions"],
    ["CRED","FinTech / Credit Services","11,200 chars","~2,800 tokens","Credit statements, bank SMS, credit scores"],
    ["MakeMyTrip","Travel / Hospitality","64,000 chars","~16,000 tokens","Passport, itineraries, biometric check-ins"],
    ["Tata 1mg","Health-Tech / Pharmacy","22,600 chars","~5,650 tokens","Prescriptions, diagnostic reports"],
    ["redBus","Travel / Intercity Ticketing","15,400 chars","~3,850 tokens","Passenger manifests, location tracking"],
])
FT(t)
H2("C. Algorithmic Evaluation Metrics")
BP("1) Optimal Bipartite Multi-Violation F1: max-weight bipartite matching over P={p_i} x G={g_j}, weight W(p_i,g_j) = w(s_j)*I(type match)*I(section match), w(Critical)=1.0, w(High)=0.8, w(Medium)=0.6, w(Low)=0.4. 2) SHR: citations outside DPDP S.1-44, Rules 1-22. JCR: foreign provisions (GDPR/CCPA) in rationales. 3) Context Faithfulness (CF): CoT LLM-as-judge [54][55][56] scoring s_CF in [1,5]. 4) McNemar: chi2 = (|n_01-n_10|-1)^2/(n_01+n_10). 5) Wilson 95% CI: [p_hat + z^2/(2N) +/- z*sqrt(p_hat(1-p_hat)/N + z^2/(4N^2))] / [1+z^2/N], z=1.96.")
print("evaluation framework ok")
