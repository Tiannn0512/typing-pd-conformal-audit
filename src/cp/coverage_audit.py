#!/usr/bin/env python
"""coverage_audit.py — primary family 覆盖判定（TODO-4.2，论文主结果）

预注册口径（analysis_plan_v1.md §6/§7）：
  确证性分析 = 单一预指定切分（seed=1，configs/seeds.yaml split_seeds 首位；50-seed 均值
  仅用于描述性矩阵——同一批受试者重复 50 次不能当二项 n 膨胀精度）。
  源 70/30 分层 train/cal（LR 主参照 CHG-P1，零调参）→ split conformal α=0.10 →
  目标域全部冻结受试者覆盖 K/n。
  三分类（§6，名义，未调 CI）：hi<0.90 → Incompatible；否则 lo≥0.80 → Compatible；
  否则 Undetermined（重叠区 Incompatible 优先已钉）。
  Primary family 判定（§7，主结论）：H0 = 真实覆盖 ≥0.90（单侧不足），
  p = P_{Bin(n,0.90)}(K ≤ K_obs)；家族内 Holm（m=3，family-wise 0.10，
  步降阈值 α/3, α/2, α）；**主判定基于 Holm**：q_i < 0.10 → Incompatible（家族受控地
  确立覆盖 < 0.90）；未拒绝者按 §6 名义规则（lo ≥ 0.80 → Compatible，否则 Undetermined）。
  LGBM 对照（DEC-T1）同管线描述性报告，不进判定。

产出：results/primary_family.csv + primary_family_report.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.stats import binom

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime import config_path, require

from protocol import FAMILY_WISE, SEED, COVERAGE_H0, DIRECTIONS
from models.common import fit_direction
from cp.metrics import metrics


def holm(pvals: list[float]) -> list[float]:
    """Holm 步降 adjusted p-values（单调，cap 1.0）。"""
    m = len(pvals)
    order = np.argsort(pvals)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        val = (m - rank) * pvals[i]
        running = max(running, val)
        adj[i] = min(running, 1.0)
    return list(adj)


def run_direction(cfg: dict, model_name: str) -> dict:
    result = fit_direction(cfg, model_name)
    m = metrics(result["y_t"], result["sets"])
    columns = ("k", "n", "coverage", "ci_lo", "ci_hi", "mean_size", "singleton_rate", "cpc_pd", "cpc_hc")
    return {**{key: m[key] for key in columns},
            "p_one_sided": float(binom.cdf(m["k"], m["n"], COVERAGE_H0)),
            "tier": result["tier"], "n_source": result["n_source"], "n_cal": result["n_cal"]}


def nominal_three_class(lo: float, hi: float) -> str:
    """§6 名义规则（未调 CI，Incompatible 优先）。"""
    if hi < 0.90:
        return "Incompatible"
    if lo >= 0.80:
        return "Compatible"
    return "Undetermined"


def main() -> None:
    seeds_cfg = yaml.safe_load((config_path("seeds.yaml"))
                               .read_text(encoding="utf-8"))
    require(seeds_cfg["split_seeds"][0] == SEED, "确证性切分必须用登记 seed 首位")

    results = []
    for cfg in DIRECTIONS:
        for model in ("lr", "lgbm"):
            r = run_direction(cfg, model)
            r.update({"direction": cfg["direction"], "model": model})
            if model == "lr":
                r["nominal_three_class"] = nominal_three_class(r["ci_lo"], r["ci_hi"])
            results.append(r)

    # Holm（LR 主参照，m=3）
    lr_rows = [r for r in results if r["model"] == "lr"]
    pvals = [r["p_one_sided"] for r in lr_rows]
    qvals = holm(pvals)
    for r, q in zip(lr_rows, qvals):
        r["holm_q"] = q
        if q < FAMILY_WISE:
            r["primary_verdict"] = "Incompatible (family-controlled: coverage < 0.90 established)"
        else:
            r["primary_verdict"] = nominal_three_class(r["ci_lo"], r["ci_hi"]) + " (Holm 未拒绝)"

    Path("results").mkdir(exist_ok=True)  # 全新 checkout 一键重跑守卫（终审建议项）
    out = pd.DataFrame(results)
    # 对照模型的判定列显式 NA（不进 family、不参与判定；避免裸 NaN 歧义）
    for c in ("holm_q", "nominal_three_class", "primary_verdict"):
        out[c] = out.get(c, pd.Series("NA (comparator)", index=out.index))
        out[c] = out[c].fillna("NA (comparator)")
    cols_front = ["direction", "model", "tier", "k", "n", "coverage", "ci_lo", "ci_hi",
                  "p_one_sided", "holm_q", "nominal_three_class", "primary_verdict"]
    cols = [c for c in cols_front if c in out.columns] + \
           [c for c in out.columns if c not in cols_front]
    out = out[cols]
    out.to_csv("results/primary_family.csv", index=False)

    print(out[[c for c in cols_front if c in out.columns]].to_string(index=False))
    for r in lr_rows:
        print(f"[primary] {r['direction']}: K={r['k']}/{r['n']} cov={r['coverage']:.4f} "
              f"CI=[{r['ci_lo']:.4f},{r['ci_hi']:.4f}] 名义={r['nominal_three_class']} "
              f"Holm q={r['holm_q']:.4g} → 主判定={r['primary_verdict']}")
    (Path("results").parent / "data" / "interim" / "parse_reports").mkdir(parents=True, exist_ok=True)
    Path("data/interim/parse_reports/primary_family_report.json").write_text(
        json.dumps(results, indent=2, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
