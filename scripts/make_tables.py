#!/usr/bin/env python
"""make_tables.py — 论文表格定稿

冻结来源：全部单元格由 results/*.csv 程序化派生（零手抄数字——审计门要求图表
数字与 results/ 一致）。输出 results/paper_tables/table1..6.csv（写作期直接引用）。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

OUT = Path("results/paper_tables")


def fmt(r: pd.Series, cols: tuple[str, ...] = ("coverage",)) -> str:
    cov = r[cols[0]]
    return f"{cov:.3f} [{r['ci_lo']:.3f}, {r['ci_hi']:.3f}]"


def table1_cohort() -> None:
    cf = pd.read_csv("results/cohort_flow.csv")
    cf.to_csv(OUT / "table1_cohort_flow.csv", index=False)


def table2_primary() -> None:
    pf = pd.read_csv("results/primary_family.csv")
    rows = []
    for _, r in pf.iterrows():
        hq = r["holm_q"]
        hq_s = f"{hq:.2e}" if isinstance(hq, (int, float)) and not pd.isna(hq) else str(hq)
        rows.append({
            "direction": r["direction"], "model": r["model"], "tier": int(r["tier"]),
            "K/n": f"{int(r['k'])}/{int(r['n'])}",
            "coverage (95% CI)": f"{r['coverage']:.3f} [{r['ci_lo']:.3f}, {r['ci_hi']:.3f}]",
            "Holm q": hq_s,
            "verdict": r["primary_verdict"],
            "mean set size": f"{r['mean_size']:.2f}",
            "singleton rate": f"{r['singleton_rate']:.3f}",
        })
    pd.DataFrame(rows).to_csv(OUT / "table2_primary_family.csv", index=False)


def table3_class_conditional() -> None:
    cc = pd.read_csv("results/class_conditional_coverage.csv")
    rows = []
    for _, r in cc.iterrows():
        rows.append({
            "direction": r["direction"], "model": r["model"],
            "overall": f"{r['coverage_overall']:.3f} [{r['ci_lo_overall']:.3f}, {r['ci_hi_overall']:.3f}]",
            "PD": f"{r['coverage_cls_pd']:.3f} [{r['ci_lo_cls_pd']:.3f}, {r['ci_hi_cls_pd']:.3f}] (n={int(r['n_cls_pd'])})",
            "HC": f"{r['coverage_cls_hc']:.3f} [{r['ci_lo_cls_hc']:.3f}, {r['ci_hi_cls_hc']:.3f}] (n={int(r['n_cls_hc'])})",
            "gap PD": f"{r['gap_pd_vs_overall']:+.3f}",
            "gap HC": f"{r['gap_hc_vs_overall']:+.3f}",
        })
    pd.DataFrame(rows).to_csv(OUT / "table3_class_conditional.csv", index=False)


def table4_recovery_cost() -> None:
    rc = pd.read_csv("results/recovery_cost_table.csv")
    rows = []
    for _, r in rc.iterrows():
        rows.append({
            "direction": r["direction"], "method": r["method"],
            "budget %": int(r["budget_pct"]),
            "target labels": int(r["n_target_labels"]),
            "coverage": f"{r['coverage']:.3f} [{r['ci_lo']:.3f}, {r['ci_hi']:.3f}]",
            "PD coverage": f"{r['cpc_pd']:.3f}",
            "mean set size": f"{r['mean_size']:.2f}",
            "singleton rate": f"{r['singleton_rate']:.3f}",
            "rejection rate": f"{r['rejection_rate']:.3f}",
            "degenerate": bool(r["qhat_inf"]),
        })
    pd.DataFrame(rows).to_csv(OUT / "table4_recovery_cost.csv", index=False)


def table5_three_arm() -> None:
    ta = pd.read_csv("results/three_arm_stress_test.csv")
    rows = []
    for _, r in ta.iterrows():
        rows.append({
            "arm": r["arm"], "scope": r["scope"],
            "source pool": f"{int(r['n_pd_pool'])}PD/{int(r['n_hc_pool'])}HC (pi={r['realized_prev']:.3f})",
            "flips": f"{int(r['n_flip_pd'])}/{int(r['n_flip_hc'])}",
            "coverage (delta)": f"{r['coverage']:.3f} ({r['delta_coverage_vs_phenotype']:+.3f})",
            "mean size (delta)": f"{r['mean_size']:.2f} ({r['delta_mean_size_vs_phenotype']:+.2f})",
            "PD": f"{r['cpc_pd']:.3f}", "HC": f"{r['cpc_hc']:.3f}",
            "reproduced": "yes" if r["reproduced"] else "no",
        })
    pd.DataFrame(rows).to_csv(OUT / "table5_three_arm.csv", index=False)


def table6_sensitivity() -> None:
    sb = pd.read_csv("results/sensitivity_batch.csv")
    rows = []
    for _, r in sb.iterrows():
        cov = f"{r['coverage']:.4f}"
        if r["variant"] == "seeds_1_50":
            cov += f" ± {r['seed_std']:.4f}"
        elif "ci_lo" in r and pd.notna(r.get("ci_lo")):
            cov += f" [{r['ci_lo']:.4f}, {r['ci_hi']:.4f}]"
        rows.append({"variant": r["variant"], "direction": r["direction"],
                     "coverage": cov})
    pd.DataFrame(rows).to_csv(OUT / "table6_sensitivity.csv", index=False)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in (table1_cohort, table2_primary, table3_class_conditional,
              table4_recovery_cost, table5_three_arm, table6_sensitivity):
        f()
        print(f"[ok] {f.__name__}")
    print(f"→ {OUT}/table1..6.csv")


if __name__ == "__main__":
    main()
