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
    assert {e.number for e in tagged} == {397, 398, 399, 400, 401}
    assert len(tagged) == 1 + 6 + 6 + 5 + 5  # r_BOEQ [Q]; 6 asset, 5 liability


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
# Equations whose oracle form is not known (test_oracle.DIVERGENT, plus the
# §3.3.2 parameter gaps). Holding them at the oracle is a diagnostic of how
# much of the baseline gap they carry, not a model mode.
UNDIAGNOSED = ("GCF_NFCD", "EQLTR_NFC", "OTEQL_NFC", "OTEQL_NMFI", "SOCB_GVT",
               "CONS_HHP", "OTEQA_HH", "CF_NFF", "r_IBA_PSLR", "r_IBL_NMFILR",
               "r_IBL_GVTLR", "prop_NFF", "CR_PS", "GCF_PSD", "OTEQL_PS")


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


@requires_cached_run
def test_manual_as_printed_leaks_through_the_dividend_row(solved):
    """As printed Σ LEND is 5.87 in 2023Q1 and grows to 72.9 by 2040Q4
    (measured 2026-11-06): the dividend allocation does not close."""
    worst = max(abs(_sum_lend(solved["manual"], t)) for t in _SIM)
    assert 50.0 < worst < 100.0
    assert _sum_lend(solved["manual"], 144) == pytest.approx(5.87, abs=0.05)


@requires_cached_run
@pytest.mark.xfail(strict=True, reason="undiagnosed §3.4 forms (UNDIAGNOSED; "
                   "chiefly the equity revaluations Eqs. (184), (240), (113)) "
                   "send the whole-model baseline 44% below the oracle's GDP")
def test_whole_model_baseline_gdp_within_1_percent(solved, base):
    p = solved["empirical"]
    assert max(abs(p[t]["GDP"] / base[t]["GDP"] - 1) for t in _SIM) < 0.01


@requires_cached_run
def test_undiagnosed_equations_carry_the_baseline_gap(base):
    """Holding the 15 undiagnosed equations at the oracle (diagnostic only):
    GDP within 2.2% of the oracle every quarter, household consumption
    within 0.1%, and Σ LEND still 0 (measured 2026-11-06)."""
    p = _solve(base, "empirical", hold=UNDIAGNOSED)
    assert max(abs(p[t]["GDP"] / base[t]["GDP"] - 1) for t in _SIM) < 0.025
    assert max(abs(p[t]["CONS_HH"] / base[t]["CONS_HH"] - 1) for t in _SIM) < 1e-3
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
    return out


@requires_cached_run
def test_gpi_never_reaches_the_economy_under_the_manual_as_printed(gpi_cum):
    """Eq. (23) has no SPEND_GVTPS term, Eq. (272) GCF_GVT is exogenous and
    Eq. (281) has no SPEND_GVTPS: the printed manual gives the green public
    investment shock no channel at all, whole model included."""
    for k in (-1.0, -0.5, 0.5, 1.0):
        assert all(gpi_cum["manual", k][v] == 0.0 for v in ("GDP", "GDP_R", "CONS_HH"))


@requires_cached_run
def test_gpi_whole_model_sign_linearity_symmetry_and_sfc(gpi_cum):
    """+100% of the GPI path (cum 91.23bn): cum nominal GDP +143.0 (1.57 per
    pound), household consumption +68.2, real GDP +27.1, government net
    lending -152.5; linear within 0.5% for nominal GDP."""
    s = {k: gpi_cum["empirical", k] for k in (-1.0, -0.5, 0.5, 1.0)}
    for v in ("GDP", "CONS_HH"):
        assert s[1.0][v] > 0
        assert s[1.0][v] / (2 * s[0.5][v]) == pytest.approx(1.0, abs=0.01)
        # Not symmetric to 7%: -1x/+1x is 1.09 (GDP) and 1.07 (CONS_HH),
        # 1.93 for real GDP, because the response sits on a baseline that
        # drifts 44% off the oracle (measured 2026-11-06).
        assert -s[-1.0][v] / s[1.0][v] == pytest.approx(1.0, abs=0.12)
    assert s[1.0]["LEND_GVT"] < 0  # the government borrows for it
    assert all(c["sfc"] < 1e-8 for c in s.values())


@requires_cached_run
@pytest.mark.xfail(strict=True, reason="multiplier on a baseline 44% off the "
                   "oracle (test_whole_model_baseline_gdp_within_1_percent)")
def test_gpi_cumulative_multiplier_matches_the_oracle_2_30(gpi_cum, base, gpi):
    d_sp = sum(g["SPEND_GVTPS"] - b["SPEND_GVTPS"] for g, b in zip(gpi[144:], base[144:]))
    assert gpi_cum["empirical", 1.0]["GDP"] / d_sp == pytest.approx(2.30, rel=0.1)
