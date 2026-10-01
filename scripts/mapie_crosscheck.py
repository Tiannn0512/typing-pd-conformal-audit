#!/usr/bin/env python
"""mapie_crosscheck.py — 本项目 split conformal 实现 vs MAPIE 官方库对拍（一次性验证）

同一合成数据、同一模型（逻辑回归）、同一校准/测试切分下：
  本实现（src/cp/conformal.py，score = 1 − 真类概率，k = ceil((n+1)(1−α)) 有限样本校正）
  vs MAPIE 1.5.0 SplitConformalClassifier（conformity_score='lac'，同一口径）
对比：逐测试点预测集一致率、覆盖率、平均集合大小。
结果落 results/mapie_crosscheck.md。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cp.conformal import lac_scores, predict_sets_split  # noqa: E402

from mapie.classification import SplitConformalClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402

SEED = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "configs" / "seeds.yaml").read_text(encoding="utf-8")
)["unit_test_seed"]
ALPHA = 0.10


def main() -> None:
    rng = np.random.default_rng(SEED)
    # 合成二分类：二维高斯，非线性边界（保证模型非完美、集合非平凡）
    n = 6000
    x0 = rng.multivariate_normal([0, 0], [[1, 0.3], [0.3, 1]], n // 2)
    x1 = rng.multivariate_normal([1.2, 0.8], [[1.2, -0.2], [-0.2, 0.9]], n // 2)
    X = np.vstack([x0, x1])
    y = np.array([0] * (n // 2) + [1] * (n // 2))
    X_tr, X_tmp, y_tr, y_tmp = train_test_split(X, y, test_size=0.5, random_state=SEED, stratify=y)
    X_cal, X_te, y_cal, y_te = train_test_split(X_tmp, y_tmp, test_size=0.6,
                                                 random_state=SEED + 1, stratify=y_tmp)  # 衍生 seed 见 seeds.yaml derived_seeds

    model = LogisticRegression(max_iter=1000, random_state=SEED).fit(X_tr, y_tr)
    probs_cal = model.predict_proba(X_cal)
    probs_te = model.predict_proba(X_te)

    # 本实现
    scores_cal = lac_scores(probs_cal, y_cal)
    sets_ours = predict_sets_split(scores_cal, probs_te, ALPHA)

    # MAPIE（lac = 1 − 真类概率，同一口径）
    mapie = SplitConformalClassifier(
        estimator=model, confidence_level=1 - ALPHA, conformity_score="lac", prefit=True
    )
    mapie.conformalize(X_cal, y_cal)
    _, ps_mapie = mapie.predict_set(X_te)
    # MAPIE 返回 one-hot 形状 (n, n_classes)；转集合
    sets_mapie = [frozenset(np.where(row)[0].tolist()) for row in np.asarray(ps_mapie)]

    n_equal = sum(a == b for a, b in zip(sets_ours, sets_mapie))
    cov_ours = float(np.mean([y in s for y, s in zip(y_te, sets_ours)]))
    cov_mapie = float(np.mean([y in s for y, s in zip(y_te, sets_mapie)]))
    avg_ours = float(np.mean([len(s) for s in sets_ours]))
    avg_mapie = float(np.mean([len(s) for s in sets_mapie]))

    lines = [
        "# MAPIE 对拍报告（一次性验证）",
        "",
        f"**生成**：2026-09-26 ｜ **实现**：src/cp/conformal.py ｜ **对照**：MAPIE 1.5.0 "
        f"SplitConformalClassifier(conformity_score='lac', prefit=True)",
        f"**数据**：合成二维二分类 n=6000（train 3000 / cal 1200 / test 1800），seed={SEED}，α={ALPHA}",
        "",
        "| 指标 | 本实现 | MAPIE |",
        "|---|---|---|",
        f"| 覆盖率 | {cov_ours:.4f} | {cov_mapie:.4f} |",
        f"| 平均集合大小 | {avg_ours:.4f} | {avg_mapie:.4f} |",
        f"| 预测集逐点一致率 | {n_equal}/{len(sets_ours)} = {n_equal / len(sets_ours):.4%} | — |",
        "",
        f"**结论**：{'一致 ✅' if n_equal == len(sets_ours) else '存在差异，须排查 ❌'}"
        "（两实现使用同一 LAC 分数与同一有限样本校正分位；逐点一致为预期）。",
    ]
    Path("results").mkdir(exist_ok=True)
    Path("results/mapie_crosscheck.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"[mapie_crosscheck] equal={n_equal}/{len(sets_ours)} cov ours={cov_ours:.4f} mapie={cov_mapie:.4f}")
    if n_equal != len(sets_ours):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
