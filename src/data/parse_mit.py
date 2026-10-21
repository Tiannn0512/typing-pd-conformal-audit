from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import numpy as np
import pandas as pd

import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from data.digraph_derive import add_digraph_timing

P_MOUSE = re.compile(r'("mouse.+")')
P_LONG_META = re.compile(r'("Shift.+")|("Alt.+")|("Control.+")')

FILE_RE = re.compile(r"([0-9]+)\.([0-9]+)_([0-9]+)_([0-9]+)\.csv")

def sanity_keep(dataHT: np.ndarray, t_start: np.ndarray, t_end: np.ndarray) -> np.ndarray:
    bad = t_start <= 0
    bad = bad | (t_end <= 0)
    bad = bad | (dataHT < 0)
    bad = bad | (dataHT >= 5)
    non_cons_tmp = np.zeros(len(t_start)) == 0
    non_cons = np.zeros(len(t_start)) > 0
    start_tmp = t_start.copy()
    while np.sum(non_cons_tmp) > 0:
        non_cons_tmp = np.append([False], np.diff(start_tmp) < 0)
        non_cons = non_cons | non_cons_tmp
        idx = np.arange(len(non_cons_tmp))[non_cons_tmp]
        start_tmp[idx] = start_tmp[idx - 1]
    bad = bad | non_cons
    return ~bad

def parse_session_file(path: Path) -> dict:
    data = np.genfromtxt(str(path), dtype=None, delimiter=",", skip_header=0)
    data = np.atleast_1d(data)
    keys = data["f0"].astype(str)
    ht = data["f1"].astype(float)
    t_end = data["f2"].astype(float)
    t_start = data["f3"].astype(float)
    n_raw = len(keys)

    keep = sanity_keep(ht, t_start, t_end)
    n_sanity_removed = int((~keep).sum())

    keys, ht, t_start, t_end = keys[keep], ht[keep], t_start[keep], t_end[keep]

    lbl = np.array([P_MOUSE.match(k) is None for k in keys])
    lbl &= np.array([P_LONG_META.match(k) is None for k in keys])
    n_autofilt_removed = int((~lbl).sum())
    keys, ht, t_start, t_end = keys[lbl], ht[lbl], t_start[lbl], t_end[lbl]

    n = len(keys)
    df = pd.DataFrame(
        {
            "char": [k.strip('"') for k in keys],
            "press_ms": t_start * 1000.0,
            "release_ms": t_end * 1000.0,
            "hold_ms": ht * 1000.0,
        }
    )
    df = add_digraph_timing(df, "press_ms", "release_ms", group_cols=None, hold_col=None)
    df["char_from"] = df["char"].shift(1)
    df["char_to"] = df["char"]
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
            raise ValueError(f"filename does not match the official layout: {p.name}")
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
    print(
        f"[parse_mit] subjects={report['n_subjects']} (PD={n_pd}/HC={n_hc}) "
        f"sessions={report['n_sessions']} events kept={report['n_events_kept']} "
        f"sanity_removed={report['n_events_sanity_removed']} autofilt_removed={report['n_events_autofilt_removed']}"
    )
    if files_missing_in_gt or files_missing_on_disk:
        print(f"[parse_mit][WARN] file-set mismatch: gt_only={files_missing_on_disk} disk_only={files_missing_in_gt}")

if __name__ == "__main__":
    main()
