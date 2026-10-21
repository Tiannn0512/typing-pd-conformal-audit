from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from lightgbm import LGBMClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

MODEL_SEED = 42

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/baseline_mit.csv")
    args = ap.parse_args()

    seeds_path = Path(__file__).resolve().parents[2] / "configs" / "analysis.yml"
    seeds_cfg = yaml.safe_load(open(seeds_path, encoding="utf-8"))
    split_seeds = seeds_cfg["split_seeds"]

    subjects = pd.read_csv("data/processed/subjects.csv")
    mit = subjects[subjects["dataset"] == "mit"].copy()
    assert len(mit) == 82, f"mit row count {len(mit)} != 82 (cohort table)"
    feature_cols = [c for c in mit.columns if c.startswith("L1_")]
    assert len(feature_cols) == 15
    X_all = mit[feature_cols].to_numpy(dtype=float)
    y_all = mit["label_pd"].to_numpy(dtype=int)
    assert not np.isnan(X_all).any()

    rows = []
    for seed in split_seeds:
        X_tr, X_tmp, y_tr, y_tmp = train_test_split(
            X_all, y_all, test_size=0.60, random_state=seed, stratify=y_all)
        X_va, X_te, y_va, y_te = train_test_split(
            X_tmp, y_tmp, test_size=0.50, random_state=seed, stratify=y_tmp)
        scaler = StandardScaler().fit(X_tr)
        X_tr_s, X_va_s, X_te_s = scaler.transform(X_tr), scaler.transform(X_va), scaler.transform(X_te)

        clf = LogisticRegression(random_state=MODEL_SEED, max_iter=1000).fit(X_tr_s, y_tr)
        auc_va = roc_auc_score(y_va, clf.predict_proba(X_va_s)[:, 1])
        auc_te = roc_auc_score(y_te, clf.predict_proba(X_te_s)[:, 1])
        rows.append({"seed": seed, "model": "lr", "auc_val": auc_va, "auc_test": auc_te,
                     "lgbm_min_child_samples": None, "lgbm_max_depth": None,
                     "n_train": len(y_tr), "n_val": len(y_va), "n_test": len(y_te)})

        grid = [(5, 2), (5, 3), (10, 2), (10, 3)]
        best = None
        for mcs, depth in grid:
            clf = LGBMClassifier(random_state=MODEL_SEED, verbose=-1,
                                 min_child_samples=mcs, max_depth=depth).fit(X_tr_s, y_tr)
            v = roc_auc_score(y_va, clf.predict_proba(X_va_s)[:, 1])
            if best is None or v > best[0]:
                best = (v, mcs, depth)
        val_sel, mcs_sel, depth_sel = best
        clf = LGBMClassifier(random_state=MODEL_SEED, verbose=-1,
                             min_child_samples=mcs_sel, max_depth=depth_sel).fit(X_tr_s, y_tr)
        auc_te = roc_auc_score(y_te, clf.predict_proba(X_te_s)[:, 1])
        rows.append({"seed": seed, "model": "lightgbm", "auc_val": val_sel, "auc_test": auc_te,
                     "lgbm_min_child_samples": mcs_sel, "lgbm_max_depth": depth_sel,
                     "n_train": len(y_tr), "n_val": len(y_va), "n_test": len(y_te)})

    res = pd.DataFrame(rows)
    Path(args.out).parent.mkdir(exist_ok=True)
    res.to_csv(args.out, index=False)

    summary = {}
    for model_name in ("lr", "lightgbm"):
        sub = res[res["model"] == model_name]
        summary[model_name] = {
            "mean_auc_test": float(sub["auc_test"].mean()),
            "median_auc_test": float(sub["auc_test"].median()),
            "std_auc_test": float(sub["auc_test"].std(ddof=1)),
            "se_mean": float(sub["auc_test"].std(ddof=1) / np.sqrt(len(sub))),
            "mean_auc_val": float(sub["auc_val"].mean()),
        }
    gate_stat = summary["lightgbm"]["mean_auc_test"]
    gate_lo, gate_hi = 0.75, 0.91
    gate_pass = gate_lo <= gate_stat <= gate_hi
    print(f"[baseline_mit] seeds={len(split_seeds)} LR mean={summary['lr']['mean_auc_test']:.4f} "
          f"LightGBM mean={gate_stat:.4f} (median={summary['lightgbm']['median_auc_test']:.4f}, "
          f"se={summary['lightgbm']['se_mean']:.4f})")
    if gate_pass:
        print(f"[baseline_mit] GATE [0.75, 0.91]: PASS")
    else:
        print(f"[baseline_mit] GATE [0.75, 0.91]: FAIL "
              f"(documented outcome: LightGBM fails the in-domain gate; LR is the primary model)")

if __name__ == "__main__":
    main()
