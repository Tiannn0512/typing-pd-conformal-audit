from __future__ import annotations

import argparse
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
                continue
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
    args = ap.parse_args()

    base = Path(args.raw) / DATA_SUBDIR
    data_dir = base / "Data"
    subject_dirs = sorted(data_dir.glob("S*"))

    frames, qc_trials = [], []
    for sdir in subject_dirs:
        subject = sdir.name
        for trial in sorted(sdir.glob(f"{subject}_TEX*.txt")):
            df = parse_trial_file(trial)
            n_malformed = int(df["_malformed"].notna().sum()) if "_malformed" in df else 0
            good = df[df["_malformed"].isna()].copy() if "_malformed" in df else df.copy()
            good = good.drop(columns=["_malformed"])
            good.insert(0, "dataset", "typd")
            good.insert(1, "subject", subject)
            good.insert(2, "session", trial.stem)
            good["hold_ms"] = good["release_ms"] - good["press_ms"]
            good["keep_flag"] = np.isfinite(good["press_ms"]) & np.isfinite(good["release_ms"]) & (good["hold_ms"] >= 0)
            frames.append(good)
            qc_trials.append(
                {"subject": subject, "trial": trial.stem, "n_raw": len(df), "n_malformed": n_malformed}
            )

    out = pd.concat(frames, ignore_index=True)
    out = add_digraph_timing(out, "press_ms", "release_ms",
                             group_cols=["subject", "session"], hold_col=None)
    for c in ("dataset", "subject", "session"):
        out[c] = out[c].astype("category")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.out, index=False)

    clinical = pd.read_excel(base / "Demographics_Clinical_Characteristics.xlsx", sheet_name=0, dtype={"Subject ID": str})
    clinical["Subject ID"] = clinical["Subject ID"].str.strip()
    clinical["subject"] = "S" + clinical["Subject ID"].str.zfill(2)
    clinical = clinical.drop(columns=["Subject ID"])
    Path(args.clinical_out).parent.mkdir(parents=True, exist_ok=True)
    clinical.to_csv(args.clinical_out, index=False)

    trial_counts = out.groupby("subject", observed=True)["session"].nunique()
    group_counts = clinical["Group"].value_counts(dropna=False).to_dict()
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
    print(
        f"[parse_typd] subjects={report['n_subjects_events']} events={report['n_events']} "
        f"malformed={report['n_malformed_lines']} trials/person={report['trials_per_subject_min']}"
        f"-{report['trials_per_subject_max']}"
    )
    print(f"[parse_typd] clinical rows={report['clinical_rows']} group={report['group_counts']} "
          f"missing_except_side={report['clinical_missing_except_side']}")

if __name__ == "__main__":
    main()
