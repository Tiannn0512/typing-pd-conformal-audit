"""conformal.py — split conformal 与 weighted conformal（二分类）核心实现（TODO-3.1）

冻结依据：分析冻结协议 v1 §4——Primary: split conformal（二分类，score = 1 − 真类概率）；
weighted CP（探索性，密度比权重）。
方法学参考：Vovk et al.（算法学习理论）；Tibshirani et al. 2019（协变量偏移下的 weighted
conformal，权重 w(x) = dP_target/dP_source 已知或可估）。

实现注记：
- split conformal 分位水平 k = ceil((n+1)(1−alpha))，k>n 时返回 +inf（预测全集，小校准诚实退化）
- weighted conformal 逐候选标签条件（Tibshirani 2019 式(8) 的直接实现）：
    含 y  ⟺  W_<(s_y) < (1−alpha)·(T_raw + w_test)
  其中 W_<(·) 为校准分数中**严格小于** s_y 的原始权重质量（searchsorted side="left"）、
  T_raw = Σw_cal、w_test = 该测试点密度比。论文式(8)：C(x) = {y: V_{n+1} ≤ Quantile(1−α;
  Σp_i^w δ_{V_i} + p_{n+1}^w δ_∞)}——∞ 原子仅在 w_test/Σw_cal > α 时使分位数取 +∞
  （全集）。实现经验证：w 恒 1 时与本项目 split 实现逐点一致（守卫测试
  test_6_weighted_ones_equals_split 钉死该不变量；历史上此路径曾发生尾方向反转——
  反转规则的边际覆盖率同为 1−α，覆盖率 MC 断言对其结构性免疫，逐点一致性测试是唯一防线）。
  正确性由 test_4 的独立式(8) oracle（广义逆分位数构造，与实现无共享代数）逐点对拍保证。
- 全部函数无 RNG、无拟合；分数由调用方给出（模型分数或解析后验）。
"""

from __future__ import annotations

import numpy as np


def validate_alpha(alpha):
    if isinstance(alpha, (bool, np.bool_)) or not np.isscalar(alpha):
        raise ValueError("alpha must be a finite number strictly between 0 and 1")
    try:
        value = float(alpha)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "alpha must be a finite number strictly between 0 and 1"
        ) from exc
    if not np.isfinite(value) or not 0 < value < 1:
        raise ValueError("alpha must be a finite number strictly between 0 and 1")
    return value


def validate_probs(probs):
    probs = np.asarray(probs, dtype=float)
    if probs.ndim != 2 or probs.shape[1] != 2:
        raise ValueError("Probabilities must have shape (n, 2)")
    if not np.isfinite(probs).all() or np.any((probs < 0) | (probs > 1)):
        raise ValueError("Probabilities must be finite and lie in [0, 1]")
    if not np.allclose(probs.sum(axis=1), 1.0, rtol=0, atol=1e-7):
        raise ValueError("Probability rows must sum to 1")
    return probs


def validate_labels(y, n):
    y = np.asarray(y)
    if y.ndim != 1 or len(y) != n or not np.isin(y, [0, 1]).all():
        raise ValueError(
            "Labels must be a one-dimensional array of 0 or 1 matching the rows"
        )
    return y.astype(int)


def validate_scores(scores_cal):
    scores = np.asarray(scores_cal, dtype=float)
    if scores.ndim != 1 or not len(scores):
        raise ValueError("Calibration scores must be a nonempty one-dimensional array")
    if not np.isfinite(scores).all() or np.any((scores < 0) | (scores > 1)):
        raise ValueError("LAC calibration scores must be finite and lie in [0, 1]")
    return scores


def lac_scores(probs: np.ndarray, y: np.ndarray) -> np.ndarray:
    probs = validate_probs(probs)
    y = validate_labels(y, len(probs))
    return 1.0 - probs[np.arange(len(y)), y]


def split_conformal_quantile(scores_cal: np.ndarray, alpha: float) -> float:
    scores_cal = validate_scores(scores_cal)
    alpha = validate_alpha(alpha)
    n = len(scores_cal)
    k = int(np.ceil((n + 1) * (1.0 - alpha)))
    if k > n:
        return float("inf")
    return float(np.sort(scores_cal)[k - 1])


def sets_at_quantile(probs, q):
    probs = validate_probs(probs)
    if isinstance(q, (bool, np.bool_)) or not np.isscalar(q):
        raise ValueError(
            "The LAC quantile must lie in [0, 1] or equal positive infinity"
        )
    try:
        q = float(q)
    except (TypeError, ValueError) as exc:
        raise ValueError("The LAC quantile must be numeric") from exc
    if np.isnan(q) or q < 0 or (np.isfinite(q) and q > 1):
        raise ValueError(
            "The LAC quantile must lie in [0, 1] or equal positive infinity"
        )
    return [frozenset(np.flatnonzero(1.0 - row <= q).tolist()) for row in probs]


def predict_sets_split(
    scores_cal: np.ndarray, probs_test: np.ndarray, alpha: float
) -> list[frozenset[int]]:
    return sets_at_quantile(probs_test, split_conformal_quantile(scores_cal, alpha))


class WeightedConformal:
    """Weighted LAC prediction sets using the registered strict-below mass rule."""

    def __init__(self, w_cal: np.ndarray, scores_cal: np.ndarray, alpha: float):
        scores_cal = validate_scores(scores_cal)
        w_cal = self._weights(w_cal, len(scores_cal), "Calibration")
        total = float(w_cal.sum())
        if not np.isfinite(total) or total <= 0:
            raise ValueError("Calibration weights must have a positive finite sum")
        self.n = len(scores_cal)
        self.alpha = validate_alpha(alpha)
        self._t_raw = total
        order = np.argsort(scores_cal, kind="mergesort")
        self._sorted_scores = scores_cal[order]
        self._cdf_weights = w_cal[order]
        self._cdf = np.concatenate([[0.0], np.cumsum(self._cdf_weights)])

    @staticmethod
    def _weights(weights, n, role):
        weights = np.asarray(weights, dtype=float)
        if weights.ndim != 1 or len(weights) != n:
            raise ValueError(
                f"{role} weights must be one-dimensional and match the row count"
            )
        if not np.isfinite(weights).all() or np.any(weights < 0):
            raise ValueError(f"{role} weights must be nonnegative and finite")
        return weights

    def _weighted_cdf_below(self, s: np.ndarray) -> np.ndarray:
        idx = np.searchsorted(self._sorted_scores, s, side="left")
        return self._cdf[idx]

    def predict_sets(
        self, w_test_ratio: np.ndarray, probs_test: np.ndarray
    ) -> list[frozenset[int]]:
        probs = validate_probs(probs_test)
        w_test = self._weights(w_test_ratio, len(probs), "Test")
        with np.errstate(over="ignore"):
            totals = self._t_raw + w_test
        if not np.isfinite(totals).all():
            raise ValueError("Combined calibration and test weight must remain finite")
        below = self._weighted_cdf_below(1.0 - probs)
        thresholds = (1.0 - self.alpha) * totals
        return [
            frozenset(np.flatnonzero(row < threshold).tolist())
            for row, threshold in zip(below, thresholds)
        ]
