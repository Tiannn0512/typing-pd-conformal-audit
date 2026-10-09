#!/usr/bin/env python
"""class_conditional.py — PD/HC 类条件覆盖：安全性诊断终点（TODO-4.3）

预注册口径（analysis_plan_v1.md §8）：PD/HC 类条件覆盖 = pre-specified safety
diagnostic，**非分布无关保证**（依据 arXiv:2607.18088，Han et al.：协变量+标签偏移
并存时类条件覆盖可能不可识别）；与总体覆盖差异显式呈现。诊断不进 primary family、
不做三分类判定、不做 Holm——只报精确二项 CI 与差距。

管线与 coverage_audit.py 完全同源（同一 seed=1 确证切分、同一 tier=min(全链 cap)、
同一 LR 主参照/LGBM 对照 DEC-T1），并对 primary_family.csv 的全部已存列
（k/n/coverage/cpc_pd/cpc_hc/mean_size/singleton_rate/tier/n_source/n_cal）
做逐列一致性断言：任何管线漂移在落盘前即被拦截。

产出：results/class_conditional_coverage.csv（正式）
     + data/interim/parse_reports/class_conditional_subject_hits.csv（复核用受试者级）
     + data/interim/parse_reports/class_conditional_report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from scipy.stats import beta as _beta
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cp.conformal import lac_scores, predict_sets_split  # noqa: E402
from cp.coverage_audit import ALPHA, CAP, DIRECTIONS, SEED, load_pooled  # noqa: E402
from models.run_transfer import load_matrix  # noqa: E402

# 2607.18088 对表声明（预注册 §8 措辞，输出文件与报告均携带）
DIAGNOSTIC_CAVEAT = (
    "Class-conditional coverage is reported as a pre-specified safety diagnostic, "
    "not a distribution-free guarantee: under joint covariate+label shift it may be "
    "unidentifiable without target labels (arXiv:2607.18088). Values are empirical "
    "rates with Clopper-Pearson exact binomial CIs on the frozen target cohort."
)


def cp_ci(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Clopper-Pearson 精确二项 CI，含 K=0/K=n 边界守卫（与 coverage_audit 同式）。

    端点字面量 0.025/0.975 与 coverage_audit 逐字一致——(1-0.95)/2 的代数等价形式
    会因浮点量化使 beta.ppf 末位差 1 ulp（审核定位：跨表 ci_lo 尾差根因）。"""
    if n == 0:
        return float("nan"), float("nan")
    lo = float(_beta.ppf(0.025, k, n - k + 1)) if k > 0 else 0.0
    hi = float(_beta.ppf(0.975, k + 1, n - k)) if k < n else 1.0
    return lo, hi


def run_direction_hits(cfg: dict, model_name: str) -> dict:
    """与 coverage_audit.run_direction 同管线，返回受试者级 hits/sets 供类条件分解。"""
    srcs, tgt = cfg["sources"], cfg["target"]
    tgt_datasets = {"merged_self": ["tappy", "oe"]}.get(tgt, [tgt])
    tier = min(CAP[d] for d in srcs + tgt_datasets)
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
    X_tr_s, X_cal_s, X_te_s = (scaler.transform(X_s[tr_idx]), scaler.transform(X_s[cal_idx]),
                               scaler.transform(X_t))

    if model_name == "lr":
        clf = LogisticRegression(random_state=42, max_iter=1000)
    else:
        mcs = max(1, int(len(tr_idx) // 4))  # DEC-T1 规则
        clf = LGBMClassifier(random_state=42, verbose=-1, min_child_samples=mcs, max_depth=3)
    clf.fit(X_tr_s, y_s[tr_idx])

    scores_cal = lac_scores(clf.predict_proba(X_cal_s), y_s[cal_idx])
    sets = predict_sets_split(scores_cal, clf.predict_proba(X_te_s), ALPHA)
    hits = np.array([y in s for y, s in zip(y_t, sets)])
    sizes = np.array([len(s) for s in sets])
    return {"tier": tier, "y_t": y_t, "hits": hits, "sizes": sizes,
            "n_source": len(y_s[tr_idx]), "n_cal": len(y_s[cal_idx])}


def class_stats(y_t: np.ndarray, hits: np.ndarray, sizes: np.ndarray,
                cls: int) -> dict:
    """单类（1=PD / 0=HC）覆盖诊断：k/n/覆盖率/精确 CI/集合效率。"""
    m = y_t == cls
    k, n = int(hits[m].sum()), int(m.sum())
    lo, hi = cp_ci(k, n)
    return {"k_cls": k, "n_cls": n, "coverage_cls": k / n, "ci_lo_cls": lo, "ci_hi_cls": hi,
            "mean_size_cls": float(sizes[m].mean()), "singleton_rate_cls": float((sizes[m] == 1).mean()),
            "empty_sets_cls": int((sizes[m] == 0).sum())}


def main() -> None:
    ap = argparse.ArgumentParser(description="PD/HC class-conditional coverage (safety diagnostic)")
    ap.add_argument("--classes", default="PD,HC", help="诊断类别（冻结为二类）")
    ap.add_argument("--primary-directions", action="store_true",
                    help="仅跑 primary family 三方向（本终点口径）")
    args = ap.parse_args()
    assert args.classes == "PD,HC", "本终点按预注册仅定义 PD/HC 两类"
    assert args.primary_directions, "须显式指定 --primary-directions（防误扩展到探索方向）"

    frozen = pd.read_csv("results/primary_family.csv")

    results, subject_rows = [], []
    for cfg in DIRECTIONS:
        for model in ("lr", "lgbm"):
            r = run_direction_hits(cfg, model)
            y_t, hits, sizes = r["y_t"], r["hits"], r["sizes"]
            direction, n = cfg["direction"], len(y_t)
            k = int(hits.sum())
            cov_lo, cov_hi = cp_ci(k, n)

            # 同源性硬断言：复算聚合量必须与 frozen primary_family.csv 逐列一致
            f = frozen[(frozen["direction"] == direction) & (frozen["model"] == model)].iloc[0]
            for col, val in [("k", k), ("n", n), ("tier", r["tier"]),
                             ("n_source", r["n_source"]), ("n_cal", r["n_cal"])]:
                assert int(f[col]) == val, f"{direction}/{model} {col} 漂移: {f[col]} != {val}"
            for col, val in [("coverage", k / n), ("cpc_pd", hits[y_t == 1].mean()),
                             ("cpc_hc", hits[y_t == 0].mean()), ("mean_size", sizes.mean()),
                             ("singleton_rate", (sizes == 1).mean())]:
                assert abs(float(f[col]) - val) < 1e-12, f"{direction}/{model} {col} 漂移"

            pd_s = class_stats(y_t, hits, sizes, 1)
            hc_s = class_stats(y_t, hits, sizes, 0)
            row = {"direction": direction, "model": model, "tier": r["tier"],
                   "k_overall": k, "n_overall": n,
                   "coverage_overall": k / n, "ci_lo_overall": cov_lo, "ci_hi_overall": cov_hi,
                   **{f"{key}_pd": v for key, v in pd_s.items()},
                   **{f"{key}_hc": v for key, v in hc_s.items()},
                   "gap_pd_vs_overall": pd_s["coverage_cls"] - k / n,
                   "gap_hc_vs_overall": hc_s["coverage_cls"] - k / n,
                   "pd_ci_excludes_090": bool(pd_s["ci_hi_cls"] < 0.90),
                   "hc_ci_excludes_090": bool(hc_s["ci_hi_cls"] < 0.90),
                   "n_source": r["n_source"], "n_cal": r["n_cal"]}
            results.append(row)

            for i in range(n):
                subject_rows.append({"direction": direction, "model": model, "row_idx": i,
                                     "y_true": int(y_t[i]), "hit": int(hits[i]),
                                     "set_size": int(sizes[i])})

    out = pd.DataFrame(results)
    out.to_csv("results/class_conditional_coverage.csv", index=False)

    hits_path = Path("data/interim/parse_reports/class_conditional_subject_hits.csv")
    hits_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(subject_rows).to_csv(hits_path, index=False)

    Path("data/interim/parse_reports/class_conditional_report.json").write_text(
        json.dumps({"caveat": DIAGNOSTIC_CAVEAT, "alpha": ALPHA, "seed": SEED,
                    "rows": results}, indent=2, default=float), encoding="utf-8")

    # 显式呈现：总体 vs PD vs HC 并排（2607.18088 对表：总体覆盖可掩盖类间失衡）
    for _, row in out.iterrows():
        print(f"[{row['direction']}/{row['model']}] 总体 {row['coverage_overall']:.4f} "
              f"CI[{row['ci_lo_overall']:.4f},{row['ci_hi_overall']:.4f}] (n={row['n_overall']}) | "
              f"PD {row['coverage_cls_pd']:.4f} CI[{row['ci_lo_cls_pd']:.4f},{row['ci_hi_cls_pd']:.4f}] "
              f"(n={row['n_cls_pd']}, gap={row['gap_pd_vs_overall']:+.4f}) | "
              f"HC {row['coverage_cls_hc']:.4f} CI[{row['ci_lo_cls_hc']:.4f},{row['ci_hi_cls_hc']:.4f}] "
              f"(n={row['n_cls_hc']}, gap={row['gap_hc_vs_overall']:+.4f})")
        for cls in ("pd", "hc"):
            if row[f"ci_hi_cls_{cls}"] < 0.90:
                print(f"    诊断: {cls.upper()} 类条件覆盖 CI 上界 < 0.90（安全性信号，非判定）")
    print(f"\n{DIAGNOSTIC_CAVEAT}")


if __name__ == "__main__":
    main()
