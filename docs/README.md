# Ssense Documentation Suite

Welcome to the comprehensive technical documentation and research archive for **Ssense** — an in situ statutory compliance auditing framework and sovereign Legal Small Language Model (Law-LM) for India's **Digital Personal Data Protection (DPDP) Act, 2023** and **DPDP Rules, 2025**.

---

## Documentation Directory Map

```
docs/
├── README.md                              <-- Master documentation index (this file)
├── paper/                                 <-- Research paper & academic artifacts
│   ├── ssense_paper.md                    <-- Flagship IEEE paper (62 citations, 26 enums)
│   ├── ssense_equations.md                <-- Mathematical formulations & proofs
│   ├── METHODOLOGY.md                     <-- Scientific methodology & experimental design
│   ├── eval_final.md                      <-- Final empirical evaluation metrics
│   ├── simulate_chat_eval.py              <-- Conversational dialogue evaluation harness
│   ├── simulate_high_volume.py            <-- High-concurrency serving simulation
│   ├── Ssense_IEEE_Paper_41refs.docx      <-- Pre-print manuscript document (Word)
│   └── Ssense_IEEE_Paper_41refs.pdf       <-- Pre-print manuscript document (PDF)
│
├── research/ (Research Groundings)
│   ├── citations.md                       <-- Canonical 62-reference bibliography & prior art
│   ├── DATA_FORGE_RESEARCH_GROUNDING.md   <-- Synthetic data distillation & deontic groundings
│   ├── ML_ARCHITECTURE_RESEARCH_GROUNDING.md <-- Law-LM & hybrid RAG research groundings
│   ├── TRAINING_RESEARCH_GROUNDING.md     <-- rsLoRA & SimPO preference alignment groundings
│   └── Evaluation.md                      <-- Evaluation metrics & statistical gating
│
├── architecture/
│   ├── ARCHITECTURE.md                    <-- End-to-end system architecture & component flow
│   ├── SLM_Server_Architecture.md         <-- Inference serving engine & backend architecture
│   ├── SECURITY.md                        <-- Threat modeling, injection defense & crypto verification
│   └── DESIGN.md                          <-- UI/UX design tokens & interface aesthetics
│
├── deployment/ & Operations
│   ├── DEPLOYMENT.md                      <-- Production deployment (AWS EC2, Cloudflare, Docker)
│   ├── BUILD.md                           <-- Monorepo build & environment setup
│   ├── MANUAL_START_GUIDE.md              <-- Native local execution without Docker
│   └── TESTING_WINDOWS.md                 <-- Windows testbed & driver validation
│
├── extension/
│   ├── CHROME_WEB_STORE_MANUAL.md         <-- Chrome Web Store maintainer & release guide
│   ├── CHROME_WEB_STORE_LISTING.md        <-- Extension store listing copy & assets
│   └── USER_MANUAL.md                     <-- End-user operations & features guide
│
├── reports/ & Changelogs
│   ├── project_report.md                  <-- Project milestones & architectural summary
│   ├── verification.md                    <-- System validation & compliance test matrix
│   ├── UPGRADES_2026_09.md                <-- September 2026 platform upgrades
│   └── V1_RELEASE_UPGRADE.md              <-- v1 to v2.3 migration & release changelog
│
└── reviews/
    ├── SLM_Server_Review_Round3.md        <-- Architectural review: RAG device & multi-chunk audit
    └── SLM_Server_Review_Round4.md        <-- Architectural review: single-pass deterministic audit
```

---

## 1. Academic Research & Publications

- **[Flagship IEEE Research Paper](paper/ssense_paper.md)**: The authoritative manuscript formatted to IEEE Transactions standards. Details the joint statutory reduction from 44 sections of the DPDP Act, 2023 and 22 rules of the DPDP Rules, 2025 to the complete 26-node actionable taxonomy ($\mathcal{V}_{26}$), fine-tuned dual rsLoRA ($r=128, \alpha=32$ for auditor; $r=64, \alpha=16$ for dialogue), SimPO alignment ($\beta=2.0$), XGrammar pushdown automaton (PDA) schema constrained decoding, attention-aware hybrid RAG (BGE + BM25Okapi + Cross-Encoder reranker), and continuous batching with PagedAttention.
- **[Mathematical Formulations & Equations](paper/ssense_equations.md)**: Formal proofs for deontic statutory logic, omission firewall gating, loss functions, and Wilson score confidence bounds.
- **[Methodology Specification](paper/METHODOLOGY.md)**: Complete experimental design, pilot testbed of 100 enterprise privacy policies, 3-senior-privacy-counsel gold standard, and ablation protocols.
- **[Canonical Citations & Prior Art](citations.md)**: Complete 62-reference bibliography spanning modern top-tier venues (ACL, EMNLP, NeurIPS, ICLR, OSDI, SOSP, USENIX Security, IEEE S&P).

---

## 2. System Architecture & Core Engineering

- **[System Architecture](ARCHITECTURE.md)**: High-level overview of the Ssense monorepo, covering the Chrome extension client, Next.js enterprise dashboard, FastAPI SLM server, and hybrid local/cloud topologies.
- **[SLM Server Architecture](SLM_Server_Architecture.md)**: Detailed specification of the inference engine, vLLM / Transformers backends, dynamic VRAM allocation, and multi-tier SHA-256 caching.
- **[Security & Threat Defense](SECURITY.md)**: 18-axis security certification, indirect prompt injection defense (NFKC normalization, character entropy filtering), HMAC token authentication, and sandboxed client execution.
- **[Design System](DESIGN.md)**: Design tokens, color palettes, dark-mode styling, and accessible layout guidelines.

---

## 3. Operations, Deployment & Setup

- **[Production Deployment Guide](DEPLOYMENT.md)**: Step-by-step instructions for deploying Ssense on AWS EC2 GPU instances with Docker, Docker Compose, and Cloudflare zero-trust tunnels.
- **[Manual Quickstart Guide](MANUAL_START_GUIDE.md)**: Run Ssense directly on bare metal without Docker using Python virtual environments, PyTorch CUDA, and Node.js.
- **[Monorepo Build Guide](BUILD.md)**: Instructions for compiling TypeScript, Rust crates, Python dependencies, and Turborepo packages.
- **[Windows Testbed Guide](TESTING_WINDOWS.md)**: Hardware configuration, NVIDIA CUDA drivers, and troubleshooting for Windows workstation environments.

---

## 4. Chrome Extension & User Guides

- **[Chrome Web Store Release Manual](CHROME_WEB_STORE_MANUAL.md)**: Maintainer instructions for building, packaging, and submitting the zero-config Manifest V3 extension to the Chrome Web Store.
- **[Store Listing & Assets](CHROME_WEB_STORE_LISTING.md)**: Official marketing descriptions, permission disclosures, and feature highlights.
- **[User Manual](USER_MANUAL.md)**: Guide for end-users on how to read the DPDP Trust Score, inspect statutory violations, and consult the AI legal dialogue co-pilot.

---

## 5. Development Reviews & Evolution History

- **[Project Report](project_report.md)** & **[Verification Matrix](verification.md)**: Comprehensive verification of accuracy, latency, and compliance across 100 enterprise domains.
- **[Review Round 3](reviews/SLM_Server_Review_Round3.md)** & **[Review Round 4](reviews/SLM_Server_Review_Round4.md)**: Development decision logs explaining why multi-chunk auditing was unified into a single deterministic aggregation layer.
