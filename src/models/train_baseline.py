#!/usr/bin/env python
"""train_baseline.py — MIT 库内基线（TODO-3.2 go/no-go）

冻结配置：configs/baseline_mit.yaml（含 DEC-B1/B2/B3 三条看数前决策）。
规格：dataset=mit（82 人：42 PD/40 HC，冻结队列表口径），L1 15 特征，
两步 stratified 40/30/30 切分（实际 32/25/25），50 seeds（split_seeds 1-50），
LR + LightGBM 官方默认参数（零调参），AUC 于 val/test 分别记录。
Golden gate：LightGBM 50-seed 平均 test AUC ∈ [0.75, 0.91]；越界 → SystemExit(1)（停，先讨论）。

用法：python src/models/train_baseline.py --config configs/baseline_mit.yaml
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from lightgbm import LGBMClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

MODEL_SEED = 42  # configs/seeds.yaml model_seed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/baseline_mit.yaml")
    ap.add_argument("--out", default="results/baseline_mit.csv")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))

    seeds_path = Path(__file__).resolve().parents[2] / "configs" / "seeds.yaml"
    seeds_cfg = yaml.safe_load(open(seeds_path, encoding="utf-8"))
    split_seeds = seeds_cfg["split_seeds"]

    subjects = pd.read_csv("data/processed/subjects.csv")
    mit = subjects[subjects["dataset"] == "mit"].copy()
    assert len(mit) == 82, f"mit 行数 {len(mit)} ≠ 82（冻结队列表口径）"
    feature_cols = [c for c in mit.columns if c.startswith("L1_")]
    assert len(feature_cols) == 15
    X_all = mit[feature_cols].to_numpy(dtype=float)
    y_all = mit["label_pd"].to_numpy(dtype=int)
    assert not np.isnan(X_all).any()

    rows = []
    for seed in split_seeds:
        # 两步 stratified 切分：60/40 → 50/50（实际 32/25/25，DEC-B2 接受 sklearn 取整）
        X_tr, X_tmp, y_tr, y_tmp = train_test_split(
            X_all, y_all, test_size=0.60, random_state=seed, stratify=y_all)
        X_va, X_te, y_va, y_te = train_test_split(
            X_tmp, y_tmp, test_size=0.50, random_state=seed, stratify=y_tmp)
        # 标准化仅在 train 折内 fit（泄漏守卫）
        scaler = StandardScaler().fit(X_tr)
        X_tr_s, X_va_s, X_te_s = scaler.transform(X_tr), scaler.transform(X_va), scaler.transform(X_te)

        # LR：官方默认（DEC-B3 零调参不变）
        clf = LogisticRegression(random_state=MODEL_SEED, max_iter=1000).fit(X_tr_s, y_tr)
        auc_va = roc_auc_score(y_va, clf.predict_proba(X_va_s)[:, 1])
        auc_te = roc_auc_score(y_te, clf.predict_proba(X_te_s)[:, 1])
        rows.append({"seed": seed, "model": "lr", "auc_val": auc_va, "auc_test": auc_te,
                     "lgbm_min_child_samples": None, "lgbm_max_depth": None,
                     "n_train": len(y_tr), "n_val": len(y_va), "n_test": len(y_te)})

        # LightGBM：DEC-B3b 预声明微网格，val AUC 选择（源域内部，协议 §3），test 一次性评估
        grid = [(5, 2), (5, 3), (10, 2), (10, 3)]  # (min_child_samples, max_depth) 声明序=平局序
        best = None
        for mcs, depth in grid:
            clf = LGBMClassifier(random_state=MODEL_SEED, verbose=-1,
                                 min_child_samples=mcs, max_depth=depth).fit(X_tr_s, y_tr)
            v = roc_auc_score(y_va, clf.predict_proba(X_va_s)[:, 1])
            if best is None or v > best[0]:
                best = (v, mcs, depth)
        val_sel, mcs_sel, depth_sel = best
        clf = LGBMClassifier(random_state=MODEL_SEED, verbose=-1,
                             min_child_samples=mcs_sel, max_depth=depth_sel).fit(X_tr_s, y_tr)
        auc_te = roc_auc_score(y_te, clf.predict_proba(X_te_s)[:, 1])
        rows.append({"seed": seed, "model": "lightgbm", "auc_val": val_sel, "auc_test": auc_te,
                     "lgbm_min_child_samples": mcs_sel, "lgbm_max_depth": depth_sel,
                     "n_train": len(y_tr), "n_val": len(y_va), "n_test": len(y_te)})

    res = pd.DataFrame(rows)
    Path(args.out).parent.mkdir(exist_ok=True)
    res.to_csv(args.out, index=False)

    summary = {}
    for model_name in ("lr", "lightgbm"):
        sub = res[res["model"] == model_name]
        summary[model_name] = {
            "mean_auc_test": float(sub["auc_test"].mean()),
            "median_auc_test": float(sub["auc_test"].median()),
            "std_auc_test": float(sub["auc_test"].std(ddof=1)),
            "se_mean": float(sub["auc_test"].std(ddof=1) / np.sqrt(len(sub))),
            "mean_auc_val": float(sub["auc_val"].mean()),
        }
    gate_stat = summary["lightgbm"]["mean_auc_test"]
    gate_lo, gate_hi = 0.75, 0.91
    gate_pass = gate_lo <= gate_stat <= gate_hi
    report = {
        "config_echo": args.config,
        "n_subjects": len(mit),
        "n_pd": int(y_all.sum()),
        "n_hc": int(len(y_all) - y_all.sum()),
        "features": feature_cols,
        "summary": summary,
        "gate": {"rule": "lightgbm mean_auc_test ∈ [0.75, 0.91]",
                 "stat": gate_stat, "pass": gate_pass},
    }
    out_json = Path("data/interim/parse_reports/baseline_mit_report.json")
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"[baseline_mit] seeds={len(split_seeds)} LR mean={summary['lr']['mean_auc_test']:.4f} "
          f"LightGBM mean={gate_stat:.4f} (median={summary['lightgbm']['median_auc_test']:.4f}, "
          f"se={summary['lightgbm']['se_mean']:.4f})")
    print(f"[baseline_mit] GATE [0.75, 0.91]: {'PASS' if gate_pass else 'FAIL — 停，先讨论'}")
    if not gate_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
