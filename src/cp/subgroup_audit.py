from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cp.conformal import lac_scores, predict_sets_split
from cp.coverage_audit import ALPHA, CAP, DIRECTIONS, SEED, load_pooled
from cp.remediate import cp_ci
from models.run_transfer import load_matrix, tier_columns

MIT_SEX_CAVEAT = ("MIT public data has no sex field; literature figure: the female share is ~17pp higher among controls"
                  "; the sex stratum is not computable for this direction")

def load_target_with_ids(cfg: dict) -> dict:
    srcs, tgt = cfg["sources"], cfg["target"]
    tgt_datasets = {"merged_self": ["tappy", "oe"]}.get(tgt, [tgt])
    tier = min(CAP[d] for d in srcs + tgt_datasets)
    X_s, y_s = load_pooled(srcs, tier)
    subjects = pd.read_csv("data/processed/subjects.csv")
    if tgt == "merged_self":
        pool = subjects[subjects["dataset"].isin(["tappy", "oe"])].copy()
        cols = [c for c in pool.columns if c.startswith("L1_")]
        X_t = pool[cols].to_numpy(dtype=float)
        y_t = pool["label_pd"].to_numpy(dtype=int)
        ids = pool["subject_id"].to_numpy()
        origin = pool["dataset"].to_numpy()
    else:
        sub = subjects[subjects["dataset"] == tgt]
        l2l3 = pd.read_csv("data/processed/subjects_l2l3.csv")
        merged = sub.merge(l2l3, on="subject_id", how="left")
        cols = tier_columns(tgt, tier)
        X_t = merged[cols].to_numpy(dtype=float)
        y_t = merged["label_pd"].to_numpy(dtype=int)
        ids = merged["subject_id"].to_numpy()
        origin = np.array([tgt] * len(y_t), dtype=object)
    assert X_s.shape[1] == X_t.shape[1] and not np.isnan(X_t).any()
    return {"X_s": X_s, "y_s": y_s, "X_t": X_t, "y_t": y_t, "ids": ids,
            "origin": origin, "tier": tier}

def tappy_demo() -> pd.DataFrame:
    tu = pd.read_csv("data/interim/tappy_users.csv")
    subjects = pd.read_csv("data/processed/subjects.csv")
    tap = subjects[subjects["dataset"] == "tappy"][["subject_id", "subject"]]
    tap = tap.merge(tu[["subject", "Gender", "BirthYear"]], on="subject", how="left")
    sp = pd.read_parquet("data/processed/sessions.parquet")
    taps = sp[sp["dataset"] == "tappy"]
    yy = taps["session"].str.extract(r"_(\d{2})\d{2}$")[0]
    taps = taps.assign(yr=2000 + yy.astype(int))
    med_year = taps.groupby("subject")["yr"].median()
    byear = pd.to_numeric(tap["BirthYear"], errors="coerce")
    tap["sex"] = tap["Gender"]
    tap["age"] = tap["subject"].map(med_year) - byear
    return tap[["subject_id", "sex", "age"]]

def main() -> None:
    ap = argparse.ArgumentParser(description="Subgroup coverage audit (descriptive)")
    ap.add_argument("--strata", default="sex,age_median")
    ap.add_argument("--directions", default="primary")
    args = ap.parse_args()
    assert args.strata.split(",") == ["sex", "age_median"], "strata must be sex,age_median"
    assert args.directions == "primary"

    demo = tappy_demo()
    fam = pd.read_csv("results/primary_family.csv")

    rows, avail = [], []
    for cfg in DIRECTIONS:
        d = load_target_with_ids(cfg)
        direction, n = cfg["direction"], len(d["y_t"])
        idx = np.arange(len(d["X_s"]))
        tr_idx, cal_idx = train_test_split(idx, test_size=0.30, random_state=SEED,
                                           stratify=d["y_s"])
        scaler = StandardScaler().fit(d["X_s"][tr_idx])
        clf = LogisticRegression(random_state=42, max_iter=1000)
        clf.fit(scaler.transform(d["X_s"][tr_idx]), d["y_s"][tr_idx])
        sets = predict_sets_split(
            lac_scores(clf.predict_proba(scaler.transform(d["X_s"][cal_idx])),
                       d["y_s"][cal_idx]),
            clf.predict_proba(scaler.transform(d["X_t"])), ALPHA)
        hits = np.array([t in s for t, s in zip(d["y_t"], sets)])
        sizes = np.array([len(s) for s in sets])
        k = int(hits.sum())
        f = fam[(fam["direction"] == direction) & (fam["model"] == "lr")].iloc[0]
        assert int(f["k"]) == k and int(f["n"]) == n, f"{direction} k/n drift"
        for col in ("coverage", "cpc_pd", "cpc_hc", "mean_size", "singleton_rate"):
            assert abs(float(f[col]) - (hits.mean() if col == "coverage" else
                                        hits[d["y_t"] == 1].mean() if col == "cpc_pd" else
                                        hits[d["y_t"] == 0].mean() if col == "cpc_hc" else
                                        sizes.mean() if col == "mean_size" else
                                        (sizes == 1).mean())) < 1e-12, f"{direction} {col} drift"

        tgt_ids = pd.DataFrame({"subject_id": d["ids"], "origin": d["origin"],
                                "hit": hits, "size": sizes})
        merged_ids = tgt_ids.merge(demo, on="subject_id", how="left")

        tappy_mask = merged_ids["origin"].isin(["tappy"])
        sex_ok = merged_ids["sex"].notna()
        age_ok = merged_ids["age"].notna()
        if direction == "tappy2mit":
            avail.append({"direction": direction, "stratum": "sex",
                          "status": "unavailable_no_field",
                          "covers_n": 0, "of_target": n, "note": MIT_SEX_CAVEAT})
            avail.append({"direction": direction, "stratum": "age_median",
                          "status": "unavailable_no_field",
                          "covers_n": 0, "of_target": n,
                          "note": "MIT public data has no birth-year/age field"})
        else:
            for stratum in ("sex", "age_median"):
                m = sex_ok if stratum == "sex" else age_ok
                avail.append({"direction": direction, "stratum": stratum,
                              "status": "computed_partial",
                              "covers_n": int(m.sum()), "of_target": n,
                              "note": f"computable for Tappy-origin only (OE has no demographics); "
                                      f"covers {int(m.sum())}/{n}"})

        def emit(stratum: str, level: str, mask: np.ndarray, note: str) -> None:
            hits_m, sizes_m, y_m = hits[mask], sizes[mask], d["y_t"][mask]
            k_m, n_m = int(hits_m.sum()), int(mask.sum())
            lo, hi = cp_ci(k_m, n_m)
            rows.append({"direction": direction, "stratum": stratum, "level": level,
                         "n": n_m, "n_pd": int(y_m.sum()), "k": k_m,
                         "coverage": k_m / n_m, "ci_lo": lo, "ci_hi": hi,
                         "mean_size": float(sizes_m.mean()),
                         "singleton_rate": float((sizes_m == 1).mean()),
                         "covers_n": n_m, "of_target": n, "note": note})

        if direction != "tappy2mit":
            med = float(merged_ids.loc[age_ok, "age"].median())
            emit("sex", "Male", (merged_ids["sex"] == "Male").to_numpy(),
                 "self-report Gender (tappy_users); Tappy sub-slice")
            emit("sex", "Female", (merged_ids["sex"] == "Female").to_numpy(),
                 "self-report Gender (tappy_users); Tappy sub-slice")
            emit("age_median", "age<=median", (merged_ids["age"] <= med).to_numpy(),
                 f"median session year - BirthYear; median of non-missing = {med:.1f}")
            emit("age_median", "age>median", (merged_ids["age"] > med).to_numpy(),
                 f"median session year - BirthYear; median of non-missing = {med:.1f}")
            n_unknown = int((~age_ok).sum())
            n_oe = int((~tappy_mask).sum())
            emit("age_median", "unknown", (~age_ok).to_numpy(),
                 f"OE no field {n_oe} + Tappy BirthYear missing {n_unknown - n_oe}")

    out = pd.DataFrame(rows)
    out.to_csv("results/subgroup_coverage_audit.csv", index=False)
    pd.DataFrame(avail).to_csv("results/subgroup_strata_availability.csv", index=False)

    print("\n=== Subgroup-conditional coverage (descriptive; LR primary, seed=1 split) ===")
    for _, r in out.iterrows():
        print(f"[{r['direction']}|{r['stratum']}={r['level']}] n={int(r['n'])}"
              f" (PD {int(r['n_pd'])}) cov={r['coverage']:.4f} "
              f"CI[{r['ci_lo']:.4f},{r['ci_hi']:.4f}] size={r['mean_size']:.3f}")
    for a in avail:
        if a["status"].startswith("unavailable"):
            print(f"[{a['direction']}|{a['stratum']}] {a['status']} - {a['note']}")
    caveat = ("Descriptive observation only: marginal CP does not extend to "
              "group-conditional guarantees (Rafe 2026). "
              "Small strata carry wide CIs.")
    print(f"\n{caveat}")

    print(f"{len(out)} stratum rows -> results/subgroup_coverage_audit.csv")

if __name__ == "__main__":
    main()
