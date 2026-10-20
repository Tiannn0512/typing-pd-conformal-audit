"""Target calibration sampling and the registered density-ratio estimator."""

import numpy as np
from sklearn.linear_model import LogisticRegression
from protocol import MODEL_SEED
from runtime import require

W_CLIP_QUANTILE = 0.99


def stratified_draw(y: np.ndarray, m: int, rng: np.random.Generator) -> np.ndarray:
    """类别分层比例抽取 m 个下标（PD 先 round，HC 取余），精确命中 m。"""
    n_pd = int((y == 1).sum())
    m_pd = min(max(int(round(m * n_pd / len(y))), 0), m)
    m_hc = m - m_pd
    m_pd = min(m_pd, n_pd)
    m_hc = min(m_hc, int((y == 0).sum()))
    idx = np.concatenate(
        [
            rng.choice(np.flatnonzero(y == 1), size=m_pd, replace=False),
            rng.choice(np.flatnonzero(y == 0), size=m_hc, replace=False),
        ]
    )
    require(len(idx) == m, f"分层抽取未命中 m={m}")
    return np.sort(idx)


def protocol_budget_split(n: int, n_tappy: int, m: int) -> tuple[int, int]:
    m_tappy = int(round(m * n_tappy / n))
    return m_tappy, m - m_tappy


def density_ratio_weights(
    X_s_tr: np.ndarray,
    X_cal: np.ndarray,
    X_t: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """预登记密度比估计：域分类器 LR（balanced，同主参照配置）→ w=p/(1−p)，
    合池 p99 截断，c=1/mean(w_test) 归一（同一 c 作用 cal/test）。"""
    X_dom = np.vstack([X_s_tr, X_t])
    y_dom = np.concatenate([np.zeros(len(X_s_tr), int), np.ones(len(X_t), int)])
    dom = LogisticRegression(
        class_weight="balanced", random_state=MODEL_SEED, max_iter=1000
    )
    dom.fit(X_dom, y_dom)

    def odds(X):
        p = dom.predict_proba(X)[:, 1]
        p = np.clip(p, 1e-12, 1 - 1e-12)
        return p / (1.0 - p)

    w_cal_raw, w_te_raw = odds(X_cal), odds(X_t)
    cap = float(np.quantile(np.concatenate([w_cal_raw, w_te_raw]), W_CLIP_QUANTILE))
    frac_clipped = float((w_te_raw >= cap).mean())
    w_cal, w_te = np.minimum(w_cal_raw, cap), np.minimum(w_te_raw, cap)
    c = 1.0 / float(w_te.mean())
    w_cal, w_te = w_cal * c, w_te * c
    stats = {
        "w_mean": float(w_te.mean()),
        "w_median": float(np.median(w_te)),
        "w_p95": float(np.quantile(w_te, 0.95)),
        "w_p99": float(np.quantile(w_te, 0.99)),
        "w_max": float(w_te.max()),
        "frac_clipped": frac_clipped,
        "w_cap_raw": cap,
    }
    return w_cal, w_te, stats
