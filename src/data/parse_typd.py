#!/usr/bin/env python
"""parse_typd.py — TyPD (i-PROGNOSIS DS2.5) 事件 + 临床表解析器（TODO-1.3）

原始格式（33 个受试者目录 Data/S##/，每人 5–11 个 trial S##_TEX##.txt）：
    首行为空行；其后每行脏格式（官方 ReadMe 写的是 5 字段 "Press,Tp,Release,Tr,NP"，
    实测为 4 字段且 "Release" 与时间戳粘连）：
        Press,<press_ms>,Release <release_ms>,<pressure(0-1)>
    时间为 ms；无按键身份列（L1 上限的实测依据，TODO-1.4 落档）；压力通道按协议弃用
    （可行性报告"协议不齐坑 1"），解析保留原始值仅作 QC，不入特征。

Excel 临床表 Demographics_Clinical_Characteristics.xlsx（sheet Demographics_Clinical）：
    Subject ID/Age/Gender/.../Group(PD-HC)/Years from diagnosis/Hoehn & Yahr stage/
    Most affected side(PD only,患侧)/LEDD/UPDRS_III Total + 分项。
    Gate：33 人（18 PD/15 HC）；除患侧（HC 无）外零缺失。

label-blind：临床表产出独立文件，绝不 join 进事件表。

用法：
    python src/data/parse_typd.py --raw data/raw/typd/extracted --out data/interim/typd_events.parquet \
        --clinical-out data/interim/typd_clinical.csv
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

DATA_SUBDIR = "i-PROGNOSIS_DS2.5_Sub1_KeystrokeTimingPressureData"


def parse_trial_file(path: Path) -> pd.DataFrame:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue  # 官方首行空行
            parts = line.split(",")
            if len(parts) != 4 or parts[0] != "Press":
                rows.append({"_malformed": line})
                continue
            press_s, rel_field, pressure_s = parts[1], parts[2], parts[3]
            if not rel_field.startswith("Release"):
                rows.append({"_malformed": line})
                continue
            rows.append(
                {
                    "press_ms": float(press_s),
                    "release_ms": float(rel_field.replace("Release", "", 1).strip()),
                    "pressure": float(pressure_s),
                    "_malformed": None,
                }
            )
    df = pd.DataFrame(rows)
    if "_malformed" not in df.columns:
        df["_malformed"] = None
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw/typd/extracted")
    ap.add_argument("--out", default="data/interim/typd_events.parquet")
    ap.add_argument("--clinical-out", default="data/interim/typd_clinical.csv")
    ap.add_argument("--report", default="data/interim/parse_reports/parse_typd_report.json")
    args = ap.parse_args()

    base = Path(args.raw) / DATA_SUBDIR
    data_dir = base / "Data"
    subject_dirs = sorted(data_dir.glob("S*"))

    frames, qc_trials = [], []
    for sdir in subject_dirs:
        subject = sdir.name  # S01..
        for trial in sorted(sdir.glob(f"{subject}_TEX*.txt")):
            df = parse_trial_file(trial)
            n_malformed = int(df["_malformed"].notna().sum()) if "_malformed" in df else 0
            good = df[df["_malformed"].isna()].copy() if "_malformed" in df else df.copy()
            good = good.drop(columns=["_malformed"])
            good.insert(0, "dataset", "typd")
            good.insert(1, "subject", subject)
            good.insert(2, "session", trial.stem)  # S##_TEX##
            good["hold_ms"] = good["release_ms"] - good["press_ms"]
            good["keep_flag"] = np.isfinite(good["press_ms"]) & np.isfinite(good["release_ms"]) & (good["hold_ms"] >= 0)
            frames.append(good)
            qc_trials.append(
                {"subject": subject, "trial": trial.stem, "n_raw": len(df), "n_malformed": n_malformed}
            )

    out = pd.concat(frames, ignore_index=True)
    # digraph 三信号派生（冻结协议 §2 L1 四库全部；trial 内派生，不跨 trial）——共享规范实现
    out = add_digraph_timing(out, "press_ms", "release_ms",
                             group_cols=["subject", "session"], hold_col=None)
    for c in ("dataset", "subject", "session"):
        out[c] = out[c].astype("category")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.out, index=False)

    # ---- Excel 临床表 ----
    clinical = pd.read_excel(base / "Demographics_Clinical_Characteristics.xlsx", sheet_name=0, dtype={"Subject ID": str})
    clinical["Subject ID"] = clinical["Subject ID"].str.strip()
    clinical["subject"] = "S" + clinical["Subject ID"].str.zfill(2)
    clinical = clinical.drop(columns=["Subject ID"])
    Path(args.clinical_out).parent.mkdir(parents=True, exist_ok=True)
    clinical.to_csv(args.clinical_out, index=False)

    trial_counts = out.groupby("subject", observed=True)["session"].nunique()
    group_counts = clinical["Group"].value_counts(dropna=False).to_dict()
    # 缺失审计：除患侧（Most affected side，HC 应缺）外零缺失
    miss = clinical.isna().sum()
    miss_except_side = miss.drop(labels=["Most affected side (PD patients only)"])
    report = {
        "n_subjects_dirs": len(subject_dirs),
        "n_subjects_events": int(trial_counts.size),
        "n_events": len(out),
        "n_malformed_lines": int(sum(q["n_malformed"] for q in qc_trials)),
        "trials_per_subject_min": int(trial_counts.min()),
        "trials_per_subject_max": int(trial_counts.max()),
        "trial_counts": {str(k): int(v) for k, v in trial_counts.sort_index().items()},
        "group_counts": {str(k): int(v) for k, v in group_counts.items()},
        "clinical_rows": len(clinical),
        "clinical_missing_except_side": {str(k): int(v) for k, v in miss_except_side.items() if v > 0},
        "events_subjects_vs_clinical_subjects_diff": sorted(
            set(out["subject"].astype(str)) ^ set(clinical["subject"])
        ),
    }
    rep = Path(args.report)
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        f"[parse_typd] subjects={report['n_subjects_events']} events={report['n_events']} "
        f"malformed={report['n_malformed_lines']} trials/person={report['trials_per_subject_min']}"
        f"-{report['trials_per_subject_max']}"
    )
    print(f"[parse_typd] clinical rows={report['clinical_rows']} group={report['group_counts']} "
          f"missing_except_side={report['clinical_missing_except_side']}")


if __name__ == "__main__":
    main()
