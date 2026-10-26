# Ssense Training Pipeline: Parameter Audit & Empirical Research Groundings

This document provides a line-by-line audit and rigorous academic investigation of every parameter, training heuristic, and optimization setting implemented in the Ssense fine-tuning engine ([`ml/slm-training/train_audit.py`](file:///d:/Ssense/ml/slm-training/train_audit.py) and [`ml/slm-training/train_chatbot.py`](file:///d:/Ssense/ml/slm-training/train_chatbot.py)). 

Every parameter is mapped to its underlying theoretical foundation, mathematical derivation, and authoritative peer-reviewed literature.

---

## 1. Master Training Parameter Audit Matrix

| Parameter / Configuration | Forensic Legal Auditor | Conversational Chatbot | Governing Research & Citation | Theoretical Justification |
| :--- | :---: | :---: | :--- | :--- |
| **Base Model Architecture** | `Qwen2.5-7B-Instruct` | `Qwen2.5-7B-Instruct` | Qwen Team (2024); Ainslie et al. (*EMNLP 2023*) | GQA (4 KV heads), RoPE base $\theta=10^6$, SwiGLU activations, and structural token compression for JSON. |
| **Context Window (`MAX_SEQ_LENGTH`)** | **8,192 tokens** | **4,096 tokens** | Su et al. (*Neurocomputing 2024*); Dao (*ICLR 2024*) | Ingests multi-page legal terms without attention collapse; chatbot uses 4k for fast multi-turn conversational responses. |
| **Effective Batch Size** | **8** (SFT) / **16** (SimPO) | **8** (SFT) / **16** (SimPO) | Loshchilov & Hutter (*ICLR 2019*) | Micro-batch 1 with gradient accumulation prevents VRAM spikes while providing smooth stochastic gradient trajectory. |
| **SFT Learning Rate (`LR_SFT`)** | **$1.5 \times 10^{-5}$** | **$1.5 \times 10^{-5}$** | Kalajdzievski (*arXiv:2312.03732*) | Optimal learning rate for rsLoRA adapter weights without disturbing frozen base representations. |
| **SimPO Learning Rate (`LR_DPO`)** | **$5.0 \times 10^{-6}$** | **$5.0 \times 10^{-6}$** | Meng, Xia, & Chen (*NeurIPS 2024*) | Low learning rate prevents policy drift and catastrophic forgetting of SFT JSON schemas. |
| **LR Scheduler & Minimum** | `cosine_with_min_lr` ($\eta_{\min} = 0.1$) | `cosine_with_min_lr` ($\eta_{\min} = 0.1$) | Loshchilov & Hutter (*ICLR 2017*) | Decays smoothly to 10% peak LR, avoiding complete freeze and allowing fine parameter adjustments. |
| **Optimizer & State** | `adamw_torch_fused` | `adamw_torch_fused` | Loshchilov & Hutter (*ICLR 2019*) | Decoupled weight decay with fused GPU kernels to eliminate CPU-GPU dispatch latency. |
| **Weight Decay** | **0.05** | **0.05** | Loshchilov & Hutter (*ICLR 2019*) | Regularizes adapter weights, penalizing magnitude explosion in high-rank matrices. |
| **Gradient Clipping (`max_grad_norm`)** | **1.0** | **1.0** | Pascanu, Mikolov, & Bengio (*ICML 2013*) | Prevents loss spikes caused by unusually dense statutory passages. |
| **Numerical Precision** | **BFloat16 (Native)** | **BFloat16 (Native)** | Kalamkar et al. (*2019*) | Matches FP32 dynamic range (8-bit exponent), preventing gradient underflow/overflow during accumulation. |
| **LoRA Rank ($r$) / Alpha ($\alpha$)** | **$r=128$, $\alpha=128$** | **$r=64$, $\alpha=16$** | Kalajdzievski (*arXiv:2312.03732*); Hu et al. (*ICLR 2022*) | High rank captures compound statutory rules; chatbot uses $r=64$ for dialogue fluidity. |
| **Scaling Formula (`use_rslora`)** | **$\alpha / \sqrt{r} \approx 11.31$** | **$\alpha / \sqrt{r} = 2.0$** | Kalajdzievski (*arXiv:2312.03732*) | Overcomes $\mathcal{O}(1/\sqrt{r})$ gradient collapse inherent in standard LoRA scaling ($\alpha/r$). |
| **LoRA Dropout** | **0.0** | **0.0** | Dettmers et al. (*NeurIPS 2023*) | Set to zero to prevent synthetic data under-fitting and regularization redundancy. |
| **Target Linear Projections** | All 7 projections (`q, k, v, o, gate, up, down`) | All 7 projections (`q, k, v, o, gate, up, down`) | Dettmers et al. (*NeurIPS 2023*); Wu & Ma (*ACM DEAI 2025*) | Full linear adaptation is necessary to match full fine-tuning performance in complex reasoning tasks. |
| **Embedding Noise (`neftune_alpha`)** | **5.0** | **5.0** | Jain et al. (*ICLR 2024*) | Injects uniform noise into token embeddings to prevent memorization of synthetic prompt templates. |
| **Loss Masking Scheme** | `train_on_responses_only` | `train_on_responses_only` | ChatML Format | User/system prompts masked with `-100`; gradient energy focuses 100% on assistant completions. |
| **Preference Alignment** | `loss_type="simpo"` | `loss_type="simpo"` | Meng, Xia, & Chen (*NeurIPS 2024*) | Reference-free objective; saves 50% VRAM while normalizing by length to eliminate verbosity bias. |
| **SimPO Reward Scale ($\beta$)** | **2.0** | **1.0** | Meng, Xia, & Chen (*NeurIPS 2024*) | High $\beta$ creates strict schema-boundary enforcement; lower $\beta$ preserves conversational naturalness. |
| **SimPO Target Margin ($\gamma$)** | **0.5** | **0.5** | Meng, Xia, & Chen (*NeurIPS 2024*) | Forces an explicit logit gap between grounded audits and hallucinated outputs. |
| **Pre-Training Token Firewall** | Custom Length Filter | Custom Length Filter | TRL Issue Analysis | Drops sequences $>8192$ tokens prior to batching, preventing silent truncation of trailing JSON brackets. |
| **Citation Trip-Wire** | `preflight_citation_check` | `preflight_citation_check` | Dahl et al. (*2024*); Ma et al. (*COLING 2025*) | Pre-flight audit checking if statutory sections cited in completions exist in prompt context. |
| **Split Strategy** | Grouped on `source_id` | Grouped on `source_id` | Leakage Prevention Standards | Prevents train/test leakage by ensuring policies from the same domain do not straddle partitions. |
| **Process Isolation** | `multiprocessing.Process(spawn)` | `multiprocessing.Process(spawn)` | PyTorch Memory Profiling | Subprocess isolation forces the CUDA driver to release 100% of VRAM between SFT and SimPO phases. |
| **Quantization Format** | Standalone BF16 + GGUF `q4_k_m` | Standalone BF16 + GGUF `q4_k_m` | Gerganov et al. (*llama.cpp*) | Native HuggingFace CPU merge bypasses Unsloth export bugs; GGUF K-quants allow 4.3GB edge execution. |

---

## 2. In-Depth Analysis of Individual Parameter Selections

### 2.1 Rank-Stabilized LoRA Scaling ($\alpha / \sqrt{r}$)
Conventional LoRA uses the update rule:
$$\Delta W = \frac{\alpha}{r} (B \cdot A)$$
When scaling rank $r$ from 16 to 128 to learn the 26 DPDP statutory violation phenotypes, the conventional scaling factor $\frac{\alpha}{r}$ decreases by $8\times$. However, the Frobenius norm of the product of two independent Gaussian matrices scales as:
$$\mathbb{E}[\|B \cdot A\|_F] = \Theta(\sqrt{r})$$
Consequently, the expected magnitude of the parameter update collapses:
$$\|\Delta W\| = \Theta\left( \frac{\alpha}{r} \cdot \sqrt{r} \right) = \Theta\left( \frac{\alpha}{\sqrt{r}} \right) \to 0 \quad \text{as } r \to \infty$$
**Damjan Kalajdzievski (2023)** proved that setting the scaling factor to $\frac{\alpha}{\sqrt{r}}$ stabilizes the update norm:
$$\|\Delta W\|_{\text{rsLoRA}} = \Theta\left( \frac{\alpha}{\sqrt{r}} \cdot \sqrt{r} \right) = \Theta(\alpha)$$
In Ssense:
- For the **Forensic Auditor** ($r=128$, $\alpha=128$):
  $$\gamma_{\text{rsLoRA}} = \frac{128}{\sqrt{128}} = \sqrt{128} \approx 11.314$$
  Standard LoRA would yield $\frac{128}{128} = 1.0$. The rsLoRA formulation provides **$11.31\times$ stronger gradient propagation**, allowing the model to acquire complex multi-step statutory deduction without gradient vanishing.
- For the **Conversational Chatbot** ($r=64$, $\alpha=16$):
  $$\gamma_{\text{rsLoRA}} = \frac{16}{\sqrt{64}} = 2.0$$
  This prevents adapter saturation and preserves conversational empathy and fluency.

---

### 2.2 SimPO Alignment Mechanics ($\beta = 2.0$, $\gamma = 0.5$)
Ssense aligns the model using Simple Preference Optimization (Meng, Xia, & Chen, NeurIPS 2024).

#### The Mathematical Objective
$$\mathcal{L}_{\text{SimPO}}(\theta) = -\mathbb{E}_{(x, y_w, y_l) \sim \mathcal{D}} \left[ \log \sigma \left( \frac{\beta}{|y_w|} \log \pi_\theta(y_w \mid x) - \frac{\beta}{|y_l|} \log \pi_\theta(y_l \mid x) - \gamma \right) \right]$$

#### Why $\beta = 2.0$ for the Auditor vs. $\beta = 1.0$ for the Chatbot
The parameter $\beta$ controls the steepness of the sigmoid function, dictating how aggressively the optimization penalizes preference inversions:
$$\nabla_\theta \mathcal{L}_{\text{SimPO}} = -\beta \left( 1 - \sigma(\Delta r - \gamma) \right) \left[ \frac{\nabla_\theta \log \pi_\theta(y_w \mid x)}{|y_w|} - \frac{\nabla_\theta \log \pi_\theta(y_l \mid x)}{|y_l|} \right]$$
- In the **Forensic Auditor**, false positives (over-calling non-violations) and fabricated statutory sections are catastrophic errors. Setting $\beta = 2.0$ steepens the loss gradient, aggressively penalizing non-compliant responses and collapsing the probability of rejected samples to zero.
- In the **Conversational Chatbot**, conversational dialogue requires lexical diversity and syntactic flexibility. Setting $\beta = 1.0$ softens the penalty, preserving natural phrasing while still enforcing factual statutory adherence.

#### The Role of the Target Margin ($\gamma = 0.5$)
Without a margin ($\gamma = 0$), the model achieves zero loss as long as the reward difference $\Delta r > 0$, even if the difference is infinitesimally small ($\epsilon = 0.001$). By enforcing $\gamma = 0.5$, Ssense requires that:
$$\frac{1}{|y_w|} \log \pi_\theta(y_w \mid x) - \frac{1}{|y_l|} \log \pi_\theta(y_l \mid x) \ge \frac{0.5}{\beta}$$
This guarantees a wide, confident decision boundary between compliant legal assessments and hallucinated claims.

---

### 2.3 Length Bias Mitigation via Length Normalization ($\frac{1}{|y|}$)
Standard Direct Preference Optimization (Rafailov et al., NeurIPS 2023) defines the sequence reward as:
$$r_{\text{DPO}}(x, y) = \beta \sum_{t=1}^{|y|} \log \frac{\pi_\theta(y_t \mid x, y_{<t})}{\pi_{\text{ref}}(y_t \mid x, y_{<t})}$$
**Ryan Park et al. (ACL 2024)** proved that because log-probabilities are summed over tokens, DPO suffers from severe **verbosity exploitation**. When a model generates longer sequences, small positive per-token advantages accumulate linearly with sequence length:
$$r(x, y) \approx |y| \cdot \mathbb{E}[\log \pi_\theta - \log \pi_{\text{ref}}]$$
Consequently, DPO-tuned models learn to append disclaimers, repeated legal phrasing, and unnecessary boilerplate purely to increase token count and artificially inflate the reward.

In Ssense, verbose boilerplate degrades browser extension responsiveness and breaks strict JSON parsing. SimPO divides by $|y|$, computing the **exact average token log-likelihood**:
$$r_{\text{SimPO}}(x, y) = \frac{\beta}{|y|} \sum_{t=1}^{|y|} \log \pi_\theta(y_t \mid x, y_{<t})$$
This neutralizes verbosity bias and forces the model to maximize the information density of every generated token.

---

### 2.4 Regularization via NEFTune Embedding Noise ($\alpha_{\text{NEFT}} = 5.0$)
In [`train_audit.py`](file:///d:/Ssense/ml/slm-training/train_audit.py#L656) and [`train_chatbot.py`](file:///d:/Ssense/ml/slm-training/train_chatbot.py#L87), Ssense enables NEFTune noise injection.

**Neel Jain et al. (ICLR 2024)** discovered that Large Language Models trained on instruction datasets rapidly over-fit to specific token combinations in the prompt formatting. During forward passes, NEFTune adds bounded uniform noise to the token embeddings:
$$\mathbf{e}' = \mathbf{e} + \boldsymbol{\epsilon}, \quad \boldsymbol{\epsilon}_{i} \sim \text{Uniform}\left(-\frac{\alpha}{\sqrt{d \cdot L}}, \frac{\alpha}{\sqrt{d \cdot L}}\right)$$
where $d$ is the hidden embedding dimension (3,584 for Qwen2.5-7B) and $L$ is sequence length.
- At $\alpha = 5.0$, the magnitude of the noise vector is scaled appropriately to perturb surface token features without distorting semantic meaning.
- This prevents the model from memorizing exact syntactic phrases from the synthetic training corpus and forces the attention heads to attend to the underlying legal concepts.

---

### 2.5 Retrieval-Augmented Fine-Tuning (RAFT) for the Chatbot
The conversational co-pilot is trained following the **RAFT** paradigm (**Tianjun Zhang et al., TMLR 2024**).

In standard fine-tuning, models memorize facts directly into parametric weights, leading to hallucinations when statutes are amended. In RAFT:
1. **Oracle Context**: The prompt includes the exact retrieved statutory subsection (e.g., Section 6(1) on notice requirements).
2. **Distractor Context**: The prompt is deliberately injected with irrelevant sections (e.g., Section 28 on the Board's penalties).
3. **Chain-of-Thought Citations**: The model is fine-tuned to extract direct quotes from the oracle text while ignoring distractors, and to refuse out-of-scope inquiries using standardized refusal phrases (`REFUSAL_PHRASES`).

This training formulation ensures that the Chatbot relies strictly on runtime RAG retrieval ([`rag_engine.py`](file:///d:/Ssense/apps/slm-server/rag_engine.py)) rather than hallucinating outdated legal provisions.

---

## 3. Structural Safeguards in the Training Loop

### 3.1 The Token Length Firewall
In TRL's `SFTTrainer` and `CPOTrainer`, setting `truncation_mode="keep_start"` causes the tokenizer to truncate tokens exceeding `MAX_SEQ_LENGTH` from the **right-hand side** of the sequence. In legal audit generation, the prompt appears first (system prompt + policy text), while the assistant's JSON response appears at the very end.

If an input sequence reaches 8,250 tokens, standard truncation silently drops the final 58 tokens — amputating the closing brackets (`]}`) of the JSON payload. Training on truncated JSON teaches the model invalid syntax. Ssense eliminates this vulnerability by implementing an explicit pre-training filter:
```python
dataset = dataset.filter(
    lambda x: token_len(tokenizer, x["text"]) <= MAX_SEQ_LENGTH,
    num_proc=8,
)
```
Overlong samples are dropped before batch construction, guaranteeing that 100% of training completions are structurally intact.

### 3.2 Pre-Flight Grounding Trip-Wire
To prevent training on synthetic hallucinations generated by the teacher model, [`preflight_citation_check()`](file:///d:/Ssense/ml/slm-training/train_audit.py#L352-L380) scans every completion for statutory references:
```python
cited = extract_citations(completion)
bad = [c for c in cited if c.lower() not in (context or "").lower()]
```
If more than 5% of citations in the training labels reference sections absent from the prompt context, the pipeline halts immediately.

### 3.3 Subprocess Isolation & CUDA Memory Airlock
PyTorch's caching allocator retains allocated CUDA memory pools even after `del model` and `torch.cuda.empty_cache()` are invoked. When transitioning from Phase 1 (SFT) to Phase 2 (SimPO), residual memory fragmentation frequently triggers Out-Of-Memory (OOM) faults.

Ssense wraps each training phase in an isolated OS process:
```python
multiprocessing.set_start_method("spawn")
p_sft = multiprocessing.Process(target=run_sft)
p_sft.start()
p_sft.join()
```
When Phase 1 finishes, the OS process exits, destroying the CUDA context and releasing 100% of physical GPU VRAM before Phase 2 initializes.

---

## 4. Summary: Why These Parameters Guarantee Production Viability

1. **Memory Feasibility**: SimPO eliminates the reference model $\pi_{\text{ref}}$, halving VRAM requirements and allowing full $r=128$ adaptation at 8,192 token context on a single accelerator.
2. **Deterministic Output**: Response-only loss masking and length normalization prevent length exploitation, producing crisp, schema-compliant JSON reports.
3. **Gradient Stability**: rsLoRA eliminates the rank-collapse problem of standard LoRA, delivering $11.31\times$ stronger gradient updates to specialized legal projections.
4. **Generalization**: NEFTune embedding noise and RAFT distractor training prevent over-fitting, enabling the model to generalize across diverse real-world corporate policies.
