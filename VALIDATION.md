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
| GPI cumulative multiplier 1.78 (cum ΔGDP 209.9 / cum ΔSPEND_GVT 118.2; real cum 250.6) | own computation on cached run | abs ±0.01 (multiplier), ±0.5 (cumulants) | `test_validation.py` |
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
| Green public investment cumulative multiplier | **1.78** by our own computation (cum ΔGDP 209.9 / cum ΔSPEND_GVT 118.2, nominal, full simulation; `define_uk.validation.gpi_multiplier`, pinned in `tests/test_validation.py`) | OBR capital-spending impact multiplier ≈ 1.0 (an IMF "1.1–1.5, Batini et al. 2021" comparator was withdrawn on 2026-08-13: no such publication could be located) | Above the comparator, but **not like-for-like** — see the three caveats below. Defensible as what this closure implies; not defensible as a direct comparison. The previously quoted ≈2.4 is the upstream table's real/real ratio (TotalDeltaGDP 250.76 / TotalDeltaG 104.22). It is not quoted here: its row label is shifted by one, and it uses a different impulse and real rather than nominal values (issue #16, where the impulse definition is decided). |
| `Multiplier_Summary.csv` M_Impact / M_4Q / M_8Q | −32.22 / −0.88 / 2.6 **identical across all 8 scenarios** | — | **Upstream artifact confirmed unusable** (2026-08-05): scenario-invariant multiplier columns (every policy scenario sets the common `GVT_ENERGY = 1` switch, so M_Impact measures that switch, not the policy). **Corrected 2026-11-06 (issue #16):** the totals do reconcile, once the labels are read correctly. The upstream multiplier chunk labels its rows one scenario off, so the row "Green Public Investment" is `Variables_GPI + Green Bonds.csv`: TotalDeltaG 104.22 is the cumulative delta of upstream's real G, (CONS_GVT + GCF_GVT + SPEND_GVTPS) at baseline prices (104.1 by our sum), and TotalDeltaGDP 250.76 its real-GDP delta (250.6). The earlier "unreproducible" reading was wrong. Superseded by `define_uk.validation.gpi_multiplier`. |

Since 2026-08-05 this table is COMPUTED, not prose: `define_uk.validation.
baseline_calibration()` recomputes every row from the cached pinned run
against pinned external observations, the result is committed as
`validation/baseline_vs_external.csv`, and `tests/test_validation.py` fails
on any drift between the committed artifact and a recomputation. (Values
there use the annual-mean convention, e.g. 2025 growth 4.66% vs Table 4's
4.96% — the same −0.30pp anchoring gap recorded under target 1a; emissions
are annualised from the quarterly EMIS flow, 401.5 in 2024.)

### The 1.78 multiplier, qualified (2026-08-12)

The number is reproducible and the arithmetic checks (209.9 / 118.2 =
1.7758). What does *not* hold is reading it straight against published
short-horizon figures. Three properties are carried as
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
   ΔGCF_GVTG) is an open decision; no alternative number is published here.
3. **Closure.** Demand-led, with a Kaldor–Verdoorn productivity equation
   (Eq. (31)) that makes a demand impulse raise productivity growth
   permanently, and real GDP not held to the supply ceiling (Eq. (38)). A
   multiplier above 1 over fifteen years is what this closure *implies*.

Verdict: not a red flag about the implementation, and not a reason to
discount the deltas — but a reason to label the number precisely wherever it
is served, and a reason to settle the impulse definition before it is
compared to anyone else's.

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
