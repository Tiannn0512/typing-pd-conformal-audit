#!/usr/bin/env python
"""qc.py — Phase 2 QC 报告生成器（TODO-2.2）

产出 results/qc_report.md：清洗后分析就绪数据的质量审计。
Gate（TODO-2.2）：①无 Tier-A（L1）特征缺失 >50%；②MIT 性别失衡（文献口径：对照女多
17pp）显式记录进分组审计预备——本数据 MIT 无性别字段，按"字段不可得+文献口径照抄"记录。

用法：python src/data/qc.py --config configs/cleaning.yaml
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PROCESSED = Path("data/processed")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/cleaning.yaml")
    ap.add_argument("--out", default="results/qc_report.md")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))

    subjects = pd.read_csv(PROCESSED / "subjects.csv")
    sessions = pd.read_parquet(PROCESSED / "sessions.parquet")
    eligible_keys = subjects[["dataset", "subject"]].assign(subject=lambda d: d["subject"].astype(str))
    sessions = sessions.merge(eligible_keys, on=["dataset", "subject"], how="inner")  # 仅 475 名入队者
    # 严格存活口径（合并终审 B/发现2 统一）：session 级幸存 且 非 person/label 出队
    alive = sessions[(sessions["excluded_by"] == "") & (~sessions["person_excluded"]) & (~sessions["label_excluded"])]
    flow = pd.read_csv("results/cohort_flow.csv")

    l1_cols = [c for c in subjects.columns if c.startswith("L1_")]
    l2_cols = [c for c in subjects.columns if c.startswith("L2")]
    lines: list[str] = []
    ap_line = lines.append
    ap_line("# QC 报告 — Phase 2 清洗后分析就绪数据（TODO-2.2）")
    ap_line("")
    ap_line(f"**生成**：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')} ｜ **配置**：{args.config}"
            f" ｜ **权威队列表**：results/cohort_flow.csv（eligible=475：PD 270/HC 205）")
    ap_line("")

    ap_line("## 1. 特征缺失率（Tier-A = L1 三信号 15 列）")
    ap_line("")
    ap_line("| 特征列 | 缺失数 | 缺失率 |")
    ap_line("|---|---|---|")
    miss_rates = {}
    for c in l1_cols + l2_cols:
        n_miss = int(subjects[c].isna().sum())
        rate = n_miss / len(subjects)
        miss_rates[c] = rate
        if n_miss > 0:
            ap_line(f"| {c} | {n_miss} | {rate:.1%} |")
    n_zero_miss_l1 = sum(1 for c in l1_cols if miss_rates[c] == 0)
    ap_line(f"")
    ap_line(f"L1 15 列中 {n_zero_miss_l1} 列零缺失；"
            f"L1 最大缺失率 = {max(miss_rates[c] for c in l1_cols):.1%}（gate：<50% → "
            f"{'PASS' if max(miss_rates[c] for c in l1_cols) < 0.5 else 'FAIL'}）。"
            f"L2tappy 6 列仅 Tappy 行（173/475）非空，属设计内档位差异，不计缺失。")
    ap_line("")

    ap_line("## 2. 零方差列")
    ap_line("")
    zero_var = [c for c in l1_cols if subjects[c].nunique(dropna=True) <= 1]
    ap_line(f"L1 零方差列：{zero_var if zero_var else '无'}")

    ap_line("")
    ap_line("## 3. 性别分布（分组审计预备）")
    ap_line("")
    ap_line("| 数据集 | 字段可得性 | 分布 |")
    ap_line("|---|---|---|")
    ap_line("| mit | **本数据无性别字段**（GT 列不含 Gender）| 文献口径照抄：对照组女性偏多 ~17pp"
            "（可行性报告 §四；计划书局限声明已冻结）——分组审计按文献口径预备 |")
    tappy_g = subjects[subjects.dataset == "tappy"].merge(
        pd.read_csv("data/interim/tappy_users.csv")[["subject", "Gender"]], on="subject", how="left")
    tappy_tab = tappy_g.groupby(["label_pd", "Gender"]).size().to_dict()
    ap_line(f"| tappy | 有（自报）| {tappy_tab} |")
    typd_c = pd.read_csv("data/interim/typd_clinical.csv")
    typd_m = subjects[subjects.dataset == "typd"].merge(typd_c[["subject", "Gender"]], on="subject", how="left")
    ap_line(f"| typd | 有（临床）| {typd_m.groupby(['label_pd', 'Gender']).size().to_dict()} |")
    ap_line("| oe | **本数据无性别字段** | 不可得（在线招募未含性别入公开 CSV）|")
    ap_line("")

    ap_line("## 4. session 数分布（每人，存活 session）")
    ap_line("")
    ap_line("| 数据集 | session 定义 | min | 中位 | max |")
    ap_line("|---|---|---|---|---|")
    for ds, definition in (("mit", "visit 文件"), ("tappy", "月文件（USER_YYMM）"),
                           ("typd", "visit（全部 TEX trial 合并评估，CHG-1）"), ("oe", "participant×response")):
        g = alive[alive.dataset == ds].groupby("subject").size()
        ap_line(f"| {ds} | {definition} | {g.min()} | {int(g.median())} | {g.max()} |")
    ap_line("")
    ap_line("**Tappy 月文件切 session 口径记录**：session = 自然月文件（USER_YYMM），同一人跨月多 "
            "session 属设计内（自然打字纵向流）；tappy 为自由文本，flight/速率规则豁免，仅适用 "
            "digraph 通用规则 + valid<100。")
    ap_line("")

    ap_line("## 5. person 有效 digraph 分布")
    ap_line("")
    for ds in ("mit", "tappy", "typd", "oe"):
        g = alive[alive.dataset == ds].groupby("subject")["n_valid"].sum()
        ap_line(f"- {ds}: min={int(g.min())} / median={int(g.median())} / max={int(g.max())}")
    ap_line("")
    big = alive[alive.dataset == "tappy"].groupby("subject")["n_valid"].sum()
    n_big = int((big > 100_000).sum())
    ap_line(f"**观察**：Tappy 有 {n_big} 名用户有效 digraph >10 万（最大 {int(big.max()):,}，"
            f"约占 Tappy 总量 {big.max() / big.sum():.0%}）——person 级聚合下每人一行不受影响，"
            f"但 Phase 4 涉及 Tappy digraph 总量口径的统计时须注意该长尾。")
    ap_line("")

    ap_line("## 6. Gate 检查")
    ap_line("")
    g1 = max(miss_rates[c] for c in l1_cols) < 0.5
    ap_line(f"- [x] 无 Tier-A 特征缺失 >50%：{'PASS（最大 ' + format(max(miss_rates[c] for c in l1_cols), '.1%') + '）' if g1 else 'FAIL'}")
    ap_line("- [x] MIT 性别失衡（对照女多 17pp，文献口径）已显式记录（§3；本数据无 MIT 性别字段，"
            "分组审计按文献口径预备——与计划书局限声明一致）")

    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"[qc] report -> {args.out}")
    print(f"[qc] gates: L1 missing {'PASS' if g1 else 'FAIL'}; gender imbalance documented")


if __name__ == "__main__":
    main()
