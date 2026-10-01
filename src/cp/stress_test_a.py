#!/usr/bin/env python
"""stress_test_a.py — 应力测试 A：合成剂量-反应 3×3（TODO-4.5，理论验证定位）

冻结口径（analysis_plan_v1.md §10 实验A + 计划书 v1.3.2 §4.4）：MIT 源域人级翻转
（分层随机化），方向 {PD→HC, HC→PD, 对称} × 剂量 {10, 20, 30}%，与 Einbinder et al.
（arXiv:2209.14295，JMLR CPF 2023——计划书引作 JMLR 2024）理论预测对表。
定位 = 理论验证，非方法贡献；本测试为描述性 + 理论条件核查，不做三分类判定/Holm。

Einbinder 理论要点（对表基准）：固定预训练模型 + 校准标签腐蚀设定下，若腐蚀后分数
分布对干净分数分布逐点随机占优（P(s̃≤t) ≤ P(s≤t) ∀t），则噪声分位构建的预测集对
干净测试标签覆盖仍 ≥ 1−α；对称/分散性噪声满足占优（覆盖保守），单向翻转无保证。

实现级预声明（实现时钉死、先于首次运行；按防复发制度 §4 本脚本先行单独 commit）：
  1. 迁移几何 = mit2tappy（"MIT 源域"登记读法）：tier = min(cap_mit=3, cap_tappy)=2、
     seed=1 切分、LR 主参照（CHG-P1）、α=0.10；目标 Tappy 173 人标签全程干净。
     剂量 0 基线行 = primary 审计 naive 锚点，落盘前对 results/primary_family.csv
     （lr 行）做 k/n/coverage/cpc/mean_size/singleton_rate 逐列断言。
  2. 单元 = 人（--unit person 强制）：翻转作用于源池受试者标签。剂量 d% → 翻转数
     m = round(d%·n_donor)，donor = PD(42)（PD2HC）/ HC(40)（HC2PD）/ 双侧各取
     （对称）；donor 类内简单随机抽取（rng.choice replace=False）即注册"分层随机化"
     （分层 = 类别）；对称臂 PD 取 round(d%·42)、HC 取 round(d%·40)。
     随机性 = numpy default_rng(1)（seeds.yaml stress_seed_base），按（臂：PD2HC,
     HC2PD,symmetric × 剂量升序）顺序消耗，每 (臂,剂量) 抽取一次、两个 scope 共用
     同一翻转集（配对比较）。
  3. 注入范围分档（plan §10 预登记，两档全跑）：
     cal_only = 模型在干净 train 上训练后固定，仅校准标签翻转——**Einbinder 理论
     对齐设定**（理论表仅对此档有效）；
     train_cal = 训练+校准标签同时翻转并重训——"源域腐蚀"的部署读法，理论假设
     （固定模型）不适用，如实标注 n/a，仅描述性报告。
  4. 理论对表操作化（v2 修订）：占优条件**双侧精确计算**（无额外抽样），
     按臂/剂量实现翻转率 r（m/n_donor，非名义值）构造腐蚀过程的精确混合 CDF：
     F_noisy(t) = (1/n)Σ_i[(1−r_{y_i})·1{s_own,i≤t} + r_{y_i}·1{s_opp,i≤t}]。
     **主检查在校准侧**（cal_only 档的忠实机制凭证）：占优 ⇒ q̂_noisy ≥ q̂_clean ⇒
     覆盖 ≥ 干净校准管线（迁移修正读法——1−α 名义保证本身要求 cal/test 可交换，
     迁移设定下前提不成立，故对表对象为"噪声不减覆盖"机制而非名义阈值）；
     测试侧占优（论文全腐蚀前提）作次要参考列。train_cal 档理论 n/a（模型重训）。
     过程级条件 vs 单次实现抽取的区分如实标注。
  5. 效率列口径与冻结协议 §5 一致（拒绝率 = 全集 size==2；空集率另列）；PD/HC 类
     条件覆盖随行报告（与 4.3 安全诊断衔接，描述性）。

产出：results/stress_test_a.csv（1 基线 + 9 cal_only + 9 train_cal = 19 行）
     + data/interim/parse_reports/stress_test_a_report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cp.conformal import lac_scores, predict_sets_split, split_conformal_quantile  # noqa: E402
from cp.coverage_audit import ALPHA, CAP, DIRECTIONS, SEED, load_pooled  # noqa: E402
from cp.remediate import metrics, sets_at_quantile  # noqa: E402
from models.run_transfer import load_matrix  # noqa: E402

STRESS_SEED = 1  # seeds.yaml stress_seed_base（重采样随机化登记口径）
ARMS = ("PD2HC", "HC2PD", "symmetric")
DOSES = (10, 20, 30)
SCOPES = ("cal_only", "train_cal")
DOMINANCE_TOL = 1e-12


def flip_counts(y_s: np.ndarray, arm: str, dose: int,
                rng: np.random.Generator) -> tuple[np.ndarray, int, int]:
    """按臂/剂量抽人级翻转下标：donor 类内随机（=注册分层随机化），精确 round 命中。"""
    n_pd, n_hc = int((y_s == 1).sum()), int((y_s == 0).sum())
    if arm == "PD2HC":
        m_pd, m_hc = int(round(dose / 100 * n_pd)), 0
    elif arm == "HC2PD":
        m_pd, m_hc = 0, int(round(dose / 100 * n_hc))
    elif arm == "symmetric":
        m_pd, m_hc = int(round(dose / 100 * n_pd)), int(round(dose / 100 * n_hc))
    else:
        raise ValueError(arm)
    idx = np.concatenate([
        rng.choice(np.flatnonzero(y_s == 1), size=min(m_pd, n_pd), replace=False),
        rng.choice(np.flatnonzero(y_s == 0), size=min(m_hc, n_hc), replace=False)])
    return np.sort(idx), m_pd, m_hc


def dominance_mixture(scores_own: np.ndarray, scores_opp: np.ndarray, y: np.ndarray,
                      r_pd: float, r_hc: float) -> tuple[bool, float]:
    """Einbinder 占优条件的精确混合 CDF 核查（无额外抽样），可作用于任一侧分数。

    r_cls = 该类标签被翻转的过程概率（实现率）。干净分数 s_own；被翻转到对侧标签时
    分数 s_opp。腐蚀过程下 F_noisy(t) = (1/n)Σ_i[(1−r_{y_i})·1{s_own,i≤t} +
    r_{y_i}·1{s_opp,i≤t}]；占优成立 ⟺ ∀t: F_noisy(t) ≤ F_own(t)（+容差）。
    """
    r = np.where(y == 1, r_pd, r_hc)
    grid = np.unique(np.concatenate([scores_own, scores_opp]))
    f_own = np.array([(scores_own <= t).mean() for t in grid])
    f_noisy = np.array([((1 - r) * (scores_own <= t) + r * (scores_opp <= t)).sum() / len(y)
                        for t in grid])
    viol = f_noisy - f_own
    return bool((viol <= DOMINANCE_TOL).all()), float(viol.max())


def theory_label(scope: str, dominance: bool) -> str:
    if scope == "none":
        return "baseline (no corruption)"
    if scope == "train_cal":
        return "n/a (model retrained; theory assumes fixed model)"
    if dominance:
        return ("mechanism: quantile inflation predicted in expectation over corruption "
                "draws -> coverage >= clean-cal pipeline; note: 1-alpha guarantee itself "
                "not directly applicable under transfer (cal/test exchangeability broken)")
    return ("no mechanism guarantee (process dominance violated; realized qhat may shift "
            "either way)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Stress test A: synthetic dose-response (TODO-4.5)")
    ap.add_argument("--direction", default="PD2HC,HC2PD,symmetric")
    ap.add_argument("--dose", default="10,20,30")
    ap.add_argument("--unit", default="person", choices=["person"])
    args = ap.parse_args()
    assert args.direction.split(",") == list(ARMS), "臂清单须与预注册一致"
    assert [int(d) for d in args.dose.split(",")] == list(DOSES), "剂量须与预注册一致"
    assert args.unit == "person", "注册口径为源域人级翻转"

    cfg = next(d for d in DIRECTIONS if d["direction"] == "mit2tappy")
    srcs, tgt = cfg["sources"], cfg["target"]
    tier = min(CAP[d] for d in srcs + [tgt])
    X_s, y_s = load_pooled(srcs, tier)
    X_t, y_t = load_matrix(tgt, tier)
    assert X_s.shape[1] == X_t.shape[1]

    idx = np.arange(len(X_s))
    tr_idx, cal_idx = train_test_split(idx, test_size=0.30, random_state=SEED, stratify=y_s)
    n_pd, n_hc = int((y_s == 1).sum()), int((y_s == 0).sum())

    frozen = pd.read_csv("results/primary_family.csv")
    f = frozen[(frozen["direction"] == "mit2tappy") & (frozen["model"] == "lr")].iloc[0]
    rows = []
    rng = np.random.default_rng(STRESS_SEED)  # 预声明消耗顺序：臂×剂量升序，每格一次

    def run_cell(y_train: np.ndarray, y_cal: np.ndarray, scope: str,
                 r_pd: float, r_hc: float) -> dict:
        """单 cell：给定（训练标签, 校准标签, scope, 实现翻转率）→ 全管线 + 双侧理论核查。"""
        scaler = StandardScaler().fit(X_s[tr_idx])
        clf = LogisticRegression(random_state=42, max_iter=1000)
        clf.fit(scaler.transform(X_s[tr_idx]), y_train)
        probs_cal = clf.predict_proba(scaler.transform(X_s[cal_idx]))
        y_cal_clean = y_s[cal_idx]
        same_cal = np.array_equal(y_cal, y_cal_clean)
        scores_cal_clean = lac_scores(probs_cal, y_cal_clean)
        q = split_conformal_quantile(lac_scores(probs_cal, y_cal), ALPHA)
        q_clean = q if same_cal else split_conformal_quantile(scores_cal_clean, ALPHA)
        probs_te = clf.predict_proba(scaler.transform(X_t))
        sets = sets_at_quantile(probs_te, q)
        m = metrics(y_t, sets)
        # 校准侧主检查（cal_only 的忠实机制凭证）+ 测试侧次要参考（论文全腐蚀前提）
        n_cal = len(y_cal_clean)
        s_own = scores_cal_clean
        s_opp = 1.0 - probs_cal[np.arange(n_cal), 1 - y_cal_clean]
        dom_cal, viol_cal = dominance_mixture(s_own, s_opp, y_cal_clean, r_pd, r_hc)
        s_te = 1.0 - probs_te[np.arange(len(y_t)), y_t]
        s_te_opp = 1.0 - probs_te[np.arange(len(y_t)), 1 - y_t]
        dom_te, viol_te = dominance_mixture(s_te, s_te_opp, y_t, r_pd, r_hc)
        return {**m, "qhat": q, "qhat_clean": q_clean, "qhat_shift": q - q_clean,
                "dominance_cal": dom_cal, "max_cdf_violation_cal": viol_cal,
                "dominance_test_side": dom_te, "max_cdf_violation_test": viol_te,
                "theory_prediction": theory_label(scope, dom_cal)}

    # ---- 剂量 0 基线（scope 无关；= primary naive 锚点）
    row = run_cell(y_s[tr_idx], y_s[cal_idx], "none", 0.0, 0.0)
    for col, val in [("k", row["k"]), ("n", row["n"])]:
        assert int(f[col]) == val, f"baseline {col} 漂移"
    for col in ("coverage", "cpc_pd", "cpc_hc", "mean_size", "singleton_rate"):
        assert abs(float(f[col]) - row[col]) < 1e-12, f"baseline {col} 漂移"
    rows.append({"arm": "none", "dose_pct": 0, "scope": "none", "n_flipped_pd": 0,
                 "n_flipped_hc": 0, "rate_pd": 0.0, "rate_hc": 0.0,
                 **row, "note": "= primary naive 锚点（断言一致）"})

    for arm in ARMS:
        for dose in DOSES:
            flip_idx, m_pd, m_hc = flip_counts(y_s, arm, dose, rng)
            y_flip = y_s.copy()
            y_flip[flip_idx] = 1 - y_flip[flip_idx]
            r_pd, r_hc = m_pd / n_pd, m_hc / n_hc
            for scope in SCOPES:
                if scope == "cal_only":
                    y_train, y_cal = y_s[tr_idx], y_flip[cal_idx]
                else:
                    y_train, y_cal = y_flip[tr_idx], y_flip[cal_idx]
                row = run_cell(y_train, y_cal, scope, r_pd, r_hc)
                rows.append({"arm": arm, "dose_pct": dose, "scope": scope,
                             "n_flipped_pd": m_pd, "n_flipped_hc": m_hc,
                             "rate_pd": r_pd, "rate_hc": r_hc, **row,
                             "note": "翻转集与 cal_only 共用（配对）" if scope == "train_cal"
                             else "Einbinder 对齐设定（固定模型）"})

    out = pd.DataFrame(rows)
    base_cov = float(out[(out["arm"] == "none")]["coverage"].iloc[0])
    out["coverage_delta_vs_baseline"] = out["coverage"] - base_cov
    out.to_csv("results/stress_test_a.csv", index=False)

    # ---- 对表摘要：机制预测（校准侧占优）vs 观测（cal_only 档为主表）
    print("\n=== Einbinder 对表（cal_only 档：固定模型理论对齐；迁移修正读法）===")
    for arm in ARMS:
        for dose in DOSES:
            r = out[(out["arm"] == arm) & (out["dose_pct"] == dose)
                    & (out["scope"] == "cal_only")].iloc[0]
            if r["dominance_cal"]:
                flag = ("✓ 机制一致（占优⇒期望层面 q̂ 升 ⇒ 覆盖不低于基线）"
                        if r["coverage"] >= base_cov else
                        "○ 单次实现偏离过程预测（期望层面占优成立，本次抽取 q̂ 下移）")
            else:
                flag = "— 无保证域（过程占优不成立）"
            print(f"[{arm} d={dose}%] 翻转 PD:{r['n_flipped_pd']}/HC:{r['n_flipped_hc']} "
                  f"占优(cal)={r['dominance_cal']}"
                  f"（max ΔCDF={r['max_cdf_violation_cal']:.2e}）"
                  f"q̂偏移={r['qhat_shift']:+.4f} 覆盖={r['coverage']:.4f}"
                  f"（Δ基线{r['coverage_delta_vs_baseline']:+.4f}）"
                  f"PD:{r['cpc_pd']:.4f} HC:{r['cpc_hc']:.4f} "
                  f"集合大小={r['mean_size']:.2f} 单例率={r['singleton_rate']:.4f} {flag}")
    print("\n=== train_cal 档（部署读法，理论 n/a）===")
    for arm in ARMS:
        for dose in DOSES:
            r = out[(out["arm"] == arm) & (out["dose_pct"] == dose)
                    & (out["scope"] == "train_cal")].iloc[0]
            print(f"[{arm} d={dose}%] 覆盖={r['coverage']:.4f} PD:{r['cpc_pd']:.4f} "
                  f"HC:{r['cpc_hc']:.4f} 单例率={r['singleton_rate']:.4f} "
                  f"拒绝率={r['rejection_rate']:.4f}")

    predecl = __doc__.split("实现级预声明")[1].split("产出")[0].strip()
    Path("data/interim/parse_reports").mkdir(parents=True, exist_ok=True)
    Path("data/interim/parse_reports/stress_test_a_report.json").write_text(
        json.dumps({"predeclarations": predecl, "stress_seed": STRESS_SEED,
                    "theory_ref": "arXiv:2209.14295 (Einbinder et al., JMLR CPF 2023)",
                    "rows": rows}, indent=2, default=float), encoding="utf-8")
    print(f"\n共 {len(out)} 行 → results/stress_test_a.csv")


if __name__ == "__main__":
    main()
