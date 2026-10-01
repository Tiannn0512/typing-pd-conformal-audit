#!/usr/bin/env python
"""make_figures.py — 论文图表定稿 v3（配色多样化轮，JOMS/Springer 双栏 183mm）

版式规范（scientific-visualization skill）：
- 物理尺寸统一：双栏宽 7.2 in（183 mm），constrained_layout，不用 bbox_inches="tight"；
- 600 DPI 导出；Arial；白底；去 top/right spine；
- 每图一套独立但同一饱和度家族的配色：
    fig1 森林图   LR #315A86 / LGBM #B86F83（锚定蓝-玫瑰对）
    fig2 类条件   PD #B85C5C / HC #587A9E（暖-冷类对，与 fig6C 类色一致）
    fig3 解耦图   LR #3E8474 / LGBM #8E6C9E（青-梅对）
    fig4 恢复曲线 T→M #C28A3A / M→T #315A86 / C→S #8E6C9E
    fig5 权衡柱   naive #CFCFCF 灰 / weighted #3E8474 青
    fig6 压力测试 arms PD→HC #8E6C9E / HC→PD #C28A3A / symmetric #587A9E；类色同 fig2
    fig7 热图     发散 #B86F83→#D7B4B8→#F2F0EA→#9AAEC2→#315A86（0.4–1.0 定标）
- 参考线统一：0.90 名义 #777777 虚线 / 0.80 预注册审计阈值 #999999 点线；
- 标签避让：图例一律出数据区。
冻结来源不变：全部数字只读自 results/*.csv。
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator

FIG = Path("figures")
AUC_REF = {"lr": 0.7868, "lgbm": 0.7257}  # 冻结结果层库内参照
C1 = {"lr": "#315A86", "lgbm": "#B86F83"}                       # fig1
C2 = {"pd": "#B85C5C", "hc": "#587A9E"}                         # fig2 / fig6C
C3 = {"lr": "#3E8474", "lgbm": "#8E6C9E"}                       # fig3
C4 = {"tappy2mit": "#C28A3A", "mit2tappy": "#315A86",
      "gold_merged2self": "#8E6C9E"}                            # fig4
C5_W = "#3E8474"                                                # fig5 weighted
C6 = {"PD2HC": ("#8E6C9E", "-"), "HC2PD": ("#C28A3A", "--"),
      "symmetric": ("#587A9E", "-.")}                           # fig6 arms
DIR3 = {"tappy2mit": "Tappy\u2192MIT", "mit2tappy": "MIT\u2192Tappy",
        "gold_merged2self": "Clinical\u2192Self-report"}
SHORT = {"tappy2mit": "T\u2192M", "mit2tappy": "M\u2192T", "tappy2oe": "T\u2192O",
         "oe2tappy": "O\u2192T", "mit2oe": "M\u2192O", "oe2mit": "O\u2192M",
         "typd2mit": "Y\u2192M", "mit2typd": "M\u2192Y", "typd2tappy": "Y\u2192T",
         "tappy2typd": "T\u2192Y", "typd2oe": "Y\u2192O", "oe2typd": "O\u2192Y"}

plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7,
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
    "text.color": "#222222", "axes.labelcolor": "#222222",
    "xtick.color": "#222222", "ytick.color": "#222222", "axes.edgecolor": "#222222",
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 600, "savefig.dpi": 600, "axes.linewidth": 0.7,
    "figure.constrained_layout.h_pad": 0.06, "figure.constrained_layout.w_pad": 0.06,
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
                        [r["ci_hi"] - r["coverage"]]], fmt="o", color=C1[model],
                        capsize=2.5, ms=4.5, lw=1.1)
            ax.annotate(f"{int(r['k'])}/{int(r['n'])}", (r["ci_hi"], y),
                        xytext=(4, -2.5), textcoords="offset points", fontsize=6.5,
                        color=C1[model])
    for i, direction in enumerate(groups):
        ax.axhline(i, color="#D9D9D9", lw=0.5, zorder=0)
    ax.axvline(0.90, color="#777777", ls="--", lw=0.8)
    ax.axvline(0.80, color="#999999", ls=":", lw=0.8)
    ax.annotate("nominal 0.90", (0.90, 1.0), xycoords=("data", "axes fraction"),
                xytext=(2, 3), textcoords="offset points", fontsize=6.5, color="#666666",
                ha="left")
    ax.annotate("audit 0.80", (0.80, 1.0), xycoords=("data", "axes fraction"),
                xytext=(-2, 3), textcoords="offset points", fontsize=6.5, color="#666666",
                ha="right")
    ax.set_yticks(range(len(groups)))
    ax.set_yticklabels([DIR3[d] for d in groups])
    ax.invert_yaxis()
    ax.set_ylim(2.62, -0.62)
    ax.set_xlabel("Coverage on target cohort (Clopper-Pearson 95% CI)")
    ax.set_xlim(0.3, 1.06)
    ax.scatter([], [], color=C1["lr"], label="LR")
    ax.scatter([], [], color=C1["lgbm"], label="LGBM")
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
        for k, (cls, marker) in enumerate((("pd", "s"), ("hc", "o"))):
            cov = sub[f"coverage_cls_{cls}"]
            lo, hi = sub[f"ci_lo_cls_{cls}"], sub[f"ci_hi_cls_{cls}"]
            ax.errorbar(xs + (k - 0.5) * 0.3, cov, yerr=[cov - lo, hi - cov],
                        fmt=marker, color=C2[cls], capsize=2.5, ms=4.5, lw=1.1,
                        label=cls.upper())
            for x, l, n in zip(xs, lo, sub[f"n_cls_{cls}"]):
                dy = -22 if l > 0.87 else -10
                ax.annotate(f"n={int(n)}", (x + (k - 0.5) * 0.3, l),
                            xytext=(0, dy), textcoords="offset points",
                            fontsize=6.2, ha="center", color=C2[cls],
                            bbox=dict(fc="white", ec="none", alpha=0.85, pad=0.6))
        ax.axhline(0.90, color="#777777", ls="--", lw=0.8)
        ax.axhline(0.80, color="#999999", ls=":", lw=0.8)
        ax.set_xticks(xs)
        ax.set_xticklabels([DIR3[d] for d in sub["direction"]], fontsize=7)
        ax.set_title({"lr": "LR", "lgbm": "LGBM"}[model])
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
    cols = {"lr": ("auc_mean", "coverage_mean"),
            "lgbm": ("lgbm_auc_mean", "lgbm_coverage_mean")}
    # 两 panel 几何不同，各用一套避让偏移（OE 簇：O→M 与 O→Y 上下错开）
    offs = {
        "lr": {"mit2tappy": (6, 4), "oe2tappy": (6, 4), "tappy2oe": (6, -3),
               "typd2oe": (6, 4), "tappy2typd": (6, 4), "mit2oe": (5, -10),
               "typd2mit": (6, -11), "mit2typd": (6, 4), "oe2mit": (6, 5),
               "oe2typd": (5, -11), "typd2tappy": (5, 6), "tappy2mit": (6, 4)},
        "lgbm": {"mit2tappy": (-8, -9), "tappy2oe": (6, 5), "oe2tappy": (-6, -9),
                 "tappy2mit": (6, 4), "tappy2typd": (6, -10), "typd2oe": (6, 5),
                 "typd2mit": (5, 4), "mit2oe": (5, -10), "mit2typd": (6, 4),
                 "oe2typd": (5, 6), "oe2mit": (6, -10), "typd2tappy": (5, 6)},
    }
    for ax, model in zip(axes, ("lr", "lgbm")):
        auc_col, cov_col = cols[model]
        d_a = tm[auc_col] - AUC_REF[model]
        d_c = tm[cov_col] - 0.90
        ax.axhline(0, color="#999999", ls="--", lw=0.8)
        ax.axvline(0, color="#999999", ls="--", lw=0.8)
        ax.scatter(d_a, d_c, s=20, color=C3[model], alpha=0.9)
        for da, dc, name in zip(d_a, d_c, tm["direction"]):
            dx, dy = offs[model].get(name, (5, 4))
            ha = "right" if dx < 0 else "left"
            # 不加白底衬：会切断 0 参考虚线；偏移已保证标签不压数据点
            ax.annotate(SHORT.get(name, name), (da, dc), xytext=(dx, dy),
                        textcoords="offset points", fontsize=6.5, ha=ha,
                        color="#444444")
        ax.set_title({"lr": "LR", "lgbm": "LGBM"}[model])
        ax.set_xlabel("\u0394AUC vs in-domain reference")
        ax.set_xlim(-0.29, 0.13)
    axes[0].set_ylabel("ΔCoverage vs nominal 0.90")
    fig.savefig(FIG / "fig3_decoupling.png")
    plt.close(fig)


def fig4_recovery_cost() -> None:
    rc = pd.read_csv("results/recovery_cost_table.csv")
    fig, ax = plt.subplots(figsize=(7.2, 3.6), layout="constrained")
    stars = {}
    for direction in C4:
        r = rc[(rc["direction"] == direction) & (rc["method"] == "weighted_cp")].iloc[0]
        stars[direction] = (float(r["n_target_labels"]), float(r["coverage"]))
    # 重合星标横向让位（T→M 与 M→T 的 weighted CP 同为 (0, 1.000)，不挪会互相盖住）
    dup = {}
    for k in set(stars.values()):
        same = [d for d, v in stars.items() if v == k]
        for i, d in enumerate(same):
            if len(same) > 1:
                dup[d] = (i - (len(same) - 1) / 2) * 3.6
    for direction, color in C4.items():
        sub = rc[(rc["direction"] == direction) & (rc["method"] == "target_recalib")]
        nd = sub[~sub["qhat_inf"]].sort_values("n_target_labels")
        ax.plot(nd["n_target_labels"], nd["coverage"], "o-", color=color, ms=4.5,
                lw=1.2, label=DIR3[direction], markeredgecolor="white",
                markeredgewidth=1.0, zorder=3)
        deg = sub[sub["qhat_inf"]]
        if len(deg):
            ax.scatter(deg["n_target_labels"], deg["coverage"], facecolors="none",
                       edgecolors=color, s=38, lw=1.0)
        nx, cov = stars[direction]
        ax.scatter(nx + dup.get(direction, 0.0), cov, marker="*", s=60, color=color,
                   edgecolors="black", linewidths=0.4, zorder=5)
    ax.axhline(0.80, color="#999999", ls=":", lw=0.9)
    ax.axhline(0.90, color="#777777", ls="--", lw=0.8)
    ax.text(-2.5, 0.8975, "nominal 0.90", fontsize=6.5, color="#666666", ha="left",
            va="top")
    ax.text(0.995, 0.7965, "audit 0.80", fontsize=6.5, color="#666666",
            transform=ax.get_yaxis_transform(), ha="right", va="top")
    ax.set_xlabel("Target-domain labeled subjects used for recalibration")
    ax.set_ylabel("Overall coverage on held-out\ntarget subjects")
    ax.set_ylim(0.78, 1.015)
    ax.set_xlim(-4, 120)
    handles, labels_ = ax.get_legend_handles_labels()
    handles += [Line2D([0], [0], marker="*", ls="none", ms=8, mfc="#666666",
                       mec="black", mew=0.4),
                Line2D([0], [0], marker="o", ls="none", ms=6, mfc="none",
                       mec="#666666", mew=1.0)]
    labels_ += ["Weighted CP", r"$\hat{q}\to\infty$ (full set)"]
    ax.legend(handles, labels_, loc="upper right", fontsize=7, frameon=False)
    fig.savefig(FIG / "fig4_recovery_cost.png")
    plt.close(fig)


def fig5_weighted_cp_tradeoff() -> None:
    cc = pd.read_csv("results/calibration_comparison.csv")
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.1), layout="constrained")
    dirs = ["tappy2mit", "mit2tappy", "gold_merged2self"]
    labels = [DIR3[d] for d in dirs]
    naive = [cc[(cc["direction"] == d) & (cc["method"] == "gold_direct")].iloc[0] for d in dirs]
    wcp = [cc[(cc["direction"] == d) & (cc["method"] == "weighted_cp")].iloc[0] for d in dirs]
    x = np.arange(len(dirs))
    w = 0.36
    for ax, key, ylab in ((axes[0], "coverage", "Coverage on held-out target subjects"),
                          (axes[1], "rejection_rate", "Rejection (abstention) rate")):
        ax.bar(x - w / 2, [m[key] for m in naive], w, color="#CFCFCF",
               edgecolor="#999999", lw=0.5, label="Naive split CP")
        ax.bar(x + w / 2, [m[key] for m in wcp], w, color=C5_W,
               edgecolor="white", lw=0.5, label="Weighted CP")
        ax.set_xticks(x, labels, fontsize=7)
        ax.set_ylabel(ylab)
        ax.set_ylim(0, 1.09)
    axes[0].axhline(0.90, color="#777777", ls="--", lw=0.8)
    axes[0].axhline(0.80, color="#999999", ls=":", lw=0.9)
    for xi, m in zip(x - w / 2, naive):
        axes[0].text(xi, m["coverage"] + 0.015, f"{m.coverage:.2f}", ha="center",
                     fontsize=6, color="#444444")
    for xi, m in zip(x + w / 2, wcp):
        axes[1].text(xi, m["rejection_rate"] + 0.02, f"{m.rejection_rate:.2f}",
                     ha="center", fontsize=6, color="#444444")
    handles, labels_ = axes[0].get_legend_handles_labels()
    handles += [Line2D([0], [0], color="#777777", ls="--", lw=0.8),
                Line2D([0], [0], color="#999999", ls=":", lw=0.9)]
    labels_ += ["nominal 0.90", "audit 0.80"]
    fig.legend(handles, labels_, loc="outside upper center", ncols=4, fontsize=6.5,
               frameon=False)
    fig.savefig(FIG / "fig5_weighted_cp_tradeoff.png")
    plt.close(fig)


def fig6_stress_tests() -> None:
    st = pd.read_csv("results/stress_test_a.csv")
    ta = pd.read_csv("results/three_arm_stress_test.csv")
    fig = plt.figure(figsize=(7.2, 8.8), layout="constrained")
    gs = fig.add_gridspec(2, 2)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, :])
    arm_label = {"PD2HC": "PD\u2192HC flip", "HC2PD": "HC\u2192PD flip",
                 "symmetric": "Symmetric flips"}
    base = st[(st["arm"] == "none")]["coverage"].iloc[0]
    for arm, (hue, ls) in C6.items():
        for ax, scope in ((ax_a, "cal_only"), (ax_b, "train_cal")):
            sub = st[(st["arm"] == arm) & (st["scope"] == scope)].sort_values("dose_pct")
            ys = [base] + sub["coverage"].tolist()
            ax.plot([0] + sub["dose_pct"].tolist(), ys, ls, marker="o", color=hue,
                    ms=4, lw=1.2, markeredgecolor="white", markeredgewidth=0.6)
    for ax in (ax_a, ax_b):
        ax.scatter([0], [base], marker="D", s=22, facecolor="#D9D9D9",
                   edgecolor="#999999", linewidths=0.6, zorder=5)
        ax.axhline(0.90, color="#777777", ls="--", lw=0.8)
        ax.set_xlabel("Label-flip dose (% of the flipped class)")
        ax.set_xlim(-2, 32)
        ax.set_xticks([0, 10, 20, 30])
        ax.set_ylim(0.79, 1.01)
        ax.yaxis.set_major_locator(MultipleLocator(0.05))
    ax_a.set_ylabel("Overall coverage on Tappy target")
    for ax in (ax_a, ax_b):
        ax.text(0.5, 0.9045, "nominal 0.90", fontsize=6, color="#666666",
                ha="left", va="bottom")
    proxies = [Line2D([0], [0], color=hue, ls=ls, lw=1.2, marker="o", ms=3.5,
                      markeredgecolor="white") for hue, ls in C6.values()]
    proxies.append(Line2D([0], [0], marker="D", ls="none", markersize=4.5,
                          markerfacecolor="#D9D9D9", markeredgecolor="#999999"))
    fig.legend(proxies, [arm_label[a] for a in C6] + ["Baseline"],
               loc="outside upper center", ncols=4, fontsize=7, frameon=False)
    ax_a.set_title("A  Calibration-only flip")
    ax_b.set_title("B  Train+calibration flip")
    obs = ta[ta["arm"] == "baseline"].iloc[0]
    groups = [("Observed", None, None),
              ("Prevalence re-matching", "resample_only", None),
              ("Prevalence-preserving flips", "flip_only", "train_cal"),
              ("Combination", "both", "train_cal")]

    def _row(g):
        _, arm, scope = g
        if arm is None:
            return obs
        if scope is None:
            return ta[ta["arm"] == arm].iloc[0]
        return ta[(ta["arm"] == arm) & (ta["scope"] == scope)].iloc[0]

    rows = [_row(g) for g in groups]
    ax_c.axhspan(obs["cpc_pd"] - 0.05, obs["cpc_pd"] + 0.05, color="#D9D9D9",
                 alpha=0.35, zorder=0)
    ax_c.axhspan(obs["cpc_hc"] - 0.05, obs["cpc_hc"] + 0.05, color="#D9D9D9",
                 alpha=0.35, zorder=0)
    x = np.arange(len(groups))
    w = 0.36
    ax_c.bar(x - w / 2, [r["cpc_pd"] for r in rows], w, color=C2["pd"],
             label="PD-conditional", edgecolor="white", lw=0.5, zorder=2)
    ax_c.bar(x + w / 2, [r["cpc_hc"] for r in rows], w, color=C2["hc"],
             label="HC-conditional", edgecolor="white", lw=0.5, zorder=2)
    for xi, r in zip(x - w / 2, rows):
        ax_c.text(xi, r["cpc_pd"] + 0.02, f'{r["cpc_pd"]:.3f}', ha="center",
                  fontsize=6.5, color="#444444")
    for xi, r in zip(x + w / 2, rows):
        ax_c.text(xi, r["cpc_hc"] + 0.02, f'{r["cpc_hc"]:.3f}', ha="center",
                  fontsize=6.5, color="#444444")
    ax_c.set_xticks(x, [g[0] for g in groups], fontsize=7)
    ax_c.set_ylim(0, 1.09)
    ax_c.set_ylabel("Class-conditional coverage")
    ax_c.set_xlabel("C  Three-arm real-transfer test", fontsize=7.5)
    ax_c.legend(loc="upper left", fontsize=6.5, frameon=False)
    fig.savefig(FIG / "fig6_stress_tests.png")
    plt.close(fig)


def fig7_transfer_heatmap() -> None:
    from matplotlib.colors import LinearSegmentedColormap
    tm = pd.read_csv("results/transfer_matrix.csv")
    order = ["mit", "tappy", "typd", "oe"]
    fig, ax = plt.subplots(figsize=(5.9, 4.9), layout="constrained")
    cmap = LinearSegmentedColormap.from_list(
        "biomed", ["#B86F83", "#D7B4B8", "#F2F0EA", "#9AAEC2", "#315A86"])
    norm = plt.Normalize(vmin=0.4, vmax=1.0)
    grid = np.full((4, 4), np.nan)
    for _, r in tm.iterrows():
        i, j = order.index(r["source"]), order.index(r["target"])
        grid[i, j] = r["auc_mean"]
    ax.imshow(np.ma.masked_invalid(grid), cmap=cmap, norm=norm)
    for i in range(4):
        for j in range(4):
            if i == j:
                ax.text(j, i, "\u2014", ha="center", va="center", fontsize=8,
                        color="#999999")
            else:
                v = grid[i, j]
                txt = "#222222" if 0.15 < norm(v) < 0.72 else "white"
                ax.text(j, i, f"{v:.3f}", ha="center", va="center", fontsize=8,
                        color=txt)
    ax.set_xticks(range(4), order, fontsize=8)
    ax.set_yticks(range(4), order, fontsize=8)
    ax.set_xlabel("target")
    ax.set_ylabel("source")
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    cbar = fig.colorbar(ax.images[0], ax=ax, fraction=0.046, pad=0.03,
                        ticks=np.arange(0.4, 1.01, 0.1))
    cbar.set_label("mean test AUC (50 seeds)", fontsize=7.5)
    cbar.ax.tick_params(labelsize=7)
    fig.savefig(FIG / "fig7_transfer_heatmap.png")
    plt.close(fig)


def main() -> None:
    FIG.mkdir(exist_ok=True)
    for f in (fig1_forest, fig2_class_conditional, fig3_decoupling,
              fig4_recovery_cost, fig5_weighted_cp_tradeoff, fig6_stress_tests,
              fig7_transfer_heatmap):
        f()
        print(f"[ok] {f.__name__}")
    print("→ figures/fig1..fig7.png (600 DPI, 183 mm double-column width)")


if __name__ == "__main__":
    main()
