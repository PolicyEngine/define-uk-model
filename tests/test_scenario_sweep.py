"""Scenario sweep over every cached solve: accounting, zero shock, units.

Runs on the cached pinned run (skips in CI, where no cache can exist). Each
check runs on all 30 ``Variables_*.csv`` files (22 scenarios plus the
baseline repeated in each block folder), not on one example.

- Stock-flow consistency: the redundant equation (LEND, the sum of sectoral
  net lending) is zero in every quarter, and the seven sectoral balances add
  up to it. Two solves break it; they are pinned and ``run_scenario``
  refuses them. Every break is one missing flow: GO_PS valued at P_ELECLR
  while buyers pay P_ELEC (manual Eq. (74)), in the price-regime quarters.
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
def test_every_break_is_the_power_sector_valuation_gap():
    """The cause of the two refused solves, pinned (2026-11-06).

    In each failing quarter, and in no other simulation quarter of any of
    the 30 files, GO_PS != GO_PSR * P_ELEC (manual Eq. (74)): the seller's
    revenue is valued at P_ELECLR while buyers pay P_ELEC. LEND is the same
    fraction (-0.61) of that gap in all three quarters, so the gap accounts
    for the whole break.
    """
    breaks = {}
    for rel in FILES:
        d = _load(rel)
        for t in range(SIM_START, len(d["LEND"])):
            gap = d["GO_PSR"][t] * d["P_ELEC"][t] - d["GO_PS"][t]
            if abs(gap) > 0.01 * max(1.0, abs(d["GO_PS"][t])):
                breaks[(_key(rel), f"{1987 + t // 4}Q{t % 4 + 1}")] = (
                    gap, d["LEND"][t], d["GO_PS"][t] / d["GO_PSR"][t],
                    d["P_ELECLR"][t],
                )
    assert {(k, q) for k, qs in REFERENCE["known_failures"].items()
            for q in qs} == set(breaks)
    for gap, lend, price, p_lr in breaks.values():
        assert lend / gap == pytest.approx(-0.608, abs=0.005)
        assert price == pytest.approx(p_lr, rel=2e-3)


@needs_cache
def test_sfc_check_reports_the_valuation_gap():
    rel = "power_sector_regulation/no_forward_guidance/Variables_Fossil Fuel Ban.csv"
    gap = sfc_check(ROOT / rel)["electricity_valuation_gap"]
    assert gap == {"2035Q3": pytest.approx(122.54, abs=0.05),
                   "2036Q1": pytest.approx(81.79, abs=0.05)}
    ok = "gvt_investment/Variables_Baseline.csv"
    assert sfc_check(ROOT / ok)["electricity_valuation_gap"] == {}


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


# --- Duplicate solves and the expectation regimes (docs/scenario-notes.md) ---


def _param_row(folder: str, label: str) -> dict[str, str]:
    with (ROOT / folder / f"Parameters-sorted_{label}.csv").open() as fh:
        row = next(csv.DictReader(fh))
    return {k.strip(): v.strip() for k, v in row.items() if k and k.strip()}


@needs_cache
def test_identical_to_matches_the_cached_files_exactly():
    """Two registered names share a solve if and only if IDENTICAL_TO says
    so: byte-identical Variables files and equal parameter rows. 22 names,
    16 distinct solves."""
    from define_uk.scenarios import _REGISTRY, IDENTICAL_TO

    where = {name: (folder, label) for name, _, folder, label, _ in _REGISTRY}
    sha = {n: _sha(f"{f}/Variables_{lab}.csv") for n, (f, lab) in where.items()}
    assert len(set(sha.values())) == 16
    by_file = {
        frozenset(n for n in where if sha[n] == h) for h in set(sha.values())
    }
    declared = {
        frozenset({n, *(d for d, o in IDENTICAL_TO.items() if o == n)})
        for n in where if n not in IDENTICAL_TO
    }
    assert by_file == declared
    for name, other in IDENTICAL_TO.items():
        assert _param_row(*where[name]) == _param_row(*where[other]), name


@needs_cache
def test_expectation_regimes_are_the_cached_parameter_sets():
    """Each regime folder's two ban scenarios carry exactly the regime's
    CRED / GVT_CRED / ELEC_BUFFER; the subsidy-only scenario carries the
    Baseline's values (mutual trust) in every folder, which is why it is one
    solve under five labels."""
    from define_uk.scenarios import EXPECTATION_REGIMES

    for case, want in EXPECTATION_REGIMES.items():
        folder = f"power_sector_regulation/{case}"
        for label in ("Fossil Fuel Ban", "Fossil Fuel Ban + Subsidy"):
            row = _param_row(folder, label)
            assert {k: float(row[k]) for k in want} == want, (case, label)
        for label in ("Power Sector Subsidy", "Baseline"):
            row = _param_row(folder, label)
            assert {k: float(row[k]) for k in want} == \
                EXPECTATION_REGIMES["mutual_trust"], (case, label)


@needs_cache
@pytest.mark.parametrize("label", ["Fossil Fuel Ban", "Fossil Fuel Ban + Subsidy"])
def test_fossil_capital_is_struck_out_exactly_where_gvt_cred_is_one(label):
    """What GVT_CRED does, read from the outputs: fossil generation capital
    K_PSFFR is positive in 2031Q4 in every case and exactly zero from 2032Q1
    (FF_CAP_BAN = 181) where GVT_CRED = 1; where GVT_CRED = 0 it is kept."""
    from define_uk.scenarios import EXPECTATION_REGIMES

    t_ban = 180  # 2032Q1, quarter 181 counted from 1987Q1
    for case, regime in EXPECTATION_REGIMES.items():
        k = _load(f"power_sector_regulation/{case}/Variables_{label}.csv")["K_PSFFR"]
        assert k[t_ban - 1] > 30, case
        if regime["GVT_CRED"] == 1:
            assert all(v == 0 for v in k[t_ban:]), case
        else:
            assert all(v > 0 for v in k[t_ban:]), case


@needs_cache
def test_false_confidence_gap_is_the_2032_capacity_shortfall():
    """Why the ban cuts 18.5 MtCO2e more under false confidence than under
    mutual trust (-417.0 against -398.5, 2027-2040), from the cached files.

    The two runs differ only in GVT_CRED and are identical through 2031Q4.
    Under mutual trust the fossil capital is struck out in 2032Q1, capacity
    falls below demand for two quarters, the electricity price is 1.4x and
    2.0x the false-confidence price in 2032Q2-Q3, the green share of NFC
    investment (manual Eq. (168)) dips, and green production capital stays
    behind for the rest of the run. Energy intensity, the electricity share
    and the non-electric emission intensity are functions of that capital
    (Eqs. (16), (18), (19)), so the whole gap is non-electric emissions.
    The ban + subsidy pair is the control: no shortfall, no gap."""
    ban = "power_sector_regulation/{}/Variables_Fossil Fuel Ban.csv"
    mt, fc = _load(ban.format("mutual_trust")), _load(ban.format("false_confidence"))
    t0, t1, n = 160, 180, len(mt["EMIS"])  # 2027Q1, 2032Q1

    def same(a: float, b: float) -> bool:
        return a == b or (math.isnan(a) and math.isnan(b))

    assert all(same(mt[k][t], fc[k][t]) for k in mt for t in range(t1))

    def gap(var: str, a: int = t0, b: int | None = None) -> float:
        return sum(fc[var][t] - mt[var][t] for t in range(a, b or n))

    assert gap("EMIS") == pytest.approx(-18.48, abs=0.05)
    assert gap("EMIS_NELEC") == pytest.approx(-18.51, abs=0.05)
    assert abs(gap("EMIS_ELEC")) < 0.05

    def ceiling(d: dict) -> list[int]:
        return [t for t in range(t0, n) if d["E_ELEC"][t] >= 0.999 * d["E_ELECMAX"][t]]

    assert ceiling(mt) == [180, 181] and ceiling(fc) == []  # 2032Q1-Q2
    assert mt["E_ELECMAX"][180] < mt["E_ELECD"][180] < fc["E_ELECMAX"][180]
    ratio = [mt["P_ELEC"][t] / fc["P_ELEC"][t] for t in (181, 182)]
    assert ratio == pytest.approx([1.39, 2.00], abs=0.01)
    assert [mt["beta_nfc"][t] for t in (181, 182)] == pytest.approx(
        [0.0751, 0.0616], abs=1e-4)
    assert [fc["beta_nfc"][t] for t in (181, 182)] == pytest.approx(
        [0.0858, 0.0859], abs=1e-4)
    # Green production capital: 4.0 behind at 2032Q4, still 1.5 behind in
    # 2040Q4; energy intensity above the false-confidence run throughout.
    assert fc["K_PGR"][183] - mt["K_PGR"][183] == pytest.approx(4.0, abs=0.1)
    assert fc["K_PGR"][n - 1] - mt["K_PGR"][n - 1] == pytest.approx(1.5, abs=0.1)
    assert all(mt["epsilon"][t] > fc["epsilon"][t] for t in range(183, n))
    assert all(mt["omega_NELEC"][t] > fc["omega_NELEC"][t] for t in range(183, n))
    assert all(mt["theta_P"][t] < fc["theta_P"][t] for t in range(183, n))
    # Not an output effect: cumulative real GDP differs by 6 (GBP bn,
    # quarterly flows summed) on quarterly flows of about 800-950.
    assert abs(gap("GDP_R", t1)) < 10

    # Control: with the subsidy there is no shortfall under mutual trust and
    # the emissions gap is within CSV rounding.
    both = "power_sector_regulation/{}/Variables_Fossil Fuel Ban + Subsidy.csv"
    mt2, fc2 = _load(both.format("mutual_trust")), _load(both.format("false_confidence"))
    assert ceiling(mt2) == [] and ceiling(fc2) == []
    assert abs(sum(fc2["EMIS"][t] - mt2["EMIS"][t] for t in range(t0, n))) < 0.1


@needs_cache
def test_cross_regime_figures_in_the_notes():
    """The by-regime figures in docs/scenario-notes.md that the false-
    confidence test above does not cover (review of 2026-11-18): cumulative
    emissions cuts 2027-2040 by regime, non-fossil capital at 2031Q4,
    maximum generation at 2032Q1, quarters at the capacity ceiling, and the
    non-fossil generation share in 2033Q4 and 2036Q4. The two ban-alone
    solves under no forward guidance and unexpected enforcement are refused
    by run_scenario; their figures are read from the files directly."""
    t0, t_ban = 160, 180  # 2027Q1, 2032Q1
    want = {
        # case: (ban cum EMIS, EMIS_ELEC, EMIS_NELEC, ban + subsidy cum EMIS,
        #        K_PSNFFR 2031Q4, E_ELECMAX 2032Q1, quarters at the ceiling,
        #        beta_NFF 2033Q4)
        "mutual_trust": (-398.5, -118.7, -279.8, -517.7, 127.7, 78.1, 2, 0.975),
        "false_confidence": (-417.0, -118.7, -298.3, -517.8, 127.7, 128.3, 0, 0.975),
        "poor_credibility": (-217.9, -67.8, -150.1, -397.9, 110.9, 129.1, 0, 0.936),
        "no_forward_guidance": (-121.3, -65.5, -55.6, -243.7, 100.3, 64.1, 31, 0.975),
        "unexpected_enforcement": (-183.5, -77.8, -105.7, -381.6, 109.5, 72.0, 4, 0.967),
    }
    base = _load("power_sector_regulation/mutual_trust/Variables_Baseline.csv")
    for case, (emis, elec, nelec, emis_sub, knff, emax, n_ceil, share) in want.items():
        ban = _load(f"power_sector_regulation/{case}/Variables_Fossil Fuel Ban.csv")
        sub = _load(f"power_sector_regulation/{case}/"
                    "Variables_Fossil Fuel Ban + Subsidy.csv")

        def cum(d, var):
            return sum(d[var][t] - base[var][t] for t in range(t0, len(base[var])))

        assert cum(ban, "EMIS") == pytest.approx(emis, abs=0.06), case
        assert cum(ban, "EMIS_ELEC") == pytest.approx(elec, abs=0.06), case
        assert cum(ban, "EMIS_NELEC") == pytest.approx(nelec, abs=0.06), case
        assert cum(sub, "EMIS") == pytest.approx(emis_sub, abs=0.06), case
        assert ban["K_PSNFFR"][t_ban - 1] == pytest.approx(knff, abs=0.06), case
        assert ban["E_ELECMAX"][t_ban] == pytest.approx(emax, abs=0.06), case
        ceil = [t for t in range(t0, len(ban["E_ELEC"]))
                if ban["E_ELEC"][t] >= 0.999 * ban["E_ELECMAX"][t]]
        assert len(ceil) == n_ceil, case
        assert ban["beta_NFF"][187] == pytest.approx(share, abs=6e-4), case
        assert ban["beta_NFF"][199] == pytest.approx(0.975, abs=6e-4), case
    # Unexpected enforcement's nonzero ELEC_BUFFER is the only regime
    # parameter the notes do not explain; it is the only one not zero.
    from define_uk.scenarios import EXPECTATION_REGIMES
    assert [c for c, r in EXPECTATION_REGIMES.items() if r["ELEC_BUFFER"]] == [
        "unexpected_enforcement"]


@needs_cache
def test_capacity_ceiling_years_by_scenario():
    """Which registered scenarios reach the capacity ceiling, and when: three
    served ones, all in 2032, and the two refused solves (one to 2039)."""
    from define_uk.scenarios import _BY_NAME, _capacity_years

    years = {
        name: sorted(y for y in _capacity_years(
            ROOT / folder / f"Variables_{label}.csv") if y >= 2027)
        for name, (_, _, folder, label, _) in _BY_NAME.items()
    }
    assert {n: y for n, y in years.items() if y} == {
        "fossil_fuel_ban": [2032],
        "fossil_fuel_ban_subsidy__no_forward_guidance": [2032],
        "fossil_fuel_ban_subsidy__unexpected_enforcement": [2032],
        "fossil_fuel_ban__no_forward_guidance": list(range(2032, 2040)),
        "fossil_fuel_ban__unexpected_enforcement": [2032],
    }


def _at(name: str, var: str, year: int) -> float:
    r = run_scenario(name, include_pre_policy=True)
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
