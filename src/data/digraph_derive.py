"""digraph_derive.py — 二连键三信号派生的唯一权威实现（TODO-3.1 审核必修2 提取）

规范派生（全项目统一口径，原散布于 parse_mit/parse_typd/parse_oe 的同式代码收敛于此）：
    hold_ms    = release − press
    latency_ms = press[i] − release[i−1]   （组内；组首行 NaN）
    flight_ms  = press[i] − press[i−1]     （组内；组首行 NaN）
MIT 的 hold 例外：官方 f1 列即为 hold（sanityCheck 已验证 f2−f3=f1），hold_col 传 None 时
不覆盖既有 hold 列。组内排序用 mergesort（稳定），组首行 digraph 列为 NaN 属预期。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def add_digraph_timing(
    df: pd.DataFrame,
    press_col: str,
    release_col: str,
    group_cols: list[str] | tuple[str, ...] | None,
    hold_col: str | None = "hold_ms",
) -> pd.DataFrame:
    """向 df 原位追加 latency_ms/flight_ms（及 hold_ms，若 hold_col 给定）。

    group_cols=None 时全表平铺派生（MIT 单 session 场景）；否则组内排序后派生
    （typd: [subject, session]；oe: [participant_id, response_id]）。
    返回重排索引后的 df（组内按 press 升序，mergesort 稳定）。
    """
    if group_cols:
        df = df.sort_values([*group_cols, press_col], kind="mergesort").reset_index(drop=True)
        g = df.groupby(list(group_cols), sort=False)
        latency_base = g[release_col].shift(1)
        flight_base = g[press_col].shift(1)
        if hold_col:
            df[hold_col] = df[release_col] - df[press_col]
    else:
        latency_base = df[release_col].shift(1)
        flight_base = df[press_col].shift(1)
        if hold_col:
            df[hold_col] = df[release_col] - df[press_col]
    df["latency_ms"] = (df[press_col] - latency_base).astype("float32")
    df["flight_ms"] = (df[press_col] - flight_base).astype("float32")
    return df
