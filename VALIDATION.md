# Validation — DEFINE-UK replication gate

**Status: NOT VALIDATED.** No published DEFINE-UK result has been reproduced
by this adapter yet. Nothing built on this repository may present model
output as meaningful until this file records passing replications.

## Standard

Same bar as the suite's other replications (boe-var-model, us-hank-model):

1. Run the pinned upstream code unmodified (`define_uk.runner.run`).
2. Compare against the published scenario outputs of *"Evaluating climate
   policy mixes in the UK: an E-SFC approach"* and the DEFINE-UK 1.1 manual
   (S1 baseline plus at least the fossil-fuel-ban and green-public-investment
   scenarios).
3. Record here: figure/table replicated, tolerance, result, upstream commit,
   R version, date.

## Targets (to fill)

| # | Published output | Scenario | Tolerance | Status |
|---|------------------|----------|-----------|--------|
| 1 | — | S1 baseline | — | pending |
| 2 | — | power-sector regulation (S1–S4) | — | pending |
| 3 | — | green public investment (S8–S9) | — | pending |

## Run record

| Date | Upstream commit | R | Result |
|------|-----------------|---|--------|
| 2026-08-01 | `846081a` | 4.3.0 (macOS) | Full notebook renders end to end via `define_uk.runner.run` (rstudioapi shim; upstream unmodified). 151 output files: figures and tables for all four scenario blocks plus `tables/Multiplier_Summary.csv`. **Execution ≠ validation**: no comparison against the published figures/tables has been made yet, so every target above remains pending. |

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
| Green public investment cumulative multiplier | ≈ 2.4 (ΔGDP 250.76 / ΔG 104.22, `Multiplier_Summary.csv`) | IMF green-spending multipliers ≈ 1.1–1.5 (Batini et al. 2021); OBR capital-spending impact multiplier ≈ 1.0 | High — plausible only under strong demand-led assumptions; label accordingly. |
| `Multiplier_Summary.csv` M_Impact / M_4Q / M_8Q | −32.22 / −0.88 / 2.6 **identical across all 8 scenarios** | — | **Upstream artifact**: scenario-invariant multiplier columns are almost certainly a computation bug in the upstream table (an impact multiplier of −32 is absurd). Do not quote; verify against our own delta computation when the reimplementation reaches milestone 5. |

Implication for the site: even after replication passes, near-term baseline
levels are not competitive with `obr-macro`/`boe-svar` and must never be
presented as forecasts; the defensible outputs are scenario *deltas* with
the demand-led caveat stated.

## Known blockers

- Upstream carries no license; hosting results publicly should wait on the
  DEFINE team's response (see README roadmap item 1).
- Full-notebook runtime and R dependency set (26 packages incl. `seasonal`
  / X-13) are untested in CI.
