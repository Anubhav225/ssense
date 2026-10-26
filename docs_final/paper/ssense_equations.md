# Ssense: Mathematical Formulations and System Equations

This document compiles the unique mathematical models, decision-making algorithms, and optimization equations that govern the **Ssense** DPDP Act compliance architecture. These formulations are specifically engineered to bridge probabilistic Large Language Models (LLMs) with deterministic legal enforcement.

---

## 1. Machine Learning & Alignment Optimizations

### 1.1 Simple Preference Optimization (SimPO)
Ssense utilizes **SimPO** rather than traditional RLHF or DPO to align the SLM (Qwen2.5-7B-Instruct). SimPO eliminates the need for a reference model, effectively halving the VRAM requirement during the Unsloth training phase. The alignment objective is formalized as:

$$ \mathcal{L}_{\text{SimPO}} = -\mathbb{E}\left[ \log \sigma \left( \frac{\beta}{|y_w|} \log \pi_\theta(y_w | x) - \frac{\beta}{|y_l|} \log \pi_\theta(y_l | x) - \gamma \right) \right] $$

* **$y_w$**: The chosen (high-quality, schema-valid, legally accurate) audit response.
* **$y_l$**: The rejected (hallucinated or omission-heavy) response.
* **$\beta$**: Margin scaling factor governing the strictness of the forensic auditor.
* **$\gamma$**: Target reward margin ensuring a distinct separation between compliant and hallucinated outputs.

### 1.2 Rank-Stabilized LoRA (rsLoRA)
To prevent gradient collapse when scaling the rank ($r$) for complex legal reasoning, Ssense's adapter utilizes the **rsLoRA** scaling factor. Unlike standard LoRA which scales by $\frac{\alpha}{r}$, rsLoRA scales by the square root:

$$ \Delta W = \frac{\alpha}{\sqrt{r}} A B $$

This mathematical stabilization is crucial for allowing the SLM to retain pre-trained language capabilities while absorbing the highly specialized DPDP legal corpus.

---

## 2. Hybrid Retrieval-Augmented Generation (RAG) Convergence

### 2.1 Dual-Index Convex Combination
The 237-chunk legal context is retrieved using a dual-index architecture to capture both exact statutory phrasing and semantic intent. For a given legal query $q$ and text chunk $c$, the initial hybrid retrieval score is a convex combination of normalized BM25 (Lexical) and BGE (Dense) vectors:

$$ S_{hybrid}(q, c) = \alpha \cdot \frac{S_{BM25}(q, c)}{\max_{i}(S_{BM25})} + (1 - \alpha) \cdot \frac{S_{BGE}(q, c)}{\max_{j}(S_{BGE})} $$

* **$\alpha$**: Weighting factor dictating reliance on exact terminology vs. semantic meaning.

### 2.2 Cross-Encoder Re-Ranking
The top-$K$ candidates retrieved by the hybrid formula are passed through a deep Cross-Encoder, which calculates the final contextual relevance by computing attention across both the query and the chunk simultaneously:

$$ S_{final} = \text{CrossEncoder}(q, \text{TopK}_{hybrid}(C)) $$

This convergence ensures that the context window injected into the SLM is mathematically grounded in the actual DPDP Act 2023, minimizing external hallucinations.

---

## 3. Deterministic Decision Making & Legal Enforcement

### 3.1 The 26/44 Bureaucracy Firewall (Statutory Pruning)
The DPDP Act comprises 44 sections. Ssense mechanically prunes administrative sections ($\mathcal{S}_{admin}$) such as Data Protection Board setup and Appellate Tribunals, narrowing the focus to enforceable Data Fiduciary phenotypes ($\mathcal{P}_{enforce}$):

$$ \mathcal{P}_{enforce} = \mathcal{S}_{total} \setminus ( \mathcal{S}_{admin} \cup \mathcal{S}_{tribunal} ) $$

This mapping condenses 44 theoretical sections into exactly **26 unique, machine-enforceable violation phenotypes** (e.g., `CONSENT_NOT_FREE_OR_SPECIFIC`).

### 3.2 The Statutory Compliance Layer (SCL) Backstop
Because SLMs suffer from "negation blindness" and probabilistic attention decay over long contexts, Ssense introduces the SCL. It acts as a mathematically lossless union operator, combining the SLM-detected violations ($V_{SLM}$) with regex-detected deterministic violations ($V_{SCL}$), provided they survive the safe-harbor filters:

$$ V_{final} = V_{SLM} \cup \left\{ v \in V_{SCL} \mid \text{regex\_match}(\mathcal{P}_{text}, R_v) \land \neg \text{safe\_harbor}(\mathcal{P}_{text}, H_v) \right\} $$

* **$R_v$**: The strict regex pattern denoting a violation (e.g., "retain data indefinitely").
* **$H_v$**: The safe-harbor pattern that legally excuses the behavior (e.g., "unless required by law").

---

## 4. Hardware Inference & Multi-Tenant Orchestration

### 4.1 Task Key Hash (Request Coalescing)
To safely isolate multiple concurrent users while optimizing GPU throughput, the `MemoryOrchestrator` computes a cryptographic deterministic state hash for every incoming request:

$$ \text{TaskKey} = \text{SHA256}(\text{Operation} \parallel \text{UserID} \parallel \text{DomainURL} \parallel \text{PromptState}) $$

This guarantees that identical requests from different tabs are coalesced into a single inference pass, preventing redundant compute cycles, while strictly isolating different users' memory states.

### 4.2 Unified VRAM Hardware Partitioning
For inference on unified memory architectures (hybrid GPU-CPU processing), the total inference latency ($T_{infer}$) is optimized by splitting the Transformer layers ($L_{total}$) across discrete physical processors to eliminate PCIe bottlenecking:

$$ T_{infer} = \sum_{i=1}^{L_{GPU}} T_{VRAM}(l_i) + \sum_{j=L_{GPU}+1}^{L_{total}} T_{RAM}(l_j) + \text{Overhead}_{transfer} $$

By keeping layer computation physically grouped (e.g., 19 layers on GPU VRAM, remaining layers on CPU RAM) and using native BF16 quantization, Ssense minimizes $\text{Overhead}_{transfer}$ (the ping-pong swapping between CPU and GPU), ensuring the lowest possible latency for real-time web auditing.
