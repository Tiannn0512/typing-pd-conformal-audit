#!/usr/bin/env python
"""overlap_priority_compare.py — 三分类重叠区两种归属的对照模拟

背景：三分类规则的 {lo≥0.80 且 hi<0.90} 重叠区归属在冻结文本中欠定义（审核发现）。
两种读法：
  Incompatible 优先（现行实现 classify()）：hi < 0.90 → Incompatible；否则 lo ≥ 0.80 → Compatible；否则 Undetermined
  Compatible 优先（条文顺序读法）：lo ≥ 0.80 → Compatible；否则 hi < 0.90 → Incompatible；否则 Undetermined
本脚本在同一模拟链路（Binomial → CP CI → 两种优先级分类）下输出 16 cells × 两口径的
判定概率对照，作为重叠区归属拍板的入账证据（决定：Incompatible 优先，2026-09-26 批准）。
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys_path = Path(__file__).resolve().parents[1] / "src"
import sys  # noqa: E402

sys.path.insert(0, str(sys_path))
from power_sim import clopper_pearson_ci  # noqa: E402

PRIMARY = ("tappy2mit", "mit2tappy", "gold_merged2self")


def classify_incompatible_first(lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """现行实现口径：hi<0.90 → Incompatible；否则 lo≥0.80 → Compatible；否则 Undetermined。"""
    out = np.full(len(lo), 2, dtype=int)  # Undetermined
    out[lo >= 0.80] = 0
    out[hi < 0.90] = 1  # 覆盖：重叠区归 Incompatible
    return out


def classify_compatible_first(lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """条文顺序读法口径：lo≥0.80 → Compatible；否则 hi<0.90 → Incompatible；否则 Undetermined。"""
    out = np.full(len(lo), 2, dtype=int)
    out[hi < 0.90] = 1
    out[lo >= 0.80] = 0  # 覆盖：重叠区归 Compatible
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tests", default="tappy2mit:n85,mit2tappy:n227,gold_merged2self:n457,mit2typd:n33")
    ap.add_argument("--true-cov", default="0.90,0.85,0.80,0.70")
    ap.add_argument("--reps", type=int, default=50_000)
    ap.add_argument("--out", default="results/overlap_priority_compare.csv")
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
            v_inc = classify_incompatible_first(lo, hi)
            v_com = classify_compatible_first(lo, hi)
            overlap = float(np.mean((lo >= 0.80) & (hi < 0.90)))
            rows.append({
                "direction": name, "is_primary": name in PRIMARY, "n": n, "true_coverage": pi,
                "reps": args.reps, "seed": seed,
                "overlap_mass": overlap,
                "inc_first_p_compatible": float(np.mean(v_inc == 0)),
                "inc_first_p_incompatible": float(np.mean(v_inc == 1)),
                "inc_first_p_undetermined": float(np.mean(v_inc == 2)),
                "com_first_p_compatible": float(np.mean(v_com == 0)),
                "com_first_p_incompatible": float(np.mean(v_com == 1)),
                "com_first_p_undetermined": float(np.mean(v_com == 2)),
            })
    table = pd.DataFrame(rows)
    Path(args.out).parent.mkdir(exist_ok=True)
    table.to_csv(args.out, index=False)

    show = ["direction", "n", "true_coverage", "overlap_mass",
            "inc_first_p_compatible", "inc_first_p_incompatible",
            "com_first_p_compatible", "com_first_p_incompatible"]
    print(table[show].to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\n[overlap_compare] 重叠区质量集中在 π=0.85 的 gold_merged2self 行——"
          f"两口径的检出力差异即拍板依据（详见 {args.out}）")


if __name__ == "__main__":
    main()
