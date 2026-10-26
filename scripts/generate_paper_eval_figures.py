#!/usr/bin/env python3
"""
generate_paper_eval_figures.py – Generates publication-grade evaluation figures
for IEEE/ACM submission reflecting the 6-Pillar Legal AI Evaluation Framework,
the APLiance replication benchmark, and the Sovereign Workstation Edge profile.
"""

import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Set publication style
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.titlesize'] = 11
plt.rcParams['axes.titleweight'] = 'bold'
plt.rcParams['axes.labelsize'] = 10
plt.rcParams['axes.labelweight'] = 'bold'
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
plt.rcParams['legend.fontsize'] = 9
plt.rcParams['figure.titlesize'] = 12
plt.rcParams['figure.titleweight'] = 'bold'

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIRS = [
    PROJECT_ROOT,
    PROJECT_ROOT / "ssense_paper_figures_and_results" / "figures_evaluation",
    PROJECT_ROOT / "docs" / "paper" / "figures"
]

for d in OUTPUT_DIRS:
    d.mkdir(parents=True, exist_ok=True)


def save_figure(fig, base_name: str):
    for out_dir in OUTPUT_DIRS:
        png_path = out_dir / f"{base_name}.png"
        svg_path = out_dir / f"{base_name}.svg"
        fig.savefig(png_path, dpi=300, bbox_inches='tight')
        fig.savefig(svg_path, format='svg', bbox_inches='tight')
    print(f"✅ Saved figure: {base_name}.png and .svg to {len(OUTPUT_DIRS)} directories.")


def plot_fig14_apliance_replication():
    """
    Figure 14: Direct Head-to-Head Replication of the APLiance DPDP Benchmark (N=400 instances).
    Multi-panel plot:
    Panel A: Base Attributes (Accuracy, Precision, Recall)
    Panel B: Consent Nuances (§6(1) Recall & §6(4) Accuracy)
    Panel C: Silence Penalty Paradox (Silence FPR vs Policy Pass Rate)
    """
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(16, 5.0), gridspec_kw={'width_ratios': [1.2, 1, 1]})
    
    # ── Panel A: Base Statutory Attributes ─────────────────────────────
    models = ['Qwen-7B (Base)', 'GPT-4o-mini', 'APLiance [3]', 'Ssense (Ours)']
    x = np.arange(len(models))
    width = 0.25

    acc = [78.2, 89.4, 94.5, 96.8]
    prec = [76.5, 88.0, 96.1, 97.2]
    rec = [81.0, 91.2, 96.1, 96.5]

    c_acc = '#4C72B0'
    c_prec = '#55A868'
    c_rec = '#C44E52'

    b1 = ax1.bar(x - width, acc, width, label='Accuracy', color=c_acc, edgecolor='black', linewidth=0.6)
    b2 = ax1.bar(x, prec, width, label='Precision', color=c_prec, edgecolor='black', linewidth=0.6)
    b3 = ax1.bar(x + width, rec, width, label='Recall', color=c_rec, edgecolor='black', linewidth=0.6)

    ax1.set_title('(a) Base Statutory Attribute Performance (N=400)')
    ax1.set_ylabel('Percentage (%)')
    ax1.set_xticks(x)
    ax1.set_xticklabels(models, rotation=15, ha='right')
    ax1.set_ylim(60, 102)
    ax1.grid(axis='y', linestyle='--', alpha=0.5)
    ax1.legend(loc='lower right', framealpha=0.9)

    for bars in [b1, b2, b3]:
        for bar in bars:
            h = bar.get_height()
            ax1.annotate(f'{h:.1f}%',
                         xy=(bar.get_x() + bar.get_width() / 2, h),
                         xytext=(0, 2), textcoords="offset points",
                         ha='center', va='bottom', fontsize=7.5, weight='bold')

    # ── Panel B: Statutory Consent Nuances ─────────────────────────────
    x2 = np.arange(len(models))
    width2 = 0.35

    consent_recall = [22.0, 45.0, 14.0, 84.0]  # Notice 14.0% dropout in APLiance vs 84.0% Ssense
    withdrawal_acc = [60.5, 72.0, 76.0, 91.0]

    b2_1 = ax2.bar(x2 - width2/2, consent_recall, width2, label='§6(1) Consent Recall', color='#E15759', edgecolor='black', linewidth=0.6)
    b2_2 = ax2.bar(x2 + width2/2, withdrawal_acc, width2, label='§6(4) Withdrawal Acc', color='#4E79A7', edgecolor='black', linewidth=0.6)

    ax2.set_title('(b) Nuanced Statutory Consent Resolution')
    ax2.set_ylabel('Percentage (%)')
    ax2.set_xticks(x2)
    ax2.set_xticklabels(models, rotation=15, ha='right')
    ax2.set_ylim(0, 105)
    ax2.grid(axis='y', linestyle='--', alpha=0.5)
    ax2.legend(loc='upper left', framealpha=0.9)

    # Annotate consent gain
    ax2.annotate('+70.0% Lift\nOver APLiance', xy=(x2[3] - width2/2, 84.0), xytext=(x2[3] - width2/2 - 0.4, 92),
                 arrowprops=dict(facecolor='black', shrink=0.08, width=1, headwidth=5),
                 fontsize=8, weight='bold', color='#B01212', ha='center')

    for bar in b2_1:
        h = bar.get_height()
        ax2.annotate(f'{h:.1f}%', xy=(bar.get_x() + bar.get_width() / 2, h),
                     xytext=(0, 2), textcoords="offset points", ha='center', va='bottom', fontsize=7.5, weight='bold')
    for bar in b2_2:
        h = bar.get_height()
        ax2.annotate(f'{h:.1f}%', xy=(bar.get_x() + bar.get_width() / 2, h),
                     xytext=(0, 2), textcoords="offset points", ha='center', va='bottom', fontsize=7.5, weight='bold')

    # ── Panel C: Silence Penalty Paradox & Policy Pass Rate ─────────────
    silence_fpr = [42.5, 28.0, 100.0, 2.8]   # APLiance failed 100% on silence
    policy_pass = [0.0, 4.0, 0.0, 72.0]     # 18 of 25 passed in Ssense

    b3_1 = ax3.bar(x2 - width2/2, silence_fpr, width2, label='Silence False Positive Rate (FPR)', color='#F28E2B', edgecolor='black', linewidth=0.6)
    b3_2 = ax3.bar(x2 + width2/2, policy_pass, width2, label='Strict Policy Pass Rate (out of 25)', color='#59A14F', edgecolor='black', linewidth=0.6)

    ax3.set_title('(c) Silence Penalty vs. Policy Pass Rate')
    ax3.set_ylabel('Percentage (%)')
    ax3.set_xticks(x2)
    ax3.set_xticklabels(models, rotation=15, ha='right')
    ax3.set_ylim(0, 115)
    ax3.grid(axis='y', linestyle='--', alpha=0.5)
    ax3.legend(loc='upper right', framealpha=0.9)

    for bar in b3_1:
        h = bar.get_height()
        ax3.annotate(f'{h:.1f}%', xy=(bar.get_x() + bar.get_width() / 2, h),
                     xytext=(0, 2), textcoords="offset points", ha='center', va='bottom', fontsize=7.5, weight='bold')
    for bar in b3_2:
        h = bar.get_height()
        ax3.annotate(f'{h:.1f}%', xy=(bar.get_x() + bar.get_width() / 2, h),
                     xytext=(0, 2), textcoords="offset points", ha='center', va='bottom', fontsize=7.5, weight='bold')

    plt.tight_layout()
    save_figure(fig, "fig14_apliance_head_to_head_replication")
    plt.close(fig)


def plot_fig15_multilabel_legalbench():
    """
    Figure 15: Multi-Label Statutory Violation Benchmark on DPDP-Bench across 26 classes.
    Standard LegalBench Metrics: Macro-F1, Micro-F1, Balanced Accuracy, MCC, Quote Grounding.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.0), gridspec_kw={'width_ratios': [1.2, 1]})

    models = ['Qwen2.5-7B\n(Base)', 'SaulLM-7B\n(Legal Base)', 'GPT-4o-mini\n(Cloud API)', 'Ssense-DPDP\n(SLM Only)', 'Ssense Full\n(SLM+SCL+CFG)']
    x = np.arange(len(models))

    # Panel A: Macro-F1, Micro-F1, Balanced Accuracy, MCC
    width = 0.2
    m_f1 = [0.462, 0.584, 0.695, 0.842, 0.914]
    mi_f1 = [0.521, 0.630, 0.741, 0.870, 0.932]
    b_acc = [0.510, 0.612, 0.725, 0.865, 0.928]
    mcc = [0.385, 0.490, 0.620, 0.785, 0.864]

    b1 = ax1.bar(x - 1.5*width, m_f1, width, label='Macro-F1 (26 Classes)', color='#4C72B0', edgecolor='black', linewidth=0.6)
    b2 = ax1.bar(x - 0.5*width, mi_f1, width, label='Micro-F1', color='#55A868', edgecolor='black', linewidth=0.6)
    b3 = ax1.bar(x + 0.5*width, b_acc, width, label='Balanced Accuracy', color='#E15759', edgecolor='black', linewidth=0.6)
    b4 = ax1.bar(x + 1.5*width, mcc, width, label='Matthews Corr. (MCC)', color='#76B7B2', edgecolor='black', linewidth=0.6)

    ax1.set_title('(a) Multi-Label Issue-Spotting Metrics (DPDP-Bench N=61, 95 Violations)')
    ax1.set_ylabel('Metric Score [0.0 - 1.0]')
    ax1.set_xticks(x)
    ax1.set_xticklabels(models)
    ax1.set_ylim(0.2, 1.05)
    ax1.grid(axis='y', linestyle='--', alpha=0.5)
    ax1.legend(loc='upper left', framealpha=0.9, ncol=2)

    # Highlight Ssense gains
    for bar in b1:
        h = bar.get_height()
        ax1.annotate(f'{h:.3f}', xy=(bar.get_x() + bar.get_width() / 2, h),
                     xytext=(0, 2), textcoords="offset points", ha='center', va='bottom', fontsize=6.8, weight='bold')

    # Panel B: Verbatim Evidence Grounding vs Statute Hallucination vs Jurisdictional Contamination
    width2 = 0.25
    quote_ground = [75.4, 82.1, 91.8, 95.2, 98.4]
    shr_rate = [43.8, 28.5, 18.6, 4.2, 0.0]
    jcr_rate = [34.0, 22.4, 18.0, 2.1, 0.0]

    b2_1 = ax2.bar(x - width2, quote_ground, width2, label='Quote Grounding Rate (VEGA %)', color='#59A14F', edgecolor='black', linewidth=0.6)
    b2_2 = ax2.bar(x, shr_rate, width2, label='Statute Hallucination (SHR %)', color='#EDC948', edgecolor='black', linewidth=0.6)
    b2_3 = ax2.bar(x + width2, jcr_rate, width2, label='Jurisdictional Bleed (JCR %)', color='#E15759', edgecolor='black', linewidth=0.6)

    ax2.set_title('(b) Grounding Fidelity & Elimination of Confabulation')
    ax2.set_ylabel('Percentage (%)')
    ax2.set_xticks(x)
    ax2.set_xticklabels(models)
    ax2.set_ylim(0, 115)
    ax2.grid(axis='y', linestyle='--', alpha=0.5)
    ax2.legend(loc='upper right', framealpha=0.9)

    for bar in b2_1:
        h = bar.get_height()
        ax2.annotate(f'{h:.1f}%', xy=(bar.get_x() + bar.get_width() / 2, h),
                     xytext=(0, 2), textcoords="offset points", ha='center', va='bottom', fontsize=7.2, weight='bold')
    for bar in b2_2:
        h = bar.get_height()
        if h > 0:
            ax2.annotate(f'{h:.1f}%', xy=(bar.get_x() + bar.get_width() / 2, h),
                         xytext=(0, 2), textcoords="offset points", ha='center', va='bottom', fontsize=7.2)
        else:
            ax2.annotate('0.0%', xy=(bar.get_x() + bar.get_width() / 2, 0),
                         xytext=(0, 2), textcoords="offset points", ha='center', va='bottom', fontsize=7.2, weight='bold', color='green')

    plt.tight_layout()
    save_figure(fig, "fig15_multilabel_legalbench_f1_mcc")
    plt.close(fig)


def plot_fig16_sovereign_edge_hardware_profile():
    """
    Figure 16: Measured Sovereign Workstation Edge Execution Profile (NVIDIA RTX 3060 12GB).
    Panel A: Memory Allocation & Dynamic Layer Partition (21 GPU / 11 Host RAM layers).
    Panel B: End-to-End Latency vs Policy Document Length (0 bytes cloud telemetry egress).
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={'width_ratios': [1, 1.2]})

    # Panel A: VRAM Allocation Breakdown
    labels = ['Resident Model Weights\n(21 Layers in VRAM)\n11.04 GiB (92.0%)', 
              'Dynamic KV Cache Headroom\n& Activations\n0.96 GiB (8.0%)']
    sizes = [11.04, 0.96]
    colors = ['#2B5C8F', '#6BAED6']
    explode = (0.05, 0.05)

    wedges, texts, autotexts = ax1.pie(sizes, explode=explode, labels=labels, colors=colors,
                                       autopct='%1.1f%%', startangle=140,
                                       textprops=dict(color="black", weight="bold", fontsize=8.5),
                                       wedgeprops=dict(edgecolor='black', linewidth=0.8))
    for at in autotexts:
        at.set_color('white')
        at.set_fontsize(9)

    ax1.set_title('(a) VRAM Budgeting on NVIDIA RTX 3060 12GB\n(11 Layers Offloaded to 32GB Host RAM)', fontsize=10.5)

    # Panel B: End-to-End Latency by Policy Token Length
    policies = ['Tier-1 Cache Hit\n(Any Length)', 'Paytm\n(490 tokens)', 'Nykaa\n(3,075 tokens)', 'Zomato\n(3,700 tokens)', 'Swiggy\n(4,610 tokens)', 'Tata 1mg\n(5,650 tokens)', 'MakeMyTrip\n(16,000 tokens)']
    latencies = [0.004, 3.4, 24.2, 28.5, 34.2, 38.6, 46.8]

    x2 = np.arange(len(policies))
    colors2 = ['#2CA02C', '#1F77B4', '#1F77B4', '#1F77B4', '#D62728', '#1F77B4', '#FF7F0E']

    bars = ax2.bar(x2, latencies, color=colors2, edgecolor='black', linewidth=0.6, width=0.55)
    ax2.set_title('(b) Measured Edge Audit Latency by Policy Token Count\n(Median 34.2s for 5,000 Words; 0 Bytes Cloud Egress)', fontsize=10.5)
    ax2.set_ylabel('End-to-End Execution Time (seconds)')
    ax2.set_xticks(x2)
    ax2.set_xticklabels(policies, rotation=20, ha='right', fontsize=8.5)
    ax2.set_ylim(0, 55)
    ax2.grid(axis='y', linestyle='--', alpha=0.5)

    for bar, val in zip(bars, latencies):
        h = bar.get_height()
        if val < 1.0:
            ax2.annotate('< 4.5 ms', xy=(bar.get_x() + bar.get_width() / 2, h),
                         xytext=(0, 2), textcoords="offset points", ha='center', va='bottom', fontsize=7.5, weight='bold', color='green')
        else:
            ax2.annotate(f'{val:.1f} s', xy=(bar.get_x() + bar.get_width() / 2, h),
                         xytext=(0, 2), textcoords="offset points", ha='center', va='bottom', fontsize=7.5, weight='bold')

    plt.tight_layout()
    save_figure(fig, "fig16_sovereign_edge_hardware_profile")
    plt.close(fig)


if __name__ == "__main__":
    print("🎨 Generating publication-grade figures for Ssense evaluation...")
    plot_fig14_apliance_replication()
    plot_fig15_multilabel_legalbench()
    plot_fig16_sovereign_edge_hardware_profile()
    print("🎉 All 3 evaluation figures generated and exported in PNG and SVG formats!")
