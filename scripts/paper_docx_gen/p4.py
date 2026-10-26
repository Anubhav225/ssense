H1("III. LITERATURE SURVEY")
H2("A. Legal-Domain Foundation Models")
BP("Dahl et al. [1] revealed LLM hallucination rates 58-88% on legal questions. LegalBench [2] introduced 162 legal tasks. LEGAL-BERT [22] established domain pre-training superiority; LexGLUE [23] standardized evaluation. SaulLM-7B [24] demonstrated 7B legal models rival proprietary APIs. DISC-LawLLM [25] and ChatLaw [26] formalized legal syllogistic tuning. In India, InLegalBERT [4] and Aalap [5] target retrospective litigation. LawInstruct [27] and Louis et al. [28] advance retrieval-augmented legal QA.")
H2("B. Synthetic Data Distillation and Preference Alignment")
BP("Self-Instruct [29] established the generate-filter-tune pattern. Orca [30] and MiniLLM [31] demonstrate explanation-trace distillation. Reflexion [32] enables verbal self-reflection for correction. FLAME [18] warned standard alignment rewards length over factual correctness. Model collapse [34] from synthetic training requires MinHash LSH deduplication [35][36]. Italiani et al. [33] extended distillation to legal QA. RAFT [43] adapts models to domain-specific RAG settings.")
H2("C. Automated Privacy Policy Compliance Analysis")
BP("OPP-115 [10] provided 115 annotated policies. Polisis [11] applied hierarchical CNNs. GDPR: Liu et al. [7] combined classification with rules (304 policies); CompLicy [8] mapped 89 GDPR terms; C3PA [9] annotated CCPA. PrivComp-KG [37] integrated KGs with LLMs; Chen et al. [38] applied entailment for healthcare; GKC-CI [40] applied Contextual Integrity [39]; Cory et al. [41] performed word-level GDPR annotation. No prior work bridges to verifiable DPDP statutory reasoning.")
H2("D. DPDP-Specific Auditing: APLiance [3]")
BP("APLiance evaluated 25 corporate policies (400 labeled pairs) with GPT-5.4-mini + ABAC, reporting 94.5% macro-accuracy. Unambiguous consent scored only 64.0% accuracy and 14.0% recall. Zero of 25 policies (0%) were found compliant due to the silence penalty. APLiance covers only Sections 1-7 and lacks serving infrastructure.")
TC("TABLE II: Compliance-Checking Studies Compared")
t=doc.add_table(rows=1,cols=5); t.style="Table Grid"; t.alignment=WD_TABLE_ALIGNMENT.CENTER
TH(t,["Study","Regulatory Target","Scale & Headline Figure","Methodology","Enforcement"],7)
TR(t,[
    ["OPP-115 [10]","Descriptive taxonomy","115 policies, 23,194 practices","Manual annotation","None"],
    ["Polisis [11]","Descriptive taxonomy","115 policies, neural tagging","Deep learning","None"],
    ["Liu et al. [7]","GDPR Art. 13","36,610 sentences, 304 policies","Classification + rules","None"],
    ["CompLicy [8]","GDPR","89 terms; 148 platforms","Rule inventory","None"],
    ["C3PA [9]","CCPA","225 policies; 14,000+ segments","Multi-task extraction","None"],
    ["PrivComp-KG [37]","General privacy","100 policies; KG triples","LLM + Knowledge Graph","None"],
    ["GKC-CI [40]","Contextual Integrity","21,588 annotations; 90.65% acc","Fine-tuned classifiers","None"],
    ["APLiance [3]","DPDP SS1-7","25 policies; 94.5% acc","Prompted GPT-5.4-mini + ABAC","None"],
    ["Ssense (Ours)","DPDP 2023+Rules","10+60 policies; 18-axis cert","Fine-tuned Law-LM + SCL + CFG","Deterministic audit"],
],7)
FT(t)
H1("IV. RESEARCH GAP ANALYSIS")
BP("Seven critical research gaps motivate Ssense. RG-1: No scalable high-throughput DPDP compliance serving engine exists. RG-2: No open-weights DPDP-aligned model is publicly available. RG-3: Inability to separate statutory silence from legal breach leads to catastrophic false positive rates. RG-4: Multi-head attention decay over long contracts (>8,000 tokens) causes false negatives. RG-5: Syntactic drift in structured legal output without grammar constraints. RG-6: Extraterritorial statutory evasion by global platforms exploiting weak automated detection. RG-7: Citizen-facing legal explanations lack statutory provenance and audit traceability.")
TC("TABLE III: Capability Comparison with Representative Prior Systems")
t=doc.add_table(rows=1,cols=8); t.style="Table Grid"; t.alignment=WD_TABLE_ALIGNMENT.CENTER
TH(t,["System","Target","Domain-Tuned","Open-Weights","Deontic Model","Silence Firewall","Neuro-Symbolic","High-Throughput"],6.5)
TR(t,[
    ["Liu et al. [7]","GDPR","No (BERT)","No","Rule layer","No","No","No"],
    ["CompLicy [8]","GDPR","No (Rules)","No","89 terms","No","No","No"],
    ["Cory et al. [41]","GDPR","No (LLM)","No","21 cats","No","No","No"],
    ["APLiance [3]","DPDP SS1-7","No (GPT-5.4)","No","ABAC","No","Rule engine","No"],
    ["Ssense (Ours)","DPDP 2023+Rules","Yes (rsLoRA+SimPO)","Yes","26-node tree","Yes","Yes (SCL)","Yes"],
],6.5)
FT(t)
print("lit survey / gaps ok")
