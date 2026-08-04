# define-uk-model

Adapter for **DEFINE-UK**, the ecological stock-flow consistent (E-SFC) model
of the UK economy by Dafermos, Nikolaidi and co-authors
([define-model.org/define-uk](https://define-model.org/define-uk/)), for the
[PolicyEngine Macro](https://github.com/PolicyEngine/macro) suite.

> **Status: scaffold — pre-replication.** This repository contains the
> PolicyEngine adapter and validation harness only. It does not yet
> reproduce any published DEFINE-UK result, and nothing here should be used
> for analysis until `VALIDATION.md` records a passing replication of the
> paper's scenarios.

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
  scenarios.py  # curated scenario levers exposed to policyengine-macro
```

- **Pinned upstream revision:** `846081a580a6033159d5c421632ad8f0b30d0ded`
  (`DEFINE_UK_1.1@main`, fetched 2026-08-01).
- **R requirement:** R ≥ 4.0 with the packages listed in the upstream
  README; `runner.py` checks and reports what is missing rather than
  auto-installing.

## Roadmap

1. **License/permission request to the DEFINE team** (issue on the upstream
   repo + email), so the model can be vendored and hosted like the suite's
   other members. In parallel, a **clean-room Python reimplementation** from
   the published Model Manual v1.1 — hostable regardless of the upstream
   licence — proceeds under the protocol in
   [REIMPLEMENTATION.md](REIMPLEMENTATION.md) (`src/define_uk/model/`).
2. **Replication gate:** reproduce the paper's headline scenario outputs
   (S1 baseline and at least two policy scenarios) and record them in
   `VALIDATION.md` with tolerances — the same validated-replication standard
   as [boe-var-model](https://github.com/PolicyEngine/boe-var-model) and
   [us-hank-model](https://github.com/PolicyEngine/us-hank-model).
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
