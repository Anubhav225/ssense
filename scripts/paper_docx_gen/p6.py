H1("VI. LAW-LM ARCHITECTURE AND SCALABLE INFERENCE ENGINE")
H2("A. System Overview")
BP("Ssense has four core components: (i) asynchronous statutory extraction and policy normalization engine; (ii) domain-adapted Legal SLM (Ssense-DPDP-7B); (iii) deterministic Statutory Compliance Layer (SCL); (iv) high-throughput inference serving architecture. The system ingests raw policy documents, evaluates them against T_statute, and emits schema-bound, cryptographically auditable JSON verdicts.")
H2("B. Statutory Corpus and Hybrid Retrieval Grounding")
BP("The corpus of 237 statutory chunks (44 DPDP Act sections + 22 Rules) is indexed via two parallel engines: (1) Lexical BM25 (k1=1.5, b=0.75) for exact statutory terminology; (2) Dense BAAI/bge-large-en-v1.5 for semantic matching. Merged via RRF: Score_RRF(c) = sum_{m in {BM25,Dense}} I(c in TopRank_m) / (k_rrf + rank_m(c)), k_rrf=60. Re-ranked by bge-reranker-v2-m3 neural cross-encoder with LRU embedding cache (2,048 entries).")
H2("C. Synthetic Training Data, rsLoRA, SimPO, and Open-Weights Release")
BP("Because no DPDP-annotated corpus existed, training pairs were synthesized via a generate-filter-retry loop: Qwen2-72B-Instruct teacher (FP8 via vLLM) generated structured audits over policy excerpts with retrieved statutory context. Samples were filtered for JSON validity, omission compliance, and citation correctness. Failures regenerated (retry k=3) using Reflexion-style [32] error feedback. MinHash 7-gram LSH confirmed zero contamination (max Jaccard J=0.124 < 0.85; [35][36]).")
BP("For preference alignment, subtle legal defects were injected into compliant policies to create rejected samples y_l. rsLoRA adapters trained with r=128, alpha=32 (auditor) and r=64, alpha=16 (dialogue). SimPO applied with beta=2.0 (auditor) and beta=1.0 (dialogue), gamma=0.5. After training, adapters were merged into base Transformer weights producing standalone open-weights Ssense-DPDP-7B (safetensors BF16).")
TC("TABLE V: Law-LM Dual-Track Model Specifications")
t=doc.add_table(rows=1,cols=3); t.style="Table Grid"; t.alignment=WD_TABLE_ALIGNMENT.CENTER
TH(t,["Property","Forensic Statutory Auditor","Conversational Legal Dialogue"])
TR(t,[
    ["Base Model","Qwen2.5-7B-Instruct (28 layers, GQA, RoPE theta=10^6, 152k vocab)","Qwen2.5-7B-Instruct (28 layers, GQA, RoPE theta=10^6, 152k vocab)"],
    ["Context Window","8,192 tokens","4,096 tokens"],
    ["Output Format","Strict dpdp_schema.json via XGrammar CFG","Markdown Legal Reasoning"],
    ["rsLoRA Rank / Alpha","128 / 32 (effective scale = alpha/sqrt(r) = 2.83)","64 / 16 (effective scale = 2.00)"],
    ["Target Modules","All 7 linear projections (q, k, v, o, gate, up, down)","All 7 linear projections"],
    ["SimPO Beta","2.0 (strict factuality)","1.0 (conversational fluency)"],
    ["Training Hardware","NVIDIA DGX Spark (GB10 Superchip), CUDA 13.0, Unsloth 2026.8","NVIDIA DGX Spark (GB10 Superchip), CUDA 13.0, Unsloth 2026.8"],
    ["Released Artifact","Merged BF16 Open-Weights (Ssense-DPDP-7B)","Standalone LoRA Adapter + Merged Weights"],
])
FT(t)
H2("D. Output Contract, Omission Firewall, and SCL")
BP("The auditor emits JSON with: global_legal_reasoning, violations[], dpdp_trust_score (int, [0,100]), subtlety_score (int, [0,100]). Every violation executes the three deductive steps. V_final = V_SLM union {v in V_SCL | exists e in T_policy: e |= R_v and e not|= H_v}, where R_v is violation regex and H_v is safe-harbor lookaround. This union ensures no false negatives on explicitly worded admissions while safe-harbor lookarounds prevent spurious flags on PMLA/SEBI statutorily-protected retention.")
H2("E. Multi-Tier Cache Hierarchy")
BP("Five-stage caching: (1) In-Memory LRU-TTL Cache (512 entries, 5-min TTL) resolving burst queries in <1 ms; (2) Persistent SQLite Domain Store (90-day TTL); (3) Cryptographic SHA-256 Policy Hash Matching serving cached audits if text unchanged; (4) Concurrent Request Coalescing via atomic mutex on key kappa = domain || hash; (5) SLM Execution on complete cache miss. Cache hit rates: LRU 42.1%, SQLite 51.9%; SLM invocations reduced by ~94%.")
H2("F. Inference Optimizations: PagedAttention, Speculative Decoding, XGrammar")
BP("PagedAttention [48]: KV cache in non-contiguous 16-token physical blocks, capping peak FP8 VRAM at 14.8 GB across B=16 streams, preventing OOM versus naive allocation requiring >24 GB. Continuous Batching (vLLM): requests inserted at iteration boundaries for maximal tensor core utilization. S-LoRA [49]: forensic (r=128) and dialogue (r=64) adapters on shared base with sub-ms adapter swapping. Prompt KV Pre-Warming [50]: 1,200-token system prompt held in GPU SRAM (<15 ms prefill). Speculative Lookup Decoding [51] (k=3): n-gram overlap delivers 1.8x end-to-end speedup. XGrammar [21]: Logits'_t(w) = Logits_t(w) if w in CFG(q_t) else -inf, guaranteeing 100% schema validity.")
H2("G. Consumer Hardware Deployment")
BP("Layer-partitioned hybrid execution: 19 layers on GPU VRAM (reserved: 6.0 GB), 9 layers offloaded to CPU RAM; throughput 0.5-18.5 tokens/s on commodity hardware. TTFT P50 on CPU offload: 8.45 s vs. 1.12 s on full GPU (Table XII), establishing deployment viability across low-cost regulatory monitoring environments.")
print("architecture ok")
