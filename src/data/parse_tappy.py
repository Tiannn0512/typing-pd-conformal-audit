#!/usr/bin/env python
"""parse_tappy.py — Tappy Keystroke 事件长表解析器（TODO-1.2）

原始格式（622 个月文件 "Tappy Data/{USER}_{YYMM}.txt"，Tab 分隔，CRLF，尾空列）：
    列1 subject  列2 YYMMDD  列3 HH:MM:SS.mmm  列4 Hand(L/R)  列5 HoldTime
    列6 Direction(LL/LS/LR/RL/RR/RS/SL/SR/SS)  列7 LatencyTime  列8 FlightTime  列9 空

冻结口径（计划书 v1.3.2 §4.2 / TODO-1.2）：
    - Tappy 无字符身份列 → 长表按三信号最小集执行：hold/latency/flight，无 char 列
    - 长表字段：dataset/subject/session/hand_from/hand_to/direction/hold_ms/latency_ms/
      flight_ms/keep_flag + 两列 QC 布尔（subject_mismatch / field_valid）
    - session = 月文件（文件名 stem，USER_YYMM）；TODO-2.2 记录该切分口径
    - 零填充字符串（"0101.6"）→ float ms；解析失败或非有限的行 keep_flag=False（值置 NaN，
      不丢弃——失败行保留到 Phase 2 清洗，防静默丢数）

数据结构事实（2026-09-25 首轮实测，风险登记册 #1）：
    - 事件文件覆盖 266 个 subject ID（文件名均干净、格式合法）；标签档案仅 227 人
    - 49 个"有事件无标签"、10 个"有标签无事件"（交集 217 = 后续可入队上限）
    - 处置：本解析器只如实记录三向对账数；"无标签用户是否入队"是 Phase 2 冻结
      队列表的预登记决策，解析层不做任何排除
    - 少量列错位/脏行（direction 出现时间戳/日期/ID 形态垃圾）→ field_valid=False 打标保留

label-blind：标签表内容绝不 join 进本表；--labels 仅取 ID 集合做对账计数。

用法：
    python src/data/parse_tappy.py --raw data/raw/tappy \
        --labels data/raw/tappy/Archived-users-extracted --out data/interim/tappy_events.parquet
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNS = ["subject", "date", "time", "hand", "hold", "direction", "latency", "flight", "_trailing"]
TIMING_COLS = ["hold", "latency", "flight"]
VALID_DIRECTIONS = {"LL", "LR", "LS", "RL", "RR", "RS", "SL", "SR", "SS"}
VALID_HANDS = {"L", "R", "S"}


def parse_month_file(path: Path) -> tuple[pd.DataFrame, dict]:
    stem = path.stem  # {USER}_{YYMM}
    file_subject = stem.split("_")[0]
    df = pd.read_csv(
        path,
        sep="\t",
        header=None,
        names=COLUMNS,
        dtype={"subject": str, "hand": str, "direction": str, "hold": str, "latency": str, "flight": str},
        engine="c",
        quoting=3,  # QUOTE_NONE
        na_filter=False,
    )
    # 列9 应为全空；若某行列数异常 pandas 会进 _trailing 或缺列，做防御断言
    if not (df["_trailing"].fillna("") == "").all():
        raise ValueError(f"{path.name}: 尾列非空，schema 与预期不符")
    n_raw = len(df)

    # 行内列1 subject 与文件名一致性（不抛异常：脏行打标保留，Phase 2 预登记处置）
    # 已观察脏形态：真 ID 前粘连垃圾字符（"0EA27ICB0EA27ICBLF"、"00EA27ICBLF"）
    subject_mismatch = df["subject"].str.strip() != file_subject

    # 字段有效性：direction/hand 白名单（列错位行在此暴露）
    direction = df["direction"].str.strip()
    hand = df["hand"].str.strip()
    field_valid = direction.isin(VALID_DIRECTIONS) & hand.isin(VALID_HANDS)

    out = pd.DataFrame(
        {
            "dataset": "tappy",
            "subject": file_subject,
            "session": stem,
            "hand_from": hand,
            "hand_to": direction.str[1].where(direction.isin(VALID_DIRECTIONS)),  # 非法时置 NaN
            "direction": direction,
        }
    )
    keep = pd.Series(True, index=df.index)
    keep &= ~subject_mismatch          # ID 串位行打标（Phase 2 决定丢弃或修复）
    keep &= field_valid                # 列错位/垃圾字段行打标
    for c in TIMING_COLS:
        v = pd.to_numeric(df[c].str.strip(), errors="coerce")   # 零填充字符串 → float（ms）
        out[f"{c}_ms"] = v.astype("float32")
        keep &= v.notna() & np.isfinite(v)
    out["keep_flag"] = keep
    out["subject_mismatch"] = subject_mismatch
    out["field_valid"] = field_valid
    n_flagged_file = int((~keep).sum())

    qc = {
        "file": path.name,
        "n_raw": n_raw,
        "n_flagged": n_flagged_file,
        "n_subject_mismatch": int(subject_mismatch.sum()),
        "n_field_invalid": int((~field_valid).sum()),
        "subject_mismatch_samples": sorted(set(df.loc[subject_mismatch, "subject"]))[:5],
    }
    return out, qc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw/tappy")
    ap.add_argument("--labels", default="data/raw/tappy/Archived-users-extracted",
                    help="仅取 ID 集合做对账，不读标签内容")
    ap.add_argument("--out", default="data/interim/tappy_events.parquet")
    ap.add_argument("--report", default="data/interim/parse_reports/parse_tappy_report.json")
    args = ap.parse_args()

    data_dir = Path(args.raw) / "Tappy Data"
    files = sorted(data_dir.glob("*.txt"))
    if not files:
        raise FileNotFoundError(f"{data_dir} 下无月文件")

    frames, qcs = [], []
    for p in files:
        df, qc = parse_month_file(p)
        frames.append(df)
        qcs.append(qc)

    out = pd.concat(frames, ignore_index=True)
    for c in ("dataset", "subject", "session", "hand_from", "hand_to", "direction"):
        out[c] = out[c].astype("category")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.out, index=False)

    label_ids = {p.stem.replace("User_", "") for p in Path(args.labels).glob("User_*.txt")}
    event_ids = set(out["subject"].astype(str).unique())
    per_user = out.groupby("subject", observed=True).size()
    report = {
        "n_files": len(files),
        "n_rows": len(out),
        "n_rows_flagged": int((~out["keep_flag"]).sum()),
        "n_flagged_subject_mismatch": int(out["subject_mismatch"].sum()),
        "n_flagged_field_invalid": int((~out["field_valid"]).sum()),
        "n_users_in_events": len(event_ids),
        "n_users_in_labels": len(label_ids),
        "n_users_both": len(event_ids & label_ids),
        "n_users_labeled_without_events": len(label_ids - event_ids),
        "n_users_events_without_labels": len(event_ids - label_ids),
        "rows_per_user_min": int(per_user.min()),
        "rows_per_user_median": float(per_user.median()),
        "rows_per_user_max": int(per_user.max()),
        "files_with_flagged_rows": int(sum(1 for q in qcs if q["n_flagged"] > 0)),
        "direction_counts_top": {str(k): int(v) for k, v in out["direction"].value_counts().head(12).items()},
        "hand_from_counts": {str(k): int(v) for k, v in out["hand_from"].value_counts().items()},
    }
    rep = Path(args.report)
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        f"[parse_tappy] files={report['n_files']} rows={report['n_rows']} "
        f"flagged={report['n_rows_flagged']} (subj_mismatch={report['n_flagged_subject_mismatch']}, "
        f"field_invalid={report['n_flagged_field_invalid']})"
    )
    print(
        f"[parse_tappy] users: events={report['n_users_in_events']} labels={report['n_users_in_labels']} "
        f"both={report['n_users_both']} labeled_no_events={report['n_users_labeled_without_events']} "
        f"events_no_labels={report['n_users_events_without_labels']}"
    )
    print(f"[parse_tappy] directions(top)={report['direction_counts_top']}")


if __name__ == "__main__":
    main()
