#!/usr/bin/env python
"""remediate.py — 补救三层链 + 恢复-代价表（TODO-4.4，RQ3 正式结果）

冻结口径（analysis_plan_v1.md §11 + 分析冻结协议 v1 §6）：
  行 = {naive CP, 目标域重校准(5/10/20/30), weighted CP, group-weighted CP}；
  列 = {所需目标域标注数, 总体覆盖, PD 覆盖, 平均集合大小, 单例率, 拒绝率}。
  Golden gate：回答"恢复审计阈值（0.80，pre-specified operational audit threshold）
  以上覆盖需要多少目标域标注"。
  目标泄漏硬条款：目标库不进任何模型选择；模型一律只在源域 train split 上训练
  （与 primary 审计同 tr_idx），目标域适应仅限下列预先指定的校准程序。

实现级预声明（实现时钉死、先于首次运行，随本 commit 入账）：
  1. 方向 = primary family 三方向（§7）；模型 = LR 主参照（CHG-P1）单通道。
  2. naive CP = primary 审计管线的 b=0 锚点行：源域 cal（seed=1 切分）→ 全体目标测试。
     落盘前对 results/primary_family.csv（LR 行）做 k/n/coverage/cpc/mean_size/
     singleton_rate 逐列一致性断言。
  3. 目标域重校准：模型不变（源域 tr_idx 训练），校准集 = m = max(2, round(b%·n_target))
     个标注目标受试者（类别分层比例抽取），测试 = 其余目标受试者（互补集，无重叠）。
     抽取随机性：numpy default_rng(seed=1)（= seeds.yaml stress_seed_base，登记口径
     "重采样随机化与 split_seeds 复用 1-50"），按（方向, 预算升序）顺序单次消耗，
     不做重复抽取（与确证性单切分风格一致）。
  4. weighted CP（预算 0，不用目标标签；探索性、预注册零预期）：密度比 w(x)=p_t(x)/p_s(x)
     经域分类器估计 = LogisticRegression(class_weight="balanced", random_state=42,
     max_iter=1000)（与主参照同族同配置；输入为源 train 与全体目标的 tier 档标准化特征），
     w_raw = p/(1-p)。权重截断：以 cal∪test 合池 p99 为上限双侧截断（预登记规则，非调优值）；
     截断后按 c = 1/mean(w_test) 归一（同一 c 作用于 cal 与 test，保持式(8) 标度一致）。
     权重分布报告（预登记细节）落 CSV 列。分位规则 = WeightedConformal（Tibshirani 式(8)
     直接实现，独立 oracle 已对拍）。
  5. group-weighted CP（按设备/协议分组，remediation benchmark 引 EJS 2026 框架）：
     分组 = 数据集协议身份（subjects.csv dataset 列；无设备元数据，协议=库）。
     操作化 = 协议组条件校准：gold_merged2self 目标含 Tappy(OYOD)与 OE(web)两协议，
     预算按协议规模比例分配（tappy 先取 round，oe 取余），协议内再按类别分层；
     每协议测试子集用**本协议预算**的分位数（协议组条件/Mondrian 读法）。
     方向 1/2 目标为单协议，本方法按构造与目标域重校准逐位相同——如实报告等价性
     （cross-dataset 几何下源协议与目标协议永不同组，组条件校准只能消费目标预算），
     断言逐位一致并在 note 列标注。b=0 时组条件无预算可用，退化为 naive，不单列行。
  6. 拒绝率 = 预测集=全集（二类 size=2）比例（冻结协议 §5 部署效用映射：全集=系统拒绝）；
     空集率另列（LAC 可产生空集，病理如实报告）。qhat=+inf（m<9 小校准诚实退化）
     行标记 degenerate——名义覆盖 1.0 但集合效用全毁，恢复判读不得只看点估计。
  7. 恢复判据（Golden gate）双向呈现不挑数：点估计 cov ≥ 0.80 的最小预算 与
     CI 下界 ≥ 0.80 的最小预算（与 plan §6 Compatible 同式的 CI 下界判据，仅为
     判据复用、不对任何行施加三分类判定），并标注退化行。

产出：results/recovery_cost_table.csv（正式）+ data/interim/parse_reports/recovery_cost_report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import beta as _beta
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
from models.run_transfer import load_matrix  # noqa: E402

DRAW_SEED = 1  # seeds.yaml stress_seed_base（重采样随机化登记口径）
BUDGET_GRADIENT = (5, 10, 20, 30)  # §11 登记梯度（%；0 = naive/weighted 锚点行）
AUDIT_THRESHOLD = 0.80  # pre-specified operational audit threshold（§6）
W_CLIP_QUANTILE = 0.99  # 预登记截断规则（合池 p99，非调优值）


def cp_ci(k: int, n: int) -> tuple[float, float]:
    lo = float(_beta.ppf(0.025, k, n - k + 1)) if k > 0 else 0.0
    hi = float(_beta.ppf(0.975, k + 1, n - k)) if k < n else 1.0
    return lo, hi


def sets_at_quantile(probs: np.ndarray, q: float) -> list[frozenset[int]]:
    return [frozenset(y for y in (0, 1) if (1.0 - row[y]) <= q) for row in np.asarray(probs, float)]


def metrics(y: np.ndarray, sets: list[frozenset[int]]) -> dict:
    hits = np.array([t in s for t, s in zip(y, sets)])
    sizes = np.array([len(s) for s in sets])
    k, n = int(hits.sum()), int(len(hits))
    lo, hi = cp_ci(k, n)
    return {"k": k, "n": n, "coverage": k / n, "ci_lo": lo, "ci_hi": hi,
            "cpc_pd": float(hits[y == 1].mean()), "cpc_hc": float(hits[y == 0].mean()),
            "mean_size": float(sizes.mean()), "singleton_rate": float((sizes == 1).mean()),
            "rejection_rate": float((sizes == 2).mean()), "empty_rate": float((sizes == 0).mean())}


def stratified_draw(y: np.ndarray, m: int, rng: np.random.Generator) -> np.ndarray:
    """类别分层比例抽取 m 个下标（PD 先 round，HC 取余），精确命中 m。"""
    n_pd = int((y == 1).sum())
    m_pd = min(max(int(round(m * n_pd / len(y))), 0), m)
    m_hc = m - m_pd
    m_pd = min(m_pd, n_pd)
    m_hc = min(m_hc, int((y == 0).sum()))
    idx = np.concatenate([rng.choice(np.flatnonzero(y == 1), size=m_pd, replace=False),
                          rng.choice(np.flatnonzero(y == 0), size=m_hc, replace=False)])
    assert len(idx) == m, f"分层抽取未命中 m={m}"
    return np.sort(idx)


def protocol_budget_split(n: int, n_tappy: int, m: int) -> tuple[int, int]:
    m_tappy = int(round(m * n_tappy / n))
    return m_tappy, m - m_tappy


def density_ratio_weights(X_s_tr: np.ndarray, X_cal: np.ndarray, X_t: np.ndarray,
                          ) -> tuple[np.ndarray, np.ndarray, dict]:
    """预登记密度比估计：域分类器 LR（balanced，同主参照配置）→ w=p/(1−p)，
    合池 p99 截断，c=1/mean(w_test) 归一（同一 c 作用 cal/test）。"""
    X_dom = np.vstack([X_s_tr, X_t])
    y_dom = np.concatenate([np.zeros(len(X_s_tr), int), np.ones(len(X_t), int)])
    dom = LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000)
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
    stats = {"w_mean": float(w_te.mean()), "w_median": float(np.median(w_te)),
             "w_p95": float(np.quantile(w_te, 0.95)), "w_p99": float(np.quantile(w_te, 0.99)),
             "w_max": float(w_te.max()), "frac_clipped": frac_clipped,
             "w_cap_raw": cap}
    return w_cal, w_te, stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Remediation chain + recovery-cost table (TODO-4.4)")
    ap.add_argument("--methods", default="target_recalib,weighted_cp,group_weighted")
    ap.add_argument("--budget", default="0,5,10,20,30")
    args = ap.parse_args()
    methods = args.methods.split(",")
    budgets = [int(b) for b in args.budget.split(",")]
    assert "target_recalib" in methods, "recalib 链为恢复-代价表主体（RQ3 正式结果）"

    frozen = pd.read_csv("results/primary_family.csv")
    rows = []
    rng = np.random.default_rng(DRAW_SEED)  # 预声明：单生成器按（方向, 预算）顺序消耗

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
        direction = cfg["direction"]
        n_target = len(y_t)

        # ---- naive CP（b=0 锚点；与 primary_family.csv 断言同源一致）
        sets_naive = predict_sets_split(scores_cal, probs_te, ALPHA)
        m_naive = metrics(y_t, sets_naive)
        f = frozen[(frozen["direction"] == direction) & (frozen["model"] == "lr")].iloc[0]
        for col, val in [("k", m_naive["k"]), ("n", m_naive["n"])]:
            assert int(f[col]) == val, f"{direction} naive {col} 漂移"
        for col in ("coverage", "cpc_pd", "cpc_hc", "mean_size", "singleton_rate"):
            assert abs(float(f[col]) - m_naive[col]) < 1e-12, f"{direction} naive {col} 漂移"
        rows.append({"direction": direction, "method": "naive_cp", "budget_pct": 0,
                     "n_target_labels": 0, **m_naive, "qhat_inf": False,
                     "note": "= primary 审计锚点行（断言一致）"})

        # ---- weighted CP（预算 0；探索性，预注册零预期）
        if "weighted_cp" in methods:
            w_cal, w_te, w_stats = density_ratio_weights(X_tr_s, X_cal_s, X_te_s)
            wc = WeightedConformal(w_cal, scores_cal, ALPHA)
            sets_w = wc.predict_sets(w_te, probs_te)
            rows.append({"direction": direction, "method": "weighted_cp", "budget_pct": 0,
                         "n_target_labels": 0, **metrics(y_t, sets_w), "qhat_inf": False,
                         "note": f"域分类器密度比，合池p99截断={w_stats['w_cap_raw']:.3g}",
                         **w_stats})

        # ---- 目标域重校准（b>0）与 group-weighted（协议组条件）
        for b in budgets:
            if b <= 0:
                continue
            m = max(2, int(round(b / 100 * n_target)))
            if tgt == "merged_self":
                is_tappy = proto_t == "tappy"
                pos_tappy, pos_oe = np.flatnonzero(is_tappy), np.flatnonzero(~is_tappy)
                m_tappy, m_oe = protocol_budget_split(n_target, len(pos_tappy), m)
                bud = np.concatenate([pos_tappy[stratified_draw(y_t[pos_tappy], m_tappy, rng)],
                                      pos_oe[stratified_draw(y_t[pos_oe], m_oe, rng)]])
                bud = np.sort(bud)
            else:
                bud = stratified_draw(y_t, m, rng)
            test_mask = np.ones(n_target, bool)
            test_mask[bud] = False
            y_test, probs_test = y_t[test_mask], probs_te[test_mask]
            scores_bud = lac_scores(clf.predict_proba(X_te_s[bud]), y_t[bud])

            # recalib：目标预算单分位
            q = split_conformal_quantile(scores_bud, ALPHA)
            sets_rec = sets_at_quantile(probs_test, q)
            note = "目标预算单分位重校准" + ("；qhat=inf 诚实退化全集" if np.isinf(q) else "")
            rows.append({"direction": direction, "method": "target_recalib", "budget_pct": b,
                         "n_target_labels": int(len(bud)), **metrics(y_test, sets_rec),
                         "qhat_inf": bool(np.isinf(q)), "note": note})

            # group-weighted：协议组条件分位（方向 1/2 单协议 → 与 recalib 逐位等价）
            if "group_weighted" in methods and tgt == "merged_self":
                sets_grp = np.empty(int(test_mask.sum()), dtype=object)
                grp_q_inf = False
                for p_name in ("tappy", "oe"):
                    pmask = proto_t[test_mask] == p_name
                    pmask_bud = proto_t[bud] == p_name
                    q_p = split_conformal_quantile(scores_bud[pmask_bud], ALPHA)
                    grp_q_inf = grp_q_inf or bool(np.isinf(q_p))
                    sets_grp[pmask] = np.array(sets_at_quantile(probs_test[pmask], q_p),
                                               dtype=object)
                sets_grp = list(sets_grp)
                rows.append({"direction": direction, "method": "group_weighted",
                             "budget_pct": b, "n_target_labels": int(len(bud)),
                             **metrics(y_test, sets_grp), "qhat_inf": grp_q_inf,
                             "note": "协议组条件分位（tappy/oe 各自预算）"})
            elif "group_weighted" in methods:
                rows.append({"direction": direction, "method": "group_weighted",
                             "budget_pct": b, "n_target_labels": int(len(bud)),
                             **metrics(y_test, sets_rec), "qhat_inf": bool(np.isinf(q)),
                             "note": "目标单协议：按构造与 target_recalib 逐位等价（协议组条件退化）"})

    out = pd.DataFrame(rows)
    out.to_csv("results/recovery_cost_table.csv", index=False)

    # ---- Golden gate：恢复判据双向呈现（点估计 / CI 下界 ≥ 0.80），以非退化行为准，
    #      退化行（qhat=inf：名义覆盖 1.0、拒绝率 1.0 的全集退化）单独披露，不得计入恢复
    print(f"\n=== 恢复判据（审计阈值 {AUDIT_THRESHOLD}，pre-specified operational audit threshold）===")
    recovery = {}
    for direction in out["direction"].unique():
        sub = out[(out["direction"] == direction) & (out["method"] == "target_recalib")]
        nd = sub[~sub["qhat_inf"]]
        deg = sub[sub["qhat_inf"] & (sub["coverage"] >= AUDIT_THRESHOLD)]
        p = nd[nd["coverage"] >= AUDIT_THRESHOLD]
        c = nd[nd["ci_lo"] >= AUDIT_THRESHOLD]
        w_row = out[(out["direction"] == direction) & (out["method"] == "weighted_cp")].iloc[0]
        recovery[direction] = {
            "min_budget_point_ge_080_nondegenerate": int(p["budget_pct"].min()) if len(p) else None,
            "min_budget_cilo_ge_080_nondegenerate": int(c["budget_pct"].min()) if len(c) else None,
            "degenerate_budgets_nominal_only": sorted(int(b) for b in deg["budget_pct"]),
            "weighted_cp_0budget": {"coverage": float(w_row["coverage"]),
                                    "rejection_rate": float(w_row["rejection_rate"])},
            "note": None if len(c) else ("预算梯度内未达成 CI 下界 ≥ 0.80"
                                         if len(nd) else "全部预算行退化")}
        r = recovery[direction]
        wtxt = (f"weighted CP（0 标注）点估计 {r['weighted_cp_0budget']['coverage']:.4f}"
                f"/拒绝率 {r['weighted_cp_0budget']['rejection_rate']:.2f}")
        ptxt = f"{r['min_budget_point_ge_080_nondegenerate']}%" \
            if r["min_budget_point_ge_080_nondegenerate"] is not None else "梯度内未达成"
        ctxt = f"{r['min_budget_cilo_ge_080_nondegenerate']}%" \
            if r["min_budget_cilo_ge_080_nondegenerate"] is not None else "梯度内未达成"
        dtxt = f"；退化行 {r['degenerate_budgets_nominal_only']} 仅名义达标" \
            if r["degenerate_budgets_nominal_only"] else ""
        print(f"[{direction}] 非退化：点估计≥0.80 最小预算 = {ptxt}；CI下界≥0.80 最小预算 = "
              f"{ctxt}{dtxt}；{wtxt}")

    rep = {"predeclarations": __doc__.split("实现级预声明")[1].split("产出")[0].strip(),
           "draw_seed": DRAW_SEED, "audit_threshold": AUDIT_THRESHOLD,
           "recovery": recovery, "rows": rows}
    Path("data/interim/parse_reports").mkdir(parents=True, exist_ok=True)
    Path("data/interim/parse_reports/recovery_cost_report.json").write_text(
        json.dumps(rep, indent=2, default=float), encoding="utf-8")
    print(f"\n共 {len(out)} 行 → results/recovery_cost_table.csv")


if __name__ == "__main__":
    main()
