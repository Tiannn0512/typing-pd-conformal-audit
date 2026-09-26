#!/usr/bin/env python
"""run_pipeline.py — Phase 4 共形审计主管线（TODO-3.5 冒烟入口）

--mode smoke（TODO-3.5，严格读法）：端到端跑通 Tappy→MIT 方向（源训练/校准 → 目标测试 →
split conformal 预测集 → 内存内覆盖计算），**只输出工程状态与格式合法性断言**；
覆盖数值不打印、不落盘、不进任何报告——预注册时序硬约束（analysis_plan_v1.md 文件头）。

pass 判定（全部满足）：
  S1 数据装载：source/target 特征 15 列、无缺失、标签二值
  S2 源内切分：train/cal 受试者级不相交
  S3 模型拟合：LR 概率行和=1
  S4 校准：分位数量有限且 ∈ [0,1]
  S5 预测集：每测试点集合 ⊆ {0,1} 且非空（split CP 性质）
  S6 覆盖格式：覆盖率可计算且 ∈ [0,1]（数值本身不输出）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cp.conformal import lac_scores, predict_sets_split  # noqa: E402


def load_features(dataset: str) -> tuple[np.ndarray, np.ndarray]:
    df = pd.read_csv("data/processed/subjects.csv")
    sub = df[df["dataset"] == dataset]
    cols = [c for c in sub.columns if c.startswith("L1_")]
    X = sub[cols].to_numpy(dtype=float)
    y = sub["label_pd"].to_numpy(dtype=int)
    assert not np.isnan(X).any(), f"{dataset} 特征含 NaN"
    assert set(np.unique(y)) <= {0, 1}, f"{dataset} 标签非二值"
    return X, y


def run_smoke(scenario: str, seed: int = 1) -> tuple[bool, list[str]]:
    source, target = scenario.split("2")
    stages: list[str] = []

    # S1 数据装载
    X_s, y_s = load_features(source)
    X_t, y_t = load_features(target)
    ok = X_s.shape[1] == X_t.shape[1] == 15 and len(X_s) > 0 and len(X_t) > 0
    stages.append(f"S1 数据装载 source={X_s.shape} target={X_t.shape}: {'PASS' if ok else 'FAIL'}")
    if not ok:
        return False, stages

    # S2 源内切分（受试者级：一人一行，天然不相交）
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(X_s))
    n_cal = max(1, int(0.3 * len(X_s)))
    cal_idx, tr_idx = idx[:n_cal], idx[n_cal:]
    ok = set(cal_idx).isdisjoint(set(tr_idx)) and len(y_tr := y_s[tr_idx]) > 1 and len(np.unique(y_cal := y_s[cal_idx])) == 2
    stages.append(f"S2 源内切分 train={len(tr_idx)} cal={len(cal_idx)} 不相交+校准双类: {'PASS' if ok else 'FAIL'}")
    if not ok:
        return False, stages

    # S3 模型拟合
    scaler = StandardScaler().fit(X_s[tr_idx])
    clf = LogisticRegression(random_state=42, max_iter=1000).fit(scaler.transform(X_s[tr_idx]), y_tr)
    probs = clf.predict_proba(scaler.transform(X_t))
    ok = bool(np.allclose(probs.sum(axis=1), 1.0))
    stages.append(f"S3 模型拟合 + 目标域概率行和=1: {'PASS' if ok else 'FAIL'}")

    # S4 校准
    scores_cal = lac_scores(probs_cal := clf.predict_proba(scaler.transform(X_s[cal_idx])), y_cal)
    from cp.conformal import split_conformal_quantile
    q = split_conformal_quantile(scores_cal, alpha=0.10)
    ok = np.isfinite(q) and 0.0 <= q <= 1.0
    stages.append(f"S4 校准分位数有限且∈[0,1]: {'PASS' if ok else 'FAIL'}")

    # S5 预测集
    sets = predict_sets_split(scores_cal, probs, alpha=0.10)
    ok = all(sset <= {0, 1} and len(sset) >= 1 for sset in sets)
    stages.append(f"S5 预测集 ⊆{{0,1}} 且非空: {'PASS' if ok else 'FAIL'}")

    # S6 覆盖格式（数值不输出——预注册时序硬约束）
    hits = [int(y in sset) for y, sset in zip(y_t, sets)]
    cov = float(np.mean(hits)) if hits else float("nan")
    ok = np.isfinite(cov) and 0.0 <= cov <= 1.0
    stages.append(f"S6 覆盖格式可计算且∈[0,1]（数值不落盘）: {'PASS' if ok else 'FAIL'}")

    return all("FAIL" not in st for st in stages), stages


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="tappy2mit")
    ap.add_argument("--mode", default="smoke", choices=["smoke"])
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    if args.mode != "smoke":
        raise SystemExit("仅实现 smoke 模式（Phase 4 正式模式随 TODO-4.x 交付）")

    ok, stages = run_smoke(args.scenario, args.seed)
    for st in stages:
        print(f"[pilot:{args.scenario}] {st}")
    print(f"[pilot:{args.scenario}] SMOKE {'PASS' if ok else 'FAIL'}"
          f"（覆盖数值按预注册时序约束不打印/不落盘）")
    Path("logs").mkdir(exist_ok=True)
    with open("logs/pilot_smoke_status.txt", "a", encoding="utf-8") as f:
        f.write(f"{args.scenario} seed={args.seed}: {'PASS' if ok else 'FAIL'}\n")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
