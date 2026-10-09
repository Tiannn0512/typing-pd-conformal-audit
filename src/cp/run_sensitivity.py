#!/usr/bin/env python
"""run_sensitivity.py — 敏感性分析批（TODO-4.10，plan §12 预登记五项）

登记清单与执行状态（预声明，先于首次运行；按防复发制度 §4 本脚本先行单独 commit）：
  1. α=0.20：primary 三方向 × LR × seed=1，k=⌈(n+1)(1−α)⌉ 同式——全执行。
  2. 50 seeds（split_seeds 1–50 登记）：primary 三方向 × LR，报告 mean/std/min/max
     ——全执行（50-seed 为描述性汇总，不作二项 n 膨胀，与 §5 纪律一致）。
  3. Tappy 震颤 3 人双向计入：tappy_users 中 Tremors=True & Parkinsons=False 者，
     分别以 PD / HC 标签拼回涉及 Tappy 的全部 primary 方向（tappy2mit 源侧 /
     mit2tappy 目标侧 / gold_merged2self 目标侧）——全执行。前置：同人 S6 规则
     （有效 digraph ≥300）逐人核查，不满足者如实剔除并报告。
  4. Tappy session 切分口径变体：月会话→季度会话（YYMM→YYYYQn），会话有效性
     规则不变（≥100 digraphs/会话；Tappy 无速率规则——S5 rate 对 tappy 为 NaN），
     冻结人池（173）固定不变、仅重聚合特征（灵敏度问题=特征构建稳健性，非队列
     重定义）——全执行。**验证锚点**：月单位重聚合复现 subjects.csv 特征——L1 15 列
     ≤1e-9、L2tappy 6 列 ≤1e-4（冻结 L2 为构建期 float32 累加产物，导出上转后不可
     精确复现，实测 max|Δ|≈1.6e-5；L1 逐位级。两容差均远小于任何真实配方错误的
     量级），否则中止不产出。
  5. ~~OE H&Y0 剔除~~：不适用（预注册：公开数据无 H&Y 字段）——不出行。
  6. 特征档位协变量（plan §2/§5"显式协变量记录"）：描述性表——12 方向 tier ×
     覆盖/AUC（读 frozen transfer_matrix.csv），无新拟合。
基线锚点：每方向 seed=1 原始管线对 primary_family.csv lr 行断言。
rng：无新随机性（切分 seed=登记 split_seeds；模型 42；全链确定性）。
产出：results/sensitivity_batch.csv + results/sensitivity_tier_covariate.csv
     + data/interim/parse_reports/sensitivity_report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cp.conformal import lac_scores, predict_sets_split, split_conformal_quantile  # noqa: E402
from cp.coverage_audit import ALPHA, CAP, DIRECTIONS, SEED, load_pooled  # noqa: E402
from cp.remediate import cp_ci  # noqa: E402
from models.run_transfer import load_matrix  # noqa: E402

L1_COLS = [f"L1_{s}_{stat}" for s in ("hold", "latency", "flight")
           for stat in ("mean", "median", "sd", "p10", "p90")]
# 列序必须与 run_transfer.tier_columns 逐位一致（sig 外层/h 内层）——拼接矩阵与
# 源模型按位置对齐，错位即静默特征置换
L2TAPPY_COLS = [f"L2tappy_{s}_{h}_mean" for s in ("hold", "latency", "flight")
                for h in ("L", "R")]


def person_features_tappy(rows: pd.DataFrame) -> pd.DataFrame:
    """build_tables.person_features(tappy) 的逐字复刻（L1 15 列 + L2tappy 6 列）。"""
    recs = []
    for subj, g in rows.groupby("subject", observed=True):
        rec = {"subject": str(subj)}
        for sig, col in (("hold", "hold_ms"), ("latency", "latency_ms"),
                         ("flight", "flight_ms")):
            v = g[col].to_numpy(dtype="float64")
            rec[f"L1_{sig}_mean"] = float(np.mean(v))
            rec[f"L1_{sig}_median"] = float(np.median(v))
            rec[f"L1_{sig}_sd"] = float(np.std(v, ddof=1)) if len(v) > 1 else 0.0
            rec[f"L1_{sig}_p10"] = float(np.percentile(v, 10))
            rec[f"L1_{sig}_p90"] = float(np.percentile(v, 90))
        for hand in ("L", "R"):
            gh = g[g["hand_from"] == hand]
            for sig, col in (("hold", "hold_ms"), ("latency", "latency_ms"),
                             ("flight", "flight_ms")):
                rec[f"L2tappy_{sig}_{hand}_mean"] = float(gh[col].mean()) if len(gh) else np.nan
        recs.append(rec)
    return pd.DataFrame(recs)


def session_valid_features(events: pd.DataFrame, unit: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """按会话单位（month=原口径 / quarter=变体）重应用会话有效性（≥100）再人级聚合。
    Tappy 无速率规则（S5 rate=NaN）——仅 n≥100。返回（人级特征, 存活事件行）。"""
    ev = events.copy()
    if unit == "quarter":
        yy = ev["session"].str.extract(r"_(\d{2})(\d{2})$")
        ev["sess_unit"] = (ev["subject"] + "_Q20" + yy[0] + "Q"
                           + ((yy[1].astype(int) - 1) // 3 + 1).astype(str))
    else:
        ev["sess_unit"] = ev["subject"] + "_" + ev["session"]
    n = ev.groupby("sess_unit", observed=True).size()
    keep_units = set(n[n >= 100].index)
    kept = ev[ev["sess_unit"].isin(keep_units)]
    return person_features_tappy(kept), kept


def load_direction(cfg: dict) -> dict:
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
        ids_t = pool["subject_id"].to_numpy()
    else:
        X_t, y_t = load_matrix(tgt, tier)
        subjects = pd.read_csv("data/processed/subjects.csv")
        ids_t = subjects[subjects["dataset"] == tgt]["subject_id"].to_numpy()
    assert X_s.shape[1] == X_t.shape[1]
    return {"X_s": X_s, "y_s": y_s, "X_t": X_t, "y_t": y_t, "ids_t": ids_t, "tier": tier}


def run_fit(X_s, y_s, X_t, y_t, alpha: float, seed: int) -> dict:
    idx = np.arange(len(X_s))
    tr_idx, cal_idx = train_test_split(idx, test_size=0.30, random_state=seed,
                                       stratify=y_s)
    scaler = StandardScaler().fit(X_s[tr_idx])
    clf = LogisticRegression(random_state=42, max_iter=1000)
    clf.fit(scaler.transform(X_s[tr_idx]), y_s[tr_idx])
    scores_cal = lac_scores(clf.predict_proba(scaler.transform(X_s[cal_idx])), y_s[cal_idx])
    sets = predict_sets_split(scores_cal, clf.predict_proba(scaler.transform(X_t)), alpha)
    hits = np.array([t in s for t, s in zip(y_t, sets)])
    sizes = np.array([len(s) for s in sets])
    k, n = int(hits.sum()), int(len(hits))
    lo, hi = cp_ci(k, n)
    return {"k": k, "n": n, "coverage": k / n, "ci_lo": lo, "ci_hi": hi,
            "cpc_pd": float(hits[y_t == 1].mean()), "cpc_hc": float(hits[y_t == 0].mean()),
            "mean_size": float(sizes.mean()), "singleton_rate": float((sizes == 1).mean())}


def main() -> None:
    ap = argparse.ArgumentParser(description="Sensitivity batch (TODO-4.10)")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    assert args.all, "须 --all（§12 预登记批整体执行）"

    frozen = pd.read_csv("results/primary_family.csv")
    rows = []

    def anchor_assert(direction: str, m: dict) -> None:
        f = frozen[(frozen["direction"] == direction) & (frozen["model"] == "lr")].iloc[0]
        assert int(f["k"]) == m["k"] and int(f["n"]) == m["n"]
        for col in ("coverage", "cpc_pd", "cpc_hc", "mean_size", "singleton_rate"):
            assert abs(float(f[col]) - m[col]) < 1e-12, f"{direction} {col} 锚点漂移"

    dirs = {c["direction"]: c for c in DIRECTIONS}
    loaded = {name: load_direction(cfg) for name, cfg in dirs.items()}

    # ---- 锚点（seed=1 原始）
    for name, d in loaded.items():
        m = run_fit(d["X_s"], d["y_s"], d["X_t"], d["y_t"], ALPHA, SEED)
        anchor_assert(name, m)
        rows.append({"variant": "anchor_seed1", "direction": name, **m})

    # ---- 1. α=0.20
    for name, d in loaded.items():
        m = run_fit(d["X_s"], d["y_s"], d["X_t"], d["y_t"], 0.20, SEED)
        rows.append({"variant": "alpha_020", "direction": name, **m})

    # ---- 2. 50 seeds（运行时对登记口径断言，防漂移）
    seeds_cfg = yaml.safe_load((Path(__file__).resolve().parents[2] / "configs" / "seeds.yaml")
                               .read_text(encoding="utf-8"))
    seeds = list(range(1, 51))
    assert seeds == list(seeds_cfg["split_seeds"]), "50-seed 清单与 seeds.yaml split_seeds 不符"
    for name, d in loaded.items():
        covs = [run_fit(d["X_s"], d["y_s"], d["X_t"], d["y_t"], ALPHA, s)["coverage"]
                for s in seeds]
        rows.append({"variant": "seeds_1_50", "direction": name, "coverage": float(np.mean(covs)),
                     "seed_std": float(np.std(covs, ddof=1)), "seed_min": float(min(covs)),
                     "seed_max": float(max(covs)), "n_seeds": 50})

    # ---- 3+4. Tappy 事件层变体（先验证聚合器锚点）
    ev = pd.read_parquet("data/interim/final_digraphs.parquet")
    ev_t = ev[ev["dataset"] == "tappy"].copy()
    frozen_tappy = pd.read_csv("data/processed/subjects.csv")
    frozen_tappy = frozen_tappy[frozen_tappy["dataset"] == "tappy"]
    feat_m, _ = session_valid_features(ev_t, "month")
    feat_m = feat_m.set_index("subject")
    idx_order = frozen_tappy["subject"].astype(str).values
    mine = feat_m.loc[idx_order]
    # 锚点口径：L1 ≤1e-9（逐位级，仅求和序噪声）；L2tappy ≤1e-4——冻结 L2 值为
    # 构建期 float32 累加产物（导出 concat 上转 float64，从导出池只可复现到
    # ~1.6e-5，实测），ms 量纲下无关紧要；变体与锚点同一聚合器，内部自洽。
    max_diff = 0.0
    for col in L1_COLS + L2TAPPY_COLS:
        a = mine[col].to_numpy(dtype=float)
        b = frozen_tappy[col].to_numpy(dtype=float)
        atol = 1e-9 if col.startswith("L1_") else 1e-4
        assert np.allclose(a, b, rtol=0, atol=atol, equal_nan=True), \
            f"聚合器锚点失败: {col} max|Δ|={np.nanmax(np.abs(a - b))}"
        both = ~(np.isnan(a) | np.isnan(b))
        if both.any():
            max_diff = max(max_diff, float(np.abs(a[both] - b[both]).max()))
    print(f"[anchor] 月单位重聚合复现 subjects.csv Tappy L1+L2tappy（21 列；"
          f"L1 ≤1e-9、L2 ≤1e-4（构建期 float32 累加，实测 max|Δ|={max_diff:.2e}））")

    # 震颤 3 人（S6 ≥300 逐人核查——只数存活会话内事件）
    tu = pd.read_csv("data/interim/tappy_users.csv")
    tremor_ids = tu[(tu["Tremors"] == True) & (tu["Parkinsons"] == False)]["subject"].astype(str)  # noqa: E712
    ev_tr = ev_t[ev_t["subject"].astype(str).isin(set(tremor_ids))]
    tr_feat, ev_tr_kept = session_valid_features(ev_tr, "month")
    tr_feat = tr_feat[tr_feat["subject"].isin(set(tremor_ids))]
    n_dig = ev_tr_kept.groupby(ev_tr_kept["subject"].astype(str)).size()
    eligible = tr_feat[tr_feat["subject"].map(n_dig).fillna(0) >= 300].copy()
    print(f"[tremor] 候选 {len(set(tremor_ids))} 人，S6≥300 幸存 {len(eligible)} 人")
    assert len(eligible) >= 1, "震颤者无一人满足 S6，变体 3 不可执行"

    def tappy_matrix_with(extra: pd.DataFrame, labels: list[int]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        base = frozen_tappy[L1_COLS + L2TAPPY_COLS].to_numpy(dtype=float)
        y_base = frozen_tappy["label_pd"].astype(int).to_numpy()
        ex = extra[L1_COLS + L2TAPPY_COLS].to_numpy(dtype=float)
        assert not np.isnan(ex).any(), "拼接行含 NaN 特征"
        X = np.vstack([base, ex])
        y = np.concatenate([y_base, np.array(labels, int)])
        ids = np.concatenate([frozen_tappy["subject_id"].to_numpy(),
                              ("tappy_" + extra["subject"].astype(str)).to_numpy()])
        return X, y, ids

    for tag, lab in (("tremor_as_pd", 1), ("tremor_as_hc", 0)):
        X_tap, y_tap, _ = tappy_matrix_with(eligible, [lab] * len(eligible))
        # tappy2mit：源侧拼接
        d = loaded["tappy2mit"]
        m = run_fit(X_tap, y_tap, d["X_t"], d["y_t"], ALPHA, SEED)
        rows.append({"variant": tag, "direction": "tappy2mit", **m,
                     "note": f"源池 +{len(eligible)} 人"})
        # mit2tappy：目标侧拼接
        d = loaded["mit2tappy"]
        m = run_fit(d["X_s"], d["y_s"], X_tap, y_tap, ALPHA, SEED)
        rows.append({"variant": tag, "direction": "mit2tappy", **m,
                     "note": f"目标 +{len(eligible)} 人（分母含新行）"})
        # gold_merged2self：目标侧拼接（L1 only）
        d = loaded["gold_merged2self"]
        base = pd.read_csv("data/processed/subjects.csv")
        pool = base[base["dataset"].isin(["tappy", "oe"])]
        ex1 = eligible[L1_COLS].to_numpy(dtype=float)
        X_t2 = np.vstack([pool[[c for c in pool.columns if c.startswith("L1_")]].to_numpy(float), ex1])
        y_t2 = np.concatenate([pool["label_pd"].to_numpy(int), np.full(len(eligible), lab)])
        m = run_fit(d["X_s"], d["y_s"], X_t2, y_t2, ALPHA, SEED)
        rows.append({"variant": tag, "direction": "gold_merged2self", **m,
                     "note": f"目标 +{len(eligible)} 人（L1）"})

    # session 口径变体（冻结人池固定，特征重聚合）
    feat_q, ev_q_kept = session_valid_features(ev_t, "quarter")
    feat_q = feat_q.set_index("subject")
    assert set(idx_order).issubset(feat_q.index), "季度口径下冻结人池成员缺特征"
    q_mat = feat_q.loc[idx_order, L1_COLS + L2TAPPY_COLS].to_numpy(dtype=float)
    assert not np.isnan(q_mat).any(), "季度口径特征含 NaN"
    y_tap_frozen = frozen_tappy["label_pd"].astype(int).to_numpy()
    d = loaded["tappy2mit"]
    m = run_fit(q_mat, y_tap_frozen, d["X_t"], d["y_t"], ALPHA, SEED)
    rows.append({"variant": "session_quarter", "direction": "tappy2mit", **m,
                 "note": "源侧特征季度重聚合；人池固定 173"})
    d = loaded["mit2tappy"]
    m = run_fit(d["X_s"], d["y_s"], q_mat, y_tap_frozen, ALPHA, SEED)
    rows.append({"variant": "session_quarter", "direction": "mit2tappy", **m,
                 "note": "目标侧特征季度重聚合；人池固定 173"})
    d = loaded["gold_merged2self"]
    pool = pd.read_csv("data/processed/subjects.csv")
    pool = pool[pool["dataset"].isin(["tappy", "oe"])]
    tappy_pos = (pool["dataset"] == "tappy").to_numpy()
    X_t3 = pool[[c for c in pool.columns if c.startswith("L1_")]].to_numpy(float).copy()
    X_t3[tappy_pos] = feat_q.loc[idx_order, L1_COLS].to_numpy(dtype=float)
    m = run_fit(d["X_s"], d["y_s"], X_t3, pool["label_pd"].to_numpy(int), ALPHA, SEED)
    rows.append({"variant": "session_quarter", "direction": "gold_merged2self", **m,
                 "note": "目标 Tappy 切片季度重聚合；人池固定"})

    out = pd.DataFrame(rows)
    out.to_csv("results/sensitivity_batch.csv", index=False)

    # ---- 6. 特征档位协变量（描述性，frozen 矩阵）
    tm = pd.read_csv("results/transfer_matrix.csv")
    tier_tab = (tm.groupby("tier").agg(n_dirs=("direction", "count"),
                                       cov_mean=("coverage_mean", "mean"),
                                       cov_min=("coverage_mean", "min"),
                                       cov_max=("coverage_mean", "max"),
                                       auc_mean=("auc_mean", "mean")).reset_index())
    tier_tab.to_csv("results/sensitivity_tier_covariate.csv", index=False)

    print("\n=== 敏感性批（plan §12）===")
    for _, r in out.iterrows():
        cov = r.get("coverage")
        extra = f"±{r['seed_std']:.4f}" if r["variant"] == "seeds_1_50" else \
            f"CI[{r['ci_lo']:.4f},{r['ci_hi']:.4f}]" if "ci_lo" in r and pd.notna(r.get("ci_lo")) else ""
        print(f"[{r['variant']:<16}|{r['direction']:<17}] 覆盖={cov:.4f} {extra}")
    print("\n=== 档位协变量（描述性，12 方向 50-seed 均值）===")
    print(tier_tab.to_string(index=False))

    predecl = __doc__.split("登记清单与执行状态")[1].split("产出")[0].strip()
    Path("data/interim/parse_reports").mkdir(parents=True, exist_ok=True)
    Path("data/interim/parse_reports/sensitivity_report.json").write_text(
        json.dumps({"predeclarations": predecl, "rows": rows,
                    "tier_table": tier_tab.to_dict("records")}, indent=2, default=float),
        encoding="utf-8")
    print(f"\n共 {len(out)} 行 → results/sensitivity_batch.csv")


if __name__ == "__main__":
    main()
