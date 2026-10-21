from __future__ import annotations

import numpy as np

def lac_scores(probs: np.ndarray, y: np.ndarray) -> np.ndarray:
    probs = np.asarray(probs, dtype=float)
    y = np.asarray(y, dtype=int)
    return 1.0 - probs[np.arange(len(y)), y]

def split_conformal_quantile(scores_cal: np.ndarray, alpha: float) -> float:
    scores_cal = np.asarray(scores_cal, dtype=float)
    n = len(scores_cal)
    if n == 0:
        raise ValueError("empty calibration set (almost surely an upstream zero-row merge); refusing silent degeneration to full sets")
    k = int(np.ceil((n + 1) * (1.0 - alpha)))
    if k > n:
        return float("inf")
    return float(np.sort(scores_cal)[k - 1])

def predict_sets_split(scores_cal: np.ndarray, probs_test: np.ndarray,
                       alpha: float) -> list[frozenset[int]]:
    q = split_conformal_quantile(scores_cal, alpha)
    sets = []
    for row in np.asarray(probs_test, dtype=float):
        labels = {y for y, p_y in enumerate(row) if (1.0 - p_y) <= q}
        sets.append(frozenset(labels))
    return sets

class WeightedConformal:

    def __init__(self, w_cal: np.ndarray, scores_cal: np.ndarray, alpha: float):
        w_cal = np.asarray(w_cal, dtype=float)
        scores_cal = np.asarray(scores_cal, dtype=float)
        if np.any(~np.isfinite(w_cal)) or np.any(w_cal < 0):
            raise ValueError("weights must be non-negative and finite")
        if np.sum(w_cal) <= 0:
            raise ValueError("weight sum must be positive")
        n = len(scores_cal)
        self.n = n
        self.alpha = float(alpha)
        self._t_raw = float(np.sum(w_cal))
        order = np.argsort(scores_cal, kind="mergesort")
        self._sorted_scores = scores_cal[order]
        self._cdf_weights = w_cal[order]

    def _weighted_cdf_below(self, s: np.ndarray) -> np.ndarray:
        idx = np.searchsorted(self._sorted_scores, s, side="left")
        cdf = np.concatenate([[0.0], np.cumsum(self._cdf_weights)])
        return cdf[idx]

    def predict_sets(self, w_test_ratio: np.ndarray, probs_test: np.ndarray) -> list[frozenset[int]]:
        w_test = np.asarray(w_test_ratio, dtype=float)
        if np.any(~np.isfinite(w_test)) or np.any(w_test < 0):
            raise ValueError("test-point weights must be non-negative and finite")
        s_all = 1.0 - np.asarray(probs_test, dtype=float)
        if np.any(~np.isfinite(s_all)):
            raise ValueError("probs_test contains non-finite values")
        W_below = self._weighted_cdf_below(s_all.ravel()).reshape(s_all.shape)
        thresholds = (1.0 - self.alpha) * (self._t_raw + w_test)
        sets = []
        for row_w, thr in zip(W_below, thresholds):
            labels = {y for y, w_val in enumerate(row_w) if w_val < thr}
            sets.append(frozenset(labels))
        return sets
