from __future__ import annotations

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
from cp.conformal import lac_scores, predict_sets_split
from models.run_transfer import load_matrix

ALPHA = 0.10
FAMILY_WISE = 0.10
SEED = 1
COVERAGE_H0 = 0.90
COVERAGE_LO = 0.80
DIRECTIONS = [
    {"direction": "tappy2mit", "sources": ["tappy"], "target": "mit"},
    {"direction": "mit2tappy", "sources": ["mit"], "target": "tappy"},
    {"direction": "gold_merged2self", "sources": ["mit", "typd"], "target": "merged_self"},
]
CAP = {"mit": 3, "tappy": 2, "typd": 1, "oe": 3}

def load_pooled(datasets: list[str], tier: int) -> tuple[np.ndarray, np.ndarray]:
    if len(datasets) == 1:
        X, y = load_matrix(datasets[0], tier)
        return X, y
    assert tier == 1, "pooled multi-source direction requires tier 1 (TyPD included)"
    subjects = pd.read_csv("data/processed/subjects.csv")
    pool = subjects[subjects["dataset"].isin(datasets)]
    cols = [c for c in pool.columns if c.startswith("L1_")]
    X = pool[cols].to_numpy(dtype=float)
    y = pool["label_pd"].to_numpy(dtype=int)
    assert not np.isnan(X).any()
    return X, y

def holm(pvals: list[float]) -> list[float]:
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
    X_tr_s, X_cal_s, X_te_s = scaler.transform(X_s[tr_idx]), scaler.transform(X_s[cal_idx]), scaler.transform(X_t)

    if model_name == "lr":
        clf = LogisticRegression(random_state=42, max_iter=1000)
    else:
        mcs = max(1, int(len(tr_idx) // 4))
        clf = LGBMClassifier(random_state=42, verbose=-1, min_child_samples=mcs, max_depth=3)
    clf.fit(X_tr_s, y_s[tr_idx])

    scores_cal = lac_scores(clf.predict_proba(X_cal_s), y_s[cal_idx])
    sets = predict_sets_split(scores_cal, clf.predict_proba(X_te_s), ALPHA)
    hits = np.array([y in s for y, s in zip(y_t, sets)])
    k, n = int(hits.sum()), int(len(hits))
    from scipy.stats import beta as _beta
    lo = float(_beta.ppf(0.025, k, n - k + 1)) if k > 0 else 0.0
    hi = float(_beta.ppf(0.975, k + 1, n - k)) if k < n else 1.0
    p_one_sided = float(binom.cdf(k, n, COVERAGE_H0))
    sizes = np.array([len(s) for s in sets])
    return {"k": k, "n": n, "coverage": k / n, "ci_lo": lo, "ci_hi": hi,
            "p_one_sided": p_one_sided, "mean_size": float(sizes.mean()),
            "singleton_rate": float((sizes == 1).mean()),
            "cpc_pd": float(hits[y_t == 1].mean()), "cpc_hc": float(hits[y_t == 0].mean()),
            "tier": tier, "n_source": len(y_s[tr_idx]), "n_cal": len(y_s[cal_idx])}

def nominal_three_class(lo: float, hi: float) -> str:
    if hi < 0.90:
        return "Incompatible"
    if lo >= 0.80:
        return "Compatible"
    return "Undetermined"

def main() -> None:
    seeds_cfg = yaml.safe_load((Path(__file__).resolve().parents[2] / "configs" / "analysis.yml")
                               .read_text(encoding="utf-8"))
    assert seeds_cfg["split_seeds"][0] == SEED, "the confirmatory split must use the first split_seeds entry"

    results = []
    for cfg in DIRECTIONS:
        for model in ("lr", "lgbm"):
            r = run_direction(cfg, model)
            r.update({"direction": cfg["direction"], "model": model})
            if model == "lr":
                r["nominal_three_class"] = nominal_three_class(r["ci_lo"], r["ci_hi"])
            results.append(r)

    lr_rows = [r for r in results if r["model"] == "lr"]
    pvals = [r["p_one_sided"] for r in lr_rows]
    qvals = holm(pvals)
    for r, q in zip(lr_rows, qvals):
        r["holm_q"] = q
        if q < FAMILY_WISE:
            r["primary_verdict"] = "Incompatible (family-controlled: coverage < 0.90 established)"
        else:
            r["primary_verdict"] = nominal_three_class(r["ci_lo"], r["ci_hi"]) + " (Holm not rejected)"

    Path("results").mkdir(exist_ok=True)
    out = pd.DataFrame(results)
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
              f"CI=[{r['ci_lo']:.4f},{r['ci_hi']:.4f}] nominal={r['nominal_three_class']} "
              f"Holm q={r['holm_q']:.4g} -> primary_verdict={r['primary_verdict']}")

if __name__ == "__main__":
    main()
