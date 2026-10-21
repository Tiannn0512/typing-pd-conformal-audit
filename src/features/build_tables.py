from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

HOLD_MAX_MS = 10_000
FLIGHT_MAX_MS = 3_000
MIN_RATE = 20.0
SESSION_MIN_DIGRAPH = 100
PERSON_MIN_DIGRAPH = 300

INTERIM = Path("data/interim")
PROCESSED = Path("data/processed")

EVENTS = {
    "mit": INTERIM / "mit_digraph.parquet",
    "tappy": INTERIM / "tappy_events.parquet",
    "typd": INTERIM / "typd_events.parquet",
    "oe": INTERIM / "oe_events.parquet",
}
PRESS_COL = {"mit": "press_ms", "typd": "press_ms", "oe": "keydown", "tappy": None}

def load_labels() -> dict[str, pd.DataFrame]:
    mit = []
    for cs in ("MIT-CS1PD", "MIT-CS2PD"):
        df = pd.read_csv(INTERIM.parent / "raw" / "mit" / cs / f"GT_DataPD_{cs}.csv")
        assert df["gt"].notna().all(), f"{cs} gt column contains NaN"
        for _, r in df.iterrows():
            gt = r["gt"]
            label_pd = bool(gt) if isinstance(gt, (bool, np.bool_)) else str(gt).strip().lower() == "true"
            mit.append({"subject": str(int(r["pID"])), "label_pd": label_pd,
                        "tremor_only": False, "label_source": "clinical"})
    typd = pd.read_csv(INTERIM / "typd_clinical.csv")
    assert typd["Group"].notna().all(), "typd clinical Group column contains NaN"
    typd = pd.DataFrame({
        "subject": typd["subject"],
        "label_pd": typd["Group"] == "PD",
        "tremor_only": False,
        "label_source": "clinical",
    })
    tappy = pd.read_csv(INTERIM / "tappy_users.csv")
    assert tappy["Parkinsons"].notna().all() and tappy["Tremors"].notna().all(),         "tappy label table Parkinsons/Tremors contain NaN"
    tappy = pd.DataFrame({
        "subject": tappy["subject"].astype(str),
        "label_pd": tappy["Parkinsons"] == True,
        "tremor_only": (tappy["Tremors"] == True) & (tappy["Parkinsons"] == False),
        "label_source": "self_report",
    })
    oe = pd.read_csv(INTERIM / "oe_subjects.csv")
    assert oe["diagnosis"].notna().all(), "oe_subjects diagnosis column contains NaN"
    oe = pd.DataFrame({
        "subject": oe["subject"].astype(str),
        "label_pd": oe["diagnosis"] == 1,
        "tremor_only": False,
        "label_source": "self_report",
    })
    out = {"mit": pd.DataFrame(mit), "typd": typd, "tappy": tappy, "oe": oe}
    for name, df_lab in out.items():
        assert df_lab["subject"].notna().all(), f"{name} label table subject contains NaN"
        assert df_lab["label_pd"].notna().all(), f"{name} label table label_pd contains NaN"
        assert df_lab["tremor_only"].notna().all(), f"{name} label table tremor_only contains NaN"
    return out

def clean_dataset(dataset: str, flow: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_parquet(EVENTS[dataset])
    press = PRESS_COL[dataset]
    n_raw_events = len(df)
    subjects_raw = df["subject"].nunique()

    if dataset == "typd":
        df = df.copy()
        df["session"] = df["subject"].astype(str)

    pool = df[df["keep_flag"]].copy()
    n_no_pred = int(pool["latency_ms"].isna().sum())
    pool = pool[pool["latency_ms"].notna() & pool["flight_ms"].notna()]
    n_pool = len(pool)

    ok = (pool["hold_ms"] > 0) & (pool["hold_ms"] <= HOLD_MAX_MS) \
        & (pool["latency_ms"] > 0) & (pool["latency_ms"] <= HOLD_MAX_MS)
    n_drop_hold_latency = int((~ok).sum())
    pool = pool[ok]
    n_after_universal = len(pool)

    n_drop_flight = 0
    if dataset in ("mit", "typd", "oe"):
        okf = pool["flight_ms"] <= FLIGHT_MAX_MS
        n_drop_flight = int((~okf).sum())
        pool = pool[okf]

    if dataset in ("mit", "typd", "oe"):
        pcol = "press_ms" if dataset != "oe" else "keydown"
        sess_stat = pool.groupby(["subject", "session"], observed=True).agg(
            n_valid=("hold_ms", "size"),
            t0=(pcol, "min"),
            t1=(pcol, "max"),
        ).reset_index()
        sess_stat["rate"] = sess_stat["n_valid"] / ((sess_stat["t1"] - sess_stat["t0"]) / 60_000.0).replace(0, np.nan)
    else:
        sess_stat = pool.groupby(["subject", "session"], observed=True).size().rename("n_valid").reset_index()
        sess_stat["rate"] = np.nan

    sess_stat["visit_selected"] = True
    n_drop_visit_sessions = 0
    if dataset == "mit":
        sess_stat["epoch"] = sess_stat["session"].str.split(".").str[0].astype("int64")
        keep_sess = sess_stat.groupby("subject", observed=True)["epoch"].transform("min") == sess_stat["epoch"]
        n_drop_visit_sessions = int((~keep_sess).sum())
        sess_stat = sess_stat[keep_sess].drop(columns=["epoch"])

    sess_stat["excluded_by"] = ""
    if dataset in ("mit", "typd", "oe"):
        m = sess_stat["rate"] < MIN_RATE
        sess_stat.loc[m, "excluded_by"] = "rate_lt20"
    m2 = sess_stat["n_valid"] < SESSION_MIN_DIGRAPH
    sess_stat.loc[m2 & (sess_stat["excluded_by"] == ""), "excluded_by"] = "valid_lt100"

    kept_sessions = sess_stat[sess_stat["excluded_by"] == ""]
    n_drop_rate = int((sess_stat["excluded_by"] == "rate_lt20").sum())
    n_drop_min100 = int((sess_stat["excluded_by"] == "valid_lt100").sum())

    s5_sessions = int(len(kept_sessions))
    s5_digraphs = int(kept_sessions["n_valid"].sum())

    persons_before = set(sess_stat["subject"].unique())
    per_subj = kept_sessions.groupby("subject", observed=True)["n_valid"].sum()
    ok_subj = set(per_subj[per_subj >= PERSON_MIN_DIGRAPH].index)
    kept_sessions = kept_sessions[kept_sessions["subject"].isin(ok_subj)]
    persons_after = set(kept_sessions["subject"].unique())
    n_drop_all_sessions = len(persons_before - set(per_subj.index))
    n_drop_person = len(set(per_subj.index) - ok_subj)

    kept_keys = kept_sessions[["subject", "session"]]
    final = pool.merge(kept_keys, on=["subject", "session"], how="inner")
    sess_stat["n_digraphs_final"] = sess_stat["session"].map(final.groupby("session", observed=True).size()).fillna(0).astype("int64")
    sess_stat["person_excluded"] = ~sess_stat["subject"].isin(persons_after)

    subjects_kept = final["subject"].nunique()
    _s0_note = ("parser events on record; session count = visit (338 trials; unit = visit)" if dataset == "typd" else "parser events on record")
    flow.append({"dataset": dataset, "step": "S0_raw_events", "n_subjects": subjects_raw,
                 "n_sessions": int(df["session"].nunique()),
                 "n_digraphs": n_raw_events, "note": _s0_note})
    flow.append({"dataset": dataset, "step": "S1_digraph_rules", "n_subjects": subjects_raw,
                 "n_sessions": int(df["session"].nunique()), "n_digraphs": n_pool,
                 "note": f"digraph pool (keep_flag + timestamps); no_predecessor={n_no_pred}"})
    flow.append({"dataset": dataset, "step": "S2_universal_rules", "n_subjects": subjects_raw,
                 "n_sessions": int(df["session"].nunique()), "n_digraphs": int(n_after_universal),
                 "note": f"dropped hold/latency outside (0,10s]: {n_drop_hold_latency}"})
    if dataset in ("mit", "typd", "oe"):
        flow.append({"dataset": dataset, "step": "S3_fixed_text_rules", "n_subjects": subjects_raw,
                     "n_sessions": int(df["session"].nunique()), "n_digraphs": int(len(pool)),
                     "note": f"dropped flight>3s: {n_drop_flight}"})
    flow.append({"dataset": dataset, "step": "S4_visit_selection", "n_subjects": subjects_raw,
                 "n_sessions": int(len(sess_stat) + n_drop_visit_sessions), "n_digraphs": int(len(pool)),
                 "note": f"dropped non-first-visit MIT sessions: {n_drop_visit_sessions}" if n_drop_visit_sessions else "n/a"})
    flow.append({"dataset": dataset, "step": "S5_session_rules", "n_subjects": subjects_raw,
                 "n_sessions": s5_sessions, "n_digraphs": s5_digraphs,
                 "note": f"dropped rate<20: {n_drop_rate}; valid<100: {n_drop_min100}"})
    flow.append({"dataset": dataset, "step": "S6_person_rules", "n_subjects": subjects_kept,
                 "n_sessions": int(len(kept_sessions)), "n_digraphs": int(kept_sessions["n_valid"].sum()),
                 "note": f"excluded person<300: {n_drop_person}; person's sole session removed by session rules: {n_drop_all_sessions}"})

    sess_stat.insert(0, "dataset", dataset)
    sess_stat["subject"] = sess_stat["subject"].astype(str)
    return final, sess_stat, set(df["subject"].astype(str).unique())

def person_features(final: pd.DataFrame, dataset: str) -> pd.DataFrame:
    rows = []
    for subj, g in final.groupby("subject", observed=True):
        rec = {"subject_id": f"{dataset}_{subj}", "dataset": dataset, "subject": str(subj)}
        for sig, col in (("hold", "hold_ms"), ("latency", "latency_ms"), ("flight", "flight_ms")):
            v = g[col].to_numpy(dtype="float64")
            rec[f"L1_{sig}_mean"] = float(np.mean(v))
            rec[f"L1_{sig}_median"] = float(np.median(v))
            rec[f"L1_{sig}_sd"] = float(np.std(v, ddof=1)) if len(v) > 1 else 0.0
            rec[f"L1_{sig}_p10"] = float(np.percentile(v, 10))
            rec[f"L1_{sig}_p90"] = float(np.percentile(v, 90))
        if dataset == "tappy":
            for hand in ("L", "R"):
                gh = g[g["hand_from"] == hand]
                for sig, col in (("hold", "hold_ms"), ("latency", "latency_ms"), ("flight", "flight_ms")):
                    rec[f"L2tappy_{sig}_{hand}_mean"] = float(gh[col].mean()) if len(gh) else np.nan
        rows.append(rec)
    return pd.DataFrame(rows)

def main() -> None:
    ap = argparse.ArgumentParser()
    args = ap.parse_args()

    PROCESSED.mkdir(parents=True, exist_ok=True)
    Path("results").mkdir(exist_ok=True)
    flow: list[dict] = []
    finals, sess_all = {}, []
    raw_subjects = {}
    for dataset in ("mit", "tappy", "typd", "oe"):
        final, sess_stat, subj_set = clean_dataset(dataset, flow)
        finals[dataset] = final
        sess_all.append(sess_stat)
        raw_subjects[dataset] = subj_set

    final_pool = pd.concat(
        [f.assign(subject=f["subject"].astype(str)) for f in finals.values()],
        ignore_index=True)
    INTERIM.mkdir(parents=True, exist_ok=True)
    final_pool.to_parquet(INTERIM / "final_digraphs.parquet", index=False)

    labels = load_labels()
    subj_rows = []
    for dataset, final in finals.items():
        lab = labels[dataset]
        feats = person_features(final, dataset)
        feats = feats.merge(lab, on="subject", how="left")

        n_no_label = int(feats["label_pd"].isna().sum())
        feats["tremor_only"] = feats["tremor_only"].fillna(False).astype(bool)
        feats = feats[feats["label_pd"].notna()].copy()
        feats["label_pd"] = feats["label_pd"].astype(bool)
        n_tremor = int(feats["tremor_only"].sum())
        feats_main = feats[~feats["tremor_only"]].copy()
        subj_rows.append((dataset, feats, feats_main, n_no_label, n_tremor))

        labeled_no_events = int(len(lab) - lab["subject"].isin(raw_subjects[dataset]).sum())
        last = [f for f in flow if f["dataset"] == dataset][-1]
        flow.append({"dataset": dataset, "step": "S7_label_rules", "n_subjects": int(len(feats_main)),
                     "n_sessions": int(last["n_sessions"]), "n_digraphs": int(last["n_digraphs"]),
                     "note": f"no label: {n_no_label}; tremor-only excluded from the main analysis: {n_tremor}; "
                             f"labeled but no events: {labeled_no_events}"})
        flow.append({"dataset": dataset, "step": "S8_eligible_main", "n_subjects": int(len(feats_main)),
                     "n_sessions": int(last["n_sessions"]), "n_digraphs": int(last["n_digraphs"]),
                     "note": f"PD={int(feats_main['label_pd'].sum())} HC={int((~feats_main['label_pd']).sum())}"})

    subjects_all = pd.concat([fm for _, _, fm, _, _ in subj_rows], ignore_index=True)
    subjects_full = pd.concat([fa for _, fa, _, _, _ in subj_rows], ignore_index=True)
    sessions_out = pd.concat(sess_all, ignore_index=True)

    eligible_keys = set(zip(subjects_all["dataset"], subjects_all["subject"].astype(str)))
    sessions_out["label_excluded"] = [
        (d, str(sub)) not in eligible_keys for d, sub in zip(sessions_out["dataset"], sessions_out["subject"])
    ]
    dup = sessions_out.duplicated(subset=["dataset", "subject", "session"])
    assert not dup.any(), f"session uniqueness assertion failed: {int(dup.sum())} duplicate (dataset,subject,session)"

    subjects_out = subjects_all.copy()
    cols_front = ["subject_id", "dataset", "subject", "label_pd", "label_source"]
    subjects_out = subjects_out[cols_front + [c for c in subjects_out.columns if c not in cols_front]]
    subjects_out.to_csv(PROCESSED / "subjects.csv", index=False)
    sessions_out.to_parquet(PROCESSED / "sessions.parquet", index=False)

    flow_df = pd.DataFrame(flow)
    totals = []
    for step in flow_df["step"].unique():
        sub = flow_df[flow_df["step"] == step]
        if step in ("S7_label_rules", "S4_visit_selection", "S1_digraph_rules", "S2_universal_rules", "S3_fixed_text_rules"):
            continue
        totals.append({"dataset": "TOTAL", "step": step,
                       "n_subjects": int(sub["n_subjects"].sum()),
                       "n_sessions": int(sub["n_sessions"].sum()),
                       "n_digraphs": int(sub["n_digraphs"].sum()),
                       "note": ""})
    flow_df = pd.concat([flow_df, pd.DataFrame(totals)], ignore_index=True)
    flow_df.to_csv("results/cohort_flow.csv", index=False)

    n_eligible = int(len(subjects_all))
    n_pd = int(subjects_all["label_pd"].sum())
    gate_pass = n_eligible >= 400
    per_ds = {d: int(len(fm)) for d, _, fm, _, _ in subj_rows}
    print(f"[build_tables] eligible={n_eligible} (PD={n_pd}/HC={n_eligible - n_pd}) "
          f"per-dataset={per_ds}")
    print(f"[build_tables] gate(>=400): {'PASS' if gate_pass else 'FAIL'}")
    if not gate_pass:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
