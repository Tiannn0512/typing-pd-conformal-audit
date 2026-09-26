"""test_schema.py — schema 校验器单元测试（TODO-1.4）

合成小样测试：校验器对合规表放行、对各类违规（缺列/空值/空表/类型错/TyPD 手别列）拦截。
全部用内存合成数据，不触碰真实数据文件。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "data"))
from validate_schema import validate_table  # noqa: E402


def _mini_row(dataset: str) -> dict:
    base = {"dataset": dataset, "subject": "S01", "session": "S01_T01", "keep_flag": True}
    if dataset == "mit":
        base.update({"char": "a", "char_from": None, "char_to": "a", "press_ms": 100.0,
                     "release_ms": 150.0, "hold_ms": 50.0, "latency_ms": np.nan,
                     "flight_ms": np.nan, "rep": 1, "exp": 14})
    elif dataset == "tappy":
        base.update({"hand_from": "L", "hand_to": "L", "direction": "LL", "hold_ms": 50.0,
                     "latency_ms": 30.0, "flight_ms": 80.0,
                     "subject_mismatch": False, "field_valid": True})
    elif dataset == "typd":
        base.update({"press_ms": 100.0, "release_ms": 150.0, "hold_ms": 50.0,
                     "latency_ms": np.nan, "flight_ms": np.nan, "pressure": 0.5})
    elif dataset == "oe":
        base.update({"key": "a", "char_from": None, "char_to": "a", "keydown": 100.0,
                     "keyup": 150.0, "hold_ms": 50.0, "latency_ms": np.nan,
                     "flight_ms": np.nan, "solitary": False})
    return base


def _write(tmp_path: Path, dataset: str, n: int = 3) -> Path:
    df = pd.DataFrame([_mini_row(dataset) for _ in range(n)])
    d = tmp_path / dataset
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{dataset}.parquet"
    df.to_parquet(p, index=False)
    return p


def test_valid_tables_pass(tmp_path):
    for ds in ("mit", "tappy", "typd", "oe"):
        r = validate_table(_write(tmp_path, ds))
        assert r["ok"], f"{ds} 应通过: {r['errors']}"


def test_missing_column_fails(tmp_path):
    p = _write(tmp_path, "mit")
    df = pd.read_parquet(p).drop(columns=["hold_ms"])
    df.to_parquet(p, index=False)
    r = validate_table(p)
    assert not r["ok"] and any("缺列" in e for e in r["errors"])


def test_extra_column_fails(tmp_path):
    p = _write(tmp_path, "typd")
    df = pd.read_parquet(p)
    df["hand_from"] = "L"  # 模拟 TyPD 混入手别列
    df.to_parquet(p, index=False)
    r = validate_table(p)
    assert not r["ok"] and any("多列" in e for e in r["errors"])
    assert any("手别/字符" in e for e in r["errors"])


def test_null_subject_fails(tmp_path):
    p = _write(tmp_path, "oe")
    df = pd.read_parquet(p)
    df.loc[0, "subject"] = None
    df.to_parquet(p, index=False)
    r = validate_table(p)
    assert not r["ok"] and any("subject" in e for e in r["errors"])


def test_empty_table_fails(tmp_path):
    p = tmp_path / "typd.parquet"
    pd.DataFrame([_mini_row("typd")]).iloc[:0].to_parquet(p, index=False)
    r = validate_table(p)
    assert not r["ok"] and any("空表" in e for e in r["errors"])


def test_nonboolean_keep_flag_fails(tmp_path):
    p = _write(tmp_path, "tappy")
    df = pd.read_parquet(p)
    df["keep_flag"] = df["keep_flag"].astype("int8")
    df.to_parquet(p, index=False)
    r = validate_table(p)
    assert not r["ok"] and any("keep_flag 非布尔" in e for e in r["errors"])


def test_nonfinite_hold_in_keep_rows_fails(tmp_path):
    p = _write(tmp_path, "mit")
    df = pd.read_parquet(p)
    df.loc[0, "hold_ms"] = np.nan
    df.to_parquet(p, index=False)
    r = validate_table(p)
    assert not r["ok"] and any("hold_ms 非有限" in e for e in r["errors"])


def test_missing_file_fails(tmp_path):
    r = validate_table(tmp_path / "nope.parquet")
    assert not r["ok"]


def test_feature_tiers_yaml_consistency():
    import yaml
    cfg = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "configs" / "feature_tiers.yaml").read_text(encoding="utf-8")
    )
    # 冻结协议 §2：L1 全部四库；L2 = MIT/Tappy/OE；L3 = MIT/OE；TyPD 上限 L1
    assert cfg["tiers"]["L1"]["features"] == ["hold", "flight", "latency"]
    assert cfg["dataset_max_tier"] == {"mit": 3, "tappy": 2, "typd": 1, "oe": 3}
    # 跨库降档规则 = min(源, 目标)
    assert "min" in cfg["cross_dataset_rule"]
