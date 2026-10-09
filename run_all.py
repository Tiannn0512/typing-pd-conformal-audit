#!/usr/bin/env python
"""run_all.py — 全管线复现入口（按 PROVENANCE 开发顺序串接各阶段 CLI）

阶段 = 数据解析/质检 → 特征与队列 → 基线验收门 + 12 方向迁移 → 共形审计/
类条件/补救/校准对照/应力/BBSE/敏感性/分组 → 功效模拟 → 论文表与图。
各阶段命令即生产调用：默认值 = 注册口径（模块内 assert 钉死），改参即偏离
预注册分析计划（docs/analysis_plan_v1.md）。

冻结纪律：--run 将再生成 results/ 冻结层。重跑产物须与 results-frozen-v1
（ce26f33）逐文件比对一致后方可替换；不一致即为偏离，先停下来查，不覆盖。

默认打印执行计划不执行；--run 真跑；--from NAME 从指定阶段起跑（断点续跑），
阶段失败即停，退出码非零。
"""
from __future__ import annotations

import argparse
import subprocess
import sys

PY = sys.executable

STAGES = [
    ("data.parse_mit",     [PY, "src/data/parse_mit.py"]),
    ("data.parse_oe",      [PY, "src/data/parse_oe.py"]),
    ("data.parse_tappy",   [PY, "src/data/parse_tappy.py"]),
    ("data.parse_tappy_users", [PY, "src/data/parse_tappy_users.py"]),
    ("data.parse_typd",    [PY, "src/data/parse_typd.py"]),
    ("data.qc",            [PY, "src/data/qc.py"]),
    ("data.validate_schema", [PY, "src/data/validate_schema.py", "--all"]),
    ("feat.build_features", [PY, "src/features/build_features.py"]),
    ("feat.build_tables",  [PY, "src/features/build_tables.py"]),
    ("model.train_baseline", [PY, "src/models/train_baseline.py"]),
    ("model.run_transfer", [PY, "src/models/run_transfer.py"]),
    ("cp.coverage_audit",  [PY, "src/cp/coverage_audit.py"]),
    ("cp.class_conditional", [PY, "src/cp/class_conditional.py", "--primary-directions"]),
    ("cp.remediate",       [PY, "src/cp/remediate.py"]),
    ("cp.calibration_compare", [PY, "src/cp/calibration_compare.py"]),
    ("cp.stress_test_a",   [PY, "src/cp/stress_test_a.py"]),
    ("cp.stress_three_arm", [PY, "src/cp/stress_three_arm.py"]),
    ("cp.bbse_synthetic",  [PY, "src/cp/bbse_synthetic.py"]),
    ("cp.run_sensitivity", [PY, "src/cp/run_sensitivity.py", "--all"]),
    ("cp.subgroup_audit",  [PY, "src/cp/subgroup_audit.py"]),
    ("power.power_sim",    [PY, "src/power_sim.py"]),
    ("docs.make_tables",   [PY, "scripts/make_tables.py"]),
    ("docs.make_figures",  [PY, "scripts/make_figures.py"]),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="真执行（默认只打印计划）")
    ap.add_argument("--from", dest="from_stage", default=None, help="从该阶段起跑")
    args = ap.parse_args()

    names = [n for n, _ in STAGES]
    start = 0
    if args.from_stage:
        if args.from_stage not in names:
            raise SystemExit(f"未知阶段: {args.from_stage}（可选: {', '.join(names)}）")
        start = names.index(args.from_stage)

    plan = STAGES[start:]
    if not args.run:
        print(f"[run_all] 计划 {len(plan)} 个阶段（未执行；加 --run 真跑）")
        for n, cmd in plan:
            print(f"  {n:24s} {' '.join(cmd[1:])}")
        return

    for n, cmd in plan:
        print(f"[run_all] >>> {n}")
        rc = subprocess.run(cmd).returncode
        if rc != 0:
            raise SystemExit(f"[run_all] 阶段失败: {n}（rc={rc}）——已停在失败阶段")
    print(f"[run_all] 全部 {len(plan)} 个阶段完成。冻结纪律：与 results-frozen-v1 "
          "逐文件比对一致后方可替换 results/。")


if __name__ == "__main__":
    main()
