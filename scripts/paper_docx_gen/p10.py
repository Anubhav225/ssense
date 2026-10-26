H2("C. Component Ablation Study")
TC("TABLE XI: Systematic Component Ablation Study")
t=doc.add_table(rows=1,cols=7); t.style="Table Grid"; t.alignment=WD_TABLE_ALIGNMENT.CENTER
TH(t,["Architecture Configuration","F1 (Weighted)","Precision","Recall","FPR","SHR","Schema Compliance"],7)
configs=[
    (["Full Ssense Framework","0.912","0.941","0.885","0.00%","0.00%","100.0%"],True),
    (["(i) w/o Deterministic SCL Backstop","0.835","0.945","0.748","0.00%","0.00%","100.0%"],False),
    (["(ii) w/o Epistemic Omission Firewall","0.744","0.628","0.912","37.20%","0.00%","100.0%"],False),
    (["(iii) w/o SimPO (SFT-Only)","0.814","0.820","0.808","8.40%","7.40%","100.0%"],False),
    (["(iv) w/o Pushdown CFG Masking","0.890","0.932","0.852","1.20%","0.00%","84.6%"],False),
    (["(v) w/o Cross-Encoder Re-Ranking","0.862","0.885","0.840","3.50%","1.80%","100.0%"],False),
]
for rd, bold in configs:
    row=t.add_row()
    for i,v in enumerate(rd):
        if i < len(row.cells):
            c=row.cells[i]; c.text=v
            for run in c.paragraphs[0].runs:
                run.font.size=Pt(7); run.font.name="Times New Roman"
                if bold: run.bold=True
FT(t)
BP("Key ablation insights: (1) SCL removal: Recall drops 13.7pp (0.885 to 0.748) -- attention dispersion over verbose policies causes missed explicit admissions; SCL union closes this gap. (2) Omission Firewall removal: Precision plummets 0.941 to 0.628; FPR surges 37.20%, reproducing APLiance's silence penalty pathology. (3) SimPO removal: 7.40% SHR and 8.40% FPR emerge, confirming SimPO length-normalized margin regularizes over-calling. (4) CFG removal: Schema compliance drops 100% to 84.6%, generating 23.1% malformed JSON requiring fallback. (5) Cross-Encoder removal: NDCG@3 degrades 0.914 to 0.812 as first-stage retrieval misranks statutory paraphrases.")
H2("D. Inference Serving Telemetry")
TC("TABLE XII: Inference Serving Telemetry across Batch Sizes (GPU, FP8, B=1-16)")
t=doc.add_table(rows=1,cols=8); t.style="Table Grid"; t.alignment=WD_TABLE_ALIGNMENT.CENTER
TH(t,["Batch Size","Mean Latency (s)","TTFT P50 (ms)","TTFT P95 (ms)","P99 Latency (s)","Throughput (tok/s)","Peak VRAM (GB)","OOM Rate"],7)
TR(t,[
    ["B=1 (Single Stream)","1.14","420","840","1.82","42.5","8.4","0.0%"],
    ["B=4 (Standard Load)","1.58","680","1,240","2.25","112.4","9.6","0.0%"],
    ["B=8 (High Load)","2.12","890","1,510","2.94","198.6","11.8","0.0%"],
    ["B=16 (Peak Capacity)","3.42","1,120","1,840","4.15","312.8","14.8","0.0%"],
],7)
FT(t)
BP("PagedAttention prevents OOM at B=16 where naive allocation requires >24 GB. Scaling B=1 to B=16 yields 7.36x throughput gain (42.5 to 312.8 tok/s) while mean latency remains bounded at 1.14-3.42 s. Multi-tier caching: LRU-TTL resolves 42.1% of repeat requests in <1 ms; SQLite 51.9% at 3.8 ms average; SHA-256 deduplication eliminates redundant SLM invocations. Speculative decoding (k=3, prompt n-gram overlap) delivers 1.8x additional speedup without an auxiliary draft model.")
H2("E. Citizen Legal Dialogue Performance")
BP("The citizen dialogue adapter evaluated across four high-frequency privacy queries: third-party marketing sharing, transaction data retention post-deletion, cookie consent refusal consequences, payment tokenization security. Streaming TTFT: 480 ms (GPU). Context Faithfulness CF=4.82/5.00 (near-perfect statutory fidelity with offline 72B judge). Statute Citation Precision SCP=94.6% (WLB: 84.9%). Schema Bleed: 0.00% (zero JSON tokens in conversational responses). Lexical Richness: MTLD=78.4.")
H2("F. Adversarial Security and Long-Context Evaluation")
BP("(1) 2D Needle In A Haystack (NIAH, 20k tokens): violating clauses injected at depths 0%, 25%, 50%, 75%, 100%. Ssense achieved 98.4% retrieval, proving RoPE base frequency scaling (theta=10^6) with positional XML structuring eliminates 'Lost in the Middle' [52] attention collapse. (2) Indirect Prompt Injection [44][45]: NFKC normalization + CFG logit masking achieved 97.9% refusal (ASR=2.1% vs. 5% gate). (3) Anti-Sycophancy: SimPO-aligned SLM refuted false premises in 94.2% of cases. (4) JSON Schema Fuzzing: malformed payloads, truncated brackets, high-entropy strings -- zero system crashes (100% fuzzing resilience).")
H2("G. Decision Semantics of Contractual Silence")
TC("TABLE XIII: Silence Decision Semantics: Ssense vs. APLiance [3]")
t=doc.add_table(rows=1,cols=3); t.style="Table Grid"; t.alignment=WD_TABLE_ALIGNMENT.CENTER
TH(t,["Dimension","Ssense Philosophy","APLiance Benchmark [3]"])
TR(t,[
    ["Prerequisite for Violation","Affirmative contradiction in verbatim policy text","Missing attributes or ambiguous declarations"],
    ["Epistemology of Silence","Dropped via Omission Firewall (3-step deductive chain)","Non-declaration treated as non-compliance"],
    ["Statutory Coverage","26 violation types across S.3-S.16, Rules, Schedules 1-3","16 attributes covering Sections 1-7"],
    ["22-Language Notice","Evaluated; handled by affirmative duty analysis","Causes 100% policy failure on silence"],
    ["Audit Resolution","Multi-violation JSON with verbatim evidence and severity weights","Binary COMPLIANT / NON-COMPLIANT"],
    ["False Positive Rate","0.00% (10 fiduciaries, 60-policy holdout)","~100% (0/25 real policies found compliant)"],
])
FT(t)
print("results part 2 ok")
