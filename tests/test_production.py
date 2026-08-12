"""§3.3.1 domestic production module, manual Eqs. (44)-(70).

Same two things as tests/test_macro.py, and the same standard:

1. **Transcription** — each equation computes what the manual prints, checked
   against the manual's own §5 Table 6 initial values, which is the only
   independent reference available before the oracle comparison.
2. **Closure** — quantities are demand-led, prices are cost-plus on *lagged*
   unit costs, and distribution runs share -> wage rate, not the other way
   round. Each of those is pinned, because each could be "fixed" into a
   different (and published-scenario-invalidating) model.

Nineteen of the section's twenty-seven equations reproduce Table 6 inside its
four-significant-figure printing noise. Five do not, by one to three orders of
magnitude more than that noise, and are pinned individually below with the
measured gap rather than absorbed into a tolerance. Two more, Eqs. (49) and
(55), reference a lagged variable and therefore cannot be checked against a
single-period snapshot at all — the tests say only what a snapshot can
support, which is that the implied one-period growth is the tabulated one.
"""

from __future__ import annotations

import math

import pytest

from define_uk.model.calibration import INITIAL_VALUES, PARAMETERS
from define_uk.model.registry import Registry
from define_uk.model.sectors import production
from define_uk.model.solver import solve_period

# Four-significant-figure printing in Table 6, as in tests/test_macro.py.
SIG_FIG_TOL = 1e-3


@pytest.fixture(scope="module")
def registry() -> Registry:
    r = Registry()
    production.register(r)
    return r


@pytest.fixture(scope="module")
def equations(registry) -> dict:
    return {eq.name: eq for eq in registry}


@pytest.fixture(scope="module")
def initial() -> dict[str, float]:
    """Table 6 initial values, plus the two real green capital stocks it omits.

    Eq. (68) sums K_NFCGR and K_GVTGR; Table 6 tabulates neither, only their
    sum K_PGR = 131.4 (see production.MANUAL_GAPS). Rather than invent them,
    each is reconstructed by deflating the tabulated *nominal* green stock
    with its own sector's real/nominal capital ratio — the only assumption
    being that a sector's green and conventional capital carry the same
    deflator, which is what Table 6's own K_NFCR/K_NFC and K_GVTR/K_GVT pairs
    imply. The reconstruction is not free: it has to reproduce the tabulated
    K_PGR, and test_eq_68_reconstruction_reproduces_the_tabulated_aggregate
    checks that it does (to 2.8e-4).
    """
    values = dict(INITIAL_VALUES)
    values["K_NFCGR"] = (
        INITIAL_VALUES["K_NFCG"] * INITIAL_VALUES["K_NFCR"] / INITIAL_VALUES["K_NFC"]
    )
    values["K_GVTGR"] = (
        INITIAL_VALUES["K_GVTG"] * INITIAL_VALUES["K_GVTR"] / INITIAL_VALUES["K_GVT"]
    )
    return values


# --------------------------------------------------------------------------
# 1. Registration and provenance
# --------------------------------------------------------------------------

def test_registers_every_equation_from_44_to_70(registry):
    """§3.3.1 is Eqs. (44)-(70) inclusive — 27 equations, none missing.

    (71) is the first equation of §3.3.2, the power generation sector, which
    is a separate pass; nothing from it may leak in here.
    """
    refs = {int(eq.manual_ref.split("(")[1].rstrip(")")) for eq in registry}
    assert refs == set(range(44, 71)), sorted(set(range(44, 71)) - refs)
    assert len(registry) == 27


def test_every_equation_cites_section_3_3_1(registry):
    for eq in registry:
        assert eq.manual_ref.startswith("§3.3.1 eq. ("), eq.manual_ref


def test_no_equation_determines_a_variable_this_section_treats_as_exogenous(registry):
    overlap = set(registry.names()) & set(production.EXOGENOUS_TO_SECTION)
    assert not overlap, sorted(overlap)


def test_section_supplies_the_three_variables_macro_takes_as_given(registry):
    """§3.2 lists P_P, GO_P and K_PR as exogenous; §3.3.1 is where they come from.

    If any of the three were dropped here the two sections would never close,
    and the failure would surface far downstream as a missing key.
    """
    from define_uk.model.sectors import macro

    supplied = set(registry.names()) & set(macro.EXOGENOUS_TO_SECTION)
    assert supplied == {"P_P", "GO_P", "K_PR"}


# --------------------------------------------------------------------------
# 2. Transcription: the manual's own initial values satisfy each equation
# --------------------------------------------------------------------------

# Every entry holds at Table 6's printing precision. The five that do not are
# excluded and pinned individually in section 3 below; the two lag-dependent
# equations are handled in section 4.
IDENTITIES = [
    "F_P", "F_PR", "GO_PR", "GO_P", "COST_P", "UC",
    "WR", "WR_PRI", "W_PRI", "W_PUB", "W",
    "P_NELECT", "COST_NELEC", "COST_ER",
    "K_P", "K_PG", "K_PC", "K_PR", "K_PCR",
]


@pytest.mark.parametrize("name", IDENTITIES)
def test_identity_holds_at_manual_initial_values(equations, initial, name):
    """Worst residual here is Eq. (46), GO_PR, at 8.1e-4 — still rounding.

    That one deserves its arithmetic spelled out, because it is the only
    entry close to the tolerance: L_PP prints as 1.417, so it carries
    ±0.0005 × 777.8 = ±0.39 on its own, and GO_PR prints as 1113.0, worth a
    further ±0.5. A residual up to ~0.9 (8e-4 relative) is therefore exactly
    what four-significant-figure printing predicts, not a defect.
    """
    equation = equations[name]
    computed = equation.func(initial, initial)
    tabulated = initial[name]
    assert computed == pytest.approx(tabulated, rel=SIG_FIG_TOL), (
        f"{equation.manual_ref} computes {computed!r} but Table 6 tabulates "
        f"{tabulated!r} (relative error "
        f"{abs(computed - tabulated) / abs(tabulated):.2e})"
    )


def test_eq_68_reconstruction_reproduces_the_tabulated_aggregate(equations, initial):
    """Eq. (68) K_PGR = K_NFCGR + K_GVTGR, with both components untabulated.

    Table 6 gives only the sum. Deflating each sector's nominal green stock
    by that sector's own real/nominal ratio reproduces K_PGR = 131.4 to
    2.8e-4 — inside the printing noise — which is what makes the fixture's
    reconstruction evidence rather than assumption. It is also corroborated
    from the other side: the tabulated K_PR - K_PCR = 131.0, consistent with
    K_PGR to within the ±1.0 that two four-significant-figure numbers near
    3200 carry into their difference.
    """
    computed = equations["K_PGR"].func(initial, initial)
    assert computed == pytest.approx(INITIAL_VALUES["K_PGR"], rel=SIG_FIG_TOL)

    implied = INITIAL_VALUES["K_PR"] - INITIAL_VALUES["K_PCR"]
    assert abs(implied - INITIAL_VALUES["K_PGR"]) <= 1.0


def test_green_and_conventional_capital_partition_the_total(initial):
    """Eqs. (64)-(69) must partition, not merely aggregate.

    K_PG + K_PC = K_P and K_PGR + K_PCR = K_PR: there is no third category of
    productive capital. If a later section adds one, the emissions block's
    green share silently stops meaning what §3.3.1 says it means.
    """
    assert (initial["K_PG"] + initial["K_PC"]) == pytest.approx(
        initial["K_P"], rel=SIG_FIG_TOL
    )
    assert (initial["K_PGR"] + initial["K_PCR"]) == pytest.approx(
        initial["K_PR"], rel=SIG_FIG_TOL
    )


# --------------------------------------------------------------------------
# 3. Documented manual inconsistencies — implemented as printed, pinned here
# --------------------------------------------------------------------------

def test_eq_51_markup_is_inconsistent_with_the_tabulated_value(equations, initial):
    """DOCUMENTED MANUAL INCONSISTENCY — Eq. (51) MU = α_MU·u.

    Table 5 gives α_1MU = 0.1943 ("Calibrated so LR markup at initial
    utilisation equals mean of 45:88 and 109:132") and Table 6 gives
    u = 0.815, so Eq. (51) yields 0.1584. Table 6 tabulates µ = 0.1704 —
    a 7.1% gap, ~70x the section's rounding noise. The implied α_MU would be
    0.2091.

    The equation, not the tabulated µ, is the one corroborated: Eqs. (49) and
    (50) together imply a mark-up of P_P/UC - 1 = 0.1598 at the tabulated
    P_P and UC, which is 0.9% from Eq. (51)'s answer and 6.7% from Table 6's.
    So we implement Eq. (51) as printed and treat Table 6's µ as the outlier.
    """
    computed = equations["mu"].func(initial, initial)
    assert computed == pytest.approx(0.158355, rel=1e-4)
    assert initial["mu"] == 0.1704

    relative_gap = abs(computed - initial["mu"]) / initial["mu"]
    assert relative_gap == pytest.approx(7.1e-2, rel=0.05)
    assert relative_gap > 10 * SIG_FIG_TOL

    # The corroboration: Eqs. (49)+(50) imply 0.1598, near Eq. (51), far from µ.
    implied_by_prices = initial["P_P"] / initial["UC"] - 1.0
    assert implied_by_prices == pytest.approx(0.15979, rel=1e-4)
    assert abs(implied_by_prices - computed) < abs(implied_by_prices - initial["mu"])


def test_eq_52_wage_share_is_inconsistent_with_the_tabulated_value(equations, initial):
    """DOCUMENTED MANUAL INCONSISTENCY — Eq. (52), the wage-share logistic.

    At α_0WS = 0.4697, α_1WS = 1.759 and ru = 0.03725 the logistic gives
    0.5997, against a tabulated WS = 0.6233 — a 3.8% gap, ~40x the rounding
    noise. The tabulated value is the solid one: it is exactly W/GDP =
    364.3/584.5 on two independently tabulated data ("Free") figures.

    This is a contradiction inside the manual, not an imprecision: Table 5
    documents α_0WS as "Calibrated so [the wage share] equation equals
    observed [wage share] at t=L", which is the very property that fails
    here. The α_0WS that would reproduce Table 6 is 0.5691.

    Implemented as printed and pinned. If a revision fixes it, this fails.
    """
    computed = equations["WS"].func(initial, initial)
    assert computed == pytest.approx(0.599691, rel=1e-4)

    # The tabulated wage share is exactly the wage bill over GDP.
    assert initial["WS"] == pytest.approx(
        initial["W"] / initial["GDP"], rel=SIG_FIG_TOL
    )

    relative_gap = abs(computed - initial["WS"]) / initial["WS"]
    assert relative_gap == pytest.approx(3.8e-2, rel=0.05)
    assert relative_gap > 10 * SIG_FIG_TOL

    # The intercept that would close the gap, recorded so it is not re-derived.
    implied_a0 = math.log(initial["WS"] / (1 - initial["WS"])) + (
        PARAMETERS["alpha1_WS"] * initial["ru"]
    )
    assert implied_a0 == pytest.approx(0.5691, rel=1e-3)
    assert PARAMETERS["alpha0_WS"] == 0.4697


def test_eq_59_direct_energy_price_is_inconsistent_with_the_tabulated_value(
    equations, initial
):
    """DOCUMENTED MANUAL INCONSISTENCY — Eq. (59), the largest in the section.

    α_NELEC = 2.557 ("Pass through from gas and oil prices to overall
    non-electric energy costs") applied to the tabulated wholesale gas and
    oil prices gives 0.1491, against a tabulated P_NELEC of 0.09337 — 60%
    high. The implied pass-through is 1.601.

    Table 6 marks P_NELEC as data ("Free": DUKES table 1.1.6 costs divided by
    non-electric energy use) and it is corroborated downstream — Eqs. (60),
    (62) and (63) all reproduce their tabulated values from it to ~1e-4. So
    the initial period and the equation disagree by 60%, and a model started
    from Table 6 takes that jump in its first step. That is a question for
    the DEFINE authors, not something to paper over here.
    """
    computed = equations["P_NELEC"].func(initial, initial)
    assert computed == pytest.approx(0.149122, rel=1e-4)
    assert initial["P_NELEC"] == 0.09337

    ratio = computed / initial["P_NELEC"]
    assert ratio == pytest.approx(1.597, rel=1e-3)

    mix = (PARAMETERS["beta_NELECGAS"] * initial["P_GAS"]
           + PARAMETERS["beta_NELECOIL"] * initial["P_OIL"])
    assert initial["P_NELEC"] / mix == pytest.approx(1.601, rel=1e-3)
    # The fuel mix shares are a partition, which is not itself in doubt.
    assert PARAMETERS["beta_NELECGAS"] + PARAMETERS["beta_NELECOIL"] == 1.0


def test_eq_61_fuel_price_contradicts_the_manuals_own_normalisation(
    equations, initial
):
    """DOCUMENTED MANUAL INCONSISTENCY — Eq. (61) P_FUEL = α_PFUEL·P_GAS.

    Table 5 says of α_FUELPSLR that "at the initial condition fuel price is
    normalised to equal 1", and Table 6 duly tabulates P_FUEL = 1 as
    model-constrained. But α_PFUEL = 10.98 against P_GAS = 0.06182 gives
    0.6788 — 32% below the normalisation the manual states. The α_PFUEL
    consistent with it is 16.18.

    The consequence is not cosmetic: P_FUEL prices the production module's
    fuel sales to the power sector, so §3.3.2's fossil generation costs
    inherit this gap directly. Pinned so §3.3.2 can be written knowing it.
    """
    computed = equations["P_FUEL"].func(initial, initial)
    assert computed == pytest.approx(0.678784, rel=1e-4)
    assert initial["P_FUEL"] == 1.0

    relative_gap = abs(computed - initial["P_FUEL"]) / initial["P_FUEL"]
    assert relative_gap == pytest.approx(3.2e-1, rel=0.05)
    assert initial["P_FUEL"] / initial["P_GAS"] == pytest.approx(16.18, rel=1e-3)


def test_eq_70_depreciation_rate_differs_between_table_5_and_table_6(
    equations, initial
):
    """DOCUMENTED MANUAL INCONSISTENCY — Eq. (70) δ_KP = δ_kpc.

    Eq. (70) equates the two, but the manual tabulates them separately and
    they differ by 10.5%: Table 5's δ_kpc = 0.02375 ("Calculated from implied
    rates based on capital stock data") against Table 6's δ_KP = 0.02149
    ("Calculated from the ONS capital stock tables 2023"). Both are marked
    "Free", so neither is derived from the other — the manual simply carries
    two data estimates of one constant.

    We follow the equation and use Table 5's parameter, because Eq. (70) is
    what the model runs with from t=1 onward; the tabulated initial value
    then applies for exactly one period. Capital stocks compound, so a 10.5%
    error in the depreciation rate is not a rounding matter over a 30-year
    simulation.
    """
    computed = equations["delta_KP"].func(initial, initial)
    assert computed == PARAMETERS["delta_kpc"] == 0.02375
    assert initial["delta_KP"] == 0.02149

    relative_gap = abs(computed - initial["delta_KP"]) / initial["delta_KP"]
    assert relative_gap == pytest.approx(1.05e-1, rel=0.05)


# --------------------------------------------------------------------------
# 4. The two lagged equations, which a snapshot cannot check
# --------------------------------------------------------------------------

def test_eq_55_public_wage_rate_lag_implies_the_tabulated_growth_rate(
    equations, initial
):
    """Eq. (55) WR_PUB = β_WRPUB·WR_{t-1} — not checkable at one snapshot.

    Treating the snapshot as a steady state gives 0.973 × 11.1 = 10.80
    against a tabulated 10.6, and it would be wrong to call that a 1.9%
    inconsistency: the equation reads the *lagged* wage rate. What a snapshot
    can establish is the growth rate it implies, and that is the check here —
    WR_{t-1} = 10.6/0.973 = 10.894, so WR_t/WR_{t-1} = 1.0189, against the
    tabulated nominal growth rate g = 1.019. Agreement to three significant
    figures on a value that was never fitted to it is strong evidence that
    Table 6 is the snapshot of a growing economy rather than of a stationary
    one, which is exactly why Eqs. (49) and (55) must not be pinned the way
    Eqs. (51), (52), (59), (61) and (70) are.
    """
    implied_lagged_wr = initial["WR_PUB"] / PARAMETERS["beta_WRPUB"]
    implied_growth = initial["WR"] / implied_lagged_wr
    assert implied_growth == pytest.approx(initial["g"], rel=1e-3)

    # And the equation itself does read the lag, not the current value.
    grown = dict(initial, WR=initial["WR"] * 2.0)
    assert equations["WR_PUB"].func(grown, initial) == pytest.approx(
        PARAMETERS["beta_WRPUB"] * initial["WR"], rel=1e-12
    )


def test_eq_49_price_uses_lagged_unit_costs(equations, initial):
    """Eq. (49) P_P = (1 + MU_t)·UC_{t-1} — also lagged, also unpinnable.

    On the steady-snapshot reading it gives 1.0445 with Table 6's µ (0.92%
    off the tabulated P_P) or 1.0337 with Eq. (51)'s µ (0.12% off). Neither
    number is evidence of a defect on its own; what matters structurally is
    that the price does *not* respond to this period's costs, which is what
    breaks the price/cost simultaneity and fixes the solve order.
    """
    with_tabulated_mu = equations["P_P"].func(initial, initial)
    assert with_tabulated_mu == pytest.approx(1.04446, rel=1e-4)

    with_eq_51_mu = equations["P_P"].func(
        dict(initial, mu=PARAMETERS["alpha1_MU"] * initial["u"]), initial
    )
    assert with_eq_51_mu == pytest.approx(1.03372, rel=1e-4)
    assert abs(with_eq_51_mu - initial["P_P"]) < abs(
        with_tabulated_mu - initial["P_P"]
    )

    # Current-period unit costs are ignored, however large they get.
    shocked = dict(initial, UC=initial["UC"] * 5.0)
    assert equations["P_P"].func(shocked, initial) == pytest.approx(
        with_tabulated_mu, rel=1e-12
    )


# --------------------------------------------------------------------------
# 5. Behaviour of the pricing and distribution blocks
# --------------------------------------------------------------------------

def test_markup_is_procyclical_in_utilisation(equations, initial):
    """Eq. (51): margins widen in a boom and are cut in a slump.

    This is the manual's deliberate departure from EUROGREEN (§3.3.1, p. 17)
    and it gives the model a stabilising price channel, so the sign is not a
    detail — flipping it would change every scenario's inflation path.
    """
    mu = equations["mu"]
    hot = mu.func(dict(initial, u=initial["u"] * 1.1), initial)
    cold = mu.func(dict(initial, u=initial["u"] * 0.9), initial)
    assert cold < mu.func(initial, initial) < hot
    assert hot == pytest.approx(
        PARAMETERS["alpha1_MU"] * initial["u"] * 1.1, rel=1e-12
    )


def test_markup_floor_is_the_manuals_and_does_not_bind_in_the_baseline(
    equations, initial
):
    """§5 Table 6 records µ as "floored at 0.001 for log stability".

    The floor is the manual's, so it is implemented; but it must be inert at
    any plausible utilisation, otherwise it would be silently altering the
    pricing rule rather than protecting it.
    """
    mu = equations["mu"]
    assert mu.func(dict(initial, u=0.0), initial) == production.MU_FLOOR
    assert mu.func(dict(initial, u=-1.0), initial) == production.MU_FLOOR
    # Inert wherever utilisation is even remotely realistic.
    for u in (0.1, 0.5, initial["u"], 1.0, 1.5):
        assert mu.func(dict(initial, u=u), initial) > production.MU_FLOOR


def test_wage_share_falls_with_unemployment_and_stays_a_share(equations, initial):
    """Eq. (52): the reserve-army effect, bounded in (0, 1) by construction."""
    ws = equations["WS"]
    slack = ws.func(dict(initial, ru=0.15), initial)
    tight = ws.func(dict(initial, ru=0.01), initial)
    assert slack < ws.func(initial, initial) < tight

    # Bounded even at absurd unemployment rates — the point of the logistic.
    for ru in (-1.0, 0.0, 0.5, 1.0, 1e6, -1e6):
        share = ws.func(dict(initial, ru=ru), initial)
        assert 0.0 <= share <= 1.0

    # And no OverflowError where the naive 1/(1+exp(-x)) form would raise.
    assert ws.func(dict(initial, ru=1e9), initial) == pytest.approx(0.0)


def test_wage_rate_follows_the_share_rather_than_setting_it(equations, initial):
    """Eq. (53): distribution is decided first, the wage rate is its residual.

    Post-Keynesian causality — the wage rate is WS·GDP/EMP, so a demand
    expansion at an unchanged share raises the wage rate one-for-one. If
    someone later rewrites this as a labour-market clearing price, the wage
    share stops being determined by Eq. (52) and the model changes character.
    """
    wr = equations["WR"]
    assert wr.func(dict(initial, GDP=initial["GDP"] * 1.05), initial) == (
        pytest.approx(initial["WR"] * 1.05, rel=1e-3)
    )
    assert wr.func(dict(initial, WS=initial["WS"] * 1.05), initial) == (
        pytest.approx(initial["WR"] * 1.05, rel=1e-3)
    )


def test_unit_costs_refuse_zero_output_instead_of_returning_inf(equations, initial):
    """An inf from Eq. (50) would propagate into P_P and every nominal total."""
    with pytest.raises(ValueError, match=r"Eq\. \(50\)"):
        equations["UC"].func(dict(initial, GO_PR=0.0), initial)


def test_imports_and_indirect_tax_are_costs_that_reach_the_price_level(
    equations, initial
):
    """Eq. (48) -> (50) -> (49): the cost-push channel, explicitly.

    Imports enter the production module's cost base, so an import price shock
    raises domestic prices with a one-period lag rather than only crowding
    out demand. Pinned because dropping IMP from Eq. (48) would still leave
    every §3.3.1 identity looking plausible.
    """
    cost = equations["COST_P"].func(initial, initial)
    dearer = equations["COST_P"].func(
        dict(initial, IMP=initial["IMP"] + 10.0), initial
    )
    assert dearer - cost == pytest.approx(10.0, rel=1e-12)

    taxed = equations["COST_P"].func(
        dict(initial, ITAX_P=initial["ITAX_P"] + 10.0), initial
    )
    assert taxed - cost == pytest.approx(10.0, rel=1e-12)


# --------------------------------------------------------------------------
# 6. Closure: output is demand-led
# --------------------------------------------------------------------------

def test_gross_output_accommodates_demand_without_any_capacity_term(
    equations, initial
):
    """Eq. (46) is the Leontief inverse and nothing else.

    Real gross output is linear and homogeneous in final demand: doubling it
    doubles output, with no capacity ceiling and no price response. Together
    with §3.2's untruncated GDP_R this is the model's demand-led closure, so
    it is asserted rather than left to inspection.
    """
    go_pr = equations["GO_PR"]
    base = go_pr.func(initial, initial)
    doubled = go_pr.func(
        dict(initial, F_PR=initial["F_PR"] * 2.0, F_PSR=initial["F_PSR"] * 2.0),
        initial,
    )
    assert doubled == pytest.approx(2.0 * base, rel=1e-12)

    # Electricity demand pulls production output too — the IO link that
    # separating the power sector is there to capture.
    assert go_pr.func(dict(initial, F_PSR=initial["F_PSR"] + 1.0), initial) == (
        pytest.approx(base + initial["L_PPS"], rel=1e-9)
    )


# --------------------------------------------------------------------------
# 7. The section solves as a system
# --------------------------------------------------------------------------

def test_section_solves_and_the_residual_is_the_documented_wage_share_gap(
    registry, initial
):
    """Held at its own initial values, §3.3.1 must reproduce the ones it can.

    The demand and output block is exact to Table 6's precision. The wage and
    price block is not, and the reason is entirely accounted for: Eq. (52)
    starts the chain 3.8% low, which carries into the wage bill and from
    there into unit costs. The test asserts the size of that propagation
    rather than widening a tolerance to hide it — if the wage-share gap is
    ever fixed, these numbers move and this test says so.
    """
    exogenous = {name: initial[name] for name in production.EXOGENOUS_TO_SECTION}
    solved = solve_period(registry, lag=initial, exogenous=exogenous)

    # Quantities: demand-led and unaffected by the price-block inconsistencies.
    for name in ("F_P", "F_PR", "GO_PR", "GO_P", "K_P", "K_PR", "K_PG", "K_PC"):
        assert solved[name] == pytest.approx(initial[name], rel=SIG_FIG_TOL), (
            f"{name}: solved {solved[name]!r} vs Table 6 {initial[name]!r}"
        )

    # The wage bill inherits Eq. (52)'s 3.8% gap, damped to 2.8% because
    # public wages, Eq. (55), are set on the lagged (tabulated) wage rate and
    # so escape it.
    wage_gap = solved["W"] / initial["W"] - 1.0
    assert wage_gap == pytest.approx(-2.80e-2, rel=0.05)
    # Which passes into unit costs diluted by the non-wage cost base.
    assert solved["UC"] / initial["UC"] - 1.0 == pytest.approx(-1.13e-2, rel=0.05)

    # Accounting identities must hold *exactly* at the solved point — these
    # are definitions, not estimates.
    assert solved["W"] == pytest.approx(
        solved["W_PRI"] + solved["W_PUB"], rel=1e-12
    )
    assert solved["GO_P"] == pytest.approx(
        solved["GO_PR"] * solved["P_P"], rel=1e-12
    )
    assert solved["UC"] == pytest.approx(
        solved["COST_P"] / solved["GO_PR"], rel=1e-12
    )
    # The capital partition is the one identity that cannot be exact here:
    # Eqs. (64)-(66) sum four *separately rounded* Table 6 inputs, so
    # K_NFCG + K_NFCC recovers K_NFC exactly while K_GVTG + K_GVTC misses
    # K_GVT by 0.03. That is the printing, not the model.
    assert solved["K_P"] == pytest.approx(
        solved["K_PG"] + solved["K_PC"], rel=SIG_FIG_TOL
    )


# --------------------------------------------------------------------------
# 8. The manual gaps stay visible
# --------------------------------------------------------------------------

def test_direct_energy_symbols_are_recorded_as_a_manual_gap():
    """The body's D subscript and the tables' NELEC family are the same thing.

    Recorded because the identification is inference, not transcription: no
    D-subscripted symbol appears in Tables 5-6 and no NELEC symbol appears in
    the §3 body. The evidence is that Eqs. (60) and (62) hold to ~1e-5 under
    it, which the IDENTITIES parametrisation above checks.
    """
    assert "direct_energy_symbols" in production.MANUAL_GAPS
    for tabulated in ("P_NELEC", "P_NELECT", "COST_NELEC", "E_NELEC",
                      "ITAX_NELEC"):
        assert tabulated in INITIAL_VALUES
    # If the D-family is ever tabulated, the identification is settled and
    # this note should go with it.
    for body_name in ("P_D", "P_DT", "COST_D", "E_D", "ITAX_D"):
        assert body_name not in INITIAL_VALUES, (
            f"{body_name} is now tabulated — drop the NELEC identification "
            "note from production.MANUAL_GAPS"
        )


def test_missing_real_green_capital_components_are_recorded_as_a_manual_gap():
    """Eq. (68)'s two components are absent from Table 6; that must not go quiet."""
    assert "K_NFCGR_K_GVTGR" in production.MANUAL_GAPS
    for name in ("K_NFCGR", "K_GVTGR"):
        assert name not in INITIAL_VALUES, (
            f"{name} is now tabulated — drop the reconstruction in the "
            "`initial` fixture and its MANUAL_GAPS entry"
        )
    # The sum they must reproduce is tabulated, and is what pins them.
    assert INITIAL_VALUES["K_PGR"] == 131.4
