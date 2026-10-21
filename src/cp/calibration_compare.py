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
from cp.conformal import (
    WeightedConformal,
    lac_scores,
    predict_sets_split,
    split_conformal_quantile,
)
from cp.coverage_audit import ALPHA, CAP, DIRECTIONS, SEED, load_pooled
from cp.remediate import (
    density_ratio_weights,
    metrics,
    protocol_budget_split,
    sets_at_quantile,
    stratified_draw,
)
from models.run_transfer import load_matrix

DRAW_SEED = 1
BUDGETS = (5, 10, 20, 30)
DELTA_COLS = ("coverage", "cpc_pd", "cpc_hc", "mean_size", "singleton_rate")

def main() -> None:
    ap = argparse.ArgumentParser(description="Stress test B: three-way calibration comparison")
    ap.add_argument("--methods", default="gold_direct,target_recalib,weighted_cp")
    ap.add_argument("--directions", default="primary")
    args = ap.parse_args()
    assert args.methods.split(",") == ["gold_direct", "target_recalib", "weighted_cp"]
    assert args.directions == "primary", "scope = the three primary directions"

    fam = pd.read_csv("results/primary_family.csv")
    rc = pd.read_csv("results/recovery_cost_table.csv")

    def rc_row(direction: str, method: str, budget: int | None) -> pd.Series:
        m = (rc["direction"] == direction) & (rc["method"] == method)
        if budget is not None:
            m &= rc["budget_pct"] == budget
        out = rc[m]
        assert len(out) == 1, f"missing recovery_cost row: {direction}/{method}/{budget}"
        return out.iloc[0]

    def assert_match(direction: str, method: str, budget: int | None,
                     m: dict, q_inf: bool) -> None:
        f = rc_row(direction, method, budget)
        assert int(f["k"]) == m["k"] and int(f["n"]) == m["n"]
        assert bool(f["qhat_inf"]) == q_inf
        for col in ("coverage", "ci_lo", "ci_hi", "cpc_pd", "cpc_hc",
                    "mean_size", "singleton_rate", "rejection_rate"):
            assert abs(float(f[col]) - m[col]) < 1e-12, \
                f"{direction}/{method}/b={budget} {col} drift vs remediation chain"

    rng = np.random.default_rng(DRAW_SEED)
    RC_NAME = {"gold_direct": "naive_cp", "weighted_cp": "weighted_cp",
               "target_recalib": "target_recalib"}
    rows = []
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
        direction, n_target = cfg["direction"], len(y_t)

        def emit(method: str, budget: int, n_labels: int, m: dict, q_inf: bool,
                 note: str) -> None:
            if method == "gold_direct":
                deltas = {f"delta_{c}": 0.0 for c in DELTA_COLS}
            else:
                gold = next(r for r in rows
                            if r["direction"] == direction and r["method"] == "gold_direct")
                deltas = {f"delta_{c}": m[c] - gold[c] for c in DELTA_COLS}
            rows.append({"direction": direction, "method": method, "budget_pct": budget,
                         "n_target_labels": n_labels, **m, **deltas, "qhat_inf": q_inf,
                         "point_ge_090": bool(m["coverage"] >= 0.90),
                         "point_ge_080": bool(m["coverage"] >= 0.80),
                         "cilo_ge_080": bool(m["ci_lo"] >= 0.80),
                         "note": note})
            assert_match(direction, RC_NAME[method], budget, m, q_inf)

        sets_g = predict_sets_split(scores_cal, probs_te, ALPHA)
        m_g = metrics(y_t, sets_g)
        f = fam[(fam["direction"] == direction) & (fam["model"] == "lr")].iloc[0]
        assert int(f["k"]) == m_g["k"] and int(f["n"]) == m_g["n"]
        for col in ("coverage", "cpc_pd", "cpc_hc", "mean_size", "singleton_rate"):
            assert abs(float(f[col]) - m_g[col]) < 1e-12, f"{direction} gold_direct drift"
        emit("gold_direct", 0, 0, m_g, False, "= naive anchor (asserted vs primary and remediation chain)")

        if "weighted_cp" in args.methods.split(","):
            w_cal, w_te, w_stats = density_ratio_weights(X_tr_s, X_cal_s, X_te_s)
            sets_w = WeightedConformal(w_cal, scores_cal, ALPHA).predict_sets(w_te, probs_te)
            m_w = metrics(y_t, sets_w)
            emit("weighted_cp", 0, 0, m_w, False,
                 f"domain-classifier density ratio, pooled p99 clip={w_stats['w_cap_raw']:.3g} (as remediation chain)")

        if "target_recalib" in args.methods.split(","):
            for b in BUDGETS:
                mb = max(2, int(round(b / 100 * n_target)))
                if tgt == "merged_self":
                    is_tappy = proto_t == "tappy"
                    pos_tappy, pos_oe = np.flatnonzero(is_tappy), np.flatnonzero(~is_tappy)
                    m_tappy, m_oe = protocol_budget_split(n_target, len(pos_tappy), mb)
                    bud = np.concatenate(
                        [pos_tappy[stratified_draw(y_t[pos_tappy], m_tappy, rng)],
                         pos_oe[stratified_draw(y_t[pos_oe], m_oe, rng)]])
                    bud = np.sort(bud)
                else:
                    bud = stratified_draw(y_t, mb, rng)
                test_mask = np.ones(n_target, bool)
                test_mask[bud] = False
                q = split_conformal_quantile(
                    lac_scores(clf.predict_proba(X_te_s[bud]), y_t[bud]), ALPHA)
                m_r = metrics(y_t[test_mask], sets_at_quantile(probs_te[test_mask], q))
                emit("target_recalib", b, int(len(bud)), m_r, bool(np.isinf(q)),
                     "target-budget single-quantile recalibration (same draws as remediation chain)")

    out = pd.DataFrame(rows)
    out.to_csv("results/calibration_comparison.csv", index=False)

    print("\n=== Three-way calibration (real transfer; delta = arm - gold_direct) ===")
    for direction in out["direction"].unique():
        sub = out[out["direction"] == direction]
        g = sub[sub["method"] == "gold_direct"].iloc[0]
        print(f"\n[{direction}] gold_direct cov={g['coverage']:.4f} PD={g['cpc_pd']:.4f} "
              f"HC={g['cpc_hc']:.4f}")
        for _, r in sub[sub["method"] != "gold_direct"].iterrows():
            bl = f" b={int(r['budget_pct'])}%({int(r['n_target_labels'])} labels)" \
                if r["method"] == "target_recalib" else "(0 labels)"
            deg = " [degenerate: full sets, nominal flags meaningless]" if r["qhat_inf"] else ""
            print(f"  {r['method']:<15}{bl:<16} cov={r['coverage']:.4f}"
                  f" (delta {r['delta_coverage']:+.4f}) PD={r['cpc_pd']:.4f}"
                  f" (delta {r['delta_cpc_pd']:+.4f}) HC={r['cpc_hc']:.4f}"
                  f" (delta {r['delta_cpc_hc']:+.4f})"
                  f" point>=0.80={r['point_ge_080']} ci_lo>=0.80={r['cilo_ge_080']}"
                  f" rejection={r['rejection_rate']:.2f}{deg}")

    print(f"\n{len(out)} rows -> results/calibration_comparison.csv")

if __name__ == "__main__":
    main()
