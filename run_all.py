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
]

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="execute (default: print plan only)")
    ap.add_argument("--from", dest="from_stage", default=None, help="start from this stage")
    args = ap.parse_args()

    names = [n for n, _ in STAGES]
    start = 0
    if args.from_stage:
        if args.from_stage not in names:
            raise SystemExit(f"unknown stage: {args.from_stage} (valid: {', '.join(names)})")
        start = names.index(args.from_stage)

    plan = STAGES[start:]
    if not args.run:
        print(f"[run_all] {len(plan)} stages planned (not executed; add --run)")
        for n, cmd in plan:
            print(f"  {n:24s} {' '.join(cmd[1:])}")
        return

    for n, cmd in plan:
        print(f"[run_all] >>> {n}")
        rc = subprocess.run(cmd).returncode
        if rc != 0:
            raise SystemExit(f"[run_all] stage failed: {n} (rc={rc}) -- stopping")
    print(f"[run_all] all {len(plan)} stages done.")

if __name__ == "__main__":
    main()
