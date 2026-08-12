# Validation — DEFINE-UK replication gate

**Status: NOT VALIDATED.** No published DEFINE-UK result has been reproduced
by this adapter yet. Nothing built on this repository may present model
output as meaningful until this file records passing replications.

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
  the stated fuel-price normalisation.

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

## External comparators (recorded 2026-08-04)

Beyond the oracle (pinned upstream run) and the published figures, the
baseline can be checked against external numbers. Manual §4.1 names the
authors' own calibration sources — OBR (2025) macro forecasts, NESO
current-policy emission pathways, NGFS scenarios — and manual Table 4
publishes baseline values, which already diverge from officials in places:

| Quantity | DEFINE-UK baseline (manual Table 4 / upstream run) | External | Verdict |
|---|---|---|---|
| Real GDP growth, 2025 | 4.96% | ONS outturn ≈ 1% y/y (macro repo vintage `uk_gdp_cvm`, 2026Q1 y/y 0.9%); OBR March 2026 EFO ≈ 1–2% | **Baseline far above outturn.** Manual says the baseline "should not be seen as a prediction"; treat levels/near-term growth as non-informative. |
| Real GDP growth, mean 2025–40 | 2.35% | OBR long-run ≈ 1.5–1.8% | High vs official. |
| Unemployment, 2025 | 4.31% | ONS MGSX outturn 5.2% (2025Q4), 5.0% (2026Q1) | Below outturn by ~0.8pp. |
| Population 16+, 2025 | 55.66m | ONS 16+ population ≈ 56m | Consistent (Table 4 "population" is 16+, not total ~69m). |
| Labour force, 2025 | 35.97m | ONS ≈ 34–35m | Slightly high. |
| Total emissions, 2025 | 407 MtCO2e/yr | UK territorial GHG: 384 (2023), ≈ 371 provisional (2024), DESNZ | Above the actuals it should start from. |
| Emissions, 2030 | 382 MtCO2e/yr | NDC path (68% below 1990 ≈ 260); NESO current-policy | Manual itself notes it "falls significantly short" of the NDC — by design (current-policies baseline). |
| Green public investment cumulative multiplier | **1.78** by our own computation (cum ΔGDP 209.9 / cum ΔSPEND_GVT 118.2, nominal, full simulation; `define_uk.validation.gpi_multiplier`, pinned in `tests/test_validation.py`) | IMF green-spending multipliers ≈ 1.1–1.5 (Batini et al. 2021); OBR capital-spending impact multiplier ≈ 1.0 | Above but near the IMF range under the demand-led closure; label accordingly. The previously quoted ≈2.4 came from the upstream table's ΔG=104.22, which matches the cumulative delta of **no variable** in the scenario file — do not quote it. |
| `Multiplier_Summary.csv` M_Impact / M_4Q / M_8Q | −32.22 / −0.88 / 2.6 **identical across all 8 scenarios** | — | **Upstream artifact confirmed unusable** (2026-08-05): scenario-invariant multiplier columns, and TotalDeltaG unreproducible from the scenario files (TotalDeltaGDP=250.76 does reconcile: it is the cumulative quarterly real-GDP delta of `Variables_GPI + Green Bonds.csv`, 250.6 by our sum). Superseded by `define_uk.validation.gpi_multiplier`. |

Since 2026-08-05 this table is COMPUTED, not prose: `define_uk.validation.
baseline_calibration()` recomputes every row from the cached pinned run
against pinned external observations, the result is committed as
`validation/baseline_vs_external.csv`, and `tests/test_validation.py` fails
on any drift between the committed artifact and a recomputation. (Values
there use the annual-mean convention, e.g. 2025 growth 4.66% vs Table 4's
4.96% — the same −0.30pp anchoring gap recorded under target 1a; emissions
are annualised from the quarterly EMIS flow, 401.5 in 2024.)

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
