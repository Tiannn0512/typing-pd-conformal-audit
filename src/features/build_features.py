#!/usr/bin/env python
"""build_features.py — L2/L3 手别条件特征构建器（TODO-4.1 前置，FEATURE-DEF-1）

依据：configs/key_hand_mapping.yaml v1.0.1（已冻结）+ configs/feature_tiers.yaml
FEATURE-DEF-1（结果产出前登记的列定义）。

产出：data/processed/subjects_l2l3.csv —— subject_id 主键的增量特征表，仅含
mit/oe 行（Tappy 的原生 L2 已在 subjects.csv 的 L2tappy_* 列；TyPD L1 上限）。
列命名：L2_{ds}_{sig}_{hand}_mean（6/库）+ L3_{ds}_{sig}_{trans}_mean ×4 + L3_{ds}_frac_cross（5/库）。
QC 计数（unassigned/unmatched 剔除量）写 data/interim/parse_reports/build_features_report.json。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PROCESSED = Path("data/processed")
INTERIM = Path("data/interim")
# 事件基（FEATURE-DEF-2，2026-09-26 用户批准）：S1-S6 清洗终池（build_tables 导出），
# 与 L1 及 tappy L2（subjects.csv 内置）同事件基——修复复发猎杀 B/MEDIUM-2 的口径缺口
EVENTS = {"mit": "final_digraphs.parquet", "oe": "final_digraphs.parquet"}


def load_mapping() -> tuple[dict[str, str], set[str], dict[str, str], dict[str, str]]:
    cfg = yaml.safe_load((Path(__file__).resolve().parents[2] / "configs" / "key_hand_mapping.yaml").read_text(encoding="utf-8"))
    assert cfg["version"] == "1.0.1", "映射表版本与冻结版不符"
    hand: dict[str, str] = {}
    for h, fingers in cfg["hand_zones"].items():
        for _finger, keys in fingers.items():
            for k in keys:
                hand[k.lower()] = h
    unassigned = {u.lower() for u in cfg["unassigned"]}
    shifted = {k.lower(): v.lower() for k, v in cfg["shifted_base_map"].items()}
    aliases = {k.lower(): v.lower() for k, v in cfg["aliases"].items()}
    return hand, unassigned, shifted, aliases


def key_to_hand(k: str, hand: dict[str, str], unassigned: set[str], shifted: dict[str, str],
               aliases: dict[str, str] | None = None) -> str:
    """匹配优先级：unassigned 精确/shift 前缀 > aliases 归一化 > shifted 基准键 > zones 精确 > NA。"""
    k = str(k).strip().lower()
    if not k:
        return "NA"
    if k in unassigned or any(k == p or k.startswith(p) for p in ("shift", "control", "alt", "mouse")):
        return "UNASSIGNED"
    if aliases:
        k = aliases.get(k, k)  # v1.0.1：X11 keysym 归一化
    if k in hand:
        return hand[k]
    if k in shifted and shifted[k] in hand:
        return hand[shifted[k]]
    return "NA"


def build_dataset(ds: str, hand, unassigned, shifted, aliases) -> tuple[pd.DataFrame, dict]:
    ev = pd.read_parquet(INTERIM / "final_digraphs.parquet")
    ev = ev[ev["dataset"] == ds].copy()
    qc: dict = {"dataset": ds, "n_events_final_pool": len(ev)}

    # hand 归属（按落键 char_to）；L2 只用 L/R（unassigned/unmatched 剔除并计数）
    ev["hand"] = ev["char_to"].map(lambda k: key_to_hand(k, hand, unassigned, shifted, aliases))
    qc["excluded_unassigned"] = int((ev["hand"] == "UNASSIGNED").sum())
    qc["excluded_unmatched"] = int((ev["hand"] == "NA").sum())
    ev_lr = ev[ev["hand"].isin(["L", "R"])]

    out = pd.DataFrame({"subject_id": ev["subject"].astype(str).map(lambda s: f"{ds}_{s}"),
                        "subject": ev["subject"].astype(str)}).drop_duplicates("subject_id")

    # L2：hand ∈ {L,R} × 三信号 mean（6 列）
    g = ev_lr.groupby([ev_lr["subject"].astype(str), "hand"], observed=True)[
        ["hold_ms", "latency_ms", "flight_ms"]].mean()
    for sig, col in (("hold", "hold_ms"), ("latency", "latency_ms"), ("flight", "flight_ms")):
        for h in ("L", "R"):
            out[f"L2_{ds}_{sig}_{h}_mean"] = out["subject"].map(g[col].unstack("hand").get(h))

    # L3：digraph 手别转移——char_from 与 char_to 双方可映射（FEATURE-DEF-1 登记定义；
    # 修复复发猎杀 B/HIGH-1：此前只查 char_from，char_to=空格/退格的二连对被误判 cross）
    ev2 = ev[ev["char_from"].notna()].copy()
    ev2["hand_from_map"] = ev2["char_from"].map(lambda k: key_to_hand(k, hand, unassigned, shifted, aliases))
    both = ev2[ev2["hand_from_map"].isin(["L", "R"]) & ev2["hand"].isin(["L", "R"])].copy()
    qc["n_digraphs_both_mapped"] = int(len(both))
    qc["excluded_unmatched_digraphs"] = int(len(ev2) - len(both))
    both["trans"] = np.where(both["hand_from_map"] == both["hand"], "same", "cross")
    g2 = both.groupby([both["subject"].astype(str), "trans"], observed=True)[
        ["latency_ms", "flight_ms"]].mean()
    for sig in ("latency", "flight"):
        for tr in ("same", "cross"):
            out[f"L3_{ds}_{sig}_{tr}_mean"] = out["subject"].map(g2[sig + "_ms"].unstack("trans").get(tr))
    tot = both.groupby(both["subject"].astype(str)).size()
    cross = both[both["trans"] == "cross"].groupby(both.loc[both["trans"] == "cross", "subject"].astype(str)).size()
    out[f"L3_{ds}_frac_cross"] = out["subject"].map((cross / tot).fillna(0.0))
    return out, qc


def main() -> None:
    hand, unassigned, shifted, aliases = load_mapping()
    frames, qcs = [], []
    for ds in ("mit", "oe"):
        f, qc = build_dataset(ds, hand, unassigned, shifted, aliases)
        frames.append(f)
        qcs.append(qc)
        print(f"[build_features] {ds}: {len(f)} 人；剔除 unassigned={qc['excluded_unassigned']} "
              f"unmatched={qc['excluded_unmatched']}（事件）/{qc['excluded_unmatched_digraphs']}（二连对）")
    out = pd.concat(frames, ignore_index=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    out.to_csv(PROCESSED / "subjects_l2l3.csv", index=False)
    REPORTS = INTERIM / "parse_reports"
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "build_features_report.json").write_text(json.dumps(qcs, indent=2), encoding="utf-8")
    print(f"[build_features] subjects_l2l3.csv: {len(out)} 行 × {out.shape[1]} 列")


if __name__ == "__main__":
    main()
