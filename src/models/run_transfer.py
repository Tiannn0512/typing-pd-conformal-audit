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
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from lightgbm import LGBMClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cp.conformal import lac_scores, predict_sets_split  # noqa: E402

ALPHA = 0.10
CAP = {"mit": 3, "tappy": 2, "typd": 1, "oe": 3}
DATASETS = ["mit", "tappy", "typd", "oe"]

L1_COLS = [f"L1_{s}_{stat}" for s in ("hold", "latency", "flight")
           for stat in ("mean", "median", "sd", "p10", "p90")]
L2_COLS = [f"{s}_{h}_mean" for s in ("hold", "latency", "flight") for h in ("L", "R")]
L3_COLS = [f"{s}_{tr}_mean" for s in ("latency", "flight") for tr in ("same", "cross")] + ["frac_cross"]


def tier_columns(ds: str, tier: int) -> list[str]:
    """数据集 ds 在 tier 下的 canonical 特征列（源/目标同名对齐）。"""
    cols = list(L1_COLS)
    if tier >= 2:
        prefix = "L2tappy" if ds == "tappy" else f"L2_{ds}"
        cols += [f"{prefix}_{c}" for c in L2_COLS]
    if tier >= 3:
        cols += [f"L3_{ds}_{c}" for c in L3_COLS]
    return cols


def load_matrix(ds: str, tier: int) -> tuple[np.ndarray, np.ndarray]:
    subjects = pd.read_csv("data/processed/subjects.csv")
    sub = subjects[subjects["dataset"] == ds]
    l2l3 = pd.read_csv("data/processed/subjects_l2l3.csv")
    merged = sub.merge(l2l3, on="subject_id", how="left")
    cols = tier_columns(ds, tier)
    X = merged[cols].to_numpy(dtype=float)
    y = merged["label_pd"].to_numpy(dtype=int)
    assert not np.isnan(X).any(), f"{ds} tier{tier} 特征含 NaN（{cols}）"
    return X, y


def sixtuple(sets, y_t, scores_pos, y_obs=None) -> dict:
    """六元组（预注册 §1）：覆盖/PD类条件/HC类条件/平均集合大小/单例/模糊/空 + AUC。"""
    hits = np.array([y in s for y, s in zip(y_t, sets)])
    sizes = np.array([len(s) for s in sets])
    out = {"coverage": hits.mean(), "cpc_pd": hits[y_t == 1].mean(),
           "cpc_hc": hits[y_t == 0].mean(), "mean_size": sizes.mean(),
           "singleton_rate": (sizes == 1).mean(), "fuzzy_rate": (sizes == 2).mean(),
           "empty_rate": (sizes == 0).mean(),
           "auc": roc_auc_score(y_t, scores_pos)}
    return out


def main() -> None:
    seeds = yaml.safe_load((Path(__file__).resolve().parents[2] / "configs" / "seeds.yaml")
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
                idx = np.arange(len(X_s))
                tr_idx, cal_idx = train_test_split(idx, test_size=0.30, random_state=seed,
                                                   stratify=y_s)
                scaler = StandardScaler().fit(X_s[tr_idx])
                X_tr_s, X_cal_s, X_te_s = (scaler.transform(X_s[tr_idx]),
                                           scaler.transform(X_s[cal_idx]),
                                           scaler.transform(X_t))

                # 主参照 LR（CHG-P1）
                clf = LogisticRegression(random_state=42, max_iter=1000).fit(X_tr_s, y_s[tr_idx])
                scores_cal = lac_scores(clf.predict_proba(X_cal_s), y_s[cal_idx])
                sets = predict_sets_split(scores_cal, clf.predict_proba(X_te_s), ALPHA)
                for k, v in sixtuple(sets, y_t, clf.predict_proba(X_te_s)[:, 1]).items():
                    acc[k].append(v)

                # LGBM 对照（DEC-T1：参数按 n_train 约束规则锁定，非搜索；完整六元组，用户指令）
                mcs = max(1, int(len(tr_idx) // 4))
                lgbm = LGBMClassifier(random_state=42, verbose=-1,
                                      min_child_samples=mcs, max_depth=3).fit(X_tr_s, y_s[tr_idx])
                proba_l = lgbm.predict_proba(X_te_s)
                if len(np.unique(np.round(proba_l[:, 1], 12))) == 1:
                    raise RuntimeError(f"{src}2{tgt} seed={seed}: LGBM 对照列常数预测（机制性退化）")
                scores_cal_l = lac_scores(lgbm.predict_proba(X_cal_s), y_s[cal_idx])
                sets_l = predict_sets_split(scores_cal_l, proba_l, ALPHA)
                for k, v in sixtuple(sets_l, y_t, proba_l[:, 1]).items():
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
