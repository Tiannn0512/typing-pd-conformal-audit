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
ARMS = ("PD2HC", "HC2PD", "symmetric")
DOSES = (10, 20, 30)
SCOPES = ("cal_only", "train_cal")
DOMINANCE_TOL = 1e-12

def flip_counts(y_s: np.ndarray, arm: str, dose: int,
                rng: np.random.Generator) -> tuple[np.ndarray, int, int]:
    n_pd, n_hc = int((y_s == 1).sum()), int((y_s == 0).sum())
    if arm == "PD2HC":
        m_pd, m_hc = int(round(dose / 100 * n_pd)), 0
    elif arm == "HC2PD":
        m_pd, m_hc = 0, int(round(dose / 100 * n_hc))
    elif arm == "symmetric":
        m_pd, m_hc = int(round(dose / 100 * n_pd)), int(round(dose / 100 * n_hc))
    else:
        raise ValueError(arm)
    idx = np.concatenate([
        rng.choice(np.flatnonzero(y_s == 1), size=min(m_pd, n_pd), replace=False),
        rng.choice(np.flatnonzero(y_s == 0), size=min(m_hc, n_hc), replace=False)])
    return np.sort(idx), m_pd, m_hc

def dominance_mixture(scores_own: np.ndarray, scores_opp: np.ndarray, y: np.ndarray,
                      r_pd: float, r_hc: float) -> tuple[bool, float]:
    r = np.where(y == 1, r_pd, r_hc)
    grid = np.unique(np.concatenate([scores_own, scores_opp]))
    f_own = np.array([(scores_own <= t).mean() for t in grid])
    f_noisy = np.array([((1 - r) * (scores_own <= t) + r * (scores_opp <= t)).sum() / len(y)
                        for t in grid])
    viol = f_noisy - f_own
    return bool((viol <= DOMINANCE_TOL).all()), float(viol.max())

def theory_label(scope: str, dominance: bool) -> str:
    if scope == "none":
        return "baseline (no corruption)"
    if scope == "train_cal":
        return "n/a (model retrained; theory assumes fixed model)"
    if dominance:
        return ("mechanism: quantile inflation predicted in expectation over corruption "
                "draws -> coverage >= clean-cal pipeline; note: 1-alpha guarantee itself "
                "not directly applicable under transfer (cal/test exchangeability broken)")
    return ("no mechanism guarantee (process dominance violated; realized qhat may shift "
            "either way)")

def main() -> None:
    ap = argparse.ArgumentParser(description="Stress test A: synthetic dose-response")
    ap.add_argument("--direction", default="PD2HC,HC2PD,symmetric")
    ap.add_argument("--dose", default="10,20,30")
    ap.add_argument("--unit", default="person", choices=["person"])
    args = ap.parse_args()
    assert args.direction.split(",") == list(ARMS), "arm list must equal the fixed list"
    assert [int(d) for d in args.dose.split(",")] == list(DOSES), "dose list must equal the fixed list"
    assert args.unit == "person", "the unit is person-level source flips"

    cfg = next(d for d in DIRECTIONS if d["direction"] == "mit2tappy")
    srcs, tgt = cfg["sources"], cfg["target"]
    tier = min(CAP[d] for d in srcs + [tgt])
    X_s, y_s = load_pooled(srcs, tier)
    X_t, y_t = load_matrix(tgt, tier)
    assert X_s.shape[1] == X_t.shape[1]

    idx = np.arange(len(X_s))
    tr_idx, cal_idx = train_test_split(idx, test_size=0.30, random_state=SEED, stratify=y_s)
    n_pd, n_hc = int((y_s == 1).sum()), int((y_s == 0).sum())

    fam = pd.read_csv("results/primary_family.csv")
    f = fam[(fam["direction"] == "mit2tappy") & (fam["model"] == "lr")].iloc[0]
    rows = []
    rng = np.random.default_rng(STRESS_SEED)

    def run_cell(y_train: np.ndarray, y_cal: np.ndarray, scope: str,
                 r_pd: float, r_hc: float) -> dict:
        scaler = StandardScaler().fit(X_s[tr_idx])
        clf = LogisticRegression(random_state=42, max_iter=1000)
        clf.fit(scaler.transform(X_s[tr_idx]), y_train)
        probs_cal = clf.predict_proba(scaler.transform(X_s[cal_idx]))
        y_cal_clean = y_s[cal_idx]
        same_cal = np.array_equal(y_cal, y_cal_clean)
        scores_cal_clean = lac_scores(probs_cal, y_cal_clean)
        q = split_conformal_quantile(lac_scores(probs_cal, y_cal), ALPHA)
        q_clean = q if same_cal else split_conformal_quantile(scores_cal_clean, ALPHA)
        probs_te = clf.predict_proba(scaler.transform(X_t))
        sets = sets_at_quantile(probs_te, q)
        m = metrics(y_t, sets)
        n_cal = len(y_cal_clean)
        s_own = scores_cal_clean
        s_opp = 1.0 - probs_cal[np.arange(n_cal), 1 - y_cal_clean]
        dom_cal, viol_cal = dominance_mixture(s_own, s_opp, y_cal_clean, r_pd, r_hc)
        s_te = 1.0 - probs_te[np.arange(len(y_t)), y_t]
        s_te_opp = 1.0 - probs_te[np.arange(len(y_t)), 1 - y_t]
        dom_te, viol_te = dominance_mixture(s_te, s_te_opp, y_t, r_pd, r_hc)
        return {**m, "qhat": q, "qhat_clean": q_clean, "qhat_shift": q - q_clean,
                "dominance_cal": dom_cal, "max_cdf_violation_cal": viol_cal,
                "dominance_test_side": dom_te, "max_cdf_violation_test": viol_te,
                "theory_prediction": theory_label(scope, dom_cal)}

    row = run_cell(y_s[tr_idx], y_s[cal_idx], "none", 0.0, 0.0)
    for col, val in [("k", row["k"]), ("n", row["n"])]:
        assert int(f[col]) == val, f"baseline {col} drift"
    for col in ("coverage", "cpc_pd", "cpc_hc", "mean_size", "singleton_rate"):
        assert abs(float(f[col]) - row[col]) < 1e-12, f"baseline {col} drift"
    rows.append({"arm": "none", "dose_pct": 0, "scope": "none", "n_flipped_pd": 0,
                 "n_flipped_hc": 0, "rate_pd": 0.0, "rate_hc": 0.0,
                 **row, "note": "= primary naive anchor (asserted equal)"})

    for arm in ARMS:
        for dose in DOSES:
            flip_idx, m_pd, m_hc = flip_counts(y_s, arm, dose, rng)
            y_flip = y_s.copy()
            y_flip[flip_idx] = 1 - y_flip[flip_idx]
            r_pd, r_hc = m_pd / n_pd, m_hc / n_hc
            for scope in SCOPES:
                if scope == "cal_only":
                    y_train, y_cal = y_s[tr_idx], y_flip[cal_idx]
                else:
                    y_train, y_cal = y_flip[tr_idx], y_flip[cal_idx]
                row = run_cell(y_train, y_cal, scope, r_pd, r_hc)
                rows.append({"arm": arm, "dose_pct": dose, "scope": scope,
                             "n_flipped_pd": m_pd, "n_flipped_hc": m_hc,
                             "rate_pd": r_pd, "rate_hc": r_hc, **row,
                             "note": "flip set shared with cal_only (paired)" if scope == "train_cal"
                             else "Einbinder-aligned setting (fixed model)"})

    out = pd.DataFrame(rows)
    base_cov = float(out[(out["arm"] == "none")]["coverage"].iloc[0])
    out["coverage_delta_vs_baseline"] = out["coverage"] - base_cov
    out.to_csv("results/stress_test_a.csv", index=False)

    print("\n=== Einbinder cross-check (cal_only: fixed-model theory; transfer-corrected reading) ===")
    for arm in ARMS:
        for dose in DOSES:
            r = out[(out["arm"] == arm) & (out["dose_pct"] == dose)
                    & (out["scope"] == "cal_only")].iloc[0]
            if r["dominance_cal"]:
                flag = ("consistent (dominance => qhat rises in expectation => coverage >= baseline)"
                        if r["coverage"] >= base_cov else
                        "single-draw deviation (dominance holds in expectation; qhat moved down this draw)")
            else:
                flag = "no guarantee region (dominance fails)"
            print(f"[{arm} d={dose}%] flips PD:{r['n_flipped_pd']}/HC:{r['n_flipped_hc']} "
                  f"dominance(cal)={r['dominance_cal']}"
                  f" (max CDF violation={r['max_cdf_violation_cal']:.2e})"
                  f" qhat_shift={r['qhat_shift']:+.4f} cov={r['coverage']:.4f}"
                  f" (vs baseline {r['coverage_delta_vs_baseline']:+.4f})"
                  f" PD={r['cpc_pd']:.4f} HC={r['cpc_hc']:.4f} "
                  f"size={r['mean_size']:.2f} singleton={r['singleton_rate']:.4f} {flag}")
    print("\n=== train_cal scope (deployment reading; theory n/a) ===")
    for arm in ARMS:
        for dose in DOSES:
            r = out[(out["arm"] == arm) & (out["dose_pct"] == dose)
                    & (out["scope"] == "train_cal")].iloc[0]
            print(f"[{arm} d={dose}%] cov={r['coverage']:.4f} PD:{r['cpc_pd']:.4f} "
                  f"HC={r['cpc_hc']:.4f} singleton={r['singleton_rate']:.4f} "
                  f"rejection={r['rejection_rate']:.4f}")

    print(f"\n{len(out)} rows -> results/stress_test_a.csv")

if __name__ == "__main__":
    main()
