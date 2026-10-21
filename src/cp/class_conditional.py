from __future__ import annotations

import argparse
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
from cp.conformal import lac_scores, predict_sets_split
from cp.coverage_audit import ALPHA, CAP, DIRECTIONS, SEED, load_pooled
from models.run_transfer import load_matrix

DIAGNOSTIC_CAVEAT = (
    "Class-conditional coverage is reported as a safety diagnostic, "
    "not a distribution-free guarantee: under joint covariate+label shift it may be "
    "unidentifiable without target labels (arXiv:2607.18088). Values are empirical "
    "rates with Clopper-Pearson exact binomial CIs on the target cohort."
)

def cp_ci(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    lo = float(_beta.ppf(0.025, k, n - k + 1)) if k > 0 else 0.0
    hi = float(_beta.ppf(0.975, k + 1, n - k)) if k < n else 1.0
    return lo, hi

def run_direction_hits(cfg: dict, model_name: str) -> dict:
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
        mcs = max(1, int(len(tr_idx) // 4))
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
    m = y_t == cls
    k, n = int(hits[m].sum()), int(m.sum())
    lo, hi = cp_ci(k, n)
    return {"k_cls": k, "n_cls": n, "coverage_cls": k / n, "ci_lo_cls": lo, "ci_hi_cls": hi,
            "mean_size_cls": float(sizes[m].mean()), "singleton_rate_cls": float((sizes[m] == 1).mean()),
            "empty_sets_cls": int((sizes[m] == 0).sum())}

def main() -> None:
    ap = argparse.ArgumentParser(description="PD/HC class-conditional coverage (safety diagnostic)")
    ap.add_argument("--classes", default="PD,HC", help="diagnostic classes (two)")
    ap.add_argument("--primary-directions", action="store_true",
                    help="run only the three primary directions")
    args = ap.parse_args()
    assert args.classes == "PD,HC", "this script defines only PD/HC"
    assert args.primary_directions, "--primary-directions is required (guards against silent extension)"

    fam = pd.read_csv("results/primary_family.csv")

    results = []
    for cfg in DIRECTIONS:
        for model in ("lr", "lgbm"):
            r = run_direction_hits(cfg, model)
            y_t, hits, sizes = r["y_t"], r["hits"], r["sizes"]
            direction, n = cfg["direction"], len(y_t)
            k = int(hits.sum())
            cov_lo, cov_hi = cp_ci(k, n)

            f = fam[(fam["direction"] == direction) & (fam["model"] == model)].iloc[0]
            for col, val in [("k", k), ("n", n), ("tier", r["tier"]),
                             ("n_source", r["n_source"]), ("n_cal", r["n_cal"])]:
                assert int(f[col]) == val, f"{direction}/{model} {col} drift: {f[col]} != {val}"
            for col, val in [("coverage", k / n), ("cpc_pd", hits[y_t == 1].mean()),
                             ("cpc_hc", hits[y_t == 0].mean()), ("mean_size", sizes.mean()),
                             ("singleton_rate", (sizes == 1).mean())]:
                assert abs(float(f[col]) - val) < 1e-12, f"{direction}/{model} {col} drift"

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

    out = pd.DataFrame(results)
    out.to_csv("results/class_conditional_coverage.csv", index=False)

    for _, row in out.iterrows():
        print(f"[{row['direction']}/{row['model']}] overall {row['coverage_overall']:.4f} "
              f"CI[{row['ci_lo_overall']:.4f},{row['ci_hi_overall']:.4f}] (n={row['n_overall']}) | "
              f"PD {row['coverage_cls_pd']:.4f} CI[{row['ci_lo_cls_pd']:.4f},{row['ci_hi_cls_pd']:.4f}] "
              f"(n={row['n_cls_pd']}, gap={row['gap_pd_vs_overall']:+.4f}) | "
              f"HC {row['coverage_cls_hc']:.4f} CI[{row['ci_lo_cls_hc']:.4f},{row['ci_hi_cls_hc']:.4f}] "
              f"(n={row['n_cls_hc']}, gap={row['gap_hc_vs_overall']:+.4f})")
        for cls in ("pd", "hc"):
            if row[f"ci_hi_cls_{cls}"] < 0.90:
                print(f"    signal: {cls.upper()} class-conditional upper CI < 0.90 (failure mode, not a verdict)")
    print(f"\n{DIAGNOSTIC_CAVEAT}")

if __name__ == "__main__":
    main()
