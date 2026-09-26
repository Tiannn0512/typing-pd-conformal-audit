"""conformal.py — split conformal 与 weighted conformal（二分类）核心实现（TODO-3.1）

冻结依据：分析冻结协议 v1 §4——Primary: split conformal（二分类，score = 1 − 真类概率）；
weighted CP（探索性，密度比权重）。
方法学参考：Vovk et al.（算法学习理论）；Tibshirani et al. 2019（协变量偏移下的 weighted
conformal，权重 w(x) = dP_target/dP_source 已知或可估）。

实现注记：
- split conformal 分位水平 k = ceil((n+1)(1−alpha))，k>n 时返回 +inf（预测全集，小校准诚实退化）
- weighted conformal 逐候选标签条件（Tibshirani 2019 式(7)-(9) 精确阈值）：
    含 y  ⟺  W_raw(s_y) ≤ (1−alpha)·T_raw − alpha·w_test
  其中 W_raw(·) 为校准分数在原始密度比权重下的 ≤ 累计质量、T_raw = Σw_cal、w_test = 该测试点
  密度比（候选点自身质量 w_test 进入测度与分母，见式(8)-(9)）。该阈值含 w_test 项，
  具备论文的有限样本有效性；权重恒 1 时近似退化为标准 conformal 条件（差一阶自含项）。
- 全部函数无 RNG、无拟合；分数由调用方给出（模型分数或解析后验）。
"""
from __future__ import annotations

import numpy as np


def lac_scores(probs: np.ndarray, y: np.ndarray) -> np.ndarray:
    """LAC 分数 = 1 − 观测类概率。probs shape (n, k_classes)，y ∈ {0..k-1}。"""
    probs = np.asarray(probs, dtype=float)
    y = np.asarray(y, dtype=int)
    return 1.0 - probs[np.arange(len(y)), y]


def split_conformal_quantile(scores_cal: np.ndarray, alpha: float) -> float:
    """有限样本校正分位数：sort 后第 k = ceil((n+1)(1−alpha)) 个次序统计量。"""
    scores_cal = np.asarray(scores_cal, dtype=float)
    n = len(scores_cal)
    k = int(np.ceil((n + 1) * (1.0 - alpha)))
    if k > n:
        return float("inf")  # 校准集过小：诚实退化为全集
    return float(np.sort(scores_cal)[k - 1])


def predict_sets_split(scores_cal: np.ndarray, probs_test: np.ndarray,
                       alpha: float) -> list[frozenset[int]]:
    """split conformal 预测集：含 y ⟺ 1 − p_y ≤ q̂。返回长度 n_test 的 frozenset 列表。"""
    q = split_conformal_quantile(scores_cal, alpha)
    sets = []
    for row in np.asarray(probs_test, dtype=float):
        labels = {y for y, p_y in enumerate(row) if (1.0 - p_y) <= q}
        sets.append(frozenset(labels))
    return sets


class WeightedConformal:
    """协变量偏移下已知密度比权重的 weighted conformal（Tibshirani et al. 2019）。

    fit 阶段：记录校准分数与原始权重累计质量，构建加权 CDF。
    含 y 条件（Tibshirani 精确阈值，见模块 docstring）：W_raw(s_y) ≤ (1−α)·T_raw − α·w_test。
    """

    def __init__(self, w_cal: np.ndarray, scores_cal: np.ndarray, alpha: float):
        w_cal = np.asarray(w_cal, dtype=float)
        scores_cal = np.asarray(scores_cal, dtype=float)
        if np.any(~np.isfinite(w_cal)) or np.any(w_cal < 0):
            raise ValueError("权重必须非负且有限")
        if np.sum(w_cal) <= 0:
            raise ValueError("权重之和必须为正")
        n = len(scores_cal)
        self.n = n
        self.alpha = float(alpha)
        self._t_raw = float(np.sum(w_cal))
        order = np.argsort(scores_cal, kind="mergesort")
        self._sorted_scores = scores_cal[order]
        self._cdf_weights = w_cal[order]  # 原始权重的 ≤ 累计质量

    def _weighted_cdf_raw(self, s: np.ndarray) -> np.ndarray:
        """W_raw(s)：原始权重下 ≤ s 的累计质量（测试点无关，一次构建全程复用）。"""
        idx = np.searchsorted(self._sorted_scores, s, side="right")
        cdf = np.concatenate([[0.0], np.cumsum(self._cdf_weights)])
        return cdf[idx]

    def predict_sets(self, w_test_ratio: np.ndarray, probs_test: np.ndarray) -> list[frozenset[int]]:
        """w_test_ratio：测试点密度比 w(x)（进入精确阈值 (1−α)T_raw − α·w_test，见模块 docstring）。"""
        w_test = np.asarray(w_test_ratio, dtype=float)
        s_all = 1.0 - np.asarray(probs_test, dtype=float)  # (n_test, 2) 每候选标签分数
        W = self._weighted_cdf_raw(s_all.ravel()).reshape(s_all.shape)
        thresholds = (1.0 - self.alpha) * self._t_raw - self.alpha * w_test  # (n_test,)
        sets = []
        for row_w, thr in zip(W, thresholds):
            labels = {y for y, w_val in enumerate(row_w) if w_val <= thr}
            sets.append(frozenset(labels))
        return sets
