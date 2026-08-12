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
  calibration.py # manual §5 parameters and initial values (Tables 5–6)
  accounting.py  # §2.2 transactions + balance-sheet matrices and residuals
```

The solver is the standard SFC treatment: within each period, iterate all
registered equations until the maximum relative change falls below
tolerance; stock-flow norms (every flow from somewhere to somewhere, balance
sheets sum) are asserted each period, not assumed.

## Milestones

| # | Slice (manual §) | Gate | Status |
|---|------------------|------|--------|
| 1 | Accounting core: transactions + balance-sheet matrices (§2.2), residual instruments | matrices identically satisfied on initial values (§5) | **PASS** (2026-08-04) — `model/accounting.py` + `model/calibration.py` (§5 Tables 5–6 fully transcribed); all Table 1/2 row and column identities hold on the §5 initial values within the manual's own 4-significant-figure printing precision (`tests/test_accounting.py`). One documented manual inconsistency (Table 6 LENDM_ROW omits the DIVN_ROW term of Eq. (383); overall LENDM tabulated as 5.44 where "should equal 0"): the MFI/RoW transaction columns miss LEND by ∓DIVN_ROW, pinned exactly in the tests. |
| 2 | High-level macro + production (§3.2–3.3) | baseline GDP path vs oracle | **in progress** — §3.2 and §3.3.1 landed; §3.3.2, §3.3.3 and the oracle gate are still outstanding, so the milestone is **not** passed. See the notes below. |
| 3 | Sectoral equations (§3.4.1–3.4.7) | full S1 baseline vs oracle within tolerance | pending |
| 4 | Ecosystem block (§3.1) | emissions/energy paths vs oracle | pending |
| 5 | Policy scenarios (regulation, green public investment, 1.1 extensions) | scenario deltas vs published figures per `VALIDATION.md` | pending |

Tolerances are set per-milestone when the first comparison runs, and recorded
in `VALIDATION.md` alongside the replication-gate entries — the oracle
comparison and the published-figure replication are the same standard applied
to two references.

### Milestone 2 progress

**§3.2 High-level macroeconomic variables** (2026-08-11) — `model/sectors/macro.py`
implements Eqs. (21)–(43), all 23 equations, and the section solves as a
system (`tests/test_macro.py`). Every identity holds against the §5 Table 6
initial values at the manual's 4-significant-figure printing precision except
**Eq. (27)**, `GCF_R = GCF/P_P`, which gives 111.88 against a tabulated 112.30
(0.37%, ~10× the rounding noise) — and the manual disagrees with itself here,
since Eq. (25) only reproduces the tabulated `GDP_R` using 112.30. Pinned in
the tests, not absorbed into a tolerance. Also **Eq. (31) uses an intercept
α₀λ that Table 5 never tabulates** (the α₀ block ends at α₀WS); defaulted to
0.0, recorded in `macro.MANUAL_GAPS`, pinned by a test that fails if a value
is later published.

**§3.3.1 Domestic production module** (2026-08-12) — `model/sectors/production.py`
implements Eqs. (44)–(70), all 27 equations (final demand and the Leontief
gross-output block, mark-up pricing over lagged unit costs, the
wage-share/wage-rate distribution block, direct-energy prices and costs, and
the productive capital aggregates), tested in `tests/test_production.py`.
Nineteen identities hold against Table 6 within its printing precision (worst
8.1e-4, Eq. (46), which is exactly what L_PP's four printed digits predict).
Findings, all implemented as printed and pinned rather than patched:

- **Five inconsistencies at the manual's own initial values**, one to three
  orders of magnitude beyond the rounding noise. Eq. (51) `MU = α_MU·u` gives
  0.1584 vs a tabulated µ of 0.1704 (7.1%) — though the equation is the
  corroborated one, since Eqs. (49)+(50) imply 0.1598. Eq. (52)'s wage-share
  logistic gives 0.5997 vs a tabulated 0.6233 (3.8%), which is a
  self-contradiction: Table 5 says α₀WS was "calibrated so [the wage-share]
  equation equals observed at t=L", and the tabulated share is exactly
  W/GDP on two data figures. Eq. (59) gives a direct-energy price of 0.1491
  vs a tabulated 0.09337 (60%; implied α_NELEC 1.601, not 2.557). Eq. (61)
  gives P_FUEL = 0.6788 where Table 5 and Table 6 both state the initial fuel
  price is normalised to 1 (32%; implied α_PFUEL 16.18). Eq. (70) equates
  δ_KP to δ_kpc, but Table 5 prints 0.02375 and Table 6 0.02149 (10.5%), both
  marked "Free" — two data estimates of one constant.
- **Two equations a single-period snapshot cannot check at all**: Eqs. (49)
  and (55) read lagged variables. Eq. (55)'s implied wage-rate growth is
  1.0189 against the tabulated g = 1.019, three-significant-figure agreement
  on a quantity never fitted to it — evidence that Table 6 is the snapshot of
  a growing economy, so neither is treated as a defect.
- **Two symbol gaps**, in `production.MANUAL_GAPS`: the body's "direct
  energy" D-subscript family (P_D, P_DT, ITAX_D, E_D, COST_D) appears nowhere
  in Tables 5–6, and the tables' NELEC family appears nowhere in the body —
  they are the same variables, which Eqs. (60) and (62) confirm to ~1e-5, and
  we use the tabulated names; and Table 6 omits both components of Eq. (68)
  (K_NFCGR, K_GVTGR), tabulating only their sum K_PGR.
- A **prose/equation mismatch**: §3.3.1's text lists only household
  consumption, government consumption and exports in Eq. (44), but the
  printed equation also carries GCF, and Table 6 confirms the equation (the
  four components sum to F_P = 805.0 exactly).

## Attribution

This is the suite's standard adapted-model stance (as with the OBR
macroeconometric emulator and the Bank of England SVAR replication): the
**model design belongs to its authors**, the **implementation is ours**.
Every surface that presents results names DEFINE-UK and its authors (George,
Dafermos, Nikolaidi and co-authors), links the manual and papers, and states
that this is an independent Python implementation of the published
equations — not the authors' code, and not endorsed by them. The
implementation itself is AGPL-3.0 like the rest of the repository, which is
what makes hosting possible without any upstream licence.
