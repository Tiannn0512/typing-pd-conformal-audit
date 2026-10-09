# Provenance — development commit chain (notarization ledger)

This public repository is a curated snapshot (single seeded commit + incremental
manuscript-version commits). The authoritative development history — including the
pre-registration and result-freeze commits — is kept in the authors' development
repository. Third-party copyrighted paper PDFs and all dataset files are excluded
from this public archive, which is why the full commit history is not pushed here.

For timestamp/priority purposes, the entries below are the complete commit chain
of the development repository (hash | author date | subject), recorded verbatim.
Anyone with access to the development repository can verify each hash; the two
governance tags are called out explicitly.

## Governance tags

| Tag | Development commit | Date (UTC+8) | Meaning |
|---|---|---|---|
| v1.0-prereg | 6459a9ec9a88b4039008ceff83500c0900d33c57 | 2026-09-26 17:15:36 | Frozen analysis plan, pre-registered on OSF before any cross-dataset coverage was computed (OSF registration Sep 26, 2026, 6:09 PM, embargoed, https://osf.io/j9fvx) |
| results-frozen-v1 | ce26f33446119a25d162fb529d5872dd9e615702 | 2026-09-27 09:33:42 | Result layer frozen (all results/*.csv formal tables + analysis code); post-freeze changes require a new round per POL-1 |

## Full commit chain (120 commits, 2026-09-25 → present)

```
df1afcdd06f9852698e0092a2e89f2f91fec90b0 | 2026-10-02 00:03:19 +0800 | docs: restore in-manuscript AI-use disclosure (CHG-AI1)
70fee3bcab915217c5b8534c62c35780621fc02f | 2026-10-01 23:48:42 +0800 | docs: changelog CHG-PUB4 + PROVENANCE chain extended
bfe6428079e9f9696ab221a24221fae5917daaff | 2026-10-01 23:48:25 +0800 | chore: neutralize internal decision-narration in code comments and configs (CHG-PUB4)
b416bd78bfcef4a23cad87a61853b18a4b4d2d5c | 2026-10-01 23:48:25 +0800 | docs: final governance-vocabulary pass over V6.0 main text (CHG-PUB4)
afdadb2239842e810bb80ebd7a4f64d315df7581 | 2026-09-30 20:43:28 +0800 | docs: PROVENANCE chain extended
e5d5824dfaefc22dd4271a7be976533676c6f40a | 2026-09-30 20:43:27 +0800 | docs: changelog note for Table 1 conventional-layout follow-up
3f71e72f3402e3814f1dbbf5323967354146e7a4 | 2026-09-30 20:42:34 +0800 | docs: PROVENANCE chain extended
8dce3412c6b4a51a0a760de4e9c954f418f809f2 | 2026-09-30 20:42:33 +0800 | docs: Table 1 reduced to a conventional dataset summary (CHG-TAB1 follow-up)
8983bd1a90fbb1b5f75b58a78660db006706aaf0 | 2026-09-30 20:30:00 +0800 | docs: PROVENANCE chain extended to e8e064e
e8e064ebc57b26792d503b26b5edf62631a2c852 | 2026-09-30 20:29:47 +0800 | docs: de-AI Tables 1-2, apply two pending V6.1 vocabulary items (CHG-TAB1)
4cbb8af14a8528b31db26da0bca2217ec127f9ea | 2026-09-30 17:56:39 +0800 | docs: changelog CHG-PUB3 + PROVENANCE chain extended to c399942
c399942c7791200b84dc2fbab996ed46729226fe | 2026-09-30 17:55:49 +0800 | docs: naturalize public-facing documents, drop internal workflow notes (CHG-PUB3)
caeb1237c282de2f5cb8e1691271a90fcc90409f | 2026-09-30 10:32:27 +0800 | docs: changelog CHG-FIG14 + PROVENANCE chain extended to 499316f
499316f494a5d78c6c1d45d9f618c2bc8b8d6085 | 2026-09-30 10:31:48 +0800 | docs: V6.0 manuscript (EN+ZH) with CHG-FIG14 figures embedded
532f781a37e782d459852e780fe00bfee6ef3fff | 2026-09-30 10:31:48 +0800 | figs: strip explanatory/meta annotations from figure text (CHG-FIG14)
49a0972d7a3a7ab7c6c8cb7b34bbb384dba6f167 | 2026-09-28 17:52:15 +0800 | docs: changelog CHG-FIG13 + PROVENANCE chain extended to e31bfed
e31bfed61c91da7fadeb8e3e7cdd82032a1960f4 | 2026-09-28 17:48:31 +0800 | docs: swap V5.1 embedded figures to audited palette set; fix Fig.6 panel lettering (CHG-FIG13)
04edb4b8be8593a6761f1c0ac940755d976388d1 | 2026-09-28 17:44:45 +0800 | figs: per-figure palettes + audit-driven correctness fixes (CHG-FIG13)
1ba0ae173dd5d8ccd3f05bcabd05df363ec96654 | 2026-09-27 19:31:56 +0800 | docs: changelog CHG-FIG11
2673575b53013cc844cf18b3bff3477353de4cf1 | 2026-09-27 19:31:27 +0800 | style: figures recolored to harmonious soft palette from user-provided swatches
266f92a25be3b816e03368327fdec20d2de78a88 | 2026-09-27 19:26:15 +0800 | docs: changelog CHG-FIG10
e8fb42c7cead136a2d4136d2494effd794b7ebe8 | 2026-09-27 19:23:38 +0800 | style: recolor figures to SciencePlots/Tol CNS palettes (user feedback round 2)
0ae9a4926219f48593504f95523be792fe3eec49 | 2026-09-27 19:19:21 +0800 | docs: changelog CHG-FIG9
efb92c297337192daa1e1c88a239f602ec510034 | 2026-09-27 19:18:54 +0800 | style: per-figure distinct journal palettes + fig1 legend moved outside (user feedback)
43dba87581aee6eb83e9a905779ce57c6de3d1da | 2026-09-27 18:35:17 +0800 | docs: changelog CHG-FIG8
9b2d44ad034678b5234b15c61d2cdd346a42a8d7 | 2026-09-27 18:34:48 +0800 | style: figures overhauled to CNS-journal conventions (user-requested)
acac7c40118652ff8db32804fb1772d16298a72b | 2026-09-27 18:21:32 +0800 | docs: changelog CHG-FIG7 (fig6 legend clip fix)
b46472f70e5b47d7149e910a9642156ecbb56c25 | 2026-09-27 18:21:08 +0800 | fix: fig6 panel C legend clipped the 1.0-height bar (user-reported)
30ad50a7f1438b09d8b61d66b3dd75f3bc4dc9e8 | 2026-09-27 18:02:39 +0800 | docs: changelog CHG-STRUCT2 (V5.1 AI-disclosure removal, compliance caveat noted)
17680fc75b7478abfa439109b2d81507ae67c6eb | 2026-09-27 18:02:12 +0800 | docs: manuscript Typing_PD(V5.1) — AI-assistance disclosure section removed (user decision)
032779a862361106c2355e0321dbdb50d4a0b7a2 | 2026-09-27 17:52:37 +0800 | docs: changelog CHG-STRUCT1 (V5.0 restructure to published JMS template)
5a2b1b72eccdff796b2aa0297c1e78d5c69a2c18 | 2026-09-27 17:52:10 +0800 | docs: manuscript Typing_PD(V5.0) — restructured to match published JMS article layout (TODO-5.2f)
f56c4e69a0602d5122c137b58067adff9a26c423 | 2026-09-27 17:38:45 +0800 | docs: changelog CHG-REV4 (V4.0 fourth review round, final audit PASS)
1755d8fb41bdd910496a32c3361d8f4d8e1f320e | 2026-09-27 17:38:06 +0800 | docs: manuscript Typing_PD(V4.0) — fourth review round (14 points) applied (TODO-5.2e)
37439d7868fc5ad11dd9cc9bc046c59486570118 | 2026-09-27 17:21:19 +0800 | docs: ledger TODO-5.2d + changelog CHG-REV3 (V3.0 third review round)
23b9f3c85644faae8aaa31437971ae3813c4266b | 2026-09-27 17:20:11 +0800 | docs: manuscript Typing_PD(V3.0) — third review round (15 points) applied (TODO-5.2d)
6cb238e237b3c8fbd71e21c77ab5b1ffa1890543 | 2026-09-27 16:50:59 +0800 | docs: manuscript Typing_PD(V2.0) — 26-point review applied + reviewer-skill re-audit (TODO-5.2c)
08801163b80b5660af1e9b1d27699a3ca765983e | 2026-09-27 16:03:14 +0800 | docs: manuscript Typing_PD(V1.0) JOMS-compliant + reference verification (TODO-5.2b/5.3 reroute)
b480918a5c6f6d839ab203c103507c984827d661 | 2026-09-27 13:10:58 +0800 | fix: figure overlap round 3 (visual-judge pixel audit) - fig1 legend white frame + ref-label offsets, fig2 n-labels white bbox + dynamic offset below 0.90 line, fig3 label anchoring fix (pt-offset root cause) + dual-line avoidance, fig4 nominal label to empty segment + marker white edges + audit label below line, fig5 marker white edges; docx regenerated
1b79875b092c394e1d3dec56f2cb802eef1f7f64 | 2026-09-27 12:27:01 +0800 | docs: ZH manuscript synced to v1.0-rev (full mirror of revision round 1); both docx regenerated with final figures
9441a82f66aa2999287c88a92111f3f53957b101 | 2026-09-27 12:19:57 +0800 | docs: revision round 1 applied (three-reviewer Majors): [n] citation system, Tables 1-2 embedded, health-systems governance paragraph, research-grade qualifier, two-layer class-conditional framing, BBSE assumption framing + Lipton ref, LLM/TRIPOD+AI/preregistration in Methods, per-seed boundary disclosure; key PDFs downloaded to 04_关键文献 (4 arXiv/NeurIPS + SciAdv blocked)
fae64dce44fe56ddc56744224db2f6957d73d065 | 2026-09-27 12:10:10 +0800 | fix: figure overlap round 2 - fig1 ref labels to top, fig3 label collisions + quadrant notes moved/captioned, fig4 legend to upper right + in-image footnote to caption, fig2 minor ticks
7d495584c56ad1ee6502f2ffb37fcbb11e03c879 | 2026-09-27 11:42:36 +0800 | docs: JOMS drafts EN+ZH with embedded figures; three-reviewer round blocking fixes applied (3 CI upper bounds per frozen table, Giancardo ref title/DOI per Crossref, Arroyo/Francesconi/Collins ref corrections, Fig.3 miscite)
544559825da8a9196a575573a2671eae543f3e27 | 2026-09-27 11:15:50 +0800 | docs: JOMS-formatted draft v0.9 (journal switch JBHI->JOMS per user; 1834/4000 words main text; Springer Basic refs with zero-fabrication to-do; TRIPOD+AI checklist and LLM disclosure flagged per JOMS requirements)
32ac92c803be1ebaa427819ce65d06947dd6cfe8 | 2026-09-27 11:10:06 +0800 | fix: figure layout v2 - constrained layout, uniform 183mm double-column width, 600 DPI, collision-free labels/legends, shape+color redundant encoding (scientific-visualization skill review)
dd39cafd63a9b6e964979403f747152929708e0b | 2026-09-27 10:20:52 +0800 | docs: manuscript v0.9 (TODO-5.2) - decoupling storyline, title B, review fixes applied; table2 holm-q format fix; paper_tables whitelisted
f206f6d843344003d988e82403fa1bf1eb0e2f87 | 2026-09-27 09:56:35 +0800 | feat: frozen results + figures (TODO-5.1)
ce26f33446119a25d162fb529d5872dd9e615702 | 2026-09-27 09:33:42 +0800 | docs: results-frozen-v1 freeze record (user confirmed 2026-09-27 09:32; Phase 4 complete pending storyline decision)
18f7c08daac6bcb23d4528a7bc4df3cc436d3bdf | 2026-09-27 09:30:45 +0800 | docs: four-way review round fixes - ledger errata items 7-11, operationalization registrations (changelog sec5), seeds runtime assert, CI literal harmonization (ulp-level CSV change verified vs primary_family)
4a19520723d8a24e5a38dcb2949f9dbbb4b86d45 | 2026-09-26 23:49:18 +0800 | feat: subgroup audit + novelty scan W8 + sensitivity ledger records (TODO-4.9/4.10, review deferred to 2026-09-27 per user instruction; freeze withheld)
e110c89bcfadb5f519055e4a43ad7e7fc7b31cbd | 2026-09-26 23:45:46 +0800 | feat: sensitivity batch results (TODO-4.10) - 18 rows, anchors pass, no verdict flips
5070d90537451062c3a41ac4aeecb3d383a27646 | 2026-09-26 23:44:31 +0800 | fix: sensitivity anchor split tolerances - L1 1e-9 exact, L2tappy 1e-4 (frozen values are build-time float32 accumulation, verified irreproducible from float64 export) - TODO-4.10
f447021be5efdf3ad17015fb35ba3cb3ec5c16c0 | 2026-09-26 23:40:42 +0800 | fix: sensitivity aggregator anchor 1e-9 tolerance (parquet-roundtrip 1-ulp summation noise, first-run catch; recipe verified subject-exact) - TODO-4.10
db1fb6299667d461fe29cda8f43ce33633b3529d | 2026-09-26 23:37:02 +0800 | feat: sensitivity batch pre-declaration (TODO-4.10) - alpha 0.20 / 50-seed / tremor-3 dual inclusion / quarter-session variant with bit-exact aggregator anchor / tier covariate
fe06b925e31f76e8da77a421b5778291761b9f9a | 2026-09-26 23:28:09 +0800 | feat: subgroup audit pre-declaration (TODO-4.9) - sex/age_median strata operationalization on available fields, explicit unavailability for MIT/OE
982b5880177591eee190fe4e486f0535fb714503 | 2026-09-26 23:14:51 +0800 | feat: three-arm stress test (TODO-4.8)
c025921a1202eddfdef2cda9d961b8afac0c3c73 | 2026-09-26 23:13:49 +0800 | fix: three-arm adds the declared recovery_cost naive-row assertion (review item 5, doc-level) + stray token cleanup (TODO-4.8)
06b9d2fc792e304816413cab778a3265b6ebeafc | 2026-09-26 23:00:46 +0800 | fix: three-arm baseline row explicit deltas/reproduced (NaN-truthiness would mislabel verdict; TODO-4.8)
a566fdf7e4d4246f1fa6d78dcfa6eb5b03498e82 | 2026-09-26 22:59:31 +0800 | feat: three-arm stress test pre-declaration (TODO-4.8) - mass-matched flip operationalization, prevalence-preserving equal-count flips, scope split per plan section 10
6605fd8eb6aea3eee92c97d7426bc09137d8fb16 | 2026-09-26 22:50:54 +0800 | feat: bbse synthetic + descriptive (TODO-4.7)
bf44638ef6881604ab2892d3ab72ccd4ba3e17c5 | 2026-09-26 22:25:41 +0800 | fix: BBSE estimator v2 - class-mean confusion matrix solves target prevalence directly, drop erroneous extra pi_s multiplication (caught by pre-registered no-shift anchor; TODO-4.7)
66673e332caa96ae4606c618c76bc6816f787c49 | 2026-09-26 22:21:16 +0800 | feat: stress test C pre-declaration (TODO-4.7) - BBSE pool-resampling validation protocol + descriptive real-pair arm, pre-results commit per anti-recurrence rule 4
37c2232ef032ed2c0c5b73989aaec2d82b4cb6e6 | 2026-09-26 22:14:07 +0800 | feat: calibration comparison (TODO-4.6)
4b9c9297b3d7d6d7769ce87c4cc9485a1341e9b2 | 2026-09-26 22:00:56 +0800 | fix: show rejection rate in calibration comparison summary (weighted-arm abstention pathology visible, TODO-4.6)
d2142b449ba8a129eea14d11c51cb984b5ff58fd | 2026-09-26 22:00:18 +0800 | fix: calibration comparison carries qhat_inf column + degenerate-row markers in summary (honesty fix pre-results, TODO-4.6)
d4c389dfe6eee392ee0f4c78da9baff6506dd4ba | 2026-09-26 21:59:27 +0800 | feat: stress test B pre-declaration (TODO-4.6) - three-way calibration comparison protocol, bit-equality anchors to recovery_cost_table, delta attribution layer
6b2f25eba39bcb7d5e61ab0ba552f714afe49743 | 2026-09-26 21:49:05 +0800 | feat: stress test A (TODO-4.5)
85b9211586cae0f6e72cce2d60fef5c514ecd74f | 2026-09-26 21:25:29 +0800 | fix: stress test A v2 - dominance check relocated to calibration side (faithful mechanism certificate for cal_only scope); transfer-adjusted theory reading; test-side kept as secondary reference (TODO-4.5, revision documented pre-rerun)
25aa6c823eeb4f10b945deee725afecb042455b6 | 2026-09-26 21:21:21 +0800 | feat: stress test A pre-declaration (TODO-4.5) - dose-response 3x3 protocol + Einbinder dominance operationalization, pre-results commit per anti-recurrence rule 4
0e89302e2f2927c032007af1676eb9c534ac252d | 2026-09-26 21:11:31 +0800 | docs: round-3 audit fixes - ledger errata (6 items), CHG-GW1/CHG-FD2 registration, anti-recurrence rule 4, handoff 2110 (TODO-4.4 review round)
74e6a1aacf6e11f66831ffdd96797838524b542d | 2026-09-26 20:51:17 +0800 | feat: remediation recovery-cost (TODO-4.4)
49a2948ae37ceb81ce226822cc3fcab3e12caedc | 2026-09-26 20:17:43 +0800 | feat: class-conditional coverage (TODO-4.3)
278e6316dbe120450a19b6d0fdc23673fede4e96 | 2026-09-26 19:59:18 +0800 | feat: L2/L3 rebuild on S1-S6 final pool (FEATURE-DEF-2) + mapping v1.0.1 keysym aliases + L3 both-hands fix; matrix L2/L3 directions updated, tappy2mit primary updated (0.5976, verdict unchanged), all registrations synced (18/18 tests)
e6963f0174554e02c6ad94f44649e41b60b30c78 | 2026-09-26 19:39:16 +0800 | docs: phase-4 timestamp erratum + handoff_1945 (phase 3 close + 4.1/4.2) + header/tree sync per final audits A/B/C
0fa02ac70c55b5025e7b8b0812f952168bced67d | 2026-09-26 19:15:15 +0800 | docs: TODO-4.2 completion record (primary result: 3/3 Incompatible family-controlled)
144101021190c1f2ccdcdedb04bed48e6bdff806 | 2026-09-26 19:14:20 +0800 | feat: primary family coverage (TODO-4.2 @ 2026-09-26 19:35) - ALL THREE primary directions Incompatible (family-controlled): tappy2mit 0.585 [0.471,0.693] q=1.9e-13, mit2tappy 0.850 [0.788,0.899] q=0.023, merged 0.732 [0.684,0.777] q=2.5e-19; LGBM comparator over-covers 0.97-1.00; review PASS zero-must-fix, independent recomputation bitwise
b95dba19bde445c99f69bca1eac2b60e3d2f188e | 2026-09-26 18:59:24 +0800 | feat: transfer matrix (TODO-4.1 @ 2026-09-26 19:05) - dual-channel six-tuple (LR+LGBM DEC-T1), tier downgrades verified leak-free, gate deviation disposition per user (option 1+3), LGBM full six-tuple; review PASS_WITH_FIXES closed
5e1ed9dcac86e3f8deb2ab6e8f5f1ed0a0320742 | 2026-09-26 18:39:11 +0800 | feat(wip): 12-direction transfer matrix (TODO-4.1) - six-tuple computed, FEATURE-DEF-1 L2/L3 features built (mapping v1.0.0), 50-seed means; fixed-to-fixed AUC 0.65-0.80 below 0.85 anchor - gate deviation, stopped for discussion per pre-registered action
0b38465ddf6fd702544bf7430f4acdbe3d9bb88d | 2026-09-26 18:31:49 +0800 | docs: phase-3 close-out ledger repair (final audits A/B/C) - TODO-3.4 checked off with real-timestamp record, timestamp erratum block, docstring precision, errata log; 18/18 tests
8804af0027742a3654daf8c29a6430a0683ac267 | 2026-09-26 18:12:23 +0800 | docs: OSF registration recorded (2026-09-26 18:09, embargoed 2y, project j9fvx; DOI pending embargo per OSF rules) - TODO-3.4 fully closed, GO confirmed, Phase 4 opens
0dc31fbb063d6a1cbe7d6e815c1d313aee3ec1d4 | 2026-09-26 17:40:57 +0800 | chore: gitignore osf_upload bundle dir
9abc6c5df0c0b583d02ca192279f3eb8dddbf24b | 2026-09-26 17:25:30 +0800 | docs: novelty scan W4 YELLOW (no scoop, exact gap intact, window tightening) + TODO-3.5/3.6 closure (TODO-3.5 @ 16:45, TODO-3.6 @ 16:55)
69e2725e0e62e05cf5a3d1834cd4eee7550aacc7 | 2026-09-26 17:17:06 +0800 | feat: pilot smoke (TODO-3.5 @ 2026-09-26) - tappy2mit end-to-end PASS (6 stages), coverage values not printed/recorded per prereg temporal constraint
6459a9ec9a88b4039008ceff83500c0900d33c57 | 2026-09-26 17:15:36 +0800 | docs: analysis_plan v1.0.1 patch (TODO-3.4 review must-fixes) - dual-n reconciliation (frozen-n power table: 28.6%/1.6%/0.0%, zero demotions hold), 9-direction erratum, TyPD 12-matrix reading pinned, unconditional-outcomes clause restored, weighted truncation+report details, ICC/full-cell-disclosure clauses
dccbf29a75eba07aa1c57d000c3bb8c49a3a3394 | 2026-09-26 17:05:54 +0800 | docs: analysis_plan_v1.md FROZEN (TODO-3.4) - primary family locked (zero demotions), overlap pinned Incompatible-first, CHG-P1/DEF-1/W4-predeclaration incorporated, exploratory 9-direction list locked; freeze protocol signed
eda628a0f43ea3b3994815c5bfe266d5ac6b3587 | 2026-09-26 16:45:44 +0800 | docs+config: TODO-3.4 prerequisites all closed (user decisions) - key_hand_mapping.yaml v1.0.0 frozen (standard touch-typing zones, space/special unassigned, OE shifted by base key), DEF-1 resolved keep-as-is, overlap pinned Incompatible-first (counterfactual committed first per user), W4 pre-declaration in CHG-P1, anti-recurrence rules + degenerate alarm + oracle/mutation tests (18/18)
18fd30829fc73e8623cad173cb192840d262082b | 2026-09-26 16:43:37 +0800 | data: overlap-region counterfactual simulation committed BEFORE pinning decision (user precondition) - Incompatible-first vs Compatible-first across 16 cells; key divergence at gold_merged2self pi=0.85 (0.884 vs 0.214 detection)
a04eb61c506d43b28a927f0496ebd418411d50ee | 2026-09-26 16:19:59 +0800 | fix+docs: recurrence-hunt round - weighted CP tail-direction fixed to paper eq(8) (independent eq(8) oracle, 6 regimes, w1==split guard), degenerate-prediction alarm, anti-recurrence rules codified, TODO-3.1 erratum, ledger sync, phase-3 handoff (18/18 tests)
37ef78e722eeb1aa5514b161fa1787db3ee8e29e | 2026-09-26 15:43:31 +0800 | fix: TODO-3.1 review round fixes - paper-exact weighted condition (W_raw+w_test > alpha(T_raw+w_test)), brute-force oracle test (3 weight regimes), w_test/empty-cal validation, load_labels source-column NaN asserts, hold_col=None guard test (15/15 tests)
66c72aac546815775884bed3f8bd8470f099f9bf | 2026-09-26 15:43:16 +0800 | feat: power simulation (TODO-3.3 @ 2026-09-26 12:55) - zero demotions (32.1%/0.0%/0.0% vs 60% rule), 16/16 cells deterministically replayed, overlap-region ambiguity flagged for W4 freeze
49c9ac730005afad7019b1e19fb1f99f639c11ac | 2026-09-26 15:32:38 +0800 | docs+data: CHG-P1 protocol §3 amendment (primary ref = LR, user-approved 1+3 combo), TODO-3.2 closed with 3-run evidence chain, per-round result archives (run2 deterministically regenerated, 0.7067 verified)
6c94bca70358dc64d58e1ce5708a313539461031 | 2026-09-26 15:17:03 +0800 | feat: mit baseline DEC-B3b run (TODO-3.2 @ 2026-09-26) - val-selected 4-combo micro-grid: LGBM mean 0.7257 (median 0.7324, se 0.0139) still < 0.75 gate; LR 0.7868 unchanged; structural small-sample tree limitation (3-run evidence chain), stopped for protocol-level discussion
30dadcd29cf42bb88219ea314185466892634ba6 | 2026-09-26 13:22:29 +0800 | feat: mit baseline first run (TODO-3.2 @ 2026-09-26) - DEC-B1/B2/B3 frozen pre-run; GATE FAIL: LGBM degenerate 0.5000 (default min_child_samples=20 > n_train=32, zero splits), LR 0.7868 in-range; stopped per discipline for discussion
c72aa9c51d744633ce613b7e4c7e8c9ffaf3b9ef | 2026-09-26 12:14:05 +0800 | test: synthetic CP unit tests (TODO-3.1 @ 2026-09-26 11:55) - exact Tibshirani weighted threshold, shared digraph derivation (3 parsers byte-identical), MAPIE 1800/1800 match, 13/13 tests
752d1fb5106aabca5c268d30ae88ce54ac1e079e | 2026-09-26 11:37:14 +0800 | docs: phase 0-2 books closed (milestone x @ 2026-09-26 11:35) - triple closing audit PASS; entering phase 3
78ef904f1f4cf07eaf5aea7b947a5ea32e806a77 | 2026-09-26 11:23:29 +0800 | docs: remove string-concat artifact in TODO-2.1 erratum (repair-round re-review finding)
9e93d4cfab743ba3656b6feaadfb7ccfff663df0 | 2026-09-26 11:17:01 +0800 | docs: repair-round handoff (2026-09-26 11:18)
1e3ae312a23324626733f3c95c3d1a28290ff023 | 2026-09-26 11:16:32 +0800 | docs: ledger errata per quadruple review - 9662212 digit fix, session-total pointer corrected (2455/9259896 strict), person-split erratum (21+21 not 61/39), phase0/tree/header sync, TODO-2.1 record amended
e143832b743e9954505d6a45aeef79379526ac7b | 2026-09-26 11:16:32 +0800 | fix: repair round per quadruple final review (2026-09-26) - S5 snapshot truly pre-person, person_excluded/label_excluded session marking, session-uniqueness assert, label NaN asserts, require_events flow count, DEF-1 OE-dedup registration; subjects.csv md5 unchanged, eligible=475 unchanged
6df0ed5c408b830e52a879d5ba41bf957b894629 | 2026-09-26 10:39:55 +0800 | docs: phase 2 handoff (2026-09-26 10:45) - cohort frozen at 475 (PD270/HC205), CHG-1 on record, both bugs fixed, QC all green
0505a8684c9ec06a28db353432c78643f9fd2e5a | 2026-09-26 10:39:11 +0800 | docs: qc report (TODO-2.2 @ 2026-09-26 10:52) - L1 zero-missing, no zero-variance, gender documented (MIT/OE unavailable), tappy long tail flagged; review PASS zero-must-fix
c2017ccc07736cd966fda1a7001b210c0179700f | 2026-09-26 10:29:59 +0800 | feat: cleaning pipeline + frozen cohort table (TODO-2.1 @ 2026-09-26 10:35) - eligible=475 (PD270/HC205), clinical pool 109; MIT gt bool bugfix; CHG-1 typd session trial->visit (user-approved); TyPD L1 latency/flight derivation gap fixed
27be1c7e31b2eea4ce58eda77f826157f2f349cd | 2026-09-26 09:37:24 +0800 | docs: morning-review ledger fixes (2026-09-26 09:40) - order tree Phase0/1 checked, status header updated, cosmetic errata (18.85%, L405/L460); reviews A PASS_WITH_FIXES->closed / B PASS
52f3df04cf8d3eabf5f0bf8d89fdf792c00fc895 | 2026-09-25 22:46:41 +0800 | docs: phase 1 milestone approved & closed (2026-09-25 22:45) - triple final review A PASS / B fixes applied / C fixes applied; OE latency<=0 erratum 83459->82537 (18.85%); session stops, next = Phase 2
fab8dc75ccfe31ec26f0036732f06d621b21ac1d | 2026-09-25 22:46:41 +0800 | fix: mit keep_flag column for schema contract (TODO-1.1/1.4 follow-up @ 2026-09-25 22:45) - parse output now matches frozen 14-col EXPECTED_COLUMNS; flagged by final review B/C
197c1676174ed9fc93cbe9e4d5ace116ac6977fd | 2026-09-25 22:32:00 +0800 | feat: schema validation + tier confirmation (TODO-1.4 @ 2026-09-25 22:31) - four-table schema contract, TyPD L1 ceiling machine-asserted, MIT/OE L2 hand-mapping gated to W4 prereg
40e28aeabeb15cbef753810def3a262754380b99 | 2026-09-25 22:23:52 +0800 | feat: typd+oe parsers (TODO-1.3 @ 2026-09-25 22:23) - TyPD 33 subjects 18/15 zero-malformed; OE 437,915 rows raw=232 subjects, response-level digraph grouping, dual duplicate counts
278b330f2747109b288d911645d49d1994b420ac | 2026-09-25 21:56:29 +0800 | feat: tappy parser (TODO-1.2 @ 2026-09-25 21:56) - 9.3M rows/622 files lossless, 266/227/217 three-way reconciliation documented
7d3a4e48b14b8c127d1fc1863075aff5ecb9e965 | 2026-09-25 21:39:36 +0800 | feat: mit parser (TODO-1.1 @ 2026-09-25 21:39) - official nqDataLoader rules replicated, 116/116 files cross-check match, 85 subjects (42/43)
13c4a33412b3d6a45026c1aebeb8b4dd4529269f | 2026-09-25 20:58:24 +0800 | docs: data manifest v1 (TODO-0.2 @ 2026-09-25 20:55) - four datasets locked, official-hash-level verification all pass; proxy channel 13x speedup recorded
3a9f9216b0f4e7f200defcbfb43673ef40b10cee | 2026-09-25 20:40:13 +0800 | docs: prereg draft v0 (TODO-0.3 @ 2026-09-25 20:42) + handoff log for TODO-0.1
7aef88126ea0ace63de4a1f6defe65484ad4aa07 | 2026-09-25 20:34:56 +0800 | chore: env locked (TODO-0.1 @ 2026-09-25 20:35) - venv python3.12 (conda unavailable), seeds.yaml, PyYAML fix, results/*.csv un-ignored
986f15ab5175ab574d1389cbf678b95adf72a1fc | 2026-09-25 18:23:06 +0800 | docs: TODO v2 realigned to proposal v1.3.2 (evidence-based terminology, power table, stress tests, three-tier features, analysis freeze doc)
21840401f0f9e083cb0ed9dff3dae556e1ba2998 | 2026-09-25 18:02:18 +0800 | docs: v1.3.2 FINAL FREEZE - round-3 review patches (evidence-based terminology, operational threshold, target leakage clause, H1 tone, outcomes declaration) + Analysis Freeze Document v1
5e8c39456464b19e3c0150bc5d89b4457f2b388e | 2026-09-25 17:51:27 +0800 | docs: proposal v1.3.1 FREEZE - external review round 2 patches applied (source pool declaration, safety-diagnostic positioning, H1 formalized, tolerance labeled, calibration budget promoted, frozen cohort table)
8ca7e0b2ef8c10011c69aab931f7fe86c0e8ae26 | 2026-09-25 17:44:15 +0800 | docs: proposal v1.3 - external review audit applied (NexCP removed, class-conditional coverage added, stress-test renamed, decoupling upgraded to central hypothesis)
20d40e489d1a3606360fe03acc6aa09b46541b4c | 2026-09-25 17:14:48 +0800 | docs: proposal v1.2.1 - red-team fixes applied, two review rounds passed (2026-09-25)
03f31df1683a2a03cd9d55fe0e0a9e41c7c850f3 | 2026-09-25 16:19:01 +0800 | docs: status update - main project active (2026-09-25)
6e8f63c6b1e4daacbddd49a06e4763f741edec91 | 2026-09-25 16:18:13 +0800 | docs: execution TODO with discipline (2026-09-25)
8ff21b8e12db50fdf3e7bcb59fbe1c380bce97a4 | 2026-09-25 16:16:22 +0800 | chore: project scaffold + proposal v1.0 + reports (2026-09-25, 卒中/语音冻结后转正为主力)
```
