#!/usr/bin/env python
"""Exercise the registered transfer pipeline without printing coverage values."""
import argparse
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cp.conformal import split_conformal_quantile
from cp.metrics import set_outcomes
from models.common import direction_data, fit_transfer
from protocol import ALPHA, CAP, DIRECTIONS, SEED


def run_smoke(scenario, seed=SEED):
    cfg = next((d for d in DIRECTIONS if d["direction"] == scenario), None)
    if cfg is None:
        source, target = scenario.split("2", 1)
        if source not in CAP or target not in CAP or source == target:
            raise ValueError("The smoke scenario must name a supported source and target")
        cfg = {"direction": scenario, "sources": [source], "target": target}
    X_s, y_s, X_t, y_t, tier = direction_data(cfg)
    fitted = fit_transfer(X_s, y_s, X_t, seed=seed)
    train, calibration = fitted["train_indices"], fitted["calibration_indices"]
    q = split_conformal_quantile(fitted["scores_cal"], ALPHA)
    _, hits, sizes = set_outcomes(y_t, fitted["sets"])
    checks = [
        ("Aligned feature matrices", X_s.shape[1] == X_t.shape[1] and len(X_t) > 0),
        ("Disjoint training and calibration subjects", not np.intersect1d(train, calibration).size),
        ("Probability rows sum to one", np.allclose(fitted["probs_te"].sum(axis=1), 1.0)),
        ("LAC quantile is in [0, 1] or positive infinity", (np.isfinite(q) and 0 <= q <= 1) or np.isposinf(q)),
        ("One prediction set per target subject", len(sizes) == len(y_t)),
        ("Coverage can be calculated", np.isfinite(hits.mean())),
    ]
    messages = [f"{label}: {'PASS' if ok else 'FAIL'}" for label, ok in checks]
    return all(ok for _, ok in checks), messages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="tappy2mit")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    ok, messages = run_smoke(args.scenario, args.seed)
    for message in messages:
        print(message)
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
