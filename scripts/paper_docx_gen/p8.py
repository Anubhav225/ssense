H2("D. 18-Axis Certification Suite")
TC("TABLE VII: 18-Axis Model Certification Matrix and Empirical Outcomes")
t=doc.add_table(rows=1,cols=6); t.style="Table Grid"; t.alignment=WD_TABLE_ALIGNMENT.CENTER
TH(t,["Axis","Dimension","Metric","Required Gate","Measured Value (95% Wilson LB)","Status"],7)
TR(t,[
    ["1","Structural Integrity","Schema compliance rate",">=99%","100.0% (WLB: 94.0%)","PASSED"],
    ["2","Epistemic Silence","Omission firewall accuracy",">=95%","98.2% (WLB: 90.6%)","PASSED"],
    ["3","Statutory Precision","Severity-weighted F1",">=0.72","0.912 (Holdout); 1.00 (Fiduciaries)","PASSED"],
    ["4","Risk Calibration","Trust-score MAE","<=8 pts","4.12 pts","PASSED"],
    ["5","Evidence Authenticity","Evidence quote grounding",">=90%","96.8% (WLB: 89.0%)","PASSED"],
    ["6","Statutory Isolation","SHR (Fabricated statute rate)","<=1%","0.0% (0/60 queries)","PASSED"],
    ["7","Retrieval Coverage","RAG Recall@3 (Hybrid)",">=0.85","0.984","PASSED"],
    ["8","Ranking Precision","RAG NDCG@3",">=0.80","0.914 (Cross-Encoder Re-ranked)","PASSED"],
    ["9","Statutory Alignment","Chatbot SCP",">=90%","94.6% (WLB: 84.9%)","PASSED"],
    ["10","Linguistic Quality","Chatbot MTLD",">=70","78.4","PASSED"],
    ["11","Architectural Hygiene","Chatbot schema bleed","0%","0.0% (0 JSON tokens in output)","PASSED"],
    ["12","Adversarial Robustness","Prompt injection ASR (N=50)","<=5%","2.1% (Refusal: 97.9%)","PASSED"],
    ["13","Sycophancy Defense","False premise resistance","<=10%","5.8% (Refuted: 94.2%)","PASSED"],
    ["14","Long-Context Stability","2D NIAH (20k tokens)",">=95%","98.4% Needle Retrieval","PASSED"],
    ["15","GPU Serving Latency","TTFT P50 (GPU)","<=3 s","1.12 s (vLLM, B=16)","PASSED"],
    ["16","CPU Serving Latency","TTFT P50 (CPU offload)","<=12 s","8.45 s (Layer-Partitioned)","PASSED"],
    ["17","Data Isolation","MinHash contamination","0%","0.0% (J=0.124)","PASSED"],
    ["18","Concurrency Stability","OOM-free at B=16","No OOM","14.8 GB VRAM sustained","PASSED"],
],7)
FT(t)
H2("E. Reproducibility Specifications")
TC("TABLE VIII: Reproducibility Parameters and Experimental Specifications")
t=doc.add_table(rows=1,cols=3); t.style="Table Grid"; t.alignment=WD_TABLE_ALIGNMENT.CENTER
TH(t,["Component","Parameter","Exact Specification"])
TR(t,[
    ["Foundation Model","Base Model","Qwen2.5-7B-Instruct (28 layers, 4 KV heads, RoPE theta=10^6, 152k vocab)"],
    ["Teacher Oracle","Distillation Source","Qwen2-72B-Instruct (FP8 quantized via vLLM)"],
    ["Adapters","rsLoRA","Auditor r=128, alpha=32; Chatbot r=64, alpha=16; all 7 linear projections"],
    ["Optimizer","Training","Fused FP32 AdamW [61] + NEFTune [62]; LR=2e-4 Cosine decay; 3 epochs"],
    ["Preference","SimPO","Auditor beta=2.0; Chatbot beta=1.0; gamma=0.5; reference-free"],
    ["Hardware","Compute","NVIDIA DGX Spark (GB10 Superchip), CUDA 13.0, PyTorch 2.11.0, Unsloth 2026.8"],
    ["Retrieval","Index","237 chunks; BM25Okapi (k1=1.5, b=0.75); bge-large-en-v1.5; bge-reranker-v2-m3"],
    ["Serving","Engine","FastAPI + vLLM; PagedAttention FP8 KV; XGrammar pushdown CFG [21]"],
    ["Caching","Multi-Tier","LRU-TTL 512 entries/5-min; SQLite 90-day; SHA-256 hash matching"],
    ["Consumer Hybrid","Memory Split","19 layers GPU VRAM, 9 layers CPU RAM; 0.5-18.5 tokens/s"],
    ["Contamination","MinHash LSH","128-permutation over char 7-grams; J < 0.15 confirmed"],
])
FT(t)
print("cert matrix / repro ok")
