"""Runtime checks and reference paths for the registered analyses."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def require(condition, message="Analysis invariant failed"):
    if not condition:
        raise ValueError(message)


def reference_path(name):
    root = Path(
        os.environ.get("TYPING_PD_REFERENCE_DIR", REPO_ROOT / "results")
    ).resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Reference path must remain inside the reference directory")
    if not path.is_file():
        raise FileNotFoundError(f"Reference result is missing: {path}")
    return path


def config_path(name):
    return Path(os.environ.get("TYPING_PD_CONFIG_DIR", REPO_ROOT / "configs")) / name
