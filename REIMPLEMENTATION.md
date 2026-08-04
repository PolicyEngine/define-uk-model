# Clean-room reimplementation of DEFINE-UK 1.1

A from-scratch Python implementation of DEFINE-UK, built so PolicyEngine can
license and host the model (the upstream R code carries no license and cannot
be vendored or hosted — see README). Same play as
[obr-macroeconomic-model](https://github.com/PolicyEngine/obr-macroeconomic-model):
implement the published equations, validate against independent output.

## Protocol

**Specification sources (the only inputs to the implementation):**

- *DEFINE-UK Model Manual, Version 1.1* (George & Dafermos, April 2026)
  — full equation listing by sector (§3), calibration approach (§4), and
  parameters/initial values (§5).
  <https://define-model.org/wp-content/uploads/2026/04/define_uk_1.1.pdf>
- *"Evaluating climate policy mixes in the UK: an E-SFC approach"* — the
  published scenario results.
- Dafermos, Nikolaidi & Galanis (2017) for framework-level derivations the
  manual references.

**The upstream repository is an output oracle only.** `define_uk.upstream`
and `define_uk.runner` run the unlicensed R code at the pinned commit; its
*numerical outputs* are compared against ours in the oracle tests. Its
*source code is never read to write equations here* — every equation in
`src/define_uk/model/` must carry a `manual_ref` naming the manual section
and equation number it implements. An equation without a manual (or paper)
reference does not get merged.

**Data:** the model is calibrated to ONS Blue Book / UKEA national accounts
(manual §2.2). Input data are fetched from the official sources, not taken
from the upstream repo's `input/` spreadsheets.

## Architecture

```
src/define_uk/model/
  registry.py    # Equation(name, manual_ref, kind, func) + ordered registry
  solver.py      # per-period Gauss–Seidel iteration to SFC convergence
  sectors/       # one module per manual §3 section; equations register here
  calibration.py # manual §5 parameters and initial values (to add)
```

The solver is the standard SFC treatment: within each period, iterate all
registered equations until the maximum relative change falls below
tolerance; stock-flow norms (every flow from somewhere to somewhere, balance
sheets sum) are asserted each period, not assumed.

## Milestones

| # | Slice (manual §) | Gate |
|---|------------------|------|
| 1 | Accounting core: transactions + balance-sheet matrices (§2.2), residual instruments | matrices identically satisfied on initial values (§5) |
| 2 | High-level macro + production (§3.2–3.3) | baseline GDP path vs oracle |
| 3 | Sectoral equations (§3.4.1–3.4.7) | full S1 baseline vs oracle within tolerance |
| 4 | Ecosystem block (§3.1) | emissions/energy paths vs oracle |
| 5 | Policy scenarios (regulation, green public investment, 1.1 extensions) | scenario deltas vs published figures per `VALIDATION.md` |

Tolerances are set per-milestone when the first comparison runs, and recorded
in `VALIDATION.md` alongside the replication-gate entries — the oracle
comparison and the published-figure replication are the same standard applied
to two references.

## Relationship to the license request

The upstream license request (README roadmap #1) proceeds in parallel. If the
DEFINE team licenses the upstream code, vendoring it may ship faster than this
track finishes — the clean-room build still stands, as the hostable
implementation PolicyEngine controls, and the two validate each other.
