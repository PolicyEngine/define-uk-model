# Scenario notes: duplicate solves and the expectation regimes

Two questions about the 22 cached scenarios, answered from the cached run's
own output files (`output/tables/**/Variables_*.csv` and
`Parameters-sorted_*.csv`) and the Model Manual v1.1. Nothing here comes from
the upstream source code, and nothing was re-run. Every figure is gated in
`tests/test_scenario_sweep.py` (those tests need the cached run, so they skip
in CI).

Units: emissions are MtCO2e, quarterly flows summed over 2027Q1–2040Q4 unless
a year is named. All figures are scenario minus baseline and carry the
caveats in `define_uk.scenarios.CAVEATS`, including the Baseline/policy
α_PP mismatch (issue #20).

## What the five expectation regimes are

The power-sector block is run under five regimes. They are parameter sets.
The cached parameter files of the two scenarios that contain the fossil-fuel
ban print them (`define_uk.scenarios.EXPECTATION_REGIMES`):

| Regime | CRED | GVT_CRED | ELEC_BUFFER | Fossil capital at 2032Q1 |
|---|---|---|---|---|
| Mutual trust (the Baseline's own values) | 0.9 | 1 | 0 | struck out |
| False confidence | 0.9 | 0 | 0 | kept |
| Poor credibility | 0.3 | 0 | 0 | kept |
| No forward guidance | 0 | 1 | 0 | struck out |
| Unexpected enforcement | 0.3 | 1 | 0.05 | struck out |

- **CRED** is the manual's perceived credibility of the ban: the weight the
  power sector puts on expected future utilisation without fossil capital
  (Eq. (89)).
- **GVT_CRED** is not named in the manual. Its effect is read from the
  outputs: in all six ban files with GVT_CRED = 1, real fossil generation
  capital (K_PSFFR) is exactly zero from 2032Q1, the quarter the parameter
  FF_CAP_BAN = 181 names; in all four files with GVT_CRED = 0 it stays
  positive and declines gradually. This matches the manual's statement that
  in v1.1 "regulatory policies can directly depreciate the capital stock of
  affected sectors" (§1). Calling GVT_CRED "whether the capital ban is
  enforced" is our reading of that pattern and of the regime names, not a
  definition the authors publish.
- **ELEC_BUFFER** is not named in the manual either, and we have not
  identified its effect.

In the mutual-trust and false-confidence runs the generation mix is the
same: the non-fossil share of generation is 0.975 from 2032Q1 in both, and
fossil generation is the same residual (about 2 per quarter, consistent with
the manual's Eqs. (6)–(7), where fossil generation is the remainder and the
constant σ_ELEC is slightly below one). Those two regimes therefore differ
only in whether the fossil *capital stock* is removed in 2032, not in how
much fossil electricity is generated. The other three regimes also differ
before 2032, because less non-fossil capacity is built (non-fossil capital
at 2031Q4, ban alone: 127.7 under mutual trust and false confidence, 110.9
poor credibility, 109.5 unexpected enforcement, 100.3 no forward guidance),
and under poor credibility and unexpected enforcement the non-fossil share
reaches 0.975 later (0.936 and 0.967 at 2033Q4; 0.975 in every regime by
2036Q4).

## Duplicate solves

Six of the 22 registered names are the same cached solve as another name.
The output files are byte-identical (same SHA-256, all 817 columns and 216
quarters) and the parameter rows are equal, so there are 16 distinct solves.

| Name | Same solve as | Why |
|---|---|---|
| `power_sector_subsidy__poor_credibility` | `power_sector_subsidy` | The regime parameters are not applied to the subsidy-only scenario |
| `power_sector_subsidy__false_confidence` | `power_sector_subsidy` | as above |
| `power_sector_subsidy__no_forward_guidance` | `power_sector_subsidy` | as above |
| `power_sector_subsidy__unexpected_enforcement` | `power_sector_subsidy` | as above |
| `mixed_fossil_fuel_ban_subsidy` | `fossil_fuel_ban_subsidy` | The mixed block re-uses the single-policy solve |
| `mixed_housing_regulation_subsidy` | `housing_regulation_subsidy` | The mixed block re-uses the single-policy solve |

**Power Sector Subsidy.** In all five regime folders the subsidy-only
parameter row differs from its Baseline in the same two entries only:
POWER_SUB = 1 and the α_PP mismatch. CRED, GVT_CRED and ELEC_BUFFER keep the
Baseline's values (0.9, 1, 0) in every folder. The regime switches are set
only in the two scenarios that contain the ban. The five files are therefore
one parameter set, and one solve, under five folder labels. That is
consistent with the manual, where credibility enters only through the
expected effect of a ban (Eqs. (88)–(89)); whether the authors intended the
subsidy-only scenario to be regime-invariant is not something the outputs
can show.

**Mixed block.** The mixed block's "Fossil Fuel Ban + Subsidy" and "Housing
Regulation + Subsidy" have the same parameter rows as the single-policy
scenarios of the same name, and the files are byte-identical. Only "Both
Regulations + Subsidies" is a solve of its own.

`list_scenarios()` and `run_scenario()` carry `identical_to` for these six
names, and their results lead with a caveat saying so. Comparing a duplicate
with its original compares a solve with itself: a zero difference between
`power_sector_subsidy` and `power_sector_subsidy__poor_credibility` is not
evidence that credibility does not matter for a subsidy.

## Why the ban cuts slightly more under false confidence than under mutual trust

Cumulative emissions cut by the fossil-fuel ban, 2027–2040, by regime:

| Regime | Fossil Fuel Ban | of which electricity | of which non-electricity | Fossil Fuel Ban + Subsidy |
|---|---|---|---|---|
| Mutual trust | −398.5 | −118.7 | −279.8 | −517.7 |
| False confidence | −417.0 | −118.7 | −298.3 | −517.8 |
| Poor credibility | −217.9 | −67.8 | −150.1 | −397.9 |
| No forward guidance (ban alone refused) | −121.3 | −65.5 | −55.6 | −243.7 |
| Unexpected enforcement (ban alone refused) | −183.5 | −77.8 | −105.7 | −381.6 |

The ban alone cuts 18.5 MtCO2e more under false confidence than under mutual
trust (4.6% of the mutual-trust cut). The served annual figure for 2035 is
−45.5 against −42.6 MtCO2e per year. With the subsidy the two regimes are the
same to rounding (0.04).

The two ban runs differ in one parameter, GVT_CRED, and are identical in
every column through 2031Q4. The whole gap opens from 2032Q1 and is in
non-electricity emissions (−18.51); electricity emissions differ by 0.02.
The chain in the cached files:

1. **2032Q1, the capital ban.** Under mutual trust fossil generation capital
   goes from 47.6 to 0. Maximum generation (E_ELECMAX, Eq. (5)) falls from
   130.6 to 78.1, below electricity demand of 79.5. Under false confidence
   the capital is kept (44.4) and maximum generation is 128.3.
2. **2032Q1–Q2, a capacity shortfall.** Under mutual trust generation sits
   at the ceiling for two quarters (the served `capacity_constrained` flag
   for 2032). Annual inflation is 4.6% in 2032Q1 against 2.1%, and the
   electricity price is 1.39 and 2.00 times the false-confidence price in
   2032Q2 and Q3 (0.107 and 0.156 against 0.077 and 0.078).
3. **2032Q2–Q3, less green investment.** The green share of NFC investment
   depends on the relative price of non-electric energy to electricity
   (Eq. (168)). It dips to 0.075 and 0.062 against 0.086 in both quarters
   under false confidence, and real green NFC investment is 7.9 and 6.4
   against 9.0 and 9.1.
4. **A lasting gap in green production capital.** It is 4.0 lower at 2032Q4
   (249.5 against 253.5, 1.6%) and still 1.5 lower in 2040Q4.
5. **Higher energy and emission intensity.** In the manual, energy intensity
   (Eq. (16)), the electricity share of production energy (Eq. (18)) and the
   emission intensity of non-electric energy (Eq. (19)) are logistic
   functions of the lagged ratio of green to conventional production
   capital. In the cached files each of the three is a single function of
   that ratio across both runs, to printing precision. False confidence relative to mutual trust,
   annual means:

   | Year | Energy intensity | Non-electric share of production energy | Emission intensity, non-electric | Real gross output | Non-electricity emissions | MtCO2e |
   |---|---|---|---|---|---|---|
   | 2032 | −0.6% | −0.2% | −0.2% | +0.8% | −0.3% | −0.85 |
   | 2033 | −1.3% | −0.4% | −0.3% | +0.5% | −1.2% | −3.18 |
   | 2034 | −1.1% | −0.3% | −0.3% | −0.2% | −1.4% | −3.62 |
   | 2035 | −0.8% | −0.3% | −0.2% | −0.2% | −1.2% | −2.91 |
   | 2036 | −0.7% | −0.3% | −0.2% | −0.1% | −0.9% | −2.19 |
   | 2037 | −0.5% | −0.2% | −0.2% | −0.1% | −0.8% | −1.79 |
   | 2038 | −0.4% | −0.2% | −0.1% | −0.1% | −0.7% | −1.53 |
   | 2039 | −0.3% | −0.2% | −0.1% | −0.1% | −0.6% | −1.31 |
   | 2040 | −0.3% | −0.2% | −0.1% | −0.1% | −0.5% | −1.13 |

   The gap is in intensities, not activity: output is higher under false
   confidence in 2032–33 and 0.1–0.2% lower afterwards.

**The control.** With the subsidy, enough non-fossil capacity is in place by
2032 that striking out the fossil capital does not bring maximum generation
below demand: neither regime reaches the ceiling, there is no price spike,
and the emissions gap is 0.04. The same enforcement difference with no
shortfall produces no emissions difference, which is what ties the gap to
the shortfall and not to expectations.

**What this does and does not show.**

- It is a property of this cached run: the ordering comes from a two-quarter
  capacity shortfall at one date under one calibration. It is not a general
  finding that an unenforced ban cuts more emissions than an enforced one.
- In the model as run, keeping fossil capital on the books costs nothing in
  emissions, because fossil generation is the same residual in both regimes.
  That follows from Eqs. (6)–(7), where fossil generation is the remainder
  whatever the fossil capital stock.
- The two refused solves (the ban alone under no forward guidance and under
  unexpected enforcement) and the other served runs that reach the ceiling
  are the same regime switch, longer. With weaker expectations less
  non-fossil capacity is in place when the fossil capital is struck out:
  maximum generation at 2032Q1 is 78.1 under mutual trust, 72.0 under
  unexpected enforcement and 64.1 under no forward guidance, against demand
  of about 80, and the ceiling binds for 2, 4 and 31 quarters. The
  cumulative figures above for the ban alone under no forward guidance and
  under unexpected enforcement come from the two refused solves; they are
  shown for completeness and are not results.
- We have not established why fossil generation continues at the same level
  with zero fossil capital beyond what Eqs. (6)–(7) print, and we have not
  identified what ELEC_BUFFER does.

## Reproducing the figures

```bash
pytest tests/test_scenario_sweep.py -k "identical or regimes or struck or false_confidence"
```

needs the cached run (`define_uk.runner.run()`; see the README).
