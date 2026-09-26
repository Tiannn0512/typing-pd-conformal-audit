#!/usr/bin/env python
"""bbse_synthetic.py — 应力测试 C：BBSE 合成版 + 真实对描述性患病率（TODO-4.7）

冻结口径（analysis_plan_v1.md §10 实验C + 计划书 v1.3.2 §4.4）：BBSE 仅做合成
label shift 版（重采样构造已知患病率差——label shift 假设由构造成立，公平检验）；
真实跨库对只报患病率估计及 CI，为**描述性发现**（弱分类器下误差传播 ~10–20pp，
不做覆盖校正结论——预注册措辞）。BBSE = Black-Box Shift Estimation（Lipton,
Wang, Smola 2018）：源域按真类平均预测概率得混淆矩阵 C，目标域平均预测向量 μ̂，
解 C^T w = μ̂ 得患病率比 w，π̂_target = w ⊙ π̂_source。

实现级预声明（实现时钉死、先于首次运行；按防复发制度 §4 本脚本先行单独 commit）：
  1. 合成版几何 = mit2tappy 管线（MIT 源、tier=2、seed=1 切分、LR 主参照）：
     C 与 π̂_source 估计于源 cal（25 人）；**合成目标 = 从同一 cal 池有放回重采样**
     （按类精确计数：n_pd=round(π*·173)、n_hc=173−n_pd）——池重采样使
     p(x|y) 逐字不变、p(y)=π* 由构造成立，且 E_cal[p̂|y]=C 精确成立（同池同估计量，
     BBSE 一致性条件在池内严格成立；train 池会引入过拟合偏差，故不用）。
  2. π* 网格（升序）= {0.30, 42/82, 216/366, 0.74}：0.5122=MIT 源患病率（无移位
     锚点）、0.5902=合并自报目标实测、0.74=预注册 Tappy 实测患病率；n_t=173
     （primary 目标规模）。
  3. BBSE 估计量变体（v2 勘误后，见台账记录）：C = 按类**平均**预测概率（行=真类，
     Lipton Algorithm 1 规格），μ = C^T w 的解 w 即目标患病率（比值 γ 规格须用
     未归一化混淆矩阵，两规格不可混用）；w 截断 ≥0 → 归一化 sum 1 为预声明保护。
     v1 曾误按比值规格再乘 π̂_s（系统性 ×π̂_s 压缩），被预注册无移位锚点
     （π*=42/82 处偏差 −0.245、结构性不可能）当场拦截，v2 修正后重跑。
  4. 随机性双源（均登记）：Monte Carlo R=500 reps，numpy default_rng(1)
     （stress_seed_base，消耗顺序 = π* 升序）；bootstrap CI = percentile 95%、
     B=1000、default_rng(42)（seeds.yaml bootstrap_seed），重采样目标样本行，
     C/π̂_s 固定。经验 CI 覆盖率 = 500 reps 中 95% bootstrap CI 含真值 π* 的比例。
  5. 真实对描述性臂：三 primary 方向各用本方向管线（源 train 训练 + 源 cal 估计
     C + 全体目标 μ̂）；真值患病率取自数据本身并与冻结队列锚定断言
     （mit 42/82、tappy 133/173、merged 216/366）；仅报 π̂ + bootstrap CI + Δ真值，
     **不做覆盖校正结论**（预注册）；label-shift-only 假设在真实对上不成立
     （协变量移位并存）+ 弱分类器传播两条 caveat 随输出携带。
  6. 本实验不进任何判定链（无三分类/Holm）；产出为 RQ3 刻画素材 + 4.8 三臂
     患病率匹配（74%）的方法学前置验证。

产出：results/bbse_shift_validation.csv（4 行）+ results/bbse_real_pairs_descriptive.csv（3 行）
     + data/interim/parse_reports/bbse_report.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cp.coverage_audit import CAP, DIRECTIONS, SEED, load_pooled  # noqa: E402
from models.run_transfer import load_matrix  # noqa: E402

MC_REPS = 500
MC_SEED = 1       # seeds.yaml stress_seed_base（重采样随机化登记口径）
BOOT_B = 1000
BOOT_SEED = 42    # seeds.yaml bootstrap_seed
N_TARGET = 173
PI_GRID = (0.30, 42 / 82, 216 / 366, 0.74)
TRUE_PREV = {"tappy2mit": 42 / 82, "mit2tappy": 133 / 173, "gold_merged2self": 216 / 366}
CAVEAT = ("Descriptive only: label-shift-only assumption is violated on real pairs "
          "(covariate shift co-occurs) and the weak transfer classifier propagates "
          "~10-20pp error (pre-registered expectation). No coverage-correction "
          "conclusions are drawn from BBSE.")


def bbse_pd_prevalence(probs_src: np.ndarray, y_src: np.ndarray,
                       probs_tgt: np.ndarray) -> float:
    """Lipton et al. 2018（预声明变体，v2 勘误后）：C = 按类**平均**预测概率
    （行=真类）时，μ = C^T w 的解 w 即目标患病率向量（比值规格须用未归一化
    混淆矩阵——两种规格不可混用；v1 曾误再乘 π̂_s，被 π*=无移位锚点拦截）。
    截断 ≥0 + 归一化为预声明保护。"""
    c0 = probs_src[y_src == 0].mean(axis=0)
    c1 = probs_src[y_src == 1].mean(axis=0)
    mu = probs_tgt.mean(axis=0)
    w = np.linalg.solve(np.array([c0, c1]).T, mu)
    w = np.clip(w, 0.0, None)
    if w.sum() <= 0:
        return float("nan")
    w = w / w.sum()
    return float(w[1])


def bootstrap_ci(probs_tgt: np.ndarray, probs_src: np.ndarray, y_src: np.ndarray,
                 rng: np.random.Generator, b: int = BOOT_B) -> tuple[float, float]:
    n = len(probs_tgt)
    ests = np.array([
        bbse_pd_prevalence(probs_src, y_src, probs_tgt[rng.integers(0, n, n)])
        for _ in range(b)])
    lo, hi = np.percentile(ests, [2.5, 97.5])
    return float(lo), float(hi)


def fit_direction(cfg: dict) -> dict:
    """本方向冻结管线：源 train 训练 LR → 返回 (源 cal 概率, 源 cal 标签, 目标概率, y_t)。"""
    srcs, tgt = cfg["sources"], cfg["target"]
    tgt_datasets = {"merged_self": ["tappy", "oe"]}.get(tgt, [tgt])
    tier = min(CAP[d] for d in srcs + tgt_datasets)
    X_s, y_s = load_pooled(srcs, tier)
    if tgt == "merged_self":
        subjects = pd.read_csv("data/processed/subjects.csv")
        pool = subjects[subjects["dataset"].isin(["tappy", "oe"])]
        cols = [c for c in pool.columns if c.startswith("L1_")]
        X_t = pool[cols].to_numpy(dtype=float)
        y_t = pool["label_pd"].to_numpy(dtype=int)
    else:
        X_t, y_t = load_matrix(tgt, tier)
    assert X_s.shape[1] == X_t.shape[1]
    idx = np.arange(len(X_s))
    tr_idx, cal_idx = train_test_split(idx, test_size=0.30, random_state=SEED, stratify=y_s)
    scaler = StandardScaler().fit(X_s[tr_idx])
    clf = LogisticRegression(random_state=42, max_iter=1000)
    clf.fit(scaler.transform(X_s[tr_idx]), y_s[tr_idx])
    return {"probs_cal": clf.predict_proba(scaler.transform(X_s[cal_idx])),
            "y_cal": y_s[cal_idx],
            "probs_te": clf.predict_proba(scaler.transform(X_t)),
            "y_t": y_t}


def main() -> None:
    cfg = next(d for d in DIRECTIONS if d["direction"] == "mit2tappy")
    d = fit_direction(cfg)
    probs_cal, y_cal = d["probs_cal"], d["y_cal"]
    n_cal_pd = int((y_cal == 1).sum())

    # ---- 合成版：池重采样构造已知 π*（label shift 由构造成立）
    rng_mc = np.random.default_rng(MC_SEED)
    rng_boot = np.random.default_rng(BOOT_SEED)
    rows = []
    for pi in PI_GRID:
        n_pd = int(round(pi * N_TARGET))
        pd_pool = np.flatnonzero(y_cal == 1)
        hc_pool = np.flatnonzero(y_cal == 0)
        ests, covered = [], 0
        for _ in range(MC_REPS):
            idx_t = np.concatenate([rng_mc.choice(pd_pool, n_pd, replace=True),
                                    rng_mc.choice(hc_pool, N_TARGET - n_pd, replace=True)])
            p_tgt = probs_cal[idx_t]
            est = bbse_pd_prevalence(probs_cal, y_cal, p_tgt)
            ests.append(est)
            lo, hi = bootstrap_ci(p_tgt, probs_cal, y_cal, rng_boot)
            covered += bool(lo <= pi <= hi)
        ests = np.array(ests)
        rows.append({"pi_true": pi, "n_target_pd": n_pd, "n_target": N_TARGET,
                     "pi_hat_mean": float(ests.mean()), "bias_mean": float(ests.mean() - pi),
                     "rmse": float(np.sqrt(((ests - pi) ** 2).mean())),
                     "boot_ci_empirical_coverage": covered / MC_REPS,
                     "reps": MC_REPS, "boot_B": BOOT_B})
    val = pd.DataFrame(rows)
    val.to_csv("results/bbse_shift_validation.csv", index=False)

    # ---- 真实对描述性臂
    real_rows = []
    for direction in ("tappy2mit", "mit2tappy", "gold_merged2self"):
        cfg_r = next(dd for dd in DIRECTIONS if dd["direction"] == direction)
        dr = fit_direction(cfg_r)
        true_pi = len(dr["y_t"][dr["y_t"] == 1]) / len(dr["y_t"])
        assert abs(true_pi - TRUE_PREV[direction]) < 1e-12, \
            f"{direction} 真值患病率与冻结队列不符"
        pi_hat = bbse_pd_prevalence(dr["probs_cal"], dr["y_cal"], dr["probs_te"])
        lo, hi = bootstrap_ci(dr["probs_te"], dr["probs_cal"], dr["y_cal"], rng_boot)
        real_rows.append({"direction": direction, "n_target": len(dr["y_t"]),
                          "pi_true": true_pi, "pi_hat": pi_hat,
                          "boot_ci_lo": lo, "boot_ci_hi": hi,
                          "delta_vs_true": pi_hat - true_pi,
                          "ci_covers_true": bool(lo <= true_pi <= hi)})
    real = pd.DataFrame(real_rows)
    real.to_csv("results/bbse_real_pairs_descriptive.csv", index=False)

    print("\n=== BBSE 合成版（池重采样，label shift 由构造成立；500 reps）===")
    print(val.to_string(index=False))
    print("\n=== BBSE 真实跨库对（仅描述性）===")
    print(real.to_string(index=False))
    print(f"\n{CAVEAT}")

    predecl = __doc__.split("实现级预声明")[1].split("产出")[0].strip()
    Path("data/interim/parse_reports").mkdir(parents=True, exist_ok=True)
    Path("data/interim/parse_reports/bbse_report.json").write_text(
        json.dumps({"predeclarations": predecl, "mc_seed": MC_SEED, "boot_seed": BOOT_SEED,
                    "caveat": CAVEAT, "validation": rows, "real_pairs": real_rows},
                   indent=2, default=float), encoding="utf-8")
    print("→ results/bbse_shift_validation.csv + results/bbse_real_pairs_descriptive.csv")


if __name__ == "__main__":
    main()
