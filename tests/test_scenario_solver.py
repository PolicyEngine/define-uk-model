"""Scenario solver, §3.3.3 input-output block and the empirical-forms flag.

Hermetic half (runs in CI): solver failure modes on toy systems, the
empirical-forms switch, and the §3.3.3 identities on the manual's own §5
Table 6 values. The cached-run half (skips in CI: the upstream is
unlicensed, so CI never fetches or runs it) solves the registry over
2023Q1-2040Q4 against the pinned oracle run; see test_oracle.py for the
skip convention.
"""

from __future__ import annotations

import math

import pytest

from define_uk.model import Equation, Registry, solve_period
from define_uk.model.calibration import INITIAL_VALUES as T6
from define_uk.model.calibration import PARAMETERS
from define_uk.model.empirical import EMPIRICAL_FORMS
from define_uk.model.scenario import (
    ConvergenceError,
    quarter_label,
    solve_path,
)
from define_uk.model.sectors import build_registry, io


def _toy(c=0.8):
    r = Registry()
    r.add(Equation("Y", "test fixture", "identity", lambda s, l: s["C"] + s["G"]))
    r.add(Equation("C", "test fixture", "behavioural", lambda s, l: c * s["Y"]))
    return r


# --- solver failure modes -------------------------------------------------

def test_a_nan_sweep_raises_instead_of_converging():
    """Before 2026-11-06 a NaN made |new - old| / scale compare false, so a
    sweep producing NaN 'converged' at once and returned NaN as a result."""
    r = Registry()
    r.add(Equation("X", "test fixture", "identity", lambda s, l: math.nan))
    with pytest.raises(RuntimeError, match="not finite"):
        solve_period(r, lag={"X": 1.0})


def test_non_convergence_names_the_worst_variable():
    r = Registry()
    r.add(Equation("X", "test fixture", "identity", lambda s, l: 2.0 * s["X"] + 1.0))
    with pytest.raises(RuntimeError, match="did not converge.*in X"):
        solve_period(r, lag={"X": 1.0}, max_iter=30)


def _toy_reference(n=8, g=20.0):
    return [{"Y": 100.0, "C": 80.0, "G": g} for _ in range(n)]


def test_solve_path_reproduces_its_own_reference():
    path = solve_path(_toy(), _toy_reference(), start=2)
    for t in range(2, 8):
        assert path[t]["Y"] == pytest.approx(100.0, rel=1e-9)


def test_zero_shock_is_the_unshocked_solve_bit_for_bit():
    ref = _toy_reference()
    base = solve_path(_toy(), ref, start=2)
    same = solve_path(_toy(), ref, start=2, overrides={"G": [r["G"] for r in ref]})
    assert [p["Y"] for p in base] == [p["Y"] for p in same]


def test_toy_shock_is_linear_and_symmetric():
    ref = _toy_reference()
    base = solve_path(_toy(), ref, start=2)[5]["Y"]
    d = {k: solve_path(_toy(), ref, start=2, overrides={"G": 20.0 + k})[5]["Y"] - base
         for k in (-2.0, -1.0, 1.0, 2.0)}
    assert d[1.0] == pytest.approx(5.0, rel=1e-7)  # multiplier 1/(1-0.8)
    assert d[2.0] == pytest.approx(2 * d[1.0], rel=1e-7)
    assert d[-1.0] == pytest.approx(-d[1.0], rel=1e-7)


def test_a_quarter_that_does_not_converge_raises_with_its_label():
    # c = 1.25 makes the toy Gauss-Seidel map explosive.
    with pytest.raises(ConvergenceError, match=quarter_label(3)) as exc:
        solve_path(_toy(c=1.25), _toy_reference(), start=3, max_iter=50)
    assert exc.value.t == 3


def test_an_override_takes_the_variable_off_the_registry():
    path = solve_path(_toy(), _toy_reference(), start=2, overrides={"C": 50.0})
    assert path[4]["C"] == 50.0 and path[4]["Y"] == pytest.approx(70.0)


def test_bad_window_is_refused():
    with pytest.raises(ValueError, match="window"):
        solve_path(_toy(), _toy_reference(), start=0)


# --- empirical forms flag -------------------------------------------------

def test_default_registry_is_the_manual_as_printed():
    manual = build_registry()
    assert [e.func for e in manual] != [e.func for e in build_registry("empirical")]
    again = build_registry("manual")
    assert [e.manual_ref for e in again] == [e.manual_ref for e in manual]


def test_empirical_flag_replaces_exactly_the_twelve_forms_in_place():
    manual = list(build_registry())
    emp = list(build_registry("empirical"))
    assert len(EMPIRICAL_FORMS) == 12
    assert [e.name for e in manual] == [e.name for e in emp]  # solve order kept
    assert [e.manual_ref for e in manual] == [e.manual_ref for e in emp]
    changed = {m.name for m, e in zip(manual, emp)
               if m.func.__code__ is not e.func.__code__}
    assert changed == set(EMPIRICAL_FORMS)


def test_empirical_forms_match_the_pinned_oracle_forms():
    from test_oracle import ORACLE_FORMS
    assert set(ORACLE_FORMS) - {"alpha_PP"} == set(EMPIRICAL_FORMS)


def test_unknown_forms_value_is_refused():
    with pytest.raises(ValueError, match="forms"):
        build_registry("oracle")


def test_replace_keeps_provenance():
    r = Registry()
    r.add(Equation("X", "§3.3.3 eq. (139)", "calibrated", lambda s, l: 1.0))
    with pytest.raises(ValueError, match="manual_ref"):
        r.replace(Equation("X", "§3.3.3 eq. (140)", "calibrated", lambda s, l: 2.0))
    with pytest.raises(KeyError):
        r.replace(Equation("Y", "§3.3.3 eq. (139)", "calibrated", lambda s, l: 2.0))


# --- §3.3.3 input-output block, hermetic ----------------------------------

def test_io_section_is_contiguous_139_to_158():
    nums = sorted(e.number for e in build_registry() if e.section == "§3.3.3")
    assert nums == list(range(139, 159))


def test_leontief_inverse_inverts_i_minus_a():
    """Eqs. (154)-(158) are the 2x2 inverse: L (I - A) = I exactly."""
    a_pp, a_pps, a_psp, a_psps = 0.2762, 0.2006, 0.03955, 0.4474
    s = {"alpha_PP": a_pp, "alpha_PPS": a_pps, "alpha_PSP": a_psp,
         "alpha_PSPS": a_psps}
    by = {e.name: e for e in build_registry()}
    s["det_IA"] = by["det_IA"].func(s, {})
    L = [[by["L_PP"].func(s, {}), by["L_PPS"].func(s, {})],
         [by["L_PSP"].func(s, {}), by["L_PSPS"].func(s, {})]]
    IA = [[1 - a_pp, -a_pps], [-a_psp, 1 - a_psps]]
    for i in range(2):
        for j in range(2):
            got = sum(L[i][k] * IA[k][j] for k in range(2))
            assert got == pytest.approx(1.0 if i == j else 0.0, abs=1e-12)


def test_io_identities_hold_on_table_6():
    """The intermediate-consumption and inverse identities, Eqs. (144)-(158),
    on the manual's own §5 Table 6 values, to its printing precision."""
    by = {e.name: e for e in build_registry() if e.section == "§3.3.3"}
    s = dict(T6)
    for name in ("IC_PSPR", "IC_FUELPSR", "IC_OPPSR", "IC_PP",
                 "IC_PSP", "IC_PSPS", "IC_PPS", "IC_FUELPS", "IC_OPPS",
                 "det_IA", "L_PP", "L_PPS", "L_PSP", "L_PSPS"):
        if name not in T6:
            continue
        assert by[name].func(s, s) == pytest.approx(T6[name], rel=6e-3), name


def test_table_6_alpha_pps_is_valued_at_unit_relative_price():
    """Eq. (144) on Table 6 gives 0.1962 at the tabulated P_FUEL/P_P =
    1/1.035, 2.2% below the tabulated 0.2006; Table 6's value is exactly
    alpha_FUELPS + alpha_OPPS, i.e. P_FUEL/P_P = 1. The same base-period
    deflator pattern as Eq. (27)'s capital block (REIMPLEMENTATION.md).
    The oracle reproduces Eq. (144) in every simulated quarter (test_oracle)."""
    eq = next(e for e in build_registry() if e.name == "alpha_PPS")
    assert eq.func(T6, T6) == pytest.approx(0.19621, abs=1e-5)
    assert T6["alpha_FUELPS"] + T6["alpha_OPPS"] == pytest.approx(T6["alpha_PPS"], abs=1e-4)


def test_table_6_alphas_are_first_period_jumps_from_the_table_5_rules():
    """Eqs. (139), (141), (142) set the coefficients to their Table 5
    long-run values; Table 6 prints different t=L values (the same
    'historical mean' pattern pinned for Eqs. (51)/(59)/(94)/(111))."""
    assert T6["alpha_PP"] == 0.2798 and PARAMETERS["alpha_PPLR"] == 0.2762
    assert T6["alpha_OPPS"] == 0.07051 and PARAMETERS["alpha_OPPSLR"] == 0.0503
    assert T6["alpha_PSPS"] == 0.4474 and PARAMETERS["alpha_PSPSLR"] == 0.3836


def test_io_manual_gap_is_recorded():
    assert "alpha_FUELPSR" in io.MANUAL_GAPS


# --- cached-run half: solves against the pinned oracle run -----------------

from test_oracle import (  # noqa: E402
    ALPHA_PP_BASELINE_RUN,
    requires_cached_run,
)

_SECTOR_LEND = ("LEND_NFC", "LEND_PS", "LEND_MFI", "LEND_NMFI", "LEND_GVT",
                "LEND_HH", "LEND_RoW")
_SIM = range(144, 216)


def _ref(rel):
    from define_uk.model.scenario import load_reference, scenario_inputs
    from define_uk.scenarios import _TABLES, _run_root
    return scenario_inputs(load_reference(_run_root() / _TABLES / rel))


@pytest.fixture(scope="module")
def baseline_ref():
    return _ref("gvt_investment/Variables_Baseline.csv")


@pytest.fixture(scope="module")
def gpi_ref():
    return _ref("gvt_investment/Variables_GPI + Green Bonds.csv")


def _solve(ref, forms="empirical", **over):
    over.setdefault("alpha_PP", ALPHA_PP_BASELINE_RUN)
    return solve_path(build_registry(forms), ref, overrides=over)


@pytest.fixture(scope="module")
def emp_base(baseline_ref):
    return _solve(baseline_ref)


def _gpi_overrides(base, gpi, k):
    d_sp = [g["SPEND_GVTPS"] - b["SPEND_GVTPS"] for g, b in zip(gpi, base)]
    d_k = [g["K_GVTNFFR"] - b["K_GVTNFFR"] for g, b in zip(gpi, base)]
    return {
        "SPEND_GVTPS": [b["SPEND_GVTPS"] + k * d for b, d in zip(base, d_sp)],
        "K_GVTNFFR": [b["K_GVTNFFR"] + k * d for b, d in zip(base, d_k)],
    }


def _cum(path, base, v):
    return sum(path[t][v] - base[t][v] for t in _SIM)


@requires_cached_run
def test_every_baseline_file_uses_the_lower_alpha_pp():
    """All 7 Baseline files print alpha_PP = 0.2748 in every simulated
    quarter; all 23 policy files print Table 5's 0.2762 (Eq. (139))."""
    from define_uk.scenarios import _TABLES, _run_root
    from define_uk.model.scenario import load_reference
    files = sorted((_run_root() / _TABLES).rglob("Variables_*.csv"))
    seen = {}
    for f in files:
        vals = {r["alpha_PP"] for r in load_reference(f)[144:]}
        seen[f.name == "Variables_Baseline.csv"] = seen.get(
            f.name == "Variables_Baseline.csv", set()) | vals
    assert seen == {True: {0.2748}, False: {0.2762}}


@requires_cached_run
@pytest.mark.parametrize("forms", ["manual", "empirical"])
def test_baseline_solve_converges_every_quarter(baseline_ref, forms):
    path = _solve(baseline_ref, forms)
    assert len(path) == len(baseline_ref)
    assert all(math.isfinite(path[t]["GDP"]) for t in _SIM)


@requires_cached_run
@pytest.mark.parametrize("forms", ["manual", "empirical"])
def test_conditional_baseline_gdp_is_within_0_6_percent(baseline_ref, forms):
    """Block-exogenous closure (§3.1/§3.4 held at the oracle): GDP stays
    within 0.6% of the oracle every quarter (0.41% empirical, 0.43% manual,
    measured 2026-11-06), the price level within 1.3%. This is NOT the
    milestone-2 gate: the power-sector block does not reproduce (below)."""
    path = _solve(baseline_ref, forms)
    def worst(v):
        return max(abs(path[t][v] / baseline_ref[t][v] - 1) for t in _SIM)
    assert worst("GDP") < 6e-3
    assert worst("P") < 1.3e-2


@requires_cached_run
def test_power_sector_investment_does_not_reproduce_without_alpha0_gcfps(emp_base, baseline_ref):
    """Eq. (96)'s intercept alpha_0GCFPS is not in Table 5
    (power.MANUAL_GAPS, defaulted to 0): solved desired power investment
    GCF_PSD misses the oracle by more than 100% within three quarters, and
    the power-sector finance block (YD_PS, RP_PS, DSR_PS, LEND_PS) follows."""
    t = 146
    assert abs(emp_base[t]["GCF_PSD"] / baseline_ref[t]["GCF_PSD"] - 1) > 1.0


@requires_cached_run
def test_manual_eq_84_doubles_the_solved_electricity_price(baseline_ref):
    """As printed, (1 + MU_ELEC) MC_ELEC: the solved P_ELEC ends up more
    than 100% above the oracle; the empirical form stays within 0.4%."""
    man = _solve(baseline_ref, "manual")
    emp = _solve(baseline_ref, "empirical")
    gap = lambda p: max(abs(p[t]["P_ELEC"] / baseline_ref[t]["P_ELEC"] - 1) for t in _SIM)
    assert gap(man) > 1.0
    assert gap(emp) < 4e-3


@requires_cached_run
def test_zero_shock_scenario_is_the_baseline_bit_for_bit(baseline_ref, emp_base):
    same = _solve(baseline_ref, SPEND_GVTPS=[r["SPEND_GVTPS"] for r in baseline_ref])
    assert all(same[t] == emp_base[t] for t in _SIM)


@requires_cached_run
def test_sum_of_net_lending_is_zero_in_the_oracle_every_quarter(baseline_ref):
    worst = max(abs(sum(baseline_ref[t][k] for k in _SECTOR_LEND)) for t in _SIM)
    assert worst < 0.05


@requires_cached_run
def test_solved_stock_flow_gap_is_exactly_the_power_sector_divergence(baseline_ref, emp_base):
    """Every other sector is held at the oracle, so the solved economy-wide
    LEND gap equals LEND_PS(solved) - LEND_PS(oracle) in every quarter."""
    for t in _SIM:
        gap = sum(emp_base[t][k] for k in _SECTOR_LEND)
        oracle = sum(baseline_ref[t][k] for k in _SECTOR_LEND)
        assert gap - oracle == pytest.approx(
            emp_base[t]["LEND_PS"] - baseline_ref[t]["LEND_PS"], abs=1e-9)


@requires_cached_run
@pytest.mark.xfail(strict=True, reason="milestone 3: §3.4 counterpart sectors "
                   "not implemented, so the solve is not stock-flow consistent")
def test_solved_baseline_is_stock_flow_consistent_every_quarter(emp_base):
    worst = max(abs(sum(emp_base[t][k] for k in _SECTOR_LEND)) for t in _SIM)
    assert worst < 0.05


@pytest.fixture(scope="module")
def gpi_shocks(baseline_ref, gpi_ref):
    out = {}
    for forms in ("empirical", "manual"):
        b0 = _solve(baseline_ref, forms)
        for k in (-1.0, -0.5, 0.5, 1.0):
            p = _solve(baseline_ref, forms, **_gpi_overrides(baseline_ref, gpi_ref, k))
            out[forms, k] = {v: _cum(p, b0, v) for v in
                             ("GDP", "GDP_R", "GCF", "P", "GO_PSR", "P_ELEC")}
    return out


@requires_cached_run
def test_gpi_shock_sign_and_unit_nominal_multiplier(gpi_shocks, baseline_ref, gpi_ref):
    """+100% of the GPI + Green Bonds green public investment path (cum
    91.23bn): cum nominal GDP rises by exactly the spending (multiplier
    1.00) because nothing that would multiply it (households, NFC
    investment, imports) is solved yet. The oracle's own cum ΔGDP is 209.9
    (2.30). Real GDP rises less (69.7bn) because prices rise."""
    d_sp = sum(g["SPEND_GVTPS"] - b["SPEND_GVTPS"] for g, b in
               zip(gpi_ref[144:], baseline_ref[144:]))
    s = gpi_shocks["empirical", 1.0]
    assert d_sp == pytest.approx(91.23, abs=0.01)
    assert s["GDP"] == pytest.approx(d_sp, abs=1e-3)
    assert 0 < s["GDP_R"] < s["GDP"]
    assert s["P"] > 0 and s["GO_PSR"] > 0 and s["P_ELEC"] > 0


@requires_cached_run
@pytest.mark.parametrize("v,lin,sym", [("GDP", 1e-6, 1e-6), ("GDP_R", 2e-3, 5e-3),
                                       ("GO_PSR", 2e-3, 5e-3), ("P_ELEC", 2e-3, 5e-3),
                                       ("P", 1e-2, 3e-2)])
def test_gpi_shock_is_linear_and_symmetric(gpi_shocks, v, lin, sym):
    s = {k: gpi_shocks["empirical", k][v] for k in (-1.0, -0.5, 0.5, 1.0)}
    assert s[1.0] / (2 * s[0.5]) == pytest.approx(1.0, abs=lin)
    assert -s[-1.0] / s[1.0] == pytest.approx(1.0, abs=sym)


@requires_cached_run
def test_gpi_shock_never_reaches_gdp_under_the_manual_as_printed(gpi_shocks):
    """Eq. (23) as printed has no SPEND_GVTPS term and Eq. (272) makes
    GCF_GVT the exogenous GCF_GVTBASE, so in the printed manual the green
    public investment shock moves nothing in §3.2-§3.3.3."""
    for k in (-1.0, -0.5, 0.5, 1.0):
        assert all(x == 0.0 for x in gpi_shocks["manual", k].values())
