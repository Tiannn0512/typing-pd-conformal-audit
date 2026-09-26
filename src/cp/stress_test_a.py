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
  4. 理论对表操作化（cal_only 档）：占优条件在目标测试分数上**精确计算**（无额外
     抽样）——按臂/剂量的实现翻转率 r（m/n_donor，非名义值），腐蚀过程下测试分数
     的精确混合 CDF：F_noisy(t) = (1/n)Σ_i[(1−r_{y_i})·1{s_i≤t} + r_{y_i}·
     1{s_{1−y_i}≤t}]；dominance_holds = ∀t∈观测分数格点：F_noisy(t) ≤ F_clean(t)+1e-12。
     占优成立 → 理论预测"覆盖 ≥ 0.90 有保证"；不成立 → "无保证（非分散性腐蚀）"；
     train_cal 档 → "n/a（模型重训，理论假设固定模型不成立）"。观测覆盖与保证声明
     的一致性逐格呈现（对表交付物）。
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
from cp.remediate import cp_ci, metrics, sets_at_quantile  # noqa: E402

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


def dominance_check(probs_te: np.ndarray, y_t: np.ndarray,
                    r_pd: float, r_hc: float) -> tuple[bool, float]:
    """Einbinder 占优条件在测试分数上的精确混合 CDF 核查（无额外抽样）。

    r_cls = 该类标签被翻转的概率（实现率）。干净分数 s_i = 1−p_{y_i}；
    腐蚀分数以概率 (1−r) 取 s_i、以概率 r 取 1−p_{1−y_i}。
    占优成立 ⟺ ∀t: F_noisy(t) ≤ F_clean(t)（+容差）。
    """
    s_clean = 1.0 - probs_te[np.arange(len(y_t)), y_t]
    s_flip = 1.0 - probs_te[np.arange(len(y_t)), 1 - y_t]
    r = np.where(y_t == 1, r_pd, r_hc)
    grid = np.unique(np.concatenate([s_clean, s_flip]))
    f_clean = np.array([(s_clean <= t).mean() for t in grid])
    f_noisy = np.array([((1 - r) * (s_clean <= t) + r * (s_flip <= t)).sum() / len(y_t)
                        for t in grid])
    viol = f_noisy - f_clean
    return bool((viol <= DOMINANCE_TOL).all()), float(viol.max())


def theory_label(scope: str, dominance: bool) -> str:
    if scope == "train_cal":
        return "n/a (model retrained; theory assumes fixed model)"
    return ("guarantee: coverage >= 0.90 (dispersive corruption, dominance holds)"
            if dominance else
            "no guarantee (non-dispersive corruption, dominance violated)")


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
        """单 cell：给定（训练标签, 校准标签, scope, 实现翻转率）→ 全管线 + 理论核查。"""
        scaler = StandardScaler().fit(X_s[tr_idx])
        clf = LogisticRegression(random_state=42, max_iter=1000)
        clf.fit(scaler.transform(X_s[tr_idx]), y_train)
        scores_cal = lac_scores(clf.predict_proba(scaler.transform(X_s[cal_idx])), y_cal)
        probs_te = clf.predict_proba(scaler.transform(X_t))
        q = split_conformal_quantile(scores_cal, ALPHA)
        sets = sets_at_quantile(probs_te, q)
        m = metrics(y_t, sets)
        dom, max_viol = dominance_check(probs_te, y_t, r_pd, r_hc)
        q_clean = split_conformal_quantile(
            lac_scores(clf.predict_proba(scaler.transform(X_s[cal_idx])),
                       y_s[cal_idx]), ALPHA) if not np.array_equal(y_cal, y_s[cal_idx]) else q
        return {**m, "qhat": q, "qhat_clean": q_clean, "qhat_shift": q - q_clean,
                "dominance_holds": dom, "max_cdf_violation": max_viol,
                "theory_prediction": theory_label(scope, dom)}

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
    out.to_csv("results/stress_test_a.csv", index=False)

    # ---- 对表摘要：理论保证 vs 观测覆盖（cal_only 档为主表）
    print("\n=== Einbinder 对表（cal_only 档：固定模型理论对齐）===")
    for arm in ARMS:
        for dose in DOSES:
            r = out[(out["arm"] == arm) & (out["dose_pct"] == dose)
                    & (out["scope"] == "cal_only")].iloc[0]
            if r["dominance_holds"]:
                flag = ("✓ 理论一致（保证成立，观测≥0.90）" if r["coverage"] >= 1 - ALPHA
                        else "✗ 违反理论保证（占优成立但观测<0.90）")
            else:
                flag = "— 无保证域（占优不成立）"
            print(f"[{arm} d={dose}%] 翻转 PD:{r['n_flipped_pd']}/HC:{r['n_flipped_hc']} "
                  f"占优={r['dominance_holds']}（max ΔCDF={r['max_cdf_violation']:.4f}）"
                  f"q̂偏移={r['qhat_shift']:+.4f} 覆盖={r['coverage']:.4f} "
                  f"PD:{r['cpc_pd']:.4f} HC:{r['cpc_hc']:.4f} {flag}")
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
