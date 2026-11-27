"""Whole-model checks after §3.1 and §3.4 landed (2026-11-06, round 4).

Hermetic half (runs in CI): the CSV alias map, the sector-indexed refs of
§3.4.7, the MFI residual-sector closure and the dividend closure on the
manual's own §5 Table 6 values. Cached-run half (skips in CI; see
test_oracle.py for the convention): the whole registry solved over
2023Q1-2040Q4 with nothing read from the oracle but exogenous inputs.
"""

from __future__ import annotations

import math

import pytest

from define_uk.model.calibration import INITIAL_VALUES as T6
from define_uk.model.calibration import PARAMETERS
from define_uk.model.scenario import CSV_ALIASES
from define_uk.model.sectors import build_registry

# Table 6 keys the cached CSVs do not print under any spelling.
NOT_PRINTED = {"SUBS_GVT"}
# Registry names the CSV_ALIASES map that are not Table 6 keys.
ALIAS_EXTRAS = {"r_IBL_NFCLR", "r_IBL_PSLR", "r_IBL_NMFILR", "r_IBL_GVTLR",
                "r_IBL_HHLR", "ROW_Pg"}
SECTOR_LEND = ("LEND_NFC", "LEND_PS", "LEND_MFI", "LEND_NMFI", "LEND_GVT",
               "LEND_HH", "LEND_ROW")
DIVIDENDS = ("DIVR_NFC", "DIVR_PS", "DIVR_HH", "DIVR_NMFI")


def _eq(forms="manual"):
    return {e.name: e for e in build_registry(forms)}


def test_csv_aliases_map_onto_table_6_names():
    """Every alias target is a Table 6 key (or a listed non-Table-6 name),
    so a differently spelled CSV column always lands on the name the
    equations read. Before 2026-11-06 the map held only lambda and MU, and
    r_IBA_PS, r_IBL_PS, r_IBL_GVT, OTEQL_NMFI and WS were held at their
    2022Q4 Table 6 values in every solved quarter."""
    targets = set(CSV_ALIASES.values())
    assert targets - set(T6) == ALIAS_EXTRAS
    assert len(targets) == len(CSV_ALIASES), "two CSV names alias one variable"


def test_every_printed_equation_is_registered_and_indexed_refs_parse():
    reg = build_registry()
    assert sorted({e.number for e in reg}) == list(range(1, 402))
    tagged = [e for e in reg if e.manual_ref.endswith("]")]
    assert {e.number for e in tagged} == {159, 257, 397, 398, 399, 400, 401}
    # GOS_P [GOS]; ITAX_PS split [NFF]/[FF]; r_BOEQ [Q], INF_A [INF];
    # 6 asset, 5 liability (the manual gaps closed for issue #24).
    assert len(tagged) == 1 + 2 + 2 + 6 + 6 + 5 + 5


def test_mfi_discrepancy_is_minus_the_sum_of_the_others():
    """Eq. (211): the MFI lending discrepancy closes Σ DISC to zero."""
    eqs = _eq()
    s = dict(T6)
    for n in ("DISC_NFC", "DISC_NMFI", "DISC_GVT", "DISC_HH", "DISC_ROW"):
        s[n] = eqs[n].func(s, T6)
    s["DISC_MFI"] = eqs["DISC_MFI"].func(s, T6)
    total = sum(s[n] for n in ("DISC_NFC", "DISC_NMFI", "DISC_GVT", "DISC_HH",
                               "DISC_ROW", "DISC_MFI"))
    assert total == pytest.approx(0.0, abs=1e-12)


def _dividend_gap(forms):
    """Σ dividends received + RoW net dividends - Σ dividends paid, with the
    four receipt equations evaluated on Table 6 (payments as tabulated)."""
    eqs = _eq(forms)
    s = dict(T6)
    for _ in range(3):  # DIVR_NFC (empirical) reads DIVR_HH and DIVR_PS
        for n in DIVIDENDS:
            s[n] = eqs[n].func(s, T6)
    received = s["DIVR_NFC"] + s["DIVR_PS"] + s["DIVR_HH"] + s["DIVR_NMFI"]
    paid = s["DIVP_NFC"] + s["DIVP_PS"] + s["DIVP_NMFI"]
    return received + s["DIVN_ROW"] - paid


def test_manual_dividend_allocation_does_not_close():
    """As printed, Eqs. (93), (163), (313) give each holder beta_j times its
    equity share of DIVP_NMFI (beta_dhh = 1.333, beta_dps = 0.773, beta_dnfc
    untabulated) and Eq. (221) omits the RoW, so the dividend row of the
    transactions matrix does not sum to zero: Σ LEND != 0 by construction."""
    assert abs(_dividend_gap("manual")) > 1.0


def test_empirical_dividend_forms_close_the_dividend_row_exactly():
    """The oracle's forms (empirical.py): DIVR_NFC is the residual, DIVR_HH
    and DIVR_PS divide by EQL_NMFI - EQN_RoW, NMFIs pay the RoW's DIVN."""
    assert _dividend_gap("empirical") == pytest.approx(0.0, abs=1e-9)


# --- cached-run half: the whole model solved ------------------------------

from test_oracle import ALPHA_PP_BASELINE_RUN, requires_cached_run  # noqa: E402

_SIM = range(144, 216)
# The nine equations issue #17 listed as undiagnosed until 2026-11-27. Their
# forms are now in empirical.py (seven are the run's own parameter values).
# Holding them at the oracle remains a diagnostic of what they carry.
FORMERLY_UNDIAGNOSED = ("GCF_NFCD", "SOCB_GVT", "CF_NFF", "r_IBA_PSLR",
                        "r_IBL_NMFILR", "r_IBL_GVTLR", "prop_NFF", "CR_PS",
                        "GCF_PSD")


def _ref(rel):
    from define_uk.model.scenario import load_reference, scenario_inputs
    from define_uk.scenarios import _TABLES, _run_root
    return scenario_inputs(load_reference(_run_root() / _TABLES / rel))


@pytest.fixture(scope="module")
def base():
    return _ref("gvt_investment/Variables_Baseline.csv")


@pytest.fixture(scope="module")
def gpi():
    return _ref("gvt_investment/Variables_GPI + Green Bonds.csv")


def _overrides(base, gpi=None, k=0.0, hold=()):
    o = {"alpha_PP": ALPHA_PP_BASELINE_RUN}
    if gpi is not None:
        o["SPEND_GVTPS"] = [b["SPEND_GVTPS"] + k * (g["SPEND_GVTPS"] - b["SPEND_GVTPS"])
                            for b, g in zip(base, gpi)]
    for n in hold:
        o[n] = [r[n] for r in base]
    return o


def _solve(base, forms, **kw):
    from define_uk.model.scenario import solve_path
    return solve_path(build_registry(forms), base, overrides=_overrides(base, **kw),
                      max_iter=5000)


@pytest.fixture(scope="module")
def solved(base):
    return {f: _solve(base, f) for f in ("manual", "empirical")}


def _sum_lend(path, t):
    return sum(path[t][k] for k in SECTOR_LEND)


@requires_cached_run
def test_whole_model_solves_every_quarter_both_ways(solved):
    for path in solved.values():
        assert all(math.isfinite(path[t]["GDP"]) for t in _SIM)


@requires_cached_run
def test_empirical_whole_model_is_stock_flow_consistent_every_quarter(solved):
    """Σ_s LEND_s = 0 is the redundant equation (MFIs are the residual
    sector). With the oracle's dividend and subsidy forms it holds to
    machine precision in every solved quarter, nothing imposed."""
    assert max(abs(_sum_lend(solved["empirical"], t)) for t in _SIM) < 1e-8


def _fnw_spread(path):
    """Spread of the economy-wide financial net worth Σ_s FNW_s over the
    solved quarters, and the largest |residual| of every other financial
    row of Table 2. Σ FNW_s is constant, not zero: the solve starts from
    stocks the CSVs print at 4 s.f. plus Table 6 values for the
    power-sector stocks they do not print (0.200 at Table 6)."""
    from define_uk.model.accounting import balance_sheet_residuals
    res = [balance_sheet_residuals(path[t]) for t in _SIM]
    fnw = [r["totals"]["fnw_total"] for r in res]
    eq = [r["rows"]["equity_liabilities"] for r in res]
    other = max(abs(v) for r in res for k, v in r["rows"].items()
                if k != "equity_liabilities")
    return max(fnw) - min(fnw), max(eq) - min(eq), other


@requires_cached_run
def test_empirical_whole_model_balance_sheet_closes_every_quarter(solved):
    """Σ LEND = 0 checks the flows only. The stocks must close too: with
    the Eq. (109) form alone (power sector's equity share GO_PS/GO) and the
    manual Eq. (179) (NFC share 1 - theta_psb), the two issuers' shares did
    not sum to one and Σ FNW_s drifted from 0.2 to -18.5 by 2040Q4 through
    the equity row (r9, 13 Nov 2026). The paired Eq. (179) form holds every
    financial row and Σ FNW_s fixed to rounding."""
    fnw, eq, other = _fnw_spread(solved["empirical"])
    # Σ FNW_s sums stocks of order 1e4, so float accumulation reaches 1.2e-8;
    # before the Eq. (179) form the spread was 18.7.
    assert fnw < 1e-6 and eq < 1e-8 and other < 1e-8


@requires_cached_run
def test_manual_as_printed_leaks_through_the_dividend_row(solved):
    """As printed Σ LEND is 5.87 in 2023Q1 and grows to 69.2 by 2040Q4
    (72.9 before INF_A was made endogenous, issue #24; measured
    2026-11-15): the dividend allocation does not close."""
    worst = max(abs(_sum_lend(solved["manual"], t)) for t in _SIM)
    assert 50.0 < worst < 100.0
    assert _sum_lend(solved["manual"], 144) == pytest.approx(5.87, abs=0.05)


@requires_cached_run
@pytest.mark.xfail(strict=True, reason="whole-model baseline GDP is within "
                   "1.23% of the oracle (worst in 2025Q1; 0.1% high in "
                   "2040Q4), not 1%. It was 44% before the consumption and "
                   "equity forms of 2026-11-24 and 3.7% before the run "
                   "parameters and forms of 2026-11-27")
def test_whole_model_baseline_gdp_within_1_percent(solved, base):
    p = solved["empirical"]
    assert max(abs(p[t]["GDP"] / base[t]["GDP"] - 1) for t in _SIM) < 0.01


def _gap(path, base, v):
    return max(abs(path[t][v] / base[t][v] - 1) for t in _SIM)


def _cum_emissions_gap(path, base):
    """Emissions summed over the policy window 2027Q1-2040Q4."""
    return (sum(path[t]["EMIS"] for t in _SIM if t >= 160)
            / sum(base[t]["EMIS"] for t in _SIM if t >= 160) - 1)


@requires_cached_run
def test_whole_model_baseline_is_within_1_3_percent_on_gdp(solved, base):
    """The whole registry, nothing held at the oracle (measured 2026-11-27).

    Empirical forms (39, and the two profit rates): nominal GDP within
    1.23% of the oracle in every quarter (worst in 2025Q1, 0.1% high in
    2040Q4), real GDP 1.4%, household consumption 1.8%, the price level
    1.6%, investment 1.5%. With the 25 forms of 2026-11-24 the figures
    were 3.7%, 1.7%, 4.9%, 2.1% and 4.1%.

    Two things moved it. The 13 forms of 2026-11-27 (the run's own
    parameter values and six forms) alone leave GDP 3.4% low by 2040Q4: a
    steady downward drift. That drift is world demand: Table 5's growth
    factor 1.007 is the 4 s.f. print of 1.00742 (Eq. (372),
    empirical.ROW_DG_IMPLIED), and the difference compounds to 3.0% of
    exports' driver over 72 quarters. Neither step on its own gets below
    3%: the earlier 3.7% rested on errors that offset each other.

    Emissions: 9.2% above the oracle in 2040Q4 and 4.2% above it summed
    over 2027-2040, against 85% and 43% before 2026-11-27. The manual as
    printed still ends 48% low on GDP.
    """
    p = solved["empirical"]
    assert _gap(p, base, "GDP") == pytest.approx(0.0123, abs=0.001)
    assert p[-1]["GDP"] / base[-1]["GDP"] - 1 == pytest.approx(0.001, abs=0.002)
    assert _gap(p, base, "GDP_R") < 0.015
    assert _gap(p, base, "CONS_HH") < 0.02
    assert _gap(p, base, "P") < 0.018
    assert _gap(p, base, "GCF") < 0.016
    assert p[-1]["EMIS"] / base[-1]["EMIS"] - 1 == pytest.approx(0.092, abs=0.01)
    assert _cum_emissions_gap(p, base) == pytest.approx(0.042, abs=0.005)
    assert _gap(solved["manual"], base, "GDP") == pytest.approx(0.48, abs=0.01)


@requires_cached_run
def test_emissions_gap_is_in_the_fossil_generation_residual(solved, base):
    """Where the remaining 9.2% sits in 2040Q4 (measured 2026-11-27).
    Electricity emissions are 1.87 against the oracle's 0.70: fossil
    generation is the residual E_ELEC - E_ELECNFF (Eq. (7)), 6.2 against
    2.3, because non-fossil capital ends 9% low (the split prop_NFF is
    0.80 where the oracle's reaches 1.00). Non-electricity emissions are
    7.4% high, with green production capital 6.5% low. Before the
    power-sector forms, non-fossil capital ended 75% low and electricity
    emissions were 31.4."""
    p, b = solved["empirical"][-1], base[-1]
    assert p["EMIS_ELEC"] == pytest.approx(1.87, abs=0.15) and b["EMIS_ELEC"] < 0.7
    assert p["E_ELECFF"] == pytest.approx(6.2, abs=0.4)
    assert p["K_PSNFFR"] / b["K_PSNFFR"] - 1 == pytest.approx(-0.088, abs=0.01)
    assert p["prop_NFF"] == pytest.approx(0.80, abs=0.02) and b["prop_NFF"] > 0.999
    assert p["EMIS_NELEC"] / b["EMIS_NELEC"] - 1 == pytest.approx(0.074, abs=0.01)
    assert p["K_PG"] / b["K_PG"] - 1 == pytest.approx(-0.065, abs=0.01)
    assert p["CF_NFF"] == pytest.approx(b["CF_NFF"], rel=2e-3)  # the 0.6 floor


@requires_cached_run
def test_holding_the_nine_equations_at_the_oracle_brings_gdp_within_half_a_percent(base):
    """The nine equations issue #17 listed as undiagnosed, held at the
    oracle with the rest solved (diagnostic only): GDP within 0.5% of the
    oracle in every quarter, household consumption 0.5%, emissions 0.3% low
    in 2040Q4. On 2026-11-24 the same diagnostic gave 5.1%; the difference
    is the world-demand growth factor (Eq. (372)). So what the free solve
    still misses (1.23% on GDP, 9.2% on emissions) is the feedback through
    those nine, chiefly the power-sector investment split, not anything
    else in the registry. Σ LEND stays 0. Measured 2026-11-27."""
    p = _solve(base, "empirical", hold=FORMERLY_UNDIAGNOSED)
    assert _gap(p, base, "GDP") == pytest.approx(0.005, abs=0.002)
    assert _gap(p, base, "CONS_HH") == pytest.approx(0.005, abs=0.002)
    assert p[-1]["YD_HH"] / base[-1]["YD_HH"] - 1 == pytest.approx(-0.005, abs=0.003)
    assert p[-1]["EMIS"] / base[-1]["EMIS"] - 1 == pytest.approx(-0.003, abs=0.003)
    assert max(abs(_sum_lend(p, t)) for t in _SIM) < 1e-8


@requires_cached_run
def test_zero_shock_is_the_whole_model_baseline_bit_for_bit(base, gpi, solved):
    same = _solve(base, "empirical", gpi=gpi, k=0.0)
    assert all(same[t] == solved["empirical"][t] for t in _SIM)


@pytest.fixture(scope="module")
def gpi_cum(base, gpi, solved):
    out = {}
    for forms in ("manual", "empirical"):
        for k in (-1.0, -0.5, 0.5, 1.0):
            p = _solve(base, forms, gpi=gpi, k=k)
            out[forms, k] = {v: sum(p[t][v] - solved[forms][t][v] for t in _SIM)
                             for v in ("GDP", "GDP_R", "CONS_HH", "LEND_GVT")}
            out[forms, k]["sfc"] = max(abs(_sum_lend(p, t)) for t in _SIM)
            out[forms, k]["fnw"] = _fnw_spread(p)[0]
    return out


@requires_cached_run
def test_gpi_never_reaches_the_economy_under_the_manual_as_printed(gpi_cum):
    """Eq. (23) has no SPEND_GVTPS term, Eq. (272) GCF_GVT is exogenous and
    Eq. (281) has no SPEND_GVTPS: the printed manual gives the green public
    investment shock no channel at all, whole model included."""
    for k in (-1.0, -0.5, 0.5, 1.0):
        assert all(gpi_cum["manual", k][v] == 0.0 for v in ("GDP", "GDP_R", "CONS_HH"))


@requires_cached_run
def test_gpi_whole_model_response_and_sfc(gpi_cum):
    """+100% of the GPI path (cum 91.23bn), measured 2026-11-27: real GDP
    +374.6, household consumption +130.6, nominal GDP +11.9 (0.13 per
    pound), government net lending -15.6.

    The nominal figure is not an estimate of the multiplier. With the
    power-sector forms of 2026-11-27 the power sector responds to the
    investment as the cached run's does through the early 2030s
    (test_gpi_power_sector_response_follows_the_oracle), but the clean-room
    price level then keeps falling (-1.4% by 2040Q4 against -0.3%), which
    takes the nominal sum to near zero while the real one is larger than
    the cached run's +252. Before those forms the figures were +168.1
    nominal (1.84 per pound), +77.7 consumption and +28.2 real: the power
    sector could not respond, so there was no price effect to speak of.

    Nothing here is linear or symmetric any longer: the half shock gives
    consumption +58.6 (0.45 of the full one) and nominal GDP +2.4, and the
    negative shock moves real GDP a third as far as the positive one."""
    s = {k: gpi_cum["empirical", k] for k in (-1.0, -0.5, 0.5, 1.0)}
    for v in ("GDP", "GDP_R", "CONS_HH"):
        assert s[1.0][v] > 0 and s[0.5][v] > 0
        assert s[-1.0][v] < 0 and s[-0.5][v] < 0
    assert s[1.0]["GDP"] == pytest.approx(11.9, abs=1.0)
    assert s[1.0]["GDP_R"] == pytest.approx(374.6, abs=3.0)
    assert s[1.0]["CONS_HH"] == pytest.approx(130.6, abs=1.5)
    assert s[0.5]["CONS_HH"] / s[1.0]["CONS_HH"] == pytest.approx(0.45, abs=0.02)
    assert -s[-1.0]["GDP_R"] / s[1.0]["GDP_R"] == pytest.approx(0.32, abs=0.02)
    assert s[1.0]["LEND_GVT"] < 0  # the government borrows for it
    assert all(c["sfc"] < 1e-8 for c in s.values())
    assert all(c["fnw"] < 1e-6 for c in s.values())


@requires_cached_run
def test_gpi_power_sector_response_follows_the_oracle(base, gpi, solved):
    """The clean-room GPI shock against the cached GPI + Green Bonds delta,
    quarter by quarter (2026-11-27). Through 2033Q3 the power sector
    responds alike: fossil generation, the electricity price and emissions
    are within 30% of the cached delta in 2028Q1, 2030Q1 and 2033Q3
    (emissions: -4.38 / -4.27, -11.14 / -11.21, -17.11 / -15.12 a quarter).
    By 2040Q4 they part: the cached run has no fossil generation left to
    displace (delta +0.03), the clean-room baseline still has (-3.4), so
    its electricity price is still 0.035 lower where the cached run's is
    back at baseline. The cached delta also carries the alpha_PP mismatch
    (#20) and the rest of the GPI + Green Bonds policy."""
    b = solved["empirical"]
    p = _solve(base, "empirical", gpi=gpi, k=1.0)
    for t in (164, 172, 186):
        for v in ("E_ELECFF", "P_ELEC", "EMIS"):
            ours, theirs = p[t][v] - b[t][v], gpi[t][v] - base[t][v]
            assert ours < 0 and theirs < 0, (t, v)
            assert ours / theirs == pytest.approx(1.0, abs=0.3), (t, v)
    assert p[-1]["E_ELECFF"] - b[-1]["E_ELECFF"] < -3.0
    assert abs(gpi[-1]["E_ELECFF"] - base[-1]["E_ELECFF"]) < 0.1
    assert p[-1]["P_ELEC"] - b[-1]["P_ELEC"] == pytest.approx(-0.035, abs=0.005)
    assert abs(gpi[-1]["P_ELEC"] - base[-1]["P_ELEC"]) < 0.001


@requires_cached_run
def test_gpi_moves_the_policy_rate_through_endogenous_inflation(base, gpi, solved):
    """Issue #24: INF_A, the Taylor rule's input (Eq. (397)), was read from
    the oracle's baseline, so r_BOE moved by exactly 0 under GPI. With
    INF_A = (P_P / P_P(-1))^4 - 1 (returns.MANUAL_GAPS) it follows the
    solved price level, and r_BOE responds: +0.051pp / -0.204pp at the
    extremes against the oracle's +0.076pp / -0.194pp (2026-11-27; +0.080
    / -0.014 before the power-sector forms, when the electricity price
    barely moved)."""
    b = solved["empirical"]
    p = _solve(base, "empirical", gpi=gpi, k=1.0)
    for t in _SIM:
        assert b[t]["INF_A"] == pytest.approx((b[t]["P_P"] / b[t - 1]["P_P"]) ** 4 - 1.0)
    dr = [p[t]["r_BOE"] - b[t]["r_BOE"] for t in _SIM]
    oracle = [g["r_BOE"] - r["r_BOE"] for g, r in zip(gpi[144:], base[144:])]
    assert max(map(abs, dr)) > 1e-4  # 0.0 exactly before the fix
    assert max(dr) == pytest.approx(0.00051, abs=3e-5)
    assert min(dr) == pytest.approx(-0.00204, abs=5e-5)
    # The oracle's delta also carries the alpha_PP mismatch (#20) and the
    # rest of the GPI + Green Bonds policy; the two now agree on the size
    # and sign of both extremes.
    assert max(oracle) == pytest.approx(0.00076, abs=2e-5)
    assert min(oracle) == pytest.approx(-0.00194, abs=2e-5)


@requires_cached_run
def test_solved_state_carries_its_own_closures(solved, base):
    """Issue #24: GOS_P and the ITAX_PS split are model values in a solved
    state, not the reference's (GOS_P was the oracle's 417.1 in 2040Q4
    whatever the solve gave: 230.7 = GO_P - COST_P under the manual as
    printed, 415.3 with the empirical forms)."""
    for forms in ("manual", "empirical"):
        path = solved[forms]
        for t in _SIM:
            s = path[t]
            assert s["GOS_P"] == pytest.approx(s["GO_P"] - s["COST_P"], rel=1e-12)
            assert s["ITAX_PSFF"] + s["ITAX_PSNFF"] == pytest.approx(s["ITAX_PS"], rel=1e-9)
    assert abs(solved["manual"][-1]["GOS_P"] - base[-1]["GOS_P"]) > 100
    assert solved["empirical"][-1]["GOS_P"] != base[-1]["GOS_P"]


@requires_cached_run
@pytest.mark.xfail(strict=True, reason="clean-room cumulative nominal GDP "
                   "per pound of GPI is 0.13 against the oracle's 2.25 "
                   "(1.84 before the power-sector forms of 2026-11-27, "
                   "1.52 before those of 2026-11-24): the clean-room price "
                   "level falls four times as far by 2040, so the nominal "
                   "ratio is not reproduced")
def test_gpi_cumulative_multiplier_matches_the_oracle(gpi_cum, base, gpi):
    # The oracle's 2.25 is the policy-window headline (2027Q1-2040Q4). The
    # clean-room shock is the GPI spending path on the clean-room's own
    # baseline, so it has no delta before 2027 and no alpha_PP change: the
    # policy window is the like-for-like one (the target was the
    # full-simulation 2.30 +/- 10% until 2026-11-18; 0.13 misses both). The
    # band is 8% so that its lower edge stays at 2.07: the re-pin moves the
    # target, it does not make the gate easier to pass.
    d_sp = sum(g["SPEND_GVTPS"] - b["SPEND_GVTPS"] for g, b in zip(gpi[144:], base[144:]))
    assert gpi_cum["empirical", 1.0]["GDP"] / d_sp == pytest.approx(2.25, rel=0.08)
