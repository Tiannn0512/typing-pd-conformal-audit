#!/usr/bin/env python
"""subgroup_audit.py — 分组条件覆盖审计（TODO-4.9，描述性；plan §14 砍线序第二位）

冻结口径：--strata sex,age_median；描述性；MIT 性别失衡显式报告（TODO 台账）。
定位：测量真实覆盖的分层分布，供 limitations 与讨论引用——**边际 CP 保证不延伸
到组条件覆盖（Rafe 2026 陷阱，预注册引用），本审计是观察报告而非保证核查**；
无三分类/Holm/判定机制。

实现级预声明（实现时钉死、先于首次运行；按防复发制度 §4 本脚本先行单独 commit）：
  1. 方向 = primary 三方向，分层作用于**目标域**受试者；hits 由冻结管线确定性
     重算（seed=1、LR、tier=min(全链 cap)、α=0.10，与 4.2/4.3 逐位同源），每方向
     k/n 对 primary_family.csv lr 行断言。
  2. sex = Gender（data/interim/tappy_users.csv，自报字段）：仅 Tappy 来源受试者
     可算；MIT/OE 公开数据无性别字段 → 显式不可得行 + MIT 文献口径 caveat
     （对照组女性偏多 ~17pp，计划书局限声明冻结值）；TyPD 有临床 Gender 但非任何
     primary 方向目标，不入。
  3. age = 中位 session 年份 − BirthYear（仅 Tappy：session 后缀 YYMM→年；
     tappy_users BirthYear）；**缺失不静默剔除**→ unknown 层（Tappy 28/173 无
     BirthYear）；age_median = 该方向目标内非缺失年龄的中位数分割（≤med / >med）。
  4. gold_merged2self 目标 366 = Tappy 173 + OE 193：性别/年龄层仅覆盖 Tappy 子
     切片，covers 列显式（173/366=47.3%）；OE 193 无字段如实计数。
  5. 每层报 n/n_pd/k/coverage/CP 95% CI（K=0/K=n 守卫）/mean_size/singleton_rate；
     层间比较纯描述性——小层宽 CI 如实呈现。
  6. 无新随机性（全链确定性）。
产出：results/subgroup_coverage_audit.csv + results/subgroup_strata_availability.csv
     + data/interim/parse_reports/subgroup_audit_report.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cp.conformal import lac_scores, predict_sets_split  # noqa: E402
from cp.coverage_audit import ALPHA, CAP, DIRECTIONS, SEED, load_pooled  # noqa: E402
from cp.remediate import cp_ci  # noqa: E402
from models.run_transfer import load_matrix, tier_columns  # noqa: E402

MIT_SEX_CAVEAT = ("MIT 公开数据无性别字段；文献口径：对照组女性偏多 ~17pp"
                  "（计划书局限声明冻结值）——该方向性别层不可计算，仅显式登记")


def load_target_with_ids(cfg: dict) -> dict:
    """与 coverage_audit 装载路径逐字同构，额外保留 subject_id 行序。"""
    srcs, tgt = cfg["sources"], cfg["target"]
    tgt_datasets = {"merged_self": ["tappy", "oe"]}.get(tgt, [tgt])
    tier = min(CAP[d] for d in srcs + tgt_datasets)
    X_s, y_s = load_pooled(srcs, tier)
    subjects = pd.read_csv("data/processed/subjects.csv")
    if tgt == "merged_self":
        pool = subjects[subjects["dataset"].isin(["tappy", "oe"])].copy()
        cols = [c for c in pool.columns if c.startswith("L1_")]
        X_t = pool[cols].to_numpy(dtype=float)
        y_t = pool["label_pd"].to_numpy(dtype=int)
        ids = pool["subject_id"].to_numpy()
        origin = pool["dataset"].to_numpy()
    else:
        sub = subjects[subjects["dataset"] == tgt]
        l2l3 = pd.read_csv("data/processed/subjects_l2l3.csv")
        merged = sub.merge(l2l3, on="subject_id", how="left")
        cols = tier_columns(tgt, tier)
        X_t = merged[cols].to_numpy(dtype=float)
        y_t = merged["label_pd"].to_numpy(dtype=int)
        ids = merged["subject_id"].to_numpy()
        origin = np.array([tgt] * len(y_t), dtype=object)
    assert X_s.shape[1] == X_t.shape[1] and not np.isnan(X_t).any()
    return {"X_s": X_s, "y_s": y_s, "X_t": X_t, "y_t": y_t, "ids": ids,
            "origin": origin, "tier": tier}


def tappy_demo() -> pd.DataFrame:
    """Tappy 人口学：Gender（173/173 全有）+ 年龄（中位 session 年 − BirthYear）。"""
    tu = pd.read_csv("data/interim/tappy_users.csv")
    subjects = pd.read_csv("data/processed/subjects.csv")
    tap = subjects[subjects["dataset"] == "tappy"][["subject_id", "subject"]]
    tap = tap.merge(tu[["subject", "Gender", "BirthYear"]], on="subject", how="left")
    sp = pd.read_parquet("data/processed/sessions.parquet")
    taps = sp[sp["dataset"] == "tappy"]
    yy = taps["session"].str.extract(r"_(\d{2})\d{2}$")[0]
    taps = taps.assign(yr=2000 + yy.astype(int))
    med_year = taps.groupby("subject")["yr"].median()
    byear = pd.to_numeric(tap["BirthYear"], errors="coerce")
    tap["sex"] = tap["Gender"]
    tap["age"] = tap["subject"].map(med_year) - byear
    return tap[["subject_id", "sex", "age"]]


def main() -> None:
    ap = argparse.ArgumentParser(description="Subgroup coverage audit (TODO-4.9, descriptive)")
    ap.add_argument("--strata", default="sex,age_median")
    ap.add_argument("--directions", default="primary")
    args = ap.parse_args()
    assert args.strata.split(",") == ["sex", "age_median"], "分层变量须为注册对 sex,age_median"
    assert args.directions == "primary"

    demo = tappy_demo()
    frozen = pd.read_csv("results/primary_family.csv")

    rows, avail = [], []
    for cfg in DIRECTIONS:
        d = load_target_with_ids(cfg)
        direction, n = cfg["direction"], len(d["y_t"])
        idx = np.arange(len(d["X_s"]))
        tr_idx, cal_idx = train_test_split(idx, test_size=0.30, random_state=SEED,
                                           stratify=d["y_s"])
        scaler = StandardScaler().fit(d["X_s"][tr_idx])
        clf = LogisticRegression(random_state=42, max_iter=1000)
        clf.fit(scaler.transform(d["X_s"][tr_idx]), d["y_s"][tr_idx])
        sets = predict_sets_split(
            lac_scores(clf.predict_proba(scaler.transform(d["X_s"][cal_idx])),
                       d["y_s"][cal_idx]),
            clf.predict_proba(scaler.transform(d["X_t"])), ALPHA)
        hits = np.array([t in s for t, s in zip(d["y_t"], sets)])
        sizes = np.array([len(s) for s in sets])
        k = int(hits.sum())
        f = frozen[(frozen["direction"] == direction) & (frozen["model"] == "lr")].iloc[0]
        assert int(f["k"]) == k and int(f["n"]) == n, f"{direction} k/n 漂移"
        for col in ("coverage", "cpc_pd", "cpc_hc", "mean_size", "singleton_rate"):
            assert abs(float(f[col]) - (hits.mean() if col == "coverage" else
                                        hits[d["y_t"] == 1].mean() if col == "cpc_pd" else
                                        hits[d["y_t"] == 0].mean() if col == "cpc_hc" else
                                        sizes.mean() if col == "mean_size" else
                                        (sizes == 1).mean())) < 1e-12, f"{direction} {col} 漂移"

        tgt_ids = pd.DataFrame({"subject_id": d["ids"], "origin": d["origin"],
                                "hit": hits, "size": sizes})
        merged_ids = tgt_ids.merge(demo, on="subject_id", how="left")

        # 分层可用性登记
        tappy_mask = merged_ids["origin"].isin(["tappy"])
        sex_ok = merged_ids["sex"].notna()
        age_ok = merged_ids["age"].notna()
        if direction == "tappy2mit":
            avail.append({"direction": direction, "stratum": "sex",
                          "status": "unavailable_no_field",
                          "covers_n": 0, "of_target": n, "note": MIT_SEX_CAVEAT})
            avail.append({"direction": direction, "stratum": "age_median",
                          "status": "unavailable_no_field",
                          "covers_n": 0, "of_target": n,
                          "note": "MIT 公开数据无出生年/年龄字段"})
        else:
            for stratum in ("sex", "age_median"):
                m = sex_ok if stratum == "sex" else age_ok
                avail.append({"direction": direction, "stratum": stratum,
                              "status": "computed_partial",
                              "covers_n": int(m.sum()), "of_target": n,
                              "note": f"仅 Tappy 来源可算（OE 无人口学字段）；"
                                      f"覆盖 {int(m.sum())}/{n}"})

        def emit(stratum: str, level: str, mask: np.ndarray, note: str) -> None:
            hits_m, sizes_m, y_m = hits[mask], sizes[mask], d["y_t"][mask]
            k_m, n_m = int(hits_m.sum()), int(mask.sum())
            lo, hi = cp_ci(k_m, n_m)
            rows.append({"direction": direction, "stratum": stratum, "level": level,
                         "n": n_m, "n_pd": int(y_m.sum()), "k": k_m,
                         "coverage": k_m / n_m, "ci_lo": lo, "ci_hi": hi,
                         "mean_size": float(sizes_m.mean()),
                         "singleton_rate": float((sizes_m == 1).mean()),
                         "covers_n": n_m, "of_target": n, "note": note})

        if direction != "tappy2mit":
            med = float(merged_ids.loc[age_ok, "age"].median())
            emit("sex", "Male", (merged_ids["sex"] == "Male").to_numpy(),
                 "自报 Gender（tappy_users）；Tappy 子切片")
            emit("sex", "Female", (merged_ids["sex"] == "Female").to_numpy(),
                 "自报 Gender（tappy_users）；Tappy 子切片")
            emit("age_median", "age<=median", (merged_ids["age"] <= med).to_numpy(),
                 f"中位 session 年−BirthYear，非缺失中位数={med:.1f}")
            emit("age_median", "age>median", (merged_ids["age"] > med).to_numpy(),
                 f"中位 session 年−BirthYear，非缺失中位数={med:.1f}")
            n_unknown = int((~age_ok).sum())
            n_oe = int((~tappy_mask).sum())
            emit("age_median", "unknown", (~age_ok).to_numpy(),
                 f"OE 无字段 {n_oe} + Tappy BirthYear 缺失 {n_unknown - n_oe}"
                 "（不静默剔除）")

    out = pd.DataFrame(rows)
    out.to_csv("results/subgroup_coverage_audit.csv", index=False)
    pd.DataFrame(avail).to_csv("results/subgroup_strata_availability.csv", index=False)

    print("\n=== 分组条件覆盖审计（描述性；LR 主参照，seed=1 确证切分）===")
    for _, r in out.iterrows():
        print(f"[{r['direction']}|{r['stratum']}={r['level']}] n={int(r['n'])}"
              f"（PD {int(r['n_pd'])}）覆盖={r['coverage']:.4f} "
              f"CI[{r['ci_lo']:.4f},{r['ci_hi']:.4f}] 大小={r['mean_size']:.3f}")
    for a in avail:
        if a["status"].startswith("unavailable"):
            print(f"[{a['direction']}|{a['stratum']}] {a['status']} — {a['note']}")
    caveat = ("Descriptive observation only: marginal CP does not extend to "
              "group-conditional guarantees (Rafe 2026 trap, pre-registered). "
              "Small strata carry wide CIs.")
    print(f"\n{caveat}")

    predecl = __doc__.split("实现级预声明")[1].split("产出")[0].strip()
    Path("data/interim/parse_reports").mkdir(parents=True, exist_ok=True)
    Path("data/interim/parse_reports/subgroup_audit_report.json").write_text(
        json.dumps({"predeclarations": predecl, "caveat": caveat, "rows": rows,
                    "availability": avail}, indent=2, default=float), encoding="utf-8")
    print(f"共 {len(out)} 层行 → results/subgroup_coverage_audit.csv")


if __name__ == "__main__":
    main()
