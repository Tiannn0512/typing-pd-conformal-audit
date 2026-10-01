#!/usr/bin/env python
"""build_tables.py — 清洗管线 + 冻结队列表 + 分析就绪特征表（TODO-2.1）

规则来源：configs/cleaning.yaml（逐条对应分析冻结协议 v1 §1/§2，label-blind）。
执行顺序（预登记，不可调换）：
  ① digraph 池定义（keep_flag=True 且 latency/flight 非缺失；session 组首行计 no_predecessor）
  ② digraph 级规则（四库通用）：0 < hold ≤ 10s 且 0 < latency ≤ 10s
  ③ 固定文本规则（mit/typd/oe）：flight ≤ 3s；session 速率 ≥ 20 字符/分
  ④ session 级规则（四库统一）：有效 digraph ≥ 100
  ⑤ 访视选择（冻结协议 §1）：MIT 每人仅首次访视（文件名 epoch 最早，label-blind）
     ——⑤在③④之前执行：访视选择是 session 集合定义，先定集合再验规则
  ⑥ person 级规则：存活 session 内有效 digraph ≥ 300
  ⑦ 队列定义（此处才用标签）：require_label / require_events / Tappy 单纯震颤主分析排除
     / OE H&Y0 规则不可操作化记录（公开数据无该字段）

输出：
  data/processed/sessions.parquet   session 级记录表（每 session 的规则结果）
  data/processed/subjects.csv       分析就绪 person 表（L1 特征四库 + Tappy 原生 L2 + 标签 + QC 计数）
  results/cohort_flow.csv           冻结队列表（全项目唯一权威样本数口径）
  data/interim/parse_reports/build_tables_report.json  运行报告 + gate 检查
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HOLD_MAX_MS = 10_000
FLIGHT_MAX_MS = 3_000
MIN_RATE = 20.0
SESSION_MIN_DIGRAPH = 100
PERSON_MIN_DIGRAPH = 300

INTERIM = Path("data/interim")
PROCESSED = Path("data/processed")
REPORTS = INTERIM / "parse_reports"

EVENTS = {
    "mit": INTERIM / "mit_digraph.parquet",
    "tappy": INTERIM / "tappy_events.parquet",
    "typd": INTERIM / "typd_events.parquet",
    "oe": INTERIM / "oe_events.parquet",
}
PRESS_COL = {"mit": "press_ms", "typd": "press_ms", "oe": "keydown", "tappy": None}


def load_labels() -> dict[str, pd.DataFrame]:
    """标签旁表 → 统一 schema(subject, label_pd, tremor_only, label_source)。仅在 ⑦ 使用。
    NaN 防护（2026-09-26 终审 B/F1 修正）：对**原始源列**在比较强转之前断言——
    比较运算会把 NaN 静默转 False（标签缺失滑入 HC 组），对派生列断言永远不触发。"""
    mit = []
    for cs in ("MIT-CS1PD", "MIT-CS2PD"):
        df = pd.read_csv(INTERIM.parent / "raw" / "mit" / cs / f"GT_DataPD_{cs}.csv")
        assert df["gt"].notna().all(), f"{cs} GT gt 列含 NaN"
        for _, r in df.iterrows():
            # gt 列被 read_csv 自动推断为 bool（或保持 "True" 字符串）——双态兼容
            gt = r["gt"]
            label_pd = bool(gt) if isinstance(gt, (bool, np.bool_)) else str(gt).strip().lower() == "true"
            mit.append({"subject": str(int(r["pID"])), "label_pd": label_pd,
                        "tremor_only": False, "label_source": "clinical"})
    typd = pd.read_csv(INTERIM / "typd_clinical.csv")
    assert typd["Group"].notna().all(), "typd 临床表 Group 列含 NaN"
    typd = pd.DataFrame({
        "subject": typd["subject"],
        "label_pd": typd["Group"] == "PD",
        "tremor_only": False,
        "label_source": "clinical",
    })
    tappy = pd.read_csv(INTERIM / "tappy_users.csv")
    assert tappy["Parkinsons"].notna().all() and tappy["Tremors"].notna().all(),         "tappy 标签表 Parkinsons/Tremors 含 NaN"
    tappy = pd.DataFrame({
        "subject": tappy["subject"].astype(str),
        "label_pd": tappy["Parkinsons"] == True,   # noqa: E712
        "tremor_only": (tappy["Tremors"] == True) & (tappy["Parkinsons"] == False),  # noqa: E712
        "label_source": "self_report",
    })
    oe = pd.read_csv(INTERIM / "oe_subjects.csv")
    assert oe["diagnosis"].notna().all(), "oe_subjects diagnosis 列含 NaN"
    oe = pd.DataFrame({
        "subject": oe["subject"].astype(str),
        "label_pd": oe["diagnosis"] == 1,
        "tremor_only": False,
        "label_source": "self_report",
    })
    out = {"mit": pd.DataFrame(mit), "typd": typd, "tappy": tappy, "oe": oe}
    # 标签 NaN 防护第二层（源列断言见上；此处派生列断言对 bool 列恒真、对 subject 列有效）
    for name, df_lab in out.items():
        assert df_lab["subject"].notna().all(), f"{name} 标签表 subject 含 NaN"
        assert df_lab["label_pd"].notna().all(), f"{name} 标签表 label_pd 含 NaN"
        assert df_lab["tremor_only"].notna().all(), f"{name} 标签表 tremor_only 含 NaN"
    return out


def clean_dataset(dataset: str, flow: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """返回 (存活 digraph DataFrame, session 记录表 DataFrame)。flow 原地追加队列表行。"""
    df = pd.read_parquet(EVENTS[dataset])
    press = PRESS_COL[dataset]
    n_raw_events = len(df)
    subjects_raw = df["subject"].nunique()

    # ① digraph 指派 session 评估粒度（CHG-1：typd 升为 visit 级——同一受试者全部 trial 合并；
    #    digraph 派生口径不受影响，仅 session 级规则的评估单位变化）
    if dataset == "typd":
        df = df.copy()
        df["session"] = df["subject"].astype(str)

    # ① digraph 池：keep_flag + 时间戳齐全（组首行 = no_predecessor，非违规）
    pool = df[df["keep_flag"]].copy()
    n_no_pred = int(pool["latency_ms"].isna().sum())
    pool = pool[pool["latency_ms"].notna() & pool["flight_ms"].notna()]
    n_pool = len(pool)

    # ② digraph 通用规则
    ok = (pool["hold_ms"] > 0) & (pool["hold_ms"] <= HOLD_MAX_MS) \
        & (pool["latency_ms"] > 0) & (pool["latency_ms"] <= HOLD_MAX_MS)
    n_drop_hold_latency = int((~ok).sum())
    pool = pool[ok]
    n_after_universal = len(pool)  # 快照：flight 过滤前（S2 行显示口径）

    # ③ 固定文本规则
    n_drop_flight = 0
    if dataset in ("mit", "typd", "oe"):
        okf = pool["flight_ms"] <= FLIGHT_MAX_MS
        n_drop_flight = int((~okf).sum())
        pool = pool[okf]

    # session 打字速率（固定文本；press 时间戳取自事件表自带列：mit/typd=press_ms，oe=keydown）
    if dataset in ("mit", "typd", "oe"):
        pcol = "press_ms" if dataset != "oe" else "keydown"
        sess_stat = pool.groupby(["subject", "session"], observed=True).agg(
            n_valid=("hold_ms", "size"),
            t0=(pcol, "min"),
            t1=(pcol, "max"),
        ).reset_index()
        sess_stat["rate"] = sess_stat["n_valid"] / ((sess_stat["t1"] - sess_stat["t0"]) / 60_000.0).replace(0, np.nan)
    else:
        sess_stat = pool.groupby(["subject", "session"], observed=True).size().rename("n_valid").reset_index()
        sess_stat["rate"] = np.nan

    # ⑤ MIT 访视选择（先于 session 规则执行——session 集合定义）
    sess_stat["visit_selected"] = True
    n_drop_visit_sessions = 0
    if dataset == "mit":
        sess_stat["epoch"] = sess_stat["session"].str.split(".").str[0].astype("int64")
        keep_sess = sess_stat.groupby("subject", observed=True)["epoch"].transform("min") == sess_stat["epoch"]
        n_drop_visit_sessions = int((~keep_sess).sum())
        sess_stat = sess_stat[keep_sess].drop(columns=["epoch"])

    # ③b 速率规则（仅固定文本）+ ④ session 最小 digraph 数
    sess_stat["excluded_by"] = ""
    if dataset in ("mit", "typd", "oe"):
        m = sess_stat["rate"] < MIN_RATE
        sess_stat.loc[m, "excluded_by"] = "rate_lt20"
    m2 = sess_stat["n_valid"] < SESSION_MIN_DIGRAPH
    sess_stat.loc[m2 & (sess_stat["excluded_by"] == ""), "excluded_by"] = "valid_lt100"
    # 一个 session 若同时违反速率与最小数，保留首个原因（计数不重复）

    kept_sessions = sess_stat[sess_stat["excluded_by"] == ""]
    n_drop_rate = int((sess_stat["excluded_by"] == "rate_lt20").sum())
    n_drop_min100 = int((sess_stat["excluded_by"] == "valid_lt100").sum())

    # S5 行数值快照——必须在 person 过滤之前（合并终审 B/发现1：2026-09-26 首修位置错误，
    # 快照落在了 person 过滤后致 S5==S6；本次移至 session 级过滤之后、person 过滤之前）
    s5_sessions = int(len(kept_sessions))
    s5_digraphs = int(kept_sessions["n_valid"].sum())

    # ⑥ person 级规则（口径：有存活 session 且合计 <300 才算 person 规则排除；
    #              唯一 session 已被 session 级规则剔光的人归入 n_drop_all_sessions）
    persons_before = set(sess_stat["subject"].unique())
    per_subj = kept_sessions.groupby("subject", observed=True)["n_valid"].sum()
    ok_subj = set(per_subj[per_subj >= PERSON_MIN_DIGRAPH].index)
    kept_sessions = kept_sessions[kept_sessions["subject"].isin(ok_subj)]
    persons_after = set(kept_sessions["subject"].unique())
    n_drop_all_sessions = len(persons_before - set(per_subj.index))          # session 级规则剔光者
    n_drop_person = len(set(per_subj.index) - ok_subj)                        # 真 person<300 排除

    # 最终 digraph 集合 = 存活 session 内的池
    kept_keys = kept_sessions[["subject", "session"]]
    final = pool.merge(kept_keys, on=["subject", "session"], how="inner")
    sess_stat["n_digraphs_final"] = sess_stat["session"].map(final.groupby("session", observed=True).size()).fillna(0).astype("int64")
    # person 出队者标记（合并终审 B/发现2：出队者的 session 行须可辨识，
    # 否则 excluded_by=='' 口径会多计 2,560−2,508 的行）
    sess_stat["person_excluded"] = ~sess_stat["subject"].isin(persons_after)

    # 队列表行（subject 级在此处只记 raw；标签相关行在 main() 的 ⑦ 统一追加）
    subjects_kept = final["subject"].nunique()
    _s0_note = ("解析层事件在案；session 计数=visit（trial 数=338，评估粒度见 CHG-1）" if dataset == "typd" else "解析层事件在案")
    flow.append({"dataset": dataset, "step": "S0_raw_events", "n_subjects": subjects_raw,
                 "n_sessions": int(df["session"].nunique()),
                 "n_digraphs": n_raw_events, "note": _s0_note})
    flow.append({"dataset": dataset, "step": "S1_digraph_rules", "n_subjects": subjects_raw,
                 "n_sessions": int(df["session"].nunique()), "n_digraphs": n_pool,
                 "note": f"digraph 池（keep_flag+时间戳齐）；no_predecessor={n_no_pred}"})
    flow.append({"dataset": dataset, "step": "S2_universal_rules", "n_subjects": subjects_raw,
                 "n_sessions": int(df["session"].nunique()), "n_digraphs": int(n_after_universal),
                 "note": f"hold/latency (0,10s] 剔除 {n_drop_hold_latency}"})
    if dataset in ("mit", "typd", "oe"):
        flow.append({"dataset": dataset, "step": "S3_fixed_text_rules", "n_subjects": subjects_raw,
                     "n_sessions": int(df["session"].nunique()), "n_digraphs": int(len(pool)),
                     "note": f"flight>3s 剔除 {n_drop_flight}"})
    flow.append({"dataset": dataset, "step": "S4_visit_selection", "n_subjects": subjects_raw,
                 "n_sessions": int(len(sess_stat) + n_drop_visit_sessions), "n_digraphs": int(len(pool)),
                 "note": f"MIT 首次访视外 session 剔除 {n_drop_visit_sessions}" if n_drop_visit_sessions else "不适用"})
    flow.append({"dataset": dataset, "step": "S5_session_rules", "n_subjects": subjects_raw,
                 "n_sessions": s5_sessions, "n_digraphs": s5_digraphs,
                 "note": f"rate<20 剔除 {n_drop_rate}；valid<100 剔除 {n_drop_min100}"})
    flow.append({"dataset": dataset, "step": "S6_person_rules", "n_subjects": subjects_kept,
                 "n_sessions": int(len(kept_sessions)), "n_digraphs": int(kept_sessions["n_valid"].sum()),
                 "note": f"person<300 排除 {n_drop_person}；唯一 session 被 session 级规则剔光者 {n_drop_all_sessions}"})

    sess_stat.insert(0, "dataset", dataset)
    sess_stat["subject"] = sess_stat["subject"].astype(str)  # 跨库 concat：MIT 为 int，统一 str
    return final, sess_stat, set(df["subject"].astype(str).unique())


def person_features(final: pd.DataFrame, dataset: str) -> pd.DataFrame:
    """person 级 L1 特征（15 列）+ Tappy 原生 L2（6 列）。"""
    rows = []
    for subj, g in final.groupby("subject", observed=True):
        rec = {"subject_id": f"{dataset}_{subj}", "dataset": dataset, "subject": str(subj)}
        for sig, col in (("hold", "hold_ms"), ("latency", "latency_ms"), ("flight", "flight_ms")):
            v = g[col].to_numpy(dtype="float64")
            rec[f"L1_{sig}_mean"] = float(np.mean(v))
            rec[f"L1_{sig}_median"] = float(np.median(v))
            rec[f"L1_{sig}_sd"] = float(np.std(v, ddof=1)) if len(v) > 1 else 0.0
            rec[f"L1_{sig}_p10"] = float(np.percentile(v, 10))
            rec[f"L1_{sig}_p90"] = float(np.percentile(v, 90))
        if dataset == "tappy":
            for hand in ("L", "R"):
                gh = g[g["hand_from"] == hand]
                for sig, col in (("hold", "hold_ms"), ("latency", "latency_ms"), ("flight", "flight_ms")):
                    rec[f"L2tappy_{sig}_{hand}_mean"] = float(gh[col].mean()) if len(gh) else np.nan
        rows.append(rec)
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/cleaning.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))

    PROCESSED.mkdir(parents=True, exist_ok=True)
    Path("results").mkdir(exist_ok=True)
    flow: list[dict] = []
    finals, sess_all = {}, []
    raw_subjects = {}
    for dataset in ("mit", "tappy", "typd", "oe"):
        final, sess_stat, subj_set = clean_dataset(dataset, flow)
        finals[dataset] = final
        sess_all.append(sess_stat)
        raw_subjects[dataset] = subj_set

    # FEATURE-DEF-2：导出 S1-S6 清洗终池事件表（L2/L3 特征的冻结事件基，2026-09-26 用户批准）
    final_pool = pd.concat(
        [f.assign(subject=f["subject"].astype(str)) for f in finals.values()],
        ignore_index=True)
    INTERIM.mkdir(parents=True, exist_ok=True)
    final_pool.to_parquet(INTERIM / "final_digraphs.parquet", index=False)

    # ⑦ 队列定义（标签在此才介入）
    labels = load_labels()
    subj_rows = []
    for dataset, final in finals.items():
        lab = labels[dataset]
        feats = person_features(final, dataset)
        feats = feats.merge(lab, on="subject", how="left")

        # require_label / require_events：无标签行（merge 后 label_pd 为 NaN）= events-no-labels
        # coerce：无标签幸存者使合并列出现 NaN/object，必须显式还原布尔（防 ~True==-2 陷阱）
        n_no_label = int(feats["label_pd"].isna().sum())
        feats["tremor_only"] = feats["tremor_only"].fillna(False).astype(bool)
        feats = feats[feats["label_pd"].notna()].copy()
        feats["label_pd"] = feats["label_pd"].astype(bool)
        # tremor_only 主分析排除
        n_tremor = int(feats["tremor_only"].sum())
        feats_main = feats[~feats["tremor_only"]].copy()
        subj_rows.append((dataset, feats, feats_main, n_no_label, n_tremor))

        # require_events 显式留痕（合并终审 B/发现7）：有标签但无任何解析层事件者
        labeled_no_events = int(len(lab) - lab["subject"].isin(raw_subjects[dataset]).sum())
        last = [f for f in flow if f["dataset"] == dataset][-1]
        flow.append({"dataset": dataset, "step": "S7_label_rules", "n_subjects": int(len(feats_main)),
                     "n_sessions": int(last["n_sessions"]), "n_digraphs": int(last["n_digraphs"]),
                     "note": f"无标签排除 {n_no_label}；单纯震颤主分析排除 {n_tremor}；"
                             f"有标签无事件排除 {labeled_no_events}"})
        flow.append({"dataset": dataset, "step": "S8_eligible_main", "n_subjects": int(len(feats_main)),
                     "n_sessions": int(last["n_sessions"]), "n_digraphs": int(last["n_digraphs"]),
                     "note": f"PD={int(feats_main['label_pd'].sum())} HC={int((~feats_main['label_pd']).sum())}"})

    subjects_all = pd.concat([fm for _, _, fm, _, _ in subj_rows], ignore_index=True)
    subjects_full = pd.concat([fa for _, fa, _, _, _ in subj_rows], ignore_index=True)
    sessions_out = pd.concat(sess_all, ignore_index=True)

    # label_excluded 标记：session 属于清洗幸存但被标签规则出队者（主要为 tappy 29+3）
    eligible_keys = set(zip(subjects_all["dataset"], subjects_all["subject"].astype(str)))
    sessions_out["label_excluded"] = [
        (d, str(sub)) not in eligible_keys for d, sub in zip(sessions_out["dataset"], sessions_out["subject"])
    ]
    # session 唯一性断言（TODO-1.4 移交 W3 验收项，2026-09-26 登记闭环）
    dup = sessions_out.duplicated(subset=["dataset", "subject", "session"])
    assert not dup.any(), f"session 唯一性断言失败：{int(dup.sum())} 条重复 (dataset,subject,session)"

    subjects_out = subjects_all.copy()
    cols_front = ["subject_id", "dataset", "subject", "label_pd", "label_source"]
    subjects_out = subjects_out[cols_front + [c for c in subjects_out.columns if c not in cols_front]]
    subjects_out.to_csv(PROCESSED / "subjects.csv", index=False)
    sessions_out.to_parquet(PROCESSED / "sessions.parquet", index=False)

    # 冻结队列表（results/cohort_flow.csv，入库）
    flow_df = pd.DataFrame(flow)
    totals = []
    for step in flow_df["step"].unique():
        sub = flow_df[flow_df["step"] == step]
        if step in ("S7_label_rules", "S4_visit_selection", "S1_digraph_rules", "S2_universal_rules", "S3_fixed_text_rules"):
            continue  # 过程行不进 TOTAL（避免重复计数）
        totals.append({"dataset": "TOTAL", "step": step,
                       "n_subjects": int(sub["n_subjects"].sum()),
                       "n_sessions": int(sub["n_sessions"].sum()),
                       "n_digraphs": int(sub["n_digraphs"].sum()),
                       "note": ""})
    flow_df = pd.concat([flow_df, pd.DataFrame(totals)], ignore_index=True)
    flow_df.to_csv("results/cohort_flow.csv", index=False)

    n_eligible = int(len(subjects_all))
    n_pd = int(subjects_all["label_pd"].sum())
    gate_pass = n_eligible >= 400
    report = {
        "config_echo": Path(args.config).name,
        "thresholds": {"hold_max_ms": HOLD_MAX_MS, "flight_max_ms": FLIGHT_MAX_MS,
                       "min_rate": MIN_RATE, "session_min_digraph": SESSION_MIN_DIGRAPH,
                       "person_min_digraph": PERSON_MIN_DIGRAPH},
        "n_eligible_total": n_eligible,
        "n_pd_total": n_pd,
        "n_hc_total": n_eligible - n_pd,
        "per_dataset_eligible": {d: int(len(fm)) for d, _, fm, _, _ in subj_rows},
        "gate_min400": {"pass": gate_pass, "n_eligible": n_eligible},
        "oe_hy0_rule": cfg["cohort_rules"]["oe_hy0_rule"],
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "build_tables_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"[build_tables] eligible={n_eligible} (PD={n_pd}/HC={n_eligible - n_pd}) "
          f"per-dataset={report['per_dataset_eligible']}")
    print(f"[build_tables] gate(≥400): {'PASS' if gate_pass else 'FAIL'}")
    if not gate_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
