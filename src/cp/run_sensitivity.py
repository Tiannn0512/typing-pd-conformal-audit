from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cp.conformal import lac_scores, predict_sets_split, split_conformal_quantile
from cp.coverage_audit import ALPHA, CAP, DIRECTIONS, SEED, load_pooled
from cp.remediate import cp_ci
from models.run_transfer import load_matrix

L1_COLS = [f"L1_{s}_{stat}" for s in ("hold", "latency", "flight")
           for stat in ("mean", "median", "sd", "p10", "p90")]
L2TAPPY_COLS = [f"L2tappy_{s}_{h}_mean" for s in ("hold", "latency", "flight")
                for h in ("L", "R")]

def person_features_tappy(rows: pd.DataFrame) -> pd.DataFrame:
    recs = []
    for subj, g in rows.groupby("subject", observed=True):
        rec = {"subject": str(subj)}
        for sig, col in (("hold", "hold_ms"), ("latency", "latency_ms"),
                         ("flight", "flight_ms")):
            v = g[col].to_numpy(dtype="float64")
            rec[f"L1_{sig}_mean"] = float(np.mean(v))
            rec[f"L1_{sig}_median"] = float(np.median(v))
            rec[f"L1_{sig}_sd"] = float(np.std(v, ddof=1)) if len(v) > 1 else 0.0
            rec[f"L1_{sig}_p10"] = float(np.percentile(v, 10))
            rec[f"L1_{sig}_p90"] = float(np.percentile(v, 90))
        for hand in ("L", "R"):
            gh = g[g["hand_from"] == hand]
            for sig, col in (("hold", "hold_ms"), ("latency", "latency_ms"),
                             ("flight", "flight_ms")):
                rec[f"L2tappy_{sig}_{hand}_mean"] = float(gh[col].mean()) if len(gh) else np.nan
        recs.append(rec)
    return pd.DataFrame(recs)

def session_valid_features(events: pd.DataFrame, unit: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    ev = events.copy()
    if unit == "quarter":
        yy = ev["session"].str.extract(r"_(\d{2})(\d{2})$")
        ev["sess_unit"] = (ev["subject"] + "_Q20" + yy[0] + "Q"
                           + ((yy[1].astype(int) - 1) // 3 + 1).astype(str))
    else:
        ev["sess_unit"] = ev["subject"] + "_" + ev["session"]
    n = ev.groupby("sess_unit", observed=True).size()
    keep_units = set(n[n >= 100].index)
    kept = ev[ev["sess_unit"].isin(keep_units)]
    return person_features_tappy(kept), kept

def load_direction(cfg: dict) -> dict:
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
        ids_t = pool["subject_id"].to_numpy()
    else:
        X_t, y_t = load_matrix(tgt, tier)
        subjects = pd.read_csv("data/processed/subjects.csv")
        ids_t = subjects[subjects["dataset"] == tgt]["subject_id"].to_numpy()
    assert X_s.shape[1] == X_t.shape[1]
    return {"X_s": X_s, "y_s": y_s, "X_t": X_t, "y_t": y_t, "ids_t": ids_t, "tier": tier}

def run_fit(X_s, y_s, X_t, y_t, alpha: float, seed: int) -> dict:
    idx = np.arange(len(X_s))
    tr_idx, cal_idx = train_test_split(idx, test_size=0.30, random_state=seed,
                                       stratify=y_s)
    scaler = StandardScaler().fit(X_s[tr_idx])
    clf = LogisticRegression(random_state=42, max_iter=1000)
    clf.fit(scaler.transform(X_s[tr_idx]), y_s[tr_idx])
    scores_cal = lac_scores(clf.predict_proba(scaler.transform(X_s[cal_idx])), y_s[cal_idx])
    sets = predict_sets_split(scores_cal, clf.predict_proba(scaler.transform(X_t)), alpha)
    hits = np.array([t in s for t, s in zip(y_t, sets)])
    sizes = np.array([len(s) for s in sets])
    k, n = int(hits.sum()), int(len(hits))
    lo, hi = cp_ci(k, n)
    return {"k": k, "n": n, "coverage": k / n, "ci_lo": lo, "ci_hi": hi,
            "cpc_pd": float(hits[y_t == 1].mean()), "cpc_hc": float(hits[y_t == 0].mean()),
            "mean_size": float(sizes.mean()), "singleton_rate": float((sizes == 1).mean())}

def main() -> None:
    ap = argparse.ArgumentParser(description="Sensitivity batch")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    assert args.all, "--all is required (whole batch)"

    fam = pd.read_csv("results/primary_family.csv")
    rows = []

    def anchor_assert(direction: str, m: dict) -> None:
        f = fam[(fam["direction"] == direction) & (fam["model"] == "lr")].iloc[0]
        assert int(f["k"]) == m["k"] and int(f["n"]) == m["n"]
        for col in ("coverage", "cpc_pd", "cpc_hc", "mean_size", "singleton_rate"):
            assert abs(float(f[col]) - m[col]) < 1e-12, f"{direction} {col} anchor drift"

    dirs = {c["direction"]: c for c in DIRECTIONS}
    loaded = {name: load_direction(cfg) for name, cfg in dirs.items()}

    for name, d in loaded.items():
        m = run_fit(d["X_s"], d["y_s"], d["X_t"], d["y_t"], ALPHA, SEED)
        anchor_assert(name, m)
        rows.append({"variant": "anchor_seed1", "direction": name, **m})

    for name, d in loaded.items():
        m = run_fit(d["X_s"], d["y_s"], d["X_t"], d["y_t"], 0.20, SEED)
        rows.append({"variant": "alpha_020", "direction": name, **m})

    seeds_cfg = yaml.safe_load((Path(__file__).resolve().parents[2] / "configs" / "analysis.yml")
                               .read_text(encoding="utf-8"))
    seeds = list(range(1, 51))
    assert seeds == list(seeds_cfg["split_seeds"]), "50-seed list does not match analysis.yml split_seeds"
    for name, d in loaded.items():
        covs = [run_fit(d["X_s"], d["y_s"], d["X_t"], d["y_t"], ALPHA, s)["coverage"]
                for s in seeds]
        rows.append({"variant": "seeds_1_50", "direction": name, "coverage": float(np.mean(covs)),
                     "seed_std": float(np.std(covs, ddof=1)), "seed_min": float(min(covs)),
                     "seed_max": float(max(covs)), "n_seeds": 50})

    ev = pd.read_parquet("data/interim/final_digraphs.parquet")
    ev_t = ev[ev["dataset"] == "tappy"].copy()
    tappy_cohort = pd.read_csv("data/processed/subjects.csv")
    tappy_cohort = tappy_cohort[tappy_cohort["dataset"] == "tappy"]
    feat_m, _ = session_valid_features(ev_t, "month")
    feat_m = feat_m.set_index("subject")
    idx_order = tappy_cohort["subject"].astype(str).values
    mine = feat_m.loc[idx_order]
    max_diff = 0.0
    for col in L1_COLS + L2TAPPY_COLS:
        a = mine[col].to_numpy(dtype=float)
        b = tappy_cohort[col].to_numpy(dtype=float)
        atol = 1e-9 if col.startswith("L1_") else 1e-4
        assert np.allclose(a, b, rtol=0, atol=atol, equal_nan=True), \
            f"aggregator anchor failed: {col} max|diff|={np.nanmax(np.abs(a - b))}"
        both = ~(np.isnan(a) | np.isnan(b))
        if both.any():
            max_diff = max(max_diff, float(np.abs(a[both] - b[both]).max()))
    print(f"[anchor] month-unit re-aggregation reproduces Tappy L1+L2tappy from subjects.csv (21 cols; "
          f"L1 <=1e-9, L2 <=1e-4 (float32 build-time accumulation; max|diff|={max_diff:.2e}))")

    tu = pd.read_csv("data/interim/tappy_users.csv")
    tremor_ids = tu[(tu["Tremors"] == True) & (tu["Parkinsons"] == False)]["subject"].astype(str)
    ev_tr = ev_t[ev_t["subject"].astype(str).isin(set(tremor_ids))]
    tr_feat, ev_tr_kept = session_valid_features(ev_tr, "month")
    tr_feat = tr_feat[tr_feat["subject"].isin(set(tremor_ids))]
    n_dig = ev_tr_kept.groupby(ev_tr_kept["subject"].astype(str)).size()
    eligible = tr_feat[tr_feat["subject"].map(n_dig).fillna(0) >= 300].copy()
    print(f"[tremor] {len(set(tremor_ids))} candidates, {len(eligible)} pass person-level >=300")
    assert len(eligible) >= 1, "no tremor subject passes >=300; variant 3 not runnable"

    def tappy_matrix_with(extra: pd.DataFrame, labels: list[int]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        base = tappy_cohort[L1_COLS + L2TAPPY_COLS].to_numpy(dtype=float)
        y_base = tappy_cohort["label_pd"].astype(int).to_numpy()
        ex = extra[L1_COLS + L2TAPPY_COLS].to_numpy(dtype=float)
        assert not np.isnan(ex).any(), "appended rows contain NaN features"
        X = np.vstack([base, ex])
        y = np.concatenate([y_base, np.array(labels, int)])
        ids = np.concatenate([tappy_cohort["subject_id"].to_numpy(),
                              ("tappy_" + extra["subject"].astype(str)).to_numpy()])
        return X, y, ids

    for tag, lab in (("tremor_as_pd", 1), ("tremor_as_hc", 0)):
        X_tap, y_tap, _ = tappy_matrix_with(eligible, [lab] * len(eligible))
        d = loaded["tappy2mit"]
        m = run_fit(X_tap, y_tap, d["X_t"], d["y_t"], ALPHA, SEED)
        rows.append({"variant": tag, "direction": "tappy2mit", **m,
                     "note": f"source pool +{len(eligible)}"})
        d = loaded["mit2tappy"]
        m = run_fit(d["X_s"], d["y_s"], X_tap, y_tap, ALPHA, SEED)
        rows.append({"variant": tag, "direction": "mit2tappy", **m,
                     "note": f"target +{len(eligible)} (denominator includes new rows)"})
        d = loaded["gold_merged2self"]
        base = pd.read_csv("data/processed/subjects.csv")
        pool = base[base["dataset"].isin(["tappy", "oe"])]
        ex1 = eligible[L1_COLS].to_numpy(dtype=float)
        X_t2 = np.vstack([pool[[c for c in pool.columns if c.startswith("L1_")]].to_numpy(float), ex1])
        y_t2 = np.concatenate([pool["label_pd"].to_numpy(int), np.full(len(eligible), lab)])
        m = run_fit(d["X_s"], d["y_s"], X_t2, y_t2, ALPHA, SEED)
        rows.append({"variant": tag, "direction": "gold_merged2self", **m,
                     "note": f"target +{len(eligible)} (L1)"})

    feat_q, ev_q_kept = session_valid_features(ev_t, "quarter")
    feat_q = feat_q.set_index("subject")
    assert set(idx_order).issubset(feat_q.index), "quarter-unit features missing for cohort members"
    q_mat = feat_q.loc[idx_order, L1_COLS + L2TAPPY_COLS].to_numpy(dtype=float)
    assert not np.isnan(q_mat).any(), "quarter-unit features contain NaN"
    y_tap = tappy_cohort["label_pd"].astype(int).to_numpy()
    d = loaded["tappy2mit"]
    m = run_fit(q_mat, y_tap, d["X_t"], d["y_t"], ALPHA, SEED)
    rows.append({"variant": "session_quarter", "direction": "tappy2mit", **m,
                 "note": "source features re-aggregated quarterly; cohort fixed at 173"})
    d = loaded["mit2tappy"]
    m = run_fit(d["X_s"], d["y_s"], q_mat, y_tap, ALPHA, SEED)
    rows.append({"variant": "session_quarter", "direction": "mit2tappy", **m,
                 "note": "target features re-aggregated quarterly; cohort fixed at 173"})
    d = loaded["gold_merged2self"]
    pool = pd.read_csv("data/processed/subjects.csv")
    pool = pool[pool["dataset"].isin(["tappy", "oe"])]
    tappy_pos = (pool["dataset"] == "tappy").to_numpy()
    X_t3 = pool[[c for c in pool.columns if c.startswith("L1_")]].to_numpy(float).copy()
    X_t3[tappy_pos] = feat_q.loc[idx_order, L1_COLS].to_numpy(dtype=float)
    m = run_fit(d["X_s"], d["y_s"], X_t3, pool["label_pd"].to_numpy(int), ALPHA, SEED)
    rows.append({"variant": "session_quarter", "direction": "gold_merged2self", **m,
                 "note": "target Tappy slice re-aggregated quarterly; cohort fixed"})

    out = pd.DataFrame(rows)
    out.to_csv("results/sensitivity_batch.csv", index=False)

    tm = pd.read_csv("results/transfer_matrix.csv")
    tier_tab = (tm.groupby("tier").agg(n_dirs=("direction", "count"),
                                       cov_mean=("coverage_mean", "mean"),
                                       cov_min=("coverage_mean", "min"),
                                       cov_max=("coverage_mean", "max"),
                                       auc_mean=("auc_mean", "mean")).reset_index())
    tier_tab.to_csv("results/sensitivity_tier_covariate.csv", index=False)

    print("\n=== Sensitivity batch ===")
    for _, r in out.iterrows():
        cov = r.get("coverage")
        extra = f"±{r['seed_std']:.4f}" if r["variant"] == "seeds_1_50" else \
            f"CI[{r['ci_lo']:.4f},{r['ci_hi']:.4f}]" if "ci_lo" in r and pd.notna(r.get("ci_lo")) else ""
        print(f"[{r['variant']:<16}|{r['direction']:<17}] cov={cov:.4f} {extra}")
    print("\n=== Tier covariate (descriptive; 12 directions, 50-seed means) ===")
    print(tier_tab.to_string(index=False))

    print(f"\n{len(out)} rows -> results/sensitivity_batch.csv")

if __name__ == "__main__":
    main()
