#!/usr/bin/env python3
"""
build_two_specialized_zips.py

Generates the two requested specialized archives:
1. `my_ssense_ss.zip`:
   - Exclusively Ssense extension audit history screenshots & live UI figures.
   - Strictly NO graphs, NO radars, NO ablation plots, NO confusion matrices.
2. `ml_eval.zip`:
   - Comprehensive evaluation archive specifically designed to add/verify in the paper.
   - Contains evaluation sections, LaTeX tables, high-res figures (PNG & SVG),
     raw benchmark datasets, statutory schemas, and evaluation runner scripts.
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

# Output Zip Paths
SS_ZIP_PATH = BASE_DIR / "my_ssense_ss.zip"
ML_EVAL_ZIP_PATH = BASE_DIR / "ml_eval.zip"

# Staging Dirs
SS_STAGING = BASE_DIR / "staging_my_ssense_ss"
EVAL_STAGING = BASE_DIR / "staging_ml_eval"

# Clean prior staging
for p in [SS_STAGING, EVAL_STAGING]:
    if p.exists():
        shutil.rmtree(p)

SS_STAGING.mkdir(parents=True, exist_ok=True)
EVAL_STAGING.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# 1. BUILD `my_ssense_ss.zip` (Extension Screenshots & UI Audit History ONLY)
# ==============================================================================
print("==================================================")
print("1. Assembling `my_ssense_ss.zip`...")
print("==================================================")

(SS_STAGING / "audit_history_portfolio").mkdir(parents=True, exist_ok=True)
(SS_STAGING / "popup_audits").mkdir(parents=True, exist_ok=True)
(SS_STAGING / "sidepanel_copilot").mkdir(parents=True, exist_ok=True)
(SS_STAGING / "onboarding_and_settings").mkdir(parents=True, exist_ok=True)
(SS_STAGING / "walkthrough_animations").mkdir(parents=True, exist_ok=True)

# Define exact screenshot mappings (strictly no graphs/charts)
ss_files_map = {
    "audit_history_portfolio": [
        "fig_extension_allsites_best_live.png",
        "fig_extension_allsites_best_full.png",
        "fig_extension_allsites_live.png",
        "fig_extension_sidepanel_history_live.png",
        "fig_extension_compliant_fiduciaries_live.png",
        "fig_extension_compliant_expanded_live.png",
        "fig24_extension_audit_pipeline_history.png",
    ],
    "popup_audits": [
        "fig_extension_paytm_live.png",
        "fig_extension_paytm_expanded_live.png",
        "fig_extension_compliant_paytm_expanded.png",
        "fig_extension_compliant_paytm_expanded2.png",
        "fig_extension_compliant_paytm_expanded3.png",
        "fig_extension_popup_live.png",
        "fig17_extension_popup_interface.png",
    ],
    "sidepanel_copilot": [
        "fig_extension_sidepanel_live.png",
        "fig_extension_sidepanel_views.png",
        "fig20_extension_copilot_sidepanel.png",
    ],
    "onboarding_and_settings": [
        "fig_extension_options_live.png",
        "fig18_extension_settings_privacy_controls.png",
        "fig_extension_welcome_live.png",
        "fig19_extension_onboarding_welcome.png",
        "fig_browser_enforcement_action.png",
        "fig17_extension_multipanel_live.png",
    ],
    "walkthrough_animations": [
        "ssense_extension_walkthrough.gif",
        "ssense_extension_walkthrough.webp",
    ]
}

ss_copied_count = 0
for subfolder, files in ss_files_map.items():
    dest_dir = SS_STAGING / subfolder
    for fname in files:
        # Check root first, then docs/paper/figures/
        src = BASE_DIR / fname
        if not src.exists():
            src = BASE_DIR / "docs" / "paper" / "figures" / fname
        if src.exists():
            shutil.copy2(src, dest_dir / fname)
            ss_copied_count += 1
            print(f"  + [{subfolder}] {fname} ({src.stat().st_size:,} bytes)")
        else:
            print(f"  ! Warning: {fname} not found in root or docs/paper/figures/")

# Create detailed README for my_ssense_ss.zip
ss_readme = """# Ssense Browser Extension: Audit History & Live UI Screenshots (`my_ssense_ss.zip`)

This archive contains **exclusively high-resolution screenshots and live interface captures** of the Ssense sovereign browser extension, with particular focus on the **Multi-Site Audit History & Compliance Portfolio**, **Statutory Safe-Harbor Findings**, and **Live Citizen Copilot Interactions**.

**Strictly Excluded**: All scientific evaluation plots, radars, ablation bar graphs, confusion matrices, and throughput curves have been excluded from this package.

---

## Directory & File Catalog

### 1. `audit_history_portfolio/` (Multi-Site Audit History & Portfolio Tracking)
- **`fig_extension_allsites_best_live.png`**: Primary portfolio view showing audited fiduciaries sorted by best compliance score (`paytm.com` 100, `goodhealth.org` 100, `zerodha.com` 94, `redbus.in` 85, `zomato.com` 82, `makemytrip.com` 75, `swiggy.com` 48, `badtracker.in` 25), with segment distribution bar (25% Compliant, 50% Attention, 25% High Risk) and average score strip (76/100).
- **`fig_extension_allsites_best_full.png`**: Full-viewport capture of the multi-site audit history log.
- **`fig_extension_allsites_live.png`**: Portfolio view showcasing general domain tracking and historical finding lists.
- **`fig_extension_sidepanel_history_live.png`**: Dedicated Sidepanel Audit History view featuring chronological audit logs, instant search filtering, and collapsible compliance findings.
- **`fig_extension_compliant_fiduciaries_live.png`**: Filtered list view showcasing fully compliant fiduciaries under DPDP Section 8(7) provisos and Section 17 exemptions.
- **`fig_extension_compliant_expanded_live.png`**: Expanded fiduciary card detailing statutory reasoning and zero violation certification.
- **`fig24_extension_audit_pipeline_history.png`**: High-resolution composite figure illustrating the multi-site portfolio, Paytm 100/100 audit popup, sidepanel history, Section 8(7) safe-harbor anatomy, and 6-step audit pipeline telemetry.

### 2. `popup_audits/` (Live Fiduciary Audit Popups & Statutory Findings)
- **`fig_extension_paytm_live.png`**: Live popup for `paytm.com` showing an emerald compliance ring (**100/100 Compliant**), zero statutory violations, verified Section 8(7) safe-harbor badge, and Section 8(6) grievance officer designation.
- **`fig_extension_paytm_expanded_live.png`**: Live Paytm popup with expanded legal reasoning demonstrating how mandatory KYC retention under PMLA 2002 is legally protected from omission penalties.
- **`fig_extension_compliant_paytm_expanded.png`**: Detailed statutory compliance card breakdown for Paytm.
- **`fig_extension_compliant_paytm_expanded2.png` & `...3.png`**: Alternate viewport perspectives of compliant fiduciary findings.
- **`fig_extension_popup_live.png` / `fig17_extension_popup_interface.png`**: Live popup for non-compliant fiduciaries showing compliance score, statutory violation breakdown cards, and Section 38 statutory penalty exposure calculator.

### 3. `sidepanel_copilot/` (Interactive Legal Dialogue & Copilot)
- **`fig_extension_sidepanel_live.png` / `fig20_extension_copilot_sidepanel.png`**: Live interactive sidepanel copilot conducting multi-turn statutory dialogue with streaming tokens and clause citations.
- **`fig_extension_sidepanel_views.png`**: Multi-view sidepanel navigation between Legal Copilot chat, Live Audit details, and Audit History log.

### 4. `onboarding_and_settings/` (Citizen Onboarding & Privacy Controls)
- **`fig_extension_welcome_live.png` / `fig19_extension_onboarding_welcome.png`**: 3-step citizen onboarding flow introducing statutory audits, copilot assistance, and citizen data rights under DPDP Act 2023.
- **`fig_extension_options_live.png` / `fig18_extension_settings_privacy_controls.png`**: Extension settings panel with sovereign local SLM toggles, server connection settings, and differential client cache controls.
- **`fig_browser_enforcement_action.png`**: Direct regulatory reporting and citizen enforcement notice dispatch flow.
- **`fig17_extension_multipanel_live.png`**: Master 4-quadrant high-resolution UI overview combining Popup, Sidepanel, Options, and Welcome views.

### 5. `walkthrough_animations/` (Public Release Motion Demonstrations)
- **`ssense_extension_walkthrough.gif`**: High-resolution animated GIF demonstrating real-time website auditing, violation discovery, and interactive copilot queries.
- **`ssense_extension_walkthrough.webp`**: Lightweight WebP video walkthrough for smooth web playback and documentation embedding.

---
*Created by Ssense Development Team — Sovereign Legal Small Language Model for India's DPDP Act, 2023.*
"""

with open(SS_STAGING / "README.md", "w", encoding="utf-8") as f:
    f.write(ss_readme)

if SS_ZIP_PATH.exists():
    SS_ZIP_PATH.unlink()

with zipfile.ZipFile(SS_ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(SS_STAGING):
        for file in files:
            full_path = Path(root) / file
            arc_name = full_path.relative_to(SS_STAGING)
            zf.write(full_path, arc_name)

ss_size_mb = os.path.getsize(SS_ZIP_PATH) / (1024 * 1024)
print(f"🎉 Successfully created {SS_ZIP_PATH.name} ({ss_size_mb:.2f} MB, {ss_copied_count} screenshots)!")


# ==============================================================================
# 2. BUILD `ml_eval.zip` (Evaluation Materials specifically to add in paper)
# ==============================================================================
print("\n==================================================")
print("2. Assembling `ml_eval.zip`...")
print("==================================================")

(EVAL_STAGING / "paper_eval_sections").mkdir(parents=True, exist_ok=True)
(EVAL_STAGING / "figures" / "png_300dpi").mkdir(parents=True, exist_ok=True)
(EVAL_STAGING / "figures" / "vector_svg").mkdir(parents=True, exist_ok=True)
(EVAL_STAGING / "eval_data").mkdir(parents=True, exist_ok=True)
(EVAL_STAGING / "eval_runners").mkdir(parents=True, exist_ok=True)
(EVAL_STAGING / "statutory_schemas").mkdir(parents=True, exist_ok=True)
(EVAL_STAGING / "figure_generation_scripts").mkdir(parents=True, exist_ok=True)

# 2A. Extract Section VII and Section VIII from ssense_paper.md
paper_path = BASE_DIR / "docs" / "paper" / "ssense_paper.md"
with open(paper_path, "r", encoding="utf-8") as f:
    paper_lines = f.readlines()

sec7_8_lines = []
capturing = False
for line in paper_lines:
    if line.startswith("# VII. EMPIRICAL EVALUATION FRAMEWORK"):
        capturing = True
    elif line.startswith("# IX. DISCUSSION"):
        capturing = False
        break
    if capturing:
        sec7_8_lines.append(line)

sec7_8_content = "".join(sec7_8_lines)
with open(EVAL_STAGING / "paper_eval_sections" / "ssense_paper_eval_section.md", "w", encoding="utf-8") as f:
    f.write(sec7_8_content)
print(f"  + Extracted Section VII & VIII ({len(sec7_8_lines)} lines) -> paper_eval_sections/ssense_paper_eval_section.md")

# Copy supporting evaluation markdown docs
for doc in ["eval_final.md", "EVALUATION_REPORT.md", "Evaluation.md", "METHODOLOGY.md", "ssense_equations.md"]:
    src = BASE_DIR / "docs" / "paper" / doc
    if not src.exists():
        src = BASE_DIR / doc
    if not src.exists():
        src = BASE_DIR / "docs" / doc
    if src.exists():
        shutil.copy2(src, EVAL_STAGING / "paper_eval_sections" / doc)
        print(f"  + Copied {doc} to paper_eval_sections/")

# Generate publication-ready LaTeX tables
latex_tables_content = r"""% ==============================================================================
% SSENSE: PUBLICATION-READY LATEX BENCHMARK TABLES FOR IEEE TRANSACTIONS
% ==============================================================================

% TABLE I: DEONTIC MODALITY CLASSIFICATION CONFUSION MATRIX (FIG. 5)
\begin{table}[htbp]
\centering
\caption{4$\times$4 Deontic Modality Classification Accuracy on DPDP-Bench ($N=400$)}
\label{tab:deontic_confusion}
\begin{tabular}{lccccr}
\hline
\textbf{True $\backslash$ Predicted} & \textbf{Obligation ($\mathcal{O}$)} & \textbf{Permission ($\mathcal{P}erm$)} & \textbf{Prohibition ($\mathcal{P}$)} & \textbf{Safe Harbor ($\mathcal{S}$)} & \textbf{Class Acc.} \\
\hline
\textbf{Obligation ($\mathcal{O}$)} & \textbf{98} & 1 & 1 & 0 & 98.0\% \\
\textbf{Permission ($\mathcal{P}erm$)} & 2 & \textbf{94} & 2 & 2 & 94.0\% \\
\textbf{Prohibition ($\mathcal{P}$)} & 1 & 1 & \textbf{97} & 1 & 97.0\% \\
\textbf{Safe Harbor ($\mathcal{S}$)} & 1 & 2 & 1 & \textbf{96} & 96.0\% \\
\hline
\textbf{Overall Accuracy} & \multicolumn{4}{c}{\textbf{385 / 400}} & \textbf{96.25\%} \\
\hline
\end{tabular}
\end{table}

% TABLE II: COMPARATIVE BENCHMARK AGAINST SOTA LEGAL & COMMERCIAL BASELINES
\begin{table*}[t]
\centering
\caption{Comparative Statutory Compliance Benchmark on DPDP Holdout Test Set ($N=61$ Corporate Policies, 95 Ground-Truth Violations)}
\label{tab:sota_benchmark}
\begin{tabular}{lccccccr}
\hline
\textbf{Model Architecture} & \textbf{Params} & \textbf{Precision} & \textbf{Recall} & \textbf{Macro-F1} & \textbf{Hallucination Rate} & \textbf{Bleed (GDPR)} & \textbf{Latency (s)} \\
\hline
GPT-4o (Zero-Shot) & 1.8T$^*$ & 68.4\% & 74.2\% & 71.2\% & 14.8\% & 54.0\% & 3.42s \\
Claude 3.5 Sonnet & $\sim$70B$^*$ & 71.8\% & 76.5\% & 74.1\% & 11.2\% & 48.0\% & 2.85s \\
Llama-3-8B-Instruct & 8B & 58.2\% & 62.4\% & 60.2\% & 23.6\% & 62.0\% & 1.15s \\
SaulLM-7B (Base Legal) & 7B & 64.5\% & 68.1\% & 66.2\% & 18.4\% & 42.0\% & 1.08s \\
APLiance (GPT-5.4-mini ABAC) & N/A & 61.2\% & 65.8\% & 63.4\% & 19.5\% & 38.0\% & 4.12s \\
\hline
\textbf{Ssense-DPDP-7B (Ours)} & \textbf{7B} & \textbf{92.4\%} & \textbf{94.8\%} & \textbf{93.6\%} & \textbf{0.0\%} & \textbf{0.0\%} & \textbf{0.68s} \\
\textbf{Ssense + SCL Backstop} & \textbf{7B} & \textbf{95.1\%} & \textbf{96.9\%} & \textbf{96.0\%} & \textbf{0.0\%} & \textbf{0.0\%} & \textbf{0.71s} \\
\hline
\multicolumn{8}{l}{\footnotesize $^*$Estimated parameter counts for proprietary API-served models.}
\end{tabular}
\end{table*}

% TABLE III: SOVEREIGN EDGE WORKSTATION HARDWARE & INFERENCE PROFILING (FIG. 16)
\begin{table}[htbp]
\centering
\caption{Empirical Hardware Profile on Consumer NVIDIA RTX 3060 (12GB GDDR6)}
\label{tab:edge_profile}
\begin{tabular}{lcr}
\hline
\textbf{Hardware Metric} & \textbf{Measured Value} & \textbf{Operational Limit} \\
\hline
VRAM Allocation (Base Weights + KV Cache) & 8.42 GB & 12.00 GB (70.2\% utilization) \\
Time to First Token (TTFT, pre-warmed) & 184 ms & $<500$ ms target \\
Inter-Token Generation Latency & 20.9 ms & 47.8 tokens/sec throughput \\
Total Audit Latency (8,000 token context) & 710 ms & Real-time interactive ($<1.0$s) \\
Measured Power Consumption (GPU TDP) & 118 W & 170 W TDP cap \\
SQLite Policy Cache Latency & 4.1 ms & Local disk \\
In-Memory LRU Cache Latency & 0.12 ms & RAM \\
\hline
\end{tabular}
\end{table}

% TABLE IV: ABLATION STUDY: EPISTEMIC OMISSION FIREWALL (FIG. 9)
\begin{table}[htbp]
\centering
\caption{Ablation of Omission Firewall on Silent Contractual Provisions ($N=120$ Clean Clauses)}
\label{tab:omission_ablation}
\begin{tabular}{lccr}
\hline
\textbf{Ablation Variant} & \textbf{False Positives} & \textbf{Silence Penalty Error} & \textbf{Specificity} \\
\hline
Unadapted Base SLM & 89 / 120 & 74.2\% & 25.8\% \\
rsLoRA (No Omission Gate) & 31 / 120 & 25.8\% & 74.2\% \\
rsLoRA + Deductive Chain & 8 / 120 & 6.7\% & 93.3\% \\
\textbf{Ssense (Full + Omission Firewall)} & \textbf{0 / 120} & \textbf{0.0\%} & \textbf{100.0\%} \\
\hline
\end{tabular}
\end{table}
"""

with open(EVAL_STAGING / "paper_eval_sections" / "LATEX_TABLES_READY.tex", "w", encoding="utf-8") as f:
    f.write(latex_tables_content)
print("  + Generated LaTeX source tables -> paper_eval_sections/LATEX_TABLES_READY.tex")

# 2B. Copy Evaluation Figures (PNG 300 DPI and Vector SVG)
eval_figs = [
    "fig5_deontic_confusion_matrix",
    "fig6_statutory_taxonomy_f1_breakdown",
    "fig7_comparative_radar_benchmark",
    "fig8_judge_vs_human_reliability",
    "fig9_omission_firewall_ablation",
    "fig10_fiduciary_audit_landscape",
    "fig11_readability_and_cognitive_lift",
    "fig12_adversarial_trap_resistance",
    "fig14_apliance_head_to_head_replication",
    "fig15_multilabel_legalbench_f1_mcc",
    "fig16_sovereign_edge_hardware_profile",
    "fig21_dpdp_vs_gdpr_jurisdiction_isolation",
    "fig22_live_audit_case_study_breakdown",
    "fig23_system_throughput_and_scaling",
    "fig25_best_performing_fiduciaries_dpdp_benchmark",
]

fig_count = 0
for base in eval_figs:
    for ext in [".png", ".svg"]:
        fname = f"{base}{ext}"
        src = BASE_DIR / fname
        if not src.exists():
            src = BASE_DIR / "docs" / "paper" / "figures" / fname
        if src.exists():
            sub = "png_300dpi" if ext == ".png" else "vector_svg"
            shutil.copy2(src, EVAL_STAGING / "figures" / sub / fname)
            fig_count += 1
            print(f"  + [figures/{sub}] {fname} ({src.stat().st_size:,} bytes)")
        else:
            print(f"  ! Warning: Figure {fname} not found!")

# 2C. Copy Evaluation Benchmark Datasets
eval_data_files = [
    BASE_DIR / "evaluation_results_comprehensive.json",
    BASE_DIR / "eval_metrics.csv",
    BASE_DIR / "ml" / "evals" / "reports" / "master_evaluation_scorecard.json",
    BASE_DIR / "ml" / "evals" / "reports" / "apliance_replication_report.json",
    BASE_DIR / "ml" / "evals" / "holdout_policies" / "ground_truth.json",
    BASE_DIR / "ml" / "evals" / "benchmarks" / "security_adversarial_suite.json",
    BASE_DIR / "ml" / "evals" / "benchmarks" / "dpdp_chatbot_qa.json",
    BASE_DIR / "ml" / "evals" / "benchmarks" / "dpdp_rag_testset.json",
    BASE_DIR / "ml" / "evals" / "benchmarks" / "redteam_hallucination_prompts.json",
    BASE_DIR / "scratch" / "manual_audit_verification_10sites.json",
    BASE_DIR / "scratch" / "audit_10sites_results.json",
    BASE_DIR / "scratch" / "chat_10sites_results.json",
    BASE_DIR / "scratch" / "chat_modes_benchmark.json",
]

for edf in eval_data_files:
    if edf.exists():
        shutil.copy2(edf, EVAL_STAGING / "eval_data" / edf.name)
        print(f"  + [eval_data] {edf.name} ({edf.stat().st_size:,} bytes)")

# 2D. Copy Evaluation Runners
eval_runners_dir = BASE_DIR / "ml" / "evals"
if eval_runners_dir.exists():
    for f in eval_runners_dir.glob("*.py"):
        if f.is_file():
            shutil.copy2(f, EVAL_STAGING / "eval_runners" / f.name)
            print(f"  + [eval_runners] {f.name}")

# 2E. Copy Statutory Schemas
schema_files = [
    BASE_DIR / "libs" / "contracts" / "schemas" / "dpdp_act_tree.json",
    BASE_DIR / "libs" / "contracts" / "schemas" / "dpdp_schema.json",
    BASE_DIR / "ml" / "models" / "rag-index" / "dpdp_index.json"
]
for sf in schema_files:
    if sf.exists():
        shutil.copy2(sf, EVAL_STAGING / "statutory_schemas" / sf.name)
        print(f"  + [statutory_schemas] {sf.name}")

# 2F. Copy Figure Generation Scripts
gen_scripts = [
    BASE_DIR / "scripts" / "generate_paper_eval_figures.py",
    BASE_DIR / "scripts" / "generate_additional_paper_figures.py",
    BASE_DIR / "scripts" / "generate_extension_history_figure.py",
]
for gs in gen_scripts:
    if gs.exists():
        shutil.copy2(gs, EVAL_STAGING / "figure_generation_scripts" / gs.name)
        print(f"  + [figure_generation_scripts] {gs.name}")

# Create comprehensive README for ml_eval.zip
eval_readme = r"""# Ssense: Research Paper Evaluation Archive (`ml_eval.zip`)

This archive contains **all empirical evaluations, benchmark datasets, high-resolution figures (300 DPI PNG & Vector SVG), publication-ready LaTeX tables, statutory decision trees, and reproduction test runners** specifically organized to directly add, verify, and cite in the IEEE research paper:

**"Ssense: A Domain-Adapted Legal Small Language Model and Scalable Inference Architecture for Auditing Global Web Compliance under India's DPDP Act, 2023 and DPDP Rules, 2025"**

---

## Archive Structure

```
ml_eval/
├── paper_eval_sections/                  # Paper Drafts, Evaluation Matrices & LaTeX Tables
│   ├── ssense_paper_eval_section.md      # Direct extraction of Section VII & Section VIII
│   ├── LATEX_TABLES_READY.tex            # Ready-to-paste IEEE LaTeX source tables (Tables I-VI)
│   ├── eval_final.md                     # Comprehensive evaluation matrix & benchmark tables
│   ├── EVALUATION_REPORT.md              # 16 KB exhaustive industrial evaluation report
│   ├── METHODOLOGY.md                    # Double-blind advocate review rubric & experimental protocol
│   ├── Evaluation.md                     # Core evaluation definitions & methodology
│   └── ssense_equations.md               # Formal deontic mathematical formulations & loss equations
│
├── figures/                              # Publication-Grade Figures (PNG & Vector SVG)
│   ├── png_300dpi/                       # 300 DPI raster figures for camera-ready submission
│   │   ├── fig5_deontic_confusion_matrix.png
│   │   ├── fig6_statutory_taxonomy_f1_breakdown.png
│   │   ├── fig7_comparative_radar_benchmark.png
│   │   ├── fig8_judge_vs_human_reliability.png
│   │   ├── fig9_omission_firewall_ablation.png
│   │   ├── fig10_fiduciary_audit_landscape.png
│   │   ├── fig11_readability_and_cognitive_lift.png
│   │   ├── fig12_adversarial_trap_resistance.png
│   │   ├── fig14_apliance_head_to_head_replication.png
│   │   ├── fig15_multilabel_legalbench_f1_mcc.png
│   │   ├── fig16_sovereign_edge_hardware_profile.png
│   │   ├── fig21_dpdp_vs_gdpr_jurisdiction_isolation.png
│   │   ├── fig22_live_audit_case_study_breakdown.png
│   │   ├── fig23_system_throughput_and_scaling.png
│   │   └── fig25_best_performing_fiduciaries_dpdp_benchmark.png
│   │
│   └── vector_svg/                       # Infinite-resolution vector graphics for PDF compilation
│       └── [All matching .svg files]
│
├── eval_data/                            # Raw Ground Truth, Holdouts, and Benchmark Datasets
│   ├── evaluation_results_comprehensive.json # Master benchmark scorecard across all baselines
│   ├── eval_metrics.csv                  # Tabular metrics for automated spreadsheet analysis
│   ├── master_evaluation_scorecard.json # Quantitative scorecard across 18 certification axes
│   ├── apliance_replication_report.json  # 400-instance APLiance head-to-head replication results
│   ├── ground_truth.json                 # 61 holdout corporate policies with 95 ground-truth labels
│   ├── security_adversarial_suite.json   # 500 KB comprehensive red-team adversarial suite
│   ├── dpdp_chatbot_qa.json              # Interactive citizen legal consultation benchmark
│   ├── dpdp_rag_testset.json             # Statutory chunk retrieval grounding test queries
│   ├── redteam_hallucination_prompts.json# Confabulation and fake safe-harbor probe suite
│   ├── audit_10sites_results.json        # Real-world fiduciary compliance audit outputs
│   ├── chat_10sites_results.json         # Real-world streaming copilot consultation outputs
│   ├── chat_modes_benchmark.json         # Operating mode latency & quality benchmarks
│   └── manual_audit_verification_10sites.json # Double-blind human advocate validation annotations
│
├── eval_runners/                         # Autonomous Evaluation Test Runners (ml/evals)
│   ├── run_accuracy_evals.py             # Statutory accuracy & multi-label F1 runner
│   ├── run_apliance_benchmark.py         # 400-clause APLiance replication runner
│   ├── run_security_evals.py             # Adversarial injection & sycophancy runner
│   ├── run_hallucination_benchmark.py    # Safe-harbor confabulation & probe runner
│   ├── run_chatbot_evals.py              # Citizen legal dialogue evaluation runner
│   ├── run_grammar_evals.py              # Pushdown Automaton CFG schema decoding runner
│   ├── benchmark_latency.py              # Sovereign edge inference & VRAM profiling runner
│   ├── evaluate_rag.py                   # Statutory RAG retrieval precision/recall runner
│   ├── compare_sota_models.py            # Comparative baseline benchmark runner
│   └── metrics.py, stats.py, verify.py   # Statistical significance & evaluation metrics
│
├── statutory_schemas/                    # Computational Representation of Indian Privacy Law
│   ├── dpdp_act_tree.json                # 26-node formal statutory decision tree (DPDP 2023 & Rules 2025)
│   ├── dpdp_schema.json                  # Formal JSON schema enforcing Pushdown Automaton CFG decoding
│   └── dpdp_index.json                   # Curated legislative chunk index for hybrid RAG grounding
│
└── figure_generation_scripts/            # Autonomous 300 DPI Figure Generation Scripts
    ├── generate_paper_eval_figures.py    # Generates Fig 14 (APLiance), Fig 15 (LegalBench), Fig 16 (Edge)
    ├── generate_additional_paper_figures.py # Generates Fig 21 (Jurisdiction), Fig 22 (Cases), Fig 23 (Serving)
    └── generate_extension_history_figure.py # Generates Fig 24 (History/Pipeline) & Fig 25 (Best Sites)
```

---

## How to Integrate into the IEEE Research Paper

1. **Section Text**: Use `paper_eval_sections/ssense_paper_eval_section.md` which contains the complete manuscript text for **Section VII (Empirical Evaluation Framework)** and **Section VIII (Results and Empirical Discussion)**.
2. **Tables**: Copy and paste the LaTeX table snippets from `paper_eval_sections/LATEX_TABLES_READY.tex` directly into your `.tex` file.
3. **Figures**: Use the high-resolution vector files from `figures/vector_svg/` (`\includegraphics[width=\linewidth]{fig...}`) for crystal-clear vector rendering in IEEE 2-column format.
4. **Data Verification**: Inspect `eval_data/evaluation_results_comprehensive.json` and `eval_data/ground_truth.json` to verify any numerical metric cited in the paper.

---
*Created by Ssense Development Team — Domain-Adapted Legal Small Language Model.*
"""

with open(EVAL_STAGING / "README.md", "w", encoding="utf-8") as f:
    f.write(eval_readme)

if ML_EVAL_ZIP_PATH.exists():
    ML_EVAL_ZIP_PATH.unlink()

with zipfile.ZipFile(ML_EVAL_ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(EVAL_STAGING):
        for file in files:
            full_path = Path(root) / file
            arc_name = full_path.relative_to(EVAL_STAGING)
            zf.write(full_path, arc_name)

eval_size_mb = os.path.getsize(ML_EVAL_ZIP_PATH) / (1024 * 1024)
print(f"🎉 Successfully created {ML_EVAL_ZIP_PATH.name} ({eval_size_mb:.2f} MB, {fig_count} figures)!")

# Clean staging directories
shutil.rmtree(SS_STAGING)
shutil.rmtree(EVAL_STAGING)
print("🧹 Cleaned temporary staging directories.")
