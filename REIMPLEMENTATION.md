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
| 2 | High-level macro + production (§3.2–3.3) | baseline GDP path vs oracle | **in progress** — §3.2, §3.3.1 and §3.3.2 landed; §3.3.3 and the oracle gate are still outstanding, so the milestone is **not** passed. See the notes below. |
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
(0.37%, ~10× the rounding noise), and Eq. (25) only reproduces the tabulated
`GDP_R` using 112.30. This is not a §3.2 finding on its own: Table 6 deflates
its *entire* capital block at 1.031 — GCF, GCF_NFC, GCF_HH, GCF_GVT, K_P,
K_NFC all give nominal/real ratios of 1.0309–1.0312 — while the equations
prescribe P_P = 1.035, which is the same 0.4% that shows up in §3.3.2's
Eqs. (104), (105), (132) and (133). One systematic property of Table 6's
capital rows, most likely a national-accounts investment deflator where the
equations want the production deflator. Pinned in the tests, not absorbed
into a tolerance. Also **Eq. (31) uses an intercept
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

- **Five gaps at the manual's own initial values**, one to three orders of
  magnitude beyond the rounding noise — but only three of them are the manual
  contradicting itself, and the list is split accordingly, because Table 5
  states the provenance of every parameter and that provenance decides which
  is which.

  *Contradictions.* Eq. (52)'s wage-share logistic gives 0.5997 vs a
  tabulated 0.6233 (3.8%): Table 5 says α₀WS was "calibrated so [the
  wage-share] equation equals observed at t=L", and it is not, while the
  tabulated share is exactly W/GDP on two data figures. Eq. (61) gives
  P_FUEL = 0.6788 against a tabulated 1 (32%; implied α_PFUEL 16.18), where
  Table 5 calls α_PFUEL "based on initial data" and says of α_FUELPSLR that
  "at the initial condition fuel price is normalised to equal 1" — and
  §3.3.2 supplies a third witness, tabulating IC_FUELPS and IC_FUELPSR at the
  same 15.75, which is only possible at P_FUEL = 1. Eq. (70) equates δ_KP to
  δ_kpc, but Table 5 prints 0.02375 and Table 6 0.02149 (10.5%), both marked
  "Free" — two data estimates of one constant.

  *First-period jumps*, where Table 5 describes the parameter as a historical
  mean and so never claims it reproduces t=L. Eq. (51) `MU = α_MU·u` gives
  0.1584 vs a tabulated µ of 0.1704 (7.1%), and α₁MU is "calibrated so LR
  markup at initial utilisation equals mean of 45:88 and 109:132 (excl. COVID
  and GFC)". Eq. (59) gives a direct-energy price of 0.1491 vs a tabulated
  0.09337 (60%; implied α_NELEC 1.601, not 2.557), and α_NELEC is "calculated
  using the mean over past data" while P_GAS and P_OIL are tabulated at the
  2022Q4 spike that Table 6's own INF_A = 0.107 and "GDP price deflator
  indexed at Q4 2022" date. These matter — a run started from Table 6 takes
  both jumps in its first quarter, and the second moves a price that steers
  green investment — but they are *not* reported as the manual disagreeing
  with itself.

  On Eq. (51) specifically, an earlier version of this file claimed the
  equation was "the corroborated one" because Eqs. (49)+(50) imply 0.1598.
  That inference does not hold and has been withdrawn: Eq. (49) reads
  UC_{t−1}, and 0.1598 is what it gives only if unit costs were flat into the
  initial period. Honouring the lag, the tabulated µ implies +0.91% quarterly
  unit-cost growth and Eq. (51)'s µ implies −0.12% (deflation) — and the
  manual's own initial period is growing and inflating (Eq. (29)'s quarterly
  nominal GDP growth g = 1.019, INF_A = 0.107), which favours the tabulated
  value if anything. Neither side is the outlier on the evidence a snapshot
  provides.
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

**§3.3.2 Power generation sector** (2026-08-12) — `model/sectors/power.py`
implements Eqs. (71)–(138), all 68 equations (electricity final demand and
the Leontief block, the fossil/non-fossil cost split, marginal-cost
electricity pricing, the utilisation and forward-looking-expectation block
that drives investment, credit-rationed capital formation, and the sector's
full financial account through to leverage, illiquidity and credit
rationing), tested in `tests/test_power.py`. Thirty identities hold against
Table 6 within its printing precision (worst 9.1e-4, Eq. (73), exactly what
L_PSP's four printed digits predict).

The section is, however, in materially worse shape than §3.2 or §3.3.1, and
the two findings that matter most are about what §5 does *not* contain:

- **§3.3.2 as published cannot be simulated forward.** Six parameters it
  uses are absent from Table 5 — α₀GCFPS (Eq. (96)), α₀bNFF and α₁bNFF
  (Eq. (99)), and α₁CRPS, α₂CRPS, α₃CRPS (Eq. (138)) — and two *variables*,
  the capital profit rates r_KNFF and r_KFF of Eq. (99), are never defined
  anywhere in the manual. All are defaulted to 0.0 in `power.MANUAL_GAPS`
  and pinned. The consequences are not cosmetic: credit rationing degenerates
  to a constant logistic(α₀CRPS) = 0.939, the green/fossil investment split
  degenerates to 50:50 against the 69:31 Table 6 implies, and desired
  power-sector investment turns negative. Held at its own initial values the
  section returns GCF_PS = −0.021 against a tabulated +2.15.
- **Ten identities disagree with Table 6 by one to three orders of magnitude
  more than the printing noise**, all implemented as printed and pinned
  individually. The largest is Eq. (84), P_ELEC = (1+MU_ELEC)·MC_ELEC, which
  gives 0.9725 against a tabulated 0.3198 — a factor of 3.04, and an implied
  mark-up of −0.267, i.e. electricity sold below marginal cost. Both sides
  are corroborated independently (MC_ELEC by Eqs. (82)+(83) to 4.5e-5,
  P_ELEC by Eq. (74) to 3.7e-4), so the manual's two chains meet at a
  contradiction — and the likeliest reason is the missing price rule
  described below, not a wrong number. Then Eq. (108) EQATR_PS 0.5025 vs
  0.3836 (α_EQAPS is "model-constrained", i.e. its remark names the equation
  it fails); Eq. (131) K_PS 136.6 vs 132.5, where Table 6's entry equals
  K_PSR to all four digits — the real value copied into the nominal row, and
  propagated consistently into its own Eqs. (134) and (135); Eq. (136)
  ILLIQ_PS 1.271 vs 1.046, which matters because Eq. (117) is exponential in
  it; and Eqs. (104), (105), (132), (133), all ~3.9e-3 out — one finding, not
  four, and the same one as §3.2's Eq. (27): Table 6's capital block is
  deflated at 1.031 throughout while the equations prescribe P_P = 1.035.

  Two of the ten are **first-period jumps rather than contradictions**, on
  Table 5's own account of the parameter: Eq. (94) DIVP_PS 2.111 vs 1.251,
  where α_DIVPPS is "set as the mean of past implied values", and Eq. (111)
  RESTR_PS −30.76 vs −8.569 (3.6×), where η_PSB is "taken as the mean of past
  data" (and is within 1% of η_NFCT, which Table 5 reuses for the power
  sector in nine other places). Both tabulated values are corroborated —
  Eq. (95) reproduces RP_PS exactly from DIVP_PS, and Eq. (110) reproduces
  IBLTR_PS to 2e-4 from RESTR_PS — so the jump is real; it is simply not
  evidence of a defect.
- **Four are sign contradictions no lag or vintage can rescue**: Eqs. (107),
  (112), (113) and (116) each have a determinate-sign right-hand side and
  Table 6 tabulates the opposite one. Table 6 is the corroborated side —
  Eqs. (90)/(118) and (91)/(119) are two independent routes to each lagged
  interest-bearing stock and agree to 1.4e-4 and 3.6e-5, and Eq. (110)
  reproduces the tabulated IBLTR_PS from the tabulated transfers to 2e-4.
  Table 5 makes it worse, since α_IBAPS and δ_IBAPS are both marked
  "model-constrained" with remarks naming these very equations (the manual
  never defines the category, so "derived so the equation reproduces the
  initial value" is our reading of the remark, not a stated rule).

  One qualification that belongs with the finding wherever it is quoted:
  **Eq. (107) is not a power-sector defect.** The manual prints the same α·GO
  rule for three other sectors — Eq. (177) IBATR_NFC, Eq. (231) IBATR_NMFI,
  Eq. (284) IBATR_GVT — every α is positive and Table 6 tabulates all four
  transfers negative (−37.73, −141.5, −9.236, −1.065), with magnitudes out by
  1.7× to 4.6× as well. Whatever is wrong is wrong in the interest-bearing
  asset transfer rule, or in Table 6's sign convention for it, model-wide;
  §3.3.2 is only where we meet it first. Confirming that needs §3.4.1, §3.4.3
  and §3.4.4, which are not implemented yet.
- **§5 calibrates an electricity price rule §3 never prints.** Table 5 gives
  t_ELECswitch = 153, "Time index (quarter) for the switch in the electricity
  price long-run formation rule", and Table 6 gives P_ELECLR, "Long run
  electricity price", set equal to the initial price. Neither symbol occurs
  anywhere in §§1–4, and the only electricity price equation printed is
  Eq. (84) — a fixed mark-up with no long-run term and no switch. This is the
  mirror image of the missing-parameter gaps above (a tabulated symbol with
  no equation, like Table 5's α₀GCFFF and α₀GCFNFF, which the v1.1 body
  replaced but §5 still carries), and it is the most economical explanation
  of Eq. (84)'s factor of 3.04.
- **Nine equations a single-period snapshot cannot check**: Eqs. (78), (79),
  (90), (91), (114), (115), (117), (127), (128). Eqs. (78)–(79)'s sum
  matches Table 6's total power-sector cost to 8.6e-4, which localises their
  disagreement to the split alone — β_NFF,t−1 = 0.5095 closes it, against a
  current 0.5976, which the model's own dispatch structure (fossil is the
  swing plant at u_FF = 0.31) makes plausible. Eqs. (127)–(128) imply fossil
  generation capital fell 0.40% and non-fossil rose 1.42% over the initial
  quarter — the decarbonisation mechanism, visible in the snapshot.
- **Eq. (61) propagates but does not contaminate the checks.** §3.3.1's fuel
  price gap (0.6788 against a normalised 1) reaches this section only through
  IC_FUELPS, which §3.3.3 determines and Table 6 tabulates, so no identity
  above is affected. In a *simulation* it cuts IC_FUELPS 32%, and since the
  carbon bill is under 0.5% of Eq. (82)'s numerator at the baseline ETS price
  it carries that −32% essentially undiluted into MC_FF, MC_ELEC and P_ELEC,
  and −18% into COST_PSFF. It does not cancel Eq. (84): 3.04 × 0.68 still leaves the
  electricity price 2.07× Table 6's. §3.3.2 also supplies a third,
  independent witness that the normalisation is the right side of that
  finding — Table 6 tabulates IC_FUELPS and IC_FUELPSR at the same 15.75,
  which is only possible at P_FUEL = 1.
- **Two structural notes.** Eq. (88)'s printed inequality points the opposite
  way from the prose above it (as printed, fossil capacity is removed from
  expected utilisation when the ban date is at or *beyond* the planning
  horizon); the printed form is implemented and the baseline switch is −∞ so
  that the no-ban case returns u_PS, which is what the manual's own
  annotation asserts. And the price block is undefined at full
  decarbonisation — Eqs. (81), (82) and (85) all divide by fossil quantities
  that go to zero on exactly the path Eq. (88) exists to simulate — so those
  guards raise rather than invent a limit.

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
