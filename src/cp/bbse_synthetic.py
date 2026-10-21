from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cp.coverage_audit import CAP, DIRECTIONS, SEED, load_pooled
from models.run_transfer import load_matrix

MC_REPS = 500
MC_SEED = 1
BOOT_B = 1000
BOOT_SEED = 42
N_TARGET = 173
PI_GRID = (0.30, 42 / 82, 216 / 366, 0.74)
TRUE_PREV = {"tappy2mit": 42 / 82, "mit2tappy": 133 / 173, "gold_merged2self": 216 / 366}
CAVEAT = ("Descriptive only: label-shift-only assumption is violated on real pairs "
          "(covariate shift co-occurs) and the weak transfer classifier propagates "
          "~10-20pp error. No coverage-correction "
          "conclusions are drawn from BBSE.")

def bbse_pd_prevalence(probs_src: np.ndarray, y_src: np.ndarray,
                       probs_tgt: np.ndarray) -> float:
    c0 = probs_src[y_src == 0].mean(axis=0)
    c1 = probs_src[y_src == 1].mean(axis=0)
    mu = probs_tgt.mean(axis=0)
    w = np.linalg.solve(np.array([c0, c1]).T, mu)
    w = np.clip(w, 0.0, None)
    if w.sum() <= 0:
        return float("nan")
    w = w / w.sum()
    return float(w[1])

def bootstrap_ci(probs_tgt: np.ndarray, probs_src: np.ndarray, y_src: np.ndarray,
                 rng: np.random.Generator, b: int = BOOT_B) -> tuple[float, float]:
    n = len(probs_tgt)
    ests = np.array([
        bbse_pd_prevalence(probs_src, y_src, probs_tgt[rng.integers(0, n, n)])
        for _ in range(b)])
    lo, hi = np.percentile(ests, [2.5, 97.5])
    return float(lo), float(hi)

def fit_direction(cfg: dict) -> dict:
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
    clf = LogisticRegression(random_state=42, max_iter=1000)
    clf.fit(scaler.transform(X_s[tr_idx]), y_s[tr_idx])
    return {"probs_cal": clf.predict_proba(scaler.transform(X_s[cal_idx])),
            "y_cal": y_s[cal_idx],
            "probs_te": clf.predict_proba(scaler.transform(X_t)),
            "y_t": y_t}

def main() -> None:
    cfg = next(d for d in DIRECTIONS if d["direction"] == "mit2tappy")
    d = fit_direction(cfg)
    probs_cal, y_cal = d["probs_cal"], d["y_cal"]
    n_cal_pd = int((y_cal == 1).sum())

    rng_mc = np.random.default_rng(MC_SEED)
    rng_boot = np.random.default_rng(BOOT_SEED)
    rows = []
    for pi in PI_GRID:
        n_pd = int(round(pi * N_TARGET))
        pd_pool = np.flatnonzero(y_cal == 1)
        hc_pool = np.flatnonzero(y_cal == 0)
        ests, covered = [], 0
        for _ in range(MC_REPS):
            idx_t = np.concatenate([rng_mc.choice(pd_pool, n_pd, replace=True),
                                    rng_mc.choice(hc_pool, N_TARGET - n_pd, replace=True)])
            p_tgt = probs_cal[idx_t]
            est = bbse_pd_prevalence(probs_cal, y_cal, p_tgt)
            ests.append(est)
            lo, hi = bootstrap_ci(p_tgt, probs_cal, y_cal, rng_boot)
            covered += bool(lo <= pi <= hi)
        ests = np.array(ests)
        rows.append({"pi_true": pi, "n_target_pd": n_pd, "n_target": N_TARGET,
                     "pi_hat_mean": float(ests.mean()), "bias_mean": float(ests.mean() - pi),
                     "rmse": float(np.sqrt(((ests - pi) ** 2).mean())),
                     "boot_ci_empirical_coverage": covered / MC_REPS,
                     "reps": MC_REPS, "boot_B": BOOT_B})
    val = pd.DataFrame(rows)
    val.to_csv("results/bbse_shift_validation.csv", index=False)

    real_rows = []
    for direction in ("tappy2mit", "mit2tappy", "gold_merged2self"):
        cfg_r = next(dd for dd in DIRECTIONS if dd["direction"] == direction)
        dr = fit_direction(cfg_r)
        true_pi = len(dr["y_t"][dr["y_t"] == 1]) / len(dr["y_t"])
        assert abs(true_pi - TRUE_PREV[direction]) < 1e-12, \
            f"{direction} true prevalence mismatch vs cohort"
        pi_hat = bbse_pd_prevalence(dr["probs_cal"], dr["y_cal"], dr["probs_te"])
        lo, hi = bootstrap_ci(dr["probs_te"], dr["probs_cal"], dr["y_cal"], rng_boot)
        real_rows.append({"direction": direction, "n_target": len(dr["y_t"]),
                          "pi_true": true_pi, "pi_hat": pi_hat,
                          "boot_ci_lo": lo, "boot_ci_hi": hi,
                          "delta_vs_true": pi_hat - true_pi,
                          "ci_covers_true": bool(lo <= true_pi <= hi)})
    real = pd.DataFrame(real_rows)
    real.to_csv("results/bbse_real_pairs_descriptive.csv", index=False)

    print("\n=== BBSE synthetic (pool resampling; label shift holds by construction; 500 reps) ===")
    print(val.to_string(index=False))
    print("\n=== BBSE real cross-dataset pairs (descriptive only) ===")
    print(real.to_string(index=False))
    print(f"\n{CAVEAT}")

    print("-> results/bbse_shift_validation.csv + results/bbse_real_pairs_descriptive.csv")

if __name__ == "__main__":
    main()
