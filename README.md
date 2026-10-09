# Cross-Dataset Conformal Coverage Audit of PD Typing Classifiers

Code for a pre-registered audit of split-conformal prediction coverage when
keystroke-based Parkinson's disease (PD) classifiers are deployed across
typing datasets.

Keystroke dynamics is an established digital marker for PD screening, and
public datasets have supported a decade of classifier development. Evaluation
of these classifiers is dominated by discrimination metrics such as the AUC.
This study asks a second question: after a classifier and its calibration set
are transported to a new dataset, does its prediction-set coverage still hold
at the nominal level? The audit covers 12 ordered transfer directions between
four public datasets (MIT-CSXPD, Tappy, TyPD/i-PROGNOSIS DS2.5, Online
English), with three pre-specified primary directions under Holm control
(one-sided binomial test, H0: true coverage >= 0.90).

## Main results

- All three primary directions were Incompatible with nominal 0.90 coverage:
  Tappy→MIT 0.598 [95% CI 0.483–0.704], MIT→Tappy 0.850 [0.788–0.899],
  clinical-pool→self-report 0.732 [0.684–0.777].
- Discrimination and coverage did not move together: a LightGBM comparator
  with lower AUC on all 12 directions held higher marginal coverage on 11 of
  them, at the cost of larger prediction sets.
- Marginal totals hid class-conditional failure: PD-conditional coverage
  0.214 (HC 1.000) in Tappy→MIT; the failing class differed across target
  cohorts.
- Coverage recovery was direction-dependent: 9 and 18 target labels restored
  two directions past the 0.80 audit threshold; the worst direction did not
  reach it within a 30% budget. Label-free density-ratio weighting reached
  nominal coverage only by abstaining on 86–100% of subjects.
- Synthetic label flips produced one-sided class-conditional collapse, but no
  tested mechanism reproduced the observed pattern within pre-set tolerances;
  BBSE rejected pure label shift for the worst direction (estimate 0.000 vs
  observed 0.512).

## Repository structure

```
run_all.py              pipeline entry: 23 stages in development order
docs/                   frozen analysis plan (OSF-registered)
01_研究计划/             study proposal versions + analysis freeze protocol
02_查新报告/             novelty scan report
03_可行性分析/           dataset feasibility report
src/data/               dataset parsers, QC, schema validation
src/features/           feature tiers L1-L3, cohort tables
src/models/             baseline gate + 12-direction transfer pipeline
src/cp/                 conformal audit: primary family, class-conditional,
                        remediation, stress tests, BBSE, sensitivity, subgroups
src/power_sim.py        pre-registered power simulation
scripts/                figure and paper-table generation (from frozen CSVs)
results/                frozen result layer (CSV, tag results-frozen-v1)
results/paper_tables/   camera-ready tables, derived programmatically
figures/                publication figures (600 dpi)
reports/                supplementary tables S1-S3
tests/                  unit tests incl. MAPIE 1.5.0 cross-check (1800/1800)
configs/                registered seeds, cleaning rules, feature tiers
logs/                   changelogs, novelty scans, pilot smoke status
PROVENANCE.md           commit chain and governance tags
```

## Installation

Python 3.12, pinned dependencies:

```
pip install -r requirements.txt
```

Raw data is not redistributed. Obtain the four public datasets and place
them under `data/raw/` following `data/raw/DATA_MANIFEST.md` (sources, file
lists, SHA-256 checksums):

| Dataset | Access | Labels |
|---|---|---|
| MIT-CSXPD (PhysioNet nqmitcsxpd 1.0.0) | open | clinical |
| Tappy (PhysioNet tappy 1.0.0) | registration | self-report |
| TyPD / i-PROGNOSIS DS2.5 (Zenodo 2571623) | application | clinical |
| Online English (OSF ew34b) | open | self-report |

## Usage

```
python run_all.py                             # print the 23-stage plan
python run_all.py --run                       # end-to-end (needs data/)
python run_all.py --from cp.coverage_audit    # resume from a stage
```

Stages run in development order: parsing → QC → features → cohort → baseline
gate → 12-direction transfer → conformal audit → class-conditional →
remediation → calibration comparison → stress tests → BBSE → sensitivity →
subgroups → power → tables/figures. Stage commands use module defaults, which
equal the registered settings; module-level asserts reject deviations
(arm lists, doses, strata, prevalence constants). Regenerated outputs must be
diffed against the frozen layer in `results/` before anything is replaced.

Unit tests: `python -m pytest tests/`
MAPIE cross-check: `python scripts/mapie_crosscheck.py`

Result-table mapping: `results/primary_family.csv` → manuscript Table 2,
`results/paper_tables/table6_sensitivity.csv` → Table 3,
`results/cohort_flow.csv` → supplementary Table S1,
`results/transfer_matrix.csv` → supplementary Table S2,
`results/power_table*.csv` → supplementary Table S3.

## Governance

- The analysis plan was frozen and OSF-registered (embargoed; reviewers get
  read access) before any cross-dataset coverage was computed. Development
  tag `v1.0-prereg`.
- Results were frozen at commit `ce26f33` (2026-09-27), tag
  `results-frozen-v1`. Later changes are append-only, recorded in
  `PROVENANCE.md` and `logs/changelog_*.md`.
- The primary model was switched from LightGBM to logistic regression by a
  registered amendment (CHG-P1) after LightGBM failed the pre-specified
  acceptance gate (MIT in-domain, 50 seeds, AUC within 0.75-0.91); the three
  gate runs are kept in `results/baseline_mit_*.csv`.

## Ethics

Retrospective analysis of previously published, de-identified public
datasets; no new human data were collected and no intervention was performed.

## Citation

```bibtex
@article{typingpd2026,
  title  = {Cross-dataset conformal coverage audit of PD typing classifiers
            under deployment shift},
  author = {Tiannn0512, Taylor},
  year   = {2026},
  note   = {In preparation. Pre-registered analysis plan and frozen results
            archived in this repository}
}
```

## License

Code under the MIT License (`LICENSE`). The four source datasets keep their
own terms and are not redistributed here.
