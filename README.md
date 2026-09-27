# Conformal Coverage Audit for Parkinson's Disease Typing Detection

**A pre-registered, four-dataset audit of split-conformal prediction coverage under cross-dataset deployment of keystroke-based Parkinson's disease (PD) classifiers.**

Manuscript: `reports/Typing_PD(V1.0).docx` (English; `reports/Typing_PD(V1.0)_zh.docx` is an internal Chinese mirror) — in preparation for submission to *Journal of Medical Systems*.

## Purpose of this repository

This is the **public timestamp archive** for the study. It exists to establish a verifiable, dated public record of the frozen analysis plan, frozen results, and manuscript draft, independent of peer review.

- **Frozen analysis plan**: `docs/analysis_plan_v1.md` + `01_研究计划/分析冻结协议_v1.md` (pre-registered on OSF, tag `v1.0-prereg`, before any cross-dataset coverage was computed).
- **Frozen results**: everything under `results/` is the frozen result layer (tag `results-frozen-v1` in the development repository, commit `ce26f33`, 2026-09-27). Post-freeze changes to results follow a new-round protocol with a change log — they are never silently overwritten.
- **Provenance**: `logs/` contains per-phase change logs, review-gate records, and handoff notes; `TODO_0925.md` is the full execution ledger with per-task evidence.

## Headline findings (from the frozen result layer)

- All three pre-registered primary transfer directions were **Incompatible** with the nominal 0.90 coverage level under family-wise (Holm) control: Tappy→MIT 0.598 [95% CI 0.483–0.704], MIT→Tappy 0.850 [0.788–0.899], clinical-pool→self-report 0.732 [0.684–0.777].
- Marginal totals concealed class-conditional collapse: PD-conditional coverage 0.214 in Tappy→MIT (healthy controls 1.000).
- Coverage degradation was **score-dependent**: a LightGBM comparator with lower AUC maintained 0.925–1.000 class-conditional coverage in every primary direction — discrimination and coverage behave as distinct reliability dimensions.
- Recovery costs ranged from 9–18 target labels to not-achieved-within-30%; label-free density-ratio weighting attained nominal coverage only by abstaining on 86–100% of subjects.
- Prevalence re-matching and label corruption did not reproduce the observed phenotype within pre-specified tolerances; the feature-space shift itself remains an uneliminated factor (no causal identification claimed).

## Repository map

```
00_README.md            project index (Chinese, internal)
README.md               this file (public)
TODO_0925.md            execution ledger (pre-registration of workflow, per-task evidence)
01_研究计划/             research proposal + analysis freeze document
02_查新报告/             novelty scan report
03_可行性分析/           data feasibility report
docs/                   frozen analysis plan (analysis_plan_v1.md)
configs/                registered seeds, key-hand mapping, feature tiers
src/cp/                 audit pipeline (primary family, class-conditional, remediation,
                        stress tests, BBSE validation, subgroup audit, sensitivity)
src/models/             transfer baseline pipeline
scripts/                figure and paper-table generation (derive all numbers from frozen CSVs)
results/                frozen aggregate result tables (CSV; no subject-level data)
results/paper_tables/   camera-ready tables derived programmatically from frozen results
figures/                publication figures (600 dpi, no in-image titles)
reports/                manuscript (Typing_PD(V1.0).docx) and internal Chinese mirror
logs/                   change logs, review-gate records, handoffs
tests/                  unit tests incl. conformal implementation cross-checks (MAPIE 1.5.0)
```

## Data availability

The study uses four **public** datasets; **no data files are redistributed in this repository** (only the manifest with sources and SHA256 checksums, `data/raw/DATA_MANIFEST.md`):

- MIT-CSXPD — neuroQWERTY release (clinical labels)
- Tappy Keplar (Tappy User Keystroke) — public repository, registration required (self-report labels)
- TyPD / i-PROGNOSIS DS2.5 — application-based release (clinical labels)
- Online English — web-based typing dataset accompanying its publication (self-report labels)

The frozen cohort construction with step-by-step inclusion/exclusion counts is in the ledger and result tables.

## Reproducibility

- Python stack pinned in `requirements.txt` (LightGBM 4.7.0, MAPIE 1.5.0, scikit-learn 1.9.1, pandas 3.0.6, numpy 2.5.3).
- Every figure (`scripts/make_figures.py`) and every paper table (`scripts/make_tables.py`) is derived programmatically from the frozen CSVs — no hand-copied numbers.
- The split-CP implementation is verified pointwise against MAPIE 1.5.0 (1800/1800 cells) and passes the unit-test suite in `tests/`.

## Disclosure

AI agent assistance (ZCode CLI accessing GLM models via API) was used under human direction for pipeline execution, code generation, internal consistency auditing, and drafting of the manuscript from the frozen results; all outputs were verified by the author, who is accountable for all content. This is disclosed in the manuscript (Methods and Declarations) per journal policy.

## License & contact

© 2026 the author. Contents are provided for timestamping, transparency, and peer review; reuse requires permission until a license is finalized with the published article. Contact: [corresponding author e-mail — see manuscript title page].
