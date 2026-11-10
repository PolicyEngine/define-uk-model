# define-uk-model

Adapter for **DEFINE-UK**, the ecological stock-flow consistent (E-SFC) model
of the UK economy by Dafermos, Nikolaidi and co-authors
([define-model.org/define-uk](https://define-model.org/define-uk/)), for the
[PolicyEngine Macro](https://github.com/PolicyEngine/macro) suite.

> **Status: partially validated** (see `VALIDATION.md`). The baseline
> macro block reproduces the manual's Table 4 within tolerance (2025 growth
> −0.30pp against a ±0.31pp tolerance); baseline emissions run below the
> table, by 23% in 2040. The scenario surface is gated against the pinned
> oracle run only: no machine-readable published scenario results exist. The scenario
> surface is **local-only** — it reads a locally cached run of the
> unlicensed upstream code; nothing is hosted or redistributed — and
> **deltas-only**: baseline levels are not validated against outturns and
> must never be presented as forecasts. The defensible outputs are
> scenario-minus-baseline deltas under the model's demand-led closure,
> with the caveats every result carries.

## What DEFINE-UK is

An ecological stock-flow consistent macro model calibrated to UK national
accounting data, simulating the UK macrofinancial system and its
environmental impacts under climate-policy scenarios (fossil-fuel
regulation, power-sector subsidies, housing regulation, green public
investment). Two published versions exist: 1.0 and 1.1 (April 2026, adds
regulation policies), documented in the model manuals on the DEFINE site
and the paper *"Evaluating climate policy mixes in the UK: an E-SFC
approach"*.

## Licensing and what this repo does NOT contain

The upstream model code
([DEFINE-model/DEFINE_UK_1.1](https://github.com/DEFINE-model/DEFINE_UK_1.1))
is public on GitHub but **carries no license**, so this repository does not
vendor, copy, or redistribute any of it. Instead, `define_uk.upstream`
fetches the upstream repository **at a pinned commit** into a local cache at
run time, and the adapter runs it in place with R. If the DEFINE team
publishes a license or grants permission, vendoring at a pinned revision
(the pattern used by
[us-frb-model](https://github.com/PolicyEngine/us-frb-model)) becomes
possible; an upstream request is the first item in the roadmap below.

Code in this repository (the adapter, not the model) is AGPL-3.0, matching
PolicyEngine convention.

## Architecture

```
src/define_uk/
  upstream.py   # pinned-commit fetch + cache of DEFINE-model/DEFINE_UK_1.1
  runner.py     # runs the upstream Rmd scenarios via Rscript (subprocess)
  scenarios.py  # curated scenario surface over the CACHED upstream run
```

### Scenario surface (`define_uk.scenarios`)

`list_scenarios()` enumerates the 22 upstream scenarios (four blocks:
`gvt_investment`, `housing_regulation`, `power_sector_regulation` under
five expectation regimes, and `mixed`). `run_scenario(name)` returns
annualised **scenario-minus-baseline delta paths** (level and %) for
`GDP_R`, `EMIS`, `UPLOT`, `CONS_R` by default, with calendar years
(run anchored 1987Q1–2040Q4), provenance (pinned commit, cache path, R
run date), `result_type="scenario deltas"`, and mandatory caveats.
It only ever reads the locally cached run produced by
`define_uk.runner.run()` — it never runs R, and raises with instructions
when no cache exists. Every result carries `sfc_check`, and two scenarios
are refused (`StockFlowInconsistent`): the fossil-fuel ban under no forward
guidance and under unexpected enforcement, where the cached upstream output
breaks stock-flow consistency (net lending summed across sectors is not
zero; the break is the power-sector valuation gap in Eq. 74, issue #17). Gated by
`tests/test_scenarios.py` against the pinned oracle run. VALIDATION.md
targets 2/3 are closed at the achievable ceiling, not passed: scenario
design plus two coarse anchors from a conference version of the paper.

- **Pinned upstream revision:** `846081a580a6033159d5c421632ad8f0b30d0ded`
  (`DEFINE_UK_1.1@main`, fetched 2026-08-01).
- **R requirement:** R ≥ 4.0 with the packages listed in the upstream
  README; `runner.py` checks and reports what is missing rather than
  auto-installing.

## Roadmap

1. **Clean-room Python reimplementation** from the published Model Manual
   v1.1, under the protocol in
   [REIMPLEMENTATION.md](REIMPLEMENTATION.md) (`src/define_uk/model/`).
   The unlicensed upstream code is used only as a numerical oracle; the
   implementation is AGPL-3.0 and hostable like the suite's other adapted
   models, credited to the DEFINE authors as an independent implementation
   of their published design. Every printed equation is now registered
   and the whole model solves, but **it does not reproduce the oracle**:
   baseline GDP is up to 44% below the oracle by 2040 (15 equations
   undiagnosed, mainly the equity revaluations), and its green public
   investment multiplier is 1.57 against the oracle's 2.30. Milestone 1
   (accounting matrices) passes; milestone 2 is not passed. Every number
   this repo serves comes from the cached upstream R run. That run has its
   own caveat: its Baseline files use a different α_PP (0.2748) from its
   policy files (0.2762), so every published policy-minus-baseline delta
   carries part of that change; removing it moves the GPI multiplier from
   1.78 to about 1.73–1.75 (VALIDATION.md, round 5; issue #20).
2. **Replication gate:** reproduce the paper's headline scenario outputs
   (S1 baseline and at least two policy scenarios) and record them in
   `VALIDATION.md` with tolerances, as
   [boe-var-model](https://github.com/PolicyEngine/boe-var-model) and
   [us-hank-model](https://github.com/PolicyEngine/us-hank-model) do for
   their own targets (neither has validated response magnitudes).
3. **Adapter surface:** a `define_scenario` entry point in
   `policyengine-macro` (curated levers, model-unit validation, ScoreResult
   provenance), refusing anything unreplicated.
4. **Microsimulation connection:** macro→micro incidence of scenario
   household-income and energy-price paths through the PolicyEngine
   microsimulation, following the suite's `EconomicAssumptions` overlay
   pattern; no `score_reform` bridge unless a defensible statute mapping
   exists.

## PolicyEngine Macro

This model joins the suite behind
[policyengine-macro.vercel.app](https://policyengine-macro.vercel.app) —
open models with a common discovery, run, and validation surface.
