from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.stats import beta

PRIMARY_DIRECTIONS = ("tappy2mit", "mit2tappy", "gold_merged2self")
DEMOTION_THRESHOLD = 0.60

def clopper_pearson_ci(k: np.ndarray, n: int, conf: float = 0.95) -> tuple[np.ndarray, np.ndarray]:
    a = 1.0 - conf
    lo = np.where(k == 0, 0.0, beta.ppf(a / 2, k, n - k + 1))
    hi = np.where(k == n, 1.0, beta.ppf(1 - a / 2, k + 1, n - k))
    return lo, hi

def classify(lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    out = np.full(len(lo), 2, dtype=int)
    out[lo >= 0.80] = 0
    out[hi < 0.90] = 1
    return out

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tests", default="tappy2mit:n85,mit2tappy:n227,gold_merged2self:n457,mit2typd:n33")
    ap.add_argument("--true-cov", default="0.90,0.85,0.80,0.70")
    ap.add_argument("--reps", type=int, default=50_000)
    ap.add_argument("--out", default="results/power_table.csv")
    args = ap.parse_args()

    seed = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "configs" / "analysis.yml").read_text(encoding="utf-8")
    )["unit_test_seed"]
    rng = np.random.default_rng(seed)

    tests = [(name, int(n.lstrip("n"))) for name, n in (t.split(":") for t in args.tests.split(","))]
    true_covs = [float(v) for v in args.true_cov.split(",")]

    rows = []
    for name, n in tests:
        for pi in true_covs:
            k = rng.binomial(n, pi, size=args.reps)
            lo, hi = clopper_pearson_ci(k, n)
            verdict = classify(lo, hi)
            rows.append({
                "direction": name,
                "is_primary": name in PRIMARY_DIRECTIONS,
                "n": n,
                "true_coverage": pi,
                "reps": args.reps,
                "seed": seed,
                "p_compatible": float(np.mean(verdict == 0)),
                "p_incompatible": float(np.mean(verdict == 1)),
                "p_undetermined": float(np.mean(verdict == 2)),
            })
    table = pd.DataFrame(rows)
    Path(args.out).parent.mkdir(exist_ok=True)
    table.to_csv(args.out, index=False)

    demotions = []
    for name in PRIMARY_DIRECTIONS:
        row = table[(table.direction == name) & (table.true_coverage == 0.90)].iloc[0]
        if row.p_undetermined > DEMOTION_THRESHOLD:
            demotions.append(name)

    meta = {
        "rule": f"primary directions are demoted to exploratory when P(Undetermined) at pi=0.90 exceeds {DEMOTION_THRESHOLD:.0%}",
        "demotions": demotions,
        "primary_family_after_rule": [d for d in PRIMARY_DIRECTIONS if d not in demotions],
        "seed": seed,
        "reps": args.reps,
    }
    print(table.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\n[power_sim] demotion rule: survivors = {meta['primary_family_after_rule'] or 'none'}"
          f" | demoted: {demotions or 'none'}")

if __name__ == "__main__":
    main()
