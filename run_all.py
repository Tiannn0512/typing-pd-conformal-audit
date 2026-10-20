#!/usr/bin/env python
"""Run the registered analysis in a separate workspace and compare reference tables."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent
PY = sys.executable

STAGES = [
    ("data.parse_mit", [PY, "src/data/parse_mit.py"]),
    ("data.parse_oe", [PY, "src/data/parse_oe.py"]),
    ("data.parse_tappy", [PY, "src/data/parse_tappy.py"]),
    ("data.parse_tappy_users", [PY, "src/data/parse_tappy_users.py"]),
    ("data.parse_typd", [PY, "src/data/parse_typd.py"]),
    ("data.validate_schema", [PY, "src/data/validate_schema.py", "--all"]),
    ("feat.build_tables", [PY, "src/features/build_tables.py"]),
    ("feat.build_features", [PY, "src/features/build_features.py"]),
    ("data.qc", [PY, "src/data/qc.py"]),
    ("model.train_baseline", [PY, "src/models/train_baseline.py"]),
    ("model.run_transfer", [PY, "src/models/run_transfer.py"]),
    ("cp.coverage_audit", [PY, "src/cp/coverage_audit.py"]),
    (
        "cp.class_conditional",
        [PY, "src/cp/class_conditional.py", "--primary-directions"],
    ),
    ("cp.remediate", [PY, "src/cp/remediate.py"]),
    ("cp.calibration_compare", [PY, "src/cp/calibration_compare.py"]),
    ("cp.stress_test_a", [PY, "src/cp/stress_test_a.py"]),
    ("cp.stress_three_arm", [PY, "src/cp/stress_three_arm.py"]),
    ("cp.bbse_synthetic", [PY, "src/cp/bbse_synthetic.py"]),
    ("cp.run_sensitivity", [PY, "src/cp/run_sensitivity.py", "--all"]),
    ("cp.subgroup_audit", [PY, "src/cp/subgroup_audit.py"]),
    ("power.power_sim", [PY, "src/power_sim.py"]),
    ("docs.make_tables", [PY, "scripts/make_tables.py"]),
    ("docs.make_figures", [PY, "scripts/make_figures.py"]),
]

STAGE_OUTPUTS = {
    "data.parse_mit": ["data/interim/mit_digraph.parquet"],
    "data.parse_oe": ["data/interim/oe_events.parquet", "data/interim/oe_subjects.csv"],
    "data.parse_tappy": ["data/interim/tappy_events.parquet"],
    "data.parse_tappy_users": ["data/interim/tappy_users.csv"],
    "data.parse_typd": [
        "data/interim/typd_events.parquet",
        "data/interim/typd_clinical.csv",
    ],
    "data.validate_schema": ["data/interim/parse_reports/schema_validation.json"],
    "feat.build_tables": [
        "data/interim/final_digraphs.parquet",
        "data/processed/subjects.csv",
        "data/processed/sessions.parquet",
        "results/cohort_flow.csv",
    ],
    "feat.build_features": ["data/processed/subjects_l2l3.csv"],
    "data.qc": ["results/qc_report.md"],
    "model.train_baseline": ["results/baseline_mit.csv"],
    "model.run_transfer": ["results/transfer_matrix.csv"],
    "cp.coverage_audit": ["results/primary_family.csv"],
    "cp.class_conditional": ["results/class_conditional_coverage.csv"],
    "cp.remediate": ["results/recovery_cost_table.csv"],
    "cp.calibration_compare": ["results/calibration_comparison.csv"],
    "cp.stress_test_a": ["results/stress_test_a.csv"],
    "cp.stress_three_arm": ["results/three_arm_stress_test.csv"],
    "cp.bbse_synthetic": [
        "results/bbse_shift_validation.csv",
        "results/bbse_real_pairs_descriptive.csv",
    ],
    "cp.run_sensitivity": [
        "results/sensitivity_batch.csv",
        "results/sensitivity_tier_covariate.csv",
    ],
    "cp.subgroup_audit": [
        "results/subgroup_coverage_audit.csv",
        "results/subgroup_strata_availability.csv",
    ],
    "power.power_sim": ["results/power_table.csv"],
    "docs.make_tables": [
        f"results/paper_tables/{name}.csv"
        for name in (
            "table1_cohort_flow",
            "table2_primary_family",
            "table3_class_conditional",
            "table4_recovery_cost",
            "table5_three_arm",
            "table6_sensitivity",
        )
    ],
    "docs.make_figures": [
        "figures/fig1_primary_forest.png",
        "figures/fig4_class_conditional.png",
        "figures/fig3_decoupling.png",
        "figures/fig5_recovery_cost.png",
        "figures/fig6_weighted_cp_tradeoff.png",
        "figures/fig7_stress_tests.png",
        "figures/fig2_transfer_heatmap.png",
    ],
}
PARSED_EVENTS = [
    STAGE_OUTPUTS[name][0]
    for name in (
        "data.parse_mit",
        "data.parse_oe",
        "data.parse_tappy",
        "data.parse_typd",
    )
]
REQUIRED_INPUTS = {
    "data.validate_schema": PARSED_EVENTS,
    "feat.build_tables": PARSED_EVENTS
    + [
        "data/interim/oe_subjects.csv",
        "data/interim/tappy_users.csv",
        "data/interim/typd_clinical.csv",
    ],
    "feat.build_features": ["data/interim/final_digraphs.parquet"],
    "data.qc": [
        "data/processed/subjects.csv",
        "data/processed/sessions.parquet",
        "results/cohort_flow.csv",
    ],
    "model.train_baseline": ["data/processed/subjects.csv"],
    "model.run_transfer": [
        "data/processed/subjects.csv",
        "data/processed/subjects_l2l3.csv",
    ],
    **{
        name: ["data/processed/subjects.csv", "data/processed/subjects_l2l3.csv"]
        for name, _ in STAGES
        if name.startswith("cp.")
    },
    "docs.make_tables": [
        "results/cohort_flow.csv",
        "results/primary_family.csv",
        "results/class_conditional_coverage.csv",
        "results/recovery_cost_table.csv",
        "results/three_arm_stress_test.csv",
        "results/sensitivity_batch.csv",
    ],
    "docs.make_figures": [
        "results/primary_family.csv",
        "results/class_conditional_coverage.csv",
        "results/transfer_matrix.csv",
        "results/recovery_cost_table.csv",
        "results/calibration_comparison.csv",
        "results/stress_test_a.csv",
        "results/three_arm_stress_test.csv",
    ],
}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_hashes(root):
    return {
        p.relative_to(root).as_posix(): file_hash(p)
        for p in sorted(root.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    }


def dependency_versions():
    return {
        distribution.metadata["Name"]: distribution.version
        for distribution in importlib.metadata.distributions()
        if distribution.metadata["Name"]
    }


def source_hashes():
    paths = [Path("run_all.py"), Path("requirements.txt")]
    for folder in ("src", "scripts", "configs"):
        paths += [
            p.relative_to(REPO_ROOT)
            for p in (REPO_ROOT / folder).rglob("*")
            if p.is_file() and p.suffix in (".py", ".yaml")
        ]
    return {str(p): file_hash(REPO_ROOT / p) for p in sorted(paths)}


def save_record(workspace, record):
    temporary = workspace / "run.json.tmp"
    temporary.write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    temporary.replace(workspace / "run.json")


def prepare_workspace(output_dir, data_dir, reference_dir):
    output_dir, data_dir, reference_dir = map(
        lambda p: Path(p).resolve(), (output_dir, data_dir, reference_dir)
    )
    if not data_dir.is_dir() or not reference_dir.is_dir():
        raise ValueError("Raw-data and reference directories must exist")
    if output_dir == REPO_ROOT or REPO_ROOT.is_relative_to(output_dir):
        raise ValueError("The workspace must not contain the repository")
    for source in (data_dir, reference_dir, REPO_ROOT / "src", REPO_ROOT / "configs"):
        if (
            output_dir == source
            or output_dir.is_relative_to(source)
            or source.is_relative_to(output_dir)
        ):
            raise ValueError(
                "The workspace must be separate from inputs, code and reference results"
            )
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "data").mkdir()
    # Keep parser paths unchanged inside the workspace; no intermediate data is reused.
    try:
        (output_dir / "data/raw").symlink_to(data_dir, target_is_directory=True)
    except OSError:
        shutil.copytree(data_dir, output_dir / "data/raw")
    shutil.copytree(REPO_ROOT / "configs", output_dir / "configs")
    shutil.copytree(reference_dir, output_dir / "reference")
    for name in ("results", "figures", "logs"):
        (output_dir / name).mkdir()
    record = {
        "status": "RUNNING",
        "started_at": stamp(),
        "ended_at": None,
        "raw_data_dir": str(data_dir),
        "reference_dir": str(reference_dir),
        "source_hashes": source_hashes(),
        "input_hashes": tree_hashes(data_dir),
        "reference_hashes": tree_hashes(output_dir / "reference"),
        "config_hashes": tree_hashes(output_dir / "configs"),
        "python": sys.version,
        "platform": platform.platform(),
        "dependencies": dependency_versions(),
        "stages": [],
    }
    save_record(output_dir, record)
    return output_dir, record


def compare_tables(actual_dir, reference_dir, atol=1e-9):
    if not math.isfinite(atol) or atol < 0:
        raise ValueError("Comparison tolerance must be finite and nonnegative")
    comparisons = []
    for path in sorted(actual_dir.rglob("*.csv")):
        relative = path.relative_to(actual_dir)
        reference = reference_dir / relative
        if not reference.is_file():
            comparisons.append({"file": relative.as_posix(), "status": "NO_REFERENCE"})
            continue
        with (
            path.open(encoding="utf-8", newline="") as a,
            reference.open(encoding="utf-8", newline="") as b,
        ):
            actual_rows, expected_rows = list(csv.reader(a)), list(csv.reader(b))
        equal = (
            len(actual_rows) == len(expected_rows)
            and bool(actual_rows)
            and actual_rows[0] == expected_rows[0]
        )
        if equal:
            for actual_row, expected_row in zip(actual_rows[1:], expected_rows[1:]):
                if len(actual_row) != len(expected_row):
                    equal = False
                    break
                for actual, expected in zip(actual_row, expected_row):
                    if actual == expected:
                        continue
                    try:
                        x, y = float(actual), float(expected)
                        match = (
                            (math.isnan(x) and math.isnan(y))
                            or x == y
                            or abs(x - y) <= atol
                        )
                    except ValueError:
                        match = False
                    if not match:
                        equal = False
                        break
                if not equal:
                    break
        comparisons.append(
            {"file": relative.as_posix(), "status": "PASS" if equal else "FAILED"}
        )
    return comparisons


def verify_inputs(workspace, record):
    if (
        sys.version != record["python"]
        or dependency_versions() != record["dependencies"]
    ):
        raise ValueError("The Python environment changed; start a new run")
    if source_hashes() != record["source_hashes"]:
        raise ValueError(
            "Analysis code or source configuration changed during this run"
        )
    if tree_hashes(workspace / "configs") != record["config_hashes"]:
        raise ValueError("Workspace configuration changed during this run")
    if tree_hashes(Path(record["raw_data_dir"])) != record["input_hashes"]:
        raise ValueError("Raw inputs changed during this run")
    if tree_hashes(workspace / "data/raw") != record["input_hashes"]:
        raise ValueError("Workspace raw inputs changed during this run")
    if tree_hashes(workspace / "reference") != record["reference_hashes"]:
        raise ValueError("Reference snapshot changed during this run")


def execute_plan(workspace, record, plan, atol=1e-9):
    environment = os.environ.copy()
    environment["PYTHONPATH"] = (
        str(REPO_ROOT / "src") + os.pathsep + environment.get("PYTHONPATH", "")
    )
    environment["TYPING_PD_REFERENCE_DIR"] = str(workspace / "reference")
    environment["TYPING_PD_CONFIG_DIR"] = str(workspace / "configs")
    environment["TYPING_PD_ARTIFACT_DIR"] = str(workspace / "models")
    record.update(status="RUNNING", ended_at=None, comparison_atol=atol)
    try:
        verify_inputs(workspace, record)
        for name, command in plan:
            entry = {"name": name, "started_at": stamp(), "status": "RUNNING"}
            record["stages"].append(entry)
            save_record(workspace, record)
            for relative in REQUIRED_INPUTS.get(name, []):
                if not (workspace / relative).is_file():
                    raise FileNotFoundError(f"{name} requires {relative}")
            environment["TYPING_PD_STAGE"] = name
            absolute_command = [command[0], str(REPO_ROOT / command[1]), *command[2:]]
            print(f"[run_all] >>> {name}", flush=True)
            with (workspace / "logs" / f"{name}.log").open(
                "w", encoding="utf-8"
            ) as log:
                completed = subprocess.run(
                    absolute_command,
                    cwd=workspace,
                    env=environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
            entry.update(
                ended_at=stamp(),
                returncode=completed.returncode,
                status="PASS" if completed.returncode == 0 else "FAILED",
            )
            if completed.returncode == 0:
                for relative in STAGE_OUTPUTS.get(name, []):
                    if not (workspace / relative).is_file():
                        entry["status"] = "FAILED"
                        raise FileNotFoundError(f"{name} did not produce {relative}")
            save_record(workspace, record)
            if completed.returncode:
                raise RuntimeError(
                    f"{name} failed; see {workspace / 'logs' / (name + '.log')}"
                )
        verify_inputs(workspace, record)
        comparisons = compare_tables(
            workspace / "results", workspace / "reference", atol
        )
        record["comparisons"] = comparisons
        if any(row["status"] != "PASS" for row in comparisons):
            raise ValueError(
                "Reference comparisons failed or are unavailable; inspect run.json"
            )
        record["status"] = "PASS"
    except (Exception, KeyboardInterrupt) as exc:
        record.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
        if record["stages"] and record["stages"][-1]["status"] == "RUNNING":
            record["stages"][-1].update(status="FAILED", ended_at=stamp())
        raise
    finally:
        record["ended_at"] = stamp()
        record["output_hashes"] = tree_hashes(workspace / "results")
        save_record(workspace, record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run", action="store_true", help="Execute the plan in a separate workspace"
    )
    parser.add_argument(
        "--from", dest="from_stage", choices=[name for name, _ in STAGES]
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=REPO_ROOT / "data/raw",
        help="Prepared raw-data directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="New workspace, or the existing workspace when resuming",
    )
    parser.add_argument("--reference-dir", type=Path, default=REPO_ROOT / "results")
    parser.add_argument(
        "--atol",
        type=float,
        default=1e-9,
        help="Absolute tolerance for numeric CSV comparisons",
    )
    args = parser.parse_args()
    if not math.isfinite(args.atol) or args.atol < 0:
        parser.error("--atol must be finite and nonnegative")
    names = [name for name, _ in STAGES]
    start = names.index(args.from_stage) if args.from_stage else 0
    plan = STAGES[start:]
    if not args.run:
        print(f"[run_all] {len(plan)} stages; add --run to execute")
        for name, command in plan:
            print(f"  {name:24s} {' '.join(command[1:])}")
        return
    if args.from_stage:
        if not args.output_dir:
            parser.error(
                "Resuming requires --output-dir pointing to an existing workspace"
            )
        workspace = args.output_dir.resolve()
        record = json.loads((workspace / "run.json").read_text(encoding="utf-8"))
        completed = {s["name"] for s in record["stages"] if s["status"] == "PASS"}
        if any(name not in completed for name in names[:start]):
            parser.error("Earlier stages have not completed in this workspace")
        record.setdefault("resume_history", []).append(
            {
                "resumed_at": stamp(),
                "from_stage": args.from_stage,
                "previous_status": record["status"],
                "previous_stages": record["stages"],
                "previous_error": record.get("error"),
            }
        )
        record["stages"] = [s for s in record["stages"] if s["name"] in names[:start]]
        record.pop("error", None)
    else:
        output = args.output_dir or REPO_ROOT / "runs" / datetime.now(
            timezone.utc
        ).strftime("%Y%m%dT%H%M%S.%fZ")
        workspace, record = prepare_workspace(output, args.data_dir, args.reference_dir)
    execute_plan(workspace, record, plan, args.atol)
    print(f"[run_all] Results and comparison report: {workspace}")


if __name__ == "__main__":
    main()
