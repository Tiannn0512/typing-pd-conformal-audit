"""Aligned feature loading and source-only model fitting."""

from datetime import datetime, timezone
import hashlib
import itertools
import json
import os
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from cp.conformal import lac_scores, predict_sets_split, validate_labels
from protocol import ALPHA, CALIBRATION_FRACTION, CAP, MODEL_SEED, SEED
from runtime import require

L1_COLS = [
    f"L1_{signal}_{stat}"
    for signal in ("hold", "latency", "flight")
    for stat in ("mean", "median", "sd", "p10", "p90")
]
L2_COLS = [
    f"{signal}_{hand}_mean"
    for signal in ("hold", "latency", "flight")
    for hand in ("L", "R")
]
L3_COLS = [
    f"{signal}_{transition}_mean"
    for signal in ("latency", "flight")
    for transition in ("same", "cross")
] + ["frac_cross"]
_ARTIFACT_IDS = itertools.count(1)


def tier_columns(dataset, tier):
    require(
        dataset in CAP and type(tier) is int and 1 <= tier <= CAP[dataset],
        f"Unsupported feature tier: {dataset}/{tier}",
    )
    columns = list(L1_COLS)
    if tier >= 2:
        prefix = "L2tappy" if dataset == "tappy" else f"L2_{dataset}"
        columns += [f"{prefix}_{column}" for column in L2_COLS]
    if tier >= 3:
        columns += [f"L3_{dataset}_{column}" for column in L3_COLS]
    return columns


def _subjects():
    subjects = pd.read_csv("data/processed/subjects.csv")
    require(
        subjects["subject_id"].notna().all() and subjects["subject_id"].is_unique,
        "Subject IDs must be present and unique",
    )
    return subjects


def load_matrix(dataset, tier):
    subjects = _subjects()
    sub = subjects[subjects["dataset"] == dataset]
    require(len(sub) > 0, f"No subjects for {dataset}")
    if tier > 1 and dataset != "tappy":
        extra = pd.read_csv("data/processed/subjects_l2l3.csv")
        require(
            extra["subject_id"].notna().all(), "Extra-feature subject IDs are missing"
        )
        sub = sub.merge(extra, on="subject_id", how="left", validate="one_to_one")
    columns = tier_columns(dataset, tier)
    X = sub[columns].to_numpy(dtype=float)
    y = validate_labels(sub["label_pd"].to_numpy(), len(sub))
    require(np.isfinite(X).all(), f"{dataset} tier {tier} features must be finite")
    return X, y


def load_pooled(datasets, tier):
    require(
        bool(datasets)
        and len(datasets) == len(set(datasets))
        and all(d in CAP for d in datasets),
        "Source datasets must be known and distinct",
    )
    if len(datasets) == 1:
        return load_matrix(datasets[0], tier)
    require(tier == 1, "Registered multi-dataset pools use tier 1")
    # Preserve subject row order while fixing the feature order across all pools.
    pool = _subjects()
    pool = pool[pool["dataset"].isin(datasets)]
    require(len(pool) > 0, "The pooled dataset is empty")
    X = pool[L1_COLS].to_numpy(dtype=float)
    y = validate_labels(pool["label_pd"].to_numpy(), len(pool))
    require(np.isfinite(X).all(), "Pooled features must be finite")
    return X, y


def direction_data(cfg):
    targets = ["tappy", "oe"] if cfg["target"] == "merged_self" else [cfg["target"]]
    tier = min(CAP[d] for d in cfg["sources"] + targets)
    X_s, y_s = load_pooled(cfg["sources"], tier)
    X_t, y_t = load_pooled(targets, tier)
    return X_s, y_s, X_t, y_t, tier


def source_split(y, seed=SEED):
    y = validate_labels(y, len(y))
    require(len(np.unique(y)) == 2, "Source data must contain both classes")
    train, calibration = train_test_split(
        np.arange(len(y)), test_size=CALIBRATION_FRACTION, random_state=seed, stratify=y
    )
    require(
        not np.intersect1d(train, calibration).size,
        "Train/calibration subjects overlap",
    )
    return train, calibration


def fit_model(X_train, y_train, model_name="lr", **parameters):
    X_train = np.asarray(X_train, dtype=float)
    require(
        X_train.ndim == 2 and np.isfinite(X_train).all(),
        "Training features must be a finite matrix",
    )
    y_train = validate_labels(y_train, len(X_train))
    require(len(np.unique(y_train)) == 2, "Training labels must contain both classes")
    scaler = StandardScaler().fit(X_train)
    if model_name == "lr":
        clf = LogisticRegression(
            **{"random_state": MODEL_SEED, "max_iter": 1000, **parameters}
        )
    elif model_name in ("lgbm", "lightgbm"):
        from lightgbm import LGBMClassifier

        params = {
            "min_child_samples": max(1, len(y_train) // 4),
            "max_depth": 3,
            **parameters,
        }
        clf = LGBMClassifier(random_state=MODEL_SEED, verbose=-1, **params)
    else:
        raise ValueError(f"Unknown model: {model_name}")
    started_at = datetime.now(timezone.utc).isoformat()
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        clf.fit(scaler.transform(X_train), y_train)
    clf._audit_started_at = started_at
    clf._audit_ended_at = datetime.now(timezone.utc).isoformat()
    return scaler, clf


def record_fit(scaler, clf, arrays):
    artifact_root = os.environ.get("TYPING_PD_ARTIFACT_DIR")
    if not artifact_root:
        return
    directory = Path(artifact_root) / os.environ.get("TYPING_PD_STAGE", "analysis")
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"fit-{next(_ARTIFACT_IDS):06d}"
    saved = {
        **{
            name: value
            for name, value in arrays.items()
            if not name.endswith(("features", "labels"))
        },
        "scaler_mean": scaler.mean_,
        "scaler_scale": scaler.scale_,
    }
    if hasattr(clf, "coef_"):
        saved.update(coefficients=clf.coef_, intercept=clf.intercept_)
    else:
        (directory / f"{stem}.txt").write_text(
            clf.booster_.model_to_string(), encoding="utf-8"
        )
    np.savez_compressed(directory / f"{stem}.npz", **saved)
    metadata = {
        "model": type(clf).__name__,
        "started_at": clf._audit_started_at,
        "ended_at": clf._audit_ended_at,
        "parameters": clf.get_params(),
        "array_hashes": {
            name: hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()
            for name, value in arrays.items()
        },
    }
    (directory / f"{stem}.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


def fit_transfer(X_s, y_s, X_t, model_name="lr", seed=SEED, alpha=ALPHA):
    X_s, X_t = np.asarray(X_s, dtype=float), np.asarray(X_t, dtype=float)
    require(
        X_s.ndim == X_t.ndim == 2
        and X_s.shape[1] == X_t.shape[1]
        and np.isfinite(X_s).all()
        and np.isfinite(X_t).all(),
        "Source and target must be finite feature matrices with matching columns",
    )
    y_s = validate_labels(y_s, len(X_s))
    train, calibration = source_split(y_s, seed)
    scaler, clf = fit_model(X_s[train], y_s[train], model_name)
    probs_cal = clf.predict_proba(scaler.transform(X_s[calibration]))
    probs_te = clf.predict_proba(scaler.transform(X_t))
    scores_cal = lac_scores(probs_cal, y_s[calibration])
    sets = predict_sets_split(scores_cal, probs_te, alpha)
    record_fit(
        scaler,
        clf,
        {
            "train_indices": train,
            "calibration_indices": calibration,
            "source_features": X_s,
            "source_labels": y_s,
            "target_features": X_t,
            "probs_cal": probs_cal,
            "probs_te": probs_te,
        },
    )
    return {
        "scaler": scaler,
        "clf": clf,
        "train_indices": train,
        "calibration_indices": calibration,
        "probs_cal": probs_cal,
        "probs_te": probs_te,
        "scores_cal": scores_cal,
        "sets": sets,
    }


def fit_direction(cfg, model_name="lr"):
    X_s, y_s, X_t, y_t, tier = direction_data(cfg)
    result = fit_transfer(X_s, y_s, X_t, model_name)
    return {
        **result,
        "y_t": y_t,
        "y_cal": y_s[result["calibration_indices"]],
        "tier": tier,
        "n_source": len(result["train_indices"]),
        "n_cal": len(result["calibration_indices"]),
    }
