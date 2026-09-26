#!/usr/bin/env python
"""stress_three_arm.py — 三臂应力测试（TODO-4.8，RQ3 核心交付）

冻结口径（analysis_plan_v1.md §10 + 计划书 v1.3.2 §4.4）：
  臂 1 纯重采样（患病率→Tappy 实测 74%）/ 臂 2 纯非对称翻转（保持患病率）/
  臂 3 叠加；判据 = 整体覆盖 ±5pp、集合大小 ±0.3 内复现真实 Tappy 覆盖模式
  （pre-specified practical equivalence tolerance，非统计显著性阈值）；
  注入范围分档：仅校准集翻转 vs 训练+校准同时翻转，以不翻转为基线；
  **结论措辞（冻结模板）**："检验患病率重配与随机标签腐蚀是否**足以复现**观察到
  的覆盖模式"——不主张因果识别。几何 = mit2tappy（源 MIT 操纵、目标 Tappy 173 人
  标签全程干净并担任 ground truth 角色——"目标域标签角色下计算覆盖"）。

实现级预声明（实现时钉死、先于首次运行；按防复发制度 §4 本脚本先行单独 commit）：
  1. 表型 = results/primary_family.csv mit2tappy/lr 行实时读取
     （coverage 0.8497、mean_size 1.5318、cpc_pd 0.8947、cpc_hc 0.7000）；
     基线行（无操纵）对该行 + recovery_cost_table.csv naive 行双重断言。
  2. 臂 1（resample_only）：源池人级无放回重采样匹配 π*=0.74——保留全部 42 PD、
     抽 n_hc = round(42·(1−0.74)/0.74) = 15 HC → 57 人池（实现患病率 42/57=0.7368，
     与注册 0.74 差 0.0032，有限池约束如实报告；冻结队列 Tappy 实值 133/173=0.7688
     另注）。重采样池内重新分层切分（seed=1）。重采样是池级操作，无 scope 分档。
  3. 臂 2（flip_only）："保持患病率"操作化 = **双向等计数翻转**（唯一精确保持
     患病率的规范构造：PD−x+9 与 HC−9+x 相消）；计数与臂 1 的患病率位移质量匹配：
     x = round((0.74−0.5122)·82/2) = 9/向（rates 21.4%/22.5%，类间不等即注册词
     "非对称"的字面成立）。scope 分档（plan §10）：cal_only（训练标签干净、仅校准
     标签翻转）/ train_cal（训练+校准同翻）。
  4. 臂 3（both）：臂 1 重采样池（57 人）+ 等计数翻转，计数与 57 人池的位移质量
     匹配：x' = round((0.74−0.5122)·57/2) = 6/向（rates 14.3%/40%——HC 侧重为池收缩
     的必然结果，如实报告）；同两 scope。
  5. 抽取随机性：单 numpy default_rng(1)（stress_seed_base），消耗顺序固定：
     ①臂 1 抽 15 HC（40 池，replace=False）→ ②臂 2 抽 9 PD + 9 HC（原池）→
     ③臂 3 抽 6 PD（42 池）+ 6 HC（臂 1 重采样池内 15 HC）。切分/模型与 primary
     同构（LR 42/1000、scaler 源 train fit、α=0.10）。
  6. 判据（预注册容差）：reproduced = |coverage−表型|≤0.05 AND |mean_size−表型|
     ≤0.30；类条件覆盖/单例率/拒绝率随行描述性报告，不入判据。结论措辞按冻结
     模板（"是否足以复现"），本脚本与其输出不使用因果识别表述。
产出：results/three_arm_stress_test.csv（6 行）+ data/interim/parse_reports/
     three_arm_stress_test_report.json
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

STRESS_SEED = 1   # seeds.yaml stress_seed_base
MATCH_PREV = 0.74  # 注册"Tappy 实测 74%"（冻结队列实值 0.7688，见预声明 2）
TOL_COV = 0.05
TOL_SIZE = 0.30
FLIP_ARMS = ("resample_only", "flip_only", "both")


def flip_counts_for_pool(pi_ref: float, n_pool: int, n_pd: int, n_hc: int) -> tuple[int, int]:
    """质量匹配的等计数翻转：x = round((π_match−π_ref)·n_pool/2)。π_ref 恒取
    原始源池患病率 42/82（臂 2 原池、臂 3 重采样池均按同一位移源计算），不取
    各臂自身池患病率（否则臂 3 已在 0.7368 会算出 0 翻转，静默退化为臂 1）。"""
    x = int(round((MATCH_PREV - pi_ref) * n_pool / 2))
    return min(max(x, 0), n_pd), min(max(x, 0), n_hc)


def main() -> None:
    ap = argparse.ArgumentParser(description="Three-arm stress test (TODO-4.8)")
    ap.add_argument("--arm", default="resample_only,flip_only,both")
    ap.add_argument("--match-prevalence", type=float, default=MATCH_PREV)
    args = ap.parse_args()
    assert args.arm.split(",") == list(FLIP_ARMS), "臂清单须与预注册一致"
    assert abs(args.match_prevalence - MATCH_PREV) < 1e-12, "患病率须为注册值 0.74"

    cfg = next(d for d in DIRECTIONS if d["direction"] == "mit2tappy")
    tier = min(CAP["mit"], CAP["tappy"])
    X_s, y_s = load_pooled(cfg["sources"], tier)
    X_t, y_t = load_matrix(cfg["target"], tier)
    assert X_s.shape[1] == X_t.shape[1]
    n_pd, n_hc, n_pool = int((y_s == 1).sum()), int((y_s == 0).sum()), len(y_s)
    assert (n_pd, n_hc, n_pool) == (42, 40, 82), "MIT 源池构成与冻结队列不符"

    # 表型实时读取（预声明 1）
    frozen = pd.read_csv("results/primary_family.csv")
    ph = frozen[(frozen["direction"] == "mit2tappy") & (frozen["model"] == "lr")].iloc[0]
    PH = {"coverage": float(ph["coverage"]), "mean_size": float(ph["mean_size"]),
          "cpc_pd": float(ph["cpc_pd"]), "cpc_hc": float(ph["cpc_hc"])}

    def run(y_train: np.ndarray, y_cal: np.ndarray, X_tr: np.ndarray, X_cl: np.ndarray,
            ) -> dict:
        scaler = StandardScaler().fit(X_tr)
        clf = LogisticRegression(random_state=42, max_iter=1000)
        clf.fit(scaler.transform(X_tr), y_train)
        q = split_conformal_quantile(lac_scores(clf.predict_proba(scaler.transform(X_cl)),
                                                y_cal), ALPHA)
        probs_te = clf.predict_proba(scaler.transform(X_t))
        m = metrics(y_t, sets_at_quantile(probs_te, q))
        m["reproduced"] = bool(abs(m["coverage"] - PH["coverage"]) <= TOL_COV
                               and abs(m["mean_size"] - PH["mean_size"]) <= TOL_SIZE)
        m["delta_coverage_vs_phenotype"] = m["coverage"] - PH["coverage"]
        m["delta_mean_size_vs_phenotype"] = m["mean_size"] - PH["mean_size"]
        return m

    rng = np.random.default_rng(STRESS_SEED)  # 预声明 5：消耗顺序 ①→②→③
    rows = []

    # ---- 基线（无操纵）
    idx = np.arange(n_pool)
    tr_idx, cal_idx = train_test_split(idx, test_size=0.30, random_state=SEED, stratify=y_s)
    scaler = StandardScaler().fit(X_s[tr_idx])
    clf = LogisticRegression(random_state=42, max_iter=1000)
    clf.fit(scaler.transform(X_s[tr_idx]), y_s[tr_idx])
    sets_b = predict_sets_split(lac_scores(clf.predict_proba(scaler.transform(X_s[cal_idx])),
                                           y_s[cal_idx]), clf.predict_proba(scaler.transform(X_t)),
                                ALPHA)
    m_b = metrics(y_t, sets_b)
    assert int(ph["k"]) == m_b["k"] and int(ph["n"]) == m_b["n"]
    for col in ("coverage", "cpc_pd", "cpc_hc", "mean_size", "singleton_rate"):
        assert abs(float(ph[col]) - m_b[col]) < 1e-12, f"基线 {col} 漂移"
    rc = pd.read_csv("results/recovery_cost_table.csv")
    rc_naive = rc[(rc["direction"] == "mit2tappy") & (rc["method"] == "naive_cp")].iloc[0]
    assert int(rc_naive["k"]) == m_b["k"] and int(rc_naive["n"]) == m_b["n"], \
        "基线与 4.4 recovery_cost naive 行漂移"
    for col in ("coverage", "cpc_pd", "cpc_hc", "mean_size", "singleton_rate"):
        assert abs(float(rc_naive[col]) - m_b[col]) < 1e-12, f"基线 vs 4.4 {col} 漂移"
    m_b["reproduced"] = True  # 基线即表型本身（断言已证逐位相等）
    m_b["delta_coverage_vs_phenotype"] = 0.0
    m_b["delta_mean_size_vs_phenotype"] = 0.0
    rows.append({"arm": "baseline", "scope": "none", "n_pool": n_pool,
                 "n_pd_pool": n_pd, "n_hc_pool": n_hc, "realized_prev": n_pd / n_pool,
                 "n_flip_pd": 0, "n_flip_hc": 0, **m_b, "note": "= primary 锚点（双断言）"})

    # ---- 臂 1：纯重采样（保留全部 PD，抽 15 HC；池级操作，无 scope）
    hc_all = np.flatnonzero(y_s == 0)
    keep_hc = np.sort(rng.choice(hc_all, size=15, replace=False))
    keep = np.sort(np.concatenate([np.flatnonzero(y_s == 1), keep_hc]))
    X_r, y_r = X_s[keep], y_s[keep]
    tr2, cal2 = train_test_split(np.arange(len(y_r)), test_size=0.30,
                                 random_state=SEED, stratify=y_r)
    m1 = run(y_r[tr2], y_r[cal2], X_r[tr2], X_r[cal2])
    rows.append({"arm": "resample_only", "scope": "pool_level", "n_pool": len(y_r),
                 "n_pd_pool": int((y_r == 1).sum()), "n_hc_pool": int((y_r == 0).sum()),
                 "realized_prev": float((y_r == 1).mean()), "n_flip_pd": 0, "n_flip_hc": 0,
                 **m1, "note": "保留全部 PD+抽 15 HC；注册 0.74 vs 实现 0.7368"})

    # ---- 臂 2：纯翻转（原池 82 人，等计数 9/向，两 scope）
    x2pd, x2hc = flip_counts_for_pool(n_pd / n_pool, n_pool, n_pd, n_hc)
    fl_pd = rng.choice(np.flatnonzero(y_s == 1), size=x2pd, replace=False)
    fl_hc = rng.choice(hc_all, size=x2hc, replace=False)
    y_flip = y_s.copy()
    y_flip[fl_pd] = 0
    y_flip[fl_hc] = 1
    assert abs((y_flip == 1).mean() - y_s.mean()) < 1e-12, "臂 2 未保持患病率"
    for scope, ytr, ycl in [("cal_only", y_s[tr_idx], y_flip[cal_idx]),
                            ("train_cal", y_flip[tr_idx], y_flip[cal_idx])]:
        m2 = run(ytr, ycl, X_s[tr_idx], X_s[cal_idx])
        rows.append({"arm": "flip_only", "scope": scope, "n_pool": n_pool,
                     "n_pd_pool": n_pd, "n_hc_pool": n_hc, "realized_prev": n_pd / n_pool,
                     "n_flip_pd": x2pd, "n_flip_hc": x2hc, **m2,
                     "note": f"等计数 {x2pd}/向 保持患病率（rates {x2pd/n_pd:.1%}/"
                             f"{x2hc/n_hc:.1%}）"})

    # ---- 臂 3：叠加（57 人池 + 等计数 6/向，两 scope）
    x3pd, x3hc = flip_counts_for_pool(n_pd / n_pool, len(y_r),
                                      int((y_r == 1).sum()), int((y_r == 0).sum()))
    fl3_pd = rng.choice(np.flatnonzero(y_r == 1), size=x3pd, replace=False)
    fl3_hc = rng.choice(np.flatnonzero(y_r == 0), size=x3hc, replace=False)
    y_r_flip = y_r.copy()
    y_r_flip[fl3_pd] = 0
    y_r_flip[fl3_hc] = 1
    assert abs((y_r_flip == 1).mean() - y_r.mean()) < 1e-12, "臂 3 未保持重采样池患病率"
    tr3, cal3 = train_test_split(np.arange(len(y_r)), test_size=0.30,
                                 random_state=SEED, stratify=y_r)
    n_pd_r, n_hc_r = int((y_r == 1).sum()), int((y_r == 0).sum())
    for scope, ytr, ycl in [("cal_only", y_r[tr3], y_r_flip[cal3]),
                            ("train_cal", y_r_flip[tr3], y_r_flip[cal3])]:
        m3 = run(ytr, ycl, X_r[tr3], X_r[cal3])
        rows.append({"arm": "both", "scope": scope, "n_pool": len(y_r),
                     "n_pd_pool": int((y_r_flip == 1).sum()), "n_hc_pool": int((y_r_flip == 0).sum()),
                     "realized_prev": float((y_r_flip == 1).mean()),
                     "n_flip_pd": x3pd, "n_flip_hc": x3hc, **m3,
                     "note": f"重采样池 + 等计数 {x3pd}/向（rates {x3pd/n_pd_r:.1%}/"
                             f"{x3hc/n_hc_r:.1%}，HC 侧重为池收缩必然）"})

    out = pd.DataFrame(rows)
    out.to_csv("results/three_arm_stress_test.csv", index=False)

    print(f"\n=== 三臂应力测试（表型 = mit2tappy 真实覆盖模式：覆盖 {PH['coverage']:.4f} / "
          f"集合大小 {PH['mean_size']:.4f} / PD {PH['cpc_pd']:.4f} / HC {PH['cpc_hc']:.4f}）===")
    print(f"判据（预设实用等价容差）：|Δ覆盖|≤{TOL_COV} 且 |Δ集合大小|≤{TOL_SIZE}")
    for _, r in out.iterrows():
        verdict = ("✓ 足以复现" if r["reproduced"] else "✗ 不足以复现")
        print(f"[{r['arm']:<14}|{r['scope']:<10}] 池={int(r['n_pool'])}人"
              f"（PD{int(r['n_pd_pool'])}/HC{int(r['n_hc_pool'])}，π={r['realized_prev']:.4f}）"
              f"翻转 {int(r['n_flip_pd'])}/{int(r['n_flip_hc'])} → "
              f"覆盖={r['coverage']:.4f}（Δ{r['delta_coverage_vs_phenotype']:+.4f}）"
              f"大小={r['mean_size']:.4f}（Δ{r['delta_mean_size_vs_phenotype']:+.4f}）"
              f"PD={r['cpc_pd']:.4f} HC={r['cpc_hc']:.4f} → {verdict}")
    print("\n结论措辞（冻结模板）：本表检验患病率重配与随机标签腐蚀是否**足以复现**"
          "观察到的覆盖模式——不主张因果识别。")

    predecl = __doc__.split("实现级预声明")[1].split("产出")[0].strip()
    Path("data/interim/parse_reports").mkdir(parents=True, exist_ok=True)
    Path("data/interim/parse_reports/three_arm_stress_test_report.json").write_text(
        json.dumps({"predeclarations": predecl, "stress_seed": STRESS_SEED,
                    "match_prevalence_registered": MATCH_PREV,
                    "phenotype": PH, "tolerances": {"coverage": TOL_COV, "mean_size": TOL_SIZE},
                    "rows": rows}, indent=2, default=float), encoding="utf-8")
    print(f"共 {len(out)} 行 → results/three_arm_stress_test.csv")


if __name__ == "__main__":
    main()
