from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PROCESSED = Path("data/processed")
INTERIM = Path("data/interim")
EVENTS = {"mit": "final_digraphs.parquet", "oe": "final_digraphs.parquet"}

def load_mapping() -> tuple[dict[str, str], set[str], dict[str, str], dict[str, str]]:
    cfg = yaml.safe_load((Path(__file__).resolve().parents[2] / "configs" / "key_hand_mapping.yml").read_text(encoding="utf-8"))
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
    k = str(k).strip().lower()
    if not k:
        return "NA"
    if k in unassigned or any(k == p or k.startswith(p) for p in ("shift", "control", "alt", "mouse")):
        return "UNASSIGNED"
    if aliases:
        k = aliases.get(k, k)
    if k in hand:
        return hand[k]
    if k in shifted and shifted[k] in hand:
        return hand[shifted[k]]
    return "NA"

def build_dataset(ds: str, hand, unassigned, shifted, aliases) -> tuple[pd.DataFrame, dict]:
    ev = pd.read_parquet(INTERIM / "final_digraphs.parquet")
    ev = ev[ev["dataset"] == ds].copy()
    qc: dict = {"dataset": ds, "n_events_final_pool": len(ev)}

    ev["hand"] = ev["char_to"].map(lambda k: key_to_hand(k, hand, unassigned, shifted, aliases))
    qc["excluded_unassigned"] = int((ev["hand"] == "UNASSIGNED").sum())
    qc["excluded_unmatched"] = int((ev["hand"] == "NA").sum())
    ev_lr = ev[ev["hand"].isin(["L", "R"])]

    out = pd.DataFrame({"subject_id": ev["subject"].astype(str).map(lambda s: f"{ds}_{s}"),
                        "subject": ev["subject"].astype(str)}).drop_duplicates("subject_id")

    g = ev_lr.groupby([ev_lr["subject"].astype(str), "hand"], observed=True)[
        ["hold_ms", "latency_ms", "flight_ms"]].mean()
    for sig, col in (("hold", "hold_ms"), ("latency", "latency_ms"), ("flight", "flight_ms")):
        for h in ("L", "R"):
            out[f"L2_{ds}_{sig}_{h}_mean"] = out["subject"].map(g[col].unstack("hand").get(h))

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
        print(f"[build_features] {ds}: {len(f)} subjects; excluded unassigned={qc['excluded_unassigned']} "
              f"unmatched={qc['excluded_unmatched']} (events) / {qc['excluded_unmatched_digraphs']} (digraph pairs)")
    out = pd.concat(frames, ignore_index=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    out.to_csv(PROCESSED / "subjects_l2l3.csv", index=False)
    print(f"[build_features] subjects_l2l3.csv: {len(out)} rows x {out.shape[1]} cols")

if __name__ == "__main__":
    main()
