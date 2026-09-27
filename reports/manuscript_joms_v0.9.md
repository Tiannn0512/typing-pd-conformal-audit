# Score-Dependent Conformal Coverage Under Cross-Dataset Deployment of Parkinson's Disease Typing Classifiers: A Pre-Registered Four-Dataset Audit

**Manuscript draft v1.0-rev (Journal of Medical Systems — Research article, main text ≤ 4,000 words)**
2026-09-27 ｜ Revision round 1 (three-reviewer feedback applied) ｜ Results source: frozen tag `results-frozen-v1`

> **Title page (author to complete before submission):** Author: Taylor [Given name, Family name]; Affiliation: [Department, Institution, City, Country]; ORCID: [__]; Corresponding email: [__]. CRediT roles: [to assign].

**Keywords:** conformal prediction; Parkinson's disease; keystroke dynamics; coverage audit; cross-dataset deployment; clinical decision support

---

## Abstract

Background: Conformal prediction (CP) provides distribution-free prediction sets with guaranteed marginal coverage under exchangeability. In keystroke-based Parkinson's disease (PD) detection, cross-dataset deployment degrades discrimination, but the fate of the coverage guarantee had not been audited. Methods: Under a pre-registered protocol, we audited split-CP coverage (α = 0.10; standard split-conformal scores; logistic-regression reference model) when classifiers trained on one public keystroke dataset are deployed on another, across four public datasets (frozen cohort: 475 subjects). The pre-registered primary family covered three high-power transfer directions with Holm correction. PD/HC class-conditional coverage was a pre-specified safety diagnostic. Recovery (target-domain calibration budgets) and attribution (prevalence-resampling and label-flip stress tests against pre-specified practical tolerances) were pre-registered secondary analyses. Results: All three primary directions were Incompatible — a pre-registered audit verdict of statistical incompatibility with the nominal 0.90 level, not a clinical determination (family-controlled): Tappy→MIT 0.598 [95% CI 0.483–0.704], MIT→Tappy 0.850 [0.788–0.899], clinical-pool→self-report 0.732 [0.684–0.777]. Marginal totals concealed severe class asymmetry (PD-conditional coverage 0.214 in Tappy→MIT; HC 1.000). Coverage degradation was score-dependent: a LightGBM comparator with lower discrimination maintained 0.925–1.000 class-conditional coverage in every primary direction. Recovery required 9–18 target labels (5% budgets) in two directions but was not achieved within a 30% budget in Tappy→MIT by the CI criterion; label-free weighting achieved coverage only by abstaining on 86–100% of subjects. Prevalence re-matching and label corruption, alone or combined, did not reproduce the observed phenotype. Conclusions: Discrimination and coverage behave as distinct reliability dimensions under deployment shift; deployment reporting should include coverage audits and class-conditional diagnostics alongside AUC.

---

## 1. Introduction

Keystroke dynamics have been proposed as a scalable digital-biomarker candidate for Parkinson's disease (PD) screening, and public datasets have supported a decade of classifier development evaluated almost exclusively by discrimination — typically AUC under cross-dataset transfer, where degradation is well documented [4]. A deployed screening system must deliver a second property: calibrated uncertainty. Coverage is the promised rate at which the system's prediction sets contain the true diagnosis; when coverage fails, the system is miscalibrated — worst of all when it outputs a single confident label that is wrong, which is precisely the case a triage workflow cannot afford. Conformal prediction (CP) promises such calibration: under exchangeability, split CP covers the true label with probability at least 1−α regardless of the underlying model [5,6]. Deployment across datasets breaks exchangeability, and the behavior of CP coverage under realistic clinical data shift has been studied mostly in theory or outside medicine [7–10]. To our knowledge, this is the first systematic empirical audit of conformal prediction coverage across publicly available Parkinson's keystroke datasets.

This audit characterizes whether discrimination degradation and coverage degradation exhibit non-identical patterns across deployment shifts (pre-registered hypothesis H1). We report three lines of pre-registered evidence that they do: the primary-family coverage verdicts are uniformly negative while discrimination remains moderate; a comparator model with lower discrimination exhibits higher coverage, so coverage failure is score-dependent rather than a property of the task shift alone; and controlled label manipulations that reproduce class-conditional collapse in form do not reproduce the observed phenotype in magnitude — prevalence and noise alone are insufficient, pointing to the feature-space shift itself. This audit evaluates research-grade classifiers on public datasets; it establishes no clinical screening validity, and the models studied are not validated screening devices. We report the work as a mapping-reliability audit rather than a failure claim: the pre-registered verdict vocabulary asserts statistical compatibility with a pre-specified operational audit threshold, not clinical failure, and primary outcomes were not conditioned on observing degradation.

The study contributes: (i) a pre-registered, embargoed systematic audit of CP coverage across four public PD keystroke datasets, with a frozen cohort and family-wise controlled primary endpoints (novelty claim stated once, Introduction); (ii) a coverage–discrimination decoupling map across all 12 ordered transfer directions and two score functions; (iii) in-the-wild quantification of heterogeneous label sources (clinical vs self-report) on coverage, with controlled-shift stress tests; and (iv) an open audit toolkit (three-tier feature system, coverage-restoration unit tests including an independent oracle for weighted CP, pre-registered protocol, and a coverage-to-workflow mapping: singleton = auto-pass, doubleton = manual review, full set = system rejection).

## 2. Methods

### 2.1 Data and cohorts
Four public datasets were used: MIT-CSXPD (clinical gold standard), Tappy Keplar (self-report, bring-your-own-device), TyPD (clinical, i-PROGNOSIS), and Online English (self-report, web-based). Cleaning rules were pre-registered and label-blind (seven steps; session validity ≥ 100 digraphs; person eligibility ≥ 300 valid digraphs). The frozen cohort comprised 475 subjects (PD 270 / HC 205): MIT 82 (42/40), Tappy 173 (133/40), TyPD 27 (12/15), and Online English 193 (83/110) (Table 1). PD status was defined by clinical diagnosis fields (MIT, TyPD) or self-report fields (Tappy, OE). Three Tappy participants reporting tremor without PD diagnosis were excluded from the primary analysis; dual re-inclusion is reported as sensitivity.

This study used exclusively de-identified public datasets released for research use; no new human data were collected and no intervention occurred. We report per the TRIPOD+AI statement [14]; the completed checklist accompanies the submission as supplementary material. The analysis plan was pre-registered on the Open Science Framework before any cross-dataset coverage was computed (2-year embargo; frozen plan v1, tag `v1.0-prereg`; access during embargo on request). AI agent assistance (ZCode CLI with GLM models) was used under human direction for pipeline execution, code generation, and internal consistency auditing; the author designed the study, verified all outputs, and is accountable for all content, including citations. [Tool version and usage dates to be completed at submission.]

### 2.2 Features and models
Person-level features aggregate all valid digraphs of a person (one subject = one conformal observation). Three pre-registered tiers — L1: hold/latency/flight distribution summaries (15 features, all datasets); L2: hand-conditional summaries (MIT/Tappy/OE); L3: digraph-transition features (MIT/OE) — with the transfer tier fixed at the minimum of the chain's dataset caps and recorded as an audit covariate. The effective primary reference model was L2-regularized logistic regression (amendment CHG-P1: the pre-registered LightGBM failed a pre-declared in-domain gate in three documented runs and is reported as comparator with shallow-tree settings). All hyperparameters were fixed before target data were accessed; target datasets were never used for model selection.

### 2.3 Conformal procedures
Split CP used LAC scores (1 − true-class probability), a stratified 30% source calibration split (single confirmatory seed = 1, the first registered seed; 50-seed summaries are descriptive), α = 0.10, and the finite-sample order-statistic quantile at level ⌈(n+1)(1−α)⌉. Elements per procedure — predictor: source-trained classifier; score: LAC; calibration: the above split and quantile; guarantee target: marginal 1−α coverage on the target cohort. Pre-specified remediation arms: target-domain recalibration at 0/5/10/20/30% labeled budgets (class-stratified single draw; test on the complement); weighted CP under estimated density ratios (domain-classifier odds, pooled p99 truncation; Tibshirani et al. eq. (8) direct form [7], verified against an independent oracle; guarantee target: covariate-shift-weighted marginal 1−α — noting that truncation voids the formal guarantee, so this arm is reported as a practical intervention); and protocol-conditional recalibration (guarantee target: protocol-group-conditional 1−α). The split-CP implementation matches MAPIE 1.5.0 pointwise (1800/1800) and passes 18 synthetic tests.

### 2.4 Outcomes and verdicts
The pre-registered primary family was three high-power directions × α = 0.10 × marginal coverage — Tappy→MIT, MIT→Tappy, and clinical-pool (MIT+TyPD) → self-report (Tappy+OE) — with one-sided binomial tests (H0: true coverage ≥ 0.90) and Holm correction at family-wise 0.10 (confirmatory inference). Operationally, each direction also receives an audit label from the unadjusted 95% Clopper-Pearson interval against the pre-specified operational audit threshold of 0.80 (Compatible: lower bound ≥ 0.80; Incompatible: upper bound < 0.90; else Undetermined; Incompatible priority in the overlap). The 0.80 threshold has no clinical-safety interpretation. For the primary directions the two procedures agree in this data set; the alignment of the audit-label rule with the pre-registered "Holm-adjusted CI" wording is recorded as an amendment in the protocol change log. PD/HC class-conditional coverage was a pre-specified safety diagnostic with exact Clopper-Pearson intervals. Even in-domain, split CP guarantees only marginal — not class-conditional — coverage; under joint covariate and label shift, class-conditional coverage may further be unidentifiable without target labels, which is why it is measured. All class-conditional, subgroup, and comparator analyses are descriptive and unadjusted.

### 2.5 Recovery and attribution
The pre-registered recovery-cost table crossed {naive CP, target recalibration (5/10/20/30%), weighted CP, protocol-conditional recalibration} with {target labels used, coverage, PD coverage, mean set size, singleton rate, rejection rate}. Attribution stress tests: (A) synthetic dose–response — donor-class person-level label flips at 10/20/30% in three flip directions, compared with the dispersive-noise theory of Einbinder et al. [9] via the exact calibration-side stochastic-dominance condition; (B) a three-arm real-transfer test — prevalence re-matching to 74% by resampling, prevalence-preserving two-way label flips, and their combination — against pre-specified practical-equivalence tolerances (±5 percentage points coverage; ±0.3 mean set size, corresponding to 30% of the binary set-size range); (C) black-box shift estimation (BBSE) [16], which estimates target prevalence from a source-trained classifier's class-conditional confusion matrix under the label-shift assumption P(x|y) unchanged — validated on constructed label shift and applied descriptively to real pairs. Following the frozen wording template, these tests ask whether the manipulations are sufficient to reproduce the observed patterns; no causal identification is claimed.

## 3. Results

### 3.1 Primary family: all three directions Incompatible
Every primary direction fell statistically short of the nominal level under family-wise control (Table 2, Fig. 1): Tappy→MIT 0.598 [0.483, 0.704] (Holm q = 1.2×10⁻¹²), MIT→Tappy 0.850 [0.788, 0.899] (q = 0.023), clinical-pool→self-report 0.732 [0.684, 0.777] (q = 2.5×10⁻¹⁹). Prediction sets were short (mean sizes 1.11–1.53; singleton rates 0.47–0.89), so deficits reflect confident miscoverage rather than uninformative outputs. The singleton rate is the fraction of subjects receiving a single-class prediction set — the system's committed diagnosis. The LightGBM comparator covered 0.963–0.988 in the same directions with near-full sets (mean 1.92–1.97; singleton rates 0.03–0.08) — coverage bought conservatively.

### 3.2 Safety diagnostic: marginal coverage concealed class-conditional collapse
In Tappy→MIT, PD-conditional coverage was 0.214 [0.103, 0.368] (n = 42) while HC coverage was 1.000 (n = 40): 33 of 42 PD patients (78.6%) received sets excluding their true label — predominantly confident singletons containing only the non-PD label, i.e., false reassurance under an auto-pass screening workflow (Fig. 2). The under-served class flipped with target prevalence: HC-conditional coverage was the deficient one in the two PD-heavy targets (0.700 in MIT→Tappy; 0.627 in clinical→self-report). The comparator score was near-uniform across classes (0.925–1.000). These are measured, unadjusted diagnostics on a frozen cohort, not guarantees.

### 3.3 Decoupling: discrimination and coverage degrade on different axes
Across all 12 transfer directions, discrimination and coverage moved asynchronously in both score functions (Fig. 3). The comparator's mean coverage exceeded the reference's in 11 of 12 directions despite lower AUC in all 12; reference-model directions spanning AUC 0.55–0.81 showed coverage from 0.58 to 0.91. Per the pre-registered H1 plan this is a descriptive cross-direction characterization (no significance testing across 12 non-independent directions); the pattern is the paper's central object.

### 3.4 Recovery: cheap where the score survives, expensive where it collapses
Target recalibration with 9 labels restored the audit threshold with CI support in MIT→Tappy (0.982 [0.947, 0.996]); 18 labels sufficed for clinical→self-report (0.876 [0.837, 0.909]). Tappy→MIT was different: at the first non-degenerate budget (16 labels) the point estimate crossed 0.80 (0.833), but the CI lower bound never reached 0.80 within a 30% budget (25 labels; 0.877 [0.763, 0.949]), and the PD-conditional residual persisted (0.759 vs HC 1.000) — pooled recalibration repairs the marginal quantile, not class-conditional miscalibration. The protocol-conditional arm, evaluated on the two-protocol merged target, did not clear the threshold at the 5% budget (0.836 [0.793, 0.874]), a different estimand from the pooled quantile. Label-free density-ratio weighting attained nominal coverage (0.918–1.000) only by abstaining on 86–100% of subjects: coverage without utility. Fewer than 9 target labels yield degenerate full-set calibration sets at α = 0.10.

### 3.5 Attribution: the observed phenotype is not manufactured by prevalence or noise alone
Synthetic dose–response on the clinical source reproduced the form of class-conditional collapse — the HC→PD flip pinned PD-conditional coverage at 1.000 while HC-conditional coverage fell monotonically to 0.425 — and the dispersive-noise dominance condition held at the process level in 9/9 theory-aligned cells. In the three-arm test, none of prevalence re-matching, prevalence-preserving corruption, or their combination reproduced the observed MIT→Tappy phenotype within the pre-specified tolerances — every arm missed both tolerances, two by overshooting into extreme asymmetry (HC coverage 0.025 and 0.000) absent from the real data (Fig. 5). BBSE, validated as unbiased with nominal interval coverage on constructed label shift, degenerated on exactly the worst direction (Tappy→MIT, estimated PD prevalence 0.000): its label-shift assumption is least plausible exactly there, so the estimate is reported as an assumption-violation diagnostic, not a prevalence estimate. The deployed coverage phenotype was not reproduced by prevalence re-matching or label corruption alone at the pre-specified doses in this direction; the feature-space shift itself remains an uneliminated factor (no causal identification claimed) and is not a target that prevalence correction or label cleaning could address on their own.

### 3.6 Robustness and subgroups
Under the pre-registered confirmatory pipeline (single seed = 1), no pre-registered sensitivity analysis flipped the primary verdicts: α = 0.20 (0.522–0.705); dual re-inclusion of the three tremor-only participants (largest shift +0.073); quarter-level session re-aggregation (identical results); feature tier as covariate (no monotone gradient). The MIT→Tappy verdict sits close to the decision boundary (CI upper bound 0.8994), and its per-seed split distribution (mean 0.853 ± 0.058) implies that individual splits can fall in the Undetermined band; the family-level conclusion (mean coverage below 0.90 across splits, 50-seed z ≈ 5.7 against 0.90) and the pre-registered power analysis are provided in the supplement. Sex-stratified coverage (computable only for Tappy-origin targets) showed an 8.7 pp male deficit in MIT→Tappy; MIT and OE publish no demographic fields, which is reported as a limitation rather than imputed.

## 4. Discussion

Principal finding. Under cross-dataset deployment of PD typing classifiers, the conformal coverage guarantee behaves as a reliability dimension distinct from discrimination: it fails family-wisely where discrimination looks acceptable, survives where discrimination looks poor, conceals class-conditional collapse behind acceptable marginal totals, recovers at widely different label costs, and cannot be reproduced by the tested prevalence and label-noise mechanisms alone. A deployed screening system reporting only AUC has characterized half of its own reliability.

For practice — coverage auditing as deployment governance. Operationally, these results say a deployment can pass its AUC acceptance test yet silently route most positive patients to an auto-pass path — which is why coverage belongs in the acceptance gate, not the post-hoc evaluation. Concretely: (i) treat the pre-registered verdict vocabulary as a pre-deployment acceptance gate (Undetermined/Incompatible = do not sign off without remediation evidence), and schedule periodic re-audits with re-triggering on upstream device or population changes; (ii) budget a small, class-stratified standing calibration set per deployment site — this evidence supports a 9–18 subject budget where the score survives, and a do-not-deploy (or abstention-only workflow) policy where it does not; (iii) make class-conditional audit results a gating condition for permitting any auto-pass workflow — in Tappy→MIT, auto-passing singletons meant 78.6% of PD patients were silently cleared; at mean set sizes of 1.1–1.5, the manual-review workload that would have caught this is 10–50% of subjects, a modest cost against the failure mode; (iv) position typing-based PD triage as one component of a health-information system referral pathway, not a standalone diagnostic.

Relation to prior work. Coverage audits of medical CP exist for chest radiographs, ICU mortality, visual domain transfer, EEG, and EHR settings; PD digital phenotyping has used CP for medication-need intervals and selective refusal in multimodal assessment — in-domain. Cross-dataset keystroke benchmarks have left uncertainty unexamined. Our results do not contradict CP theory; they measure what the theory predicts at the boundary of its assumptions, on data a deployment would actually meet.

Conclusions. Discrimination metrics and coverage guarantees fail independently under deployment shift. Health systems deploying keystroke-based screening should treat coverage auditing — marginal and class-conditional, per target cohort — as a standing requirement alongside discrimination evaluation, budget for small per-site calibration sets, and evaluate candidate score functions' coverage behavior as part of model selection.

## Limitations
(1) Self-report labels qualify the estimand on self-report targets; random flips are not structured mislabeling, and reproduction claims are limited to "sufficient to reproduce" at the pre-specified doses in one direction. (2) The effective reference model is logistic regression following a pre-registered gate failure of the original LightGBM choice (three runs documented); the amendment was frozen before cross-dataset coverage was computed, and the comparator is reported throughout. (3) Score-dependence is established descriptively across two score functions and 12 non-independent directions; two scores demonstrate that coverage failure is not intrinsic to the task, not a general law of score space. (4) MIT and OE publish no sex/age fields, limiting subgroup audits; MIT's control group is female-biased (~17 pp) per the literature. (5) Class-conditional coverage is measured, not guaranteed, even in-domain. (6) OE retains 0.27% duplicate rows by pre-registered decision; the merged source pool statement concerns label quality, not distribution exchangeability, and no leave-one-source-out sensitivity was run. (7) Weighted CP has no third-party library cross-check; p99 truncation voids its formal guarantee; correctness of the untruncated form rests on an independent oracle, and its practical failure (abstention) is reported as an outcome.

## Statements and Declarations
**Funding.** [No funding was received for this study / to be completed by the author.]
**Competing interests.** The author declares no competing interests. [To be confirmed.]
**Ethics approval.** This study used exclusively de-identified, publicly available datasets (MIT-CSXPD, Tappy Keplar, TyPD/i-PROGNOSIS, Online English) released for research use; no new human data were collected and no intervention occurred; institutional review was therefore not required. [Institutional exemption statement to be confirmed by the author.]
**Consent to participate / to publish.** Not applicable: no individual participant data were newly collected; all datasets are public research releases with their own consent frameworks.
**Data availability.** All four datasets are publicly available from their original distributors (MIT-CSXPD via the neuroQWERTY release; Tappy Keplar via the Tappy/BBDP repository, registration required; TyPD via i-PROGNOSIS; Online English via its publication page); the frozen cohort construction with step-by-step inclusion/exclusion counts is released with the code.
**Code availability.** Full pipeline, frozen result tables (tag `results-frozen-v1`), unit-test suite, and per-cell outputs are archived at [Zenodo/OSF DOI to be minted at acceptance]; the development repository is public.
**Author contributions.** [CRediT roles to be completed: conceptualization, methodology, software, investigation, writing — to be assigned by the author.]
**Use of large language models.** AI agent assistance (ZCode CLI with GLM models) was used under human direction for pipeline execution, code generation, and internal consistency auditing; the author designed the study, verified all outputs, and is accountable for all content, including citations. [Tool version, usage dates, and access method to be completed at submission.]

## References (Springer Basic; author to verify each entry before submission — zero-fabrication policy)
1. Giancardo L, Cisco G, Sánchez-Ferro A, et al (2016) Computer keyboard interaction as an indicator of early Parkinson's disease. Sci Rep 6:34468. https://doi.org/10.1038/srep34468
2. Arroyo-Gallego T, Ledesma-Carbayo MJ, Sánchez-Ferro A, et al (2017) Detection of motor impairment in Parkinson's disease via mobile touchscreen typing. IEEE Trans Biomed Eng 64(9):1994–2002. https://doi.org/10.1109/TBME.2017.2664802 [author to verify]
3. Tripathi A, et al (2023) [Keystroke-dynamics-based PD detection on the neuroQWERTY longitudinal cohort]. IEEE Trans Biomed Eng [author to complete]
4. Francesconi F, et al (2025) Cross-dataset multivariate time-series model for Parkinson's Diagnosis via Keyboard Dynamics. arXiv:2510.15950. https://arxiv.org/abs/2510.15950
5. Vovk V, Gammerman A, Shafer G (2005) Algorithmic learning in a random world. Springer, New York
6. Angelopoulos AN, Bates S (2023) Conformal prediction: a gentle introduction. Found Trends Mach Learn 16:494–591. https://doi.org/10.1561/2200000101
7. Tibshirani RJ, Foygel Barber R, Candès E, Ramdas A (2019) Conformal prediction under covariate shift. In: NeurIPS 32
8. Barber RF, Candès E, Ramdas A, Tibshirani RJ (2023) Conformal prediction beyond exchangeability. Ann Stat 51:816–845. https://doi.org/10.1214/23-AOS2276
9. Einbinder B-S, Feldman S, Bates S, et al (2024) Label noise robustness of conformal prediction. J Mach Learn Res [author to verify volume/pages; arXiv:2209.14295]
10. Han W, et al (2026) The label complexity of class-conditional coverage under distribution shift. arXiv:2607.18088. https://arxiv.org/abs/2607.18088
11. Diaz-Rincon A, et al (2025) Uncertainty-aware prediction of Parkinson's disease medication needs: a two-stage conformal prediction approach. PMLR 298. https://arxiv.org/abs/2508.10284
12. [SGC-RML team] (2026) SGC-RML: a reliable and interpretable longitudinal assessment for PD in real-world DNS. arXiv:2605.08302 [author to complete]
13. Tuwani R, Beam E, et al (2023) [CP coverage audit in eICU] [author to complete]
14. Collins GS, Moons KGM, Dhiman P, et al (2024) TRIPOD+AI statement: updated guidance for reporting clinical prediction models that use regression or machine learning methods. BMJ 385:e078378. https://doi.org/10.1136/bmj-2023-078378
15. [MAPIE maintainers] (2025) MAPIE: a library for conformal prediction [author to complete per JOSS record; verify author list]
16. Lipton ZC, Wang Y-X, Smola A (2018) Detecting and correcting for label shift with black box predictors. In: ICML 35

---

# Tables

**Table 1.** Frozen cohort construction (subjects; PD/HC).

| Dataset | Role | Eligible | PD | HC |
|---|---|---|---|---|
| MIT-CSXPD | Clinical gold standard; source (direction 2, 3) / target (direction 1) | 82 | 42 | 40 |
| Tappy Keplar | Self-report; source (direction 1) / target (direction 2) | 173 | 133 | 40 |
| TyPD (i-PROGNOSIS) | Clinical; merged source pool only | 27 | 12 | 15 |
| Online English | Self-report; merged target only | 193 | 83 | 110 |
| **Total** | | **475** | **270** | **205** |

**Table 2.** Primary family (α = 0.10, split CP, confirmatory seed = 1). Verdicts under family-wise Holm correction (H0: true coverage ≥ 0.90).

| Direction | Model | K/n | Coverage [95% CI] | Holm q | Verdict |
|---|---|---|---|---|---|
| Tappy→MIT | LR | 49/82 | 0.598 [0.483, 0.704] | 1.2×10⁻¹² | Incompatible |
| Tappy→MIT | LGBM | 79/82 | 0.963 [0.897, 0.992] | — (comparator) | — |
| MIT→Tappy | LR | 147/173 | 0.850 [0.788, 0.899] | 0.023 | Incompatible |
| MIT→Tappy | LGBM | 171/173 | 0.988 [0.959, 0.999] | — (comparator) | — |
| Clinical→Self-report | LR | 268/366 | 0.732 [0.684, 0.777] | 2.5×10⁻¹⁹ | Incompatible |
| Clinical→Self-report | LGBM | 354/366 | 0.967 [0.943, 0.983] | — (comparator) | — |

---

# Figures (embedded for internal review; final submission places them at first citation)

**Fig. 1** Primary-family coverage on target cohorts (Clopper-Pearson 95% CI). Dashed line = nominal 0.90; dotted = pre-specified operational audit threshold 0.80. LR = primary reference; LGBM = comparator (DEC-T1).

![Fig1](../figures/fig1_primary_forest.png)

**Fig. 2** PD/HC class-conditional coverage (measured, unadjusted safety diagnostic — not a guarantee). Left = LR; right = LGBM. Squares = PD; circles = HC; annotations give per-class n.

![Fig2](../figures/fig2_class_conditional.png)

**Fig. 3** Decoupling map: ΔAUC vs Δcoverage (50-seed means; 12 non-independent directions — descriptive, no correlation test). Left = LR; right = LGBM. Labels: dataset initials T = Tappy, M = MIT, Y = TyPD, O = Online English; arrow = transfer direction.

![Fig3](../figures/fig3_decoupling.png)

**Fig. 4** Recovery-cost curves. Open markers = degenerate full-set calibration (m<9); stars = weighted CP at 0 labels (rejection 0.86–1.00): coverage without utility. Non-monotonic segments reflect single-draw sampling noise (pre-declared). Audit 0.80 = pre-specified operational audit threshold.

![Fig4](../figures/fig4_recovery_cost.png)

**Fig. 5** Stress-test A dose–response. Left = calibration-only flip (theory-aligned); right = train+calibration flip (deployment). Arms encoded by color and line style.

![Fig5](../figures/fig5_dose_response.png)
