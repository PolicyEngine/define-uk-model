# Validation — DEFINE-UK replication gate

**Status: PARTIALLY VALIDATED — read the target table before quoting
anything.** This header said "NOT VALIDATED. No published DEFINE-UK result
has been reproduced" long after target 1a passed, which made every
downstream page that cited this file as its record contradict it. What
holds today:

- **Target 1a PASS.** The manual's Table 4 macro block reproduces within
  tolerance (population and labour force exact to 0.01m; growth exact at
  2030/2040 and -0.30pp at 2025 against a +/-0.31pp gate; unemployment
  within 0.2pp).
- **Target 1b DIVERGENCE, pinned.** The emissions path runs below the
  published table and widens with horizon (-3.5% in 2025 to -23% in 2040).
  It is gated at the observed ratios, not tolerated.
- **Targets 2 and 3 CLOSED AT THE ACHIEVABLE CEILING**, not passed: no
  machine-readable v1.1 scenario results exist to compare against, so what
  is gated is scenario *design* plus two coarse anchors from a pre-1.0
  conference version.
- **Reimplementation milestone 1 PASS; milestone 2 outstanding.**

Nothing here licenses presenting scenario output as a validated result. A
claim about this model must name the target it rests on.

## Proof at a glance

Every claim this repo makes, with its status and the one place to check it.
Statuses: **MATCH** (agrees with a published number within a stated
tolerance), **DIVERGENCE** (documented and pinned at the observed value so
drift fails; a regression pin, not validation), **NOT COMPARABLE** (the
source does not define the series), **NOT POSSIBLE** (nothing published to
compare against), **INTERNAL CHECK** (the repo agrees with itself or with
the cached run; useful, but not a comparison with anything published).

| Claim | Status | Evidence |
|---|---|---|
| Manual Table 4: population, labour force, emission price (exogenous inputs) | MATCH, every cell (2025/2030/2040/mean/sd) within 0.01, i.e. to printed precision | [`validation/table4_scorecard.csv`](validation/table4_scorecard.csv), `tests/test_table4_scorecard.py` |
| Table 4: real GDP growth | MATCH within ±0.31pp: 2030 exact, 2040 0.06pp. 2025 (0.30pp) matches only because the band was set at that miss; see target 1a for why it misses | scorecard; `tests/test_replication_baseline.py` |
| Table 4: unemployment, NFC default rate, REER | MATCH (±0.2pp, ±0.02pp, ±0.02). Low-information where the tolerance exceeds the series sd: REER, and the unemployment sd | scorecard |
| Table 4: NFC credit rationing | MATCH 2025/2030 (±0.25pp); DIVERGENCE 2040, mean and sd | scorecard |
| Table 4: total emissions | DIVERGENCE: −3.5% / −10% / −23% at 2025/2030/2040 (target 1b) | scorecard; `tests/test_replication_baseline.py` |
| Table 4: non-fossil electricity share, power-sector default and credit rationing, imports, exports | DIVERGENCE (power and energy block; target 1b) | scorecard |
| Table 4: green investment | NOT COMPARABLE (definition not stated) | scorecard |
| Published v1.1 scenario results | NOT POSSIBLE: none are published; scenario design and two coarse FMM 2023 anchors are gated instead (targets 2 and 3) | `tests/test_scenario_design.py` |
| Served scenario deltas reproduce the cached run | INTERNAL CHECK at rel 1e-6 (11 pinned points) | `tests/test_scenarios.py`, `validation/reference_outputs.json` |
| Served scenario paths start when a policy starts (2027); the α_PP mismatch (#20) is flagged on every result | INTERNAL CHECK: default path is exactly the policy-active part of the full path, every served scenario | `tests/test_scenarios.py::test_pre_policy_years_are_opt_in_and_flagged` |
| Capacity-constrained years are flagged on served results | INTERNAL CHECK: years with generation at the capacity ceiling (E_ELEC = E_ELECMAX to printing precision) carry `capacity_constrained` and a leading caveat; 3 served fossil-fuel-ban results reach it, all in 2032 (corrected 2026-11-18 from "5 results in 2032–33": the other 2 are the refused solves, one of which stays at the ceiling to 2039) | `tests/test_scenarios.py::test_capacity_constrained_years_are_flagged` |
| Every served scenario is stock-flow consistent | 28 of 30 cached solves pass; the 2 that fail are refused | `define_uk.scenarios.sfc_check`, `tests/test_scenarios.py` |
| 22 registered scenario names are 16 distinct solves | INTERNAL CHECK: six names are byte-identical to another and carry `identical_to`; the subsidy-only scenario is one parameter set under five regime labels ([docs/scenario-notes.md](docs/scenario-notes.md)) | `tests/test_scenario_sweep.py::test_identical_to_matches_the_cached_files_exactly` |
| The ban cuts 18.5 MtCO2e more under false confidence than under mutual trust | EXPLAINED from the cached files and manual Eqs. (5), (16), (18), (19), (168): a two-quarter capacity shortfall in 2032 under mutual trust; the ban + subsidy pair, with no shortfall, shows no gap. What GVT_CRED and ELEC_BUFFER are is not published; GVT_CRED's effect is read from the outputs | `tests/test_scenario_sweep.py::test_false_confidence_gap_is_the_2032_capacity_shortfall` |
| GPI multiplier 2.25 (headline), 1.75 (secondary), from the policy start (2027Q1) to 2040; 2.30 and 1.78 over the full simulation from 2023 | Own computation, pinned ±0.01; back-loaded (0.47 after one year, below 1 through 2032), so below published short-horizon estimates; 2.25 is the top of the 2.08–2.25 range once the α_PP mismatch is allowed for; caveats travel with it | `define_uk.validation.gpi_multiplier`, `tests/test_validation.py` |
| Baseline levels vs ONS/DESNZ/OBR outturns | DIVERGENCE by design: why the adapter serves deltas only | [`validation/baseline_vs_external.csv`](validation/baseline_vs_external.csv) |
| Clean-room model, milestone 1 (accounting matrices) | INTERNAL CHECK: every identity holds on the manual's own Table 6 values to printed precision | `tests/test_accounting.py` |
| Clean-room model, milestone 2 (baseline GDP path) | Not passed: within 3.7% of the oracle on GDP with the forms found from the cached outputs (44% low before 2026-11-24), against a 1% gate; emissions 85% high by 2040 (issue #17) | `tests/test_full_model.py` (strict xfail; `test_whole_model_baseline_is_within_4_percent_on_gdp`) |

## Upstream queries

Findings raised with the DEFINE authors on their own tracker, so the record
here and the record there stay in step:

- [DEFINE_UK_1.1#1](https://github.com/DEFINE-model/DEFINE_UK_1.1/issues/1) —
  which code vintage produced Model Manual v1.1 Table 4; the emissions path at
  `846081a` runs below the published values.
- **Drafted 2026-11-17, not filed** (filing on the authors' tracker needs
  Vahid's go-ahead): every subsidy scenario lowers cumulative real GDP over
  2027–2040 (green power subsidy −47 against +252 for green public
  investment with a similar spending path; housing regulation with subsidy
  −150 against −104 without). The cached outputs show it through
  consumption and imports; is private power-sector investment meant to be
  this import-intensive (manual pp. 46–47), or is a subsidy channel missing?
- [DEFINE_UK_1.1#2](https://github.com/DEFINE-model/DEFINE_UK_1.1/issues/2) —
  §3.3.2 uses six parameters absent from Table 5 (α₀GCFPS, α₀bNFF, α₁bNFF,
  α₁CRPS, α₂CRPS, α₃CRPS) and two variables defined nowhere in the manual
  (r_KNFF, r_KFF), so the section cannot be simulated forward as published;
  plus Eq. (84) disagreeing with Table 6 by 3.04x and Eq. (61) contradicting
  the stated fuel-price normalisation. Both re-verified 2026-08-12. One
  addition to make on that thread when convenient: §5 calibrates
  `t_ELECswitch` ("switch in the electricity price long-run formation rule")
  and `P_ELECLR` ("long run electricity price"), neither of which appears in
  any printed equation — most likely the reason Eq. (84) alone does not
  reproduce Table 6's P_ELEC.

## Standard

Same bar as the suite's other replications (boe-var-model, us-hank-model):

1. Run the pinned upstream code unmodified (`define_uk.runner.run`).
2. Compare against the published scenario outputs of *"Evaluating climate
   policy mixes in the UK: an E-SFC approach"* and the DEFINE-UK 1.1 manual
   (S1 baseline plus at least the fossil-fuel-ban and green-public-investment
   scenarios).
3. Record here: figure/table replicated, tolerance, result, upstream commit,
   R version, date.

## Acceptance criteria (CI validation gate)

Everything checked against the pinned upstream run
(`846081a580a6033159d5c421632ad8f0b30d0ded`), with its numeric tolerance,
lives in one committed reference artifact:
**`validation/reference_outputs.json`**. The oracle tests read their pinned
values from it, so a local cached run and CI gate the same numbers, and no
tolerance or reference can drift silently in test code.

| Output checked | Reference | Tolerance | Test |
|---|---|---|---|
| Baseline macro block: population 16+, labour force (2025/2030/2040, annual means) | Manual v1.1 Table 4 | abs ±0.01 m | `test_replication_baseline.py` |
| Baseline real GDP growth (2025/2030/2040) | Manual v1.1 Table 4 | abs ±0.31 pp (2030 exact, 2040 0.06pp, 2025 0.30pp; no single growth convention reproduces all three years, see target 1a) | `test_replication_baseline.py` |
| Baseline unemployment (2025/2030/2040) | Manual v1.1 Table 4 | abs ±0.2 pp | `test_replication_baseline.py` |
| Baseline emissions vs Table 4 | observed divergence ratios 0.965 / 0.898 / 0.767 (target 1b — a documented divergence, consistent with a different vintage but not proven; gated so further drift fails) | abs ±0.02 on the ratio | `test_replication_baseline.py` |
| 11 pinned scenario-minus-baseline delta points (GDP_R, EMIS, UPLOT across GPI, housing regulation, fossil-fuel ban, mixed) | cached pinned run | rel 1e-6 | `test_scenarios.py::test_pinned_delta_points` |
| Scenario sign structure and cross-scenario ordering (deltas finite, baselines identical across blocks, EMIS falls everywhere by 2035, mixed dominates) | cached pinned run | exact sign / ordering | `test_scenarios.py` |
| Scenario design: exact policy-switch set per scenario; FMM 2023 anchors (GPI GDP peak +0.92% vs "≈+1%"; 2030 baseline emissions 342.8 vs "just under 350") | manual Table 5 / FMM 2023 | exact flags; wide anchors | `test_scenario_design.py` |
| GPI cumulative multiplier 2.25 from the policy start, 2027Q1–2040Q4 (cum ΔGDP 205.1 / cum ΔSPEND_GVTPS 91.2; denominator per issue #16, window since 2026-11-18), secondary 1.75 (/ cum ΔSPEND_GVT 117.0); real cum 252.2. Full simulation, 2023Q1–2040Q4: 2.30 (209.9 / 91.2), secondary 1.78 (/ 118.2); real cum 250.6 | own computation on cached run | abs ±0.01 (multiplier), ±0.5 (cumulants) | `test_validation.py` |
| Manual Table 4, all 15 rows × 2025/2030/2040/mean/sd (75 cells): MATCH / DIVERGENCE / NOT COMPARABLE per cell | Manual v1.1 Table 4 | per cell, in the CSV | `test_table4_scorecard.py` (hermetic + stale-check) |
| Calibration comparator table (baseline vs ONS/DESNZ/OBR) | committed `validation/baseline_vs_external.csv` | exact match vs recomputation | `test_validation.py` |

**Hermetic half (runs on every PR, no cache, no R, no upstream fetch):**
the upstream is unlicensed, so CI never fetches or runs it and the oracle
tests above skip there. `tests/test_committed_artifacts.py` is the part of
the gate CI can always enforce: the reference artifact is well-formed,
internally consistent (e.g. the committed multiplier reproduces from its
committed cumulants), pinned to the same commit as `define_uk.upstream`;
the committed calibration CSV keeps its exact schema, pinned external
observations, gap arithmetic, and headline divergences; the scenario
registry matches; and README/VALIDATION.md/LICENSE-STATUS.md still name
the pinned commit. The full oracle comparison runs wherever a cached
pinned run exists (developer machines) and gates the identical numbers.

**Changing any reference number** requires editing
`validation/reference_outputs.json` deliberately, with a run-record entry
below — never editing a test.

## Targets

| # | Published output | Scenario | Tolerance | Status |
|---|------------------|----------|-----------|--------|
| 1a | Manual Table 4, macro block (real GDP growth, unemployment, population 16+, labour force at 2025/2030/2040) | S1 baseline | pop/LF ±0.01m; growth ±0.31pp; unemployment ±0.2pp | **PASS** (2026-08-04, `tests/test_replication_baseline.py`; calendar anchored on the population path: run = 1987Q1–2040Q4, 2025 = t153) Growth, re-checked 2026-11-16: the 2025 miss is not an annualisation convention. No single convention reproduces all three years (2030 matches annual-mean y/y exactly; 2040 matches the mean of 4× quarterly growth, 2.01, but that convention gives 2.31 for 2030; 2025 matches none). 2025 falls in the post-2022 start-up transient, where quarterly y/y growth runs 6.2, 5.1, 4.1 and 3.3% within the year, so it is the year most sensitive to any vintage difference. The ±0.31pp band is kept unchanged. All 15 Table 4 rows: `validation/table4_scorecard.csv`. |
| 1b | Manual Table 4, total emissions | S1 baseline | — | **DIVERGENCE**: pinned code runs BELOW the published table, widening with horizon — 393 vs 407 (2025, −3.5%), 343 vs 382 (2030, −10%), 249 vs 324 (2040, −23%) MtCO2e/yr; components (EMIS_NELEC+EMIS_ELEC) sum exactly to EMIS and the baseline is identical across scenario folders, so it is not an extraction error; the re-check below finds it consistent with, but not proof of, a different model vintage from commit `846081a`. Gated at the observed ratios so further drift fails loudly. **Re-checked 2026-11-16 against all 15 Table 4 rows** (`validation/table4_scorecard.csv`): the exogenous inputs match to printed precision (population, labour force, emission price), as do the macro block and NFC finance (default rate once annualised, credit rationing to 2030). The power and energy block diverges: the run's non-fossil electricity share is 97.5% in 2040 against the table's 77.1%, power-sector default and credit rationing differ (credit rationing trends the opposite way), and trade shares run 1–4pp higher. A back-of-envelope rescaling of the run's electricity emissions to the table's fossil share, assuming they scale with it, adds ~22 Mt of the ~76 Mt 2040 gap (~30%). The remainder is in non-electricity emissions, which Table 4 does not break down, so it cannot be attributed. This is consistent with, but does not prove, the table coming from a different model vintage than `846081a`. It cannot be closed from this repo: the upstream code is not ours to change, rerunning a later upstream commit needs 16 R packages not installed here, and the clean-room model's own baseline is 44% off the oracle. |
| 2 | Manual scenario definitions (switch parameters); FMM 2023 anchors | power-sector regulation (S1–S4) | design: exact flag set; anchors: wide (vintage) | **CLOSED at the achievable ceiling** (2026-08-05). An exhaustive search established that **no machine-readable numeric scenario results are published for v1.1**: the manual's results stop at the baseline (Table 4) plus scenario *design* parameters; the George/Dafermos SSRN paper (abstract 6541398) is paywalled with no open mirror, and its scenario set (carbon pricing, subsidies) predates v1.1's regulation policies anyway. What IS verifiable is verified: `tests/test_scenario_design.py` pins that each cached scenario toggles exactly the policy switches its published description claims (FF_BAN + capacity/investment ban timings for the ban scenarios; POWER_SUB alone for the subsidy), plus the oracle gates of `tests/test_scenarios.py`. Upgrade path: authors publish scenario tables, or the SSRN paper becomes accessible. |
| 3 | Manual scenario definitions; FMM 2023 anchors | green public investment (S8–S9) | design: exact flag set; anchors: GDP peak 0.7–1.3%, baseline 2030 emissions 330–352 | **CLOSED at the achievable ceiling** (2026-08-05), same basis as target 2, with two coarse anchors from the open FMM 2023 conference version of the paper (pre-1.0 vintage, hence wide tolerances): green public investment peaks "around +1% of GDP" — the cached run peaks at **+0.92%** — and the current-policies baseline emits "just under 350 MtCO2e" in 2030 — the cached run gives **342.8**. Design gate: GPI toggles GVT_INVEST + GREEN_BONDS + GREEN_POWER exactly; the housing subsidy variant pins the published 40% subsidy rate (HOUSING_SUB_RATE=0.4). Published-figure sources recorded in `validation/published_targets.json`. |

## Run record

| Date | Upstream commit | R | Result |
|------|-----------------|---|--------|
| 2026-08-01 | `846081a` | 4.3.0 (macOS) | Full notebook renders end to end via `define_uk.runner.run` (rstudioapi shim; upstream unmodified). 151 output files: figures and tables for all four scenario blocks plus `tables/Multiplier_Summary.csv`. **Execution ≠ validation**: no comparison against the published figures/tables has been made yet, so every target above remains pending. |
| 2026-08-04 | `846081a` | cached run | Table 4 replication executed against the cached outputs: macro block passes (population and labour force exact to 0.01m; growth exact at 2030/2040, −0.30pp at 2025; unemployment within 0.2pp; 2025–40 mean/sd of growth and unemployment match the table). Emissions diverge as target 1b records. Suite: 14 passed. |
| 2026-08-04 | n/a (clean-room, manual only) | n/a | **Reimplementation milestone 1 gate PASS**: §2.2 transactions and balance-sheet matrices transcribed to `model/accounting.py`, §5 Tables 5–6 transcribed in full to `model/calibration.py`; every Table 1/2 row and column identity holds on the §5 initial values within the manual's 4-significant-figure printing precision (`tests/test_accounting.py`, 27 identity tests). Known manual inconsistency pinned: Table 6 LENDM_ROW omits the DIVN_ROW term of Eq. (383), so MFI/RoW transaction columns miss LEND by ∓DIVN_ROW (= 5.44; the manual itself tabulates overall LENDM = 5.44 where it "should equal 0"). Suite: 76 passed, 1 skipped. |

| 2026-08-04 | `846081a` | cached run | **Scenario surface gated against the pinned oracle**: `define_uk.scenarios` enumerates all 22 `Variables_*.csv` scenarios across the four blocks (power-sector regulation under five expectation regimes) and returns annualised scenario-minus-baseline delta paths only, framed with mandatory caveats. `tests/test_scenarios.py`: deltas finite, baselines identical across block folders, sign sanity grounded in the cached numbers, 11 pinned delta points. Suite: 116 passed, 1 skipped. Published-figure comparison for targets 2/3 still pending (no machine-readable numbers found on define-model.org). |

| 2026-08-05 | `846081a` | cached run | **Targets 2/3 closed at the achievable ceiling; calibration computed.** Scenario-design gate added (`tests/test_scenario_design.py`, 10 tests: exact policy-switch sets per scenario + FMM 2023 anchors, GPI GDP peak +0.92% vs "≈+1%", baseline 2030 emissions 342.8 vs "just under 350"). External-comparator table now computed from the cached run and committed (`validation/baseline_vs_external.csv`, `define_uk.validation`, `tests/test_validation.py`). Own GPI multiplier **1.78** (cum ΔGDP/ΔSPEND_GVT, nominal) replaces the unusable upstream `Multiplier_Summary.csv`. Published sources catalogued in `validation/published_targets.json`. Suite: 130 passed, 1 skipped. |

| 2026-08-12 | n/a (audit; manual + committed artifacts only) | n/a | **Audit of the pinned manual findings.** Every transcribed §5 value re-checked against the PDF (661 entries; each value found on the manual page its source comment names, the two documented SUBS placeholders excepted), and every pinned discrepancy recomputed independently of the sector modules. All arithmetic reproduced. Three findings re-characterised rather than withdrawn: Eqs. (51)/(59)/(94)/(111) are **first-period jumps**, not manual contradictions, because Table 5 describes each parameter as a historical mean; the Eq. (51) "the equation is the corroborated one" claim is **withdrawn** (it evaluated the lagged Eq. (49) at contemporaneous unit costs — honouring the lag, the tabulated µ is the value consistent with the manual's own g = 1.019 quarterly); and Eq. (107)'s sign contradiction is **model-wide**, shared with Eqs. (177), (231) and (284). Eqs. (27), (104), (105), (132), (133) unified as one finding (Table 6's capital block is deflated at 1.031). One new gap found: §5 calibrates an electricity price long-run formation rule (`t_ELECswitch`, `P_ELECLR`) that §3 never prints, which is the likeliest account of Eq. (84). Publicly filed claims (issues #1, #2) all verified. Suite: 236 passed, 59 skipped. |

| 2026-11-05 | `846081a` | cached run (CSV reads only) | **Multiplier denominator caveat corrected.** ΔSPEND_GVT decomposed from the cached GPI + Green Bonds run: SPEND_GVTPS +91.2, OCONS_GVT +21.1, SOCB_GVT +8.0, GCF_GVT −2.3 (sum 118.0 vs 118.2). The "social benefits fall → upper-leaning" claim and the ΔGCF_GVTG impulse ratio are withdrawn; the leftover Batini 2021 comparator in `gpi_multiplier()` is removed. No reference number changed (1.78, 209.9, 118.2, 250.6 unchanged). |

| 2026-11-06 | `846081a` | cached run (CSV reads only) | **Scenario sweep and per-equation oracle comparison.** (1) Stock-flow consistency: the redundant equation LEND (sum of sectoral net lending) is zero to rounding in 28 of the 30 cached files; it fails in the fossil-fuel ban under no forward guidance (2035Q3, 2036Q1; \|LEND\| up to 74.56) and under unexpected enforcement (2033Q1; 14.63). `run_scenario` now refuses those two scenarios (`StockFlowInconsistent`); every served result carries `sfc_check`. (2) Every registered equation is evaluated on the oracle's own inputs over 2023Q1–2040Q4 in five files (118 equations): 68 reproduce within 2e-3 (4-significant-figure printing) in all five, GCF in four, 17 diverge (pinned, not yet diagnosed), 32 cannot be compared one at a time. Eq. (23) GCF diverges only in GPI + Green Bonds, by exactly SPEND_GVTPS (the oracle counts on-balance-sheet green power investment in GCF; the printed equation does not). (3) Zero shock = baseline holds in every column before 2023Q1 except MU in 2022Q4 (pinned). (4) Public green power capital equals cumulated public green power spending net of depreciation. `test_baseline_gdp_path_matches_oracle` is now a strict xfail instead of an error whenever a cache exists. No reference number changed. Tolerances in `reference_outputs.json` (`stock_flow_consistency`, `oracle_identity_residuals`). |
| 2026-11-06 (round 2) | `846081a` | cached run (CSV reads only) | **The 17 §3.3.2 divergences diagnosed, and the cause of both stock-flow breaks.** (1) No transcription error in the Python: every one of the 17 matches the manual as printed. Three (GOS_PS, RP_PS, NW_PS) were printing noise (small differences of large 4-significant-figure terms); the comparison now allows the propagated rounding of each equation's inputs, and they reproduce. Twelve depart from the manual and, in the five comparison files (none reaches the capacity ceiling), follow a form found from the CSVs alone (lag swaps, one-column and ratio searches; pinned in `tests/test_oracle.py::ORACLE_FORMS`): timing, Eq. (82) MC_FF divides by E_ELECFF at t-1; Eq. (84) P_ELEC = MU_ELEC·MC_ELEC, not (1+MU_ELEC)·MC_ELEC (as printed, 81% higher); Eq. (111) RESTR_PS = η_PSB·GO_PS, not η_PSB·GDP_{t-1} (as printed, about 22x); Eq. (109) EQLTR_PS share is GO_PS/GO, not θ_psb; Eq. (93) DIVR_PS divides by EQL_NMFI − EQN_RoW; power subsidies (SUBS_PS > 0 from 2027Q1 in every file except GPI + Green Bonds, baseline included) enter Eq. (92) YD_PS, Eq. (102) GCF_PS and Eq. (105) GCF_PSNFFR in full and cut Eq. (101) GCF_PSNFF by 0.5·SUBS_PS before rationing; the fossil-fuel ban sets desired fossil investment to zero from 2032Q1 in the mixed policy (Eqs. (97)-(98) print no ban branch); Eq. (23) GCF adds SPEND_GVTPS − SUBS_PS (the on-balance-sheet part). Two remain parameter gaps already on DEFINE_UK_1.1#2 (prop_NFF, CR_PS), and DEF_PS misses at the 2030 illiquidity spike in two files (not diagnosed). The registry keeps the manual form throughout. (2) Both refused solves have one cause: in exactly their three failing quarters, and in no other quarter of the 30 files, GO_PS ≠ GO_PSR·P_ELEC (Eq. (74)). GO_PS is valued at P_ELECLR while buyers pay P_ELEC; the gap is 122.54, 81.79 and 24.03 and LEND is −0.61 times it each time. These are the quarters where the ban pushes generation against capacity, so the price changes regime (§3.3.2 footnote 22). The break is in the upstream output, so the refusal stands; `sfc_check` now reports the gap. (3) No size/sign shock variants: the Python model cannot solve a scenario (§3.3.3 and §3.4 are stubs) and the review machine lacks 16 of the upstream R packages. Disclosure: during this round the upstream Rmd was grepped once for the divergent variable names before the protocol was rechecked; no equation in `src/define_uk/model/` was changed, and every form above is pinned by output arithmetic. No reference number changed. |
| 2026-11-06 (round 3) | `846081a` | cached run (CSV reads only) | **§3.3.3 implemented and the first solved paths.** §3.3.3 Eqs. (139)-(158) transcribed; 19 of 20 reproduce the oracle in all five comparison files; Eq. (139) α_PP departs only in the Baseline (all 8 Baseline files print 0.2748, all 22 (corrected 2026-11-17 from 7/23) policy files Table 5's 0.2762, so every published policy-minus-baseline delta also carries a 0.5% change in production's own-input coefficient). Table 6 α_PPS (0.2006) equals α_FUELPS + α_OPPS, i.e. Eq. (144) at P_FUEL/P_P = 1, not the tabulated 1/1.035 (0.1962). Scenario solver `solve_path` (block-exogenous: §3.1/§3.4 from the reference). Baseline solve: GDP within 0.41% (empirical forms) / 0.43% (manual) every quarter, P within 1.21%, power-sector investment and finance not reproduced (Eq. (96) α_0GCFPS gap), Σ LEND up to 8.5 / 48 against 0.05 in the oracle. Zero shock = baseline bit for bit. Green public investment shock (the GPI + Green Bonds ΔSPEND_GVTPS and ΔK_GVTNFFR paths × ±0.5, ±1; cum ΔSPEND 91.23): sign positive, linear and symmetric (real GDP 0.07%/0.29%), cum nominal ΔGDP = ΔSPEND exactly (multiplier 1.00 in this closure, against the oracle's 2.30) and exactly zero under the manual as printed (Eq. (23) has no SPEND_GVTPS term, Eq. (272) GCF_GVT is exogenous). No reference number changed. |
| 2026-11-06 (round 4) | `846081a` | cached run (CSV reads only) | **Whole model implemented and solved; stock-flow closure found.** §3.1 Eqs. (1)-(20) and §3.4.1-§3.4.7 Eqs. (159)-(401) transcribed (every printed equation now registered). One-step against the oracle with print bounds: 247 of 262 new equations reproduce in all five comparison files. Bug fixed: the CSV alias map held only lambda/MU, so round-3 solves froze r_IBA_PS, r_IBL_PS, r_IBL_GVT, OTEQL_NMFI, WS (and others) at Table 6 (round-3 GDP unaffected; RP_PS worst miss 56.7 → 11.3). Closure: Σ LEND = 0 is the redundant equation with MFIs as residual sector; as printed it leaks through the dividend row (Σ LEND 5.87 in 2023Q1 → 72.9 by 2040Q4); the oracle's forms (DIVR_NFC residual, DIVR_HH over EQL_NMFI − EQN_RoW, DIVR_NMFI net of DIVN_RoW, Eq. (281) SUBS_GVT = SPEND_GVTPS) close it to machine precision every quarter (`forms="empirical"`). Also found: Eq. (18) theta_P exponent sign (as printed theta_P < 0). Whole-model baseline does not reproduce: GDP up to 44% low (empirical) / 48% (manual) by 2040, driven by the undiagnosed equity-revaluation forms Eqs. (184), (240), (113) through household wealth (Eq. (318)); holding the 15 undiagnosed equations at the oracle gives GDP within 2.2% and consumption within 0.1% (diagnostic). Zero shock = baseline bit for bit. GPI ±50/±100%: nominal GDP positive, linear within 0.5%, −1x/+1x 1.09; cum ΔGDP/ΔSPEND 1.57 against the oracle's 2.30 (0 under the manual as printed). No reference number changed. |
| 2026-11-06 (round 5) | `846081a` | cached run (CSV reads only) | **The Baseline/policy α_PP mismatch, sized.** `Parameters-sorted_*.csv`: alpha_PPLR is the only parameter outside the policy switches that differs (Baseline 0.2748 in all 8, policy 0.2762 in all 22 (corrected 2026-11-17 from 7/23); the gap is 28× the print half-unit, not rounding; the 2022Q4 calibrated mark-up MU already differs, 0.176 vs 0.1704). All 16 distinct policy files are identical in every column through 2026Q4, so no switch acts before 2027Q1 and the 2023Q1–2026Q4 deltas are the α_PP effect alone: real GDP +3.1 in 2023Q1, settling at −1.1 a quarter (−0.16%) through 2026, nominal GDP +0.25, UPLOT +0.037, EMIS −0.02. The pinned GPI 2026 real-GDP delta (−1.125) is therefore no policy effect, and the docstring's "GPI depresses GDP in the first years" reading is withdrawn. After 2027Q1 the effect is unobserved; extrapolating it as zero / the 2026Q4 level / the 2026Q4 share of baseline: multiplier 1.78 → 1.73–1.75 (policy only), GPI GDP peak +0.92% → +0.92–1.08%, cumulative real ΔGDP 250.6 → 252–325, housing-regulation 2035 ΔGDP_R −2.3 → −0.96 to −2.3, fossil-fuel-ban 2030 −3.85 → −2.65 to −3.85, emissions deltas < 0.25%. `tests/test_alpha_pp_confound.py` (3, cached-run). No reference number changed. |
| 2026-11-13 (r9) | `846081a` | cached run (CSV reads only) | **Balance sheet of the whole-model solve.** Σ LEND = 0 (the round 4 closure) checks flows only. Summing financial net worth across the seven sectors on the solved empirical baseline gave 0.18 in 2023Q1 drifting to −18.5 by 2040Q4, all in the equity row (EQA_NMFI ≠ EQL_NFC + EQL_PS): the Eq. (109) form gives the power sector the share GO_PS/GO of EQATR_NMFI while Eq. (179) still gave NFCs 1 − θ_psb. The oracle's NFC share is 1 − GO_PS/GO within the printing bound in every quarter of the 28 stock-flow-consistent files (largest residual/bound 0.83; the manual form 20–23x), so Eq. (179) joins the empirical forms (19) and leaves the undiagnosed list (14). Every financial row of Table 2 now holds to 1e-8, and Σ FNW_s stays fixed to 1.2e-8 (float rounding on stocks of order 1e4), in every solved quarter (`test_empirical_whole_model_balance_sheet_closes_every_quarter`). The same check on the cached CSVs: all 28 served files close; the two refused fossil-fuel-ban solves break in the same three quarters as LEND, by more (Σ FNW 509 and 183). Whole-model GPI multiplier 1.57 → 1.56 (cum ΔGDP 143.0 → 142.7); baseline GDP gap unchanged (44%). No reference number changed. |
| 2026-11-15 | `846081a` | cached run (CSV reads only) | **Oracle carry-overs in the whole-model solve closed (issue #24).** Audit: of the CSV columns the registered equations read but do not determine, five are endogenous in the oracle and move under GPI: INF_A, ITAX_PSFF, ITAX_PSNFF and the documented r_KFF/r_KNFF (Eq. (99)); the rest are policy paths, demography, world prices, or second lags the solver already updates. The manual prints no equation for INF_A (only Eq. (397) and Table 6, "Free", from ONS CPI) or for the ITAX_PS split (Table 6 cites Eqs. (281)-(282), the government lending equations). Forms found from the CSVs: INF_A = (P_P/P_P(-1))^4 - 1 is inside the 4 s.f. printing bound in all 2,160 file-quarters 2023Q1-2040Q4 of the 30 files (worst 0.98); the linear 4(P_P/P_P(-1) - 1) exceeds the bound in about 20 file-quarters (up to 12x, served files included) and the log form in about 26 (up to 17x; counts vary by one with the bound's rounding convention); the GDP deflator P misses in about a quarter of them, by up to 0.17; P_E prints identical to P_P. ITAX_PSNFF = ITAXR_PS GO_PS beta_NFF and ITAX_PSFF = ITAXR_PS GO_PS (1 - beta_NFF) + COV_ETSPS P_ETS EMIS_ELEC within ~1e-3 relative everywhere (lagged beta_NFF misses by 19%). GOS_P (Eq. (159) gap, GO_P - COST_P) is now written into the solved state; the CSVs satisfy it to printing (|gap| <= 1.0 on ~400). All four registered under the equation that reads or splits them (tags [INF], [NFF], [FF], [GOS]) and reproduce the oracle in all five comparison files. Effect (empirical whole model, GPI +100%): r_BOE now moves +0.044pp / -0.066pp at the extremes (oracle +0.076 / -0.194; exactly 0 before); cum ΔGDP/ΔSPEND_GVTPS 1.568 → 1.528, all from INF_A (the ITAX split alone leaves 1.568); baseline GDP gap 44.2% → 43.7%; baseline r_BOE 2040Q4 0.0386 (oracle 0.0336); Σ LEND ≤ 4e-11. Measured without the Eq. (179) equity form; with it (#25, merged first) the multiplier is 1.525 (1.52), GDP gap 43.7%, Σ FNW constant. No reference number changed. |
| 2026-11-15 (#16) | `846081a` | cached run (CSV reads only) | **Headline multiplier definition decided (issue #16, option B).** `gpi_multiplier()` takes a `definition`; the default `"impulse"` divides cum ΔGDP 209.9 by cum ΔSPEND_GVTPS 91.2 = **2.30**, the policy instrument; `"total_spending"` gives the former headline 1.78 (/ ΔSPEND_GVT 118.2) and is returned as `secondary`. `reference_outputs.json` re-pinned (2.30, 91.2; secondary 1.78, 118.2). α_PP-adjusted range for the headline 2.08–2.25 (secondary 1.73–1.75, unchanged method), pinned in `tests/test_alpha_pp_confound.py`. The "TotalDeltaG matches no variable" text in `gpi_multiplier()` corrected: it is upstream's real G, 104.1 recomputed. |
| 2026-11-16 | `846081a` | cached run (CSV reads only) | **Table 4 re-checked in full.** All 15 rows × 5 statistics compared (sd = sample sd of the 16 annual means 2025–2040, which reproduces the table's population and labour-force sd). Exogenous inputs and the macro/NFC block match; the power/energy block, emissions and trade shares diverge (target 1b). The growth explanation is corrected: the 2025 miss is not an annualisation convention (no single convention fits all three years). The emissions gap is decomposed: ~30% of the 2040 gap is the faster power decarbonisation (back-of-envelope); the rest cannot be attributed from Table 4. New committed `validation/table4_scorecard.csv` and `tests/test_table4_scorecard.py`; "Proof at a glance" table added. No tolerance changed. |
| 2026-11-16 (scenarios) | `846081a` | cached run (CSV reads only) | **Served paths start at the policy start.** Every cached scenario departs from its baseline in 2023, but only because of the α_PP mismatch (#20); no policy acts before 2027Q1. `run_scenario` now starts at `policy_start_year` (the first quarter the cached policy files stop being identical, 2027Q1, read from the cache, not hard-coded) and returns 2027–2040 by default. `include_pre_policy=True` restores 2023–2026, flagged `policy_active=False`. Every result carries `baseline_parameter_mismatch`, because the mismatch persists after 2027. Units for GDP_R/CONS_R now read £ billion at 2022 prices (manual Table 6). The GPI "early-year GDP dip" is no longer a sign-sanity claim: it is the mismatch. No served value changed for any year ≥ 2027. |
| 2026-11-17 (results review) | `846081a` | cached run (CSV reads only) | **Fable 5.2 results-validity review at main: valid with caveats** (every served number faithful to the cached run; labelling and window issues). Fixed here: (1) the GPI multiplier is back-loaded — new `horizon_profile` (0.47 after one year from 2027Q1, 0.79 to 2031, 1.40 to 2034, 2.25 to 2040) and `from_policy_start` 2.25; the caveat that it sits above published estimates is reversed (it is below them at their horizons); the 2.30 headline (Vahid's decision, #16) is unchanged. (2) Batini et al. (2021), IMF WP/21/87, renewable 1.1–1.5, reinstated: the 2026-08-13 withdrawal as unlocatable was wrong. (3) New served caveat: every subsidy scenario lowers cumulative real GDP (green power subsidy −47 vs GPI +252); query to the authors drafted, not filed. (4) Capacity-constrained years flagged per result (`capacity_constrained`, E_ELEC ≥ 0.999·E_ELECMAX): `fossil_fuel_ban_subsidy__no_forward_guidance` 2032 (GDP −5.7%) is served and was hidden by 2030/2035 snapshots. (5) EMIS_ELEC/EMIS_NELEC units added so the GPI emissions split can be served: 2030 −49.1 Mt/yr = −25.8 electricity, −23.3 non-electricity. (6) File counts corrected (8 Baseline / 22 policy, not 7/23). No served value changed. |
| 2026-11-18 (scenario notes) | `846081a` | cached run (CSV reads only) | **Duplicate solves and the false-confidence ordering explained.** (1) Six of the 22 registered names are byte-identical to another name with equal parameter rows (16 distinct solves): Power Sector Subsidy is one parameter set under all five regime folders (CRED, GVT_CRED and ELEC_BUFFER keep the Baseline's values; the regime switches are set only in the ban scenarios), and the mixed block re-uses two single-policy solves. `list_scenarios()` / `run_scenario()` now carry `identical_to` and a leading caveat; no served value changed. (2) The regimes are parameter sets (`EXPECTATION_REGIMES`): fossil generation capital K_PSFFR is exactly zero from 2032Q1 in the six ban files with GVT_CRED = 1 and positive in the four with GVT_CRED = 0. (3) Fossil Fuel Ban, false confidence against mutual trust (they differ only in GVT_CRED and are identical through 2031Q4): cumulative EMIS 2027–2040 −416.95 against −398.47, a gap of −18.48, of which EMIS_NELEC −18.51 and EMIS_ELEC +0.02. Under mutual trust E_ELECMAX falls 130.6 → 78.1 in 2032Q1 (demand 79.5), generation is at the ceiling in 2032Q1–Q2, P_ELEC is 1.39× and 2.00× the false-confidence price in 2032Q2–Q3, beta_nfc dips to 0.075 / 0.062 (0.086), K_PGR is 4.0 lower at 2032Q4 and 1.5 lower at 2040Q4, and epsilon, theta_P and omega_NELEC (manual Eqs. (16), (18), (19)) stay on the less-green side. Control: Fossil Fuel Ban + Subsidy has no shortfall in either regime and a gap of 0.04. Not established: what ELEC_BUFFER does; the authors' definitions of the regimes (the manual does not name GVT_CRED). Detail: [docs/scenario-notes.md](docs/scenario-notes.md). Gated by `tests/test_scenario_sweep.py` (7 new cached tests; the seventh, `test_cross_regime_figures_in_the_notes`, added in review, gates the by-regime figures in the notes) and `tests/test_scenarios.py::test_identical_scenarios_are_declared` (hermetic). |
| 2026-11-18 (multiplier window) | `846081a` | cached run (CSV reads only) | **Headline multiplier measured from the policy start: 2.25 (was 2.30).** Recomputed from `gvt_investment/Variables_{Baseline,GPI + Green Bonds}.csv`: full simulation 2023Q1–2040Q4 cum ΔGDP 209.9 / cum ΔSPEND_GVTPS 91.227 = 2.3009; policy window 2027Q1–2040Q4 205.1 / 91.227 = 2.2482. The difference is the four pre-policy years: ΔGDP 4.8, ΔSPEND_GVTPS exactly 0 (first non-zero delta 2027Q1). `gpi_multiplier()` now returns the policy-window ratio as `multiplier` (2.25; `cum_delta_gdp` 205.1, `cum_delta_gdp_real` 252.2) and the full-simulation ratio, at its earlier values, as `full_simulation` (2.30; 209.9; 250.6). The secondary moves with the window: 1.75 (205.1 / 117.0), with 1.78 (209.9 / 118.2) under `full_simulation`. The issue #16 denominator is unchanged. `validation/reference_outputs.json` is re-pinned accordingly (the earlier values are kept under `full_simulation`); no pinned tolerance changed (±0.01, ±0.5). **One re-banding, flagged:** the strict-xfail clean-room gate `tests/test_full_model.py::test_gpi_cumulative_multiplier_matches_the_oracle` moves from `approx(2.30, rel=0.1)` (2.07–2.53) to `approx(2.25, rel=0.08)` (2.07–2.43): the lower edge is held, the upper edge tightens, and the band still contains the α_PP range 2.08–2.25. Review check (2026-11-19): the clean-room shock's ΔGDP is exactly 0 in every quarter 2023Q1–2026Q4 and its ratio is 1.52 on either window, so the policy window is the like-for-like comparator; the gate still fails as it should. The α_PP range is unchanged (2.08–2.25, 1.73–1.75); the new headline is its top. The clean-room comparison is now 1.52 against 2.25 (its shock has no pre-2027 delta); still not passed. |
| 2026-11-24 (gates) | `846081a` | cached run (CSV reads only) + clean-room solves | **Issue #20 is a property of the upstream run; the package now checks it instead of asserting it, and the stock side of stock-flow consistency is gated.** (1) *Cause.* The α_PP mismatch is in the cached run's own `Parameters-sorted_*.csv` files (Baseline 0.2748, every policy file 0.2762); both sets of files belong to the one cached run, so no code here sets it and none can remove it. The run cannot be redone here: 16 of the upstream's R packages are missing, and a matched Baseline needs a change to the upstream notebook, which the clean-room rule keeps closed to us. (2) *Gate.* `scenarios.parameter_check` compares each scenario's parameter row with its Baseline's. `run_scenario` returns it as `parameter_check`, refuses any non-lever difference other than the documented α_PPLR (`BaselineParameterMismatch`), and builds `baseline_parameter_mismatch` from the printed values. `POLICY_LEVERS` is exactly the set of other parameters that vary across the 30 files. The property itself, "Baseline and policy share every parameter except the levers", is a strict xfail (`tests/test_alpha_pp_confound.py`) that turns red when a matched Baseline is pinned. (3) *After 2026.* Clean-room counterfactual, α_PP 0.2748 against 0.2762 on the Baseline's inputs: real GDP −1.16 / −0.91 a quarter in 2026 (cached run −1.125) and −1.30 / −1.21 in 2040Q4 (all equations solved / the nine undiagnosed held at the oracle; figures with the forms of the next row). The effect does not fade, so "zero after 2026", the case behind 2.25 and behind +252 for cumulative real GDP, is the one this does not support; summed over 2027–2040 it is −77 / −58, the size of the "constant share" extrapolation (−74), which puts the policy-only cumulative real-GDP effect of green public investment near +310 to +330. Its nominal-GDP effect is 2 to 4 times the cached run's in 2026, rises where the cached run's falls, and differs by 60% between the two closures, so it does not size the multiplier. It does show that the 2.08–2.25 range (three extrapolations that hold the nominal effect at its 2026 level or share) is not a bound: a price effect that builds would put the policy-only multiplier well below 2.08. No published number is changed. (4) *Stock side.* `sfc_check` now also requires Σ sectoral financial net worth (FNW) = 0. It is below 4e-8 in every simulated quarter of 28 files; the two refused solves break it from their first flow break to 2040Q4 (|FNW| up to 509.3 and 182.4), so the refused set is unchanged. A simulated quarter that prints no LEND or FNW now fails (it was skipped). `StockFlowInconsistent` carries `scenario` and `sfc_check`. No served value changed. |
| 2026-11-24 (clean-room forms) | `846081a` | cached run (CSV reads only) + clean-room solves | **Six more oracle forms found from the cached outputs; the whole-model baseline GDP gap falls from 44% to 3.7% (issue #17). Milestone 2 is still not passed.** (1) *Eq. (318), household consumption.* The cached run follows ln C = α0 + α1 ln C(−1) + α2 ln YD(−1) + α3 ln FA(−1) with Table 5's four α_CHHP: an unrestricted regression of printed consumption growth on the three lags returns them to 3 figures, and the form reproduces every quarter of the five comparison files within 0.13 of the printing bound. The manual prints an error-correction form with a speed ε_CHHP that Table 5 does not give; reading α3 as that speed (the earlier transcription) put α1 and α2 on the wrong variables and missed by up to 4% a quarter. This one equation carried most of the 44%. (2) *Equity revaluations.* Eqs. (184) and (114): the cached run discounts dividends at r_IBL_GVT − β, not + β (DIVP/EQL − r_IBL_GVT = −0.00168 in every quarter; Table 5 gives β = 0.001676). Eq. (240): as printed, floored at zero. Eqs. (344) and (113): households and the power sector take the share β·EQA(−1)/(EQL_NMFI(−1) − EQN_RoW(−1)) of the NMFI revaluation, the same denominator as the dividend forms. All reproduce in the five files within 0.66 of the printing bound. The two power-sector ones had been listed as not evaluable although the CSVs print them. (3) *Whole-model baseline, nothing held* (`forms="empirical"`, now 25 forms): nominal GDP within 3.7% of the oracle in every quarter (1.2% low in 2040Q4), real GDP 1.7%, household consumption 4.9%, price level 2.1%, investment 4.1%; Σ LEND and every financial row still close to rounding. The manual as printed ends 48% low. Emissions end 85% **above** the oracle (power-sector parameter gaps), so the clean-room model says nothing about emissions. (4) *What the earlier diagnosis got wrong.* "Holding the undiagnosed equations at the oracle brings GDP within 2.2%" held consumption itself at the oracle. With the nine equations still undiagnosed held, GDP ends 5.1% low, worse than the free solve, and household disposable income 4.6% low: the remaining miss is not only in those nine, and the free solve's 3.7% rests partly on offsetting errors. (5) *Clean-room GPI multiplier:* 1.84 (was 1.52) against the cached run's 2.25; still back-loaded (0.29 after one year, above 1 from 2037). The policy-rate response is +0.080pp at its peak against the cached run's +0.076pp. (6) *Leads not closed:* Eq. (166) fits Table 5's three coefficients exactly with utilisation lagged one quarter, from 2023Q2 (2023Q1 misses by 3.8 printing bounds, so it is not adopted); Eq. (269) fits with an intercept of 0.0604 where Table 5 gives 0.05561. No served value changed: nothing served comes from the clean-room model. |

## External comparators (recorded 2026-08-04)

Beyond the oracle (pinned upstream run) and the published figures, the
baseline can be checked against external numbers. Manual §4.1 names the
authors' own calibration sources — OBR (2025) macro forecasts, NESO
current-policy emission pathways, NGFS scenarios — and manual Table 4
publishes baseline values, which already diverge from officials in places:

| Quantity | DEFINE-UK baseline (manual Table 4 / upstream run) | External | Verdict |
|---|---|---|---|
| Real GDP growth, 2025 | 4.96% (Table 4); 4.66% annual-mean, committed CSV | ONS 2025 calendar-year mean over 2024 = 1.31% (`uk_gdp_cvm` vintage 2026-07-26, the CSV's pinned value); OBR March 2026 EFO ≈ 1–2% | **Baseline far above outturn.** Manual says the baseline "should not be seen as a prediction"; treat levels/near-term growth as non-informative. |
| Real GDP growth, mean 2025–40 | 2.35% | OBR long-run ≈ 1.5–1.8% | High vs official. |
| Unemployment, 2025 | 4.31% (Table 4); 4.39% annual-mean, committed CSV | ONS MGSX 2025 annual mean 4.88% (quarters 4.6/4.7/5.0/5.2; the CSV's pinned value) | Below outturn by ~0.5pp on the CSV's like-for-like annual means. |
| Population 16+, 2025 | 55.66m | ONS 16+ population ≈ 56m | Consistent (Table 4 "population" is 16+, not total ~69m). |
| Labour force, 2025 | 35.97m | ONS ≈ 34–35m | Slightly high. |
| Total emissions, 2025 | 407 MtCO2e/yr | UK territorial GHG: 384 (2023), ≈ 371 provisional (2024), DESNZ | Above the actuals it should start from. |
| Emissions, 2030 | 382 MtCO2e/yr | NDC path (68% below 1990 ≈ 260); NESO current-policy | Manual itself notes it "falls significantly short" of the NDC — by design (current-policies baseline). |
| Green public investment cumulative multiplier | **2.25** by our own computation (cum ΔGDP 205.1 / cum ΔSPEND_GVTPS 91.2, the policy instrument; issue #16, decided 2026-11-15), and 1.75 per pound of total non-wage spending (/ cum ΔSPEND_GVT 117.0); nominal, from the policy start (2027Q1) to 2040Q4 (window since 2026-11-18; 2.30 and 1.78 over the full simulation from 2023); `define_uk.validation.gpi_multiplier`, pinned in `tests/test_validation.py`) | OBR capital-spending impact multiplier ≈ 1.0; Batini, di Serio, Fragetta and Melina (2021), IMF WP/21/87, renewable-energy investment 1.1–1.5 over a few years (withdrawn on 2026-08-13 as unlocatable, which was wrong; reinstated 2026-11-17) | **Below** both at their horizons (0.47 after one year from the policy start, 0.79 to 2031) and above them only cumulated to 2040 (2.25; 2.30 if the four pre-policy years are included); **not like-for-like** — see the four caveats below. Defensible as what this closure implies; not defensible as a direct comparison. The previously quoted ≈2.4 is the upstream table's real/real ratio (TotalDeltaGDP 250.76 / TotalDeltaG 104.22). It is not quoted here: its row label is shifted by one, and it uses a different impulse and real rather than nominal values (issue #16, where the impulse definition was decided on 2026-11-15). |
| `Multiplier_Summary.csv` M_Impact / M_4Q / M_8Q | −32.22 / −0.88 / 2.6 **identical across all 8 scenarios** | — | **Upstream artifact confirmed unusable** (2026-08-05): scenario-invariant multiplier columns (every policy scenario sets the common `GVT_ENERGY = 1` switch, so M_Impact measures that switch, not the policy). **Corrected 2026-11-06 (issue #16):** the totals do reconcile, once the labels are read correctly. The upstream multiplier chunk labels its rows one scenario off, so the row "Green Public Investment" is `Variables_GPI + Green Bonds.csv`: TotalDeltaG 104.22 is the cumulative delta of upstream's real G, (CONS_GVT + GCF_GVT + SPEND_GVTPS) at baseline prices (104.1 by our sum), and TotalDeltaGDP 250.76 its real-GDP delta (250.6). The earlier "unreproducible" reading was wrong. Superseded by `define_uk.validation.gpi_multiplier`. |

Since 2026-08-05 this table is COMPUTED, not prose: `define_uk.validation.
baseline_calibration()` recomputes every row from the cached pinned run
against pinned external observations, the result is committed as
`validation/baseline_vs_external.csv`, and `tests/test_validation.py` fails
on any drift between the committed artifact and a recomputation. (Values
there use the annual-mean convention, e.g. 2025 growth 4.66% vs Table 4's
4.96% — the same −0.30pp anchoring gap recorded under target 1a; emissions
are annualised from the quarterly EMIS flow, 401.5 in 2024.)

### The multipliers, qualified (2026-08-12; headline changed 2026-11-15; window changed 2026-11-18)

The headline is **2.25** and the secondary **1.75**, both measured from the
policy start (2027Q1) to 2040Q4: 205.1 / 91.227 = 2.2482 and 205.1 / 117.0 =
1.7530. Over the full simulation (2023Q1–2040Q4) the same ratios are 2.30 and
1.78 (209.9 / 91.227 = 2.3009; 209.9 / 118.2 = 1.7758). All four are
reproducible from the cached run and pinned.

History of the headline: 1.78 until issue #16 was decided on 2026-11-15
(option B: divide by the policy instrument), then 2.30, then 2.25 from
2026-11-18. The last change is to the window only; the #16 denominator is
kept. The reasons for the window:

- The two windows differ by the four pre-policy years 2023–26. In them
  ΔSPEND_GVTPS is exactly zero and ΔGDP sums to 4.8 (annual sums −2.0, +3.3,
  +2.5, +1.0), which is the α_PP mismatch (issue #20), not the policy. The
  full-simulation ratio therefore adds 4.8 to the numerator and nothing to
  the denominator.
- Served scenario paths have started at the policy start since #31, and the
  multiplier's own horizon profile is counted from it. One window for the
  paths, the profile and the headline.
- The discussion on issue #16 already said the chosen ratio "should be
  computed on 2027Q1 onwards or against a matched baseline".

2.25 is not a policy-only figure: it is the top of the 2.08–2.25 range in
point 4 below.

What does *not* hold is reading it straight against published
short-horizon figures. Four properties are carried as
`define_uk.validation.GPI_MULTIPLIER_CAVEATS` and gated hermetically by
`tests/test_committed_artifacts.py::test_the_multiplier_caveats_travel_with_the_number`:

1. **Horizon** (rewritten 2026-11-17; window 2026-11-18). Ours is
   cumulative from the policy start (2027Q1) to 2040, and back-loaded: 0.47
   after one year, 0.79 to 2031, 1.40 to 2034 and 2.25 to 2040
   (`gpi_multiplier()["horizon_profile"]`); the full-simulation 2.30 also
   includes 4.8 of pre-policy (α_PP) GDP delta. At the horizons of the
   published comparators — the OBR's ≈1.0 impact multiplier and Batini et
   al. (2021, IMF WP/21/87), 1.1–1.5 for renewable investment over a few
   years — it sits **below** them, not above. The earlier text said the
   opposite.
2. **Denominator** (corrected 2026-11-05). `SPEND_GVT` is total government
   spending excluding wages, `OCONS_GVT + SOCB_GVT + GCF_GVT + SPEND_GVTPS`
   (the identity holds in the cached run to CSV rounding, ≤0.13, over
   2027–2040). Table 6's components (58.03 + 82.8 + 20.76 = 161.59 vs a
   tabulated 161.6) omit `SPEND_GVTPS` only because it is zero at the start.
   In the GPI + Green Bonds run the cumulative ΔSPEND_GVT of 118.2 (full
   simulation) is **ΔSPEND_GVTPS +91.2** (government power-sector spending,
   most of the impulse), ΔOCONS_GVT +21.1, ΔSOCB_GVT **+8.0** and ΔGCF_GVT
   −2.3 (green ΔGCF_GVTG +17.0 offset by conventional ΔGCF_GVTC −19.3: the
   scenario substitutes green for conventional public investment). From the
   policy start the same items are 117.0 = +91.2, +20.7, +7.3 and −2.5
   (+17.0 offset by −19.4; the rounded items sum to 116.7, the rest is CSV
   rounding, as for 118.0 against 118.2 over the full simulation). The earlier text
   said social benefits *fall*, biasing 1.78 *up*; the cached run shows
   they rise, so that claim and "upper-leaning" are withdrawn. The direction
   of the denominator bias against an impulse-based multiplier is not
   established. The earlier proposed impulse ratio (cum ΔGDP / cum
   ΔGCF_GVTG) is also withdrawn: green GCF is a small, offset share of the
   impulse. The impulse definition (e.g. ΔSPEND_GVTPS alone, or ΔSPEND_GVTPS +
   ΔGCF_GVTG) was decided on 2026-11-15 (issue #16, option B). The headline
   divides by ΔSPEND_GVTPS alone: it is the variable the policy switch
   sets, and it leaves out the induced spending responses above. The ratio
   to ΔSPEND_GVT is kept as a secondary ratio per pound of total non-wage
   spending, not as an impulse multiplier. The rejected options were
   ΔSPEND_GVTPS + ΔGCF_GVTG (1.94 over the full simulation; partly
   endogenous, ignores the conventional offset) and upstream's real/real
   2.41 (not comparable with nominal ratios).
3. **Closure.** Demand-led, with a Kaldor–Verdoorn productivity equation
   (Eq. (31)) that makes a demand impulse raise productivity growth
   permanently, and real GDP not held to the supply ceiling (Eq. (38)). A
   multiplier above 1 over fourteen years is what this closure *implies*.
4. **Parameter mismatch** (added 2026-11-13, issue #20). The cached Baseline
   uses α_PPLR = 0.2748 and the GPI + Green Bonds run 0.2762, so both
   multipliers also carry that parameter change. The policy effect alone is
   not observed after 2026; extrapolating the α_PP effect as zero, its 2026Q4
   level or its 2026Q4 share of baseline gives 2.08–2.25 for the headline and
   1.73–1.75 for the secondary (round 5). Measuring from the policy start is
   the "zero" case, so the published 2.25 and 1.75 are the tops of those
   ranges: the window removes the pre-policy part of the mismatch, not its
   effect after 2026. The headline's range is wider because the mismatch
   moves ΔSPEND_GVT as well as ΔGDP but leaves ΔSPEND_GVTPS unchanged
   (`tests/test_alpha_pp_confound.py`).
   The same caveat now travels with every served scenario result
   (`define_uk.scenarios.CAVEATS`), gated by
   `tests/test_committed_artifacts.py::test_the_alpha_pp_mismatch_travels_with_every_served_number`.

Verdict: not a red flag about the implementation, and not a reason to
discount the deltas — but a reason to label the number precisely wherever it
is served.

Implication for the site: even after replication passes, near-term baseline
levels are not competitive with `obr-macro`/`boe-svar` and must never be
presented as forecasts; the defensible outputs are scenario *deltas* with
the demand-led caveat stated.

## Known blockers

- Upstream carries no license, so its code is never vendored or hosted; the
  hosting path is the clean-room reimplementation (REIMPLEMENTATION.md),
  validated against this oracle.
- Full-notebook runtime and R dependency set (26 packages incl. `seasonal`
  / X-13) are untested in CI.
