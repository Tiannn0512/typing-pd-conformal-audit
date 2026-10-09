# typing-pd-conformal-audit

Pre-registered audit of split-conformal prediction coverage under cross-dataset
deployment of keystroke-based Parkinson's disease classifiers.

Four public typing datasets (MIT-CSXPD, Tappy, TyPD/i-PROGNOSIS DS2.5, Online
English) give 12 ordered transfer directions, of which three pre-specified
primary directions carry confirmatory one-sided binomial tests (H0: true
coverage >= 0.90) under Holm control. The audit measures marginal and
class-conditional coverage, prediction-set efficiency, and the target-label
budget required to restore coverage.

## Repository layout

```
run_all.py              full pipeline entry (23 stages; --run to execute,
                        --from STAGE to resume; stops at first failure)
docs/                   frozen analysis plan (pre-registered on OSF)
01_研究计划/             study proposal versions + analysis freeze protocol
02_查新报告/             novelty scan report
03_可行性分析/           dataset feasibility report
src/data/               dataset parsers, QC, schema validation
src/features/           feature tiers L1-L3, cohort tables
src/models/             baseline gate + 12-direction transfer pipeline
src/cp/                 conformal audit: primary family, class-conditional,
                        remediation, stress tests, BBSE, sensitivity, subgroups
src/power_sim.py        pre-registered power simulation
scripts/                figures and paper tables, derived from frozen CSVs
results/                frozen result layer (CSV; tag results-frozen-v1)
results/paper_tables/   camera-ready tables, derived programmatically
figures/                publication figures (600 dpi)
reports/                supplementary tables S1-S3 (cleaning attrition,
                        12-direction audit matrix, power analysis)
tests/                  unit tests incl. MAPIE 1.5.0 cross-check (1800/1800)
configs/                registered seeds, cleaning rules, feature tiers
logs/                   changelogs, novelty scans, pilot smoke status
PROVENANCE.md           development commit chain and governance tags
TODO_0925.md            execution checklist (Chinese)
00_README.md            project overview (Chinese)
```

## Prerequisites

- Python 3.12 with pinned versions in `requirements.txt`
  (scikit-learn 1.9.1, LightGBM 4.7.0, MAPIE 1.5.0).
- Raw data is NOT redistributed. Place the four public datasets under
  `data/raw/` per `data/raw/DATA_MANIFEST.md` (sources and SHA-256 checksums).
  Tappy requires registration; TyPD requires an application.

## Running

```
python run_all.py                # print the 23-stage plan
python run_all.py --run          # end-to-end (data must be in place)
python run_all.py --from cp.coverage_audit   # resume from a stage
```

Each stage invokes the module with its default arguments, which equal the
registered analysis settings; module-level asserts reject deviations from the
pre-registered protocol (arm lists, doses, strata, prevalence constants).
Regenerated outputs must be diffed against the frozen layer in `results/`
before replacing anything — the frozen layer is only replaced after a logged
change, never silently.

Unit tests: `python -m pytest tests/`
MAPIE cross-check: `python scripts/mapie_crosscheck.py`

## Governance

- The analysis plan was frozen and registered (OSF embargo, read access for
  reviewers) before any cross-dataset coverage was computed; development tag
  `v1.0-prereg`.
- Results were frozen at commit `ce26f33` (2026-09-27), tag `results-frozen-v1`.
  Later changes are append-only and recorded in `PROVENANCE.md` and
  `logs/changelog_*.md`.
- The primary model was switched from LightGBM to logistic regression by a
  registered protocol amendment (CHG-P1) after LightGBM failed the
  pre-specified acceptance gate (MIT in-domain, 50 seeds, AUC within
  0.75-0.91); all three gate runs are kept under `results/baseline_mit_*.csv`.

## License

Code under the MIT License (`LICENSE`). The four source datasets keep their
own terms and are not redistributed here.
