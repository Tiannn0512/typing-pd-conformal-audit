#!/usr/bin/env python
"""parse_oe.py — Online English (CoNLL 2020 / OSF ew34b) 事件解析器（TODO-1.3）

原始格式（125MB 单大 CSV，9 列）：
    key, response_id, response_content, participant_id, sentence_id,
    sentence_content, diagnosis, keydown, keyup
    diagnosis 列只进 subjects 旁表（oe_subjects.csv），事件表 label-free
    每行 = 一个按键事件（keydown/keyup 同行，ms）；孤立事件 = keydown 或 keyup 缺失。

孤立键处理（官方仓库 neildhir/Parkinsons_typing_markers 的 preprocess.py
remove_solitary_key_presses）：官方对无法配对的孤立按键执行"移除"。本解析器保持
无损契约——孤立行打标（solitary=True，keep_flag=False）保留入表并计数，
Phase 2 清洗按官方口径移除（与官方移除等价，但保留决策留痕）。

digraph 派生（(participant_id, response_id) 内按 keydown 排序；response = 一次连续录入）：
    hold = keyup - keydown；latency = keydown[i] - keyup[i-1]；flight = keydown[i] - keydown[i-1]
    char_from/char_to = key[i-1]/key[i]（OE 有字符身份，L3 适用库）
diagnosis：官方 1=PD（自报），0=HC；文本列（response_content/sentence_content）不入表
    （特征三信号 + 字符身份已足够，减少存储与泄漏面）。

用法：
    python src/data/parse_oe.py --raw data/raw/oe/CoNLL_2020_Online_English.csv \
        --out data/interim/oe_events.parquet
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from data.digraph_derive import add_digraph_timing

USECOLS = ["key", "response_id", "participant_id", "sentence_id", "diagnosis", "keydown", "keyup"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw/oe/CoNLL_2020_Online_English.csv")
    ap.add_argument("--out", default="data/interim/oe_events.parquet")
    ap.add_argument("--subjects-out", default="data/interim/oe_subjects.csv")
    ap.add_argument("--report", default="data/interim/parse_reports/parse_oe_report.json")
    ap.add_argument("--chunksize", type=int, default=1_000_000)
    args = ap.parse_args()

    chunks = []
    n_rows_raw = 0
    for chunk in pd.read_csv(args.raw, usecols=USECOLS, chunksize=args.chunksize):
        n_rows_raw += len(chunk)
        chunks.append(chunk)
    df = pd.concat(chunks, ignore_index=True)
    del chunks

    # 孤立事件（keydown 或 keyup 缺失）→ 打标（官方口径 = 移除；此处保留决策到 Phase 2）
    df["solitary"] = df["keydown"].isna() | df["keyup"].isna()

    df["hold_ms"] = (df["keyup"] - df["keydown"]).astype("float32")

    # 组内排序派生 digraph 三元组。
    # 分组键 = (participant_id, response_id)：response 是一次连续录入，digraph 连续性只在
    # response 内成立；按 sentence 分组会把同句的多次 response 串成假 digraph
    # （2026-09-25 审核实测：10 组跨 response 合并、659 个假 digraph 可穿透清洗规则）。
    # session 定义随之 = participant × response（与 Tappy 月文件 = session 的口径同级）。
    df = add_digraph_timing(df, "keydown", "keyup",
                            group_cols=["participant_id", "response_id"], hold_col=None)
    g = df.groupby(["participant_id", "response_id"], sort=False)
    df["char_from"] = g["key"].shift(1)
    df["char_to"] = df["key"]

    # keep_flag 只表达解析层有效性：孤立键 + hold 非有限。
    # 组首行 latency/flight/char_from 为 NaN 属预期（组内无前驱），不参与 keep_flag 判定。
    # 注意用排序后的 df 内列（掩码与行序对齐），不用排序前计算的独立 Series。
    df["keep_flag"] = ~df["solitary"] & np.isfinite(df["hold_ms"])

    # 重复记录伪象计数（同一 (participant,response,key,keydown,keyup) 精确重复；
    # 是否去重 = Phase 2 预登记决策，此处只留痕）
    # 重复记录伪象（跨 response 的同键同时间戳双记；2026-09-25 审核实测 p=125 等 7 组）。
    # 键不含 response_id——伪象恰恰是跨 response 的，含之则精确漏计（复审必修项）。
    # 双口径留痕：冗余副本数(keep=first) 与 参与重复行数(keep=False)；去重决策留 Phase 2。
    dup_cols = ["participant_id", "key", "keydown", "keyup"]
    dup_mask = df.duplicated(subset=dup_cols, keep=False)
    n_dup_rows_participating = int(dup_mask.sum())
    n_dup_redundant_copies = int(df.duplicated(subset=dup_cols, keep="first").sum())
    df.insert(0, "dataset", "oe")
    df["subject"] = df["participant_id"].astype(str)
    df["session"] = df["participant_id"].astype(str) + "_" + df["response_id"].astype(str)  # session = participant × response（与 digraph 分组键一致）

    keep_cols = [
        "dataset", "subject", "session", "key", "char_from", "char_to",
        "keydown", "keyup", "hold_ms", "latency_ms", "flight_ms",
        "keep_flag", "solitary",
    ]
    out = df[keep_cols].copy()
    for c in ("dataset", "subject", "session", "key", "char_from", "char_to"):
        out[c] = out[c].astype("category")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.out, index=False)

    # 标签独立成表（与 typd_clinical.csv 对称；事件表 label-free，跨解析器 schema 一致）
    subjects = (
        df.drop_duplicates("subject")[["subject", "diagnosis"]]
        .reset_index(drop=True)
    )
    subjects["n_events"] = subjects["subject"].map(out["subject"].value_counts())
    subjects_path = Path(args.subjects_out)
    subjects.to_csv(subjects_path, index=False)

    per_subject_diag = subjects["diagnosis"].value_counts().to_dict()
    report = {
        "n_rows_raw": n_rows_raw,
        "n_duplicate_rows_participating": n_dup_rows_participating,
        "n_duplicate_redundant_copies": n_dup_redundant_copies,
        "n_rows_out": len(out),
        "n_solitary": int(df["solitary"].sum()),
        "n_subjects": int(out["subject"].nunique()),
        "diagnosis_counts_subjects": {str(k): int(v) for k, v in per_subject_diag.items()},
        "n_sessions": int(out["session"].nunique()),
        "diagnosis_unique_values": sorted(df["diagnosis"].dropna().unique().tolist()),
        "subjects_table": str(subjects_path),
    }
    rep = Path(args.report)
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        f"[parse_oe] rows={n_rows_raw} solitary={report['n_solitary']} "
        f"subjects={report['n_subjects']} diag(1=PD,0=HC)={report['diagnosis_counts_subjects']}"
    )


if __name__ == "__main__":
    main()
