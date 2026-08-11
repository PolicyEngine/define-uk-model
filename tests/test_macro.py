"""§3.2 high-level macroeconomic variables, manual Eqs. (21)-(43).

Two things are being tested, and they are different in kind:

1. **Transcription** — each equation computes what the manual prints. The
   check is that the manual's own §5 Table 6 initial values satisfy it,
   which is the only independent reference available before the oracle
   comparison in milestone 2.
2. **Closure** — the section is demand-determined. Eq. (38) computes a
   supply ceiling that is deliberately *not* imposed on GDP_R; a test pins
   that, because "fixing" it would quietly turn DEFINE into a
   supply-determined model and every scenario result would change.

Tolerances are evidence-based, not guessed. Table 6 prints to four
significant figures, so an identity built from several tabulated values
inherits roughly 1e-3 of rounding noise; the tolerance below is the
measured residual, and anything materially larger is treated as a manual
inconsistency and pinned explicitly rather than absorbed.
"""

from __future__ import annotations

import math

import pytest

from define_uk.model.calibration import INITIAL_VALUES, PARAMETERS
from define_uk.model.registry import Registry
from define_uk.model.sectors import macro
from define_uk.model.solver import solve_period

# Four-significant-figure printing in Table 6. Identities combining several
# tabulated values sit comfortably inside this; see the module docstring.
SIG_FIG_TOL = 1e-3


@pytest.fixture(scope="module")
def registry() -> Registry:
    r = Registry()
    macro.register(r)
    return r


@pytest.fixture(scope="module")
def initial() -> dict[str, float]:
    """Table 6 initial values, plus the two §3.2 inputs Table 6 leaves implicit.

    GCF_PS is not tabulated on its own: the power sector's fossil and
    non-fossil capital formation are (GCF_PSFF, GCF_PSNFF), and their sum
    reproduces Eq. (23) against the tabulated GCF, which is what pins the
    reading. g_LFOBR and POP_OBR are exogenous OBR projections supplied per
    period; held flat here so the section can be solved in isolation.
    """
    values = dict(INITIAL_VALUES)
    values["GCF_PS"] = INITIAL_VALUES["GCF_PSFF"] + INITIAL_VALUES["GCF_PSNFF"]
    values["g_LFOBR"] = 1.0
    values["POP_OBR"] = INITIAL_VALUES["POP"]
    return values


# --------------------------------------------------------------------------
# 1. Registration and provenance
# --------------------------------------------------------------------------

def test_registers_every_equation_from_21_to_43(registry):
    """§3.2 is Eqs. (21)-(43) inclusive — 23 equations, none missing."""
    refs = {int(eq.manual_ref.split("(")[1].rstrip(")")) for eq in registry}
    assert refs == set(range(21, 44)), sorted(set(range(21, 44)) - refs)
    assert len(registry) == 23


def test_every_equation_cites_section_3_2(registry):
    for eq in registry:
        assert eq.manual_ref.startswith("§3.2 eq. ("), eq.manual_ref


def test_no_equation_determines_a_variable_this_section_treats_as_exogenous(registry):
    """A variable cannot be both an input from another section and set here.

    If §3.2 ever starts determining, say, EXP_R, the RoW section's equation
    for it becomes dead code and the duplicate would only surface as a
    registry collision much later.
    """
    overlap = set(registry.names()) & set(macro.EXOGENOUS_TO_SECTION)
    assert not overlap, sorted(overlap)


# --------------------------------------------------------------------------
# 2. Transcription: the manual's own initial values satisfy each equation
# --------------------------------------------------------------------------

# (name, tolerance). Every entry here holds at Table 6's printing precision.
# Eq. (27) is excluded and pinned separately below — it does not hold.
IDENTITIES = [
    "GDP", "CONS", "GCF", "GO", "GDP_R", "CONS_R", "GO_R", "P",
    "EMP", "EMP_PRI", "GDP_RFE", "GDP_RFK", "GDP_RMAX", "re", "u",
]


@pytest.mark.parametrize("name", IDENTITIES)
def test_identity_holds_at_manual_initial_values(registry, initial, name):
    equation = {eq.name: eq for eq in registry}[name]
    computed = equation.func(initial, initial)
    tabulated = initial[name]
    assert computed == pytest.approx(tabulated, rel=SIG_FIG_TOL), (
        f"{equation.manual_ref} computes {computed!r} but Table 6 tabulates "
        f"{tabulated!r} (relative error "
        f"{abs(computed - tabulated) / abs(tabulated):.2e})"
    )


def test_unemployment_rate_holds_on_an_absolute_scale(registry, initial):
    """Eq. (42) ru = 1 - re, checked absolutely rather than relatively.

    ru is a small residual of a near-one number, so it inherits re's
    *absolute* rounding error while having ~26x less magnitude to carry it:
    re is tabulated as 0.9627 (absolute precision 5e-5), which lands ru at
    0.03730 against a tabulated 0.03725 — 1.3e-3 in relative terms, purely
    from four-significant-figure printing.

    This is precision, not inconsistency, and the distinction matters: the
    correct check is that the discrepancy is bounded by half a unit in re's
    last printed digit. Compare Eq. (27) below, where the gap survives that
    test by an order of magnitude and is a genuine manual defect.
    """
    equation = {eq.name: eq for eq in registry}["ru"]
    computed = equation.func(initial, initial)

    # re prints as 0.9627, so the true value lies in [0.96265, 0.96275] and
    # 1 - re must lie in [0.03725, 0.03735]. The tabulated ru sits exactly at
    # that interval's lower edge, which is consistent, not contradictory.
    low, high = 1.0 - 0.96275, 1.0 - 0.96265
    assert low - 1e-12 <= computed <= high + 1e-12, (
        f"Eq. (42) computes {computed!r}, outside [{low!r}, {high!r}] implied "
        f"by re printing as {initial['re']!r}"
    )
    assert low - 1e-12 <= initial["ru"] <= high + 1e-12

    # Exactly complementary to the tabulated employment rate, by definition.
    assert computed + initial["re"] == pytest.approx(1.0, rel=1e-12)


def test_eq_27_real_gcf_is_inconsistent_in_the_manual(registry, initial):
    """DOCUMENTED MANUAL INCONSISTENCY — Eq. (27) does not hold in Table 6.

    Eq. (27) states GCF_R = GCF / P_P. At the tabulated values that gives
    115.8 / 1.035 = 111.88, but Table 6 tabulates GCF_R = 112.3 — a 0.37%
    gap, an order of magnitude beyond the ~3e-4 rounding noise every other
    identity in this section shows. The implied deflator is 1.0312 against a
    tabulated P_P of 1.035, whereas consumption and gross output imply
    1.0349 and 1.0357, both consistent with P_P.

    Note the manual is inconsistent with *itself*, not merely imprecise:
    Eq. (25) only reproduces the tabulated GDP_R when GCF_R = 112.3 is used,
    so the two equations disagree about the same variable.

    We implement Eq. (27) exactly as printed and pin the discrepancy here.
    If a later manual revision fixes it, this test fails and tells us why,
    which is the point — silently absorbing it into a tolerance would hide a
    real question for the DEFINE authors.
    """
    equation = {eq.name: eq for eq in registry}["GCF_R"]
    computed = equation.func(initial, initial)

    assert computed == pytest.approx(111.884, rel=1e-4)
    assert initial["GCF_R"] == 112.3
    relative_gap = abs(computed - initial["GCF_R"]) / initial["GCF_R"]
    assert relative_gap == pytest.approx(3.7e-3, rel=0.05)
    # Definitively beyond four-significant-figure rounding.
    assert relative_gap > 3 * SIG_FIG_TOL


# --------------------------------------------------------------------------
# 3. Productivity, Eqs. (31)-(32)
# --------------------------------------------------------------------------

def test_productivity_is_unchanged_when_neither_driver_grows(registry, initial):
    """Kaldor-Verdoorn with no demand growth and no investment growth.

    With the (untabulated) intercept at zero this must leave λ exactly at
    its lagged value — the property that makes α_0λ = 0 the neutral choice.
    """
    lam = {eq.name: eq for eq in registry}["lam"]
    assert lam.func(initial, initial) == pytest.approx(initial["lam"], rel=1e-12)


def test_productivity_responds_to_demand_and_to_productive_investment(registry, initial):
    """Both channels raise λ, and each with the tabulated elasticity."""
    lam = {eq.name: eq for eq in registry}["lam"]

    demand = dict(initial, GDP_R=initial["GDP_R"] * 1.01)
    grown = lam.func(demand, initial)
    assert grown > initial["lam"]
    # Δln λ = α_1λ · Δln GDP_R exactly, when investment is flat.
    assert math.log(grown / initial["lam"]) == pytest.approx(
        PARAMETERS["alpha1_lambda"] * math.log(1.01), rel=1e-9
    )

    # Productive investment only — housing is netted out, so raising
    # GCF_HHR alongside GCF_R by the same amount must change nothing.
    investment = dict(initial, GCF_R=initial["GCF_R"] * 1.01)
    assert lam.func(investment, initial) > initial["lam"]

    housing_only = dict(
        initial,
        GCF_R=initial["GCF_R"] + 5.0,
        GCF_HHR=initial["GCF_HHR"] + 5.0,
    )
    assert lam.func(housing_only, initial) == pytest.approx(
        initial["lam"], rel=1e-12
    )


def test_productivity_refuses_undefined_logs_instead_of_returning_nan(registry, initial):
    """A nan here would propagate through EMP into the whole supply block."""
    lam = {eq.name: eq for eq in registry}["lam"]
    broken = dict(initial, GCF_R=initial["GCF_HHR"])  # productive GCF = 0
    with pytest.raises(ValueError, match=r"Eq\. \(31\)"):
        lam.func(broken, initial)


def test_capital_productivity_is_constant(registry, initial):
    """Eq. (32) Δν = 0 — the capital ceiling moves only through investment."""
    nu = {eq.name: eq for eq in registry}["nu"]
    assert nu.func(dict(initial, nu=999.0), initial) == initial["nu"]


# --------------------------------------------------------------------------
# 4. Employment and the labour force
# --------------------------------------------------------------------------

def test_public_employment_tracks_labour_force_growth(registry, initial):
    """Eq. (34): a constant share of the labour force, so it grows with it."""
    emp_pub = {eq.name: eq for eq in registry}["EMP_PUB"]
    grown = dict(initial, LF=initial["LF"] * 1.02)
    assert emp_pub.func(grown, initial) == pytest.approx(
        initial["EMP_PUB"] * 1.02, rel=1e-12
    )


def test_labour_force_follows_the_obr_projection(registry, initial):
    lf = {eq.name: eq for eq in registry}["LF"]
    assert lf.func(dict(initial, g_LFOBR=1.005), initial) == pytest.approx(
        initial["LF"] * 1.005, rel=1e-12
    )


# --------------------------------------------------------------------------
# 5. Closure: the supply ceiling is reported, never imposed
# --------------------------------------------------------------------------

def test_supply_ceiling_is_the_binding_minimum_of_both_constraints(registry, initial):
    """Eq. (38) — at the initial calibration labour binds, not capital."""
    ceiling = {eq.name: eq for eq in registry}["GDP_RMAX"]
    assert ceiling.func(initial, initial) == min(
        initial["GDP_RFE"], initial["GDP_RFK"]
    )
    assert initial["GDP_RFE"] < initial["GDP_RFK"]


def test_real_gdp_is_demand_determined_and_may_exceed_the_ceiling(registry, initial):
    """The model is demand-determined: nothing here caps GDP_R at GDP_RMAX.

    Supply bites through prices and wages in §3.3-§3.4, not by truncating
    output. If someone "fixes" Eq. (25) by clamping it to GDP_RMAX, DEFINE
    becomes supply-determined and every published scenario delta changes —
    so this property is pinned, not left to reviewer memory.
    """
    equations = {eq.name: eq for eq in registry}
    # Push demand far above both supply constraints.
    hot = dict(initial, CONS_R=initial["CONS_R"] * 3.0)
    gdp_r = equations["GDP_R"].func(hot, initial)
    ceiling = equations["GDP_RMAX"].func(hot, initial)
    assert gdp_r > ceiling
    # And utilisation is free to exceed 1 — it is a ratio, not a bound.
    assert equations["u"].func(dict(hot, GDP_R=gdp_r), initial) > 1.0


# --------------------------------------------------------------------------
# 6. The section solves as a system
# --------------------------------------------------------------------------

def test_section_solves_to_a_fixed_point_close_to_the_manual_calibration(
    registry, initial
):
    """Held at its own initial values, §3.2 must reproduce them.

    This is the whole-section version of the identity tests: it catches a
    transcription error that happens to be self-consistent equation by
    equation but not jointly. The residual is dominated by the Eq. (27)
    inconsistency above, which feeds GCF_R into GDP_R and from there into
    employment and the ratios — so the tolerance is looser than SIG_FIG_TOL
    by roughly that gap, and no looser.
    """
    exogenous = {name: initial[name] for name in macro.EXOGENOUS_TO_SECTION}
    solved = solve_period(registry, lag=initial, exogenous=exogenous)

    for name in ("GDP", "CONS", "GCF", "GDP_R", "EMP", "LF", "re", "u"):
        assert solved[name] == pytest.approx(initial[name], rel=6e-3), (
            f"{name}: solved {solved[name]!r} vs Table 6 {initial[name]!r}"
        )

    # Accounting identities must hold *exactly* at the solved point, not
    # just to Table 6's precision — these are definitions, not estimates.
    assert solved["GDP"] == pytest.approx(
        solved["CONS"] + solved["GCF"] + solved["EXP"] - solved["IMP"], rel=1e-12
    )
    assert solved["P"] == pytest.approx(solved["GDP"] / solved["GDP_R"], rel=1e-12)
    assert solved["re"] + solved["ru"] == pytest.approx(1.0, rel=1e-12)


# --------------------------------------------------------------------------
# 7. The untabulated intercept stays visible
# --------------------------------------------------------------------------

def test_missing_alpha0_lambda_is_recorded_as_a_manual_gap():
    """Eq. (31)'s intercept is not in Table 5; that must not go quiet.

    Table 5's α_0 block runs α_0GCFFF … α_0WS and then jumps to α_1βHH.
    We default the intercept to 0.0 and record why. If the DEFINE team
    publishes a value and it is added to PARAMETERS, this test fails and
    forces the placeholder note to be removed with it.
    """
    assert "alpha0_lambda" in macro.MANUAL_GAPS
    assert "alpha0_lambda" not in PARAMETERS, (
        "alpha0_lambda is now tabulated — drop the 0.0 default in macro.py "
        "and remove its MANUAL_GAPS entry"
    )
    # The two coefficients the manual *does* tabulate are in use.
    assert PARAMETERS["alpha1_lambda"] == 0.725
    assert PARAMETERS["alpha2_lambda"] == 0.025
