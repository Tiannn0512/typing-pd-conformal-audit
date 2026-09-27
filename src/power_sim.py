#!/usr/bin/env python
"""power_sim.py — 先验功效模拟表（TODO-3.3，主终点 family 构成依据）

预登记三分类判定（分析冻结协议 §5 / 计划书 v1.3.2 §2）：
    目标域测试集覆盖 K/n 的 Clopper-Pearson 95% CI：
      下界 ≥ 0.80 → Compatible（相容）
      上界 < 0.90 → Incompatible（不相容，覆盖退化证据）
      其间        → Undetermined（证据不足）
模拟：K ~ Binomial(n, π_true)，每 cell 独立重复（默认 50,000 次，向量化），
统计三种判定的经验概率。seed = configs/seeds.yaml unit_test_seed（确定性）。

预登记降级规则（TODO-3.3 golden gate）：primary 方向在真覆盖 = 0.90 时
P(Undetermined) > 60% → 该方向降 exploratory。

用法：
    python src/power_sim.py --tests "tappy2mit:n85,mit2tappy:n227,gold_merged2self:n457,mit2typd:n33" \
        --true-cov 0.90,0.85,0.80,0.70
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.stats import beta

PRIMARY_DIRECTIONS = ("tappy2mit", "mit2tappy", "gold_merged2self")
DEMOTION_THRESHOLD = 0.60  # 真覆盖=0.90 时 Undetermined 概率超过此值 → 降 exploratory（预登记）


def clopper_pearson_ci(k: np.ndarray, n: int, conf: float = 0.95) -> tuple[np.ndarray, np.ndarray]:
    """向量化 Clopper-Pearson 精确二项 CI。k 可为数组；K=0 → 下界 0，K=n → 上界 1。"""
    a = 1.0 - conf
    lo = np.where(k == 0, 0.0, beta.ppf(a / 2, k, n - k + 1))
    hi = np.where(k == n, 1.0, beta.ppf(1 - a / 2, k + 1, n - k))
    return lo, hi


def classify(lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """三分类判定（向量化）：0=Compatible, 1=Incompatible, 2=Undetermined。"""
    out = np.full(len(lo), 2, dtype=int)
    out[lo >= 0.80] = 0
    out[hi < 0.90] = 1
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tests", default="tappy2mit:n85,mit2tappy:n227,gold_merged2self:n457,mit2typd:n33")
    ap.add_argument("--true-cov", default="0.90,0.85,0.80,0.70")
    ap.add_argument("--reps", type=int, default=50_000)
    ap.add_argument("--out", default="results/power_table.csv")
    args = ap.parse_args()

    seed = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "configs" / "seeds.yaml").read_text(encoding="utf-8")
    )["unit_test_seed"]
    rng = np.random.default_rng(seed)

    tests = [(name, int(n.lstrip("n"))) for name, n in (t.split(":") for t in args.tests.split(","))]
    true_covs = [float(v) for v in args.true_cov.split(",")]

    rows = []
    for name, n in tests:
        for pi in true_covs:
            k = rng.binomial(n, pi, size=args.reps)
            lo, hi = clopper_pearson_ci(k, n)
            verdict = classify(lo, hi)
            rows.append({
                "direction": name,
                "is_primary": name in PRIMARY_DIRECTIONS,
                "n": n,
                "true_coverage": pi,
                "reps": args.reps,
                "seed": seed,
                "p_compatible": float(np.mean(verdict == 0)),
                "p_incompatible": float(np.mean(verdict == 1)),
                "p_undetermined": float(np.mean(verdict == 2)),
            })
    table = pd.DataFrame(rows)
    Path(args.out).parent.mkdir(exist_ok=True)
    table.to_csv(args.out, index=False)

    # 降级规则判定（预登记）：primary 方向在 π=0.90 时 P(Undetermined) > 60%
    demotions = []
    for name in PRIMARY_DIRECTIONS:
        row = table[(table.direction == name) & (table.true_coverage == 0.90)].iloc[0]
        if row.p_undetermined > DEMOTION_THRESHOLD:
            demotions.append(name)

    meta = {
        "rule": f"primary 方向 π=0.90 时 P(Undetermined) > {DEMOTION_THRESHOLD:.0%} → 降 exploratory（预登记）",
        "demotions": demotions,
        "primary_family_after_rule": [d for d in PRIMARY_DIRECTIONS if d not in demotions],
        "seed": seed,
        "reps": args.reps,
    }
    Path("data/interim/parse_reports/power_sim_report.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8")

    print(table.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\n[power_sim] 降级规则: {meta['primary_family_after_rule'] or '（无存留）'}"
          f"｜降级: {demotions or '无'}")


if __name__ == "__main__":
    main()
