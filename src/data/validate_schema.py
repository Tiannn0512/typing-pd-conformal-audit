#!/usr/bin/env python
"""validate_schema.py — 四库统一长表 schema 校验器（TODO-1.4）

断言四库 interim Parquet 的列集/类型/不变量，并实测确认 TyPD 事件 schema
无手别/字符字段（L1 上限结论的机器验证依据，结论落 configs/feature_tiers.yaml）。

不变量（全库通用）：
    I1 dataset/subject/session/keep_flag 列存在且 subject/session/keep_flag 无空值
    I2 keep_flag 为布尔类型
    I3 行数 > 0（静默空表守卫）
    I4 hold_ms 为数值类型；keep_flag=True 行中 hold_ms 全部有限
库特有列（存在性断言）：
    mit  : char/char_from/char_to/press_ms/release_ms/latency_ms/flight_ms/rep/exp
    tappy: hand_from/hand_to/direction/subject_mismatch/field_valid
    typd : press_ms/release_ms/pressure —— 且断言【无】手别列（hand_*）与字符列（char_*/key）
    oe   : key/char_from/char_to/keydown/keyup/latency_ms/flight_ms/solitary
QC 计数（报告不判失败，清洗决策在 Phase 2）：keep 行 hold_ms≤0、keep 行 latency/flight≤0 计数。

用法：
    python src/data/validate_schema.py --all
    python src/data/validate_schema.py --parquet data/interim/mit_digraph.parquet
"""
from __future__ import annotations

import argparse
import json

import numpy as np
from pathlib import Path

import pandas as pd

EXPECTED_COLUMNS: dict[str, list[str]] = {
    "mit": ["dataset", "subject", "session", "char", "char_from", "char_to",
            "press_ms", "release_ms", "hold_ms", "latency_ms", "flight_ms", "rep", "exp",
            "keep_flag"],
    "tappy": ["dataset", "subject", "session", "hand_from", "hand_to", "direction",
              "hold_ms", "latency_ms", "flight_ms", "keep_flag",
              "subject_mismatch", "field_valid"],
    "typd": ["dataset", "subject", "session", "press_ms", "release_ms", "hold_ms",
             "latency_ms", "flight_ms", "pressure", "keep_flag"],
    "oe": ["dataset", "subject", "session", "key", "char_from", "char_to",
           "keydown", "keyup", "hold_ms", "latency_ms", "flight_ms",
           "keep_flag", "solitary"],
}
FORBIDDEN_TYPD_PATTERNS = ("hand", "char", "key")  # L1 上限实测依据
DEFAULT_FILES = {
    "mit": "data/interim/mit_digraph.parquet",
    "tappy": "data/interim/tappy_events.parquet",
    "typd": "data/interim/typd_events.parquet",
    "oe": "data/interim/oe_events.parquet",
}


def validate_table(parquet_path: Path) -> dict:
    errors: list[str] = []
    qc: dict = {}
    if not parquet_path.exists():
        return {"dataset": parquet_path.stem, "file": str(parquet_path), "ok": False,
                "errors": [f"文件不存在: {parquet_path}"]}
    df = pd.read_parquet(parquet_path)
    # I3 静默空表守卫（在 dataset 推断之前，空表无法推断 dataset）
    if len(df) == 0:
        return {"dataset": "unknown", "file": str(parquet_path), "ok": False,
                "errors": ["空表（0 行）——静默零守卫触发"], "n_rows": 0}
    dataset = str(df["dataset"].iloc[0])
    expected = EXPECTED_COLUMNS.get(dataset)
    if expected is None:
        return {"dataset": dataset, "file": str(parquet_path), "ok": False,
                "errors": [f"未知 dataset 值: {dataset}"]}

    # I0 列集精确匹配（缺失或多余都报）
    missing = [c for c in expected if c not in df.columns]
    extra = [c for c in df.columns if c not in expected]
    if missing:
        errors.append(f"缺列: {missing}")
    if extra:
        errors.append(f"多列: {extra}")
    # I1 非空不变量
    for c in ("subject", "session", "keep_flag"):
        if c in df.columns and df[c].isna().any():
            errors.append(f"{c} 列含空值 {int(df[c].isna().sum())} 个")
    # I2 keep_flag 布尔
    if "keep_flag" in df.columns and not pd.api.types.is_bool_dtype(df["keep_flag"]):
        errors.append(f"keep_flag 非布尔: {df['keep_flag'].dtype}")
    # I4 hold_ms 数值且 keep 行有限（np.isfinite 同时挡 NaN/±inf；仅在列齐全时检查，缺列已由 I0 报告）
    if "hold_ms" in df.columns and "keep_flag" in df.columns:
        if not pd.api.types.is_numeric_dtype(df["hold_ms"]):
            errors.append(f"hold_ms 非数值: {df['hold_ms'].dtype}")
        elif pd.api.types.is_bool_dtype(df["keep_flag"]):
            bad = df["keep_flag"] & ~np.isfinite(df["hold_ms"].to_numpy())
            n_nonfinite_keep = int(bad.sum())
            if n_nonfinite_keep:
                errors.append(f"keep_flag=True 行中 hold_ms 非有限 {n_nonfinite_keep} 个")
    # TyPD 档位上限实测：断言无手别/字符列
    if dataset == "typd":
        forbidden = [c for c in df.columns
                     if any(p in c.lower() for p in FORBIDDEN_TYPD_PATTERNS)]
        if forbidden:
            errors.append(f"TyPD 出现手别/字符类列（违反 L1 上限预期）: {forbidden}")
    # QC 计数（不判失败；Phase 2 清洗决策输入）。keep_flag 可能被恶意/误写为非布尔，统一转 bool
    keep_mask = df["keep_flag"].astype(bool) if "keep_flag" in df.columns else pd.Series(True, index=df.index)
    keep = df[keep_mask]
    for col in ("hold_ms", "latency_ms", "flight_ms"):
        if col in keep.columns:
            qc[f"keep_rows_{col}_le0"] = int((keep[col] <= 0).sum())
    qc["keep_rows"] = int(len(keep))

    return {"dataset": dataset, "file": str(parquet_path), "ok": not errors,
            "n_rows": int(len(df)), "n_columns": int(df.shape[1]),
            "errors": errors, "qc": qc}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--parquet", default=None)
    ap.add_argument("--report", default="data/interim/parse_reports/schema_validation.json")
    args = ap.parse_args()

    if args.all:
        targets = {k: Path(v) for k, v in DEFAULT_FILES.items()}
    elif args.parquet:
        targets = {Path(args.parquet).stem: Path(args.parquet)}
    else:
        ap.error("需要 --all 或 --parquet")

    results = {name: validate_table(p) for name, p in targets.items()}
    all_ok = all(r["ok"] for r in results.values())
    report = {"all_ok": all_ok, "tables": results}
    rep = Path(args.report)
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps(report, indent=2), encoding="utf-8")

    for name, r in results.items():
        status = "OK" if r["ok"] else "FAIL"
        extra = "" if r["ok"] else f" errors={r['errors']}"
        print(f"[schema] {name:6s} {status} rows={r.get('n_rows', '?')}{extra}")
    if "typd" in results:
        print("[schema] TyPD L1 上限实测：无手别/字符字段 →" + (" 断言通过" if results["typd"]["ok"] else " 断言失败"))
    if not all_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
