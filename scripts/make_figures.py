#!/usr/bin/env python
"""make_figures.py — 论文图表定稿 v2（TODO-5.1 版式修订，JOMS/Springer 双栏 183mm）

版式规范（scientific-visualization skill）：
- 物理尺寸统一：双栏宽 7.2 in（183 mm），constrained_layout，不用 bbox_inches="tight"
  （保持页面物理尺寸一致）；
- 600 DPI 线图导出；Okabe-Ito 色板（色觉安全）+ 形状冗余编码；
- 字号按最终印刷尺寸设定（基准 8 pt，最小注记 6.5 pt）；
- 标签避让：图例一律出数据区，参考线标签置于图内左上，逐一目检。
冻结来源不变：全部数字只读自 results/*.csv；参照线 = 0.90 名义 / 0.80 pre-specified
operational audit threshold / 库内 AUC 参照（CHG-P1：LR 0.7868 / LGBM 0.7257）。
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

FIG = Path("figures")
AUC_REF = {"lr": 0.7868, "lgbm": 0.7257}  # CHG-P1 冻结库内参照
C = {"lr": "#3C5488", "lgbm": "#E64B35"}  # NPG deep blue / NPG red
PAL = {"red": "#E64B35", "lblue": "#4DBBD5", "teal": "#00A087",
       "nblue": "#3C5488", "salmon": "#F39B7F", "purple": "#8491B4"}
DIR3 = {"tappy2mit": "Tappy→MIT", "mit2tappy": "MIT→Tappy",
        "gold_merged2self": "Clinical→Self-report"}
SHORT = {"tappy2mit": "T→M", "mit2tappy": "M→T", "tappy2oe": "T→O", "oe2tappy": "O→T",
         "mit2oe": "M→O", "oe2mit": "O→M", "typd2mit": "Y→M", "mit2typd": "M→Y",
         "typd2tappy": "Y→T", "tappy2typd": "T→Y", "typd2oe": "Y→O", "oe2typd": "O→Y"}

plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7,
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 600, "savefig.dpi": 600, "axes.linewidth": 0.7,
})


def fig1_forest() -> None:
    pf = pd.read_csv("results/primary_family.csv")
    fig, ax = plt.subplots(figsize=(7.2, 3.1), layout="constrained")
    groups = list(pf["direction"].unique())
    for i, direction in enumerate(groups):
        for j, model in enumerate(("lr", "lgbm")):
            r = pf[(pf["direction"] == direction) & (pf["model"] == model)].iloc[0]
            y = i + (0.32 if model == "lr" else -0.32)
            ax.errorbar(r["coverage"], y, xerr=[[r["coverage"] - r["ci_lo"]],
                        [r["ci_hi"] - r["coverage"]]], fmt="o", color=C[model],
                        capsize=2.5, ms=4.5, lw=1.1)
            ax.annotate(f"{int(r['k'])}/{int(r['n'])}", (r["ci_hi"], y),
                        xytext=(4, -2.5), textcoords="offset points", fontsize=6.5,
                        color=C[model])
    for i, direction in enumerate(groups):
        ax.axhline(i, color="#dddddd", lw=0.5, zorder=0)
    ax.axvline(0.90, color="grey", ls="--", lw=0.8)
    ax.axvline(0.80, color="grey", ls=":", lw=0.8)
    ax.annotate("nominal 0.90", (0.90, 1.0), xycoords=("data", "axes fraction"),
                xytext=(2, 3), textcoords="offset points", fontsize=6.5, color="grey",
                ha="left")
    ax.annotate("audit 0.80 (pre-specified)", (0.80, 1.0), xycoords=("data", "axes fraction"),
                xytext=(-2, 3), textcoords="offset points", fontsize=6.5, color="grey",
                ha="right")
    ax.set_yticks(range(len(groups)))
    ax.set_yticklabels([DIR3[d] for d in groups])
    ax.invert_yaxis()
    ax.set_ylim(2.62, -0.62)
    ax.set_xlabel("Coverage on target cohort (Clopper-Pearson 95% CI)")
    ax.set_xlim(0.3, 1.06)
    ax.scatter([], [], color=C["lr"], label="LR (primary reference)")
    ax.scatter([], [], color=C["lgbm"], label="LGBM (comparator)")
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=7,
              frameon=False)
    fig.savefig(FIG / "fig1_primary_forest.png")
    plt.close(fig)


def fig2_class_conditional() -> None:
    cc = pd.read_csv("results/class_conditional_coverage.csv")
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), sharey=True,
                             layout="constrained")
    for ax, model in zip(axes, ("lr", "lgbm")):
        sub = cc[cc["model"] == model]
        xs = np.arange(len(sub))
        for k, (cls, color, marker) in enumerate((("pd", "#B24745", "s"),
                                                  ("hc", "#374E55", "o"))):
            cov = sub[f"coverage_cls_{cls}"]
            lo, hi = sub[f"ci_lo_cls_{cls}"], sub[f"ci_hi_cls_{cls}"]
            ax.errorbar(xs + (k - 0.5) * 0.3, cov, yerr=[cov - lo, hi - cov],
                        fmt=marker, color=color, capsize=2.5, ms=4.5, lw=1.1,
                        label=cls.upper())
            for x, l, n in zip(xs, lo, sub[f"n_cls_{cls}"]):
                dy = -22 if l > 0.87 else -10  # 近 0.90 线的层加大下移,防穿线
                ax.annotate(f"n={int(n)}", (x + (k - 0.5) * 0.3, l),
                            xytext=(0, dy), textcoords="offset points",
                            fontsize=6.2, ha="center", color=color,
                            bbox=dict(fc="white", ec="none", alpha=0.85, pad=0.6))
        ax.axhline(0.90, color="grey", ls="--", lw=0.8)
        ax.axhline(0.80, color="grey", ls=":", lw=0.8)
        ax.set_xticks(xs)
        ax.set_xticklabels([DIR3[d] for d in sub["direction"]], fontsize=7)
        ax.set_title({"lr": "LR (primary reference)",
                      "lgbm": "LGBM (comparator)"}[model])
        ax.set_ylim(0, 1.04)
        ax.tick_params(axis="y", which="minor", left=False)
        if model != "lr":
            ax.tick_params(axis="y", which="major", left=False)
    axes[0].set_ylabel("Class-conditional coverage")
    axes[1].legend(loc="lower right", fontsize=7, frameon=False)
    fig.savefig(FIG / "fig2_class_conditional.png")
    plt.close(fig)


def fig3_decoupling() -> None:
    tm = pd.read_csv("results/transfer_matrix.csv")
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.4), sharex=True, sharey=True,
                             layout="constrained")
    offs = {"gold_merged2self": (4, -9), "mit2typd": (7, -12),
            "typd2mit": (7, -12), "oe2mit": (7, -12), "mit2oe": (5, -10),
            "oe2typd": (4, -9)}
    for ax, model in zip(axes, ("lr", "lgbm")):
        d_a = tm["auc_mean"] - AUC_REF[model]
        d_c = tm["coverage_mean"] - 0.90
        ax.axhline(0, color="grey", ls="--", lw=0.8)
        ax.axvline(0, color="grey", ls="--", lw=0.8)
        ax.scatter(d_a, d_c, s=20, color={"lr": "#3B4992", "lgbm": "#EE0000"}[model],
                   alpha=0.9)
        for da, dc, name in zip(d_a, d_c, tm["direction"]):
            dx, dy = offs.get(name, (4, 3))
            ha = "right" if dx < 0 else "left"
            ax.annotate(SHORT.get(name, name), (da, dc), xytext=(dx, dy),
                        textcoords="offset points", fontsize=6, ha=ha)
        ax.set_title({"lr": "LR (primary reference)",
                      "lgbm": "LGBM (comparator)"}[model])
        ax.set_xlabel("ΔAUC vs in-domain reference")
        ax.set_xlim(-0.29, 0.13)
    axes[0].set_ylabel("ΔCoverage vs nominal 0.90\n(50-seed mean)")
    fig.savefig(FIG / "fig3_decoupling.png")
    plt.close(fig)


def fig4_recovery_cost() -> None:
    rc = pd.read_csv("results/recovery_cost_table.csv")
    fig, ax = plt.subplots(figsize=(7.2, 3.6), layout="constrained")
    colors = {"tappy2mit": "#ED0000", "mit2tappy": "#00468B", "gold_merged2self": "#42B540"}
    for direction, color in colors.items():
        sub = rc[(rc["direction"] == direction) & (rc["method"] == "target_recalib")]
        nd = sub[~sub["qhat_inf"]].sort_values("n_target_labels")
        ax.plot(nd["n_target_labels"], nd["coverage"], "o-", color=color, ms=3.5,
                lw=1.1, label=DIR3[direction], markeredgecolor="white",
                markeredgewidth=1.0, zorder=3)
        deg = sub[sub["qhat_inf"]]
        if len(deg):
            ax.scatter(deg["n_target_labels"], deg["coverage"], facecolors="none",
                       edgecolors=color, s=38, ls="--", lw=1.0)
        w = rc[(rc["direction"] == direction) & (rc["method"] == "weighted_cp")].iloc[0]
        ax.scatter(w["n_target_labels"], w["coverage"], marker="*", s=60, color=color,
                   edgecolors="black", linewidths=0.4, zorder=5)
    ax.axhline(0.80, color="grey", ls=":", lw=0.9)
    ax.axhline(0.90, color="grey", ls="--", lw=0.8)
    ax.text(-2.5, 0.9065, "nominal 0.90", fontsize=6.5, color="grey", ha="left")
    ax.text(0.995, 0.7965, "audit 0.80 (pre-specified)", fontsize=6.5, color="grey",
            transform=ax.get_yaxis_transform(), ha="right", va="top")
    ax.set_xlabel("Target-domain labeled subjects used for recalibration")
    ax.set_ylabel("Overall coverage on held-out\ntarget subjects")
    ax.set_ylim(0.78, 1.015)
    ax.set_xlim(-4, 120)
    ax.legend(loc="upper right", fontsize=7, frameon=False)
    fig.savefig(FIG / "fig4_recovery_cost.png")
    plt.close(fig)


def fig5_weighted_cp_tradeoff() -> None:
    cc = pd.read_csv("results/calibration_comparison.csv")
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9), layout="constrained")
    dirs = ["tappy2mit", "mit2tappy", "gold_merged2self"]
    labels = [DIR3[d] for d in dirs]
    naive = [cc[(cc["direction"] == d) & (cc["method"] == "gold_direct")].iloc[0] for d in dirs]
    wcp = [cc[(cc["direction"] == d) & (cc["method"] == "weighted_cp")].iloc[0] for d in dirs]
    x = np.arange(len(dirs))
    w = 0.36
    for ax, key, ylab in ((axes[0], "coverage", "Coverage on held-out\ntarget subjects"),
                          (axes[1], "rejection_rate", "Rejection (abstention) rate")):
        ax.bar(x - w / 2, [m[key] for m in naive], w, color="#374E55",
               label="Naive split CP", edgecolor="white", lw=0.5)
        ax.bar(x + w / 2, [m[key] for m in wcp], w, color="#DF8F44",
               label="Weighted CP (0 labels)", edgecolor="white", lw=0.5)
        ax.set_xticks(x, labels, fontsize=7)
        ax.set_ylim(0, 1.09)
        ax.set_ylabel(ylab)
        ax.set_xlabel("Transfer direction")
    axes[0].axhline(0.90, color="grey", ls="--", lw=0.8)
    axes[0].axhline(0.80, color="grey", ls=":", lw=0.9)
    axes[0].set_ylim(0.45, 1.09)
    for xi, m in zip(x - w / 2, naive):
        axes[0].text(xi, m["coverage"] + 0.015, f'{m["coverage"]:.2f}', ha="center",
                     fontsize=6, color="#374E55")
    for xi, m in zip(x + w / 2, wcp):
        axes[1].text(xi, m["rejection_rate"] + 0.02, f'{m["rejection_rate"]:.2f}',
                     ha="center", fontsize=6, color="#DF8F44")
    from matplotlib.lines import Line2D
    handles, labels_ = axes[0].get_legend_handles_labels()
    handles += [Line2D([0], [0], color="grey", ls="--", lw=0.8),
                Line2D([0], [0], color="grey", ls=":", lw=0.9)]
    labels_ += ["nominal 0.90", "audit 0.80 (pre-specified)"]
    fig.legend(handles, labels_, loc="outside upper center", ncols=4, fontsize=6.5,
               frameon=False)
    fig.savefig(FIG / "fig5_weighted_cp_tradeoff.png")
    plt.close(fig)


def fig6_stress_tests() -> None:
    st = pd.read_csv("results/stress_test_a.csv")
    ta = pd.read_csv("results/three_arm_stress_test.csv")
    fig = plt.figure(figsize=(7.2, 5.6), layout="constrained")
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.0])
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1], sharey=ax_a)
    ax_c = fig.add_subplot(gs[1, :])
    arm_color = {"PD2HC": "#3B4992", "HC2PD": "#EE0000", "symmetric": "#008280"}
    arm_style = {"PD2HC": "-", "HC2PD": "--", "symmetric": "-."}
    base = st[(st["arm"] == "none")]["coverage"].iloc[0]
    for ax, scope, title in ((ax_a, "cal_only", "A  Calibration-only flip (theory-aligned)"),
                             (ax_b, "train_cal", "B  Train+calibration flip (deployment)")):
        for arm, color in arm_color.items():
            sub = st[(st["arm"] == arm) & (st["scope"] == scope)].sort_values("dose_pct")
            ax.plot([0] + sub["dose_pct"].tolist(), [base] + sub["coverage"].tolist(),
                    arm_style[arm], marker="o", color=color, ms=4, lw=1.1, label=arm,
                    markeredgecolor="white", markeredgewidth=1.0)
        ax.axhline(0.90, color="grey", ls="--", lw=0.8)
        ax.set_title(title, fontsize=8, loc="left")
        ax.set_xlabel("Flip dose (% of donor class)")
        ax.set_ylim(0.79, 1.01)
        ax.set_xticks([0, 10, 20, 30])
    ax_a.set_ylabel("Overall coverage on Tappy target")
    ax_a.annotate("nominal 0.90", (28, 0.904), fontsize=6.5, color="grey", ha="right")
    handles, labels = ax_a.get_legend_handles_labels()
    ax_a.legend(handles, labels, loc="lower left", fontsize=6.5, frameon=True,
                framealpha=1.0, edgecolor="none")

    groups = [("Observed\n(MIT→Tappy)", ta[ta["arm"] == "baseline"].iloc[0]),
              ("Prevalence\nre-matching", ta[(ta["arm"] == "resample_only")].iloc[0]),
              ("Prevalence-preserving\nflips", ta[(ta["arm"] == "flip_only") &
                                                  (ta["scope"] == "train_cal")].iloc[0]),
              ("Combination", ta[(ta["arm"] == "both") &
                                 (ta["scope"] == "train_cal")].iloc[0])]
    x = np.arange(len(groups))
    w = 0.36
    obs_pd = groups[0][1]["cpc_pd"]
    obs_hc = groups[0][1]["cpc_hc"]
    ax_c.axhspan(obs_pd - 0.05, obs_pd + 0.05, color="#3B4992", alpha=0.10, zorder=0)
    ax_c.axhspan(obs_hc - 0.05, obs_hc + 0.05, color="#EE0000", alpha=0.10, zorder=0)
    ax_c.bar(x - w / 2, [g[1]["cpc_pd"] for g in groups], w, color="#3B4992",
             label="PD-conditional", edgecolor="white", lw=0.5, zorder=2)
    ax_c.bar(x + w / 2, [g[1]["cpc_hc"] for g in groups], w, color="#EE0000",
             label="HC-conditional", edgecolor="white", lw=0.5, zorder=2)
    for xi, g in zip(x + w / 2, groups):
        ax_c.text(xi, g[1]["cpc_hc"] + 0.02, f'{g[1]["cpc_hc"]:.3f}',
                  ha="center", fontsize=6, color="#EE0000")
    ax_c.set_xticks(x, [g[0] for g in groups], fontsize=7)
    ax_c.set_ylim(0, 1.09)
    ax_c.set_ylabel("Class-conditional coverage")
    ax_c.set_xlabel("C  Three-arm real-transfer test (shaded = pre-specified ±5 pp "
                    "practical-equivalence tolerance; not a CI)", fontsize=8, loc="left")
    ax_c.legend(loc="lower left", bbox_to_anchor=(0.0, 1.01), ncols=2, frameon=False,
                fontsize=6.5)
    fig.savefig(FIG / "fig6_stress_tests.png")
    plt.close(fig)


def main() -> None:
    FIG.mkdir(exist_ok=True)
    for f in (fig1_forest, fig2_class_conditional, fig3_decoupling,
              fig4_recovery_cost, fig5_weighted_cp_tradeoff, fig6_stress_tests):
        f()
        print(f"[ok] {f.__name__}")
    print("→ figures/fig1..fig6.png (600 DPI, 183 mm double-column width)")


if __name__ == "__main__":
    main()
