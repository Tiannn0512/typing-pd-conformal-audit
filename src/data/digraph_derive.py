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
