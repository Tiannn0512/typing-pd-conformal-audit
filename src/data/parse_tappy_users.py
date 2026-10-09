#!/usr/bin/env python
"""parse_tappy_users.py — Tappy 用户标签表解析器（TODO-1.1）

227 个键值对 txt（Archived-users-extracted/User_XXXXXXXXXX.txt）→ 单一标签表。
字段名保留官方拼写（含 "Levadopa" 官方笔误，冻结名称纪律）；缺失值官方记号为 " ------" → NA。
label-blind 纪律：本脚本只产出独立标签表文件，绝不 join 进事件表；join 只发生在
Phase 2 队列定义（清洗 label-blind，标签仅用于 PD/HC 分组与排除规则）。

用法：
    python src/data/parse_tappy_users.py --labels data/raw/tappy/Archived-users-extracted \
        --out data/interim/tappy_users.csv
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

FIELDS = [
    "BirthYear", "Gender", "Parkinsons", "Tremors", "DiagnosisYear", "Sided",
    "UPDRS", "Impact", "Levadopa", "DA", "MAOB", "Other",
]
BOOL_FIELDS = {"Parkinsons", "Tremors", "Levadopa", "DA", "MAOB", "Other"}
MISSING = "------"


def parse_user_file(path: Path) -> dict:
    row = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip()
        if k not in FIELDS:
            raise ValueError(f"{path.name}: 未知字段 {k!r}")
        row[k] = v
    missing_fields = [f for f in FIELDS if f not in row]
    if missing_fields:
        raise ValueError(f"{path.name}: 缺字段 {missing_fields}")
    out = {"subject": path.stem.replace("User_", "")}
    for f in FIELDS:
        v = row[f]
        if MISSING in v:
            out[f] = pd.NA
        elif f in BOOL_FIELDS:
            if v not in ("True", "False"):
                raise ValueError(f"{path.name}: {f} 非布尔值 {v!r}")
            out[f] = (v == "True")
        else:
            out[f] = v
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default="data/raw/tappy/Archived-users-extracted")
    ap.add_argument("--out", default="data/interim/tappy_users.csv")
    ap.add_argument("--report", default="data/interim/parse_reports/parse_tappy_users_report.json")
    args = ap.parse_args()

    files = sorted(Path(args.labels).glob("User_*.txt"))
    rows = [parse_user_file(p) for p in files]
    df = pd.DataFrame(rows)
    for b in BOOL_FIELDS:
        df[b] = df[b].astype("boolean")
    for c in ("BirthYear", "DiagnosisYear"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)

    ct = pd.crosstab(df["Parkinsons"], df["Tremors"], dropna=False)
    report = {
        "n_users": len(df),
        "n_pd_parkinsons_true": int((df["Parkinsons"] == True).sum()),   # noqa: E712
        "n_hc_both_false": int(((df["Parkinsons"] == False) & (df["Tremors"] == False)).sum()),  # noqa: E712
        "n_tremor_only": int(((df["Parkinsons"] == False) & (df["Tremors"] == True)).sum()),  # noqa: E712
        "crosstab_parkinsons_tremors": {str(k): {str(kk): int(vv) for kk, vv in v.items()}
                                        for k, v in ct.to_dict(orient="index").items()},
        "missing_counts": {c: int(df[c].isna().sum()) for c in df.columns},
    }
    rep = Path(args.report)
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        f"[parse_tappy_users] users={report['n_users']} "
        f"PD(Parkinsons=True)={report['n_pd_parkinsons_true']} "
        f"HC(both False)={report['n_hc_both_false']} tremor_only={report['n_tremor_only']}"
    )


if __name__ == "__main__":
    main()
