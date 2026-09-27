#!/usr/bin/env python
"""make_figures.py — 论文图表定稿（TODO-5.1，Phase 5 首项）

冻结来源：全部数字只读自 results/*.csv（审计门：图表数字与 results/ 一致由
subagent 逐项核对）；参照线 = 0.90 名义覆盖、0.80 pre-specified operational
audit threshold、库内 AUC 参照（CHG-P1 冻结值：LR 0.7868 / LGBM 0.7257）。
故事线（用户 2026-09-27 确认）：解耦图谱——fig3 为主图。
输出：figures/fig1..fig5.png（300 DPI）
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
C = {"lr": "#0072B2", "lgbm": "#D55E00"}
DIR_LABEL = {"tappy2mit": "Tappy→MIT", "mit2tappy": "MIT→Tappy",
             "gold_merged2self": "Clinical→Self-report"}

plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 300, "savefig.bbox": "tight"})


def fig1_forest() -> None:
    pf = pd.read_csv("results/primary_family.csv")
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    ys, ylabels = [], []
    for i, direction in enumerate(pf["direction"].unique()):
        for j, model in enumerate(("lr", "lgbm")):
            r = pf[(pf["direction"] == direction) & (pf["model"] == model)].iloc[0]
            y = i * 10 + (3 if model == "lr" else -3)
            ax.errorbar(r["coverage"], y, xerr=[[r["coverage"] - r["ci_lo"]],
                        [r["ci_hi"] - r["coverage"]]], fmt="o", color=C[model],
                        capsize=3, ms=5)
            ys.append(y)
            ax.annotate(f"K={int(r['k'])}/{int(r['n'])}", (r["ci_hi"], y),
                        xytext=(4, -3), textcoords="offset points", fontsize=7,
                        color=C[model])
        ylabels.append((i * 10, DIR_LABEL[direction]))
    ax.axvline(0.90, color="grey", ls="--", lw=0.8)
    ax.axvline(0.80, color="grey", ls=":", lw=0.8)
    ax.text(0.90, ax.get_ylim()[1], " nominal 0.90", fontsize=7, color="grey")
    ax.text(0.80, ax.get_ylim()[1], " audit 0.80", fontsize=7, color="grey")
    ax.set_yticks([y for y, _ in ylabels])
    ax.set_yticklabels([t for _, t in ylabels])
    ax.invert_yaxis()
    ax.set_xlabel("Coverage on target cohort (Clopper-Pearson 95% CI)")
    ax.set_xlim(0.3, 1.05)
    ax.scatter([], [], color=C["lr"], label="LR (primary reference)")
    ax.scatter([], [], color=C["lgbm"], label="LGBM (comparator, DEC-T1)")
    ax.legend(loc="lower right", fontsize=7, frameon=False)
    fig.savefig(FIG / "fig1_primary_forest.png")
    plt.close(fig)


def fig2_class_conditional() -> None:
    cc = pd.read_csv("results/class_conditional_coverage.csv")
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.0), sharey=True)
    for ax, model in zip(axes, ("lr", "lgbm")):
        sub = cc[cc["model"] == model]
        xs = np.arange(len(sub))
        for k, (cls, color) in enumerate((("pd", "#0072B2"), ("hc", "#E69F00"))):
            cov = sub[f"coverage_cls_{cls}"]
            lo, hi = sub[f"ci_lo_cls_{cls}"], sub[f"ci_hi_cls_{cls}"]
            ax.errorbar(xs + (k - 0.5) * 0.32, cov,
                        yerr=[cov - lo, hi - cov], fmt="s", color=color,
                        capsize=3, ms=5, label=cls.upper())
            for x, c, l, h, n in zip(xs, cov, lo, hi, sub[f"n_cls_{cls}"]):
                ax.annotate(f"{int(n)}", (x + (k - 0.5) * 0.32, l),
                            xytext=(0, -11), textcoords="offset points",
                            fontsize=6.5, ha="center", color=color)
        ax.axhline(0.90, color="grey", ls="--", lw=0.8)
        ax.axhline(0.80, color="grey", ls=":", lw=0.8)
        ax.set_xticks(xs)
        ax.set_xticklabels([DIR_LABEL[d] for d in sub["direction"]], fontsize=7.5)
        ax.set_title({"lr": "LR (primary reference)",
                      "lgbm": "LGBM (comparator)"}[model], fontsize=9)
        ax.set_ylim(0, 1.05)
    axes[0].set_ylabel("Class-conditional coverage")
    axes[0].legend(loc="lower left", fontsize=7, frameon=False)
    fig.savefig(FIG / "fig2_class_conditional.png")
    plt.close(fig)


def fig3_decoupling() -> None:
    tm = pd.read_csv("results/transfer_matrix.csv")
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.4), sharex=True, sharey=True)
    for ax, model in zip(axes, ("lr", "lgbm")):
        d_a = tm[f"auc_mean"] - AUC_REF[model]
        d_c = tm["coverage_mean"] - 0.90
        ax.axhline(0, color="grey", ls="--", lw=0.8)
        ax.axvline(0, color="grey", ls="--", lw=0.8)
        ax.scatter(d_a, d_c, s=22, color=C[model], alpha=0.85)
        for da, dc, name in zip(d_a, d_c, tm["direction"]):
            ax.annotate(name, (da, dc), xytext=(3, 3), textcoords="offset points",
                        fontsize=5.6, rotation=38)
        ax.set_title({"lr": "LR (primary reference)",
                      "lgbm": "LGBM (comparator)"}[model], fontsize=9)
        ax.set_xlabel("ΔAUC vs in-domain reference")
    axes[0].set_ylabel("ΔCoverage vs nominal 0.90 (50-seed mean)")
    fig.suptitle("Discrimination and coverage degradation are not the same axis (H1, "
                 "descriptive; no correlation test across 12 non-independent directions)",
                 fontsize=7.5, y=1.02)
    fig.savefig(FIG / "fig3_decoupling.png")
    plt.close(fig)


def fig4_recovery_cost() -> None:
    rc = pd.read_csv("results/recovery_cost_table.csv")
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    colors = {"tappy2mit": "#0072B2", "mit2tappy": "#D55E00", "gold_merged2self": "#009E73"}
    for direction, color in colors.items():
        sub = rc[(rc["direction"] == direction) & (rc["method"] == "target_recalib")]
        nd = sub[~sub["qhat_inf"]]
        ax.plot(nd["n_target_labels"], nd["coverage"], "o-", color=color, ms=4.5,
                label=DIR_LABEL[direction])
        deg = sub[sub["qhat_inf"]]
        if len(deg):
            ax.scatter(deg["n_target_labels"], deg["coverage"], facecolors="none",
                       edgecolors=color, s=42, ls="--")
        w = rc[(rc["direction"] == direction) & (rc["method"] == "weighted_cp")].iloc[0]
        ax.scatter(w["n_target_labels"], w["coverage"], marker="*", s=70, color=color,
                   edgecolors="black", linewidths=0.4, zorder=5)
    ax.axhline(0.80, color="grey", ls=":", lw=0.9)
    ax.text(112, 0.80, " audit 0.80", fontsize=7, color="grey", va="bottom")
    ax.axhline(0.90, color="grey", ls="--", lw=0.8)
    ax.text(112, 0.90, " nominal 0.90", fontsize=7, color="grey", va="bottom")
    ax.set_xlabel("Target-domain labeled subjects used for recalibration")
    ax.set_ylabel("Overall coverage on held-out target subjects")
    ax.legend(loc="lower right", fontsize=7, frameon=False)
    ax.annotate("open marker = degenerate full-set calibration (m<9)\n"
                "star = weighted CP at 0 labels (rejection 0.86–1.00)",
                xy=(0.02, 0.02), xycoords="axes fraction", fontsize=6.2, color="dimgrey")
    fig.savefig(FIG / "fig4_recovery_cost.png")
    plt.close(fig)


def fig5_dose_response() -> None:
    st = pd.read_csv("results/stress_test_a.csv")
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.0), sharey=True)
    arm_color = {"PD2HC": "#0072B2", "HC2PD": "#D55E00", "symmetric": "#009E73"}
    for ax, scope, title in ((axes[0], "cal_only", "Calibration-only flip (theory-aligned)"),
                             (axes[1], "train_cal", "Train+calibration flip (deployment)")):
        for arm, color in arm_color.items():
            sub = st[(st["arm"] == arm) & (st["scope"] == scope)].sort_values("dose_pct")
            base = st[(st["arm"] == "none")]["coverage"].iloc[0]
            ax.plot([0] + sub["dose_pct"].tolist(), [base] + sub["coverage"].tolist(),
                    "o-", color=color, ms=4, label=arm)
        ax.axhline(0.90, color="grey", ls="--", lw=0.8)
        ax.set_title(title, fontsize=8.5)
        ax.set_xlabel("Flip dose (% of donor class)")
        ax.set_ylim(0.55, 1.02)
    axes[0].set_ylabel("Overall coverage on Tappy target")
    axes[0].legend(loc="lower right", fontsize=7, frameon=False)
    fig.savefig(FIG / "fig5_dose_response.png")
    plt.close(fig)


def main() -> None:
    FIG.mkdir(exist_ok=True)
    for f in (fig1_forest, fig2_class_conditional, fig3_decoupling,
              fig4_recovery_cost, fig5_dose_response):
        f()
        print(f"[ok] {f.__name__}")
    print("→ figures/fig1..fig5.png (300 DPI)")


if __name__ == "__main__":
    main()
