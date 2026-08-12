"""§3.3.2 power generation sector, manual Eqs. (71)-(138).

Same two things as tests/test_production.py, and the same standard:

1. **Transcription** — each equation computes what the manual prints, checked
   against the manual's own §5 Table 6 initial values, which is the only
   independent reference available before the oracle comparison.
2. **Closure** — electricity output is demand-led, the electricity price is
   marginal-cost with a *fossil* marginal plant, investment is
   credit-rationed, and the green/fossil split is driven by capital rather
   than by substitution. Each is pinned, because each could be "fixed" into a
   different model.

Thirty of the section's sixty-eight equations reproduce Table 6 inside its
four-significant-figure printing noise. Fourteen do not, and are pinned
individually below with the measured gap rather than absorbed into a
tolerance; four of those fourteen are *sign* contradictions that no lag or
data vintage can explain, and four more are one systematic finding about
Table 6's capital deflator. The remaining twenty-four either read a lagged
variable, so a snapshot cannot check them at all, or determine a variable
Table 6 never tabulates. For those the tests say only what a snapshot
supports — which lagged value each one implies, and where the manual is
silent, which explicit default was chosen and how wrong it is.
"""

from __future__ import annotations

import math

import pytest

from define_uk.model.calibration import INITIAL_VALUES, PARAMETERS
from define_uk.model.registry import Registry
from define_uk.model.sectors import power
from define_uk.model.solver import solve_period

# Four-significant-figure printing in Table 6, as in tests/test_macro.py.
SIG_FIG_TOL = 1e-3


@pytest.fixture(scope="module")
def registry() -> Registry:
    r = Registry()
    power.register(r)
    return r


@pytest.fixture(scope="module")
def equations(registry) -> dict:
    return {eq.name: eq for eq in registry}


@pytest.fixture(scope="module")
def initial() -> dict[str, float]:
    """Table 6 initial values, plus the eight things it does not tabulate.

    Every addition is either a POLICY_DEFAULTS switch (all inert in the
    baseline) or recovered from Table 6 by an equation of this very section,
    never invented:

    - ``delta_KPS``: the common value of the tabulated δ_KPSFF and δ_KPSNFF,
      which are equal.
    - ``GCF_PSD``: Eqs. (97)+(98) sum to it, since prop_NFF cancels.
    - ``prop_NFF``: the same two equations' ratio.
    - ``GCF_PS``: Eq. (102); corroborated by Eq. (106) reproducing LEND_PS.
    - ``DSR_PS``: Eq. (137) read at the snapshot, needed only as a lag.
    - ``K_PS_LAG``: K_PS at t-2, for Eq. (96)'s two-period lag. Held at the
      tabulated K_PS, which makes Eq. (96)'s autoregressive term exactly the
      current investment rate — the steady reading, and the only one a
      snapshot supports.
    - ``Fu_PS``/``Eu_PS``: Eq. (89) at CRED = 0, which is u_PS.
    """
    values = dict(INITIAL_VALUES)
    values.update(power.POLICY_DEFAULTS)
    values["delta_KPS"] = INITIAL_VALUES["delta_KPSFF"]
    values["GCF_PSD"] = INITIAL_VALUES["GCF_PSFFD"] + INITIAL_VALUES["GCF_PSNFFD"]
    values["prop_NFF"] = INITIAL_VALUES["GCF_PSNFFD"] / values["GCF_PSD"]
    values["GCF_PS"] = INITIAL_VALUES["GCF_PSNFF"] + INITIAL_VALUES["GCF_PSFF"]
    values["K_PS_LAG"] = INITIAL_VALUES["K_PS"]
    values["Eu_PS"] = INITIAL_VALUES["u_PS"]
    values["Fu_PS"] = INITIAL_VALUES["u_PS"]
    values["DSR_PS"] = (
        INITIAL_VALUES["YD_PS"]
        - values["delta_KPS"] * INITIAL_VALUES["K_PS"]
        + INITIAL_VALUES["INTP_PS"]
    ) / INITIAL_VALUES["INTP_PS"]
    return values


# --------------------------------------------------------------------------
# 1. Registration and provenance
# --------------------------------------------------------------------------

def test_registers_every_equation_from_71_to_138(registry):
    """§3.3.2 is Eqs. (71)-(138) inclusive — 68 equations, none missing.

    (70) is the last equation of §3.3.1 and (139) the first of §3.3.3, the
    input-output block; neither may leak in here.
    """
    refs = {int(eq.manual_ref.split("(")[1].rstrip(")")) for eq in registry}
    assert refs == set(range(71, 139)), sorted(set(range(71, 139)) - refs)
    assert len(registry) == 68


def test_every_equation_cites_section_3_3_2(registry):
    for eq in registry:
        assert eq.manual_ref.startswith("§3.3.2 eq. ("), eq.manual_ref


def test_no_equation_determines_a_variable_this_section_treats_as_exogenous(registry):
    overlap = set(registry.names()) & set(power.EXOGENOUS_TO_SECTION)
    assert not overlap, sorted(overlap)


def test_section_supplies_what_macro_and_production_take_as_given(registry):
    """§3.2 lists GO_PS and GCF_PS as exogenous; §3.3.1 lists F_PSR.

    If any of the three were dropped here the sections would never close, and
    the failure would surface far downstream as a missing key.
    """
    from define_uk.model.sectors import macro, production

    names = set(registry.names())
    assert names & set(macro.EXOGENOUS_TO_SECTION) == {"GO_PS", "GCF_PS"}
    assert names & set(production.EXOGENOUS_TO_SECTION) == {"F_PSR"}


# --------------------------------------------------------------------------
# 2. Transcription: the manual's own initial values satisfy each equation
# --------------------------------------------------------------------------

# Every entry holds at Table 6's printing precision. The ten that do not are
# excluded and pinned individually in section 3; the nine lag-dependent ones
# are handled in section 4, and the five Table 6 never tabulates in section 5.
IDENTITIES = [
    "F_PS", "F_PSR", "GO_PSR", "GO_PS", "COST_PS", "GOS_PS", "beta_NFF",
    "AC_NFF", "AC_FF", "MC_FF", "MC_ELEC",
    "u_FF", "u_NFF", "u_PS",
    "YD_PS", "DIVR_PS", "RP_PS",
    "GCF_PSFF", "GCF_PSNFF", "GCF_PSR", "LEND_PS",
    "EQLTR_PS", "IBLTR_PS",
    "FA_PS", "FL_PS", "FNWM_PS", "FNW_PS",
    "K_PSR", "NW_PS", "LEV_PS",
]


@pytest.mark.parametrize("name", IDENTITIES)
def test_identity_holds_at_manual_initial_values(equations, initial, name):
    """Worst residual here is Eq. (73), GO_PSR, at 9.1e-4 — still rounding.

    That one deserves its arithmetic spelled out, because it is the only
    entry near the tolerance: L_PSP prints as 0.1014, so it carries
    ±0.00005 × 777.8 = ±0.039 on its own, L_PSPS ±0.0005 × 22.87 = ±0.011,
    and GO_PSR prints as 121.0, worth a further ±0.05. A residual up to ~0.1
    (8e-4 relative) is what four-significant-figure printing predicts.
    """
    equation = equations[name]
    computed = equation.func(initial, initial)
    tabulated = initial[name]
    assert computed == pytest.approx(tabulated, rel=SIG_FIG_TOL), (
        f"{equation.manual_ref} computes {computed!r} but Table 6 tabulates "
        f"{tabulated!r} (relative error "
        f"{abs(computed - tabulated) / abs(tabulated):.2e})"
    )


def test_gross_output_accommodates_electricity_demand_with_no_capacity_term(
    equations, initial
):
    """Eq. (73) is the Leontief inverse and nothing else.

    Real power output is linear and homogeneous in final demand, with no
    capacity ceiling and no price response — the same demand-led closure as
    §3.3.1's Eq. (46). u_PS exists (Eq. 87) but constrains nothing directly;
    it only steers investment, with a lag, through Eq. (96).
    """
    go = equations["GO_PSR"]
    base = go.func(initial, initial)
    doubled = go.func(
        dict(initial, F_PR=initial["F_PR"] * 2.0, F_PSR=initial["F_PSR"] * 2.0),
        initial,
    )
    assert doubled == pytest.approx(2.0 * base, rel=1e-12)

    # Production output pulls electricity: the IO link that having a separate
    # power sector is there to capture.
    assert go.func(dict(initial, F_PR=initial["F_PR"] + 1.0), initial) == (
        pytest.approx(base + initial["L_PSP"], rel=1e-9)
    )


def test_the_cost_split_partitions_the_sector_total(equations, initial):
    """Eqs. (78)+(79) must add up to the sector's whole cost base.

    Whatever β_NFF does, the fossil and non-fossil cost lines are a
    partition of indirect tax + fuel + intermediate consumption +
    depreciation. That total reproduces Table 6's COST_PSNFF + COST_PSFF =
    44.83 to 8.6e-4 — inside the printing noise — which is what localises the
    disagreement of Eqs. (78)-(79) with Table 6 to the *split* alone, and
    therefore to β_NFF. See the lag test in section 4.
    """
    total = (
        equations["COST_PSNFF"].func(initial, initial)
        + equations["COST_PSFF"].func(initial, initial)
    )
    tabulated = initial["COST_PSNFF"] + initial["COST_PSFF"]
    assert total == pytest.approx(tabulated, rel=SIG_FIG_TOL)

    # And the ingredients are exactly the ones the manual lists: Eq. (75)'s
    # cost base is *not* the same object — it excludes fuel and depreciation
    # and includes IC_PPS, so the two totals must differ.
    assert total != pytest.approx(initial["COST_PS"], rel=1e-2)


def test_only_fossil_generation_has_a_marginal_cost(equations, initial):
    """Eqs. (82)-(84): the price channel, and the one that carbon policy uses.

    Non-fossil marginal cost is zero (Heal, 2022), so the electricity price
    is set entirely by the fossil plant's fuel and carbon bill, discounted by
    the non-fossil share. Three things are pinned here because each would
    silently change every scenario if it were "fixed":

    - the carbon price reaches the price level only through Eq. (82), scaled
      by coverage COV_ETSPS (0.5 — half the sector's emissions are exempt or
      freely allocated);
    - the discount is non-linear in β_NFF with exponent μ_MCELEC = 0.325 < 1,
      so the price falls fastest *early* in the transition;
    - a higher non-fossil share lowers the price with no change in fuel
      costs at all.
    """
    mc_ff = equations["MC_FF"]
    dearer = mc_ff.func(dict(initial, P_ETS=initial["P_ETS"] * 2.0), initial)
    carbon_bill = (
        initial["COV_ETSPS"] * initial["P_ETS"] * initial["EMIS_ELEC"]
        / initial["E_ELECFF"]
    )
    assert dearer - mc_ff.func(initial, initial) == pytest.approx(
        carbon_bill, rel=1e-9
    )
    # Coverage below 1 dilutes the carbon price one-for-one.
    assert PARAMETERS["delta_COVETS2"] == 0.5 and initial["COV_ETSPS"] == 0.5

    # μ_MCELEC = 0.325 sits between the two rules it interpolates: exponent 0
    # is pure merit order (the price stays at the fossil marginal cost until
    # the last fossil unit closes) and exponent 1 is share-weighting. At
    # 0.325 the price is above the share-weighted rule everywhere — most of
    # the fossil marginal cost survives well past a 50% non-fossil share —
    # and the fall accelerates towards the end of the transition.
    mc_elec = equations["MC_ELEC"]
    assert PARAMETERS["mu_MCELEC"] == 0.325
    curve = {b: mc_elec.func(dict(initial, beta_NFF=b), initial)
             for b in (0.1, 0.2, 0.5, 0.8, 0.9)}
    assert list(curve.values()) == sorted(curve.values(), reverse=True)
    for share, value in curve.items():
        merit_order = initial["MC_FF"]
        share_weighted = initial["MC_FF"] * (1.0 - share)
        assert share_weighted < value < merit_order
    assert curve[0.5] / initial["MC_FF"] == pytest.approx(0.798, rel=1e-2)
    assert (curve[0.8] - curve[0.9]) > 3.0 * (curve[0.1] - curve[0.2])

    # And the price is proportional to the marginal cost, not to average
    # cost: AC_FF and AC_NFF are tracked (Eqs. 80-81) but never enter Eq. (84).
    price = equations["P_ELEC"]
    assert price.func(dict(initial, MC_ELEC=initial["MC_ELEC"] * 2.0), initial) == (
        pytest.approx(2.0 * price.func(initial, initial), rel=1e-12)
    )


def test_the_price_block_is_undefined_at_full_decarbonisation(equations, initial):
    """Eqs. (81), (82) and (85) all divide by a quantity that hits zero.

    This is not a hypothetical: Eq. (88) exists precisely to simulate a
    fossil ban, and the published scenarios push the non-fossil share up. At
    β_NFF = 1 the manual's marginal-cost pricing rule has no value, and its
    only hint is footnote 22 (a switch to average-cost pricing if demand
    outstrips supply). We raise rather than invent a limit, so a scenario
    that reaches this state fails loudly instead of producing a number
    nobody published.
    """
    for name, shock, ref in (
        ("AC_FF", {"beta_NFF": 1.0}, r"\(81\)"),
        ("MC_FF", {"E_ELECFF": 0.0}, r"\(82\)"),
        ("u_FF", {"K_PSFFR": 0.0}, r"\(85\)"),
    ):
        with pytest.raises(ValueError, match=ref):
            equations[name].func(dict(initial, **shock), initial)


def test_public_green_capital_crowds_out_private_green_investment(
    equations, initial
):
    """Eq. (86): K_GVTNFFR sits in the *denominator* of non-fossil utilisation.

    Government-built renewables raise measured capacity, which lowers u_NFF,
    which lowers the utilisation signal Eq. (96) invests on. That is the
    crowding-out channel Table 5's CON_FF parameterises, and it is why sce1
    and sce3 do not simply add to private investment. Pinned because it is
    counter-intuitive enough to be "corrected" away.
    """
    u_nff = equations["u_NFF"]
    assert u_nff.func(dict(initial, K_GVTNFFR=10.0), initial) < u_nff.func(
        initial, initial
    )


# --------------------------------------------------------------------------
# 3. Documented manual inconsistencies — implemented as printed, pinned here
# --------------------------------------------------------------------------

def test_eq_84_electricity_price_is_three_times_the_tabulated_value(
    equations, initial
):
    """DOCUMENTED MANUAL INCONSISTENCY — Eq. (84), the largest in the section.

    P_ELEC = (1 + MU_ELEC)·MC_ELEC with Table 5's MU_ELEC = 1.228 gives
    0.9725 against a tabulated P_ELEC of 0.3198 — a factor of 3.04. The
    implied mark-up is *negative*, -0.267: at the initial values the power
    sector sells electricity below its own marginal cost.

    Both sides are independently corroborated, which is what makes this a
    defect rather than a rounding artefact:

    - MC_ELEC = 0.4365 is reproduced by Eqs. (82)+(83) to 4.5e-5;
    - P_ELEC = 0.3198 is reproduced by Eq. (74) from the tabulated GO_PS and
      GO_PSR to 3.7e-4.

    So the manual's own two chains meet at a 3x contradiction. Table 5
    describes MU_ELEC as "calculated based on past data", i.e. a historical
    average, while the initial period is a gas-price spike in which wholesale
    marginal cost ran above the retail electricity price — an explanation,
    but not a reconciliation, and the sign of GOS_PS (-4.48, a loss-making
    power sector) says Table 6 means it. A mark-up that is a past-data mean
    cannot be *negative* on average, which is why this is not filed as a
    first-period jump the way Eqs. (94) and (111) are.

    The likelier account is that Eq. (84) is not the whole rule: §5 calibrates
    a long-run electricity price and a switch quarter for it (P_ELECLR,
    t_ELECswitch) that no printed equation uses. See
    test_the_electricity_price_long_run_rule_is_missing_from_the_body — the
    two findings should always be quoted together.
    """
    computed = equations["P_ELEC"].func(initial, initial)
    assert computed == pytest.approx(0.972522, rel=1e-4)
    assert initial["P_ELEC"] == 0.3198

    implied_markup = initial["P_ELEC"] / initial["MC_ELEC"] - 1.0
    assert implied_markup == pytest.approx(-0.2674, rel=1e-3)
    assert PARAMETERS["MU_ELEC"] == 1.228

    # The corroboration of the other side: Eq. (74) reproduces GO_PS from the
    # tabulated price, so P_ELEC is not free to be 0.9725.
    assert initial["GO_PSR"] * initial["P_ELEC"] == pytest.approx(
        initial["GO_PS"], rel=SIG_FIG_TOL
    )


def test_eq_94_dividend_rate_is_a_historical_mean_not_the_initial_period(
    equations, initial
):
    """DOCUMENTED MANUAL INCONSISTENCY — Eq. (94) DIVP_PS = α_DIVPPS·GO_PS.

    α_DIVPPS = 0.05453 against GO_PS = 38.71 gives 2.111, against a
    tabulated DIVP_PS of 1.251 — 69% high. The implied rate is 0.03232.

    Table 6 is the corroborated side: Eq. (95) reproduces the tabulated
    RP_PS = -5.217 *exactly* from it, so 1.251 is load-bearing in the
    manual's own accounts. Table 5 describes α_DIVPPS as "set as the mean of
    past implied values", so the equation is a long-run rule and the initial
    period is simply below it — but a model started from Table 6 still takes
    a 69% jump in power-sector dividends in its first step.
    """
    computed = equations["DIVP_PS"].func(initial, initial)
    assert computed == pytest.approx(2.11086, rel=1e-4)
    assert initial["DIVP_PS"] == 1.251
    assert initial["DIVP_PS"] / initial["GO_PS"] == pytest.approx(0.032317, rel=1e-4)

    relative_gap = abs(computed - initial["DIVP_PS"]) / initial["DIVP_PS"]
    assert relative_gap == pytest.approx(6.9e-1, rel=0.05)

    # The corroboration: Eq. (95) is exact on the tabulated dividend.
    assert (initial["YD_PS"] + initial["DIVR_PS"] - initial["DIVP_PS"]) == (
        pytest.approx(initial["RP_PS"], rel=1e-9)
    )


@pytest.mark.parametrize(
    "name,expected,tabulated,ref",
    [
        ("IBATR_PS", 0.468391, -1.065, "107"),
        ("OTIBA_PS", 0.0382614, -0.01658, "112"),
        ("OTEQA_PS", 1.51619, -1.208, "113"),
        ("OTIBL_PS", -0.0239026, 0.9797, "116"),
    ],
)
def test_four_transfer_equations_contradict_table_6_in_sign(
    equations, initial, name, expected, tabulated, ref
):
    """DOCUMENTED MANUAL INCONSISTENCY — Eqs. (107), (112), (113), (116).

    These four are the strongest findings in the section, because no lag, no
    data vintage and no rounding can rescue them: each right-hand side has a
    determinate sign, and Table 6 tabulates the opposite one.

    - Eq. (107) IBATR_PS = α_IBAPS·GO_PS, with α > 0 and GO_PS > 0, is
      strictly positive; Table 6 has -1.065.
    - Eq. (112) OTIBA_PS = δ_IBAPS·IBA_{t-1}, likewise; Table 6 has -0.01658.
    - Eq. (113) OTEQA_PS is β_dps × a positive stock ratio × OT_EQLNMFI, and
      OT_EQLNMFI is tabulated at +127.1; Table 6 has -1.208.
    - Eq. (116) OTIBL_PS = -DEF_PS·IBL_{t-1} is non-positive by construction;
      Table 6 has +0.9797.

    Table 6 is the corroborated side for the first of them: Eq. (90) implies
    a lagged IBA_PS of 37.047 and Eq. (118) independently implies 37.042 from
    the tabulated IBATR_PS and OTIBA_PS — 1.4e-4 apart. The tabulated
    transfers are internally consistent with the tabulated stocks and
    interest flows; it is the *rules that generate them* that are not.

    Table 5 makes this worse rather than better: α_IBAPS and δ_IBAPS are both
    marked "model-constrained", with the remark "calculated from Eq. (…)"
    naming the very equations that fail here. (The manual never defines its
    parameter categories, so "derived so the equation reproduces the initial
    value" is our reading of that remark rather than a stated rule — but it is
    the only reading under which the remark says anything, and Table 5's
    cross-references land on the right equations at the +9 offset that block
    of the table uses throughout.)

    One of the four is NOT specific to the power sector, and saying so is
    part of the finding: see the model-wide test below.
    """
    computed = equations[name].func(initial, initial)
    assert computed == pytest.approx(expected, rel=1e-4)
    assert initial[name] == tabulated
    assert computed * tabulated < 0.0, f"Eq. ({ref}) should disagree in sign"


def test_the_iba_transfer_sign_contradiction_is_model_wide(initial):
    """Eq. (107) is one instance of a manual-wide pattern, not a §3.3.2 bug.

    The manual prints the same α·GO rule for four sectors — Eq. (107)
    IBATR_PS, Eq. (177) IBATR_NFC, Eq. (231) IBATR_NMFI, Eq. (284) IBATR_GVT
    — every α is positive in Table 5 and every gross output is positive, so
    all four right-hand sides are strictly positive. Table 6 tabulates all
    four transfers *negative*, and not merely with the sign flipped: the
    magnitudes disagree by factors of 1.7 to 4.6 as well.

    This is pinned here so the §3.3.2 finding is never quoted as a
    power-sector defect. Whatever is wrong — the rule, or Table 6's sign
    convention for interest-bearing asset transfers — is wrong everywhere,
    and the sections that would confirm it (§3.4.1, §3.4.3, §3.4.4) are not
    implemented yet. Until they are, this test asserts only what Table 5 and
    Table 6 say on their own.
    """
    from define_uk.model.calibration import INITIAL_VALUES as V

    cases = [
        ("IBATR_PS", "alpha_IBAPS", "GO_PS", 107),
        ("IBATR_NFC", "alpha_IBANFC", "GO_P", 177),
        ("IBATR_NMFI", "alpha_IBANMFI", "GO", 231),
        ("IBATR_GVT", "alpha_IBAGVT", "GO", 284),
    ]
    for transfer, alpha, output, eq in cases:
        assert PARAMETERS[alpha] > 0.0, alpha
        assert V[output] > 0.0, output
        assert V[transfer] < 0.0, (
            f"Eq. ({eq}): Table 6 no longer tabulates {transfer} negative; "
            "the model-wide sign finding needs re-deriving"
        )


def test_the_lagged_interest_bearing_stocks_are_corroborated_two_ways(initial):
    """The corroboration behind the sign findings, stated on its own.

    Eqs. (90)/(118) and (91)/(119) are two independent routes to each lagged
    stock — one through the interest flow and the rate of return, one through
    the transfer and revaluation. They agree to 1.4e-4 and 3.6e-5. That is
    what licenses treating Table 6's IBATR_PS, OTIBA_PS, IBLTR_PS and
    OTIBL_PS as sound and Eqs. (107), (112) and (116) as the outliers.

    It also says the sector's interest-bearing stocks *shrank* into the
    initial period (37.05 -> 35.96 and 46.41 -> 45.94) while the economy grew
    at g = 1.019 — which is exactly why the transfer flows are negative.
    """
    iba_from_interest = initial["INTR_PS"] / initial["r_IBA_PS"]
    iba_from_stock = initial["IBA_PS"] - initial["IBATR_PS"] - initial["OTIBA_PS"]
    assert iba_from_interest == pytest.approx(iba_from_stock, rel=2e-4)
    assert iba_from_interest == pytest.approx(37.047, rel=1e-4)
    assert iba_from_stock > initial["IBA_PS"]

    ibl_from_interest = initial["INTP_PS"] / initial["r_IBL_PS"]
    ibl_from_stock = initial["IBL_PS"] - initial["IBLTR_PS"] - initial["OTIBL_PS"]
    assert ibl_from_interest == pytest.approx(ibl_from_stock, rel=1e-4)
    assert ibl_from_interest == pytest.approx(46.410, rel=1e-4)
    assert ibl_from_stock > initial["IBL_PS"]


def test_eq_108_equity_transfer_rate_misses_its_own_initial_value(
    equations, initial
):
    """DOCUMENTED MANUAL INCONSISTENCY — Eq. (108) EQATR_PS = α_EQAPS·GO_PS.

    0.01298 × 38.71 = 0.5025 against a tabulated 0.3836, 31% high; the
    implied α is 0.009910. Table 5 marks α_EQAPS "model-constrained,
    calculated from Eq. (117)" [Table 5's own numbering] — that is, derived
    so this equation reproduces the initial value, which it does not. Its
    description ("relationship between PS EQA transfers and total output from
    *production*") also disagrees with α_IBAPS's ("...from *power sector*")
    although both equations are printed against GO_PS; on the production
    reading the gap would be a factor of 39, so GO_PS is plainly meant.
    """
    computed = equations["EQATR_PS"].func(initial, initial)
    assert computed == pytest.approx(0.502456, rel=1e-4)
    assert initial["EQATR_PS"] == 0.3836
    assert initial["EQATR_PS"] / initial["GO_PS"] == pytest.approx(
        0.0099096, rel=1e-4
    )
    assert abs(computed - initial["EQATR_PS"]) / initial["EQATR_PS"] == (
        pytest.approx(3.1e-1, rel=0.05)
    )


def test_eq_111_residual_transfer_rate_is_off_by_a_factor_of_three_and_a_half(
    equations, initial
):
    """DOCUMENTED MANUAL INCONSISTENCY — Eq. (111) RESTR_PS = η_PSB·GDP_{t-1}.

    η_PSB = -0.05263 against GDP = 584.5 gives -30.76, against a tabulated
    RESTR_PS of -8.569 — 2.6x too large in absolute value, and the direction
    of the lag makes it worse, not better (a smaller lagged GDP gives a
    smaller number, but only by 1.9%). The implied η is -0.01466 on the
    lagged GDP, -0.01494 on the current one.

    A specific suspicion, recorded rather than acted on: η_PSB (-0.05263) is
    within 1% of η_NFCT (-0.05316), and Table 5 reuses NFC values for the
    power sector in nine other places. If η_PSB was copied from the NFC
    column, the power sector's own value was never entered.
    """
    computed = equations["RESTR_PS"].func(initial, initial)
    assert computed == pytest.approx(-30.7622, rel=1e-4)
    assert initial["RESTR_PS"] == -8.569
    assert abs(computed / initial["RESTR_PS"]) == pytest.approx(3.59, rel=1e-2)

    assert initial["RESTR_PS"] / initial["GDP"] == pytest.approx(-0.014660, rel=1e-4)
    # The lookalike, so nobody has to re-derive it.
    assert PARAMETERS["eta_PSB"] == -0.05263
    assert abs(PARAMETERS["eta_PSB"] / PARAMETERS["eta_NFCT"] - 1.0) < 0.01


def test_eq_131_nominal_power_capital_contradicts_its_own_components(
    equations, initial
):
    """DOCUMENTED MANUAL INCONSISTENCY — Eq. (131) K_PS = K_PSNFF + K_PSFF.

    The components sum to 136.62; Table 6 tabulates K_PS = 132.5, 3.1% less.
    The tabulated K_PS is also, to all four printed digits, exactly K_PSR —
    the *real* stock — which no deflator other than 1 permits, and Table 6's
    P_P is 1.035. So K_PS looks like the real value copied into the nominal
    row.

    Two corroborations that the components, not the total, are right:
    Eq. (129) sums the real stocks to 132.52, matching K_PSR to 1.5e-4; and
    Eqs. (132)-(133) reproduce the tabulated nominal components from the real
    ones at a deflator of 1.031, which is the deflator Table 6 uses for
    *every* capital stock (see the test below).

    The defect propagates inside Table 6 itself: Eqs. (134) and (135) both
    reproduce their tabulated values using 132.5 and neither does using
    136.62. So the manual is self-consistent downstream of an error.
    """
    computed = equations["K_PS"].func(initial, initial)
    assert computed == pytest.approx(136.62, rel=1e-4)
    assert initial["K_PS"] == initial["K_PSR"] == 132.5
    assert abs(computed - initial["K_PS"]) / initial["K_PS"] == (
        pytest.approx(3.1e-2, rel=0.05)
    )

    # Downstream, Table 6 uses the erroneous total consistently.
    assert initial["FNW_PS"] + initial["K_PS"] == pytest.approx(
        initial["NW_PS"], rel=SIG_FIG_TOL
    )
    assert initial["FNW_PS"] + computed != pytest.approx(
        initial["NW_PS"], rel=SIG_FIG_TOL
    )


@pytest.mark.parametrize(
    "name,real,nominal",
    [
        ("GCF_PSFFR", "GCF_PSFFR", "GCF_PSFF"),
        ("GCF_PSNFFR", "GCF_PSNFFR", "GCF_PSNFF"),
        ("K_PSFF", "K_PSFFR", "K_PSFF"),
        ("K_PSNFF", "K_PSNFFR", "K_PSNFF"),
    ],
)
def test_capital_deflator_in_table_6_is_1_031_not_the_tabulated_P_P(
    equations, initial, name, real, nominal
):
    """DOCUMENTED MANUAL INCONSISTENCY — Eqs. (104), (105), (132), (133).

    All four say a power-sector capital quantity is the real one times (or
    divided by) the production deflator P_P = 1.035. All four miss by
    3.7e-3 to 4.0e-3 — about four times the printing noise, in the same
    direction, because Table 6's own nominal/real ratios are 1.0309-1.0312.

    This is not a power-sector problem: K_P/K_PR = 1.0310, K_NFC/K_NFCR =
    1.0309, GCF/GCF_R = 1.0312 across the whole of Table 6. The capital block
    of Table 6 was deflated with an investment deflator of 1.031, and the
    equations of §3.3.2 (and §3.3.1's capital block with it) prescribe P_P.
    A 0.4% level error is small; it is recorded because it is systematic, and
    because it is evidence about which of Table 6's twins to trust when they
    disagree — as in Eq. (131) above.
    """
    computed = equations[name].func(initial, initial)
    tabulated = initial[name]
    gap = abs(computed - tabulated) / abs(tabulated)
    assert 3.0e-3 < gap < 5.0e-3, gap

    implied = initial[nominal] / initial[real]
    assert implied == pytest.approx(1.031, rel=1e-3)
    assert initial["P_P"] == 1.035
    # The same deflator, table-wide.
    assert initial["K_P"] / initial["K_PR"] == pytest.approx(1.031, rel=1e-3)
    assert initial["GCF"] / initial["GCF_R"] == pytest.approx(1.031, rel=1e-3)
    for nom, rl in (("K_NFC", "K_NFCR"), ("GCF_NFC", "GCF_NFCR"),
                    ("GCF_HH", "GCF_HHR"), ("GCF_GVT", "GCF_GVTR")):
        assert initial[nom] / initial[rl] == pytest.approx(1.031, rel=1e-3), nom

    # And therefore §3.2's Eq. (27) is the same finding, not a separate one:
    # GCF/P_P misses the tabulated GCF_R by the same 0.4%, same direction.
    assert initial["GCF"] / initial["P_P"] / initial["GCF_R"] == pytest.approx(
        1.031 / 1.035, rel=1e-3
    )


def test_eq_136_illiquidity_ratio_is_twenty_percent_above_the_tabulated_value(
    equations, initial
):
    """DOCUMENTED MANUAL INCONSISTENCY — Eq. (136), the illiquidity ratio.

    The printed ratio gives 1.2709 against a tabulated 1.046 — 21.5% high,
    ~200x the printing noise. Every ingredient is a tabulated Table 6 value
    (or, for GCF_PS, recovered from Eq. (102) and corroborated by Eq. (106)),
    so the disagreement is in the equation's composition, not in its inputs.

    It matters more than its size suggests: ILLIQ_PS is the sole argument of
    the default function Eq. (117), which is exponential in it, and a 21.5%
    error there is a factor of ~11 in the default rate. Pinned rather than
    tuned.
    """
    computed = equations["ILLIQ_PS"].func(initial, initial)
    assert computed == pytest.approx(1.27087, rel=1e-4)
    assert initial["ILLIQ_PS"] == 1.046
    assert abs(computed - initial["ILLIQ_PS"]) / initial["ILLIQ_PS"] == (
        pytest.approx(2.15e-1, rel=0.05)
    )
    # Subsidies enter the inflow side, so they reduce illiquidity — the
    # channel through which sce3's green power subsidy loosens credit.
    assert equations["ILLIQ_PS"].func(dict(initial, SUBS_PS=10.0), initial) < computed


# --------------------------------------------------------------------------
# 4. The lagged equations, which a snapshot cannot check
# --------------------------------------------------------------------------

def test_eqs_78_and_79_imply_a_lagged_non_fossil_share_of_0_51(
    equations, initial
):
    """Eqs. (78)-(79) apportion operating costs by β_NFF *at t-1*.

    At the current β_NFF = 0.5976 they give 17.07 and 27.80 against tabulated
    14.75 and 30.08 — 16% and 8% out. But their sum matches Table 6's to
    8.6e-4 (see the partition test above), so the disagreement is entirely in
    the split, and one number closes it: β_NFF,t-1 = 0.5095. That is *one*
    fact, not two, since the two implied values are tied by the total; the
    test says so rather than claiming independent corroboration.

    Whether 0.5095 -> 0.5976 in one quarter is a plausible lag or a defect,
    a snapshot cannot say — but the model's own structure makes it plausible:
    fossil plant runs at u_FF = 0.31 while non-fossil runs at u_NFF = 1.0, so
    fossil is the swing supplier and the *energy* mix moves with dispatch,
    far faster than the capacity mix behind it (which Eqs. (127)-(128) imply
    moved only 0.39 points over the same quarter).
    """
    ic = initial["IC_PSPS"] + initial["IC_OPPS"]
    implied_nff = (
        initial["COST_PSNFF"] - initial["ITAX_PSNFF"]
        - initial["delta_KPS"] * initial["K_PSNFF"]
    ) / ic
    implied_ff = 1.0 - (
        initial["COST_PSFF"] - initial["ITAX_PSFF"] - initial["IC_FUELPS"]
        - initial["delta_KPS"] * initial["K_PSFF"]
    ) / ic
    assert implied_nff == pytest.approx(0.50878, rel=1e-4)
    assert implied_ff == pytest.approx(0.51025, rel=1e-4)
    assert initial["beta_NFF"] == 0.5976

    # The equations do read the lag, not the current share.
    shocked = dict(initial, beta_NFF=0.99)
    assert equations["COST_PSNFF"].func(shocked, initial) == pytest.approx(
        equations["COST_PSNFF"].func(initial, initial), rel=1e-12
    )


def test_eqs_127_and_128_imply_fossil_retiring_and_non_fossil_building(
    equations, initial
):
    """Eqs. (127)-(128): perpetual inventory, and the transition in one line.

    Neither is checkable at a snapshot, but each implies its own lagged real
    stock, and the pair says something the model is *for*: fossil generation
    capital fell 0.40% over the initial quarter while non-fossil rose 1.42%.
    A common depreciation rate with a green-tilted investment split is the
    entire decarbonisation mechanism in DEFINE-UK — there is no scrapping
    rule and no technology frontier.
    """
    depreciation = 1.0 - initial["delta_KPS"]
    lagged_ff = (initial["K_PSFFR"] - initial["GCF_PSFFR"]) / depreciation
    lagged_nff = (initial["K_PSNFFR"] - initial["GCF_PSNFFR"]) / depreciation

    assert initial["K_PSFFR"] / lagged_ff - 1.0 == pytest.approx(-0.00395, rel=1e-2)
    assert initial["K_PSNFFR"] / lagged_nff - 1.0 == pytest.approx(0.01416, rel=1e-2)

    # The capacity mix, which moves far more slowly than the energy mix.
    def capacity_share(ff, nff):
        green = initial["CF_NFF"] * nff
        return green / (PARAMETERS["CF_FF"] * ff + green)

    assert capacity_share(lagged_ff, lagged_nff) == pytest.approx(0.3102, rel=1e-3)
    assert capacity_share(initial["K_PSFFR"], initial["K_PSNFFR"]) == (
        pytest.approx(0.3141, rel=1e-3)
    )


def test_eq_117_default_rate_implies_a_lagged_illiquidity_of_1_15(
    equations, initial
):
    """Eq. (117) DEF_PS reads ILLIQ_{t-1} — not checkable at one snapshot.

    On the steady reading it gives 1.66e-4 against a tabulated 5.203e-4, and
    it would be wrong to call that a 68% inconsistency: the function is
    exponential in the lag, so the tabulated default rate implies
    ILLIQ_PS,t-1 = 1.149 against a current 1.046. A 10% fall in illiquidity
    within the initial period is unremarkable; what the test pins is the
    exponential sensitivity itself, since that is what makes Eq. (136)'s 21%
    error consequential.
    """
    steady = equations["DEF_PS"].func(initial, initial)
    assert steady == pytest.approx(1.66357e-4, rel=1e-4)

    implied_illiq = (
        PARAMETERS["def1"]
        - math.log((PARAMETERS["def_max"] / initial["DEF_PS"] - 1.0)
                   / PARAMETERS["def0_PS"])
    ) / PARAMETERS["def2"]
    assert implied_illiq == pytest.approx(1.1494, rel=1e-4)

    # Exponential: a 21.5% rise in illiquidity multiplies defaults by ~11.
    stressed = equations["DEF_PS"].func(
        initial, dict(initial, ILLIQ_PS=initial["ILLIQ_PS"] * 1.215)
    )
    assert stressed / steady == pytest.approx(11.0, rel=0.2)
    # Bounded above by def_max whatever happens.
    assert equations["DEF_PS"].func(
        initial, dict(initial, ILLIQ_PS=1e6)
    ) == pytest.approx(PARAMETERS["def_max"], rel=1e-9)


def test_eq_114_equity_revaluation_cannot_be_reconciled_from_a_snapshot(
    equations, initial
):
    """Eq. (114) OT_EQLPS capitalises dividends and nets off EQL_{t-1}.

    Three quantities have to agree and only two are tabulated. Eq. (121)
    implies EQL_PS,t-1 = 101.28 from the tabulated stock, transfer and
    revaluation; feeding that back into Eq. (114) requires DIVP_PS = 1.607,
    which matches neither Table 6's 1.251 nor Eq. (94)'s 2.111. The test
    records all three numbers rather than picking one.

    What is checkable is the mechanism, and it is pinned: a higher risk-free
    rate marks the sector's equity down. That is a real transmission channel
    from monetary policy to the green transition, via Eq. (121) -> Eq. (123)
    -> Eq. (136) -> credit rationing.
    """
    lagged_eql = initial["EQL_PS"] - initial["EQLTR_PS"] - initial["OTEQL_PS"]
    assert lagged_eql == pytest.approx(101.28, rel=1e-4)

    needed_divp = (initial["OTEQL_PS"] + lagged_eql) * (
        initial["r_IBL_GVT"] + PARAMETERS["beta_EQLPS"]
    )
    assert needed_divp == pytest.approx(1.6069, rel=1e-3)
    assert initial["DIVP_PS"] == 1.251

    dearer_money = equations["OTEQL_PS"].func(
        dict(initial, r_IBL_GVT=initial["r_IBL_GVT"] * 2.0), initial
    )
    assert dearer_money < equations["OTEQL_PS"].func(initial, initial)


def test_eq_115_residual_revaluation_is_an_order_of_magnitude_short(
    equations, initial
):
    """Eq. (115) OT_RESPS = δ_RESPS·RES_{t-1}, lagged and still far out.

    Eq. (125) implies RES_PS,t-1 = -5.609 from the tabulated stock and flows;
    δ_RESPS × that is 0.527, against a tabulated OT_RESPS of 6.692 — a factor
    of 12.7, and the sign of δ_RESPS (-0.09403) means it only produces a
    positive revaluation from a negative stock at all. This one is recorded,
    not diagnosed: RES is the residual instrument that absorbs the national
    accounts' statistical discrepancy, so its "rule" is a curve fit to a
    residual and there is no economics to appeal to.
    """
    lagged_res = initial["RES_PS"] - initial["RESTR_PS"] - initial["OTRES_PS"]
    assert lagged_res == pytest.approx(-5.609, rel=1e-3)

    implied = PARAMETERS["delta_RESPS"] * lagged_res
    assert implied == pytest.approx(0.5274, rel=1e-3)
    assert initial["OTRES_PS"] / implied == pytest.approx(12.7, rel=1e-2)


# --------------------------------------------------------------------------
# 5. What Table 6 never tabulates, recovered from what it does
# --------------------------------------------------------------------------

def test_the_untabulated_investment_variables_are_recovered_from_table_6(
    equations, initial
):
    """GCF_PSD, prop_NFF and GCF_PS are absent from Table 6.

    All three are recoverable, and the recovery is not free — it has to close
    against something Table 6 does print, and it does: GCF_PS = 2.1528 from
    Eq. (102) reproduces the tabulated LEND_PS = -7.37 through Eq. (106) to
    2.7e-5. Recorded in MANUAL_GAPS so the reconstruction is visible rather
    than assumed.
    """
    assert "untabulated_endogenous" in power.MANUAL_GAPS
    for name in ("GCF_PSD", "prop_NFF", "GCF_PS", "DSR_PS", "Fu_PS", "Eu_PS"):
        assert name not in INITIAL_VALUES, (
            f"{name} is now tabulated — drop its reconstruction from the "
            "`initial` fixture and its MANUAL_GAPS entry"
        )

    assert initial["GCF_PSD"] == pytest.approx(2.4433, rel=1e-4)
    assert initial["prop_NFF"] == pytest.approx(0.69169, rel=1e-4)
    assert initial["GCF_PS"] == pytest.approx(2.1528, rel=1e-4)
    # The check that makes it evidence.
    assert equations["LEND_PS"].func(initial, initial) == pytest.approx(
        INITIAL_VALUES["LEND_PS"], rel=SIG_FIG_TOL
    )


def test_eq_99_investment_split_default_is_wrong_and_says_so(equations, initial):
    """MANUAL GAP — Eq. (99) has neither its parameters nor its variables.

    α_0bNFF and α_1bNFF are absent from Table 5, and r_KNFF and r_KFF — the
    profit rates of non-fossil and fossil capital — are never defined
    anywhere in the manual, in any section. At the explicit 0.0 defaults the
    logistic returns exactly 1/2, against the 0.6917 Table 6 implies.

    This is the single largest hole in §3.3.2: prop_NFF is what steers
    investment green, so the section as published cannot reproduce its own
    baseline investment split. Pinned at the wrong answer deliberately — if
    someone quietly tunes the defaults to fit Table 6, this fails.
    """
    assert "alpha_bNFF_and_capital_profit_rates" in power.MANUAL_GAPS
    assert power.A0_BNFF == power.A1_BNFF == 0.0
    assert equations["prop_NFF"].func(initial, initial) == pytest.approx(0.5)
    assert initial["prop_NFF"] == pytest.approx(0.69169, rel=1e-4)

    # And nothing has been published since.
    for symbol in ("alpha0_bNFF", "alpha1_bNFF"):
        assert symbol not in PARAMETERS
    for symbol in ("r_KNFF", "r_KFF"):
        assert symbol not in INITIAL_VALUES


def test_eq_96_intercept_is_missing_and_the_implied_value_is_recorded_unused(
    equations, initial
):
    """MANUAL GAP — Eq. (96)'s α_0GCFPS is not in Table 5.

    What Table 5 does carry is α_0GCFFF and α_0GCFNFF, "parameter in the
    power sector fossil/non-fossil fuel investment equation" — the intercepts
    of a *split* investment rule that v1.1's Eq. (96) plus Eqs. (97)-(98)
    have replaced. Neither can be substituted without guessing which.

    Defaulted to 0.0, which makes desired power-sector investment negative at
    Table 6's utilisation: α_1GCFNFC·(u_PS - u_T) = 0.02948 × (-0.278) is
    worth more than the autoregressive term. So §3.3.2 as published cannot be
    simulated forward, and this test is the record of why. The steady-state
    reading of Table 6 implies about 0.0210 — asserted here so it is not
    re-derived, and deliberately not used, because both of Eq. (96)'s
    right-hand-side terms are lagged and the steady reading is an assumption.
    """
    assert "alpha0_GCFPS" in power.MANUAL_GAPS
    assert power.A0_GCFPS == 0.0
    assert "alpha0_GCFPS" not in PARAMETERS
    assert PARAMETERS["alpha0_GCFFF"] == 0.01465
    assert PARAMETERS["alpha0_GCFNFF"] == 0.02144

    rate = initial["GCF_PSD"] / initial["K_PS"]
    implied_intercept = rate - (
        PARAMETERS["alpha1_GCFNFC"] * (initial["u_PS"] - PARAMETERS["u_T"])
        + PARAMETERS["alpha2_GCFNFC"] * rate
    )
    assert implied_intercept == pytest.approx(0.02101, rel=1e-3)

    # At the default the investment function is unusable, and visibly so.
    assert equations["GCF_PSD"].func(initial, initial) < 0.0


def test_eq_138_credit_rationing_slopes_are_missing(equations, initial):
    """MANUAL GAP — Eq. (138) needs α_1CRPS, α_2CRPS, α_3CRPS; §5 has none.

    Table 5 tabulates only α_0CRPS = 2.736. With the slopes at their explicit
    0.0 defaults, credit rationing degenerates to a constant logistic(2.736)
    = 0.939 — the mechanism the manual builds the sector around (banks ration
    when the borrower's debt service worsens *and* when their own balance
    sheet does) is simply absent from the published calibration.

    The NFC equation is printed with the same structure and its slopes are
    tabulated, and Table 5 reuses NFC values for the power sector in nine
    other places — but borrowing them is our inference, not the manual's
    instruction, and it does not reproduce Table 6 either (it gives 0.598
    against a tabulated CR_PS of 0.1188). Recorded, not adopted.
    """
    assert "alpha_CRPS_slopes" in power.MANUAL_GAPS
    assert power.A1_CRPS == power.A2_CRPS == power.A3_CRPS == 0.0
    for symbol in ("alpha1_CRPS", "alpha2_CRPS", "alpha3_CRPS"):
        assert symbol not in PARAMETERS

    degenerate = equations["CR_PS"].func(initial, initial)
    assert degenerate == pytest.approx(0.93917, rel=1e-4)
    assert initial["CR_PS"] == 0.1188

    # The nine places Table 5 reuses NFC values for the power sector — the
    # evidence for the suspicion, kept explicit so it is checkable.
    for ps_name, nfc_name in (
        ("spr_psl", "spr_nfcl"), ("delta_IBLPS", "delta_IBLNFC"),
        ("delta_EQAPS", "delta_EQANFC"), ("delta_EQLPS", "delta_EQLNFC"),
        ("sigma_ps", "sigma_nfc"), ("tau_rlps", "tau_rlnfc"),
        ("tau_raps", "tau_ranfc"), ("delta_IBAPS", "delta_IBANFC"),
        ("beta_EQLPS", "beta_EQLNFC"),
    ):
        assert PARAMETERS[ps_name] == PARAMETERS[nfc_name], ps_name


def test_the_electricity_price_long_run_rule_is_missing_from_the_body(registry):
    """MANUAL GAP — §5 calibrates an electricity price rule §3 never prints.

    Table 5 tabulates t_ELECswitch = 153, "Time index (quarter) for the switch
    in the electricity price long-run formation rule", and Table 6 tabulates
    P_ELECLR, "Long run electricity price", "set equal to initial electricity
    price". Neither symbol occurs anywhere in §§1-4. The only electricity
    price equation printed is Eq. (84), a fixed mark-up over marginal cost
    with no long-run term and no switch — so §3 does not contain the rule §5
    calibrates, and no equation in this registry consumes either symbol.

    This is the mirror image of the missing-parameter gaps: a *tabulated*
    symbol with no equation, as with Table 5's α_0GCFFF and α_0GCFNFF (which
    §3.3.2 replaced with Eq. (96) but §5 still carries). It is also the most
    economical explanation of Eq. (84)'s factor of 3.04 — a missing equation
    rather than a wrong number — and it is recorded so that finding is quoted
    with that alternative attached.
    """
    assert "electricity_price_long_run_rule" in power.MANUAL_GAPS

    # Both are transcribed in §5 ...
    assert PARAMETERS["t_ELECswitch"] == 153
    assert INITIAL_VALUES["P_ELECLR"] == INITIAL_VALUES["P_ELEC"] == 0.3198

    # ... and neither is read by any §3.3.2 equation. P_ELEC is determined by
    # Eq. (84) alone: perturbing the long-run price changes nothing.
    values = dict(INITIAL_VALUES)
    values.update(power.POLICY_DEFAULTS)
    values["delta_KPS"] = INITIAL_VALUES["delta_KPSFF"]
    equations = {eq.name: eq for eq in registry}
    base = equations["P_ELEC"].func(values, values)
    shocked = equations["P_ELEC"].func(
        dict(values, P_ELECLR=10.0, t_ELECswitch=0), values
    )
    assert shocked == base

    # The orphan investment intercepts, the same class of gap, already
    # recorded under alpha0_GCFPS.
    assert {"alpha0_GCFFF", "alpha0_GCFNFF"} <= set(PARAMETERS)


def test_delta_KPS_is_seeded_from_the_two_equal_tabulated_rates(
    equations, initial
):
    """MANUAL GAP — Eq. (130)'s δ_KPS is not tabulated; the split rates are.

    δ_KPSFF and δ_KPSNFF are both 0.01227, so there is no ambiguity, and
    Eq. (130) carries the seeded value forward unchanged forever. If a
    revision ever makes the two rates differ, Eqs. (127)-(128) need rewriting
    rather than reseeding — which is why this asserts equality rather than
    just picking one.
    """
    assert "delta_KPS" in power.MANUAL_GAPS
    assert "delta_KPS" not in INITIAL_VALUES
    assert INITIAL_VALUES["delta_KPSFF"] == INITIAL_VALUES["delta_KPSNFF"] == 0.01227
    assert equations["delta_KPS"].func(initial, initial) == 0.01227


def test_government_generation_capital_is_zero_in_the_baseline(equations, initial):
    """MANUAL GAP — K_GVTNFFR is untabulated, and measured at zero twice over.

    Eq. (86) returns u_NFF = 1.0000 against a tabulated 1.0 at K_GVTNFFR = 0,
    and §3.1's Eq. (5) returns E_ELECMAX = 127.27 against a tabulated 127.3.
    Two independent equations, neither fitted to the other. It is a scenario
    instrument, so its baseline value is a fact about the baseline rather
    than a gap in the data.
    """
    assert "K_GVTNFFR" in power.MANUAL_GAPS
    assert "K_GVTNFFR" not in INITIAL_VALUES
    assert power.POLICY_DEFAULTS["K_GVTNFFR"] == 0.0

    assert equations["u_NFF"].func(initial, initial) == pytest.approx(
        initial["u_NFF"], rel=SIG_FIG_TOL
    )
    elecmax = (
        PARAMETERS["CF_FF"] * initial["K_PSFFR"]
        + initial["CF_NFF"] * (initial["K_PSNFFR"] + 0.0)
    )
    assert elecmax == pytest.approx(initial["E_ELECMAX"], rel=SIG_FIG_TOL)


# --------------------------------------------------------------------------
# 6. The forward-looking block, Eqs. (88)-(89)
# --------------------------------------------------------------------------

def test_the_baseline_expectation_is_myopic_and_equals_current_utilisation(
    equations, initial
):
    """Eqs. (88)-(89) are inert in the baseline, and must be.

    With no ban the first branch of Eq. (88) is the whole grid's capacity,
    which is E_ELECMAX minus the K_GVTNFFR term — so it equals u_PS exactly
    while government generation capital is zero, which is what the manual's
    own annotation on that branch asserts. And with CRED = 0 Eq. (89) puts no
    weight on expectations at all.
    """
    assert equations["Eu_PS"].func(initial, initial) == pytest.approx(
        initial["u_PS"], rel=SIG_FIG_TOL
    )
    assert equations["Fu_PS"].func(initial, initial) == initial["u_PS"]


def test_an_announced_ban_raises_expected_utilisation_before_it_bites(
    equations, initial
):
    """Eq. (88)'s second branch, and the point of the whole 1.1 addition.

    Strike fossil capacity out of the denominator and expected utilisation
    jumps from 0.53 to 1.67 — a signal to invest that arrives *before* the
    ban does. Eq. (89) then mixes it with the myopic rate by credibility, so
    a half-believed announcement moves investment half as much.

    Two things are pinned. First the magnitude, because the manual asserts
    the second branch exceeds u_PS and that is only true while fossil
    capacity is non-zero. Second the linearity in CRED, because that is what
    makes credibility a policy lever rather than a switch.
    """
    banned = dict(initial, t_FFBAN=10.0, t_PS=0.0)
    expected = equations["Eu_PS"].func(banned, initial)
    assert expected == pytest.approx(1.6732, rel=1e-3)
    assert expected > initial["u_PS"]

    for credibility in (0.0, 0.25, 0.5, 1.0):
        blended = equations["Fu_PS"].func(dict(banned, CRED=credibility), initial)
        assert blended == pytest.approx(
            credibility * expected + (1.0 - credibility) * initial["u_PS"], rel=1e-9
        )


def test_hyperbolic_weights_are_normalised_so_they_average_the_path(
    equations, initial
):
    """Eq. (89) divides by N = Σ δ^τ, so the discounting is a weighting.

    That is easy to get wrong — the same expression without N would be a
    present value and would scale F(u_PS) by 1/(1-δ). Here a constant
    expected path must come back unchanged whatever δ and T are, and a ban
    that arrives part-way through the horizon must be weighted between the
    two branches, never outside them.
    """
    banned = dict(initial, t_FFBAN=10.0, t_PS=0.0, CRED=1.0)
    flat = equations["Fu_PS"].func(dict(banned, T_PSPLAN=8.0, delta_PSPLAN=0.9), initial)
    assert flat == pytest.approx(
        equations["Eu_PS"].func(banned, initial), rel=1e-9
    )

    # A ban that lapses inside the horizon: strictly between the branches.
    partial = dict(initial, t_FFBAN=4.0, t_PS=0.0, CRED=1.0,
                   T_PSPLAN=8.0, delta_PSPLAN=0.9)
    blended = equations["Fu_PS"].func(partial, initial)
    assert initial["u_PS"] < blended < 1.6733

    # Heavier discounting weights the near horizon, where the ban still binds.
    impatient = equations["Fu_PS"].func(dict(partial, delta_PSPLAN=0.5), initial)
    assert impatient > blended


def test_the_ban_condition_direction_is_the_printed_one_and_is_flagged(initial):
    """The printed inequality in Eq. (88) points the other way from the prose.

    As printed, fossil capacity is removed when B >= L + t — i.e. when the
    ban date is at or *beyond* the planning horizon — while the prose above
    it says fossil is removed once the ban "comes into force". We implement
    the printed inequality, and the baseline switch is -inf rather than +inf
    precisely because of it: under the printed rule "no ban ever" has to be a
    date in the infinite past to leave fossil capacity in the denominator.

    Recorded here because it is the difference between a ban that stimulates
    green investment in advance and one that stimulates it forever after.
    """
    assert "ban_condition_direction" in power.MANUAL_GAPS
    assert power.POLICY_DEFAULTS["t_FFBAN"] == -math.inf


# --------------------------------------------------------------------------
# 7. Eq. (61)'s fuel price, and how far it reaches into this section
# --------------------------------------------------------------------------

def test_eq_61_fuel_price_gap_propagates_through_the_whole_price_block(initial):
    """§3.3.1's Eq. (61) computes P_FUEL = 0.6788 where Table 5 and 6 say 1.

    That gap does not touch any identity checked above, because every one of
    them takes IC_FUELPS as tabulated (it is determined in §3.3.3). It
    dominates any *simulation*, though, because P_FUEL prices the only
    variable input of the marginal plant:

      IC_FUELPS  15.75 -> 10.69   (-32%)
      MC_FF     0.5868 -> 0.3990  (-32%, diluted only by the carbon bill,
                                   which is 0.29% of the fossil cost base)
      MC_ELEC   0.4365 -> 0.2968  (-32%, Eq. (83) is linear in MC_FF)
      P_ELEC    0.9725 -> 0.6613  (-32%, and still 2.07x Table 6's 0.3198)
      COST_PSFF  27.80 -> 22.74   (-18%, diluted by tax and depreciation)

    So Eq. (61) and Eq. (84) push the electricity price in opposite
    directions and do not cancel: Eq. (84) is 3.04x high, Eq. (61) is 0.68x,
    and the product is still 2.07x the tabulated price.

    This test also adds a corroboration §3.3.1 could not reach: Table 6
    tabulates IC_FUELPS and IC_FUELPSR at *the same* 15.75, which is only
    possible at P_FUEL = 1. That is a third witness — beside Table 5's
    α_FUELPSLR note and Table 6's own P_FUEL entry — that the normalisation
    is right and α_PFUEL = 10.98 is the outlier.
    """
    computed_fuel_price = PARAMETERS["alpha_PFUEL"] * initial["P_GAS"]
    assert computed_fuel_price == pytest.approx(0.678784, rel=1e-4)
    assert initial["P_FUEL"] == 1.0

    # The third witness: nominal and real fuel input are the same number.
    assert initial["IC_FUELPS"] == initial["IC_FUELPSR"] == 15.75

    fuel_cost = initial["IC_FUELPSR"] * computed_fuel_price
    carbon = initial["COV_ETSPS"] * initial["P_ETS"] * initial["EMIS_ELEC"]
    mc_ff = (fuel_cost + carbon) / initial["E_ELECFF"]
    mc_elec = mc_ff * (1.0 - initial["beta_NFF"]) ** PARAMETERS["mu_MCELEC"]
    p_elec = (1.0 + PARAMETERS["MU_ELEC"]) * mc_elec

    assert mc_ff / initial["MC_FF"] - 1.0 == pytest.approx(-0.320, rel=1e-2)
    assert mc_elec == pytest.approx(0.29680, rel=1e-4)
    assert p_elec == pytest.approx(0.66127, rel=1e-4)
    # The two errors compound rather than cancel.
    assert p_elec / initial["P_ELEC"] == pytest.approx(2.068, rel=1e-3)

    # The carbon bill is a rounding error next to the fuel bill at the
    # baseline ETS price — which is why sce2 has to raise it so far.
    assert carbon / (fuel_cost + carbon) < 0.005


# --------------------------------------------------------------------------
# 8. The section solves as a system
# --------------------------------------------------------------------------

def test_section_solves_and_the_residuals_are_the_documented_ones(
    registry, initial
):
    """Held at its own initial values, §3.3.2 must reproduce the ones it can.

    The demand and dispatch block comes back at Table 6's precision. Nothing
    downstream of the electricity price does, and this test measures the
    damage rather than tolerating it, because two separate published defects
    compound here:

    - Eq. (84) puts the price 3.04x high, which triples nominal gross output
      and turns a loss-making sector (GOS_PS = -4.48) into a highly
      profitable one (+74.6);
    - the untabulated slopes of Eq. (138) leave credit rationing at
      logistic(α_0CRPS) = 0.939, and the untabulated intercept of Eq. (96)
      leaves desired investment negative, so gross capital formation comes
      out at -0.021 against a tabulated +2.15 and the real capital stock
      shrinks 1.24% in one quarter instead of the 0.4%/-1.4% split
      Eqs. (127)-(128) imply.

    Together those say §3.3.2 as published cannot be simulated forward from
    Table 6 without a source for the missing parameters. That is the finding;
    the numbers below are how big it is.
    """
    exogenous = {
        name: initial[name] for name in power.EXOGENOUS_TO_SECTION
    }
    solved = solve_period(registry, lag=initial, exogenous=exogenous)

    # Demand and dispatch: untouched by either defect.
    for name in ("F_PS", "F_PSR", "GO_PSR", "beta_NFF", "u_PS"):
        assert solved[name] == pytest.approx(initial[name], rel=SIG_FIG_TOL), (
            f"{name}: solved {solved[name]!r} vs Table 6 {initial[name]!r}"
        )

    # The price defect, propagated exactly once into nominal output.
    assert solved["P_ELEC"] / initial["P_ELEC"] == pytest.approx(3.042, rel=1e-3)
    assert solved["GO_PS"] / initial["GO_PS"] == pytest.approx(3.044, rel=1e-3)
    assert solved["GOS_PS"] > 0.0 > initial["GOS_PS"]

    # The missing-calibration defect, propagated into the capital stock.
    assert solved["CR_PS"] == pytest.approx(0.93912, rel=1e-4)
    assert solved["GCF_PSD"] == pytest.approx(-0.3409, rel=1e-3)
    assert solved["GCF_PS"] == pytest.approx(-0.02076, rel=1e-3)
    assert solved["K_PSFFR"] / initial["K_PSFFR"] - 1.0 == pytest.approx(
        -0.01240, rel=1e-3
    )
    assert solved["u_FF"] / initial["u_FF"] - 1.0 == pytest.approx(0.0124, rel=1e-2)

    # Accounting identities must hold *exactly* at the solved point — these
    # are definitions, not estimates.
    assert solved["GO_PS"] == pytest.approx(
        solved["GO_PSR"] * solved["P_ELEC"], rel=1e-12
    )
    assert solved["FA_PS"] == pytest.approx(
        solved["IBA_PS"] + solved["EQA_PS"], rel=1e-12
    )
    assert solved["FNW_PS"] == pytest.approx(
        solved["FA_PS"] - solved["FL_PS"] + solved["RES_PS"], rel=1e-12
    )
    assert solved["K_PSR"] == pytest.approx(
        solved["K_PSFFR"] + solved["K_PSNFFR"], rel=1e-12
    )
    assert solved["GCF_PS"] == pytest.approx(
        solved["GCF_PSFF"] + solved["GCF_PSNFF"], rel=1e-12
    )
    # Net lending is retained profit less investment, and the balance sheet
    # closes on it through Eq. (110) — the SFC constraint of this sector.
    assert solved["LEND_PS"] == pytest.approx(
        solved["RP_PS"] - solved["GCF_PS"], rel=1e-12
    )
    assert (solved["IBATR_PS"] + solved["EQATR_PS"] + solved["RESTR_PS"]) == (
        pytest.approx(solved["LEND_PS"] + solved["EQLTR_PS"] + solved["IBLTR_PS"],
                      rel=1e-9)
    )


def test_the_second_lag_key_is_declared_rather_than_approximated(registry, initial):
    """Eq. (96) reads K_PS at t-2; the solver exposes one lag.

    The caller carries it under power.SECOND_LAG_KEYS. Dividing by K_PS at
    t-1 instead would change the equation — a small error in a steady state
    and an arbitrary one out of it — so the key is required, and its absence
    is a loud KeyError rather than a silent substitution.
    """
    assert power.SECOND_LAG_KEYS == ("K_PS_LAG",)
    equations = {eq.name: eq for eq in registry}
    incomplete = {k: v for k, v in initial.items() if k not in power.SECOND_LAG_KEYS}
    with pytest.raises(KeyError, match="K_PS_LAG"):
        equations["GCF_PSD"].func(initial, incomplete)
