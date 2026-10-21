from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from data.digraph_derive import add_digraph_timing

USECOLS = ["key", "response_id", "participant_id", "sentence_id", "diagnosis", "keydown", "keyup"]

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw/oe/CoNLL_2020_Online_English.csv")
    ap.add_argument("--out", default="data/interim/oe_events.parquet")
    ap.add_argument("--subjects-out", default="data/interim/oe_subjects.csv")
    ap.add_argument("--chunksize", type=int, default=1_000_000)
    args = ap.parse_args()

    chunks = []
    n_rows_raw = 0
    for chunk in pd.read_csv(args.raw, usecols=USECOLS, chunksize=args.chunksize):
        n_rows_raw += len(chunk)
        chunks.append(chunk)
    df = pd.concat(chunks, ignore_index=True)
    del chunks

    df["solitary"] = df["keydown"].isna() | df["keyup"].isna()

    df["hold_ms"] = (df["keyup"] - df["keydown"]).astype("float32")

    df = add_digraph_timing(df, "keydown", "keyup",
                            group_cols=["participant_id", "response_id"], hold_col=None)
    g = df.groupby(["participant_id", "response_id"], sort=False)
    df["char_from"] = g["key"].shift(1)
    df["char_to"] = df["key"]

    df["keep_flag"] = ~df["solitary"] & np.isfinite(df["hold_ms"])

    dup_cols = ["participant_id", "key", "keydown", "keyup"]
    dup_mask = df.duplicated(subset=dup_cols, keep=False)
    n_dup_rows_participating = int(dup_mask.sum())
    n_dup_redundant_copies = int(df.duplicated(subset=dup_cols, keep="first").sum())
    df.insert(0, "dataset", "oe")
    df["subject"] = df["participant_id"].astype(str)
    df["session"] = df["participant_id"].astype(str) + "_" + df["response_id"].astype(str)

    keep_cols = [
        "dataset", "subject", "session", "key", "char_from", "char_to",
        "keydown", "keyup", "hold_ms", "latency_ms", "flight_ms",
        "keep_flag", "solitary",
    ]
    out = df[keep_cols].copy()
    for c in ("dataset", "subject", "session", "key", "char_from", "char_to"):
        out[c] = out[c].astype("category")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.out, index=False)

    subjects = (
        df.drop_duplicates("subject")[["subject", "diagnosis"]]
        .reset_index(drop=True)
    )
    subjects["n_events"] = subjects["subject"].map(out["subject"].value_counts())
    subjects_path = Path(args.subjects_out)
    subjects.to_csv(subjects_path, index=False)

    per_subject_diag = subjects["diagnosis"].value_counts().to_dict()
    report = {
        "n_rows_raw": n_rows_raw,
        "n_duplicate_rows_participating": n_dup_rows_participating,
        "n_duplicate_redundant_copies": n_dup_redundant_copies,
        "n_rows_out": len(out),
        "n_solitary": int(df["solitary"].sum()),
        "n_subjects": int(out["subject"].nunique()),
        "diagnosis_counts_subjects": {str(k): int(v) for k, v in per_subject_diag.items()},
        "n_sessions": int(out["session"].nunique()),
        "diagnosis_unique_values": sorted(df["diagnosis"].dropna().unique().tolist()),
        "subjects_table": str(subjects_path),
    }
    print(
        f"[parse_oe] rows={n_rows_raw} solitary={report['n_solitary']} "
        f"subjects={report['n_subjects']} diag(1=PD,0=HC)={report['diagnosis_counts_subjects']}"
    )

if __name__ == "__main__":
    main()
