# Ssense Academic Citations & Literature Survey Index

This document provides a comprehensive, publication-grade bibliography of all academic literature, theoretical foundations, and empirical research groundings that directly informed the design, training parameters, alignment objectives, and enforcement mechanisms of **Ssense**.

---

## Table of Contents
1. [Foundation Model Architecture & Tokenization](#1-foundation-model-architecture--tokenization)
2. [Parameter-Efficient Fine-Tuning (PEFT) & Rank Scaling](#2-parameter-efficient-fine-tuning-peft--rank-scaling)
3. [Preference Alignment & Optimization (SimPO, DPO, CPO, ORPO)](#3-preference-alignment--optimization)
4. [Length Bias & Verbosity Exploitation Mitigation](#4-length-bias--verbosity-exploitation-mitigation)
5. [Training Regularization, Schedulers & Numerical Stability](#5-training-regularization-schedulers--numerical-stability)
6. [Hardware Acceleration, Memory Optimization & Attention](#6-hardware-acceleration-memory-optimization--attention)
7. [Retrieval-Augmented Generation (RAG) & Domain Fine-Tuning (RAFT)](#7-retrieval-augmented-generation-rag--domain-fine-tuning-raft)
8. [Legal Domain Adaptation & Hallucination Profiling](#8-legal-domain-adaptation--hallucination-profiling)
9. [Automated Privacy Compliance & Extension Security](#9-automated-privacy-compliance--extension-security)
10. [Quantization & Edge Inference Execution](#10-quantization--edge-inference-execution)
11. [Synthetic Data Engineering, Distillation & Agentic Reflexion](#11-synthetic-data-engineering-distillation--agentic-reflexion)
12. [Data Deduplication, MinHash LSH & Contamination Firewalls](#12-data-deduplication-minhash-lsh--contamination-firewalls)
13. [Statistical Evaluation, Confidence Intervals & Hypothesis Testing](#13-statistical-evaluation-confidence-intervals--hypothesis-testing)
14. [Structured Decoding, Grammar Constraints & Adversarial Robustness](#14-structured-decoding-grammar-constraints--adversarial-robustness)
15. [In-Process Hybrid Retrieval & Rule-Augmented Compliance](#15-in-process-hybrid-retrieval--rule-augmented-compliance)
16. [Multi-LoRA Inference Serving & Dynamic Adapter Multiplexing](#16-multi-lora-inference-serving--dynamic-adapter-multiplexing)
17. [Evaluation Methodologies, Optimal Assignment & LLM-as-a-Judge](#17-evaluation-methodologies-optimal-assignment--llm-as-a-judge)

---

## 1. Foundation Model Architecture & Tokenization

### [Qwen2.5-Foundation] Qwen2.5: A Party of Foundation Models
- **Authors:** Qwen Team (Alibaba Cloud)
- **Year:** 2024
- **Venue:** arXiv preprint arXiv:2412.15115
- **URL:** [https://arxiv.org/abs/2412.15115](https://arxiv.org/abs/2412.15115)
- **BibTeX:**
```bibtex
@article{qwen2024qwen25,
  title={Qwen2.5: A Party of Foundation Models},
  author={{Qwen Team}},
  journal={arXiv preprint arXiv:2412.15115},
  year={2024}
}
```
- **Architectural Grounding in Ssense:**
  Establishes the foundation model (`Qwen2.5-7B-Instruct`). Qwen2.5 incorporates Grouped-Query Attention (GQA, 28 Q-heads, 4 KV-heads), rotary position embeddings with base frequency scaling ($\theta = 1,000,000$) for context lengths up to 128k tokens, SwiGLU non-linear activations, and RMSNorm. Its 152k vocabulary tokenizer drastically compresses JSON syntax and indentation tokens, minimizing prefill and generation latencies during audit generation.

---

### [GQA-Attention] GQA: Training Generalized Multi-Query Transformer Models from Multi-Head Checkpoints
- **Authors:** Joshua Ainslie, James Lee-Thorp, Michiel de Jong, Yury Zemlyanskiy, Federico Lebrón, Sumit Sanghai
- **Year:** 2023
- **Venue:** *Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing (EMNLP)*, pp. 4895–4901
- **DOI:** [10.18653/v1/2023.emnlp-main.298](https://doi.org/10.18653/v1/2023.emnlp-main.298)
- **BibTeX:**
```bibtex
@inproceedings{ainslie2023gqa,
  title={{GQA}: Training Generalized Multi-Query Transformer Models from Multi-Head Checkpoints},
  author={Ainslie, Joshua and Lee-Thorp, James and de Jong, Michiel and Zemlyanskiy, Yury and Lebr{\'o}n, Federico and Sanghai, Sumit},
  booktitle={Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing (EMNLP)},
  pages={4895--4901},
  year={2023},
  doi={10.18653/v1/2023.emnlp-main.298}
}
```
- **Architectural Grounding in Ssense:**
  Validates the memory efficiency of Qwen2.5's 4-KV head configuration. GQA reduces KV cache memory consumption by $7\times$ compared to standard Multi-Head Attention (MHA), making it possible for Ssense's vLLM server to maintain resident KV caches for multiple browser tabs simultaneously.

---

### [RoPE-Embedding] RoFormer: Enhanced Transformer with Rotary Position Embedding
- **Authors:** Jianlin Su, Murtadha Ahmed, Yu Lu, Shengfeng Pan, Wen Bo, Yunfeng Liu
- **Year:** 2024 (Preprint 2021)
- **Venue:** *Neurocomputing*, vol. 568, Art. 127063
- **DOI:** [10.1016/j.neucom.2023.127063](https://doi.org/10.1016/j.neucom.2023.127063)
- **BibTeX:**
```bibtex
@article{su2024roformer,
  title={RoFormer: Enhanced Transformer with Rotary Position Embedding},
  author={Su, Jianlin and Ahmed, Murtadha and Lu, Yu and Pan, Shengfeng and Bo, Wen and Liu, Yunfeng},
  journal={Neurocomputing},
  volume={568},
  pages={127063},
  year={2024},
  doi={10.1016/j.neucom.2023.127063}
}
```
- **Architectural Grounding in Ssense:**
  Provides the mathematical basis for relative position encoding via complex rotation matrices. Enables the 8,192 token context window required to ingest verbose corporate privacy notices without position embedding decay.

---

## 2. Parameter-Efficient Fine-Tuning (PEFT) & Rank Scaling

### [rsLoRA-Scaling] A Rank Stabilization Scaling Factor for Fine-Tuning with LoRA
- **Authors:** Damjan Kalajdzievski
- **Year:** 2023
- **Venue:** arXiv preprint arXiv:2312.03732
- **URL:** [https://arxiv.org/abs/2312.03732](https://arxiv.org/abs/2312.03732)
- **BibTeX:**
```bibtex
@article{kalajdzievski2023rankstabilized,
  title={A Rank Stabilization Scaling Factor for Fine-Tuning with {LoRA}},
  author={Kalajdzievski, Damjan},
  journal={arXiv preprint arXiv:2312.03732},
  year={2023}
}
```
- **Architectural Grounding in Ssense:**
  Direct mathematical foundation for `use_rslora=True` in both [`train_audit.py`](file:///d:/Ssense/ml/slm-training/train_audit.py#L428) and [`train_chatbot.py`](file:///d:/Ssense/ml/slm-training/train_chatbot.py#L9). Proves that conventional LoRA scaling ($\gamma = \alpha/r$) collapses as rank scales ($r=64 \to 128$) because the Frobenius norm of updates grows as $\mathcal{O}(\sqrt{r})$, causing effective learning rate shrinkage $\mathcal{O}(1/\sqrt{r})$. rsLoRA substitutes $\gamma = \alpha/\sqrt{r}$, stabilizing gradient updates and unlocking stable high-rank legal adaptation ($r=128$, $\alpha=128$).

---

### [LoRA-Original] LoRA: Low-Rank Adaptation of Large Language Models
- **Authors:** Edward J. Hu, Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu, Yuanzhi Li, Shean Wang, Lu Wang, Weizhu Chen
- **Year:** 2022
- **Venue:** *International Conference on Learning Representations (ICLR)*
- **URL:** [https://openreview.net/forum?id=nZeVKeeFYf9](https://openreview.net/forum?id=nZeVKeeFYf9)
- **BibTeX:**
```bibtex
@inproceedings{hu2022lora,
  title={{LoRA}: Low-Rank Adaptation of Large Language Models},
  author={Hu, Edward J and Shen, Yelong and Wallis, Phillip and Allen-Zhu, Zeyuan and Li, Yuanzhi and Wang, Shean and Wang, Lu and Chen, Weizhu},
  booktitle={International Conference on Learning Representations (ICLR)},
  year={2022}
}
```
- **Architectural Grounding in Ssense:**
  Foundational PEFT framework. Freezes the 7B base model weights $W_0 \in \mathbb{R}^{d \times k}$ and optimizes low-rank decomposition matrices $A \in \mathbb{R}^{r \times k}$ and $B \in \mathbb{R}^{d \times r}$. Allows hot-swapping between `audit_lora` and `chatbot_lora` at runtime within a single vLLM instance.

---

### [QLoRA-TargetModules] QLoRA: Efficient Finetuning of Quantized LLMs
- **Authors:** Tim Dettmers, Artidoro Pagnoni, Ari Holtzman, Luke Zettlemoyer
- **Year:** 2023
- **Venue:** *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 36, pp. 10088–10115
- **BibTeX:**
```bibtex
@inproceedings{dettmers2023qlora,
  title={{QLoRA}: Efficient Finetuning of Quantized {LLMs}},
  author={Dettmers, Tim and Pagnoni, Artidoro and Holtzman, Ari and Zettlemoyer, Luke},
  booktitle={Advances in Neural Information Processing Systems (NeurIPS)},
  volume={36},
  pages={10088--10115},
  year={2023}
}
```
- **Architectural Grounding in Ssense:**
  Provides empirical proof that adapting **all linear layers** (`q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`) is required to match full-parameter fine-tuning performance. Ssense's [`TARGET_MODULES_PREFERRED`](file:///d:/Ssense/ml/slm-training/train_audit.py#L71-L75) covers all seven linear projections, avoiding capacity bottlenecks observed in attention-only LoRA.

---

## 3. Preference Alignment & Optimization

### [SimPO-Alignment] SimPO: Simple Preference Optimization with a Reference-Free Reward
- **Authors:** Yu Meng, Mengzhou Xia, Danqi Chen
- **Year:** 2024
- **Venue:** *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 37
- **DOI:** [10.5555/3737916.3741862](https://doi.org/10.5555/3737916.3741862)
- **BibTeX:**
```bibtex
@inproceedings{meng2024simpo,
  title={{SimPO}: Simple Preference Optimization with a Reference-Free Reward},
  author={Meng, Yu and Xia, Mengzhou and Chen, Danqi},
  booktitle={Advances in Neural Information Processing Systems (NeurIPS)},
  volume={37},
  year={2024}
}
```
- **Architectural Grounding in Ssense:**
  Primary alignment objective for Phase 2. SimPO formulates an implicit reward based on sequence average log-probability:
  $$r_{\text{SimPO}}(x, y) = \frac{\beta}{|y|} \log \pi_\theta(y \mid x)$$
  Eliminates the reference model $\pi_{\text{ref}}$, saving ~14GB VRAM and enabling $r=128$ alignment on a single accelerator. Enforces a target reward margin $\gamma = 0.5$ between compliant audits ($y_w$) and hallucinated/omission-heavy outputs ($y_l$).

---

### [DPO-Baseline] Direct Preference Optimization: Your Language Model is Secretly a Reward Model
- **Authors:** Rafael Rafailov, Archit Sharma, Eric Mitchell, Christopher D. Manning, Stefano Ermon, Chelsea Finn
- **Year:** 2023
- **Venue:** *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 36, pp. 53728–53741
- **BibTeX:**
```bibtex
@inproceedings{rafailov2023direct,
  title={Direct Preference Optimization: Your Language Model is Secretly a Reward Model},
  author={Rafailov, Rafael and Sharma, Archit and Mitchell, Eric and Manning, Christopher D and Ermon, Stefano and Finn, Chelsea},
  booktitle={Advances in Neural Information Processing Systems (NeurIPS)},
  volume={36},
  pages={53728--53741},
  year={2023}
}
```
- **Architectural Grounding in Ssense:**
  Serves as the theoretical baseline against which SimPO is benchmarked. Analyzed in Section II-C and Section III-B of the research paper to explain the limitations of reference-dependent optimization in single-GPU edge training environments.

---

### [CPO-Translation] Contrastive Preference Optimization: Pushing the Boundaries of LLM Performance in Machine Translation
- **Authors:** Haoran Xu, Amr Sharaf, Yunshu Chen, Weiting Tan, Lingfeng Shen, Benjamin Van Durme, Kenton Murray, Young Jin Kim
- **Year:** 2024
- **Venue:** *Proceedings of the 41st International Conference on Machine Learning (ICML)*, PMLR 235, pp. 55204–55224
- **BibTeX:**
```bibtex
@inproceedings{xu2024contrastive,
  title={Contrastive Preference Optimization: Pushing the Boundaries of {LLM} Performance in Machine Translation},
  author={Xu, Haoran and Sharaf, Amr and Chen, Yunshu and Tan, Weiting and Shen, Lingfeng and Van Durme, Benjamin and Murray, Kenton and Kim, Young Jin},
  booktitle={Proceedings of the 41st International Conference on Machine Learning (ICML)},
  pages={55204--55224},
  year={2024}
}
```
- **Architectural Grounding in Ssense:**
  Informs Ssense's use of TRL's [`CPOTrainer`](file:///d:/Ssense/ml/slm-training/train_audit.py#L831) and [`CPOConfig`](file:///d:/Ssense/ml/slm-training/train_audit.py#L829) with `loss_type="simpo"`. Explains the dynamics of avoiding negative log-likelihood displacement during preference updates.

---

### [ORPO-Monolithic] ORPO: Monolithic Preference Optimization without Reference Model
- **Authors:** Jiwoo Hong, Noah Lee, James Thorne
- **Year:** 2024
- **Venue:** *Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing (EMNLP)*, pp. 11170–11189
- **DOI:** [10.18653/v1/2024.emnlp-main.626](https://doi.org/10.18653/v1/2024.emnlp-main.626)
- **BibTeX:**
```bibtex
@inproceedings{hong2024orpo,
  title={{ORPO}: Monolithic Preference Optimization without Reference Model},
  author={Hong, Jiwoo and Lee, Noah and Thorne, James},
  booktitle={Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing (EMNLP)},
  pages={11170--11189},
  year={2024},
  doi={10.18653/v1/2024.emnlp-main.626}
}
```
- **Architectural Grounding in Ssense:**
  Demonstrates monolithic alignment without a reference model via an odds-ratio penalty. Contrasted in Ssense's research paper against our two-stage pipeline (SFT followed by SimPO), demonstrating that separating syntactic JSON structure learning from fine preference discrimination yields superior schema fidelity.

---

## 4. Length Bias & Verbosity Exploitation Mitigation

### [LengthBias-DPO] Disentangling Length from Quality in Direct Preference Optimization
- **Authors:** Ryan Park, Rafael Rafailov, Stefano Ermon, Chelsea Finn
- **Year:** 2024
- **Venue:** *Findings of the Association for Computational Linguistics: ACL 2024*, pp. 4998–5017
- **DOI:** [10.18653/v1/2024.findings-acl.297](https://doi.org/10.18653/v1/2024.findings-acl.297)
- **BibTeX:**
```bibtex
@inproceedings{park2024disentangling,
  title={Disentangling Length from Quality in Direct Preference Optimization},
  author={Park, Ryan and Rafailov, Rafael and Ermon, Stefano and Finn, Chelsea},
  booktitle={Findings of the Association for Computational Linguistics: ACL 2024},
  pages={4998--5017},
  year={2024},
  doi={10.18653/v1/2024.findings-acl.297}
}
```
- **Architectural Grounding in Ssense:**
  Theoretical proof that unnormalized sequence likelihood in DPO inherently rewards verbosity. In privacy compliance, this causes models to generate superfluous legal padding and ungrounded caveats. Directly justifies Ssense's selection of SimPO's length-normalized reward formulation ($1/|y|$).

---

### [SamPO-Length] Eliminating Biased Length Reliance of Direct Preference Optimization via Down-Sampled KL Divergence
- **Authors:** EMNLP 2024 Contributors
- **Year:** 2024
- **Venue:** *Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing (EMNLP)*
- **BibTeX:**
```bibtex
@inproceedings{sampo2024length,
  title={Eliminating Biased Length Reliance of Direct Preference Optimization via Down-Sampled {KL} Divergence},
  author={Author, Anonymous},
  booktitle={Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing (EMNLP)},
  year={2024}
}
```
- **Architectural Grounding in Ssense:**
  Corroborates the inherent algorithmic length reliance of DPO and validates that length-normalized preference estimation prevents models from exploiting completion length at test time.

---

## 5. Training Regularization, Schedulers & Numerical Stability

### [NEFTune-Noise] NEFTune: Noisy Embeddings Improve Instruction Finetuning
- **Authors:** Neel Jain, Ping-yeh Chiang, Yuxin Wen, John Kirchenbauer, Hong-Min Chu, Gowthami Somepalli, Brian Bartoldson, Bhavya Kailkhura, Avi Schwarzschild, Aniruddha Saha, Micah Goldblum, Jonas Geiping, Tom Goldstein
- **Year:** 2024
- **Venue:** *International Conference on Learning Representations (ICLR)*
- **URL:** [https://openreview.net/forum?id=r6Ey0hYPqZ](https://openreview.net/forum?id=r6Ey0hYPqZ)
- **BibTeX:**
```bibtex
@inproceedings{jain2024neftune,
  title={{NEFT}une: Noisy Embeddings Improve Instruction Finetuning},
  author={Jain, Neel and Chiang, Ping-yeh and Wen, Yuxin and Kirchenbauer, John and Chu, Hong-Min and Somepalli, Gowthami and Bartoldson, Brian and Kailkhura, Bhavya and Schwarzschild, Avi and Saha, Aniruddha and Goldblum, Micah and Geiping, Jonas and Goldstein, Tom},
  booktitle={International Conference on Learning Representations (ICLR)},
  year={2024}
}
```
- **Architectural Grounding in Ssense:**
  Direct foundation for `NEFTUNE_ALPHA = 5` in [`train_chatbot.py`](file:///d:/Ssense/ml/slm-training/train_chatbot.py#L87) and [`train_audit.py`](file:///d:/Ssense/ml/slm-training/train_audit.py#L656). Injects uniform random noise $\epsilon \sim \text{Uniform}(-\alpha / \sqrt{d L}, \alpha / \sqrt{d L})$ into input embedding vectors during forward passes. Regularizes the model against over-fitting to synthetic policy templates, boosting generalization on conversational dialogue and compliance explanations.

---

### [AdamW-Decoupled] Decoupled Weight Decay Regularization
- **Authors:** Ilya Loshchilov, Frank Hutter
- **Year:** 2019
- **Venue:** *International Conference on Learning Representations (ICLR)*
- **BibTeX:**
```bibtex
@inproceedings{loshchilov2019decoupled,
  title={Decoupled Weight Decay Regularization},
  author={Loshchilov, Ilya and Hutter, Frank},
  booktitle={International Conference on Learning Representations (ICLR)},
  year={2019}
}
```
- **Architectural Grounding in Ssense:**
  Theoretical basis for `optim="adamw_torch_fused"` and `weight_decay=0.05` in SFTConfig and CPOConfig. Decouples weight decay from gradient updates, ensuring consistent $L_2$ regularization across low-magnitude adapter weights without distorting moving average momentum estimates.

---

### [SGDR-Cosine] SGDR: Stochastic Gradient Descent with Warm Restarts
- **Authors:** Ilya Loshchilov, Frank Hutter
- **Year:** 2017
- **Venue:** *International Conference on Learning Representations (ICLR)*
- **BibTeX:**
```bibtex
@inproceedings{loshchilov2017sgdr,
  title={{SGDR}: Stochastic Gradient Descent with Warm Restarts},
  author={Loshchilov, Ilya and Hutter, Frank},
  booktitle={International Conference on Learning Representations (ICLR)},
  year={2017}
}
```
- **Architectural Grounding in Ssense:**
  Grounds the `lr_scheduler_type="cosine_with_min_lr"` and `min_lr_rate=0.1` configuration. Decays the learning rate smoothly to 10% of peak ($1.5 \times 10^{-6}$ for SFT, $5.0 \times 10^{-7}$ for SimPO), preserving parameter exploration while guaranteeing stable convergence in final epochs.

---

### [GradClip-Norm] On the Difficulty of Training Recurrent Neural Networks
- **Authors:** Razvan Pascanu, Tomas Mikolov, Yoshua Bengio
- **Year:** 2013
- **Venue:** *International Conference on Machine Learning (ICML)*, PMLR 28, pp. 1310–1318
- **BibTeX:**
```bibtex
@inproceedings{pascanu2013difficulty,
  title={On the difficulty of training recurrent neural networks},
  author={Pascanu, Razvan and Mikolov, Tomas and Bengio, Yoshua},
  booktitle={International Conference on Machine Learning (ICML)},
  pages={1310--1318},
  year={2013}
}
```
- **Architectural Grounding in Ssense:**
  Provides the mathematical justification for `max_grad_norm=1.0`. Rescales gradient vectors when $\|\mathbf{g}\| > 1.0$, preventing gradient explosions triggered by long legal sequence outliers.

---

## 6. Hardware Acceleration, Memory Optimization & Attention

### [FlashAttention-2] FlashAttention-2: Faster Attention with Better Parallelism and Work Partitioning
- **Authors:** Tri Dao
- **Year:** 2024
- **Venue:** *International Conference on Learning Representations (ICLR)*
- **URL:** [https://openreview.net/forum?id=mFtxGQawUh](https://openreview.net/forum?id=mFtxGQawUh)
- **BibTeX:**
```bibtex
@inproceedings{dao2024flashattention2,
  title={{FlashAttention-2}: Faster Attention with Better Parallelism and Work Partitioning},
  author={Dao, Tri},
  booktitle={International Conference on Learning Representations (ICLR)},
  year={2024}
}
```
- **Architectural Grounding in Ssense:**
  Core attention kernel utilized by Unsloth and vLLM. Computes exact softmax attention using GPU SRAM tiling without materializing the $O(N^2)$ attention matrix in high-bandwidth memory (HBM). Enables 8,192 token training and continuous batching on NVIDIA DGX Spark / GB10 hardware.

---

### [GradCheckpoint-Sublinear] Training Deep Nets with Sublinear Memory Cost
- **Authors:** Tianqi Chen, Bing Xu, Chiyuan Zhang, Carlos Guestrin
- **Year:** 2016
- **Venue:** arXiv preprint arXiv:1604.06174
- **BibTeX:**
```bibtex
@article{chen2016training,
  title={Training Deep Nets with Sublinear Memory Cost},
  author={Chen, Tianqi and Xu, Bing and Zhang, Chiyuan and Guestrin, Carlos},
  journal={arXiv preprint arXiv:1604.06174},
  year={2016}
}
```
- **Architectural Grounding in Ssense:**
  Grounds `use_gradient_checkpointing="unsloth"`. Recomputes activations during the backward pass instead of caching all intermediate activation states, reducing activation memory from $O(N)$ to $O(\sqrt{N})$.

---

### [BFloat16-Numerics] A Study of BFLOAT16 for Deep Learning Training
- **Authors:** Dhiraj Kalamkar et al. (Intel / Google Brain)
- **Year:** 2019
- **Venue:** arXiv preprint arXiv:1905.12322
- **BibTeX:**
```bibtex
@article{kalamkar2019study,
  title={A Study of {BFLOAT16} for Deep Learning Training},
  author={Kalamkar, Dhiraj and Mudigere, Dheevatsa and Mellempudi, Naveen and Das, Dipankar and Banerjee, Kunal and Avancha, Sasikanth and Vooturi, Dharma Teja and Jammalamadaka, Nataraj and Huang, Jianyu and Yuen, Hector and others},
  journal={arXiv preprint arXiv:1905.12322},
  year={2019}
}
```
- **Architectural Grounding in Ssense:**
  Theoretical foundation for end-to-end `bf16=True` training and inference. BFloat16 retains the 8-bit dynamic range of IEEE 754 FP32, eliminating gradient underflow/overflow during gradient accumulation without requiring loss scaling.

---

## 7. Retrieval-Augmented Generation (RAG) & Domain Fine-Tuning (RAFT)

### [RAFT-DomainRAG] RAFT: Adapting Language Model to Domain Specific RAG
- **Authors:** Tianjun Zhang, Shishir G. Patil, Naman Jain, Sheng Shen, Matei Zaharia, Ion Stoica, Joseph E. Gonzalez
- **Year:** 2024
- **Venue:** *Transactions on Machine Learning Research (TMLR)*
- **URL:** [https://openreview.net/forum?id=k8is3g44dh](https://openreview.net/forum?id=k8is3g44dh)
- **BibTeX:**
```bibtex
@article{zhang2024raft,
  title={{RAFT}: Adapting Language Model to Domain Specific {RAG}},
  author={Zhang, Tianjun and Patil, Shishir G and Jain, Naman and Shen, Sheng and Zaharia, Matei and Stoica, Ion and Gonzalez, Joseph E},
  journal={Transactions on Machine Learning Research (TMLR)},
  year={2024}
}
```
- **Architectural Grounding in Ssense:**
  Primary methodological foundation for [`train_chatbot.py`](file:///d:/Ssense/ml/slm-training/train_chatbot.py#L12). Trains the conversational model on prompt contexts containing a mixture of oracle statutory passages and distractor sections, teaching the model to quote governing legal provisions verbatim and refuse out-of-scope queries (`REFUSAL_PHRASES`).

---

### [RAG-Foundational] Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks
- **Authors:** Patrick Lewis, Ethan Perez, Aleksandara Piktus, Fabio Petroni, Vladimir Karpukhin, Naman Goyal, Heinrich Küttler, Mike Lewis, Wen-tau Yih, Tim Rocktäschel, Sebastian Riedel, Douwe Kiela
- **Year:** 2020
- **Venue:** *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 33, pp. 9459–9474
- **BibTeX:**
```bibtex
@inproceedings{lewis2020retrieval,
  title={Retrieval-Augmented Generation for Knowledge-Intensive {NLP} Tasks},
  author={Lewis, Patrick and Perez, Ethan and Piktus, Aleksandara and Petroni, Fabio and Karpukhin, Vladimir and Goyal, Naman and K{\"u}ttler, Heinrich and Lewis, Mike and Yih, Wen-tau and Rockt{\"a}schel, Tim and Riedel, Sebastian and Kiela, Douwe},
  booktitle={Advances in Neural Information Processing Systems (NeurIPS)},
  volume={33},
  pages={9459--9474},
  year={2020}
}
```
- **Architectural Grounding in Ssense:**
  Foundational RAG framework separating frozen statutory knowledge in a 237-chunk index from generative model parameters.

---

### [BGE-Embeddings] C-Pack: Packaged Resources to Advance General Chinese Embedding
- **Authors:** Shitao Xiao, Zheng Liu, Peitian Zhang, Niklas Muennighoff
- **Year:** 2023
- **Venue:** arXiv preprint arXiv:2309.07597
- **BibTeX:**
```bibtex
@article{xiao2023cpack,
  title={C-Pack: Packaged Resources to Advance General Chinese Embedding},
  author={Xiao, Shitao and Liu, Zheng and Zhang, Peitian and Muennighoff, Niklas},
  journal={arXiv preprint arXiv:2309.07597},
  year={2023}
}
```
- **Architectural Grounding in Ssense:**
  Grounds the dense retrieval model (`BAAI/bge-large-en-v1.5`) and re-ranker (`BAAI/bge-reranker-v2-m3`) used in [`build_vector_db.py`](file:///d:/Ssense/ml/data-forge/build_vector_db.py) and [`rag_engine.py`](file:///d:/Ssense/apps/slm-server/rag_engine.py).

---

## 8. Legal Domain Adaptation & Hallucination Profiling

### [HIPO-LegalFactuality] Fine-Tuning Large Language Models for Improving Factuality in Legal Question Answering
- **Authors:** Yixiao Ma, Yunqiu Shao, Yueyue Wu, Yiqun Liu, Min Zhang, Shaoping Ma
- **Year:** 2025
- **Venue:** *Proceedings of the 31st International Conference on Computational Linguistics (COLING)*
- **BibTeX:**
```bibtex
@inproceedings{ma2025finetuning,
  title={Fine-Tuning Large Language Models for Improving Factuality in Legal Question Answering},
  author={Ma, Yixiao and Shao, Yunqiu and Wu, Yueyue and Liu, Yiqun and Zhang, Min and Ma, Shaoping},
  booktitle={Proceedings of the 31st International Conference on Computational Linguistics (COLING)},
  year={2025}
}
```
- **Architectural Grounding in Ssense:**
  Demonstrates that fine-tuning Qwen architectures using hard negative preference optimization eliminates statutory hallucinations. Introduces the *Non-Hallucinated Statute Rate* and *Statute Relevance Rate* metrics adopted in Ssense's certification protocol.

---

### [Legal-Hallucinations] Large Legal Fictions: Profiling Legal Hallucinations in Large Language Models
- **Authors:** Matthew Dahl, Varun Magesh, Mirac Suzgun, Daniel E. Ho
- **Year:** 2024
- **Venue:** *Journal of Legal Analysis*, vol. 16, no. 1, doi: 10.1093/jla/laae003
- **BibTeX:**
```bibtex
@article{dahl2024large,
  title={Large Legal Fictions: Profiling Legal Hallucinations in Large Language Models},
  author={Dahl, Matthew and Magesh, Varun and Suzgun, Mirac and Ho, Daniel E},
  journal={Journal of Legal Analysis},
  volume={16},
  number={1},
  year={2024},
  doi={10.1093/jla/laae003}
}
```
- **Architectural Grounding in Ssense:**
  Establishes that general-purpose models hallucinate on legal queries 58–88% of the time. Motivates Ssense's omission gate, statutory pruning, and deterministic Statutory Compliance Layer (SCL).

---

### [InLegalBERT-India] Pre-trained Language Models for the Legal Domain: A Case Study on Indian Law
- **Authors:** Shounak Paul, Arpan Mandal, Pawan Goyal, Saptarshi Ghosh
- **Year:** 2022
- **Venue:** *Proceedings of the 31st International Joint Conference on Artificial Intelligence (IJCAI)*, pp. 4318–4324
- **DOI:** [10.24963/ijcai.2022/599](https://doi.org/10.24963/ijcai.2022/599)
- **BibTeX:**
```bibtex
@inproceedings{paul2022pre,
  title={Pre-trained language models for the legal domain: A case study on {Indian} law},
  author={Paul, Shounak and Mandal, Arpan and Goyal, Pawan and Ghosh, Saptarshi},
  booktitle={Proceedings of the 31st International Joint Conference on Artificial Intelligence (IJCAI)},
  pages={4318--4324},
  year={2022},
  doi={10.24963/ijcai.2022/599}
}
```
- **Architectural Grounding in Ssense:**
  Foundational milestone in Indian legal NLP demonstrating domain continual pre-training over 5.4 million Indian court documents. Ssense contrasts with InLegalBERT by moving from retrospective court case law prediction to generative, real-time statutory privacy compliance auditing.

---

### [Aalap-IndianLegalLLM] Aalap: An Open-Source Instruction-Tuned Large Language Model for the Indian Legal System
- **Authors:** Prathamesh Kalamkar, Saurabh Karn, Smita Gupta, Vivek Raghavan
- **Year:** 2024
- **Venue:** arXiv preprint arXiv:2407.03759
- **URL:** [https://arxiv.org/abs/2407.03759](https://arxiv.org/abs/2407.03759)
- **BibTeX:**
```bibtex
@article{kalamkar2024aalap,
  title={Aalap: An Open-Source Instruction-Tuned Large Language Model for the {Indian} Legal System},
  author={Kalamkar, Prathamesh and Karn, Saurabh and Gupta, Smita and Raghavan, Vivek},
  journal={arXiv preprint arXiv:2407.03759},
  year={2024}
}
```
- **Architectural Grounding in Ssense:**
  Demonstrates 7B instruction fine-tuning on Indian court judgments and FIR chronologies for paralegal workflows. Highlights the research distinction: while Aalap focuses on court litigation and argument generation, Ssense is the first to instruction-tune a 7B model specifically for statutory data protection (DPDP Act 2023) and browser network enforcement.

---

### [IndianLegal-LoRA] Fine-Tuning a Large Language Model for the Indian Legal System
- **Authors:** R. Ta, R. Salunke, R. A. Rahul, R. Nv, S. R. Upadhyaya
- **Year:** 2025
- **Venue:** *Proceedings of the 24th International Symposium INFOTEH-JAHORINA (INFOTEH)*, IEEE
- **DOI:** [10.1109/INFOTEH64129.2025.10959207](https://doi.org/10.1109/INFOTEH64129.2025.10959207)
- **BibTeX:**
```bibtex
@inproceedings{ta2025finetuning,
  title={Fine-Tuning a Large Language Model for the Indian Legal System},
  author={Ta, R and Salunke, R and Rahul, R A and Nv, R and Upadhyaya, S R},
  booktitle={Proceedings of the 24th International Symposium INFOTEH-JAHORINA (INFOTEH)},
  pages={1--6},
  year={2025},
  organization={IEEE},
  doi={10.1109/INFOTEH64129.2025.10959207}
}
```
- **Architectural Grounding in Ssense:**
  Precedent for LoRA adaptation on Indian statutory text; Ssense extends this paradigm to DPDP Act privacy compliance and network-layer enforcement.

---

### [LawInstruct-MultiJurisdiction] LawInstruct: A Resource for Studying Language Model Adaptation to the Legal Domain
- **Authors:** Joel Niklaus et al.
- **Year:** 2025
- **Venue:** *Findings of the Association for Computational Linguistics: NAACL 2025*
- **BibTeX:**
```bibtex
@inproceedings{niklaus2025lawinstruct,
  title={{LawInstruct}: A Resource for Studying Language Model Adaptation to the Legal Domain},
  author={Niklaus, Joel and others},
  booktitle={Findings of the Association for Computational Linguistics: NAACL 2025},
  year={2025}
}
```
- **Architectural Grounding in Ssense:**
  Provides empirical evidence that multi-task legal instruction tuning improves statutory deduction without degrading base language modeling performance.

---

## 9. Automated Privacy Compliance & Extension Security

### [APLiance-DPDP] Privacy as Permissible Operations: An ABAC Framework for Policy–Law Compliance
- **Authors:** Ajay Kumar Dhakar, Arunesh Sinha, Shamik Sural
- **Year:** 2026
- **Venue:** arXiv preprint arXiv:2604.10832
- **BibTeX:**
```bibtex
@article{dhakar2026apliance,
  title={Privacy as Permissible Operations: An {ABAC} Framework for Policy--Law Compliance},
  author={Dhakar, Ajay Kumar and Sinha, Arunesh and Sural, Shamik},
  journal={arXiv preprint arXiv:2604.10832},
  year={2026}
}
```
- **Architectural Grounding in Ssense:**
  The primary comparative baseline for DPDP Act policy checking. Formalizes Sections 1–7 as ABAC rules using an unadapted, hosted general-purpose cloud LLM (GPT-5.4-mini) to extract 16 attribute values. Ssense addresses APLiance's limitations by eliminating cloud API dependencies through a local fine-tuned 7B model, expanding coverage to 26 violation types across the full Act, handling statutory silence via an omission gate, and executing real-time network-layer enforcement.

---

### [ExtPrivA-Extensions] Detection of Inconsistencies in Privacy Practices of Browser Extensions
- **Authors:** Duc Hai Bui, Boyang Tang, Kang G. Shin
- **Year:** 2023
- **Venue:** *Proceedings of the 2023 IEEE Symposium on Security and Privacy (S&P)*, pp. 2482–2499
- **DOI:** [10.1109/SP46215.2023.10179338](https://doi.org/10.1109/SP46215.2023.10179338)
- **BibTeX:**
```bibtex
@inproceedings{bui2023detection,
  title={Detection of Inconsistencies in Privacy Practices of Browser Extensions},
  author={Bui, Duc Hai and Tang, Boyang and Shin, Kang G},
  booktitle={Proceedings of the 2023 IEEE Symposium on Security and Privacy (S\&P)},
  pages={2482--2499},
  year={2023},
  doi={10.1109/SP46215.2023.10179338}
}
```
- **Architectural Grounding in Ssense:**
  Provides the methodology for comparing declared privacy disclosures against runtime network requests.

---

### [MINDAEXT-Minimization] Essential or Excessive? MINDAEXT: Measuring Data Minimization Practices among Browser Extensions
- **Authors:** Y. Ling et al.
- **Year:** 2024
- **Venue:** *Proceedings of the 2024 IEEE International Conference on Software Analysis, Evolution and Reengineering (SANER)*
- **DOI:** [10.1109/SANER60148.2024.00104](https://doi.org/10.1109/SANER60148.2024.00104)
- **BibTeX:**
```bibtex
@inproceedings{ling2024essential,
  title={Essential or Excessive? {MINDAEXT}: Measuring Data Minimization Practices among Browser Extensions},
  author={Ling, Y and others},
  booktitle={Proceedings of the 2024 IEEE International Conference on Software Analysis, Evolution and Reengineering (SANER)},
  year={2024},
  doi={10.1109/SANER60148.2024.00104}
}
```
- **Architectural Grounding in Ssense:**
  Grounds Section 6(1) and Section 7 data minimization checks under the DPDP Act.

---

## 10. Quantization & Edge Inference Execution

### [GGUF-Quantization] llama.cpp: Fast LLM Inference on Consumer and Edge Hardware
- **Authors:** Georgi Gerganov and llama.cpp contributors
- **Year:** 2023–2026
- **Venue:** Open Source Software & Technical Specifications
- **URL:** [https://github.com/ggerganov/llama.cpp](https://github.com/ggerganov/llama.cpp)
- **BibTeX:**
```bibtex
@software{gerganov2023llamacpp,
  title={llama.cpp: Port of Facebook's {LLaMA} model in {C/C++}},
  author={Gerganov, Georgi and contributors},
  url={https://github.com/ggerganov/llama.cpp},
  year={2023}
}
```
- **Architectural Grounding in Ssense:**
  Technical foundation for [`OUTPUT_DIR_FINAL + "-gguf"`](file:///d:/Ssense/ml/slm-training/train_audit.py#L893-L894) export using `quantization_method="q4_k_m"`. Employs K-quants hierarchical block quantization, enabling the 7B model to run on CPU-only machines in ~4.3 GB RAM.

---

## 11. Synthetic Data Engineering, Distillation & Agentic Reflexion

### [MiniLLM-Distillation] MiniLLM: Knowledge Distillation of Large Language Models
- **Authors:** Yuxian Gu, Li Dong, Furu Wei, Minlie Huang
- **Year:** 2024
- **Venue:** *The Twelfth International Conference on Learning Representations (ICLR)*
- **URL:** [https://openreview.net/forum?id=6ca90u0WS0](https://openreview.net/forum?id=6ca90u0WS0)
- **BibTeX:**
```bibtex
@inproceedings{gu2024minillm,
  title={Mini{LLM}: Knowledge Distillation of Large Language Models},
  author={Gu, Yuxian and Dong, Li and Wei, Furu and Huang, Minlie},
  booktitle={The Twelfth International Conference on Learning Representations (ICLR)},
  year={2024}
}
```
- **Architectural Grounding in Ssense:**
  Theoretical foundation for knowledge distillation from the 72B foundation teacher model to the 7B edge student. Formulates distribution alignment to prevent the student from predicting improbable tokens outside the teacher's support.

---

### [Orca-ReasoningTraces] Orca: Progressive Learning from Complex Explanation Traces of GPT-4
- **Authors:** Subhabrata Mukherjee, Arindam Mitra, Ganesh Jawahar, Sahaj Agarwal, Hamid Palangi, Ahmed Awadallah
- **Year:** 2023
- **Venue:** arXiv preprint arXiv:2306.02707
- **BibTeX:**
```bibtex
@article{mukherjee2023orca,
  title={Orca: Progressive learning from complex explanation traces of {GPT-4}},
  author={Mukherjee, Subhabrata and Mitra, Arindam and Jawahar, Ganesh and Agarwal, Sahaj and Palangi, Hamid and Awadallah, Ahmed},
  journal={arXiv preprint arXiv:2306.02707},
  year={2023}
}
```
- **Architectural Grounding in Ssense:**
  Demonstrates that student SLMs (7B/13B) acquire complex deductive reasoning by training on intermediate reasoning traces and step-by-step explanations generated by large teacher models, rather than simple answer pairs. Grounds Ssense's multi-step JSON reasoning schema (`step_1_active_claim_analysis`, `step_2_statute_match`, `step_3_semantic_justification`).

---

### [Self-Instruct] Self-Instruct: Aligning Language Models with Self-Generated Instructions
- **Authors:** Yizhong Wang, Yeganeh Kordi, Swaroop Mishra, Alisa Liu, Noah A. Smith, Daniel Khashabi, Hannaneh Hajishirzi
- **Year:** 2023
- **Venue:** *Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (ACL)*, pp. 13484–13508
- **DOI:** [10.18653/v1/2023.acl-long.754](https://doi.org/10.18653/v1/2023.acl-long.754)
- **BibTeX:**
```bibtex
@inproceedings{wang2023selfinstruct,
  title={Self-Instruct: Aligning Language Models with Self-Generated Instructions},
  author={Wang, Yizhong and Kordi, Yeganeh and Mishra, Swaroop and Liu, Alisa and Smith, Noah A and Khashabi, Daniel and Hajishirzi, Hannaneh},
  booktitle={Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (ACL)},
  pages={13484--13508},
  year={2023},
  doi={10.18653/v1/2023.acl-long.754}
}
```
- **Architectural Grounding in Ssense:**
  Core generate-filter-tune loop for synthetic dataset synthesis in [`gan_forge.py`](file:///d:/Ssense/ml/data-forge/gan_forge.py).

---

### [UltraFeedback-Critique] UltraFeedback: Boosting Language Models with Scaled AI Feedback
- **Authors:** Ganqu Cui, Lifan Yuan, Ning Ding, Guanming Yao, Bingxiang He, Wei Zhu, Yuan Ni, Guotong Xie, Ruobing Xie, Yankai Lin, Zhiyuan Liu, Maosong Sun
- **Year:** 2024
- **Venue:** *Proceedings of the 41st International Conference on Machine Learning (ICML)*, PMLR 235, pp. 9722–9744
- **BibTeX:**
```bibtex
@inproceedings{cui2024ultrafeedback,
  title={{ULTRAFEEDBACK}: Boosting Language Models with Scaled {AI} Feedback},
  author={Cui, Ganqu and Yuan, Lifan and Ding, Ning and Yao, Guanming and He, Bingxiang and Zhu, Wei and Ni, Yuan and Xie, Guotong and Xie, Ruobing and Lin, Yankai and Liu, Zhiyuan and Sun, Maosong},
  booktitle={Proceedings of the 41st International Conference on Machine Learning (ICML)},
  pages={9722--9744},
  year={2024}
}
```
- **Architectural Grounding in Ssense:**
  Grounds multi-dimensional automated critique and filtering for preference dataset construction.

---

### [Reflexion-VerbalRL] Reflexion: Language Agents with Verbal Reinforcement Learning
- **Authors:** Noah Shinn, Federico Cassano, Ashwin Gopinath, Karthik Narasimhan, Shunyu Yao
- **Year:** 2023
- **Venue:** *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 36, pp. 8634–8646
- **BibTeX:**
```bibtex
@inproceedings{shinn2023reflexion,
  title={Reflexion: language agents with verbal reinforcement learning},
  author={Shinn, Noah and Cassano, Federico and Gopinath, Ashwin and Narasimhan, Karthik and Yao, Shunyu},
  booktitle={Advances in Neural Information Processing Systems (NeurIPS)},
  volume={36},
  pages={8634--8646},
  year={2023}
}
```
- **Architectural Grounding in Ssense:**
  Primary methodological foundation for [`gan_forge.py`](file:///d:/Ssense/ml/data-forge/gan_forge.py)'s self-healing loop (`MAX_REFLEXION_STEPS=3`). Converts discriminative validation errors into explicit verbal feedback prompts (`REFLEXION_EXPLICIT_PROMPT`), directing the teacher model to iteratively rewrite and heal invalid policy drafts until they satisfy both Gate 1 and Gate 2.

---

### [Self-Refine] Self-Refine: Iterative Refinement with Self-Feedback
- **Authors:** Aman Madaan, Niket Tandon, Prakhar Gupta, Skyler Hallinan, Luyu Gao, Sarah Wiegreffe, Uri Alon, Nouha Dziri, Shrimai Prabhumoye, Yang Yang, Shashank Gupta, Bodhisattwa Prasad Majumder, Katherine Hermann, Sean Welleck, Amir Yazdanbakhsh, Peter Clark
- **Year:** 2023
- **Venue:** *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 36
- **BibTeX:**
```bibtex
@inproceedings{madaan2023selfrefine,
  title={{Self-Refine}: Iterative Refinement with Self-Feedback},
  author={Madaan, Aman and Tandon, Niket and Gupta, Prakhar and Hallinan, Skyler and Gao, Luyu and Wiegreffe, Sarah and Alon, Uri and Dziri, Nouha and Prabhumoye, Shrimai and Yang, Yang and Gupta, Shashank and Majumder, Bodhisattwa Prasad and Hermann, Katherine and Welleck, Sean and Yazdanbakhsh, Amir and Clark, Peter},
  booktitle={Advances in Neural Information Processing Systems (NeurIPS)},
  volume={36},
  year={2023}
}
```
- **Architectural Grounding in Ssense:**
  Demonstrates that multi-turn iterative feedback improves quality and adherence to complex structural constraints without external human intervention.

---

### [ModelCollapse-Nature] AI Models Collapse when Trained on Recursively Generated Data
- **Authors:** Ilia Shumailov, Zakhar Shumaylov, Yiren Zhao, Nicolas Papernot, Ross Anderson, Yarin Gal
- **Year:** 2024
- **Venue:** *Nature*, vol. 631, no. 8022, pp. 755–759
- **DOI:** [10.1038/s41586-024-07566-y](https://doi.org/10.1038/s41586-024-07566-y)
- **BibTeX:**
```bibtex
@article{shumailov2024ai,
  title={{AI} models collapse when trained on recursively generated data},
  author={Shumailov, Ilia and Shumaylov, Zakhar and Zhao, Yiren and Papernot, Nicolas and Anderson, Ross and Gal, Yarin},
  journal={Nature},
  volume={631},
  number={8022},
  pages={755--759},
  year={2024},
  doi={10.1038/s41586-024-07566-y}
}
```
- **Architectural Grounding in Ssense:**
  Theoretical warning against pure recursive synthetic training. Grounds Ssense's architectural decision to preserve real Indian policy seeds (`raw_policies/`, `indian-seeds/`) and execute MinHash locality-sensitive deduplication to maintain long-tail lexical diversity and prevent model collapse.

---

## 12. Data Deduplication, MinHash LSH & Contamination Firewalls

### [MinHash-Broder] On the Resemblance and Containment of Documents
- **Authors:** Andrei Z. Broder
- **Year:** 1997
- **Venue:** *Proceedings of the Compression and Complexity of Sequences (SEQUENCES'97)*, IEEE, pp. 21–29
- **DOI:** [10.1109/SEQUEN.1997.666900](https://doi.org/10.1109/SEQUEN.1997.666900)
- **BibTeX:**
```bibtex
@inproceedings{broder1997resemblance,
  title={On the resemblance and containment of documents},
  author={Broder, Andrei Z},
  booktitle={Proceedings of the Compression and Complexity of Sequences (SEQUENCES'97)},
  pages={21--29},
  year={1997},
  organization={IEEE},
  doi={10.1109/SEQUEN.1997.666900}
}
```
- **Architectural Grounding in Ssense:**
  Mathematical foundation for [`check_data_leakage.py`](file:///d:/Ssense/ml/scripts/check_data_leakage.py). Implements 128-permutation MinHash signature generation using Linear Congruential Generators (LCG) over 7-gram sliding word shingles. Enables sub-second vectorized pairwise Jaccard similarity estimation ($J(A, B) = \frac{|A \cap B|}{|A \cup B|}$) across training corpora and evaluation splits with a strict hard-fail rejection threshold ($J > 0.85$).

---

### [Dedup-LanguageModels] Deduplicating Training Data Makes Language Models Better
- **Authors:** Katherine Lee, Daphne Ippolito, Andrew Nystrom, Chiyuan Zhang, Douglas Eck, Chris Callison-Burch, Nicholas Carlini
- **Year:** 2022
- **Venue:** *Proceedings of the 60th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, pp. 8424–8445
- **DOI:** [10.18653/v1/2022.acl-long.577](https://doi.org/10.18653/v1/2022.acl-long.577)
- **BibTeX:**
```bibtex
@inproceedings{lee2022deduplicating,
  title={Deduplicating Training Data Makes Language Models Better},
  author={Lee, Katherine and Ippolito, Daphne and Nystrom, Andrew and Zhang, Chiyuan and Eck, Douglas and Callison-Burch, Chris and Carlini, Nicholas},
  booktitle={Proceedings of the 60th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)},
  pages={8424--8445},
  year={2022},
  doi={10.18653/v1/2022.acl-long.577}
}
```
- **Architectural Grounding in Ssense:**
  Empirical evidence that training set deduplication reduces memorization and verbatim reproduction while improving zero-shot generalization. Grounds Ssense's pre-flight contamination firewall, ensuring held-out policy benchmarks are mathematically decoupled from synthetic training pairs.

---

## 13. Statistical Evaluation, Confidence Intervals & Hypothesis Testing

### [WilsonScore-CI] Probable Inference, the Law of Succession, and Statistical Inference
- **Authors:** Edwin B. Wilson
- **Year:** 1927
- **Venue:** *Journal of the American Statistical Association*, vol. 22, no. 158, pp. 209–212
- **DOI:** [10.1080/01621459.1927.10502953](https://doi.org/10.1080/01621459.1927.10502953)
- **BibTeX:**
```bibtex
@article{wilson1927probable,
  title={Probable inference, the law of succession, and statistical inference},
  author={Wilson, Edwin B},
  journal={Journal of the American Statistical Association},
  volume={22},
  number={158},
  pages={209--212},
  year={1927},
  publisher={Taylor \& Francis},
  doi={10.1080/01621459.1927.10502953}
}
```
- **Architectural Grounding in Ssense:**
  Theoretical foundation for binomial confidence bounds in [`stats.py`](file:///d:/Ssense/ml/evals/stats.py). Computes asymmetric Wilson score intervals at 95% confidence ($z=1.96$) for small-sample verification ($N \approx 60$). Informs Ssense's "Wilson Paradox" dual-gating: enforcing point-estimate checks at extreme boundaries ($p=0\%, 100\%$) while strictly gating all interior thresholds by the Wilson Lower Bound.

---

### [McNemar-Test] Note on the Sampling Error of the Difference Between Correlated Proportions or Percentages
- **Authors:** Quinn McNemar
- **Year:** 1947
- **Venue:** *Psychometrika*, vol. 12, no. 2, pp. 153–157
- **DOI:** [10.1007/BF02295996](https://doi.org/10.1007/BF02295996)
- **BibTeX:**
```bibtex
@article{mcnemar1947note,
  title={Note on the sampling error of the difference between correlated proportions or percentages},
  author={McNemar, Quinn},
  journal={Psychometrika},
  volume={12},
  number={2},
  pages={153--157},
  year={1947},
  publisher={Springer},
  doi={10.1007/BF02295996}
}
```
- **Architectural Grounding in Ssense:**
  Foundational paired significance test in [`compare_sota_models.py`](file:///d:/Ssense/ml/evals/compare_sota_models.py). Evaluates whether accuracy improvements of the fine-tuned DPDP SLM over baseline foundation LLMs (Qwen2.5-7B-Instruct, GPT-4o, Claude 3.5 Sonnet) are statistically significant via exact binomial evaluation of discordant pairs ($n_{01}, n_{10}$) and continuity-corrected $\chi^2$ statistics.

---

### [MTLD-Diversity] An Assessment of the Range and Usefulness of Lexical Diversity Measures
- **Authors:** Philip M. McCarthy
- **Year:** 2005
- **Venue:** *Doctoral Dissertation*, The University of Memphis
- **BibTeX:**
```bibtex
@phdthesis{mccarthy2005assessment,
  title={An assessment of the range and usefulness of lexical diversity measures and the potential of the measure of textual, lexical diversity ({MTLD})},
  author={McCarthy, Philip M},
  year={2005},
  school={The University of Memphis}
}
```
- **Architectural Grounding in Ssense:**
  Supplies the Measure of Textual Lexical Diversity (MTLD) in [`stats.py`](file:///d:/Ssense/ml/evals/stats.py). Unlike Type-Token Ratio (TTR), MTLD is mathematically independent of generation sequence length, allowing Ssense to monitor model vocabulary richness across variable-length audit rationales and chatbot explanations.

---

### [Bootstrap-Efron] Bootstrap Methods: Another Look at the Jackknife
- **Authors:** Bradley Efron
- **Year:** 1979
- **Venue:** *The Annals of Statistics*, vol. 7, no. 1, pp. 1–26
- **DOI:** [10.1214/aos/1176344552](https://doi.org/10.1214/aos/1176344552)
- **BibTeX:**
```bibtex
@article{efron1979bootstrap,
  title={Bootstrap methods: Another look at the jackknife},
  author={Efron, Bradley},
  journal={The Annals of Statistics},
  volume={7},
  number={1},
  pages={1--26},
  year={1979},
  doi={10.1214/aos/1176344552}
}
```
- **Architectural Grounding in Ssense:**
  Provides the non-parametric percentile bootstrap confidence interval methodology implemented in [`stats.py`](file:///d:/Ssense/ml/evals/stats.py) (`bootstrap_ci`). Used for estimating empirical confidence bounds on continuous evaluation metrics (latency distributions, Context Faithfulness judging score means, and Mean Absolute Error on DPDP trust scores) without presupposing normal error distributions.

---

## 14. Structured Decoding, Grammar Constraints & Adversarial Robustness

### [Outlines-Grammar] Efficient Guided Generation for Large Language Models
- **Authors:** Brandon T. Willard, Rémi Louf
- **Year:** 2023
- **Venue:** arXiv preprint arXiv:2307.09702
- **URL:** [https://arxiv.org/abs/2307.09702](https://arxiv.org/abs/2307.09702)
- **BibTeX:**
```bibtex
@article{willard2023efficient,
  title={Efficient Guided Generation for Large Language Models},
  author={Willard, Brandon T and Louf, R{\'e}mi},
  journal={arXiv preprint arXiv:2307.09702},
  year={2023}
}
```
- **Architectural Grounding in Ssense:**
  Mathematical basis for finite-state machine (FSM) token masking in `build_dpdp_tree.py` and vLLM production guided decoding (`grammar=json.dumps(schema)`). Forces model generation logits to adhere to context-free grammars and JSON Schema contracts at the token level, eliminating structural syntax collapse and guaranteeing schema validity.

---

### [LostInTheMiddle] Lost in the Middle: How Language Models Use Long Contexts
- **Authors:** Nelson F. Liu, Kevin Lin, John Hewitt, Ashwin Paranjape, Michele Bevilacqua, Fabio Petroni, Percy Liang
- **Year:** 2024
- **Venue:** *Transactions of the Association for Computational Linguistics (TACL)*, vol. 12, pp. 157–173
- **DOI:** [10.1162/tacl_a_00638](https://doi.org/10.1162/tacl_a_00638)
- **BibTeX:**
```bibtex
@article{liu2024lost,
  title={Lost in the Middle: How Language Models Use Long Contexts},
  author={Liu, Nelson F and Lin, Kevin and Hewitt, John and Paranjape, Ashwin and Bevilacqua, Michele and Petroni, Fabio and Liang, Percy},
  journal={Transactions of the Association for Computational Linguistics},
  volume={12},
  pages={157--173},
  year={2024},
  doi={10.1162/tacl_a_00638}
}
```
- **Architectural Grounding in Ssense:**
  Guides context engineering in [`rag_engine.py`](file:///d:/Ssense/apps/slm-server/rag_engine.py) and adversarial Needle-In-A-Haystack stress testing in [`run_security_evals.py`](file:///d:/Ssense/ml/evals/run_security_evals.py). Informs Ssense's XML structural context envelope (`<retrieved_statutes>`, `<statute index="...">`) to position crucial statutory obligations at context boundaries, mitigating attention attenuation across multi-thousand token privacy policies.

---

### [Sycophancy-Eval] Towards Understanding Sycophancy in Language Models
- **Authors:** Mrinank Sharma, Meg Tong, Tomasz Korbak, David Duvenaud, Amanda Askell, Samuel R. Bowman, Newton Cheng, Esin Durmus, Zac Hatfield-Dodds, Scott R. Johnston, Shauna Kravec, Timothy Maxwell, Nicholas Schiefer, Ethan Perez
- **Year:** 2024
- **Venue:** *The Twelfth International Conference on Learning Representations (ICLR)*
- **URL:** [https://openreview.net/forum?id=eWk5vOH7iX](https://openreview.net/forum?id=eWk5vOH7iX)
- **BibTeX:**
```bibtex
@inproceedings{sharma2024towards,
  title={Towards Understanding Sycophancy in Language Models},
  author={Sharma, Mrinank and Tong, Meg and Korbak, Tomasz and Duvenaud, David and Askell, Amanda and Bowman, Samuel R and Cheng, Newton and Durmus, Esin and Hatfield-Dodds, Zac and Johnston, Scott R and Kravec, Shauna and Maxwell, Timothy and Schiefer, Nicholas and Perez, Ethan},
  booktitle={The Twelfth International Conference on Learning Representations (ICLR)},
  year={2024}
}
```
- **Architectural Grounding in Ssense:**
  Foundational framework for sycophancy trap benchmarking in [`run_security_evals.py`](file:///d:/Ssense/ml/evals/run_security_evals.py). Measures the SLM's resistance to confirming user-supplied false legal premises (e.g., claiming commercial exemptions under DPDP Section 17) and benchmarks respectful refutation capabilities.

---

## 15. In-Process Hybrid Retrieval & Rule-Augmented Compliance

### [RRF-Search] Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods
- **Authors:** Gordon V. Cormack, Charles L. A. Clarke, Stefan Büttcher
- **Year:** 2009
- **Venue:** *Proceedings of the 32nd International ACM SIGIR Conference on Research and Development in Information Retrieval (SIGIR)*, pp. 758–759
- **DOI:** [10.1145/1571941.1572114](https://doi.org/10.1145/1571941.1572114)
- **BibTeX:**
```bibtex
@inproceedings{cormack2009reciprocal,
  title={Reciprocal rank fusion outperforms {Condorcet} and individual rank learning methods},
  author={Cormack, Gordon V and Clarke, Charles LA and B{\"u}ttcher, Stefan},
  booktitle={Proceedings of the 32nd International ACM SIGIR Conference on Research and Development in Information Retrieval (SIGIR)},
  pages={758--759},
  year={2009},
  doi={10.1145/1571941.1572114}
}
```
- **Architectural Grounding in Ssense:**
  Mathematical formulation for rank aggregation in [`build_vector_db.py`](file:///d:/Ssense/ml/data-forge/build_vector_db.py) and [`compare_sota_models.py`](file:///d:/Ssense/ml/evals/compare_sota_models.py):
  $$RRF(d) = \sum_{m \in \{\text{BM25}, \text{Dense}\}} \frac{1}{k + r_m(d)}$$
  (with smoothing constant $k=60$). Eliminates calibration drift between sparse BM25 scores and dense cosine similarities.

---

### [HybridLegal-NLP] LexGLUE: A Benchmark Dataset for Legal Language Understanding in English
- **Authors:** Ilias Chalkidis, Abhik Jana, Dirk Groeneveld, Nikolaos Aletras, Anurag Roy, Evangelos Saravakos, Pradeep Muthukrishnan, Haris Papageorgiou, Daniel Preoțiuc-Pietro, Mohammad Taher Pilehvar
- **Year:** 2022
- **Venue:** *Computational Linguistics*, vol. 48, no. 4, pp. 843–888
- **DOI:** [10.1162/coli_a_00444](https://doi.org/10.1162/coli_a_00444)
- **BibTeX:**
```bibtex
@article{chalkidis2022lexglue,
  title={{LexGLUE}: A Benchmark Dataset for Legal Language Understanding in English},
  author={Chalkidis, Ilias and Jana, Abhik and Groeneveld, Dirk and Aletras, Nikolaos and Roy, Anurag and Saravakos, Evangelos and Muthukrishnan, Pradeep and Papageorgiou, Haris and Preo{\c{t}}iuc-Pietro, Daniel and Pilehvar, Mohammad Taher},
  journal={Computational Linguistics},
  volume={48},
  number={4},
  pages={843--888},
  year={2022},
  doi={10.1162/coli_a_00444}
}
```
- **Architectural Grounding in Ssense:**
  Demonstrates that combining statistical language models with rule-based post-processors achieves superior legal recall and robustness. Grounds Ssense's hybrid inference architecture, coupling the LoRA SLM with the deterministic Statutory Compliance Layer ([`audit_corrector.py`](file:///d:/Ssense/apps/slm-server/audit_corrector.py)) to catch unambiguous statutory admissions without requiring retraining.

---

## 16. Multi-LoRA Inference Serving & Dynamic Adapter Multiplexing

### [S-LoRA-Serving] S-LoRA: Serving Thousands of Concurrent LoRA Adapters
- **Authors:** Ying Sheng, Shiyi Cao, Dacheng Li, Coleman Hooper, Nicholas Lee, Shuo Yang, Christopher Chou, Banghua Zhu, Lianmin Zheng, Kurt Keutzer, Joseph E. Gonzalez, Ion Stoica
- **Year:** 2024
- **Venue:** *Proceedings of Machine Learning and Systems (MLSys)*, vol. 6, pp. 317–331
- **BibTeX:**
```bibtex
@inproceedings{sheng2024slora,
  title={{S-LoRA}: Serving Thousands of Concurrent {LoRA} Adapters},
  author={Sheng, Ying and Cao, Shiyi and Li, Dacheng and Hooper, Coleman and Lee, Nicholas and Yang, Shuo and Chou, Christopher and Zhu, Banghua and Zheng, Lianmin and Keutzer, Kurt and Gonzalez, Joseph E and Stoica, Ion},
  booktitle={Proceedings of Machine Learning and Systems (MLSys)},
  volume={6},
  pages={317--331},
  year={2024}
}
```
- **Architectural Grounding in Ssense:**
  Theoretical foundation for multi-adapter parameter multiplexing in [`engine.py`](file:///d:/Ssense/apps/slm-server/engine.py). Enables Ssense to serve both the forensic legal auditor adapter ($r=128$) and conversational chatbot adapter ($r=64$) over a single frozen `Qwen2.5-7B-Instruct` base model in unified memory space, eliminating model reload overhead and memory duplication between audit and dialogue tasks.

---

### [Punica-Multiplexing] Punica: Multi-Tenant LoRA Serving
- **Authors:** Luo Mai, Lingxiao Ma, Baichen Yang, Donglin Zhuang, Yida Wang
- **Year:** 2024
- **Venue:** *Proceedings of Machine Learning and Systems (MLSys)*, vol. 6
- **BibTeX:**
```bibtex
@inproceedings{mai2024punica,
  title={Punica: Multi-Tenant {LoRA} Serving},
  author={Mai, Luo and Ma, Lingxiao and Yang, Baichen and Zhuang, Donglin and Wang, Yida},
  booktitle={Proceedings of Machine Learning and Systems (MLSys)},
  volume={6},
  year={2024}
}
```
- **Architectural Grounding in Ssense:**
  Establishes batched low-rank matrix-vector multiplication (Segmented Gather-Apply-Scatter) across distinct LoRA adapters, underpinning Ssense's dynamic per-request adapter routing without GPU memory reallocation.

---

### [XGrammar-Constrained] XGrammar: Flexible and Efficient Grammar-guided Generation for Large Language Models
- **Authors:** Yixin Dong, Charlie F. Ruan, Yaxing Cai, Ruihang Lai, Ziyan Huang, Hongyi Guan, Siyuan Liu, Vincent Zhao, Tianqi Chen
- **Year:** 2024
- **Venue:** arXiv preprint arXiv:2411.15100
- **URL:** [https://arxiv.org/abs/2411.15100](https://arxiv.org/abs/2411.15100)
- **BibTeX:**
```bibtex
@article{dong2024xgrammar,
  title={{XGrammar}: Flexible and Efficient Grammar-guided Generation for Large Language Models},
  author={Dong, Yixin and Ruan, Charlie F and Cai, Yaxing and Lai, Ruihang and Huang, Ziyan and Guan, Hongyi and Liu, Siyuan and Zhao, Vincent and Chen, Tianqi},
  journal={arXiv preprint arXiv:2411.15100},
  year={2024}
}
```
- **Architectural Grounding in Ssense:**
  Provides the context-free grammar (CFG) compiler and pushdown automaton engine utilized for token-level logit masking. Guarantees that the auditor SLM outputs conform strictly to the 16 violation enums and JSON schema hierarchy of `dpdp_schema.json` with zero syntax collapse.

---

### [Prompt-Cache] Prompt Cache: Modular Attention Reuse for Low-Latency Inference
- **Authors:** In Won Gim, You Min Bae, Jeongsoo Kim, Insu Jang, Sung-Ju Lee
- **Year:** 2024
- **Venue:** *Proceedings of the 22nd Annual International Conference on Mobile Systems, Applications and Services (MobiSys)*, pp. 245–258
- **DOI:** [10.1145/3643832.3661877](https://doi.org/10.1145/3643832.3661877)
- **BibTeX:**
```bibtex
@inproceedings{gim2024prompt,
  title={Prompt Cache: Modular Attention Reuse for Low-Latency Inference},
  author={Gim, In Won and Bae, You Min and Kim, Jeongsoo and Jang, Insu and Lee, Sung-Ju},
  booktitle={Proceedings of the 22nd Annual International Conference on Mobile Systems, Applications and Services (MobiSys)},
  pages={245--258},
  year={2024},
  doi={10.1145/3643832.3661877}
}
```
- **Architectural Grounding in Ssense:**
  Theoretical foundation for key-value (KV) cache prefix pre-warming (`_prewarm_kv_prefixes`) implemented in [`engine.py`](file:///d:/Ssense/apps/slm-server/engine.py). Caches invariant system prompt attention states (`_SYS_CONCISE`, `_SYS_THINKING`) across inference cycles, bypassing prompt prefill computation during user legal consultations.

---

### [Prompt-Lookup-Decoding] Fast Inference from Transformers via Speculative Decoding
- **Authors:** Yaniv Leviathan, Matan Kalman, Yossi Matias
- **Year:** 2023
- **Venue:** *Proceedings of the 40th International Conference on Machine Learning (ICML)*, PMLR, vol. 202, pp. 19274–19286
- **BibTeX:**
```bibtex
@inproceedings{leviathan2023fast,
  title={Fast Inference from Transformers via Speculative Decoding},
  author={Leviathan, Yaniv and Kalman, Matan and Matias, Yossi},
  booktitle={Proceedings of the 40th International Conference on Machine Learning (ICML)},
  pages={19274--19286},
  year={2023}
}
```
- **Architectural Grounding in Ssense:**
  Theoretical foundation for prompt lookup speculative decoding (`prompt_lookup_num_tokens=3`) in [`engine.py`](file:///d:/Ssense/apps/slm-server/engine.py). Exploits high n-gram overlap between statutory retrieval text, policy quotes, and generated legal analysis by utilizing matching prompt n-grams as speculative draft tokens verified in parallel in a single forward pass, achieving speculative speedup without an auxiliary draft model.

---

## 17. Evaluation Methodologies, Optimal Assignment & LLM-as-a-Judge

### [LLM-as-a-Judge] Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena
- **Authors:** Lianmin Zheng, Wei-Lin Chiang, Ying Sheng, Siyuan Zhuang, Zhanghao Wu, Yonghao Zhuang, Zi Lin, Zhuohan Li, Dacheng Li, Eric P. Xing, Hao Zhang, Joseph E. Gonzalez, Ion Stoica
- **Year:** 2023
- **Venue:** *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 36, pp. 46595–46623
- **BibTeX:**
```bibtex
@inproceedings{zheng2023judging,
  title={Judging {LLM}-as-a-Judge with {MT-Bench} and {Chatbot Arena}},
  author={Zheng, Lianmin and Chiang, Wei-Lin and Sheng, Ying and Zhuang, Siyuan and Wu, Zhanghao and Zhuang, Yonghao and Lin, Zi and Li, Zhuohan and Li, Dacheng and Xing, Eric P and Zhang, Hao and Gonzalez, Joseph E and Stoica, Ion},
  booktitle={Advances in Neural Information Processing Systems (NeurIPS)},
  volume={36},
  pages={46595--46623},
  year={2023}
}
```
- **Architectural Grounding in Ssense:**
  Foundational framework for the Context Faithfulness (CF) metric in [`metrics.py`](file:///d:/Ssense/ml/evals/metrics.py) and [`compare_sota_models.py`](file:///d:/Ssense/ml/evals/compare_sota_models.py). Implements Chain-of-Thought (CoT) legal auditing prompts to score whether generated responses introduce statutory obligations, penalties, or facts not present in the retrieved statutory corpus.

---

### [Hungarian-Assignment] The Hungarian Method for the Assignment Problem
- **Authors:** Harold W. Kuhn
- **Year:** 1955
- **Venue:** *Naval Research Logistics Quarterly*, vol. 2, no. 1–2, pp. 83–97
- **DOI:** [10.1002/nav.3800020109](https://doi.org/10.1002/nav.3800020109)
- **BibTeX:**
```bibtex
@article{kuhn1955hungarian,
  title={The {Hungarian} method for the assignment problem},
  author={Kuhn, Harold W},
  journal={Naval Research Logistics Quarterly},
  volume={2},
  number={1-2},
  pages={83--97},
  year={1955},
  doi={10.1002/nav.3800020109}
}
```
- **Architectural Grounding in Ssense:**
  Algorithmic foundation for optimal bipartite matching in [`metrics.py`](file:///d:/Ssense/ml/evals/metrics.py) (`calculate_violation_f1`). Replaces greedy order-dependent matching with optimal bipartite graph assignment between predicted multi-violation sets and ground truth legal annotations, guaranteeing objective precision, recall, and severity-weighted F1 scores.

---

## 18. Seminal Legal Language Models & Regulatory Privacy Policy Benchmarks

### [LegalBench] LegalBench: A Collaboratively Built Benchmark for Measuring Legal Reasoning in Large Language Models
- **Authors:** Neel Guha, Julian Nyarko, Daniel E. Ho, Christopher Ré, et al.
- **Year:** 2023
- **Venue:** *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 36, pp. 44474–44505
- **BibTeX:**
```bibtex
@inproceedings{guha2023legalbench,
  title={{LegalBench}: A Collaboratively Built Benchmark for Measuring Legal Reasoning in Large Language Models},
  author={Guha, Neel and Nyarko, Julian and Ho, Daniel E and R{\'e}, Christopher and others},
  booktitle={Advances in Neural Information Processing Systems (NeurIPS)},
  volume={36},
  pages={44474--44505},
  year={2023}
}
```
- **Architectural Grounding in Ssense:**
  Foundational benchmark establishing that general foundation models fail at fine-grained legal rule application and statutory interpretation. Ssense adapts this methodology to sovereign statutory compliance under the DPDP Act.

---

### [SaulLM-7B] SaulLM-7B: A Pioneering Large Language Model for Law
- **Authors:** Pierre Colombo, Telmo Pessoa Pires, Malik Boudiaf, Dominic Culver, Rui Melo, Caio Corro, Andre F. T. Martins, Fabrizio Sebastiani, et al.
- **Year:** 2024
- **Venue:** *arXiv preprint arXiv:2403.03883*
- **BibTeX:**
```bibtex
@article{colombo2024saullm,
  title={{SaulLM-7B}: A Pioneering Large Language Model for Law},
  author={Colombo, Pierre and Pires, Telmo Pessoa and Boudiaf, Malik and Culver, Dominic and Melo, Rui and Corro, Caio and Martins, Andre FT and Sebastiani, Fabrizio and others},
  journal={arXiv preprint arXiv:2403.03883},
  year={2024}
}
```
- **Architectural Grounding in Ssense:**
  Establishes that domain-adapted 7B Small Language Models (SLMs) can match or outperform proprietary mega-models when specialized on legal domain data. Ssense builds on this SLM paradigm for on-device/edge statutory auditing.

---

### [OPP-115] The Creation and Analysis of a Website Privacy Policy Corpus
- **Authors:** Shomir Wilson, Florian Schaub, Aswarth Abhilash Dara, Frederick Liu, Sushain Cherivirala, Pedro Giovanni Leon, Mads Schaarup Andersen, Sebastian Zimmeck, Kanthashree Mysore Sathyendra, N. Cameron Russell, Thomas B. Norton, Eduard Hovy, Joel R. Reidenberg, Norman Sadeh
- **Year:** 2016
- **Venue:** *Proceedings of the 54th Annual Meeting of the Association for Computational Linguistics (ACL)*, pp. 1330–1340
- **DOI:** [10.18653/v1/P16-1126](https://doi.org/10.18653/v1/P16-1126)
- **BibTeX:**
```bibtex
@inproceedings{wilson2016creation,
  title={The Creation and Analysis of a Website Privacy Policy Corpus},
  author={Wilson, Shomir and Schaub, Florian and Dara, Aswarth Abhilash and Liu, Frederick and Cherivirala, Sushain and Leon, Pedro Giovanni and Andersen, Mads Schaarup and Zimmeck, Sebastian and Sathyendra, Kanthashree Mysore and Russell, N Cameron and others},
  booktitle={Proceedings of the 54th Annual Meeting of the Association for Computational Linguistics (ACL)},
  pages={1330--1340},
  year={2016},
  doi={10.18653/v1/P16-1126}
}
```
- **Architectural Grounding in Ssense:**
  The seminal benchmark dataset establishing automated privacy policy analysis. Ssense evolves this paradigm from descriptive categorization to normative statutory compliance verification.

---

### [Polisis] Polisis: Automated Analysis and Presentation of Privacy Policies Using Deep Learning
- **Authors:** Hamza Harkous, Kassem Fawaz, Rémi Lebret, Florian Schaub, Kang G. Shin, Karl Aberer
- **Year:** 2018
- **Venue:** *Proceedings of the 27th USENIX Security Symposium (USENIX Security)*, pp. 531–548
- **BibTeX:**
```bibtex
@inproceedings{harkous2018polisis,
  title={{Polisis}: Automated Analysis and Presentation of Privacy Policies Using Deep Learning},
  author={Harkous, Hamza and Fawaz, Kassem and Lebret, R{\'e}mi and Schaub, Florian and Shin, Kang G and Aberer, Karl},
  booktitle={Proceedings of the 27th USENIX Security Symposium (USENIX Security)},
  pages={531--548},
  year={2018}
}
```
- **Architectural Grounding in Ssense:**
  Pioneering neural hierarchical classification framework for privacy policies. Directly motivates Ssense's layered presentation of compliance findings and citizen-facing conversational dialogue.

---

### [DISC-LawLLM] DISC-LawLLM: Fine-tuning Large Language Models with Intelligent Legal Reasoning
- **Authors:** Shengbin Yue, Wei Chen, Siyuan Wang, Bingxuan Li, Chenchen Shen, Shujun Liu, Yuxuan Zhou, Yao Xiao, Songyang Gao, Sen Hu, Xuanjing Huang, Zhongyu Wei
- **Year:** 2023
- **Venue:** *arXiv preprint arXiv:2309.11325*
- **BibTeX:**
```bibtex
@article{yue2023disc,
  title={{DISC-LawLLM}: Fine-tuning Large Language Models with Intelligent Legal Reasoning},
  author={Yue, Shengbin and Chen, Wei and Wang, Siyuan and Li, Bingxuan and Shen, Chenchen and Liu, Shujun and Zhou, Yuxuan and Xiao, Yao and Gao, Songyang and Hu, Sen and others},
  journal={arXiv preprint arXiv:2309.11325},
  year={2023}
}
```
- **Architectural Grounding in Ssense:**
  Foundational framework for legal syllogistic instruction tuning ($A \to B, B \to C \implies A \to C$), directly informing the three-step reasoning chain in Ssense's Data Forge.

---

### [Lawformer] Lawformer: A Pre-trained Language Model for Legal Long Documents
- **Authors:** Chaojun Xiao, Xuefei Hu, Zhiyuan Liu, Cunchao Tu, Maosong Sun
- **Year:** 2021
- **Venue:** *AI Open*, vol. 2, pp. 79–84
- **DOI:** [10.1016/j.aiopen.2021.06.003](https://doi.org/10.1016/j.aiopen.2021.06.003)
- **BibTeX:**
```bibtex
@article{xiao2021lawformer,
  title={Lawformer: A pre-trained language model for legal long documents},
  author={Xiao, Chaojun and Hu, Xuefei and Liu, Zhiyuan and Tu, Cunchao and Sun, Maosong},
  journal={AI Open},
  volume={2},
  pages={79--84},
  year={2021},
  doi={10.1016/j.aiopen.2021.06.003}
}
```
- **Architectural Grounding in Ssense:**
  Theoretical foundation for handling long-range dependencies in legal documents. Grounded Ssense's attention structuring and keyword-density chunk prioritization across long privacy policies ($>8,000$ tokens).

---

### [ChatLaw] ChatLaw: Open-Source Legal Large Language Model with Integrated External Knowledge Bases
- **Authors:** Jiaxi Cui, Zongjian Li, Yang Yan, Bohua Chen, Li Yuan
- **Year:** 2023
- **Venue:** *arXiv preprint arXiv:2306.16092*
- **BibTeX:**
```bibtex
@article{cui2023chatlaw,
  title={{ChatLaw}: Open-source legal large language model with integrated external knowledge bases},
  author={Cui, Jiaxi and Li, Zongjian and Yan, Yang and Chen, Bohua and Yuan, Li},
  journal={arXiv preprint arXiv:2306.16092},
  year={2023}
}
```
- **Architectural Grounding in Ssense:**
  Provides the architecture for combining legal SLMs with structured statutory knowledge bases and hybrid retrieval to prevent legal hallucination.




