#!/usr/bin/env python
"""calibration_compare.py — 应力测试 B：真实迁移三方校准对照（TODO-4.6）

冻结口径（analysis_plan_v1.md §10 实验B + 计划书 v1.3.2 §4.4）：真实迁移上三方
校准对照 = 金域校准直推（gold_direct）/ 目标域重校准（target_recalib，登记梯度
5/10/20/30%）/ weighted CP；方向 = primary family 三方向。实验族定位 = 归因：
在真实迁移对上分离"校准错配"（目标域标注可恢复）与"分数/模型层错配"
（标注不可恢复，weighted CP 失败 + 重校准后类条件残差为证）。

与 TODO-4.4 的关系（预声明）：三臂方法学与 recovery_cost_table.csv 同源同实现
（gold_direct ≡ naive 锚点行；target_recalib 同预算梯度同抽取协议；weighted CP
同密度比实现）。本脚本**同管线重算**并对 4.4 已审计数字做逐位断言（k/n 整数
+ 8 个指标列 1e-12），任何漂移在落盘前拦截；新增内容 = Δ vs gold_direct 归因层
+ 点估计阈值旗标（0.90 名义 / 0.80 审计阈值，描述性，不施加三分类判定/Holm）。

实现级预声明（实现时钉死、先于首次运行；按防复发制度 §4 本脚本先行单独 commit）：
  1. 管线与 4.4 完全同构：mit2tappy/tappy2mit/gold_merged2self、tier=min(全链 cap)、
     seed=1 切分、LR 主参照（CHG-P1）、α=0.10；helpers（stratified_draw/
     protocol_budget_split/density_ratio_weights/metrics/sets_at_quantile）直接
     import 自 remediate.py——结构性防漂移。
  2. 预算抽取 rng = numpy default_rng(1)（stress_seed_base），消耗顺序与 4.4 逐位
     一致：方向（DIRECTIONS 序）内仅预算循环消耗（b 升序；merged 每预算 tappy→oe
     两次）；naive/weighted 不消耗 rng——故三方重算的预算集与 4.4 逐位相同。
  3. 逐位断言对象 = results/recovery_cost_table.csv：gold_direct↔naive_cp 行、
     weighted_cp↔weighted_cp 行、target_recalib(b)↔target_recalib(b) 行
     （k/n/coverage/ci_lo/ci_hi/cpc_pd/cpc_hc/mean_size/singleton_rate/rejection_rate）；
     gold_direct 另断言 results/primary_family.csv（lr 行）。
  4. Δ 归因层（新内容）：每方法行对同方向 gold_direct 求 Δ（coverage/cpc_pd/cpc_hc/
     mean_size/singleton_rate）；旗标 = 点估计 ≥0.90（名义）/ ≥0.80（审计阈值）/
     CI 下界 ≥0.80，均为描述性标志，不进判定链。
  5. group_weighted 不在三方对照清单（TODO 工具调用口径），不产出。

产出：results/calibration_comparison.csv（3 方向 × {1+1+4} 行 = 18 行）
     + data/interim/parse_reports/calibration_comparison_report.json
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
from cp.conformal import (  # noqa: E402
    WeightedConformal,
    lac_scores,
    predict_sets_split,
    split_conformal_quantile,
)
from cp.coverage_audit import ALPHA, CAP, DIRECTIONS, SEED, load_pooled  # noqa: E402
from cp.remediate import (  # noqa: E402
    density_ratio_weights,
    metrics,
    protocol_budget_split,
    sets_at_quantile,
    stratified_draw,
)
from models.run_transfer import load_matrix  # noqa: E402

DRAW_SEED = 1  # seeds.yaml stress_seed_base（与 4.4 同源同序，见预声明 2）
BUDGETS = (5, 10, 20, 30)
DELTA_COLS = ("coverage", "cpc_pd", "cpc_hc", "mean_size", "singleton_rate")


def main() -> None:
    ap = argparse.ArgumentParser(description="Stress test B: three-way calibration comparison")
    ap.add_argument("--methods", default="gold_direct,target_recalib,weighted_cp")
    ap.add_argument("--directions", default="primary")
    args = ap.parse_args()
    assert args.methods.split(",") == ["gold_direct", "target_recalib", "weighted_cp"]
    assert args.directions == "primary", "实验 B 注册口径 = primary family 三方向"

    frozen = pd.read_csv("results/primary_family.csv")
    rc = pd.read_csv("results/recovery_cost_table.csv")

    def rc_row(direction: str, method: str, budget: int | None) -> pd.Series:
        m = (rc["direction"] == direction) & (rc["method"] == method)
        if budget is not None:
            m &= rc["budget_pct"] == budget
        out = rc[m]
        assert len(out) == 1, f"recovery_cost 行缺失: {direction}/{method}/{budget}"
        return out.iloc[0]

    def assert_match(direction: str, method: str, budget: int | None,
                     m: dict, q_inf: bool) -> None:
        f = rc_row(direction, method, budget)
        assert int(f["k"]) == m["k"] and int(f["n"]) == m["n"]
        assert bool(f["qhat_inf"]) == q_inf
        for col in ("coverage", "ci_lo", "ci_hi", "cpc_pd", "cpc_hc",
                    "mean_size", "singleton_rate", "rejection_rate"):
            assert abs(float(f[col]) - m[col]) < 1e-12, \
                f"{direction}/{method}/b={budget} {col} 与 4.4 漂移"

    rng = np.random.default_rng(DRAW_SEED)  # 预声明消耗顺序 = 4.4 逐位同序
    RC_NAME = {"gold_direct": "naive_cp", "weighted_cp": "weighted_cp",
               "target_recalib": "target_recalib"}  # 4.4 行名映射
    rows = []
    for cfg in DIRECTIONS:
        srcs, tgt = cfg["sources"], cfg["target"]
        tgt_datasets = {"merged_self": ["tappy", "oe"]}.get(tgt, [tgt])
        tier = min(CAP[d] for d in srcs + tgt_datasets)
        X_s, y_s = load_pooled(srcs, tier)
        if tgt == "merged_self":
            subjects = pd.read_csv("data/processed/subjects.csv")
            pool = subjects[subjects["dataset"].isin(["tappy", "oe"])].reset_index(drop=True)
            cols = [c for c in pool.columns if c.startswith("L1_")]
            X_t = pool[cols].to_numpy(dtype=float)
            y_t = pool["label_pd"].to_numpy(dtype=int)
            proto_t = pool["dataset"].to_numpy()
        else:
            X_t, y_t = load_matrix(tgt, tier)
            proto_t = np.array([tgt] * len(y_t), dtype=object)
        assert X_s.shape[1] == X_t.shape[1]

        idx = np.arange(len(X_s))
        tr_idx, cal_idx = train_test_split(idx, test_size=0.30, random_state=SEED, stratify=y_s)
        scaler = StandardScaler().fit(X_s[tr_idx])
        X_tr_s, X_cal_s, X_te_s = (scaler.transform(X_s[tr_idx]), scaler.transform(X_s[cal_idx]),
                                   scaler.transform(X_t))
        clf = LogisticRegression(random_state=42, max_iter=1000)
        clf.fit(X_tr_s, y_s[tr_idx])
        scores_cal = lac_scores(clf.predict_proba(X_cal_s), y_s[cal_idx])
        probs_te = clf.predict_proba(X_te_s)
        direction, n_target = cfg["direction"], len(y_t)

        def emit(method: str, budget: int, n_labels: int, m: dict, q_inf: bool,
                 note: str) -> None:
            if method == "gold_direct":
                deltas = {f"delta_{c}": 0.0 for c in DELTA_COLS}
            else:
                gold = next(r for r in rows
                            if r["direction"] == direction and r["method"] == "gold_direct")
                deltas = {f"delta_{c}": m[c] - gold[c] for c in DELTA_COLS}
            rows.append({"direction": direction, "method": method, "budget_pct": budget,
                         "n_target_labels": n_labels, **m, **deltas, "qhat_inf": q_inf,
                         "point_ge_090": bool(m["coverage"] >= 0.90),
                         "point_ge_080": bool(m["coverage"] >= 0.80),
                         "cilo_ge_080": bool(m["ci_lo"] >= 0.80),
                         "note": note})
            assert_match(direction, RC_NAME[method], budget, m, q_inf)

        # ---- 臂 1：金域校准直推（≡ naive 锚点）
        sets_g = predict_sets_split(scores_cal, probs_te, ALPHA)
        m_g = metrics(y_t, sets_g)
        f = frozen[(frozen["direction"] == direction) & (frozen["model"] == "lr")].iloc[0]
        assert int(f["k"]) == m_g["k"] and int(f["n"]) == m_g["n"]
        for col in ("coverage", "cpc_pd", "cpc_hc", "mean_size", "singleton_rate"):
            assert abs(float(f[col]) - m_g[col]) < 1e-12, f"{direction} gold_direct 漂移"
        emit("gold_direct", 0, 0, m_g, False, "≡ naive 锚点（primary + 4.4 双断言）")

        # ---- 臂 2：weighted CP（0 标注）
        if "weighted_cp" in args.methods.split(","):
            w_cal, w_te, w_stats = density_ratio_weights(X_tr_s, X_cal_s, X_te_s)
            sets_w = WeightedConformal(w_cal, scores_cal, ALPHA).predict_sets(w_te, probs_te)
            m_w = metrics(y_t, sets_w)
            emit("weighted_cp", 0, 0, m_w, False,
                 f"域分类器密度比，合池p99截断={w_stats['w_cap_raw']:.3g}（≡4.4）")

        # ---- 臂 3：目标域重校准（登记梯度）
        if "target_recalib" in args.methods.split(","):
            for b in BUDGETS:
                mb = max(2, int(round(b / 100 * n_target)))
                if tgt == "merged_self":
                    is_tappy = proto_t == "tappy"
                    pos_tappy, pos_oe = np.flatnonzero(is_tappy), np.flatnonzero(~is_tappy)
                    m_tappy, m_oe = protocol_budget_split(n_target, len(pos_tappy), mb)
                    bud = np.concatenate(
                        [pos_tappy[stratified_draw(y_t[pos_tappy], m_tappy, rng)],
                         pos_oe[stratified_draw(y_t[pos_oe], m_oe, rng)]])
                    bud = np.sort(bud)
                else:
                    bud = stratified_draw(y_t, mb, rng)
                test_mask = np.ones(n_target, bool)
                test_mask[bud] = False
                q = split_conformal_quantile(
                    lac_scores(clf.predict_proba(X_te_s[bud]), y_t[bud]), ALPHA)
                m_r = metrics(y_t[test_mask], sets_at_quantile(probs_te[test_mask], q))
                emit("target_recalib", b, int(len(bud)), m_r, bool(np.isinf(q)),
                     "目标预算单分位重校准（≡4.4 同抽取）")

    out = pd.DataFrame(rows)
    out.to_csv("results/calibration_comparison.csv", index=False)

    # ---- 归因摘要（描述性）
    print("\n=== 三方校准对照（真实迁移，Δ=臂−金域直推）===")
    for direction in out["direction"].unique():
        sub = out[out["direction"] == direction]
        g = sub[sub["method"] == "gold_direct"].iloc[0]
        print(f"\n[{direction}] 金域直推 覆盖={g['coverage']:.4f} PD={g['cpc_pd']:.4f} "
              f"HC={g['cpc_hc']:.4f}")
        for _, r in sub[sub["method"] != "gold_direct"].iterrows():
            bl = f" b={int(r['budget_pct'])}%({int(r['n_target_labels'])}标注)" \
                if r["method"] == "target_recalib" else "（0 标注）"
            deg = " [退化:全集,名义旗标无意义]" if r["qhat_inf"] else ""
            print(f"  {r['method']:<15}{bl:<16} 覆盖={r['coverage']:.4f}"
                  f"（Δ{r['delta_coverage']:+.4f}）PD={r['cpc_pd']:.4f}"
                  f"（Δ{r['delta_cpc_pd']:+.4f}）HC={r['cpc_hc']:.4f}"
                  f"（Δ{r['delta_cpc_hc']:+.4f}）"
                  f" 点≥0.80={r['point_ge_080']} CI下界≥0.80={r['cilo_ge_080']}"
                  f" 拒绝率={r['rejection_rate']:.2f}{deg}")

    rep = {"predeclarations": __doc__.split("实现级预声明")[1].split("产出")[0].strip(),
           "draw_seed": DRAW_SEED, "rows": rows}
    Path("data/interim/parse_reports").mkdir(parents=True, exist_ok=True)
    Path("data/interim/parse_reports/calibration_comparison_report.json").write_text(
        json.dumps(rep, indent=2, default=float), encoding="utf-8")
    print(f"\n共 {len(out)} 行 → results/calibration_comparison.csv")


if __name__ == "__main__":
    main()
