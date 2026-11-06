"""Scenario sweep over every cached solve: accounting, zero shock, units.

Runs on the cached pinned run (skips in CI, where no cache can exist). Each
check runs on all 30 ``Variables_*.csv`` files (22 scenarios plus the
baseline repeated in each block folder), not on one example.

- Stock-flow consistency: the redundant equation (LEND, the sum of sectoral
  net lending) is zero in every quarter, and the seven sectoral balances add
  up to it. Two solves break it; they are pinned and ``run_scenario``
  refuses them.
- Stocks equal cumulated flows: public green power capital accumulates the
  public green power spending, with depreciation, quarter by quarter.
- Zero shock = baseline: every scenario equals its baseline exactly before
  the policies start (2023Q1), except the mark-up MU in 2022Q4 (pinned),
  and every block's baseline is the same file.
- Invariance the run design implies: a scenario that the credibility cases
  do not touch is identical in every case folder, and the mixed block reuses
  the single-policy solves exactly.
- Economics: weaker credibility cuts fewer emissions; on- vs off-balance-
  sheet green power spending moves GDP in opposite directions, and the
  fiscal offset explains why.
- Units: EMIS is MtCO2e per quarter (x4 is a UK-sized annual total).

The upstream R environment is not installed on the review machine, so the
sweep covers the scenarios the pinned run ships; it does not vary policy
sizes (that needs a re-run of the R code).
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import pytest

from define_uk.scenarios import (
    _TABLES,
    START_YEAR,
    StockFlowInconsistent,
    _run_root,
    run_scenario,
    sfc_check,
)

REFERENCE = json.loads(
    (Path(__file__).resolve().parents[1] / "validation"
     / "reference_outputs.json").read_text()
)["stock_flow_consistency"]
SIM_START = 144  # 2023Q1
SECTORS = ("LEND_HH", "LEND_NFC", "LEND_MFI", "LEND_NMFI", "LEND_GVT",
           "LEND_RoW", "LEND_PS")
CRED_CASES = ("mutual_trust", "poor_credibility", "false_confidence",
              "no_forward_guidance", "unexpected_enforcement")


def _root() -> Path | None:
    try:
        return _run_root() / _TABLES
    except FileNotFoundError:
        return None


ROOT = _root()
needs_cache = pytest.mark.skipif(ROOT is None, reason="no cached DEFINE-UK run")
FILES = sorted(
    str(p.relative_to(ROOT)) for p in ROOT.rglob("Variables_*.csv")
) if ROOT else []


def _load(rel: str) -> dict[str, list[float]]:
    with (ROOT / rel).open() as fh:
        rows = list(csv.DictReader(fh))
    return {
        k: [float(r[k]) if r[k] not in ("", "NA") else math.nan for r in rows]
        for k in rows[0] if k
    }


def _key(rel: str) -> str:
    return rel.removesuffix(".csv").replace("Variables_", "")


def _sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


@needs_cache
def test_the_sweep_covers_every_cached_file():
    assert len(FILES) == 30


@needs_cache
def test_redundant_equation_holds_except_the_pinned_solves():
    failures = {
        _key(rel): c["failing_quarters"]
        for rel in FILES
        if not (c := sfc_check(ROOT / rel, REFERENCE["tolerance_abs"]))["passed"]
    }
    assert failures == REFERENCE["known_failures"]


@needs_cache
@pytest.mark.parametrize("rel", FILES)
def test_sectoral_balances_sum_to_the_redundant_equation(rel):
    """Each column is printed to 4 significant figures, so the allowed gap
    in a quarter is the sum of the printing errors of its eight terms (half
    a unit in the 4th figure each), plus the pinned absolute floor."""
    d = _load(rel)

    def half_ulp(x: float) -> float:
        return 0.0 if x == 0 else 0.5 * 10 ** (math.floor(math.log10(abs(x))) - 3)

    floor = REFERENCE["sectoral_sum_tolerance_abs"]
    for t in range(SIM_START, len(d["LEND"])):
        terms = [d[s][t] for s in SECTORS]
        gap = abs(sum(terms) - d["LEND"][t])
        bound = sum(half_ulp(x) for x in terms + [d["LEND"][t]])
        assert gap <= bound + floor, (rel, t, gap, bound)


@needs_cache
@pytest.mark.parametrize("name", [
    "fossil_fuel_ban__no_forward_guidance",
    "fossil_fuel_ban__unexpected_enforcement",
])
def test_inconsistent_solves_are_refused(name):
    with pytest.raises(StockFlowInconsistent):
        run_scenario(name)
    r = run_scenario(name, allow_inconsistent=True)
    assert not r["sfc_check"]["scenario"]["passed"]
    assert r["caveats"][0].startswith("NOT STOCK-FLOW CONSISTENT")


@needs_cache
def test_served_results_carry_a_passed_check():
    r = run_scenario("green_public_investment")
    assert r["sfc_check"]["scenario"]["passed"]
    assert r["sfc_check"]["baseline"]["passed"]


@needs_cache
def test_public_green_capital_is_cumulated_public_green_spending():
    """K_GVTNFFR[t] = (1 - delta_KPSNFF) K_GVTNFFR[t-1] + SPEND_GVTPS/P_P
    when green power investment is on the government balance sheet (GPI),
    and stays at zero when the same spending is a subsidy."""
    gpi = _load("gvt_investment/Variables_GPI + Green Bonds.csv")
    worst = 0.0
    for t in range(SIM_START, len(gpi["K_GVTNFFR"])):
        implied = ((1 - gpi["delta_KPSNFF"][t]) * gpi["K_GVTNFFR"][t - 1]
                   + gpi["SPEND_GVTPS"][t] / gpi["P_P"][t])
        worst = max(worst,
                    abs(implied - gpi["K_GVTNFFR"][t])
                    / max(abs(gpi["K_GVTNFFR"][t]), 1.0))
    assert worst < 2e-3
    assert max(gpi["K_GVTNFFR"]) > 50  # the stock is built, not trivially 0

    sub = _load("gvt_investment/Variables_Green Power Subsidy.csv")
    assert max(abs(v) for v in sub["K_GVTNFFR"] if not math.isnan(v)) == 0


@needs_cache
def test_every_block_baseline_is_the_same_file():
    shas = {_sha(rel) for rel in FILES if rel.endswith("Variables_Baseline.csv")}
    assert len(shas) == 1


@needs_cache
@pytest.mark.parametrize(
    "rel", [f for f in FILES if not f.endswith("Variables_Baseline.csv")]
)
def test_zero_shock_before_the_policies_start(rel):
    """Every column equals the baseline in every quarter before 2023Q1, and
    the scenario departs from baseline in 2023Q1 itself."""
    scen = _load(rel)
    base = _load(str(Path(rel).parent / "Variables_Baseline.csv"))

    def same(a, b):
        return (math.isnan(a) and math.isnan(b)) or a == b

    pre = {(k, t) for k in base for t in range(SIM_START)
           if not same(scen[k][t], base[k][t])}
    # One pinned exception: the mark-up MU in the last history quarter
    # (2022Q4, row 143), which seeds the first simulated P_P. The scenario
    # switches change it (baseline 0.176, GPI 0.1704); nothing else in the
    # history moves.
    assert pre <= {("MU", SIM_START - 1)}
    assert any(not same(scen[k][SIM_START], base[k][SIM_START])
               for k in ("GDP", "SPEND_GVT", "EMIS"))
    assert START_YEAR + SIM_START // 4 == 2023


@needs_cache
def test_credibility_insensitive_scenario_is_identical_in_every_case():
    shas = {
        _sha(f"power_sector_regulation/{c}/Variables_Power Sector Subsidy.csv")
        for c in CRED_CASES
    }
    assert len(shas) == 1


@needs_cache
@pytest.mark.parametrize("label", ["Fossil Fuel Ban", "Fossil Fuel Ban + Subsidy"])
def test_credibility_sensitive_scenarios_differ_by_case(label):
    shas = {
        _sha(f"power_sector_regulation/{c}/Variables_{label}.csv")
        for c in CRED_CASES
    }
    assert len(shas) == len(CRED_CASES)


@needs_cache
def test_mixed_block_reuses_the_single_policy_solves():
    assert (_sha("mixed/mutual_trust/Variables_Housing Regulation + Subsidy.csv")
            == _sha("housing_regulation/Variables_Housing Regulation + Subsidy.csv"))
    assert (_sha("mixed/mutual_trust/Variables_Fossil Fuel Ban + Subsidy.csv")
            == _sha("power_sector_regulation/mutual_trust/"
                    "Variables_Fossil Fuel Ban + Subsidy.csv"))


def _at(name: str, var: str, year: int) -> float:
    r = run_scenario(name)
    return dict(zip(r["years"], r["variables"][var]["delta_level"]))[year]


@needs_cache
@pytest.mark.parametrize("policy", ["fossil_fuel_ban", "fossil_fuel_ban_subsidy"])
def test_poor_credibility_cuts_fewer_emissions(policy):
    """Cached 2035 EMIS deltas (MtCO2e per quarter): ban -10.65 under mutual
    trust vs -6.88 under poor credibility; ban + subsidy -12.85 vs -10.95."""
    assert _at(policy, "EMIS", 2035) < _at(f"{policy}__poor_credibility",
                                            "EMIS", 2035) < 0


@needs_cache
def test_on_and_off_balance_sheet_green_power_move_gdp_opposite_ways():
    """Same green power capacity (GREEN_POWER = 1), two financing designs.

    Cumulative over the simulation (nominal unless noted), cached run:
    GPI + Green Bonds: SPEND_GVTPS +91.2, CONS_GVT +39.8, GDP +209.9,
    GDP_R +250.6. Green Power Subsidy: SPEND_GVTPS +110.8 but CONS_GVT
    -49.1 and SOCB_GVT -27.7, GDP -248.1, GDP_R -48.9. The subsidy is not
    counted in GCF, and other government spending falls, so the subsidy
    design is contractionary in this model.
    """
    def cum(rel, var):
        s = _load(f"gvt_investment/Variables_{rel}.csv")[var]
        b = _load("gvt_investment/Variables_Baseline.csv")[var]
        return sum(x - y for x, y in zip(s, b)
                   if not (math.isnan(x) or math.isnan(y)))

    assert cum("GPI + Green Bonds", "GDP_R") == pytest.approx(250.6, abs=0.5)
    assert cum("Green Power Subsidy", "GDP_R") == pytest.approx(-48.9, abs=0.5)
    assert cum("Green Power Subsidy", "SPEND_GVTPS") > cum(
        "GPI + Green Bonds", "SPEND_GVTPS") > 0
    assert cum("Green Power Subsidy", "CONS_GVT") < 0 < cum(
        "GPI + Green Bonds", "CONS_GVT")


@needs_cache
def test_emissions_are_per_quarter():
    """4 x the 1990 annual mean of EMIS is a UK-sized annual total (the UK's
    1990 base-year territorial emissions are of the order of 800 MtCO2e);
    reading EMIS as per-year would put 1990 at about 200 MtCO2e."""
    emis = _load("gvt_investment/Variables_Baseline.csv")["EMIS"]
    i = (1990 - START_YEAR) * 4
    annual_mean = sum(emis[i:i + 4]) / 4
    assert 700 < 4 * annual_mean < 900
    assert 150 < annual_mean < 250
