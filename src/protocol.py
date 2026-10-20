"""Effective settings for the registered transfer analyses."""

import yaml
from runtime import config_path, require


def load_seeds():
    settings = yaml.safe_load(config_path("seeds.yaml").read_text(encoding="utf-8"))
    require(isinstance(settings, dict), "Seed configuration must be a mapping")
    seeds = settings.get("split_seeds")
    require(
        isinstance(seeds, list)
        and len(seeds) == 50
        and all(type(seed) is int for seed in seeds)
        and seeds == list(range(1, 51)),
        "The registered split seeds must be integers 1 through 50",
    )
    require(
        type(settings.get("model_seed")) is int and settings["model_seed"] == 42,
        "The registered model seed must be 42",
    )
    return settings


SEEDS = load_seeds()
MODEL_SEED = SEEDS["model_seed"]
SEED = SEEDS["split_seeds"][0]
ALPHA = 0.10
FAMILY_WISE = 0.10
COVERAGE_H0 = 0.90
COVERAGE_LO = 0.80
CALIBRATION_FRACTION = 0.30
CAP = yaml.safe_load(config_path("feature_tiers.yaml").read_text(encoding="utf-8"))[
    "dataset_max_tier"
]
require(
    CAP == {"mit": 3, "tappy": 2, "typd": 1, "oe": 3},
    "Feature caps differ from the registered plan",
)
DIRECTIONS = [
    {"direction": "tappy2mit", "sources": ["tappy"], "target": "mit"},
    {"direction": "mit2tappy", "sources": ["mit"], "target": "tappy"},
    {
        "direction": "gold_merged2self",
        "sources": ["mit", "typd"],
        "target": "merged_self",
    },
]
