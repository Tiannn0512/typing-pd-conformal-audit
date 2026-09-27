#!/usr/bin/env python
"""parse_mit.py — MIT-CSXPD (neuroQWERTY) 事件解析器（TODO-1.1）

复刻官方 nqDataLoader.py（PD 格式分支）的加载与过滤规则，逐条对应：

官方 loadDataFile (PD branch):
    f0 = 按键字符（带引号）; f1 = HoldTime; f2 = TimeEnd(release); f3 = TimeStart(press)
    （注释 "No CHANGED 2<->3"：官方把 f3 当 press、f2 当 release）

官方 sanityCheck 剔除（复刻为 keep_sanity 判定）：
    R1 TimeStart <= 0        → 首行绝对纪元时间戳行（press 存成大负数）即由此剔除
    R2 TimeEnd  <= 0
    R3 HoldTime < 0
    R4 HoldTime >= 5（秒，未换算单位前判定）
    R5 非连续 press 时间：官方 while 循环逐行复刻——diff(press)<0 的行标记并在
       临时数组中用前一行值替换，直到无逆序（迭代处理多重逆序）

官方 autoFilt（loadDataFile 默认 True）：filtData(FLT_NO_MOUSE | FLT_NO_LONG_META)
    FLT_NO_MOUSE:     key 匹配 ("mouse.+")
    FLT_NO_LONG_META: key 匹配 ("Shift.+")|("Alt.+")|("Control.+")
    本解析器默认执行同口径并分别报告两步剔除数，便于对拍。

输出：每事件一行（保留 press/release 原始时间戳，ms）；
digraph 派生列（char_from/char_to/latency_ms/flight_ms）按官方定义就地计算：
    flight[i] = press[i] - press[i-1]      （官方 dataFT 定义）
    latency[i] = press[i] - release[i-1]   （与 Tappy 口径对齐；首行 NaN，不用官方的 0 填充）
    char_from[i] = char[i-1]; char_to[i] = char[i]
label-blind：本脚本不读 GT 标签入事件表（gt 仅用于校验 subject 集合一致性，输出在 parse report）。

用法：
    python src/data/parse_mit.py --raw data/raw/mit --out data/interim/mit_digraph.parquet
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from data.digraph_derive import add_digraph_timing

# ---- 官方 filtData 正则（原样复制，含引号锚定）----
P_MOUSE = re.compile(r'("mouse.+")')
P_LONG_META = re.compile(r'("Shift.+")|("Alt.+")|("Control.+")')

FILE_RE = re.compile(r"([0-9]+)\.([0-9]+)_([0-9]+)_([0-9]+)\.csv")  # 官方 genFileStruct


def sanity_keep(dataHT: np.ndarray, t_start: np.ndarray, t_end: np.ndarray) -> np.ndarray:
    """官方 sanityCheck 的 good 标记（True=保留）。逐条对应 R1–R5。"""
    bad = t_start <= 0                      # R1
    bad = bad | (t_end <= 0)                # R2
    bad = bad | (dataHT < 0)                # R3
    bad = bad | (dataHT >= 5)               # R4（秒）
    # R5 非连续 press：官方 while 循环逐行复刻
    non_cons_tmp = np.zeros(len(t_start)) == 0   # all True
    non_cons = np.zeros(len(t_start)) > 0        # all False
    start_tmp = t_start.copy()
    while np.sum(non_cons_tmp) > 0:
        non_cons_tmp = np.append([False], np.diff(start_tmp) < 0)
        non_cons = non_cons | non_cons_tmp
        idx = np.arange(len(non_cons_tmp))[non_cons_tmp]
        start_tmp[idx] = start_tmp[idx - 1]
    bad = bad | non_cons
    return ~bad


def parse_session_file(path: Path) -> dict:
    """解析单个 session CSV，返回事件级 DataFrame（已过 sanityCheck + autoFilt）。

    加载与官方逐字对齐：np.genfromtxt(dtype=None)——键名保留引号（官方 filtData
    正则以引号为字面量锚点，剥引号会漏剔 Shift_L 等长 meta 键，对拍已验证此坑）。
    """
    data = np.genfromtxt(str(path), dtype=None, delimiter=",", skip_header=0)
    data = np.atleast_1d(data)  # 单行文件时 genfromtxt 返回 0-d
    keys = data["f0"].astype(str)               # f0 = 键名（带引号，官方口径）
    ht = data["f1"].astype(float)               # f1 = HoldTime
    t_end = data["f2"].astype(float)            # f2 = TimeEnd(release)，官方映射
    t_start = data["f3"].astype(float)          # f3 = TimeStart(press)，官方映射
    n_raw = len(keys)

    keep = sanity_keep(ht, t_start, t_end)
    n_sanity_removed = int((~keep).sum())

    keys, ht, t_start, t_end = keys[keep], ht[keep], t_start[keep], t_end[keep]

    # 官方 autoFilt：mouse + long meta（在带引号键名上匹配，与官方一致）
    lbl = np.array([P_MOUSE.match(k) is None for k in keys])
    lbl &= np.array([P_LONG_META.match(k) is None for k in keys])
    n_autofilt_removed = int((~lbl).sum())
    keys, ht, t_start, t_end = keys[lbl], ht[lbl], t_start[lbl], t_end[lbl]

    n = len(keys)
    df = pd.DataFrame(
        {
            "char": [k.strip('"') for k in keys],  # 仅输出时剥引号
            "press_ms": t_start * 1000.0,
            "release_ms": t_end * 1000.0,
            "hold_ms": ht * 1000.0,
        }
    )
    # latency/flight 用共享规范派生（hold 保持官方 f1 口径，hold_col=None 不覆盖）
    df = add_digraph_timing(df, "press_ms", "release_ms", group_cols=None, hold_col=None)
    df["char_from"] = df["char"].shift(1)
    df["char_to"] = df["char"]
    # 官方过滤（sanityCheck + autoFilt）已在上方完成，落表行全部为 keep
    # （latency/flight 可为负：Phase 2 预登记清洗规则 hold/latency≤0 或 >10s 处置）
    df["keep_flag"] = True
    return {
        "df": df,
        "n_raw": n_raw,
        "n_sanity_removed": n_sanity_removed,
        "n_autofilt_removed": n_autofilt_removed,
    }


def load_gt(gt_path: Path) -> pd.DataFrame:
    rows = list(csv.DictReader(open(gt_path, encoding="utf-8")))
    out = []
    for r in rows:
        for col in ("file_1", "file_2"):
            fn = (r.get(col) or "").strip()
            if fn:
                out.append({"subject": int(r["pID"]), "gt": r["gt"].strip() == "True", "session_file": fn})
    return pd.DataFrame(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw/mit")
    ap.add_argument("--out", default="data/interim/mit_digraph.parquet")
    ap.add_argument("--report", default="data/interim/parse_reports/parse_mit_report.json")
    args = ap.parse_args()

    raw = Path(args.raw)
    gt = pd.concat(
        [load_gt(raw / "MIT-CS1PD" / "GT_DataPD_MIT-CS1PD.csv"),
         load_gt(raw / "MIT-CS2PD" / "GT_DataPD_MIT-CS2PD.csv")],
        ignore_index=True,
    )

    data_files = sorted((raw / "MIT-CS1PD" / "data_MIT-CS1PD").glob("*.csv")) + sorted(
        (raw / "MIT-CS2PD" / "data_MIT-CS2PD").glob("*.csv")
    )
    gt_files = set(gt["session_file"])
    disk_files = {p.name for p in data_files}
    files_missing_in_gt = sorted(disk_files - gt_files)
    files_missing_on_disk = sorted(gt_files - disk_files)

    frames, per_file = [], []
    for p in data_files:
        m = FILE_RE.match(p.name)
        if not m:
            raise ValueError(f"文件名不符合官方结构: {p.name}")
        epoch, p_id, rep, exp = m.groups()
        res = parse_session_file(p)
        df = res["df"]
        df.insert(0, "dataset", "mit")
        df.insert(1, "subject", int(p_id))
        df.insert(2, "session", p.stem)
        df["rep"] = int(rep)
        df["exp"] = int(exp)
        frames.append(df)
        per_file.append(
            {"file": p.name, "subject": int(p_id), **{k: v for k, v in res.items() if k != "df"},
             "n_kept": len(df)}
        )

    out = pd.concat(frames, ignore_index=True)
    out = out.astype(
        {
            "dataset": "category", "char": "category", "char_from": "category", "char_to": "category",
            "subject": "int32", "rep": "int8", "exp": "int8",
            "press_ms": "float64", "release_ms": "float64", "hold_ms": "float32",
            "latency_ms": "float32", "flight_ms": "float32",
        }
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.out, index=False)

    subjects = sorted(gt["subject"].unique())
    n_pd = int(gt.drop_duplicates("subject")["gt"].sum())
    n_hc = int(len(subjects) - n_pd)
    report = {
        "n_subjects": len(subjects),
        "n_pd": n_pd,
        "n_hc": n_hc,
        "n_sessions": len(data_files),
        "n_events_raw": sum(r["n_raw"] for r in per_file),
        "n_events_sanity_removed": sum(r["n_sanity_removed"] for r in per_file),
        "n_events_autofilt_removed": sum(r["n_autofilt_removed"] for r in per_file),
        "n_events_kept": len(out),
        "files_missing_in_gt": files_missing_in_gt,
        "files_missing_on_disk": files_missing_on_disk,
        "subjects_without_files": sorted(set(subjects) - set(gt[gt["session_file"].isin(disk_files)]["subject"])),
        "per_file": per_file,
    }
    rep_path = Path(args.report)
    rep_path.parent.mkdir(parents=True, exist_ok=True)
    rep_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        f"[parse_mit] subjects={report['n_subjects']} (PD={n_pd}/HC={n_hc}) "
        f"sessions={report['n_sessions']} events kept={report['n_events_kept']} "
        f"sanity_removed={report['n_events_sanity_removed']} autofilt_removed={report['n_events_autofilt_removed']}"
    )
    if files_missing_in_gt or files_missing_on_disk:
        print(f"[parse_mit][WARN] file-set mismatch: gt_only={files_missing_on_disk} disk_only={files_missing_in_gt}")


if __name__ == "__main__":
    main()
