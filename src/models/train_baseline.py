#!/usr/bin/env python
"""MIT baseline under DEC-B3b, with the approved CHG-P1 continuation policy."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime import require
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

from protocol import load_seeds
from models.common import L1_COLS, fit_model, record_fit


def load_baseline_config(path):
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    require(isinstance(cfg, dict), "Baseline configuration must be a mapping")
    parameters = cfg.get("parameters", {})
    expected = {
        "dataset": "mit",
        "feature_tier": 1,
        "expected_subjects": 82,
        "temporary_fraction": 0.60,
        "test_fraction_of_temporary": 0.50,
        "lr_max_iter": 1000,
        "lightgbm_grid": [[5, 2], [5, 3], [10, 2], [10, 3]],
        "historical_gate": [0.75, 0.91],
        "accepted_primary": "lr",
        "amendment": "CHG-P1",
    }
    require(
        parameters == expected,
        "Baseline parameters must match DEC-B3b and the accepted CHG-P1 amendment",
    )
    return parameters


def gate_decision(summary, parameters, mode):
    require(mode in ("registered", "historical"), "Unknown gate mode")
    low, high = parameters["historical_gate"]
    statistic = summary["lightgbm"]["mean_auc_test"]
    passed = low <= statistic <= high
    return {
        "rule": "lightgbm mean_auc_test in [0.75, 0.91]",
        "stat": statistic,
        "pass": passed,
        "enforced": mode == "historical",
        "accepted_primary": parameters["accepted_primary"],
        "amendment": parameters["amendment"],
        "continue_analysis": passed or mode == "registered",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Reproduce the DEC-B3b baseline; CHG-P1 selects LR for subsequent analyses"
    )
    parser.add_argument("--config", default="configs/baseline_mit.yaml")
    parser.add_argument("--out", default="results/baseline_mit.csv")
    parser.add_argument(
        "--gate-mode",
        choices=("registered", "historical"),
        default="registered",
        help="Historical mode exits nonzero on the original LightGBM gate failure",
    )
    args = parser.parse_args()
    parameters = load_baseline_config(args.config)
    seeds = load_seeds()["split_seeds"]
    subjects = pd.read_csv("data/processed/subjects.csv")
    mit = subjects[subjects["dataset"] == parameters["dataset"]].copy()
    require(
        len(mit) == parameters["expected_subjects"],
        "MIT subject count differs from the registered cohort",
    )
    require(
        mit["subject_id"].notna().all() and mit["subject_id"].is_unique,
        "MIT subject IDs must be unique",
    )
    X_all = mit[L1_COLS].to_numpy(dtype=float)
    from cp.conformal import validate_labels

    y_all = validate_labels(mit["label_pd"].to_numpy(), len(mit))
    require(np.isfinite(X_all).all(), "Baseline features must be finite")
    rows = []
    for seed in seeds:
        train, temporary = train_test_split(
            np.arange(len(y_all)),
            test_size=parameters["temporary_fraction"],
            random_state=seed,
            stratify=y_all,
        )
        validation, test = train_test_split(
            temporary,
            test_size=parameters["test_fraction_of_temporary"],
            random_state=seed,
            stratify=y_all[temporary],
        )
        scaler, clf = fit_model(
            X_all[train], y_all[train], max_iter=parameters["lr_max_iter"]
        )
        probabilities = clf.predict_proba(scaler.transform(X_all[test]))
        rows.append(
            {
                "seed": seed,
                "model": "lr",
                "auc_val": roc_auc_score(
                    y_all[validation],
                    clf.predict_proba(scaler.transform(X_all[validation]))[:, 1],
                ),
                "auc_test": roc_auc_score(y_all[test], probabilities[:, 1]),
                "lgbm_min_child_samples": None,
                "lgbm_max_depth": None,
                "n_train": len(train),
                "n_val": len(validation),
                "n_test": len(test),
            }
        )
        record_fit(
            scaler,
            clf,
            {
                "train_indices": train,
                "validation_indices": validation,
                "test_indices": test,
                "source_features": X_all,
                "source_labels": y_all,
                "probs_test": probabilities,
            },
        )
        best = None
        for mcs, depth in parameters["lightgbm_grid"]:
            scaler, candidate = fit_model(
                X_all[train],
                y_all[train],
                "lgbm",
                min_child_samples=mcs,
                max_depth=depth,
            )
            value = roc_auc_score(
                y_all[validation],
                candidate.predict_proba(scaler.transform(X_all[validation]))[:, 1],
            )
            if best is None or value > best[0]:
                best = value, mcs, depth
        value, mcs, depth = best
        scaler, clf = fit_model(
            X_all[train], y_all[train], "lgbm", min_child_samples=mcs, max_depth=depth
        )
        probabilities = clf.predict_proba(scaler.transform(X_all[test]))
        rows.append(
            {
                "seed": seed,
                "model": "lightgbm",
                "auc_val": value,
                "auc_test": roc_auc_score(y_all[test], probabilities[:, 1]),
                "lgbm_min_child_samples": mcs,
                "lgbm_max_depth": depth,
                "n_train": len(train),
                "n_val": len(validation),
                "n_test": len(test),
            }
        )
        record_fit(
            scaler,
            clf,
            {
                "train_indices": train,
                "validation_indices": validation,
                "test_indices": test,
                "source_features": X_all,
                "source_labels": y_all,
                "probs_test": probabilities,
            },
        )
    result = pd.DataFrame(rows)
    summary = {}
    for name in ("lr", "lightgbm"):
        sub = result[result["model"] == name]
        summary[name] = {
            "mean_auc_test": float(sub["auc_test"].mean()),
            "median_auc_test": float(sub["auc_test"].median()),
            "std_auc_test": float(sub["auc_test"].std(ddof=1)),
            "se_mean": float(sub["auc_test"].std(ddof=1) / np.sqrt(len(sub))),
            "mean_auc_val": float(sub["auc_val"].mean()),
        }
    gate = gate_decision(summary, parameters, args.gate_mode)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.out, index=False)
    report = {
        "effective_parameters": parameters,
        "split_seeds": seeds,
        "n_subjects": len(mit),
        "n_pd": int(y_all.sum()),
        "n_hc": int(len(y_all) - y_all.sum()),
        "features": L1_COLS,
        "summary": summary,
        "gate": gate,
    }
    report_path = Path("data/interim/parse_reports/baseline_mit_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"summary": summary, "gate": gate}, indent=2))
    if not gate["continue_analysis"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
