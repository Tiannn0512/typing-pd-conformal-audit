from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cp.conformal import lac_scores, predict_sets_split, split_conformal_quantile
from cp.coverage_audit import ALPHA, CAP, DIRECTIONS, SEED, load_pooled
from cp.remediate import metrics, sets_at_quantile
from models.run_transfer import load_matrix

STRESS_SEED = 1
MATCH_PREV = 0.74
TOL_COV = 0.05
TOL_SIZE = 0.30
FLIP_ARMS = ("resample_only", "flip_only", "both")

def flip_counts_for_pool(pi_ref: float, n_pool: int, n_pd: int, n_hc: int) -> tuple[int, int]:
    x = int(round((MATCH_PREV - pi_ref) * n_pool / 2))
    return min(max(x, 0), n_pd), min(max(x, 0), n_hc)

def main() -> None:
    ap = argparse.ArgumentParser(description="Three-arm stress test")
    ap.add_argument("--arm", default="resample_only,flip_only,both")
    ap.add_argument("--match-prevalence", type=float, default=MATCH_PREV)
    args = ap.parse_args()
    assert args.arm.split(",") == list(FLIP_ARMS), "arm list must equal the fixed list"
    assert abs(args.match_prevalence - MATCH_PREV) < 1e-12, "match prevalence must be 0.74"

    cfg = next(d for d in DIRECTIONS if d["direction"] == "mit2tappy")
    tier = min(CAP["mit"], CAP["tappy"])
    X_s, y_s = load_pooled(cfg["sources"], tier)
    X_t, y_t = load_matrix(cfg["target"], tier)
    assert X_s.shape[1] == X_t.shape[1]
    n_pd, n_hc, n_pool = int((y_s == 1).sum()), int((y_s == 0).sum()), len(y_s)
    assert (n_pd, n_hc, n_pool) == (42, 40, 82), "MIT source pool composition mismatch vs cohort"

    fam = pd.read_csv("results/primary_family.csv")
    ph = fam[(fam["direction"] == "mit2tappy") & (fam["model"] == "lr")].iloc[0]
    PH = {"coverage": float(ph["coverage"]), "mean_size": float(ph["mean_size"]),
          "cpc_pd": float(ph["cpc_pd"]), "cpc_hc": float(ph["cpc_hc"])}

    def run(y_train: np.ndarray, y_cal: np.ndarray, X_tr: np.ndarray, X_cl: np.ndarray,
            ) -> dict:
        scaler = StandardScaler().fit(X_tr)
        clf = LogisticRegression(random_state=42, max_iter=1000)
        clf.fit(scaler.transform(X_tr), y_train)
        q = split_conformal_quantile(lac_scores(clf.predict_proba(scaler.transform(X_cl)),
                                                y_cal), ALPHA)
        probs_te = clf.predict_proba(scaler.transform(X_t))
        m = metrics(y_t, sets_at_quantile(probs_te, q))
        m["reproduced"] = bool(abs(m["coverage"] - PH["coverage"]) <= TOL_COV
                               and abs(m["mean_size"] - PH["mean_size"]) <= TOL_SIZE)
        m["delta_coverage_vs_phenotype"] = m["coverage"] - PH["coverage"]
        m["delta_mean_size_vs_phenotype"] = m["mean_size"] - PH["mean_size"]
        return m

    rng = np.random.default_rng(STRESS_SEED)
    rows = []

    idx = np.arange(n_pool)
    tr_idx, cal_idx = train_test_split(idx, test_size=0.30, random_state=SEED, stratify=y_s)
    scaler = StandardScaler().fit(X_s[tr_idx])
    clf = LogisticRegression(random_state=42, max_iter=1000)
    clf.fit(scaler.transform(X_s[tr_idx]), y_s[tr_idx])
    sets_b = predict_sets_split(lac_scores(clf.predict_proba(scaler.transform(X_s[cal_idx])),
                                           y_s[cal_idx]), clf.predict_proba(scaler.transform(X_t)),
                                ALPHA)
    m_b = metrics(y_t, sets_b)
    assert int(ph["k"]) == m_b["k"] and int(ph["n"]) == m_b["n"]
    for col in ("coverage", "cpc_pd", "cpc_hc", "mean_size", "singleton_rate"):
        assert abs(float(ph[col]) - m_b[col]) < 1e-12, f"baseline {col} drift"
    rc = pd.read_csv("results/recovery_cost_table.csv")
    rc_naive = rc[(rc["direction"] == "mit2tappy") & (rc["method"] == "naive_cp")].iloc[0]
    assert int(rc_naive["k"]) == m_b["k"] and int(rc_naive["n"]) == m_b["n"], \
        "baseline drift vs remediation recovery_cost naive row"
    for col in ("coverage", "cpc_pd", "cpc_hc", "mean_size", "singleton_rate"):
        assert abs(float(rc_naive[col]) - m_b[col]) < 1e-12, f"baseline vs remediation {col} drift"
    m_b["reproduced"] = True
    m_b["delta_coverage_vs_phenotype"] = 0.0
    m_b["delta_mean_size_vs_phenotype"] = 0.0
    rows.append({"arm": "baseline", "scope": "none", "n_pool": n_pool,
                 "n_pd_pool": n_pd, "n_hc_pool": n_hc, "realized_prev": n_pd / n_pool,
                 "n_flip_pd": 0, "n_flip_hc": 0, **m_b, "note": "= primary anchor (double assertion)"})

    hc_all = np.flatnonzero(y_s == 0)
    keep_hc = np.sort(rng.choice(hc_all, size=15, replace=False))
    keep = np.sort(np.concatenate([np.flatnonzero(y_s == 1), keep_hc]))
    X_r, y_r = X_s[keep], y_s[keep]
    tr2, cal2 = train_test_split(np.arange(len(y_r)), test_size=0.30,
                                 random_state=SEED, stratify=y_r)
    m1 = run(y_r[tr2], y_r[cal2], X_r[tr2], X_r[cal2])
    rows.append({"arm": "resample_only", "scope": "pool_level", "n_pool": len(y_r),
                 "n_pd_pool": int((y_r == 1).sum()), "n_hc_pool": int((y_r == 0).sum()),
                 "realized_prev": float((y_r == 1).mean()), "n_flip_pd": 0, "n_flip_hc": 0,
                 **m1, "note": "keep all PD + draw 15 HC; target 0.74 vs achieved 0.7368"})

    x2pd, x2hc = flip_counts_for_pool(n_pd / n_pool, n_pool, n_pd, n_hc)
    fl_pd = rng.choice(np.flatnonzero(y_s == 1), size=x2pd, replace=False)
    fl_hc = rng.choice(hc_all, size=x2hc, replace=False)
    y_flip = y_s.copy()
    y_flip[fl_pd] = 0
    y_flip[fl_hc] = 1
    assert abs((y_flip == 1).mean() - y_s.mean()) < 1e-12, "arm 2 must preserve prevalence"
    for scope, ytr, ycl in [("cal_only", y_s[tr_idx], y_flip[cal_idx]),
                            ("train_cal", y_flip[tr_idx], y_flip[cal_idx])]:
        m2 = run(ytr, ycl, X_s[tr_idx], X_s[cal_idx])
        rows.append({"arm": "flip_only", "scope": scope, "n_pool": n_pool,
                     "n_pd_pool": n_pd, "n_hc_pool": n_hc, "realized_prev": n_pd / n_pool,
                     "n_flip_pd": x2pd, "n_flip_hc": x2hc, **m2,
                     "note": f"equal-count {x2pd}/way prevalence-preserving (rates {x2pd/n_pd:.1%}/"
                             f"{x2hc/n_hc:.1%})"})

    x3pd, x3hc = flip_counts_for_pool(n_pd / n_pool, len(y_r),
                                      int((y_r == 1).sum()), int((y_r == 0).sum()))
    fl3_pd = rng.choice(np.flatnonzero(y_r == 1), size=x3pd, replace=False)
    fl3_hc = rng.choice(np.flatnonzero(y_r == 0), size=x3hc, replace=False)
    y_r_flip = y_r.copy()
    y_r_flip[fl3_pd] = 0
    y_r_flip[fl3_hc] = 1
    assert abs((y_r_flip == 1).mean() - y_r.mean()) < 1e-12, "arm 3 must preserve the resampled-pool prevalence"
    tr3, cal3 = train_test_split(np.arange(len(y_r)), test_size=0.30,
                                 random_state=SEED, stratify=y_r)
    n_pd_r, n_hc_r = int((y_r == 1).sum()), int((y_r == 0).sum())
    for scope, ytr, ycl in [("cal_only", y_r[tr3], y_r_flip[cal3]),
                            ("train_cal", y_r_flip[tr3], y_r_flip[cal3])]:
        m3 = run(ytr, ycl, X_r[tr3], X_r[cal3])
        rows.append({"arm": "both", "scope": scope, "n_pool": len(y_r),
                     "n_pd_pool": int((y_r_flip == 1).sum()), "n_hc_pool": int((y_r_flip == 0).sum()),
                     "realized_prev": float((y_r_flip == 1).mean()),
                     "n_flip_pd": x3pd, "n_flip_hc": x3hc, **m3,
                     "note": f"resampled pool + equal-count flips {x3pd}/way (rates {x3pd/n_pd_r:.1%}/"
                             f"{x3hc/n_hc_r:.1%}; HC side heavier because the pool shrank)"})

    out = pd.DataFrame(rows)
    out.to_csv("results/three_arm_stress_test.csv", index=False)

    print(f"\n=== Three-arm stress test (phenotype = mit2tappy real pattern: cov {PH['coverage']:.4f} / "
          f"size {PH['mean_size']:.4f} / PD {PH['cpc_pd']:.4f} / HC {PH['cpc_hc']:.4f}) ===")
    print(f"criterion (practical-equivalence tolerance): |dcov|<={TOL_COV} and |dsize|<={TOL_SIZE}")
    for _, r in out.iterrows():
        verdict = ("SUFFICIENT to reproduce" if r["reproduced"] else "INSUFFICIENT to reproduce")
        print(f"[{r['arm']:<14}|{r['scope']:<10}] pool={int(r['n_pool'])}"
              f" (PD{int(r['n_pd_pool'])}/HC{int(r['n_hc_pool'])}, prev={r['realized_prev']:.4f})"
              f" flips {int(r['n_flip_pd'])}/{int(r['n_flip_hc'])} -> "
              f"cov={r['coverage']:.4f} (delta {r['delta_coverage_vs_phenotype']:+.4f})"
              f" size={r['mean_size']:.4f} (delta {r['delta_mean_size_vs_phenotype']:+.4f})"
              f" PD={r['cpc_pd']:.4f} HC={r['cpc_hc']:.4f} -> {verdict}")
    print("\nConclusion: this table tests whether prevalence resampling and random label corruption are sufficient to reproduce "
          "the observed coverage pattern; no causal identification is claimed.")

    print(f"{len(out)} rows -> results/three_arm_stress_test.csv")

if __name__ == "__main__":
    main()
