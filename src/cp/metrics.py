"""Prediction-set metrics shared by the registered analyses."""

import numpy as np
from scipy.stats import beta
from cp.conformal import validate_labels


def cp_ci(k, n, conf=0.95):
    if conf != 0.95:
        raise ValueError("The registered Clopper-Pearson interval has confidence 0.95")
    if (
        not isinstance(k, (int, np.integer))
        or not isinstance(n, (int, np.integer))
        or not 0 <= k <= n
    ):
        raise ValueError("Binomial counts must satisfy 0 <= k <= n")
    if n == 0:
        return float("nan"), float("nan")
    # Keep the registered literal tails to preserve the original floating-point results.
    lo = float(beta.ppf(0.025, k, n - k + 1)) if k > 0 else 0.0
    hi = float(beta.ppf(0.975, k + 1, n - k)) if k < n else 1.0
    return lo, hi


def set_outcomes(y, sets):
    y = validate_labels(y, len(sets))
    if not len(y):
        raise ValueError("Evaluation requires at least one labelled subject")
    if any(not isinstance(s, (set, frozenset)) or not s <= {0, 1} for s in sets):
        raise ValueError("Prediction sets must be subsets of {0, 1}")
    return (
        y,
        np.array([label in s for label, s in zip(y, sets)]),
        np.array([len(s) for s in sets]),
    )


def metrics(y, sets):
    y, hits, sizes = set_outcomes(y, sets)
    k, n = int(hits.sum()), len(hits)
    lo, hi = cp_ci(k, n)
    return {
        "k": k,
        "n": n,
        "coverage": k / n,
        "ci_lo": lo,
        "ci_hi": hi,
        "cpc_pd": float(hits[y == 1].mean()) if np.any(y == 1) else float("nan"),
        "cpc_hc": float(hits[y == 0].mean()) if np.any(y == 0) else float("nan"),
        "mean_size": float(sizes.mean()),
        "singleton_rate": float((sizes == 1).mean()),
        "rejection_rate": float((sizes == 2).mean()),
        "empty_rate": float((sizes == 0).mean()),
    }
