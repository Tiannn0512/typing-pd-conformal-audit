"""Regression checks for configuration, prediction alignment and isolated execution."""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cp.conformal import (
    WeightedConformal,
    lac_scores,
    predict_sets_split,
    split_conformal_quantile,
)
from cp.metrics import metrics
from features.build_tables import clean_dataset, load_cleaning_config
from models.common import L1_COLS, fit_transfer, load_matrix, load_pooled
from models.train_baseline import gate_decision, load_baseline_config
from runtime import reference_path

spec = importlib.util.spec_from_file_location(
    "reproduction_runner", ROOT / "run_all.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.parametrize("alpha", [-0.1, 0, 1, 1.1, np.nan, np.inf, True, [0.1]])
def test_invalid_alpha_is_rejected(alpha):
    with pytest.raises(ValueError):
        split_conformal_quantile([0.1, 0.2], alpha)
    with pytest.raises(ValueError):
        WeightedConformal([1, 1], [0.1, 0.2], alpha)


@pytest.mark.parametrize("y", [[-1], [0.5], [2], [np.nan], [], [[1]]])
def test_invalid_labels_are_rejected(y):
    with pytest.raises(ValueError):
        lac_scores([[0.8, 0.2]], y)


@pytest.mark.parametrize(
    "probs",
    [[0.8, 0.2], [[1.1, -0.1]], [[0.1, 0.2]], [[np.nan, 0.2]], [[0.1, 0.2, 0.7]]],
)
def test_invalid_probabilities_are_rejected(probs):
    with pytest.raises(ValueError):
        predict_sets_split([0.1, 0.2], probs, 0.1)


@pytest.mark.parametrize("weights", [[1], [1, 1, 1000], [[1, 1]]])
def test_calibration_weight_length_and_shape(weights):
    with pytest.raises(ValueError):
        WeightedConformal(weights, [0.1, 0.2], 0.1)


def test_test_weights_cannot_truncate_predictions():
    fitted = WeightedConformal([1, 1], [0.1, 0.2], 0.1)
    for weights in ([1], [1, 1, 1], [[1, 1]]):
        with pytest.raises(ValueError):
            fitted.predict_sets(weights, [[0.7, 0.3], [0.4, 0.6]])
    with pytest.raises(ValueError):
        metrics([0, 1], [frozenset({0})])


@pytest.mark.parametrize("scores", [[], [[0.1]], [np.nan], [np.inf], [-0.1], [1.1]])
def test_invalid_scores_are_rejected(scores):
    with pytest.raises(ValueError):
        WeightedConformal(np.ones(np.size(scores)), scores, 0.1)


def test_empty_sets_and_infinite_quantiles_are_valid():
    assert predict_sets_split(np.full(30, 0.1), [[0.5, 0.5]], 0.1) == [frozenset()]
    assert predict_sets_split([0.2, 0.7], [[0.5, 0.5]], 0.1) == [frozenset({0, 1})]
    assert metrics([1], [frozenset()])["coverage"] == 0


def test_registered_gate_uses_approved_continuation():
    cfg = load_baseline_config(ROOT / "configs/baseline_mit.yaml")
    table = pd.read_csv(ROOT / "results/baseline_mit.csv")
    summary = {
        name: {"mean_auc_test": float(group["auc_test"].mean())}
        for name, group in table.groupby("model")
    }
    registered = gate_decision(summary, cfg, "registered")
    historical = gate_decision(summary, cfg, "historical")
    assert not registered["pass"]
    assert registered["continue_analysis"] and not registered["enforced"]
    assert not historical["continue_analysis"] and historical["enforced"]
    assert (
        registered["accepted_primary"] == "lr" and registered["amendment"] == "CHG-P1"
    )


def test_baseline_configuration_changes_are_not_ignored(tmp_path):
    cfg = yaml.safe_load((ROOT / "configs/baseline_mit.yaml").read_text())
    cfg["parameters"]["temporary_fraction"] = 0.4
    path = tmp_path / "baseline.yaml"
    path.write_text(yaml.safe_dump(cfg))
    with pytest.raises(ValueError, match="DEC-B3b"):
        load_baseline_config(path)


def test_cleaning_threshold_is_consumed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("data/interim").mkdir(parents=True)
    events = pd.DataFrame(
        {
            "dataset": "tappy",
            "subject": "a",
            "session": "s",
            "keep_flag": True,
            "hold_ms": 100.0,
            "latency_ms": 50.0,
            "flight_ms": 150.0,
        },
        index=range(400),
    )
    events.to_parquet("data/interim/tappy_events.parquet", index=False)
    cfg = load_cleaning_config()
    default, _, _ = clean_dataset("tappy", [], cfg)
    changed = copy.deepcopy(cfg)
    changed["session_rules"]["min_valid_digraphs"] = 500
    filtered, _, _ = clean_dataset("tappy", [], changed)
    assert len(default) == 400 and len(filtered) == 0
    changed["digraph_pool"]["require_keep_flag"] = False
    path = tmp_path / "cleaning.yaml"
    path.write_text(yaml.safe_dump(changed))
    with pytest.raises(ValueError, match="require_keep_flag"):
        load_cleaning_config(path)


def test_canonical_columns_and_unique_subjects(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("data/processed").mkdir(parents=True)
    rows = [
        {
            "dataset": dataset,
            "subject_id": f"{dataset}_{i}",
            "label_pd": i % 2,
            **{c: offset + j for j, c in enumerate(L1_COLS)},
        }
        for offset, dataset in ((0, "mit"), (100, "typd"))
        for i in range(2)
    ]
    frame = pd.DataFrame(rows)
    frame = frame[list(reversed(frame.columns))]
    frame.to_csv("data/processed/subjects.csv", index=False)
    X, y = load_pooled(["mit", "typd"], 1)
    assert np.array_equal(X[0], np.arange(15))
    assert np.array_equal(X[2], 100 + np.arange(15))
    assert np.array_equal(load_matrix("mit", 1)[0], X[:2])
    pd.concat([frame, frame.iloc[:1]]).to_csv(
        "data/processed/subjects.csv", index=False
    )
    with pytest.raises(ValueError, match="unique"):
        load_matrix("mit", 1)


def test_transfer_matches_registered_source_only_fit(tmp_path, monkeypatch):
    rng = np.random.default_rng(19)
    X_s = rng.normal(size=(100, 15))
    y_s = np.tile([0, 1], 50)
    X_t = rng.normal(size=(35, 15)) + 20
    train, calibration = train_test_split(
        np.arange(100), test_size=0.30, random_state=1, stratify=y_s
    )
    scaler = StandardScaler().fit(X_s[train])
    model = LogisticRegression(random_state=42, max_iter=1000).fit(
        scaler.transform(X_s[train]), y_s[train]
    )
    expected = model.predict_proba(scaler.transform(X_t))
    monkeypatch.setenv("TYPING_PD_ARTIFACT_DIR", str(tmp_path / "models"))
    result = fit_transfer(X_s, y_s, X_t)
    np.testing.assert_array_equal(result["train_indices"], train)
    np.testing.assert_allclose(
        result["scaler"].mean_, X_s[train].mean(axis=0), rtol=0, atol=0
    )
    np.testing.assert_allclose(result["probs_te"], expected, rtol=0, atol=0)
    expected_sets = predict_sets_split(
        lac_scores(
            model.predict_proba(scaler.transform(X_s[calibration])), y_s[calibration]
        ),
        expected,
        0.1,
    )
    assert result["sets"] == expected_sets
    artifact = next((tmp_path / "models").rglob("*.npz"))
    with np.load(artifact, allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved["probs_te"], expected)
        assert "coefficients" in saved.files


def test_smoke_calls_registered_pipeline_and_allows_small_calibration(monkeypatch):
    from cp import run_pipeline

    X = np.arange(120, dtype=float).reshape(8, 15)
    y = np.tile([0, 1], 4)
    monkeypatch.setattr(
        run_pipeline, "direction_data", lambda cfg: (X, y, X[:2], y[:2], 1)
    )
    ok, checks = run_pipeline.run_smoke("tappy2mit")
    assert ok and len(checks) == 6


def test_runtime_checks_remain_active_with_optimization():
    command = [
        sys.executable,
        "-O",
        "-c",
        "from runtime import require; require(False, 'registered rule')",
    ]
    import os

    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    assert result.returncode != 0 and "ValueError: registered rule" in result.stderr


def test_pipeline_orders_producer_before_consumer():
    names = [name for name, _ in runner.STAGES]
    assert names.index("feat.build_tables") < names.index("feat.build_features")
    assert (
        "data/interim/final_digraphs.parquet"
        in runner.REQUIRED_INPUTS["feat.build_features"]
    )


def workspace_inputs(tmp_path):
    raw, reference = tmp_path / "raw", tmp_path / "reference"
    raw.mkdir()
    reference.mkdir()
    (raw / "input.txt").write_text("raw input")
    (reference / "answer.csv").write_text("sample,value\na,0.5\n")
    return raw, reference


def test_existing_workspace_is_not_overwritten(tmp_path):
    raw, reference = workspace_inputs(tmp_path)
    workspace, record = runner.prepare_workspace(tmp_path / "run", raw, reference)
    with pytest.raises(FileExistsError):
        runner.prepare_workspace(workspace, raw, reference)
    assert (reference / "answer.csv").read_text() == "sample,value\na,0.5\n"
    assert record["input_hashes"] and record["source_hashes"]


def test_workspace_cannot_overlap_reference(tmp_path):
    raw, reference = workspace_inputs(tmp_path)
    with pytest.raises(ValueError):
        runner.prepare_workspace(reference / "run", raw, reference)


def test_reference_is_separate_from_current_working_directory(tmp_path, monkeypatch):
    _, reference = workspace_inputs(tmp_path)
    monkeypatch.setenv("TYPING_PD_REFERENCE_DIR", str(reference))
    monkeypatch.chdir(tmp_path)
    Path("results").mkdir()
    Path("results/answer.csv").write_text("changed")
    assert reference_path("answer.csv") == reference / "answer.csv"
    with pytest.raises(ValueError):
        reference_path("../raw/input.txt")


def test_comparison_detects_changed_rows(tmp_path):
    raw, reference = workspace_inputs(tmp_path)
    actual = tmp_path / "actual"
    actual.mkdir()
    target = actual / "answer.csv"
    target.write_text("sample,value\na,0.5000000001\n")
    assert runner.compare_tables(actual, reference)[0]["status"] == "PASS"
    target.write_text("sample,value\na,0.6\n")
    assert runner.compare_tables(actual, reference)[0]["status"] == "FAILED"
    target.write_text("sample,value\nb,0.5\n")
    assert runner.compare_tables(actual, reference)[0]["status"] == "FAILED"


def test_stage_runs_in_workspace_and_preserves_reference(tmp_path, monkeypatch):
    raw, reference = workspace_inputs(tmp_path)
    workspace, record = runner.prepare_workspace(tmp_path / "run", raw, reference)
    script = tmp_path / "stage.py"
    script.write_text(
        "from pathlib import Path\nPath('results/answer.csv').write_text('sample,value\\na,0.5\\n')\n"
    )
    runner.execute_plan(
        workspace, record, [("test.stage", [sys.executable, str(script)])]
    )
    assert record["status"] == "PASS"
    assert record["comparisons"] == [{"file": "answer.csv", "status": "PASS"}]
    assert (reference / "answer.csv").read_text() == "sample,value\na,0.5\n"
    assert record["stages"][0]["status"] == "PASS"


def test_stage_failure_is_recorded_before_downstream_work(tmp_path):
    raw, reference = workspace_inputs(tmp_path)
    workspace, record = runner.prepare_workspace(tmp_path / "run", raw, reference)
    script = tmp_path / "fail.py"
    script.write_text("raise SystemExit(7)\n")
    with pytest.raises(RuntimeError):
        runner.execute_plan(
            workspace,
            record,
            [
                ("failed.stage", [sys.executable, str(script)]),
                ("not.run", [sys.executable, str(script)]),
            ],
        )
    stored = json.loads((workspace / "run.json").read_text())
    assert stored["status"] == "FAILED" and len(stored["stages"]) == 1
    assert stored["stages"][0]["returncode"] == 7
    assert stored["ended_at"]


def test_missing_stage_input_is_reported(tmp_path):
    raw, reference = workspace_inputs(tmp_path)
    workspace, record = runner.prepare_workspace(tmp_path / "run", raw, reference)
    with pytest.raises(FileNotFoundError, match="final_digraphs"):
        runner.execute_plan(
            workspace, record, [("feat.build_features", [sys.executable, "unused.py"])]
        )
    assert record["status"] == "FAILED"


def test_input_and_reference_tampering_are_detected(tmp_path):
    raw, reference = workspace_inputs(tmp_path)
    workspace, record = runner.prepare_workspace(tmp_path / "run", raw, reference)
    (workspace / "reference/answer.csv").write_text("changed")
    with pytest.raises(ValueError, match="Reference snapshot"):
        runner.verify_inputs(workspace, record)


def test_all_declared_dependencies_have_an_earlier_producer():
    producers = {
        path: name for name, paths in runner.STAGE_OUTPUTS.items() for path in paths
    }
    names = [name for name, _ in runner.STAGES]
    for stage, inputs in runner.REQUIRED_INPUTS.items():
        for path in inputs:
            assert path in producers
            assert names.index(producers[path]) < names.index(stage), (stage, path)
    assert names.index("feat.build_tables") < names.index("data.qc")


def test_success_without_declared_output_is_a_failure(tmp_path):
    raw, reference = workspace_inputs(tmp_path)
    workspace, record = runner.prepare_workspace(tmp_path / "run", raw, reference)
    script = tmp_path / "empty.py"
    script.write_text("pass\n")
    with pytest.raises(FileNotFoundError, match="power_table.csv"):
        runner.execute_plan(
            workspace, record, [("power.power_sim", [sys.executable, str(script)])]
        )
    assert record["status"] == "FAILED"
    assert record["stages"][0]["status"] == "FAILED"


def test_missing_reference_cannot_be_reported_as_reproduced(tmp_path):
    raw, reference = workspace_inputs(tmp_path)
    workspace, record = runner.prepare_workspace(tmp_path / "run", raw, reference)
    script = tmp_path / "stage.py"
    script.write_text(
        "from pathlib import Path\nPath('results/new.csv').write_text('value\\n1\\n')\n"
    )
    with pytest.raises(ValueError, match="unavailable"):
        runner.execute_plan(
            workspace, record, [("test.stage", [sys.executable, str(script)])]
        )
    assert record["status"] == "FAILED"
    assert record["comparisons"][0]["status"] == "NO_REFERENCE"


def test_resume_requires_an_existing_completed_prefix(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["run_all.py", "--run", "--from", "cp.coverage_audit"]
    )
    with pytest.raises(SystemExit) as exc:
        runner.main()
    assert exc.value.code == 2
    raw, reference = workspace_inputs(tmp_path)
    workspace, record = runner.prepare_workspace(tmp_path / "run", raw, reference)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_all.py",
            "--run",
            "--from",
            "cp.coverage_audit",
            "--output-dir",
            str(workspace),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        runner.main()
    assert exc.value.code == 2


def test_changed_raw_data_prevents_resume(tmp_path):
    raw, reference = workspace_inputs(tmp_path)
    workspace, record = runner.prepare_workspace(tmp_path / "run", raw, reference)
    (raw / "input.txt").write_text("changed")
    with pytest.raises(ValueError, match="Raw inputs changed"):
        runner.verify_inputs(workspace, record)


def test_environment_changes_require_a_new_run(tmp_path):
    raw, reference = workspace_inputs(tmp_path)
    workspace, record = runner.prepare_workspace(tmp_path / "run", raw, reference)
    record["dependencies"]["numpy"] = "different-version"
    with pytest.raises(ValueError, match="environment changed"):
        runner.verify_inputs(workspace, record)
