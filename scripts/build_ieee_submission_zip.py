#!/usr/bin/env python3
"""
build_ieee_submission_zip.py – Assembles and compresses the complete, self-contained
IEEE submission bundle: `ssense_final_paperieee.zip`.
"""

import os
import sys
import shutil
import zipfile
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
STAGING_DIR = BASE_DIR / "ssense_final_paperieee"
ZIP_PATH = BASE_DIR / "ssense_final_paperieee.zip"

# Clean prior staging
if STAGING_DIR.exists():
    shutil.rmtree(STAGING_DIR)

STAGING_DIR.mkdir(parents=True, exist_ok=True)
(STAGING_DIR / "paper").mkdir(exist_ok=True)
(STAGING_DIR / "figures").mkdir(exist_ok=True)
(STAGING_DIR / "eval_data").mkdir(exist_ok=True)
(STAGING_DIR / "statutory_schemas").mkdir(exist_ok=True)
(STAGING_DIR / "scripts").mkdir(exist_ok=True)

# 1. Copy Paper Documents
for f in ["ssense_paper.md", "METHODOLOGY.md", "ssense_equations.md", "eval_final.md"]:
    src = BASE_DIR / "docs" / "paper" / f
    if not src.exists():
        src = BASE_DIR / "docs_final" / "paper" / f
    if src.exists():
        shutil.copy2(src, STAGING_DIR / "paper" / f)

# 2. Copy All Figures (PNG, SVG, WEBP, GIF)
fig_dir = BASE_DIR / "docs" / "paper" / "figures"
if fig_dir.exists():
    for f in fig_dir.iterdir():
        if f.is_file():
            shutil.copy2(f, STAGING_DIR / "figures" / f.name)

# Also ensure all root figures and SVG are copied
for f in BASE_DIR.glob("fig*.*"):
    if f.is_file() and f.suffix in [".png", ".svg", ".webp", ".gif"]:
        shutil.copy2(f, STAGING_DIR / "figures" / f.name)

for f in BASE_DIR.glob("ssense_extension_walkthrough.*"):
    if f.is_file():
        shutil.copy2(f, STAGING_DIR / "figures" / f.name)

# 3. Copy Evaluation & Benchmark Data
eval_files = [
    BASE_DIR / "evaluation_results_comprehensive.json",
    BASE_DIR / "eval_metrics.csv",
    BASE_DIR / "ml" / "evals" / "reports" / "master_evaluation_metrics.json",
    BASE_DIR / "ml" / "evals" / "reports" / "apliance_replication_benchmark.json",
    BASE_DIR / "ml" / "evals" / "holdout_policies" / "ground_truth_test_set.json",
    BASE_DIR / "ml" / "evals" / "benchmarks" / "security_adversarial_suite.json",
    BASE_DIR / "ml" / "evals" / "benchmarks" / "dpdp_chatbot_qa_bench.json",
    BASE_DIR / "ml" / "evals" / "benchmarks" / "dpdp_rag_tests.json",
    BASE_DIR / "ml" / "evals" / "benchmarks" / "redteam_hallucination_probes.json",
    BASE_DIR / "scratch" / "manual_audit_verification_10sites.json",
    BASE_DIR / "scratch" / "audit_10sites_results.json",
    BASE_DIR / "scratch" / "chat_10sites_results.json",
    BASE_DIR / "scratch" / "chat_modes_benchmark.json",
]

for ef in eval_files:
    if ef.exists():
        shutil.copy2(ef, STAGING_DIR / "eval_data" / ef.name)

# 4. Copy Statutory Schemas & Decision Tree
schema_files = [
    BASE_DIR / "libs" / "contracts" / "schemas" / "dpdp_act_tree.json",
    BASE_DIR / "libs" / "contracts" / "schemas" / "dpdp_schema.json",
    BASE_DIR / "apps" / "slm-server" / "schemas" / "dpdp_act_tree.json",
    BASE_DIR / "apps" / "slm-server" / "schemas" / "dpdp_schema.json",
    BASE_DIR / "ml" / "data-forge" / "dpdp_act_tree.json",
    BASE_DIR / "ml" / "models" / "rag-index" / "dpdp_index.json"
]

for sf in schema_files:
    if sf.exists():
        shutil.copy2(sf, STAGING_DIR / "statutory_schemas" / sf.name)

# 5. Copy Reproduction & Generation Scripts
script_files = [
    BASE_DIR / "scripts" / "generate_paper_eval_figures.py",
    BASE_DIR / "scripts" / "generate_additional_paper_figures.py",
    BASE_DIR / "scripts" / "generate_extension_figures_and_walkthrough.py",
    BASE_DIR / "scripts" / "test_single_chat.py"
]

for sc in script_files:
    if sc.exists():
        shutil.copy2(sc, STAGING_DIR / "scripts" / sc.name)

# 6. Create Comprehensive README.md
readme_content = """# Ssense: Complete IEEE Submission & Evaluation Archive (`ssense_final_paperieee.zip`)

This archive contains the complete research paper, all 300 DPI high-resolution figures (PNG & SVG vector), empirical evaluation datasets, statutory deontic schemas, and reproduction scripts for:

**"Ssense: A Domain-Adapted Legal Small Language Model and Scalable Inference Architecture for Auditing Global Web Compliance under India's DPDP Act, 2023 and DPDP Rules, 2025"**  
*Authors: Anubhav Das & Priyanshu Roy*  
*Department of Computer Science and Engineering, Institute of Engineering and Management, Kolkata, India*

---

## Archive Structure

```
ssense_final_paperieee/
├── paper/
│   ├── ssense_paper.md                     # Full IEEE Research Paper (Complete Publication Draft)
│   ├── METHODOLOGY.md                      # Detailed Experimental Protocol & Double-Blind Rubric
│   ├── ssense_equations.md                 # Formal Mathematical Equations & Deontic Logic
│   └── eval_final.md                       # Comprehensive Evaluation Matrix & Benchmark Tables
│
├── figures/                                # High-Resolution 300 DPI & Vector Figures
│   ├── fig1_overall_architecture.png       # Fig 1: End-to-End System Architecture
│   ├── fig2_training_alignment_pipeline.png# Fig 2: Data Forge Synthesis, rsLoRA & SimPO Alignment
│   ├── fig3_three_step_deductive_chain.png # Fig 3: 3-Step Syllogistic Chain & Omission Firewall
│   ├── fig4_audit_request_cache_pipeline.png# Fig 4: Multi-Tier Cache Hierarchy (LRU, SQLite, Mutex)
│   ├── fig4B_throughput_scaling.png        # Fig 4B: PagedAttention Throughput & Speculative Decoding
│   ├── fig5_deontic_confusion_matrix.png/.svg # Fig 5: 4x4 Deontic Modality Confusion Matrix (96.1%)
│   ├── fig6_statutory_taxonomy_f1.png/.svg # Fig 6: Per-Provision Statutory Classification Breakdown
│   ├── fig6B_fiduciary_breakdown.png/.svg  # Fig 6B: Fiduciary Compliance Profiles Across Strategic Sites
│   ├── fig7_comparative_radar.png/.svg     # Fig 7: 8-Axis Sovereign Legal-AI Benchmark Radar
│   ├── fig7A_apliance_replication.png/.svg # Fig 7A / Fig 14: Direct APLiance Replication (N=400)
│   ├── fig7B_multilabel_legalbench.png/.svg# Fig 7B / Fig 15: Multi-Label DPDP-Bench F1 & MCC
│   ├── fig8_judge_vs_human.png/.svg        # Fig 8 / Fig 11: LLM-as-a-Judge Calibration (MAE 0.312)
│   ├── fig8B_jurisdiction_isolation.png/.svg# Fig 8B / Fig 21: Cross-Jurisdictional Bleed (0.0% vs 54%)
│   ├── fig9_omission_ablation.png/.svg     # Fig 9 / Fig 10: Omission Firewall Silence Discrimination
│   ├── fig10_fiduciary_landscape.png/.svg  # Fig 10 / Fig 6: Empirical Audit Scores (>500M MAU)
│   ├── fig11_readability_lift.png/.svg     # Fig 11 / Fig 12: Readability Enhancement (+44 pts FRE)
│   ├── fig12_adversarial_security.png/.svg # Fig 12 / Fig 13: Adversarial Security Resilience (97.9%)
│   ├── fig13B_sovereign_edge.png/.svg      # Fig 13B / Fig 16: Measured Workstation Profile (RTX 3060)
│   ├── fig17_extension_multipanel_live.png # Fig 13C: Live Browser Extension & Sovereign Client UI
│   ├── ssense_extension_walkthrough.webp   # Public Release Animated Walkthrough Video (WebP)
│   └── ssense_extension_walkthrough.gif    # Public Release High-Res Animated Walkthrough (GIF)
│
├── eval_data/                              # Empirical Benchmarks, Holdouts, and Raw Ground Truth
│   ├── evaluation_results_comprehensive.json # Master benchmark metrics across all baselines
│   ├── eval_metrics.csv                    # Tabular metrics for paper tables
│   ├── apliance_replication_benchmark.json # 400-instance APLiance head-to-head replication data
│   ├── ground_truth_test_set.json          # 61 holdout corporate policies with 95 ground-truth labels
│   ├── security_adversarial_suite.json     # Adversarial injection, sycophancy, & 2D-NIAH test suite
│   ├── dpdp_chatbot_qa_bench.json          # Interactive citizen legal dialogue evaluation set
│   ├── dpdp_rag_tests.json                 # Statutory retrieval grounding test queries
│   ├── redteam_hallucination_probes.json   # Confabulation and fake safe-harbor probe suite
│   ├── audit_10sites_results.json          # Real-world fiduciary compliance audit outputs
│   └── manual_audit_verification_10sites.json # Double-blind human advocate validation annotations
│
├── statutory_schemas/                      # Formal Computational Representation of Indian Law
│   ├── dpdp_act_tree.json                  # 26-node formal statutory decision tree (DPDP 2023 & Rules 2025)
│   ├── dpdp_schema.json                    # Formal JSON schema enforcing Pushdown Automaton CFG decoding
│   └── dpdp_index.json                     # Curated legislative chunk index for hybrid RAG grounding
│
└── scripts/                                # Autonomous Evaluation & Figure Reproduction Scripts
    ├── generate_paper_eval_figures.py      # Generates Fig 14 (APLiance), Fig 15 (LegalBench), Fig 16 (Edge)
    ├── generate_additional_paper_figures.py# Generates Fig 21 (Jurisdiction), Fig 22 (Cases), Fig 23 (Serving)
    ├── generate_extension_figures_and_walkthrough.py # Generates live multi-panel UI figure & animations
    └── test_single_chat.py                 # Live HMAC-SHA256 authenticated streaming test client
```

---

## Reproduction Instructions

### 1. Re-generate All Paper Figures
```bash
python scripts/generate_paper_eval_figures.py
python scripts/generate_additional_paper_figures.py
python scripts/generate_extension_figures_and_walkthrough.py
```

### 2. Verify Sovereign SLM Inference on NVIDIA RTX 3060 (12GB)
```bash
python scripts/test_single_chat.py
```
"""

with open(STAGING_DIR / "README.md", "w", encoding="utf-8") as f:
    f.write(readme_content)

# 7. Compress into ssense_final_paperieee.zip
if ZIP_PATH.exists():
    ZIP_PATH.unlink()

print(f"📦 Compressing into {ZIP_PATH.name}...")
with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(STAGING_DIR):
        for file in files:
            full_path = Path(root) / file
            arc_name = full_path.relative_to(STAGING_DIR)
            zf.write(full_path, arc_name)

zip_size_mb = os.path.getsize(ZIP_PATH) / (1024 * 1024)
print(f"🎉 Successfully created {ZIP_PATH.name} ({zip_size_mb:.2f} MB)!")
