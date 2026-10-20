#!/usr/bin/env python
"""run_transfer.py — 12 方向迁移矩阵（TODO-4.1，描述性六元组）

预注册口径（analysis_plan_v1.md §1/§3/§7）：
    tier(方向) = min(max_tier(源), max_tier(目标))；cap = {mit:3, tappy:2, typd:1, oe:3}
    每方向：源受试者分层 70/30 → train/cal；LR（零调参）拟合 train；split conformal 校准 cal
    （α=0.10，k=⌈(n+1)(1−α)⌉）；预测**目标域全部受试者**；50 seeds（split_seeds 1-50）取均值。
    六元组：总体覆盖 / PD 类条件覆盖 / HC 类条件覆盖 / 平均集合大小 /
            单例率 / 模糊(双例)率 / 空集率 / AUC（描述性，bootstrap 置信区间随 W9 定稿补）。
特征列（canonical，源/目标同名列对齐）：
    L1=15（subjects.csv）；L2=L1+6（mit/oe ← subjects_l2l3.csv，tappy ← subjects.csv L2tappy_*）；
    L3=L2+5（subjects_l2l3.csv）。档位入结果列。
产出：results/transfer_matrix.csv + figures/transfer_heatmap.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import seaborn as sns  # noqa: E402
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime import config_path

from protocol import CAP
from models.common import fit_transfer, load_matrix
from cp.metrics import metrics
DATASETS = ["mit", "tappy", "typd", "oe"]


def sixtuple(sets, y_t, scores_pos, y_obs=None) -> dict:
    result = metrics(y_t, sets)
    columns = ("coverage", "cpc_pd", "cpc_hc", "mean_size", "singleton_rate", "empty_rate")
    return {**{key: result[key] for key in columns}, "fuzzy_rate": result["rejection_rate"],
            "auc": roc_auc_score(y_t, scores_pos)}


def main() -> None:
    seeds = yaml.safe_load((config_path("seeds.yaml"))
                           .read_text(encoding="utf-8"))["split_seeds"]
    rows = []
    for src in DATASETS:
        for tgt in DATASETS:
            if src == tgt:
                continue
            tier = min(CAP[src], CAP[tgt])
            X_s, y_s = load_matrix(src, tier)
            X_t, y_t = load_matrix(tgt, tier)
            acc = {k: [] for k in ("coverage", "cpc_pd", "cpc_hc", "mean_size",
                                   "singleton_rate", "fuzzy_rate", "empty_rate", "auc")}
            acc_lgbm = {k: [] for k in acc}
            for seed in seeds:
                lr = fit_transfer(X_s, y_s, X_t, "lr", seed)
                for k, v in sixtuple(lr["sets"], y_t, lr["probs_te"][:, 1]).items():
                    acc[k].append(v)
                lgbm = fit_transfer(X_s, y_s, X_t, "lgbm", seed)
                proba_l = lgbm["probs_te"]
                if len(np.unique(np.round(proba_l[:, 1], 12))) == 1:
                    raise RuntimeError(f"{src}2{tgt} seed={seed}: LGBM comparator produced constant predictions")
                for k, v in sixtuple(lgbm["sets"], y_t, proba_l[:, 1]).items():
                    acc_lgbm[k].append(v)
            rows.append({
                "direction": f"{src}2{tgt}", "source": src, "target": tgt, "tier": tier,
                "n_source": len(X_s), "n_target": len(X_t),
                **{f"{k}_mean": float(np.mean(v)) for k, v in acc.items()},
                **{f"{k}_std": float(np.std(v, ddof=1)) for k, v in acc.items()},
                **{f"lgbm_{k}_mean": float(np.mean(v)) for k, v in acc_lgbm.items()},
                **{f"lgbm_{k}_std": float(np.std(v, ddof=1)) for k, v in acc_lgbm.items()},
            })
            print(f"[transfer] {src}2{tgt} tier=L{tier} LR: AUC={np.mean(acc['auc']):.4f} "
                  f"cov={np.mean(acc['coverage']):.4f} size={np.mean(acc['mean_size']):.3f} | "
                  f"LGBM: AUC={np.mean(acc_lgbm['auc']):.4f} cov={np.mean(acc_lgbm['coverage']):.4f}")

    table = pd.DataFrame(rows)
    Path("results").mkdir(exist_ok=True)
    table.to_csv("results/transfer_matrix.csv", index=False)

    auc = table.pivot(index="source", columns="target", values="auc_mean")
    fig_dir = Path("figures")
    fig_dir.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    sns.heatmap(auc.loc[DATASETS, DATASETS], annot=True, fmt=".3f", cmap="viridis",
                vmin=0.4, vmax=1.0, ax=ax, cbar_kws={"label": "mean test AUC (50 seeds)"})
    ax.set_title("Cross-dataset transfer: AUC (LR + split CP features, tier-downgraded)")
    ax.set_xlabel("target"); ax.set_ylabel("source")
    fig.tight_layout()
    fig.savefig(fig_dir / "transfer_heatmap.png", dpi=150)
    print(f"[transfer] rows={len(table)} -> results/transfer_matrix.csv + figures/transfer_heatmap.png")


if __name__ == "__main__":
    main()
