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

## Upstream queries

Findings raised with the DEFINE authors on their own tracker, so the record
here and the record there stay in step:

- [DEFINE_UK_1.1#1](https://github.com/DEFINE-model/DEFINE_UK_1.1/issues/1) —
  which code vintage produced Model Manual v1.1 Table 4; the emissions path at
  `846081a` runs below the published values.
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
| Baseline real GDP growth (2025/2030/2040) | Manual v1.1 Table 4 | abs ±0.31 pp (annualisation convention; 2030/2040 match to 0.06pp) | `test_replication_baseline.py` |
| Baseline unemployment (2025/2030/2040) | Manual v1.1 Table 4 | abs ±0.2 pp | `test_replication_baseline.py` |
| Baseline emissions vs Table 4 | observed divergence ratios 0.965 / 0.898 / 0.767 (target 1b — a known vintage gap, gated so further drift fails) | abs ±0.02 on the ratio | `test_replication_baseline.py` |
| 11 pinned scenario-minus-baseline delta points (GDP_R, EMIS, UPLOT across GPI, housing regulation, fossil-fuel ban, mixed) | cached pinned run | rel 1e-6 | `test_scenarios.py::test_pinned_delta_points` |
| Scenario sign structure and cross-scenario ordering (deltas finite, baselines identical across blocks, EMIS falls everywhere by 2035, mixed dominates) | cached pinned run | exact sign / ordering | `test_scenarios.py` |
| Scenario design: exact policy-switch set per scenario; FMM 2023 anchors (GPI GDP peak +0.92% vs "≈+1%"; 2030 baseline emissions 342.8 vs "just under 350") | manual Table 5 / FMM 2023 | exact flags; wide anchors | `test_scenario_design.py` |
| GPI cumulative multiplier 2.30 (cum ΔGDP 209.9 / cum ΔSPEND_GVTPS 91.2; headline since 2026-11-15, issue #16), secondary 1.78 (/ cum ΔSPEND_GVT 118.2); real cum 250.6 | own computation on cached run | abs ±0.01 (multiplier), ±0.5 (cumulants) | `test_validation.py` |
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

## Targets (to fill)

| # | Published output | Scenario | Tolerance | Status |
|---|------------------|----------|-----------|--------|
| 1a | Manual Table 4, macro block (real GDP growth, unemployment, population 16+, labour force at 2025/2030/2040) | S1 baseline | pop/LF ±0.01m; growth ±0.31pp; unemployment ±0.2pp | **PASS** (2026-08-04, `tests/test_replication_baseline.py`; calendar anchored on the population path: run = 1987Q1–2040Q4, 2025 = t153) |
| 1b | Manual Table 4, total emissions | S1 baseline | — | **DIVERGENCE**: pinned code runs BELOW the published table, widening with horizon — 393 vs 407 (2025, −3.5%), 343 vs 382 (2030, −10%), 249 vs 324 (2040, −23%) MtCO2e/yr; components (EMIS_NELEC+EMIS_ELEC) sum exactly to EMIS and the baseline is identical across scenario folders, so this is a vintage/calibration gap between the published table and commit `846081a`, not an extraction error. Gated at the observed ratios so further drift fails loudly. |
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
| 2026-11-06 (round 3) | `846081a` | cached run (CSV reads only) | **§3.3.3 implemented and the first solved paths.** §3.3.3 Eqs. (139)-(158) transcribed; 19 of 20 reproduce the oracle in all five comparison files; Eq. (139) α_PP departs only in the Baseline (all 7 Baseline files print 0.2748, all 23 policy files Table 5's 0.2762, so every published policy-minus-baseline delta also carries a 0.5% change in production's own-input coefficient). Table 6 α_PPS (0.2006) equals α_FUELPS + α_OPPS, i.e. Eq. (144) at P_FUEL/P_P = 1, not the tabulated 1/1.035 (0.1962). Scenario solver `solve_path` (block-exogenous: §3.1/§3.4 from the reference). Baseline solve: GDP within 0.41% (empirical forms) / 0.43% (manual) every quarter, P within 1.21%, power-sector investment and finance not reproduced (Eq. (96) α_0GCFPS gap), Σ LEND up to 8.5 / 48 against 0.05 in the oracle. Zero shock = baseline bit for bit. Green public investment shock (the GPI + Green Bonds ΔSPEND_GVTPS and ΔK_GVTNFFR paths × ±0.5, ±1; cum ΔSPEND 91.23): sign positive, linear and symmetric (real GDP 0.07%/0.29%), cum nominal ΔGDP = ΔSPEND exactly (multiplier 1.00 in this closure, against the oracle's 2.30) and exactly zero under the manual as printed (Eq. (23) has no SPEND_GVTPS term, Eq. (272) GCF_GVT is exogenous). No reference number changed. |
| 2026-11-06 (round 4) | `846081a` | cached run (CSV reads only) | **Whole model implemented and solved; stock-flow closure found.** §3.1 Eqs. (1)-(20) and §3.4.1-§3.4.7 Eqs. (159)-(401) transcribed (every printed equation now registered). One-step against the oracle with print bounds: 247 of 262 new equations reproduce in all five comparison files. Bug fixed: the CSV alias map held only lambda/MU, so round-3 solves froze r_IBA_PS, r_IBL_PS, r_IBL_GVT, OTEQL_NMFI, WS (and others) at Table 6 (round-3 GDP unaffected; RP_PS worst miss 56.7 → 11.3). Closure: Σ LEND = 0 is the redundant equation with MFIs as residual sector; as printed it leaks through the dividend row (Σ LEND 5.87 in 2023Q1 → 72.9 by 2040Q4); the oracle's forms (DIVR_NFC residual, DIVR_HH over EQL_NMFI − EQN_RoW, DIVR_NMFI net of DIVN_RoW, Eq. (281) SUBS_GVT = SPEND_GVTPS) close it to machine precision every quarter (`forms="empirical"`). Also found: Eq. (18) theta_P exponent sign (as printed theta_P < 0). Whole-model baseline does not reproduce: GDP up to 44% low (empirical) / 48% (manual) by 2040, driven by the undiagnosed equity-revaluation forms Eqs. (184), (240), (113) through household wealth (Eq. (318)); holding the 15 undiagnosed equations at the oracle gives GDP within 2.2% and consumption within 0.1% (diagnostic). Zero shock = baseline bit for bit. GPI ±50/±100%: nominal GDP positive, linear within 0.5%, −1x/+1x 1.09; cum ΔGDP/ΔSPEND 1.57 against the oracle's 2.30 (0 under the manual as printed). No reference number changed. |
| 2026-11-06 (round 5) | `846081a` | cached run (CSV reads only) | **The Baseline/policy α_PP mismatch, sized.** `Parameters-sorted_*.csv`: alpha_PPLR is the only parameter outside the policy switches that differs (Baseline 0.2748 in all 7, policy 0.2762 in all 23; the gap is 28× the print half-unit, not rounding; the 2022Q4 calibrated mark-up MU already differs, 0.176 vs 0.1704). All 16 distinct policy files are identical in every column through 2026Q4, so no switch acts before 2027Q1 and the 2023Q1–2026Q4 deltas are the α_PP effect alone: real GDP +3.1 in 2023Q1, settling at −1.1 a quarter (−0.16%) through 2026, nominal GDP +0.25, UPLOT +0.037, EMIS −0.02. The pinned GPI 2026 real-GDP delta (−1.125) is therefore no policy effect, and the docstring's "GPI depresses GDP in the first years" reading is withdrawn. After 2027Q1 the effect is unobserved; extrapolating it as zero / the 2026Q4 level / the 2026Q4 share of baseline: multiplier 1.78 → 1.73–1.75 (policy only), GPI GDP peak +0.92% → +0.92–1.08%, cumulative real ΔGDP 250.6 → 252–325, housing-regulation 2035 ΔGDP_R −2.3 → −0.96 to −2.3, fossil-fuel-ban 2030 −3.85 → −2.65 to −3.85, emissions deltas < 0.25%. `tests/test_alpha_pp_confound.py` (3, cached-run). No reference number changed. |
| 2026-11-13 (r9) | `846081a` | cached run (CSV reads only) | **Balance sheet of the whole-model solve.** Σ LEND = 0 (the round 4 closure) checks flows only. Summing financial net worth across the seven sectors on the solved empirical baseline gave 0.18 in 2023Q1 drifting to −18.5 by 2040Q4, all in the equity row (EQA_NMFI ≠ EQL_NFC + EQL_PS): the Eq. (109) form gives the power sector the share GO_PS/GO of EQATR_NMFI while Eq. (179) still gave NFCs 1 − θ_psb. The oracle's NFC share is 1 − GO_PS/GO within the printing bound in every quarter of the 28 stock-flow-consistent files (largest residual/bound 0.83; the manual form 20–23x), so Eq. (179) joins the empirical forms (19) and leaves the undiagnosed list (14). Every financial row of Table 2 now holds to 1e-8, and Σ FNW_s stays fixed to 1.2e-8 (float rounding on stocks of order 1e4), in every solved quarter (`test_empirical_whole_model_balance_sheet_closes_every_quarter`). The same check on the cached CSVs: all 28 served files close; the two refused fossil-fuel-ban solves break in the same three quarters as LEND, by more (Σ FNW 509 and 183). Whole-model GPI multiplier 1.57 → 1.56 (cum ΔGDP 143.0 → 142.7); baseline GDP gap unchanged (44%). No reference number changed. |
| 2026-11-15 | `846081a` | cached run (CSV reads only) | **Oracle carry-overs in the whole-model solve closed (issue #24).** Audit: of the CSV columns the registered equations read but do not determine, five are endogenous in the oracle and move under GPI: INF_A, ITAX_PSFF, ITAX_PSNFF and the documented r_KFF/r_KNFF (Eq. (99)); the rest are policy paths, demography, world prices, or second lags the solver already updates. The manual prints no equation for INF_A (only Eq. (397) and Table 6, "Free", from ONS CPI) or for the ITAX_PS split (Table 6 cites Eqs. (281)-(282), the government lending equations). Forms found from the CSVs: INF_A = (P_P/P_P(-1))^4 - 1 is inside the 4 s.f. printing bound in all 2,160 file-quarters 2023Q1-2040Q4 of the 30 files (worst 0.98); the linear 4(P_P/P_P(-1) - 1) exceeds the bound in about 20 file-quarters (up to 12x, served files included) and the log form in about 26 (up to 17x; counts vary by one with the bound's rounding convention); the GDP deflator P misses in about a quarter of them, by up to 0.17; P_E prints identical to P_P. ITAX_PSNFF = ITAXR_PS GO_PS beta_NFF and ITAX_PSFF = ITAXR_PS GO_PS (1 - beta_NFF) + COV_ETSPS P_ETS EMIS_ELEC within ~1e-3 relative everywhere (lagged beta_NFF misses by 19%). GOS_P (Eq. (159) gap, GO_P - COST_P) is now written into the solved state; the CSVs satisfy it to printing (|gap| <= 1.0 on ~400). All four registered under the equation that reads or splits them (tags [INF], [NFF], [FF], [GOS]) and reproduce the oracle in all five comparison files. Effect (empirical whole model, GPI +100%): r_BOE now moves +0.044pp / -0.066pp at the extremes (oracle +0.076 / -0.194; exactly 0 before); cum ΔGDP/ΔSPEND_GVTPS 1.568 → 1.528, all from INF_A (the ITAX split alone leaves 1.568); baseline GDP gap 44.2% → 43.7%; baseline r_BOE 2040Q4 0.0386 (oracle 0.0336); Σ LEND ≤ 4e-11. Measured without the Eq. (179) equity form; with it (#25, merged first) the multiplier is 1.525 (1.52), GDP gap 43.7%, Σ FNW constant. No reference number changed. |
| 2026-11-15 (#16) | `846081a` | cached run (CSV reads only) | **Headline multiplier definition decided (issue #16, option B).** `gpi_multiplier()` takes a `definition`; the default `"impulse"` divides cum ΔGDP 209.9 by cum ΔSPEND_GVTPS 91.2 = **2.30**, the policy instrument; `"total_spending"` gives the former headline 1.78 (/ ΔSPEND_GVT 118.2) and is returned as `secondary`. `reference_outputs.json` re-pinned (2.30, 91.2; secondary 1.78, 118.2). α_PP-adjusted range for the headline 2.08–2.25 (secondary 1.73–1.75, unchanged method), pinned in `tests/test_alpha_pp_confound.py`. The "TotalDeltaG matches no variable" text in `gpi_multiplier()` corrected: it is upstream's real G, 104.1 recomputed. |

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
| Green public investment cumulative multiplier | **2.30** by our own computation (cum ΔGDP 209.9 / cum ΔSPEND_GVTPS 91.2, the policy instrument; issue #16, decided 2026-11-15), and 1.78 per pound of total non-wage spending (/ cum ΔSPEND_GVT 118.2); nominal, full simulation; `define_uk.validation.gpi_multiplier`, pinned in `tests/test_validation.py`) | OBR capital-spending impact multiplier ≈ 1.0 (an IMF "1.1–1.5, Batini et al. 2021" comparator was withdrawn on 2026-08-13: no such publication could be located) | Above the comparator, but **not like-for-like** — see the four caveats below. Defensible as what this closure implies; not defensible as a direct comparison. The previously quoted ≈2.4 is the upstream table's real/real ratio (TotalDeltaGDP 250.76 / TotalDeltaG 104.22). It is not quoted here: its row label is shifted by one, and it uses a different impulse and real rather than nominal values (issue #16, where the impulse definition is decided). |
| `Multiplier_Summary.csv` M_Impact / M_4Q / M_8Q | −32.22 / −0.88 / 2.6 **identical across all 8 scenarios** | — | **Upstream artifact confirmed unusable** (2026-08-05): scenario-invariant multiplier columns (every policy scenario sets the common `GVT_ENERGY = 1` switch, so M_Impact measures that switch, not the policy). **Corrected 2026-11-06 (issue #16):** the totals do reconcile, once the labels are read correctly. The upstream multiplier chunk labels its rows one scenario off, so the row "Green Public Investment" is `Variables_GPI + Green Bonds.csv`: TotalDeltaG 104.22 is the cumulative delta of upstream's real G, (CONS_GVT + GCF_GVT + SPEND_GVTPS) at baseline prices (104.1 by our sum), and TotalDeltaGDP 250.76 its real-GDP delta (250.6). The earlier "unreproducible" reading was wrong. Superseded by `define_uk.validation.gpi_multiplier`. |

Since 2026-08-05 this table is COMPUTED, not prose: `define_uk.validation.
baseline_calibration()` recomputes every row from the cached pinned run
against pinned external observations, the result is committed as
`validation/baseline_vs_external.csv`, and `tests/test_validation.py` fails
on any drift between the committed artifact and a recomputation. (Values
there use the annual-mean convention, e.g. 2025 growth 4.66% vs Table 4's
4.96% — the same −0.30pp anchoring gap recorded under target 1a; emissions
are annualised from the quarterly EMIS flow, 401.5 in 2024.)

### The 2.30 and 1.78 multipliers, qualified (2026-08-12; headline changed 2026-11-15)

Both numbers are reproducible and the arithmetic checks (209.9 / 91.2 =
2.3009 headline; 209.9 / 118.2 = 1.7758 secondary). The headline was 1.78
until issue #16 was decided on 2026-11-15 (option B: divide by the policy
instrument). What does *not* hold is reading it straight against published
short-horizon figures. Four properties are carried as
`define_uk.validation.GPI_MULTIPLIER_CAVEATS` and gated hermetically by
`tests/test_committed_artifacts.py::test_the_multiplier_caveats_travel_with_the_number`:

1. **Horizon.** Ours is cumulative over the whole simulation to 2040. The
   OBR's ≈1.0 is a short-horizon (impact / few-year) multiplier. A
   long-horizon cumulative ratio is *expected* to exceed it, so a direct
   comparison overstates the disagreement.
2. **Denominator** (corrected 2026-11-05). `SPEND_GVT` is total government
   spending excluding wages, `OCONS_GVT + SOCB_GVT + GCF_GVT + SPEND_GVTPS`
   (the identity holds in the cached run to CSV rounding, ≤0.13, over
   2027–2040). Table 6's components (58.03 + 82.8 + 20.76 = 161.59 vs a
   tabulated 161.6) omit `SPEND_GVTPS` only because it is zero at the start.
   In the GPI + Green Bonds run the cumulative ΔSPEND_GVT of 118.2 is
   **ΔSPEND_GVTPS +91.2** (government power-sector spending, most of the
   impulse), ΔOCONS_GVT +21.1, ΔSOCB_GVT **+8.0** and ΔGCF_GVT −2.3 (green
   ΔGCF_GVTG +17.0 offset by conventional ΔGCF_GVTC −19.3: the scenario
   substitutes green for conventional public investment). The earlier text
   said social benefits *fall*, biasing 1.78 *up*; the cached run shows
   they rise, so that claim and "upper-leaning" are withdrawn. The direction
   of the denominator bias against an impulse-based multiplier is not
   established. The earlier proposed impulse ratio (cum ΔGDP / cum
   ΔGCF_GVTG) is also withdrawn: green GCF is a small, offset share of the
   impulse. The impulse definition (e.g. ΔSPEND_GVTPS alone, or ΔSPEND_GVTPS +
   ΔGCF_GVTG) was decided on 2026-11-15 (issue #16, option B). The headline
   2.30 divides by ΔSPEND_GVTPS alone: it is the variable the policy switch
   sets, and it leaves out the induced spending responses above. 1.78 is
   kept as a secondary ratio per pound of total non-wage spending, not as
   an impulse multiplier. The rejected options were ΔSPEND_GVTPS + ΔGCF_GVTG
   (1.94; partly endogenous, ignores the conventional offset) and upstream's
   real/real 2.41 (not comparable with nominal ratios).
3. **Closure.** Demand-led, with a Kaldor–Verdoorn productivity equation
   (Eq. (31)) that makes a demand impulse raise productivity growth
   permanently, and real GDP not held to the supply ceiling (Eq. (38)). A
   multiplier above 1 over fifteen years is what this closure *implies*.
4. **Parameter mismatch** (added 2026-11-13, issue #20). The cached Baseline
   uses α_PPLR = 0.2748 and the GPI + Green Bonds run 0.2762, so both
   multipliers also carry that parameter change. The policy effect alone is
   not observed after 2026; extrapolating the α_PP effect as zero, its 2026Q4
   level or its 2026Q4 share of baseline gives 2.08–2.25 for the headline and
   1.73–1.75 for the secondary (round 5). The headline's range is wider
   because ΔSPEND_GVTPS has no pre-2027 delta to offset the change in the
   numerator (`tests/test_alpha_pp_confound.py`).
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
