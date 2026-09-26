"""test_cp_synthetic.py — 合成单元测试三件套（TODO-3.1，课题可信度根基）

①合成击键流特征提取复原：手工事件序列 → digraph 三信号派生 → L1 统计，对照 numpy 闭式真值
②可交换合成数据上 split CP 覆盖落 90%±3σ：固定解析后验分数，隔离 CP 逻辑本身
③已知密度比漂移下 weighted CP 覆盖复原：解析比率 w(x)=exp(x−0.5)（source N(0,1)→target N(1,1)），
  同一分数函数下 naive split 覆盖破损、weighted 恢复 1−α

全部确定性（seeds 来自 configs/seeds.yaml 的 unit_test_seed）；无模型拟合（解析分数），
统计功效来自大样本重复。MAPIE 对拍为一次性验证（scripts/mapie_crosscheck.py），不在本文件。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cp.conformal import (  # noqa: E402
    WeightedConformal,
    lac_scores,
    predict_sets_split,
    split_conformal_quantile,
)
from features.build_tables import person_features  # noqa: E402

SEED = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "configs" / "seeds.yaml").read_text(encoding="utf-8")
)["unit_test_seed"]
ALPHA = 0.10


# ---------- ① 特征提取复原 ----------

def test_1a_digraph_derivation_recovery():
    """共享派生函数 add_digraph_timing：手工事件序列逐值复原（含真实 rollover 负 latency）。

    2026-09-26 审核必修2：原版在测试内复抄公式（零项目代码覆盖），现调用
    src/data/digraph_derive.add_digraph_timing（parse_mit/typd/oe 实际使用的实现，
    重构无损已由三库 parquet md5 逐字节一致证明）。
    """
    from data.digraph_derive import add_digraph_timing

    # 案例 A：常规序列（latency 全正）
    df_a = pd.DataFrame({"press_ms": [100.0, 260.0, 500.0], "release_ms": [180.0, 300.0, 560.0]})
    out_a = add_digraph_timing(df_a, "press_ms", "release_ms", group_cols=None, hold_col="hold_ms")
    assert np.allclose(out_a["hold_ms"], [80.0, 40.0, 60.0])
    assert np.allclose(out_a["latency_ms"][1:], [80.0, 200.0]) and np.isnan(out_a["latency_ms"][0])
    assert np.allclose(out_a["flight_ms"][1:], [160.0, 240.0]) and np.isnan(out_a["flight_ms"][0])

    # 案例 B：真实 rollover——事件 3 在事件 2 release 之前按下 → 负 latency 忠实穿透
    # （派生层不做清洗；负值由 Phase 2 预登记规则 hold/latency≤0 剔除）
    df_b = pd.DataFrame({"press_ms": [100.0, 260.0, 280.0], "release_ms": [180.0, 300.0, 400.0]})
    out_b = add_digraph_timing(df_b, "press_ms", "release_ms", group_cols=None, hold_col="hold_ms")
    assert out_b["latency_ms"][2] == -20.0  # 280 − 300 < 0
    assert out_b["flight_ms"][2] == 20.0   # 280 − 260

    # 案例 C：分组派生（跨组不连键）——组首行 NaN，跨组不得产生假 digraph
    df_c = pd.DataFrame({
        "subject": ["A", "A", "B", "B"],
        "press_ms": [10.0, 50.0, 900.0, 950.0],
        "release_ms": [20.0, 70.0, 910.0, 980.0],
    })
    out_c = add_digraph_timing(df_c, "press_ms", "release_ms",
                               group_cols=["subject"], hold_col="hold_ms")
    assert out_c["latency_ms"].isna().tolist() == [True, False, True, False]
    assert out_c["latency_ms"][1] == 30.0  # A 组内：50 − 20
    assert out_c["latency_ms"][3] == 40.0  # B 组内：950 − 910（不是 900 − 70）


def test_1b_l1_stats_recovery(tmp_path):
    """person_features 的 L1 统计对照 numpy 闭式真值（合成 digraph 表）。"""
    rng = np.random.default_rng(SEED)
    n = 500
    df = pd.DataFrame({
        "dataset": "mit",
        "subject": 1,
        "session": "s1",
        "char": "a",
        "char_from": None,
        "char_to": "a",
        "press_ms": np.arange(n, dtype=float) * 300,
        "release_ms": np.arange(n, dtype=float) * 300 + 100,
        "hold_ms": rng.uniform(50, 150, n),
        "latency_ms": rng.uniform(20, 200, n),
        "flight_ms": np.nan,  # 由派生关系回填：flight = latency + 前一行 hold
    })
    df["flight_ms"] = df["latency_ms"] + df["hold_ms"].shift(1).fillna(120.0)
    df["rep"], df["exp"], df["keep_flag"] = 1, 14, True

    feats = person_features(df, "mit")
    assert len(feats) == 1
    row = feats.iloc[0]
    for sig, col in (("hold", "hold_ms"), ("latency", "latency_ms"), ("flight", "flight_ms")):
        v = df[col].to_numpy()
        assert row[f"L1_{sig}_mean"] == pytest.approx(np.mean(v), abs=1e-9)
        assert row[f"L1_{sig}_median"] == pytest.approx(np.median(v), abs=1e-9)
        assert row[f"L1_{sig}_sd"] == pytest.approx(np.std(v, ddof=1), abs=1e-9)
        assert row[f"L1_{sig}_p10"] == pytest.approx(np.percentile(v, 10), abs=1e-9)
        assert row[f"L1_{sig}_p90"] == pytest.approx(np.percentile(v, 90), abs=1e-9)


# ---------- ② 可交换 split CP 覆盖 ----------

def _analytic_probs(x: np.ndarray) -> np.ndarray:
    """固定解析后验 p(y=1|x)=sigmoid(2x)——隔离 CP 逻辑与模型拟合噪声。"""
    p1 = 1.0 / (1.0 + np.exp(-2.0 * x))
    return np.stack([1.0 - p1, p1], axis=1)


def test_2_split_cp_exchangeable_coverage_90():
    rng = np.random.default_rng(SEED)
    trials, n_cal, n_test = 200, 1000, 2000
    coverages = []
    for _ in range(trials):
        x_cal = rng.standard_normal(n_cal)
        y_cal = (rng.random(n_cal) < _analytic_probs(x_cal)[:, 1]).astype(int)
        x_test = rng.standard_normal(n_test)
        y_test = (rng.random(n_test) < _analytic_probs(x_test)[:, 1]).astype(int)
        scores_cal = lac_scores(_analytic_probs(x_cal), y_cal)
        sets = predict_sets_split(scores_cal, _analytic_probs(x_test), ALPHA)
        coverages.append(np.mean([y in s for y, s in zip(y_test, sets)]))
    cov = np.array(coverages)
    # 校准/测试独立性下的二项噪声：σ_mean = sqrt(0.9·0.1/(n_test·trials))
    # 均值检验：标准误用经验 std（trial 间方差 = 二项分量 + 校准分位波动分量，
    # 2026-09-26 实测 std≈0.0106 vs 纯二项 0.0067）
    se = cov.std(ddof=1) / np.sqrt(trials)
    assert abs(cov.mean() - (1 - ALPHA)) <= 3 * se,         f"split CP 覆盖 {cov.mean():.4f} 偏离 {1 - ALPHA} 超过 3·se({3 * se:.4f})"
    # 离散度 sanity：纯二项 std 的 0.5-3 倍带
    sigma_trial = np.sqrt(0.9 * 0.1 / n_test)
    assert 0.5 * sigma_trial <= cov.std(ddof=1) <= 3 * sigma_trial


# ---------- ③ 已知密度比漂移下 weighted CP 复原 ----------

def _density_ratio(x: np.ndarray) -> np.ndarray:
    """source N(0,1) → target N(1,1)：w(x) = exp(x − 0.5)（解析精确）。"""
    return np.exp(x - 0.5)


def test_3_weighted_cp_covariate_shift_recovery():
    rng = np.random.default_rng(SEED)
    trials, n_cal, n_test = 100, 2000, 3000
    cov_w, cov_naive = [], []
    for _ in range(trials):
        x_cal = rng.standard_normal(n_cal)
        y_cal = (rng.random(n_cal) < _analytic_probs(x_cal)[:, 1]).astype(int)
        x_test = rng.standard_normal(n_test) + 1.0  # 目标域均值偏移
        y_test = (rng.random(n_test) < _analytic_probs(x_test)[:, 1]).astype(int)

        scores_cal = lac_scores(_analytic_probs(x_cal), y_cal)
        probs_test = _analytic_probs(x_test)

        wc = WeightedConformal(_density_ratio(x_cal), scores_cal, ALPHA)
        sets_w = wc.predict_sets(_density_ratio(x_test), probs_test)
        sets_n = predict_sets_split(scores_cal, probs_test, ALPHA)
        cov_w.append(np.mean([y in s for y, s in zip(y_test, sets_w)]))
        cov_naive.append(np.mean([y in s for y, s in zip(y_test, sets_n)]))

    cov_w = np.array(cov_w)
    cov_naive = np.array(cov_naive)
    sigma_w = cov_w.std(ddof=1) / np.sqrt(trials)
    # weighted 复原 1−α（3·经验 se：解析比率零估计误差）
    assert abs(cov_w.mean() - (1 - ALPHA)) <= 3 * sigma_w,         f"weighted CP 覆盖 {cov_w.mean():.4f} 未复原 {1 - ALPHA}"
    # naive 在同一偏移下必须显著失准（方向随偏移构造：均值上移→过覆盖；取方向无关幅度）
    sigma_n = cov_naive.std(ddof=1) / np.sqrt(trials)
    assert abs(cov_naive.mean() - (1 - ALPHA)) >= max(5 * sigma_n, 0.01),         f"naive split 在偏移下覆盖 {cov_naive.mean():.4f} 未失准？"
