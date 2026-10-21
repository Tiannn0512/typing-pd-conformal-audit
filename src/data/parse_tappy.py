from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNS = ["subject", "date", "time", "hand", "hold", "direction", "latency", "flight", "_trailing"]
TIMING_COLS = ["hold", "latency", "flight"]
VALID_DIRECTIONS = {"LL", "LR", "LS", "RL", "RR", "RS", "SL", "SR", "SS"}
VALID_HANDS = {"L", "R", "S"}

def parse_month_file(path: Path) -> tuple[pd.DataFrame, dict]:
    stem = path.stem
    file_subject = stem.split("_")[0]
    df = pd.read_csv(
        path,
        sep="\t",
        header=None,
        names=COLUMNS,
        dtype={"subject": str, "hand": str, "direction": str, "hold": str, "latency": str, "flight": str},
        engine="c",
        quoting=3,
        na_filter=False,
    )
    if not (df["_trailing"].fillna("") == "").all():
        raise ValueError(f"{path.name}: trailing column non-empty; schema mismatch")
    n_raw = len(df)

    subject_mismatch = df["subject"].str.strip() != file_subject

    direction = df["direction"].str.strip()
    hand = df["hand"].str.strip()
    field_valid = direction.isin(VALID_DIRECTIONS) & hand.isin(VALID_HANDS)

    out = pd.DataFrame(
        {
            "dataset": "tappy",
            "subject": file_subject,
            "session": stem,
            "hand_from": hand,
            "hand_to": direction.str[1].where(direction.isin(VALID_DIRECTIONS)),
            "direction": direction,
        }
    )
    keep = pd.Series(True, index=df.index)
    keep &= ~subject_mismatch
    keep &= field_valid
    for c in TIMING_COLS:
        v = pd.to_numeric(df[c].str.strip(), errors="coerce")
        out[f"{c}_ms"] = v.astype("float32")
        keep &= v.notna() & np.isfinite(v)
    out["keep_flag"] = keep
    out["subject_mismatch"] = subject_mismatch
    out["field_valid"] = field_valid
    n_flagged_file = int((~keep).sum())

    qc = {
        "file": path.name,
        "n_raw": n_raw,
        "n_flagged": n_flagged_file,
        "n_subject_mismatch": int(subject_mismatch.sum()),
        "n_field_invalid": int((~field_valid).sum()),
        "subject_mismatch_samples": sorted(set(df.loc[subject_mismatch, "subject"]))[:5],
    }
    return out, qc

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw/tappy")
    ap.add_argument("--labels", default="data/raw/tappy/Archived-users-extracted",
                    help="use the ID set for reconciliation only; label content is not read")
    ap.add_argument("--out", default="data/interim/tappy_events.parquet")
    args = ap.parse_args()

    data_dir = Path(args.raw) / "Tappy Data"
    files = sorted(data_dir.glob("*.txt"))
    if not files:
        raise FileNotFoundError(f"{data_dir}: no monthly files")

    frames, qcs = [], []
    for p in files:
        df, qc = parse_month_file(p)
        frames.append(df)
        qcs.append(qc)

    out = pd.concat(frames, ignore_index=True)
    for c in ("dataset", "subject", "session", "hand_from", "hand_to", "direction"):
        out[c] = out[c].astype("category")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.out, index=False)

    label_ids = {p.stem.replace("User_", "") for p in Path(args.labels).glob("User_*.txt")}
    event_ids = set(out["subject"].astype(str).unique())
    per_user = out.groupby("subject", observed=True).size()
    report = {
        "n_files": len(files),
        "n_rows": len(out),
        "n_rows_flagged": int((~out["keep_flag"]).sum()),
        "n_flagged_subject_mismatch": int(out["subject_mismatch"].sum()),
        "n_flagged_field_invalid": int((~out["field_valid"]).sum()),
        "n_users_in_events": len(event_ids),
        "n_users_in_labels": len(label_ids),
        "n_users_both": len(event_ids & label_ids),
        "n_users_labeled_without_events": len(label_ids - event_ids),
        "n_users_events_without_labels": len(event_ids - label_ids),
        "rows_per_user_min": int(per_user.min()),
        "rows_per_user_median": float(per_user.median()),
        "rows_per_user_max": int(per_user.max()),
        "files_with_flagged_rows": int(sum(1 for q in qcs if q["n_flagged"] > 0)),
        "direction_counts_top": {str(k): int(v) for k, v in out["direction"].value_counts().head(12).items()},
        "hand_from_counts": {str(k): int(v) for k, v in out["hand_from"].value_counts().items()},
    }
    print(
        f"[parse_tappy] files={report['n_files']} rows={report['n_rows']} "
        f"flagged={report['n_rows_flagged']} (subj_mismatch={report['n_flagged_subject_mismatch']}, "
        f"field_invalid={report['n_flagged_field_invalid']})"
    )
    print(
        f"[parse_tappy] users: events={report['n_users_in_events']} labels={report['n_users_in_labels']} "
        f"both={report['n_users_both']} labeled_no_events={report['n_users_labeled_without_events']} "
        f"events_no_labels={report['n_users_events_without_labels']}"
    )
    print(f"[parse_tappy] directions(top)={report['direction_counts_top']}")

if __name__ == "__main__":
    main()
