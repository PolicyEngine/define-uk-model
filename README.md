# define-uk-model

Adapter for **DEFINE-UK**, the ecological stock-flow consistent (E-SFC)
model of the UK economy by Dafermos, Nikolaidi, George and co-authors
([define-model.org/define-uk](https://define-model.org/define-uk/)), for the
[PolicyEngine Macro](https://github.com/PolicyEngine/macro) suite.

> **Status: partially validated.** Scenario results are
> **scenario-minus-baseline deltas only**, read from a locally cached run of
> the unlicensed upstream R model. They are never levels and never forecasts.
> What each claim rests on:
> [VALIDATION.md, "Proof at a glance"](VALIDATION.md#proof-at-a-glance).

## What it is

DEFINE-UK simulates the UK macrofinancial system and its emissions under
climate policies: fossil-fuel regulation, power-sector subsidies, housing
regulation and green public investment. It is demand-led and post-Keynesian,
calibrated to UK national accounts (Model Manual v1.1, April 2026). This
repository provides:

- `define_uk.scenarios`: the 22 upstream scenarios (16 distinct solves; six
  names repeat another, flagged `identical_to`) as annual delta paths, with
  caveats, provenance and a stock-flow check on every result.
- `define_uk.validation`: the comparison tables (manual Table 4, external
  outturns) and the green public investment multiplier.
- `define_uk.model`: a clean-room Python reimplementation from the manual.
  It solves, but does not reproduce the upstream yet (see Limits), and
  nothing served comes from it.

## Install and run

```bash
pip install -e .            # Python 3.11+; no Python dependencies
pytest -q                   # oracle tests skip without the cached run
```

The scenario surface needs a cached run of the upstream R model. Producing
it needs R 4.0+ and the upstream's R packages, and the render takes a long
time:

```python
from define_uk import runner
runner.check_r()   # lists missing R packages; installing them is your call
runner.run()       # fetches the pinned upstream commit and renders it once
```

Then, from the cache (no R needed):

```python
from define_uk import scenarios

scenarios.list_scenarios()                       # the 22 scenarios
r = scenarios.run_scenario("green_public_investment")
r["years"]                  # 2027 ... 2040: from the policy start
r["caveats"]                # read these before quoting any number
gdp = dict(zip(r["years"], r["variables"]["GDP_R"]["delta_pct"]))
emis = dict(zip(r["years"], r["variables"]["EMIS"]["delta_level"]))
gdp[2030]                   # +0.53: real GDP, % of baseline
4 * emis[2030]              # -49.1: MtCO2e per year (EMIS is quarterly)
```

Each result carries `policy_active` and `capacity_constrained` flags per
year, the `baseline_parameter_mismatch` (issue #20), `parameter_check`,
`sfc_check`, provenance and units. Years before the policy start
(2023–2026) are returned only with `include_pre_policy=True`, because they
contain no policy. Two gates refuse a cached solve:

- **Stock-flow consistency** (`StockFlowInconsistent`): sectoral net lending
  and sectoral financial net worth must each sum to zero in every quarter.
  Two cached solves fail both and are refused.
- **Shared parameters** (`BaselineParameterMismatch`): a scenario may differ
  from its Baseline only in its own policy levers, at their recorded values
  (`SCENARIO_LEVERS`; the table is
  [docs/scenario-levers.md](docs/scenario-levers.md)). The one documented
  exception is `alpha_PPLR` (issue #20), served with its caveat; any other
  difference is refused, including a lever that belongs to another
  scenario.

## Results

From the cached run, as deltas against the model's own baseline:

| Scenario | Real GDP, 2030 | Emissions, 2030 |
|---|---|---|
| Green public investment | +0.53% | −49.1 MtCO2e/yr (−14%) |
| Green power subsidy | −0.47% | −40.5 MtCO2e/yr |
| Housing regulation | −0.21% | −6.7 MtCO2e/yr |

- Emissions fall relative to baseline in every scenario by 2035.
- Every scenario with a subsidy lowers cumulative real GDP; the reason is
  not confirmed (VALIDATION.md, upstream queries).
- The fossil-fuel ban cuts slightly more under "false confidence" than under
  "mutual trust" (−417 against −398 MtCO2e over 2027–2040). The gap comes
  from a two-quarter electricity capacity shortfall in 2032 in the
  mutual-trust run, not from expectations; with the subsidy there is no
  shortfall and no gap ([docs/scenario-notes.md](docs/scenario-notes.md)).
- The **green public investment multiplier** is **2.25**: cumulative
  nominal ΔGDP over cumulative government power-sector spending
  (ΔSPEND_GVTPS, the denominator decided in issue #16), from the policy
  start in 2027 to 2040. Per pound of total non-wage government spending
  it is 1.75.
- Over the full simulation from 2023 the same ratios are 2.30 and 1.78 (the
  figures quoted before 18 Nov 2026). That window adds four years in which
  no policy acts.
- The multiplier is back-loaded: 0.47 after one year and below 1 through
  2032, so it sits below published short-horizon estimates (OBR about 1.0;
  IMF WP/21/87 1.1–1.5 for renewables), not above. Its caveats travel with
  it (`define_uk.validation.gpi_multiplier`).

## Validation

- **Manual Table 4:** all 15 rows are compared
  ([`validation/table4_scorecard.csv`](validation/table4_scorecard.csv)).
  - The inputs, the macro block and corporate finance match.
  - The power and energy block diverges: emissions are 23% below the table
    in 2040.
- **Published scenario results:** none exist for v1.1, so scenario design
  and two coarse paper anchors are gated instead.
- **Served deltas:** pinned to the cached run (`validation/reference_outputs.json`).
- **CI:** CI cannot hold the unlicensed upstream run, so it runs the
  hermetic half (`.github/workflows/validation-gate.yml`). The full oracle
  comparison runs wherever the cached run exists.

Details, tolerances and the run record: [VALIDATION.md](VALIDATION.md).

## Limits

- **Deltas only:** baseline levels sit far from outturns (2025 baseline
  growth is 4.7% against 1.3% outturn), and % deltas are relative to that
  baseline.
- **Parameter mismatch (issue #20):** the cached Baseline and policy files
  use different α_PP values, so every delta also carries that change.
  The multiplier's 2.25 assumes the change has no effect after 2026;
  otherwise it is as low as 2.08 by three extrapolations of the 2023–26
  effect. The mismatch is in the upstream run's own parameter files, so
  only an upstream re-run with a matched Baseline removes it. A clean-room
  counterfactual reproduces the 2026 real-GDP effect (−1.10 a quarter
  against −1.125) and finds it does not fade, and it does not support 2.08
  as a floor (VALIDATION.md, 2026-11-24).
- **Capacity years:** years at the electricity capacity ceiling (three
  served fossil-fuel-ban scenarios, all in 2032) are a price-regime switch
  and are flagged.
- **Duplicates:** the subsidy-only scenario is one solve under five
  expectation-regime labels, so comparing its variants compares a solve
  with itself ([docs/scenario-notes.md](docs/scenario-notes.md)).
- **Clean-room model:** every printed equation is transcribed and the whole
  model solves. With 39 forms found from the cached outputs (eight of them
  the upstream run's own parameter values, which differ from the manual's
  Table 5), baseline GDP is within 1.23% of the upstream in every quarter
  and emissions within 9.2% (issue #17; 44% low on GDP before the forms of
  24 Nov 2026, 85% high on emissions before those of 27 Nov). Its nominal
  GDP response to green public investment does not reproduce the
  upstream's, so it says nothing about the multiplier. With the manual as
  printed GDP ends 48% low. It is a diagnostic only.
  Protocol: [REIMPLEMENTATION.md](REIMPLEMENTATION.md).
- **Local only:** nothing is hosted and the upstream is never redistributed
  ([LICENSE-STATUS.md](LICENSE-STATUS.md)).

## Pins

- **Upstream:** [DEFINE-model/DEFINE_UK_1.1](https://github.com/DEFINE-model/DEFINE_UK_1.1)
  at `846081a580a6033159d5c421632ad8f0b30d0ded` (fetched 2026-08-01;
  `define_uk.upstream.UPSTREAM_COMMIT`).
- **Specification:** DEFINE-UK Model Manual v1.1 (George and Dafermos,
  April 2026).
- **Changing the pin** is a reviewed change tied to
  `validation/reference_outputs.json`.

## Layout

```
src/define_uk/
  upstream.py    pinned-commit fetch and cache of the upstream repository
  runner.py      renders the upstream notebook with Rscript
  scenarios.py   the served scenario surface (deltas, caveats, checks)
  validation.py  Table 4 scorecard, external comparators, GPI multiplier
  model/         clean-room reimplementation (registry, solver, sectors/)
validation/      committed reference artifacts gated by the tests
docs/            scenario notes (duplicate solves, expectation regimes)
tests/           hermetic tests (CI) and cached-run oracle tests
```

## Licence

The code in this repository (the adapter and the clean-room
reimplementation) is AGPL-3.0 ([LICENSE](LICENSE)). The upstream model
carries no licence, so it is fetched and run locally, never vendored. If the
DEFINE team grants a licence, vendoring at a pinned revision becomes
possible ([LICENSE-STATUS.md](LICENSE-STATUS.md)).
