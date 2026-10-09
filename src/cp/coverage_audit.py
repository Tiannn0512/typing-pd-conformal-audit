#!/usr/bin/env python
"""coverage_audit.py — primary family 覆盖判定（TODO-4.2，论文主结果）

预注册口径（analysis_plan_v1.md §6/§7）：
  确证性分析 = 单一预指定切分（seed=1，configs/seeds.yaml split_seeds 首位；50-seed 均值
  仅用于描述性矩阵——同一批受试者重复 50 次不能当二项 n 膨胀精度）。
  源 70/30 分层 train/cal（LR 主参照 CHG-P1，零调参）→ split conformal α=0.10 →
  目标域全部冻结受试者覆盖 K/n。
  三分类（§6，名义，未调 CI）：hi<0.90 → Incompatible；否则 lo≥0.80 → Compatible；
  否则 Undetermined（重叠区 Incompatible 优先已钉）。
  Primary family 判定（§7，主结论）：H0 = 真实覆盖 ≥0.90（单侧不足），
  p = P_{Bin(n,0.90)}(K ≤ K_obs)；家族内 Holm（m=3，family-wise 0.10，
  步降阈值 α/3, α/2, α）；**主判定基于 Holm**：q_i < 0.10 → Incompatible（家族受控地
  确立覆盖 < 0.90）；未拒绝者按 §6 名义规则（lo ≥ 0.80 → Compatible，否则 Undetermined）。
  LGBM 对照（DEC-T1）同管线描述性报告，不进判定。

产出：results/primary_family.csv + primary_family_report.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from lightgbm import LGBMClassifier
from scipy.stats import binom
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cp.conformal import lac_scores, predict_sets_split  # noqa: E402
from models.run_transfer import load_matrix  # noqa: E402

ALPHA = 0.10
FAMILY_WISE = 0.10
SEED = 1  # 预指定：split_seeds 首位（确证性分析单一切分）
COVERAGE_H0 = 0.90
COVERAGE_LO = 0.80
# primary family 构成（analysis_plan_v1.md §7）：源池/目标池与 tier
DIRECTIONS = [
    {"direction": "tappy2mit", "sources": ["tappy"], "target": "mit"},
    {"direction": "mit2tappy", "sources": ["mit"], "target": "tappy"},
    {"direction": "gold_merged2self", "sources": ["mit", "typd"], "target": "merged_self"},
]
CAP = {"mit": 3, "tappy": 2, "typd": 1, "oe": 3}


def load_pooled(datasets: list[str], tier: int) -> tuple[np.ndarray, np.ndarray]:
    """按给定 tier 装载（tier_transfer = min(全链 cap)，由 run_direction 计算）。"""
    if len(datasets) == 1:
        X, y = load_matrix(datasets[0], tier)
        return X, y
    assert tier == 1, "合并池多源方向 tier 必须为 1（含 TyPD）"
    subjects = pd.read_csv("data/processed/subjects.csv")
    pool = subjects[subjects["dataset"].isin(datasets)]
    cols = [c for c in pool.columns if c.startswith("L1_")]
    X = pool[cols].to_numpy(dtype=float)
    y = pool["label_pd"].to_numpy(dtype=int)
    assert not np.isnan(X).any()
    return X, y


def holm(pvals: list[float]) -> list[float]:
    """Holm 步降 adjusted p-values（单调，cap 1.0）。"""
    m = len(pvals)
    order = np.argsort(pvals)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        val = (m - rank) * pvals[i]
        running = max(running, val)
        adj[i] = min(running, 1.0)
    return list(adj)


def run_direction(cfg: dict, model_name: str) -> dict:
    srcs, tgt = cfg["sources"], cfg["target"]
    tgt_datasets = {"merged_self": ["tappy", "oe"]}.get(tgt, [tgt])
    tier = min(CAP[d] for d in srcs + tgt_datasets)  # tier_transfer = 全链 min（修 mit2tappy 目标被误装 L3 的 bug）
    X_s, y_s = load_pooled(srcs, tier)
    if tgt == "merged_self":
        subjects = pd.read_csv("data/processed/subjects.csv")
        pool = subjects[subjects["dataset"].isin(["tappy", "oe"])]
        cols = [c for c in pool.columns if c.startswith("L1_")]
        X_t = pool[cols].to_numpy(dtype=float)
        y_t = pool["label_pd"].to_numpy(dtype=int)
    else:
        X_t, y_t = load_matrix(tgt, tier)
    assert X_s.shape[1] == X_t.shape[1]

    idx = np.arange(len(X_s))
    tr_idx, cal_idx = train_test_split(idx, test_size=0.30, random_state=SEED, stratify=y_s)
    scaler = StandardScaler().fit(X_s[tr_idx])
    X_tr_s, X_cal_s, X_te_s = scaler.transform(X_s[tr_idx]), scaler.transform(X_s[cal_idx]), scaler.transform(X_t)

    if model_name == "lr":
        clf = LogisticRegression(random_state=42, max_iter=1000)
    else:
        mcs = max(1, int(len(tr_idx) // 4))  # DEC-T1 规则
        clf = LGBMClassifier(random_state=42, verbose=-1, min_child_samples=mcs, max_depth=3)
    clf.fit(X_tr_s, y_s[tr_idx])

    scores_cal = lac_scores(clf.predict_proba(X_cal_s), y_s[cal_idx])
    sets = predict_sets_split(scores_cal, clf.predict_proba(X_te_s), ALPHA)
    hits = np.array([y in s for y, s in zip(y_t, sets)])
    k, n = int(hits.sum()), int(len(hits))
    from scipy.stats import beta as _beta
    lo = float(_beta.ppf(0.025, k, n - k + 1)) if k > 0 else 0.0
    hi = float(_beta.ppf(0.975, k + 1, n - k)) if k < n else 1.0  # K=n → 上界 1（修 NaN 边界）
    p_one_sided = float(binom.cdf(k, n, COVERAGE_H0))
    sizes = np.array([len(s) for s in sets])
    return {"k": k, "n": n, "coverage": k / n, "ci_lo": lo, "ci_hi": hi,
            "p_one_sided": p_one_sided, "mean_size": float(sizes.mean()),
            "singleton_rate": float((sizes == 1).mean()),
            "cpc_pd": float(hits[y_t == 1].mean()), "cpc_hc": float(hits[y_t == 0].mean()),
            "tier": tier, "n_source": len(y_s[tr_idx]), "n_cal": len(y_s[cal_idx])}


def nominal_three_class(lo: float, hi: float) -> str:
    """§6 名义规则（未调 CI，Incompatible 优先）。"""
    if hi < 0.90:
        return "Incompatible"
    if lo >= 0.80:
        return "Compatible"
    return "Undetermined"


def main() -> None:
    seeds_cfg = yaml.safe_load((Path(__file__).resolve().parents[2] / "configs" / "seeds.yaml")
                               .read_text(encoding="utf-8"))
    assert seeds_cfg["split_seeds"][0] == SEED, "确证性切分必须用登记 seed 首位"

    results = []
    for cfg in DIRECTIONS:
        for model in ("lr", "lgbm"):
            r = run_direction(cfg, model)
            r.update({"direction": cfg["direction"], "model": model})
            if model == "lr":
                r["nominal_three_class"] = nominal_three_class(r["ci_lo"], r["ci_hi"])
            results.append(r)

    # Holm（LR 主参照，m=3）
    lr_rows = [r for r in results if r["model"] == "lr"]
    pvals = [r["p_one_sided"] for r in lr_rows]
    qvals = holm(pvals)
    for r, q in zip(lr_rows, qvals):
        r["holm_q"] = q
        if q < FAMILY_WISE:
            r["primary_verdict"] = "Incompatible (family-controlled: coverage < 0.90 established)"
        else:
            r["primary_verdict"] = nominal_three_class(r["ci_lo"], r["ci_hi"]) + " (Holm 未拒绝)"

    Path("results").mkdir(exist_ok=True)  # 全新 checkout 一键重跑守卫（终审建议项）
    out = pd.DataFrame(results)
    # 对照模型的判定列显式 NA（不进 family、不参与判定；避免裸 NaN 歧义）
    for c in ("holm_q", "nominal_three_class", "primary_verdict"):
        out[c] = out.get(c, pd.Series("NA (comparator)", index=out.index))
        out[c] = out[c].fillna("NA (comparator)")
    cols_front = ["direction", "model", "tier", "k", "n", "coverage", "ci_lo", "ci_hi",
                  "p_one_sided", "holm_q", "nominal_three_class", "primary_verdict"]
    cols = [c for c in cols_front if c in out.columns] + \
           [c for c in out.columns if c not in cols_front]
    out = out[cols]
    out.to_csv("results/primary_family.csv", index=False)

    print(out[[c for c in cols_front if c in out.columns]].to_string(index=False))
    for r in lr_rows:
        print(f"[primary] {r['direction']}: K={r['k']}/{r['n']} cov={r['coverage']:.4f} "
              f"CI=[{r['ci_lo']:.4f},{r['ci_hi']:.4f}] 名义={r['nominal_three_class']} "
              f"Holm q={r['holm_q']:.4g} → 主判定={r['primary_verdict']}")
    (Path("results").parent / "data" / "interim" / "parse_reports").mkdir(parents=True, exist_ok=True)
    Path("data/interim/parse_reports/primary_family_report.json").write_text(
        json.dumps(results, indent=2, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
