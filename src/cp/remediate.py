from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import beta as _beta
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cp.conformal import (
    WeightedConformal,
    lac_scores,
    predict_sets_split,
    split_conformal_quantile,
)
from cp.coverage_audit import ALPHA, CAP, DIRECTIONS, SEED, load_pooled
from models.run_transfer import load_matrix

DRAW_SEED = 1
BUDGET_GRADIENT = (5, 10, 20, 30)
AUDIT_THRESHOLD = 0.80
W_CLIP_QUANTILE = 0.99

def cp_ci(k: int, n: int) -> tuple[float, float]:
    lo = float(_beta.ppf(0.025, k, n - k + 1)) if k > 0 else 0.0
    hi = float(_beta.ppf(0.975, k + 1, n - k)) if k < n else 1.0
    return lo, hi

def sets_at_quantile(probs: np.ndarray, q: float) -> list[frozenset[int]]:
    return [frozenset(y for y in (0, 1) if (1.0 - row[y]) <= q) for row in np.asarray(probs, float)]

def metrics(y: np.ndarray, sets: list[frozenset[int]]) -> dict:
    hits = np.array([t in s for t, s in zip(y, sets)])
    sizes = np.array([len(s) for s in sets])
    k, n = int(hits.sum()), int(len(hits))
    lo, hi = cp_ci(k, n)
    return {"k": k, "n": n, "coverage": k / n, "ci_lo": lo, "ci_hi": hi,
            "cpc_pd": float(hits[y == 1].mean()), "cpc_hc": float(hits[y == 0].mean()),
            "mean_size": float(sizes.mean()), "singleton_rate": float((sizes == 1).mean()),
            "rejection_rate": float((sizes == 2).mean()), "empty_rate": float((sizes == 0).mean())}

def stratified_draw(y: np.ndarray, m: int, rng: np.random.Generator) -> np.ndarray:
    n_pd = int((y == 1).sum())
    m_pd = min(max(int(round(m * n_pd / len(y))), 0), m)
    m_hc = m - m_pd
    m_pd = min(m_pd, n_pd)
    m_hc = min(m_hc, int((y == 0).sum()))
    idx = np.concatenate([rng.choice(np.flatnonzero(y == 1), size=m_pd, replace=False),
                          rng.choice(np.flatnonzero(y == 0), size=m_hc, replace=False)])
    assert len(idx) == m, f"stratified draw missed m={m}"
    return np.sort(idx)

def protocol_budget_split(n: int, n_tappy: int, m: int) -> tuple[int, int]:
    m_tappy = int(round(m * n_tappy / n))
    return m_tappy, m - m_tappy

def density_ratio_weights(X_s_tr: np.ndarray, X_cal: np.ndarray, X_t: np.ndarray,
                          ) -> tuple[np.ndarray, np.ndarray, dict]:
    X_dom = np.vstack([X_s_tr, X_t])
    y_dom = np.concatenate([np.zeros(len(X_s_tr), int), np.ones(len(X_t), int)])
    dom = LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000)
    dom.fit(X_dom, y_dom)

    def odds(X):
        p = dom.predict_proba(X)[:, 1]
        p = np.clip(p, 1e-12, 1 - 1e-12)
        return p / (1.0 - p)

    w_cal_raw, w_te_raw = odds(X_cal), odds(X_t)
    cap = float(np.quantile(np.concatenate([w_cal_raw, w_te_raw]), W_CLIP_QUANTILE))
    frac_clipped = float((w_te_raw >= cap).mean())
    w_cal, w_te = np.minimum(w_cal_raw, cap), np.minimum(w_te_raw, cap)
    c = 1.0 / float(w_te.mean())
    w_cal, w_te = w_cal * c, w_te * c
    stats = {"w_mean": float(w_te.mean()), "w_median": float(np.median(w_te)),
             "w_p95": float(np.quantile(w_te, 0.95)), "w_p99": float(np.quantile(w_te, 0.99)),
             "w_max": float(w_te.max()), "frac_clipped": frac_clipped,
             "w_cap_raw": cap}
    return w_cal, w_te, stats

def main() -> None:
    ap = argparse.ArgumentParser(description="Remediation chain + recovery-cost table")
    ap.add_argument("--methods", default="target_recalib,weighted_cp,group_weighted")
    ap.add_argument("--budget", default="0,5,10,20,30")
    args = ap.parse_args()
    methods = args.methods.split(",")
    budgets = [int(b) for b in args.budget.split(",")]
    assert "target_recalib" in methods, "the recalibration chain is the body of the recovery-cost table"

    fam = pd.read_csv("results/primary_family.csv")
    rows = []
    rng = np.random.default_rng(DRAW_SEED)

    for cfg in DIRECTIONS:
        srcs, tgt = cfg["sources"], cfg["target"]
        tgt_datasets = {"merged_self": ["tappy", "oe"]}.get(tgt, [tgt])
        tier = min(CAP[d] for d in srcs + tgt_datasets)
        X_s, y_s = load_pooled(srcs, tier)
        if tgt == "merged_self":
            subjects = pd.read_csv("data/processed/subjects.csv")
            pool = subjects[subjects["dataset"].isin(["tappy", "oe"])].reset_index(drop=True)
            cols = [c for c in pool.columns if c.startswith("L1_")]
            X_t = pool[cols].to_numpy(dtype=float)
            y_t = pool["label_pd"].to_numpy(dtype=int)
            proto_t = pool["dataset"].to_numpy()
        else:
            X_t, y_t = load_matrix(tgt, tier)
            proto_t = np.array([tgt] * len(y_t), dtype=object)
        assert X_s.shape[1] == X_t.shape[1]

        idx = np.arange(len(X_s))
        tr_idx, cal_idx = train_test_split(idx, test_size=0.30, random_state=SEED, stratify=y_s)
        scaler = StandardScaler().fit(X_s[tr_idx])
        X_tr_s, X_cal_s, X_te_s = (scaler.transform(X_s[tr_idx]), scaler.transform(X_s[cal_idx]),
                                   scaler.transform(X_t))
        clf = LogisticRegression(random_state=42, max_iter=1000)
        clf.fit(X_tr_s, y_s[tr_idx])
        scores_cal = lac_scores(clf.predict_proba(X_cal_s), y_s[cal_idx])
        probs_te = clf.predict_proba(X_te_s)
        direction = cfg["direction"]
        n_target = len(y_t)

        sets_naive = predict_sets_split(scores_cal, probs_te, ALPHA)
        m_naive = metrics(y_t, sets_naive)
        f = fam[(fam["direction"] == direction) & (fam["model"] == "lr")].iloc[0]
        for col, val in [("k", m_naive["k"]), ("n", m_naive["n"])]:
            assert int(f[col]) == val, f"{direction} naive {col} drift"
        for col in ("coverage", "cpc_pd", "cpc_hc", "mean_size", "singleton_rate"):
            assert abs(float(f[col]) - m_naive[col]) < 1e-12, f"{direction} naive {col} drift"
        rows.append({"direction": direction, "method": "naive_cp", "budget_pct": 0,
                     "n_target_labels": 0, **m_naive, "qhat_inf": False,
                     "note": "= primary audit anchor row (asserted equal)"})

        if "weighted_cp" in methods:
            w_cal, w_te, w_stats = density_ratio_weights(X_tr_s, X_cal_s, X_te_s)
            wc = WeightedConformal(w_cal, scores_cal, ALPHA)
            sets_w = wc.predict_sets(w_te, probs_te)
            rows.append({"direction": direction, "method": "weighted_cp", "budget_pct": 0,
                         "n_target_labels": 0, **metrics(y_t, sets_w), "qhat_inf": False,
                         "note": f"domain-classifier density ratio, pooled p99 clip={w_stats['w_cap_raw']:.3g}",
                         **w_stats})

        for b in budgets:
            if b <= 0:
                continue
            m = max(2, int(round(b / 100 * n_target)))
            if tgt == "merged_self":
                is_tappy = proto_t == "tappy"
                pos_tappy, pos_oe = np.flatnonzero(is_tappy), np.flatnonzero(~is_tappy)
                m_tappy, m_oe = protocol_budget_split(n_target, len(pos_tappy), m)
                bud = np.concatenate([pos_tappy[stratified_draw(y_t[pos_tappy], m_tappy, rng)],
                                      pos_oe[stratified_draw(y_t[pos_oe], m_oe, rng)]])
                bud = np.sort(bud)
            else:
                bud = stratified_draw(y_t, m, rng)
            test_mask = np.ones(n_target, bool)
            test_mask[bud] = False
            y_test, probs_test = y_t[test_mask], probs_te[test_mask]
            scores_bud = lac_scores(clf.predict_proba(X_te_s[bud]), y_t[bud])

            q = split_conformal_quantile(scores_bud, ALPHA)
            sets_rec = sets_at_quantile(probs_test, q)
            note = "target-budget single-quantile recalibration" + ("; qhat=inf, degeneration to full sets" if np.isinf(q) else "")
            rows.append({"direction": direction, "method": "target_recalib", "budget_pct": b,
                         "n_target_labels": int(len(bud)), **metrics(y_test, sets_rec),
                         "qhat_inf": bool(np.isinf(q)), "note": note})

            if "group_weighted" in methods and tgt == "merged_self":
                sets_grp = np.empty(int(test_mask.sum()), dtype=object)
                grp_q_inf = False
                for p_name in ("tappy", "oe"):
                    pmask = proto_t[test_mask] == p_name
                    pmask_bud = proto_t[bud] == p_name
                    q_p = split_conformal_quantile(scores_bud[pmask_bud], ALPHA)
                    grp_q_inf = grp_q_inf or bool(np.isinf(q_p))
                    sets_grp[pmask] = np.array(sets_at_quantile(probs_test[pmask], q_p),
                                               dtype=object)
                sets_grp = list(sets_grp)
                rows.append({"direction": direction, "method": "group_weighted",
                             "budget_pct": b, "n_target_labels": int(len(bud)),
                             **metrics(y_test, sets_grp), "qhat_inf": grp_q_inf,
                             "note": "protocol-conditional quantile (per-protocol budgets for tappy/oe)"})
            elif "group_weighted" in methods:
                rows.append({"direction": direction, "method": "group_weighted",
                             "budget_pct": b, "n_target_labels": int(len(bud)),
                             **metrics(y_test, sets_rec), "qhat_inf": bool(np.isinf(q)),
                             "note": "single-protocol target: identical to target_recalib by construction (protocol-conditional degenerates to it)"})

    out = pd.DataFrame(rows)
    out.to_csv("results/recovery_cost_table.csv", index=False)

    print(f"\n=== Recovery criterion (audit threshold {AUDIT_THRESHOLD}) ===")
    recovery = {}
    for direction in out["direction"].unique():
        sub = out[(out["direction"] == direction) & (out["method"] == "target_recalib")]
        nd = sub[~sub["qhat_inf"]]
        deg = sub[sub["qhat_inf"] & (sub["coverage"] >= AUDIT_THRESHOLD)]
        p = nd[nd["coverage"] >= AUDIT_THRESHOLD]
        c = nd[nd["ci_lo"] >= AUDIT_THRESHOLD]
        w_row = out[(out["direction"] == direction) & (out["method"] == "weighted_cp")].iloc[0]
        recovery[direction] = {
            "min_budget_point_ge_080_nondegenerate": int(p["budget_pct"].min()) if len(p) else None,
            "min_budget_cilo_ge_080_nondegenerate": int(c["budget_pct"].min()) if len(c) else None,
            "degenerate_budgets_nominal_only": sorted(int(b) for b in deg["budget_pct"]),
            "weighted_cp_0budget": {"coverage": float(w_row["coverage"]),
                                    "rejection_rate": float(w_row["rejection_rate"])},
            "note": None if len(c) else ("CI lower bound >= 0.80 not reached within the budget gradient"
                                         if len(nd) else "all budget rows degenerate")}
        r = recovery[direction]
        wtxt = (f"weighted CP (0 labels): point estimate cov={r['weighted_cp_0budget']['coverage']:.4f}"
                f"/rejection={r['weighted_cp_0budget']['rejection_rate']:.2f}")
        ptxt = f"{r['min_budget_point_ge_080_nondegenerate']}%" \
            if r["min_budget_point_ge_080_nondegenerate"] is not None else "not reached within the gradient"
        ctxt = f"{r['min_budget_cilo_ge_080_nondegenerate']}%" \
            if r["min_budget_cilo_ge_080_nondegenerate"] is not None else "not reached within the gradient"
        dtxt = f"; degenerate rows {r['degenerate_budgets_nominal_only']} nominal-only" \
            if r["degenerate_budgets_nominal_only"] else ""
        print(f"[{direction}] non-degenerate: min budget with point>=0.80 = {ptxt}; min budget with ci_lo>=0.80 = "
              f"{ctxt}{dtxt}; {wtxt}")

    print(f"\n{len(out)} rows -> results/recovery_cost_table.csv")

if __name__ == "__main__":
    main()
