"""DEFINE-UK Model Manual v1.1 §3.3 Production — §3.3.2 the power generation sector.

Equations (71)-(138): the electricity input-output block, the fossil/non-fossil
cost split, marginal-cost electricity pricing, the utilisation and
forward-looking expectation block that drives power-sector investment, and the
sector's full financial account (transfers, revaluations, stocks, net worth,
leverage, illiquidity and credit rationing).

§3.3.1 (domestic production, Eqs. (44)-(70)) is in ``production.py`` and
§3.3.3 (input-output, from Eq. (139)) is a separate pass; this module's
``register`` covers §3.3.2 exactly.

Clean-room implementation from the published manual. Every equation carries
the manual section and equation number it implements; the upstream R code is
an output oracle only and is never read to write equations here (see
REIMPLEMENTATION.md).

Why this sector is separate
---------------------------
The power sector is the industry "Electricity, gas, steam and air
conditioning supply (D.35)" of the ONS input-output tables, carved out of
production so that the green/fossil split has somewhere to live. Four things
make it the pivot of the whole model:

1. **The generation mix is a quantity, not a price response.** β_NFF,
   Eq. (77), is the non-fossil share of electricity *output*, and everything
   downstream — costs, price, emissions, investment — keys off it. There is
   no substitution elasticity anywhere: the mix moves because capital moves.

2. **Prices are marginal-cost, and the marginal plant is fossil.** Eqs. (82)
   and (84): non-fossil marginal cost is zero (Heal, 2022 — no fuel, no
   emission tax), so only the fossil plant's fuel and carbon bill sets the
   price. Eq. (83) is the manual's non-linearity: the marginal cost falls as
   (1 - β_NFF)^μ_MCELEC, capturing the rising frequency of hours in which the
   grid is entirely non-fossil (manual §3.3.2, pp. 20-21, citing Carbon Brief
   2024). This is where a carbon price reaches consumer bills, and it is why
   the sector is priced on marginal rather than the mark-up-over-unit-cost
   rule §3.3.1 uses for production.

3. **Investment is demand-led but credit-rationed.** Desired investment,
   Eq. (96), responds to utilisation against a target — post-Keynesian, so
   supply follows demand — but Eqs. (100)-(101) then scale it by (1 - CR_PS),
   and CR_PS, Eq. (138), tightens when the sector cannot cover its interest
   bill (DSR) and when banks' own balance sheet deteriorates. Finance, not
   technology, is the binding constraint on decarbonisation here (manual
   §3.3.2, p. 23, citing Taghizadeh-Hesary and Yoshino 2020).

4. **It holds financial assets.** Unlike the production module (§3.3.1,
   footnote 14), the power sector has a balance sheet, a net-lending position
   and a default rate — the manual's stated innovation over other E-SFC
   models with input-output sectors (§3.3.2, p. 22).

Policy switches live here
-------------------------
The scenarios toggle, and none of them is calibrated in §5:

- ``t_FFBAN`` (the manual's *B*) — the period a fossil generation ban comes
  into force. It enters only through Eq. (88).
- ``CRED``, ``T_PSPLAN``, ``delta_PSPLAN`` — the credibility, horizon and
  hyperbolic discount of the forward-looking expectation, Eq. (89). With
  ``CRED = 0`` the sector is myopic and Eq. (89) collapses to u_PS.
- ``COV_ETSPS`` and ``P_ETS`` — carbon-price coverage and level, Eq. (82);
  the manual's sce2 raises both (Table 5: ``delta_COVETS2``,
  ``g_PETS_sce2``).
- ``K_GVTNFFR`` — government-owned non-fossil generation capital, Eq. (86).
  Zero in the baseline (see MANUAL_GAPS); Table 5's ``GCF_PSGVT_sce1`` and
  ``GCF_PSGVT_sce3`` switch it on.
- ``SUBS_PS`` — power-sector subsidies, Eq. (136), zero in the baseline.

Exogenous to this section
-------------------------
See ``EXOGENOUS_TO_SECTION``. Note that two variables §3.2 treats as
exogenous — GO_PS and GCF_PS — are determined here, by Eqs. (74) and (102),
and §3.3.1's F_PSR by Eq. (72); the three sections only close jointly.

Where the manual is silent (see ``MANUAL_GAPS``)
------------------------------------------------
Six symbols §3.3.2 uses are never given a value, and two are never even
defined. Each is defaulted explicitly here, and every default is inert or
pinned in tests/test_power.py:

  α_0GCFPS                       Eq. (96)   -> 0.0   (Table 6 implies ~0.021)
  α_0bNFF, α_1bNFF               Eq. (99)   -> 0.0
  α_1CRPS, α_2CRPS, α_3CRPS      Eq. (138)  -> 0.0
  r_KNFF, r_KFF                  Eq. (99)   never defined anywhere in the manual
  δ_KPS                          Eq. (130)  -> Table 6's δ_KPSFF = δ_KPSNFF
  K_GVTNFFR                      Eq. (86)   -> 0.0, corroborated two ways
  CRED, T, δ, B                  Eqs. (88)-(89), policy switches -> inert

Where the manual disagrees with itself (measured at the §5 Table 6 values)
-------------------------------------------------------------------------
Thirty of the section's sixty-eight equations reproduce Table 6 inside its
four-significant-figure printing noise. Fourteen do not, and are implemented
exactly as printed and pinned in tests/test_power.py with the measured gap:

  Eq. (84)   P_ELEC      0.9725 vs 0.3198 tabulated       2.0e+0
  Eq. (94)   DIVP_PS     2.111  vs 1.251                  6.9e-1
  Eq. (107)  IBATR_PS    +0.468 vs -1.065     sign contradiction
  Eq. (108)  EQATR_PS    0.5025 vs 0.3836                 3.1e-1
  Eq. (111)  RESTR_PS    -30.76 vs -8.569                 2.6e+0
  Eq. (112)  OTIBA_PS    +0.038 vs -0.0166    sign contradiction
  Eq. (113)  OTEQA_PS    +1.516 vs -1.208     sign contradiction
  Eq. (116)  OTIBL_PS    -0.024 vs +0.980     sign contradiction
  Eq. (131)  K_PS        136.6  vs 132.5                  3.1e-2
  Eq. (136)  ILLIQ_PS    1.271  vs 1.046                  2.2e-1
  Eqs. (104), (105), (132), (133)  real/nominal capital   ~3.9e-3

The remaining twenty-four either read a lagged variable, so a single-period
snapshot cannot check them at all — Eqs. (78), (79), (90), (91), (96),
(114)-(121), (125), (127), (128), (130), (138) — or determine a variable
Table 6 never tabulates: Eqs. (88), (89), (97)-(99), (102), (137). The tests
say only what a snapshot can support, which is which lagged value each one
implies; for the two interest-bearing stocks, two independent equations agree
on it to 1.4e-4 and 3.6e-5.

The section is also structurally undefined at full decarbonisation:
Eqs. (81), (82) and (85) divide by fossil generation or fossil capacity, both
of which go to zero on exactly the transition path Eq. (88)'s ban switch is
built to simulate. The guards below raise rather than invent a limit.
"""

from __future__ import annotations

import math
from typing import Mapping

from ..calibration import PARAMETERS
from ..registry import Equation, Registry

# Variables this section reads but does not determine. Kept explicit so a
# §3.3.2-only solve can assert it has been given everything it needs.
EXOGENOUS_TO_SECTION = (
    # Final demand for electricity, Eqs. (71)-(72).
    "CONS_HHPS", "CONS_HHPSR",      # household electricity      (§3.4.5)
    # Input-output block, Eqs. (73), (75), (78)-(79), (82), (136).
    "F_PR",                         # real production final demand (§3.3.1 (45))
    "L_PSP", "L_PSPS",              # Leontief inverse coefficients (§3.3.3)
    "IC_PPS", "IC_PSPS", "IC_OPPS", "IC_FUELPS",   # all §3.3.3
    "ITAX_PS", "ITAX_PSFF", "ITAX_PSNFF",          # all §3.4.4
    "P_P",                          # production deflator          (§3.3.1 (49))
    # Energy and emissions, Eqs. (77), (82), (85)-(88). All §3.1 ecosystem.
    "E_ELEC", "E_ELECFF", "E_ELECNFF", "E_ELECMAX",
    "EMIS_ELEC",                    # electricity emissions        (§3.1)
    "CF_NFF",                       # non-fossil capacity factor   (§3.1)
    "K_GVTNFFR",                    # gov non-fossil power capital (§3.4.4)
    # Carbon pricing, Eq. (82) — both are scenario instruments.
    "COV_ETSPS", "P_ETS",           # §3.4.4 / policy
    # Rates of return, Eqs. (90)-(91), (114). All §3.4.7.
    "r_IBA_PS", "r_IBL_PS", "r_IBL_GVT",
    # Counterpart sectors, Eqs. (93), (109), (113), (138).
    "EQL_NMFI", "DIVP_NMFI", "EQATR_NMFI", "OTEQL_NMFI",   # §3.4.3 NMFI
    "FA_MFI", "FL_MFI",             # §3.4.2 MFI balance sheet
    # Macro, Eq. (111).
    "GDP",                          # §3.2 (21)
    # Never defined anywhere in the manual — see MANUAL_GAPS.
    "r_KNFF", "r_KFF",              # Eq. (99)
    # Policy switches, all zero/inert in the baseline. See POLICY_DEFAULTS.
    "SUBS_PS",                      # §3.4.3 subsidies to the power sector
    "t_PS", "t_FFBAN", "CRED", "T_PSPLAN", "delta_PSPLAN",
)

# Eq. (96) is the one equation in §3.3.2 that reads two periods back: its
# autoregressive term is GCF_PSD_{t-1}/K_PS_{t-2}, the *lagged investment
# rate*. The solver exposes a single lag, so the caller carries K_PS_{t-2} in
# the lag state under this key. The alternative — silently dividing by
# K_PS_{t-1} — would change the equation, which is not ours to do.
SECOND_LAG_KEYS = ("K_PS_LAG",)

# Baseline values for the switches the scenarios toggle. These are NOT
# manual values — §5 tabulates none of them — so they are named here rather
# than buried in a default argument, and a §3.3.2 solve must be handed them
# explicitly. Every one of them is inert: with CRED = 0 the forward-looking
# term of Eq. (89) drops out entirely, and with no ban Eq. (88) returns u_PS.
POLICY_DEFAULTS = {
    # The manual's B. Eq. (88) removes fossil capacity from expected
    # utilisation when B >= L + t, so "no ban ever" is -inf, not +inf. See
    # MANUAL_GAPS["ban_condition_direction"] — the printed inequality and the
    # prose around it point opposite ways, and this is the value that
    # reproduces the manual's own annotation that the first branch "= u_PS".
    "t_FFBAN": -math.inf,
    "t_PS": 0.0,          # absolute period index, the manual's L + t
    "CRED": 0.0,          # policy credibility in (0, 1); 0 = myopic sector
    "T_PSPLAN": 0.0,      # the manual's T, "any reasonable value"
    "delta_PSPLAN": 1.0,  # the manual's hyperbolic δ in (0, 1)
    "K_GVTNFFR": 0.0,     # no government generation capital in the baseline
    "SUBS_PS": 0.0,       # no power-sector subsidy in the baseline
    "r_KNFF": 0.0,        # never defined by the manual; inert at α_1bNFF = 0
    "r_KFF": 0.0,
}

# Symbols §3.3.2 needs that manual §5 does not tabulate under the name the
# §3 body uses. Pinned in tests/test_power.py rather than silently
# reconciled.
MANUAL_GAPS = {
    "delta_KPS": (
        "Eqs. (78), (79), (127), (128), (130), (136) and (137) all use a "
        "single power-sector depreciation rate δ_KPS, and Eq. (130) says it "
        "is constant, but Table 6 tabulates only the split rates δ_KPSFF and "
        "δ_KPSNFF. They are equal (both 0.01227), so the identification is "
        "unambiguous and δ_KPS is seeded from them; Eq. (130) then carries it "
        "forward unchanged. Nothing is invented — but if a revision ever "
        "splits the two rates, Eqs. (127)-(128) need rewriting, not reseeding."
    ),
    "alpha0_GCFPS": (
        "Eq. (96)'s intercept α_0GCFPS is not in Table 5. The table does "
        "carry α_0GCFFF (0.01465) and α_0GCFNFF (0.02144), described as "
        "parameters 'in the power sector fossil/non-fossil fuel investment "
        "equation' — i.e. the intercepts of a *split* investment rule that "
        "the v1.1 body has replaced with the single Eq. (96) plus the "
        "Eqs. (97)-(98) split. Neither can be substituted without guessing "
        "which. Defaulted to 0.0 and recorded here. For the record, Table 6 "
        "implies about 0.0210 if the snapshot is read as a steady state "
        "(GCF_PSD = 2.4433 from Eqs. (97)+(98), K_PS lagged) — that value is "
        "NOT used, because the equation's two lagged terms make the "
        "steady-state reading an assumption rather than a measurement."
    ),
    "alpha_bNFF_and_capital_profit_rates": (
        "Eq. (99) splits desired investment on the gap between the profit "
        "rates of non-fossil and fossil capital, r_KNFF and r_KFF. Neither "
        "symbol is defined anywhere else in the manual and neither is "
        "tabulated; nor are the logistic's α_0bNFF and α_1bNFF. All four are "
        "defaulted to 0.0, which makes prop_NFF exactly 1/2. Table 6 implies "
        "0.6917 (GCF_PSNFFD/(GCF_PSNFFD + GCF_PSFFD)), so the default is "
        "visibly wrong and is pinned as such rather than tuned to fit: this "
        "is the single largest hole in §3.3.2, because prop_NFF is what "
        "steers investment green."
    ),
    "alpha_CRPS_slopes": (
        "Eq. (138) needs α_1CRPS, α_2CRPS and α_3CRPS; Table 5 tabulates only "
        "α_0CRPS (2.736, 'model-constrained'). The NFC credit-rationing "
        "equation is printed with exactly the same structure and its α_1-α_3 "
        "*are* tabulated, and Table 5 reuses NFC values for the power sector "
        "in at least nine other places (spr_psl = spr_nfcl, delta_IBLPS = "
        "delta_IBLNFC, delta_EQAPS = delta_EQANFC, delta_EQLPS = "
        "delta_EQLNFC, r_IBA_PS = r_IBA_NFC, r_IBL_PS = r_IBL_NFC, sigma_ps = "
        "sigma_nfc, tau_rlps = tau_rlnfc, tau_raps = tau_ranfc) — but reusing "
        "them here would be our inference, not the manual's instruction, and "
        "it does not reproduce Table 6 anyway (it gives CR_PS = 0.598 against "
        "a tabulated 0.1188). Defaulted to 0.0."
    ),
    "K_GVTNFFR": (
        "Eq. (86) puts government non-fossil power capital K_GVTNFFR in the "
        "denominator of non-fossil utilisation, and Table 6 does not "
        "tabulate it. It is zero in the baseline, and that is measured, not "
        "assumed, twice over: Eq. (86) returns u_NFF = 1.0000 (tabulated 1.0) "
        "at K_GVTNFFR = 0, and §3.1 Eq. (5) returns E_ELECMAX = 127.27 "
        "(tabulated 127.3). It is a scenario instrument — Table 5's "
        "GCF_PSGVT_sce1 and GCF_PSGVT_sce3 are exactly the government "
        "renewable investment that makes it non-zero."
    ),
    "forward_looking_switches": (
        "Eqs. (88)-(89) introduce four quantities §5 never tabulates: the "
        "ban period B, the credibility CRED, the planning horizon T and the "
        "hyperbolic discount δ. The manual says only that 0 < δ < 1, "
        "0 <= CRED <= 1 and that T 'can take any reasonable value'. They are "
        "scenario switches; POLICY_DEFAULTS gives the inert baseline, in "
        "which Eq. (89) reduces exactly to F(u_PS) = u_PS."
    ),
    "expected_capital_path": (
        "Eq. (89) averages E(u_PS,t+τ) over τ = 0..T, but the manual never "
        "says what capital stock the sector expects to hold at t+τ, and the "
        "model carries no forecast of it. We hold real capital and "
        "electricity demand at their current values across the planning "
        "horizon, so the only thing that varies with τ is whether the ban is "
        "in force. Stated here because it is our choice, not the manual's; "
        "it is inert whenever CRED = 0."
    ),
    "ban_condition_direction": (
        "Eq. (88) as printed keeps fossil capacity in the denominator when "
        "B < L + t and removes it when B >= L + t. The prose immediately "
        "above says the opposite — that fossil capital is removed 'when the "
        "ban comes into force at time B'. Under the printed condition a "
        "distant ban date removes fossil capacity and a past one restores "
        "it, which is backwards; under the prose it is not. We implement the "
        "printed inequality (transcription beats interpretation) and set the "
        "baseline switch to -inf so that the no-ban case returns u_PS, which "
        "is what the manual's own annotation on the first branch asserts."
    ),
    "untabulated_endogenous": (
        "Table 6 omits five variables §3.3.2 determines: GCF_PSD (Eq. 96), "
        "prop_NFF (99), GCF_PS (102), DSR_PS (137) and the expectation pair "
        "E(u_PS)/F(u_PS) (88)-(89). Three of them are recoverable from what "
        "Table 6 does print and are checked that way in the tests: "
        "GCF_PSD = 2.4433 and prop_NFF = 0.6917 from Eqs. (97)+(98), and "
        "GCF_PS = 2.1528 from Eq. (102), which Eq. (106) then confirms by "
        "reproducing the tabulated LEND_PS = -7.37 to 2.7e-5."
    ),
}

_CF_FF = PARAMETERS["CF_FF"]
_MU_ELEC = PARAMETERS["MU_ELEC"]
_MU_MCELEC = PARAMETERS["mu_MCELEC"]
_BETA_DPS = PARAMETERS["beta_dps"]
_ALPHA_DIVP_PS = PARAMETERS["alpha_DIVP_PS"]
_A1_GCFNFC = PARAMETERS["alpha1_GCFNFC"]
_A2_GCFNFC = PARAMETERS["alpha2_GCFNFC"]
_U_T = PARAMETERS["u_T"]
_ALPHA_IBAPS = PARAMETERS["alpha_IBAPS"]
_ALPHA_EQAPS = PARAMETERS["alpha_EQAPS"]
_THETA_PSB = PARAMETERS["theta_psb"]
_ETA_PSB = PARAMETERS["eta_PSB"]
_DELTA_IBAPS = PARAMETERS["delta_IBAPS"]
_BETA_EQLPS = PARAMETERS["beta_EQLPS"]
_DELTA_RESPS = PARAMETERS["delta_RESPS"]
_DEF_MAX = PARAMETERS["def_max"]
_DEF0_PS = PARAMETERS["def0_PS"]
_DEF1 = PARAMETERS["def1"]
_DEF2 = PARAMETERS["def2"]
_A0_CRPS = PARAMETERS["alpha0_CRPS"]

# --------------------------------------------------------------------------
# Parameters §5 never tabulates. Defaulted to zero, explicitly and visibly,
# with the reasons in MANUAL_GAPS above. Module constants rather than magic
# numbers so a published value can be dropped in at one place — and so the
# tests can assert they are still zero, which is what makes the gap loud.
# --------------------------------------------------------------------------
A0_GCFPS = 0.0      # Eq. (96)
A0_BNFF = 0.0       # Eq. (99)
A1_BNFF = 0.0       # Eq. (99)
A1_CRPS = 0.0       # Eq. (138)
A2_CRPS = 0.0       # Eq. (138)
A3_CRPS = 0.0       # Eq. (138)


def _logistic(x: float) -> float:
    """1 / (1 + e^-x), overflow-safe — the form of Eqs. (99) and (138).

    Same treatment as production._logistic: both quantities are bounded
    shares by construction (an investment proportion and a rationing rate),
    so saturating is the right answer at extreme arguments and an
    OverflowError there would be an artefact of the arithmetic.
    """
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def _div(numerator: float, denominator: float, ref: str, what: str) -> float:
    """Divide, refusing to invent a value where the manual defines none.

    Every use guards a quantity that goes to zero on the decarbonisation
    path this model exists to simulate — fossil generation, fossil capacity,
    the fossil share. The manual stops defining these equations there (its
    only hint is §3.3.2 footnote 22, that electricity pricing switches to
    average cost if demand outstrips supply), so we raise instead of
    silently returning inf, nan or a limit of our own choosing.
    """
    if denominator == 0.0:
        raise ValueError(
            f"{ref}: undefined at {what} = 0. The manual does not define this "
            f"limit; see power.MANUAL_GAPS and §3.3.2 footnote 22."
        )
    return numerator / denominator


def _expected_utilisation(state: Mapping[str, float], horizon: float) -> float:
    """Eq. (88): expected power-sector utilisation at absolute period ``horizon``.

    Two branches. With the ban not in force the denominator is the whole
    capacity of the grid; with it in force fossil capacity is struck out, so
    expected utilisation jumps — which is the point, because Eq. (96) reads
    it as a signal to invest. Note the denominator here is *not*
    §3.1 Eq. (5)'s E_ELECMAX: that one also carries CF_NFF·K_GVTNFFR, which
    Eq. (88) omits. The two coincide only while government generation
    capital is zero, i.e. in the baseline but not under sce1 or sce3 — so the
    manual's annotation that the first branch equals u_PS quietly stops
    holding in exactly the scenarios that switch K_GVTNFFR on.
    """
    non_fossil = state["CF_NFF"] * state["K_PSNFFR"]
    if state["t_FFBAN"] >= horizon:
        return _div(state["E_ELEC"], non_fossil, "§3.3.2 eq. (88)",
                    "non-fossil capacity")
    fossil = _CF_FF * state["K_PSFFR"]
    return _div(state["E_ELEC"], fossil + non_fossil, "§3.3.2 eq. (88)",
                "total capacity")


def _forward_utilisation(state: Mapping[str, float]) -> float:
    """Eq. (89): credibility-weighted, hyperbolically discounted utilisation.

    F(u_PS) = CRED·(1/N)·Σ_{τ=0..T} δ^τ·E(u_PS,t+τ) + (1 - CRED)·u_PS, with
    N = Σ_{τ=0..T} δ^τ. Because N normalises the weights, the discounted sum
    is a weighted *average* of the expected path, not a discounted present
    value — so with an unchanging ban status it equals E(u_PS) exactly, and
    the discounting only matters for how heavily a ban announced part-way
    through the horizon is priced in. CRED is the share of agents who believe
    the announcement; at CRED = 0 the sector is myopic and F(u_PS) = u_PS.

    The capital stock is held at its current level across the horizon; see
    MANUAL_GAPS["expected_capital_path"].
    """
    credibility = state["CRED"]
    if credibility == 0.0:
        return state["u_PS"]

    discount = state["delta_PSPLAN"]
    horizon = int(state["T_PSPLAN"])
    now = state["t_PS"]

    weighted = 0.0
    total_weight = 0.0
    for tau in range(horizon + 1):
        weight = discount ** tau
        weighted += weight * _expected_utilisation(state, now + tau)
        total_weight += weight
    return credibility * (weighted / total_weight) + (1.0 - credibility) * state["u_PS"]


def register(registry: Registry) -> None:
    """Register the §3.3.2 equations, manual Eqs. (71)-(138)."""

    def add(name: str, number: int, kind: str, func) -> None:
        registry.add(Equation(name, f"§3.3.2 eq. ({number})", kind, func))

    # --- Electricity demand and gross output, Eqs. (71)-(76) -------------
    # Final demand for power-sector product is household electricity and
    # nothing else: business electricity is intermediate consumption
    # (IC_PSP), not final demand, and there are no electricity exports or
    # electricity capital goods in this two-sector IO system.
    add("F_PS", 71, "identity", lambda s, l: s["CONS_HHPS"])
    add("F_PSR", 72, "identity", lambda s, l: s["CONS_HHPSR"])
    # The mirror of §3.3.1's Eq. (46): the Leontief inverse again, so power
    # output accommodates demand from both sectors with no capacity term.
    # L_PSP is what makes an expansion of *production* pull electricity.
    add("GO_PSR", 73, "identity",
        lambda s, l: s["L_PSP"] * s["F_PR"] + s["L_PSPS"] * s["F_PSR"])
    add("GO_PS", 74, "identity", lambda s, l: s["GO_PSR"] * s["P_ELEC"])
    # Manual §3.3.2, footnote 18: IC_PPS already includes power-sector wages
    # and imports, which is why no wage term appears here — every wage in the
    # model is paid out of the production module (§3.3.1, p. 17).
    add("COST_PS", 75, "identity",
        lambda s, l: s["ITAX_PS"] + s["IC_PPS"] + s["IC_PSPS"])
    add("GOS_PS", 76, "identity", lambda s, l: s["GO_PS"] - s["COST_PS"])

    # --- The green/fossil cost split, Eqs. (77)-(81) ---------------------
    # β_NFF is an *energy* share, not a capacity share. With fossil plant at
    # 31% utilisation and non-fossil at 100% (Table 6's u_FF, u_NFF), fossil
    # is the swing supplier, so β_NFF moves with dispatch and weather far
    # faster than the capital stock behind it moves.
    add("beta_NFF", 77, "identity",
        lambda s, l: _div(s["E_ELECNFF"], s["E_ELEC"], "§3.3.2 eq. (77)",
                          "total electricity"))
    # Operating costs are apportioned by *last* period's mix, and all fuel
    # goes to the fossil side. Capital costs enter as depreciation on each
    # technology's own stock, which is what makes non-fossil generation
    # capital-heavy and fossil generation fuel-heavy — the asymmetry the
    # whole transition story turns on (manual §3.3.2, footnote 21).
    add("COST_PSNFF", 78, "identity",
        lambda s, l: (s["ITAX_PSNFF"]
                      + (s["IC_PSPS"] + s["IC_OPPS"]) * l["beta_NFF"]
                      + s["delta_KPS"] * l["K_PSNFF"]))
    add("COST_PSFF", 79, "identity",
        lambda s, l: (s["ITAX_PSFF"] + s["IC_FUELPS"]
                      + (s["IC_PSPS"] + s["IC_OPPS"]) * (1.0 - l["beta_NFF"])
                      + s["delta_KPS"] * l["K_PSFF"]))
    # Average costs are tracked but do not set the price — see Eq. (84).
    add("AC_NFF", 80, "identity",
        lambda s, l: _div(s["COST_PSNFF"], s["GO_PSR"] * s["beta_NFF"],
                          "§3.3.2 eq. (80)", "non-fossil output"))
    add("AC_FF", 81, "identity",
        lambda s, l: _div(s["COST_PSFF"], s["GO_PSR"] * (1.0 - s["beta_NFF"]),
                          "§3.3.2 eq. (81)", "fossil output"))

    # --- Marginal-cost pricing, Eqs. (82)-(84) ---------------------------
    # Only fossil generation has a marginal cost: fuel plus the carbon bill
    # actually charged (COV_ETSPS < 1 because of exemptions and free
    # allowances, footnote 19). Non-fossil marginal cost is zero (Heal,
    # 2022), so it never appears.
    add("MC_FF", 82, "identity",
        lambda s, l: _div(s["IC_FUELPS"] + s["COV_ETSPS"] * s["P_ETS"] * s["EMIS_ELEC"],
                          s["E_ELECFF"], "§3.3.2 eq. (82)", "fossil generation"))
    # The manual's central non-linearity. Merit order would say the price is
    # the fossil marginal cost until the last fossil plant closes; the
    # manual instead discounts it by (1 - β_NFF)^μ, because at a 60-70%
    # non-fossil share whole half-hours already clear with no fossil plant on
    # the system at all (§3.3.2, p. 21). μ_MCELEC = 0.325 < 1 makes that
    # discount bite early — the price starts falling long before the last
    # fossil unit retires, which is what gives the green transition a
    # consumer-price dividend in this model rather than a cost.
    add("MC_ELEC", 83, "behavioural",
        lambda s, l: s["MC_FF"] * (1.0 - s["beta_NFF"]) ** _MU_MCELEC)
    # Fixed mark-up over marginal cost. Unlike §3.3.1's Eq. (51) mark-up this
    # one is a constant, so it carries no cyclical price channel of its own.
    add("P_ELEC", 84, "calibrated", lambda s, l: (1.0 + _MU_ELEC) * s["MC_ELEC"])

    # --- Utilisation and expectations, Eqs. (85)-(89) --------------------
    # Capacity, not output, is the denominator: CF converts a real capital
    # stock into the electricity it could generate. CF_FF is a constant
    # (Table 5) while CF_NFF is endogenous in §3.1 — intermittent capacity
    # earns a capacity factor that depends on the mix.
    add("u_FF", 85, "identity",
        lambda s, l: _div(s["E_ELECFF"], _CF_FF * s["K_PSFFR"],
                          "§3.3.2 eq. (85)", "fossil capacity"))
    # Government-owned non-fossil capital counts towards non-fossil capacity
    # (and so *lowers* measured utilisation and hence private investment):
    # public green investment crowds private green investment out through
    # this denominator, which is what Table 5's CON_FF is about.
    add("u_NFF", 86, "identity",
        lambda s, l: _div(s["E_ELECNFF"],
                          s["CF_NFF"] * (s["K_PSNFFR"] + s["K_GVTNFFR"]),
                          "§3.3.2 eq. (86)", "non-fossil capacity"))
    add("u_PS", 87, "identity",
        lambda s, l: _div(s["E_ELEC"], s["E_ELECMAX"], "§3.3.2 eq. (87)",
                          "maximum generation"))
    # DEFINE-UK 1.1's forward-looking block: an announced fossil ban raises
    # *expected* utilisation now, because the capacity that will be struck
    # out is already known. This is the one place in the model where a future
    # policy changes current behaviour, and CRED is how much of it is
    # believed.
    add("Eu_PS", 88, "behavioural",
        lambda s, l: _expected_utilisation(s, s["t_PS"]))
    add("Fu_PS", 89, "behavioural", lambda s, l: _forward_utilisation(s))

    # --- Income and profit, Eqs. (90)-(95) -------------------------------
    # Interest on the stocks held at the *end of last period* — no
    # within-period interest on within-period borrowing.
    add("INTR_PS", 90, "identity", lambda s, l: s["r_IBA_PS"] * l["IBA_PS"])
    add("INTP_PS", 91, "identity", lambda s, l: s["r_IBL_PS"] * l["IBL_PS"])
    # Manual §3.3.2, p. 22: the government's share of gross operating surplus
    # is taken in the government's own disposable income equation, not netted
    # off here, so YD_PS is the *pre*-distribution income of the sector.
    add("YD_PS", 92, "identity",
        lambda s, l: s["GOS_PS"] + s["INTR_PS"] - s["INTP_PS"])
    # NMFIs hold the counterpart equity asset to every equity liability in
    # the model, so power-sector dividend receipts are its share of the NMFI
    # dividend pool.
    add("DIVR_PS", 93, "identity",
        lambda s, l: _BETA_DPS * (s["EQA_PS"] / s["EQL_NMFI"]) * s["DIVP_NMFI"])
    # Dividends are paid out of gross output, not out of profit — so the
    # sector distributes even while making a loss, which at Table 6's initial
    # values it is (GOS_PS = -4.48).
    add("DIVP_PS", 94, "calibrated", lambda s, l: _ALPHA_DIVP_PS * s["GO_PS"])
    add("RP_PS", 95, "identity",
        lambda s, l: s["YD_PS"] + s["DIVR_PS"] - s["DIVP_PS"])

    # --- Investment, Eqs. (96)-(105) -------------------------------------
    # A stock-adjustment accelerator on the *forward-looking* utilisation
    # gap, with an autoregressive term in the investment rate. Note both
    # signals are lagged, so desired investment is predetermined within the
    # period — power-sector capacity cannot respond to this quarter's demand,
    # which is the manual's "investment does take time" (§3.3.2, p. 23).
    add("GCF_PSD", 96, "behavioural",
        lambda s, l: l["K_PS"] * (
            A0_GCFPS
            + _A1_GCFNFC * (l["Fu_PS"] - _U_T)
            + _A2_GCFNFC * _div(l["GCF_PSD"], l["K_PS_LAG"],
                                "§3.3.2 eq. (96)", "K_PS at t-2")
        ))
    add("GCF_PSFFD", 97, "identity",
        lambda s, l: (1.0 - s["prop_NFF"]) * s["GCF_PSD"])
    add("GCF_PSNFFD", 98, "identity", lambda s, l: s["prop_NFF"] * s["GCF_PSD"])
    # The green/fossil investment split is a *relative profitability* rule,
    # and the only thing in the model that makes it green is that non-fossil
    # capital earns more. Both profit rates are undefined in the manual and
    # both α's untabulated (see MANUAL_GAPS): at the defaults this collapses
    # to a fixed 50:50 split, against the 69:31 Table 6 implies.
    add("prop_NFF", 99, "behavioural",
        lambda s, l: _logistic(A0_BNFF + A1_BNFF * (l["r_KNFF"] - l["r_KFF"])))
    # Credit rationing applies to both technologies at the same rate, so it
    # scales investment down without tilting the mix — the constraint is on
    # the volume of green investment, not on its share.
    add("GCF_PSFF", 100, "identity",
        lambda s, l: (1.0 - s["CR_PS"]) * s["GCF_PSFFD"])
    add("GCF_PSNFF", 101, "identity",
        lambda s, l: (1.0 - s["CR_PS"]) * s["GCF_PSNFFD"])
    add("GCF_PS", 102, "identity",
        lambda s, l: s["GCF_PSNFF"] + s["GCF_PSFF"])
    add("GCF_PSR", 103, "identity",
        lambda s, l: s["GCF_PSFFR"] + s["GCF_PSNFFR"])
    # Power-sector capital goods are production products, so they carry the
    # production deflator — there is no separate capital-goods price.
    add("GCF_PSFFR", 104, "identity", lambda s, l: s["GCF_PSFF"] / s["P_P"])
    add("GCF_PSNFFR", 105, "identity", lambda s, l: s["GCF_PSNFF"] / s["P_P"])
    add("LEND_PS", 106, "identity", lambda s, l: s["RP_PS"] - s["GCF_PS"])

    # --- Financial transfers, Eqs. (107)-(111) ---------------------------
    # Asset acquisitions scale with the sector's own output; the manual's
    # approximation for a sector whose flow-of-funds data does not exist at
    # this disaggregation (§3.3.2, p. 22).
    add("IBATR_PS", 107, "calibrated", lambda s, l: _ALPHA_IBAPS * s["GO_PS"])
    add("EQATR_PS", 108, "calibrated", lambda s, l: _ALPHA_EQAPS * s["GO_PS"])
    # θ_psb is the power sector's share of NFC bank loans (Table 5), used
    # throughout as the key that apportions NFC financial behaviour to the
    # power sector.
    add("EQLTR_PS", 109, "calibrated",
        lambda s, l: _THETA_PSB * s["EQATR_NMFI"])
    # Interest-bearing liabilities — bank loans — are the residual: whatever
    # the sector cannot fund from retained profit, asset sales or equity
    # issuance, it borrows. That is what makes credit conditions bind on
    # investment rather than on some notional financing gap.
    add("IBLTR_PS", 110, "identity",
        lambda s, l: ((s["IBATR_PS"] + s["EQATR_PS"] + s["RESTR_PS"])
                      - (s["LEND_PS"] + s["EQLTR_PS"])))
    add("RESTR_PS", 111, "calibrated", lambda s, l: _ETA_PSB * l["GDP"])

    # --- Revaluations and defaults, Eqs. (112)-(117) ---------------------
    # "Other transfers" are price revaluations and other volume changes.
    add("OTIBA_PS", 112, "calibrated", lambda s, l: _DELTA_IBAPS * l["IBA_PS"])
    add("OTEQA_PS", 113, "identity",
        lambda s, l: _BETA_DPS * (l["EQA_PS"] / l["EQL_NMFI"]) * s["OTEQL_NMFI"])
    # An explicit equity valuation: the sector's market value is its dividend
    # stream capitalised at the risk-free rate plus a spread, and the
    # revaluation is whatever moves last period's stock to that value. So a
    # rise in the government's borrowing rate marks the power sector down —
    # the model's one asset-price channel from monetary policy to the green
    # transition.
    add("OTEQL_PS", 114, "identity",
        lambda s, l: _div(s["DIVP_PS"], s["r_IBL_GVT"] + _BETA_EQLPS,
                          "§3.3.2 eq. (114)", "discount rate") - l["EQL_PS"])
    add("OTRES_PS", 115, "calibrated", lambda s, l: _DELTA_RESPS * l["RES_PS"])
    # Loan write-offs: the only way a liability stock falls other than by
    # repayment. Note the sign — Eq. (116) is non-positive by construction.
    add("OTIBL_PS", 116, "identity", lambda s, l: -s["DEF_PS"] * l["IBL_PS"])
    # Defaults rise with illiquidity along a logistic bounded by def_max.
    # This is the model's financial-instability channel: an illiquid power
    # sector defaults, which writes down MFI assets, which tightens CR_PS
    # through Eq. (138) and chokes the investment that would have fixed it.
    add("DEF_PS", 117, "behavioural",
        lambda s, l: _DEF_MAX / (
            1.0 + _DEF0_PS * math.exp(_DEF1 - _DEF2 * l["ILLIQ_PS"])))

    # --- Balance sheet, Eqs. (118)-(126) ---------------------------------
    # Stock = lagged stock + transaction + revaluation. These are the SFC
    # accumulation identities; nothing may be added to or dropped from them
    # without breaking the §2.2 matrices.
    add("IBA_PS", 118, "identity",
        lambda s, l: l["IBA_PS"] + s["IBATR_PS"] + s["OTIBA_PS"])
    add("IBL_PS", 119, "identity",
        lambda s, l: l["IBL_PS"] + s["IBLTR_PS"] + s["OTIBL_PS"])
    add("EQA_PS", 120, "identity",
        lambda s, l: l["EQA_PS"] + s["EQATR_PS"] + s["OTEQA_PS"])
    add("EQL_PS", 121, "identity",
        lambda s, l: l["EQL_PS"] + s["EQLTR_PS"] + s["OTEQL_PS"])
    add("FA_PS", 122, "identity", lambda s, l: s["IBA_PS"] + s["EQA_PS"])
    add("FL_PS", 123, "identity", lambda s, l: s["IBL_PS"] + s["EQL_PS"])
    add("FNWM_PS", 124, "identity", lambda s, l: s["FA_PS"] - s["FL_PS"])
    # RES is the residual financial instrument that absorbs the national
    # accounts' statistical discrepancy — carried explicitly so the
    # accounting closes rather than being netted away (see §2.2).
    add("RES_PS", 125, "identity",
        lambda s, l: l["RES_PS"] + s["RESTR_PS"] + s["OTRES_PS"])
    add("FNW_PS", 126, "identity", lambda s, l: s["FNWM_PS"] + s["RES_PS"])

    # --- Capital stock, Eqs. (127)-(133) ---------------------------------
    # Real capital is the proxy for generation *capacity* (with CF the
    # conversion), so these two lines are the physical core of the model:
    # perpetual inventory on each technology separately, at a common
    # depreciation rate. There is no early scrapping of fossil plant here —
    # fossil capacity can only run down at δ_KPS unless a scenario retires it.
    add("K_PSFFR", 127, "identity",
        lambda s, l: (1.0 - s["delta_KPS"]) * l["K_PSFFR"] + s["GCF_PSFFR"])
    add("K_PSNFFR", 128, "identity",
        lambda s, l: (1.0 - s["delta_KPS"]) * l["K_PSNFFR"] + s["GCF_PSNFFR"])
    add("K_PSR", 129, "identity", lambda s, l: s["K_PSFFR"] + s["K_PSNFFR"])
    # Eq. (130) is a constant, written as a lag so the rate is whatever the
    # initial period was seeded with; §5 tabulates it only per technology
    # (see MANUAL_GAPS["delta_KPS"]).
    add("delta_KPS", 130, "calibrated", lambda s, l: l["delta_KPS"])
    add("K_PS", 131, "identity", lambda s, l: s["K_PSNFF"] + s["K_PSFF"])
    add("K_PSFF", 132, "identity", lambda s, l: s["K_PSFFR"] * s["P_P"])
    add("K_PSNFF", 133, "identity", lambda s, l: s["K_PSNFFR"] * s["P_P"])
    add("NW_PS", 134, "identity", lambda s, l: s["FNW_PS"] + s["K_PS"])

    # --- Financial position and credit rationing, Eqs. (135)-(138) -------
    add("LEV_PS", 135, "identity",
        lambda s, l: _div(s["IBL_PS"], s["K_PS"], "§3.3.2 eq. (135)",
                          "capital stock"))
    # Cash out over cash in, including investment and depreciation on the
    # outflow side: a sector investing heavily in capital-intensive
    # non-fossil generation is *by construction* more illiquid, and Eq. (117)
    # then raises its default rate and Eq. (138) rations its credit. That
    # feedback is the model's central obstacle to a fast transition, and it
    # is why SUBS_PS sits in the denominator — a subsidy works here by
    # relieving illiquidity, not by changing relative prices.
    add("ILLIQ_PS", 136, "identity",
        lambda s, l: _div(
            (s["INTP_PS"] + s["ITAX_PS"] + s["DIVP_PS"] + s["GCF_PS"]
             + s["delta_KPS"] * s["K_PS"] + s["IBATR_PS"] + s["EQATR_PS"]
             + s["IC_PPS"] + s["IC_PSPS"]),
            (s["GO_PS"] + s["INTR_PS"] + s["DIVR_PS"] + s["EQLTR_PS"]
             + s["IBLTR_PS"] + s["SUBS_PS"]),
            "§3.3.2 eq. (136)", "cash inflows"))
    # Income before interest and after depreciation, over interest paid: how
    # many times the sector covers its debt service. Below 1 it is borrowing
    # to pay interest.
    add("DSR_PS", 137, "identity",
        lambda s, l: _div(s["YD_PS"] - s["delta_KPS"] * l["K_PS"] + s["INTP_PS"],
                          s["INTP_PS"], "§3.3.2 eq. (137)", "interest paid"))
    # Credit rationing tightens with the sector's debt service and with MFI
    # leverage: banks ration when the borrower looks bad *and* when they
    # themselves do. Both slope parameters are untabulated (MANUAL_GAPS), so
    # at the defaults this is a constant logistic(α_0CRPS).
    add("CR_PS", 138, "behavioural",
        lambda s, l: _logistic(
            _A0_CRPS
            + A1_CRPS * l["CR_PS"]
            - A2_CRPS * l["DSR_PS"]
            + A3_CRPS * (l["FL_MFI"] / l["FA_MFI"])))
