"""Gate the curated scenario surface against the cached pinned run.

Skips when no cached upstream run exists. All assertions are on DELTAS
(scenario minus the same folder's baseline) — the only outputs this repo
presents as meaningful (VALIDATION.md).

Sign-sanity notes (grounded in the cached numbers, not priors): every
policy scenario REDUCES emissions relative to baseline by 2030 and beyond.
Green public investment shows real GDP strongly positive by 2030 (+4.08)
and 2035 (+7.75). The cached files also show it BELOW baseline before that
(-1.125 in 2026), but that is not the policy: no switch acts before 2027Q1
and every scenario carries the same -1.125, the effect of the Baseline's
lower alpha_PP (test_alpha_pp_confound.py). Since 2026-11-16 served paths
start at the policy start (2027); the pre-policy years are reachable only
with include_pre_policy=True and are flagged policy_active=False. Housing regulation is contractionary
for GDP throughout (-1.6 in 2030, -2.3 in 2035) while cutting emissions.
"""

import csv
import math
from pathlib import Path

import pytest

from define_uk.scenarios import (
    DEFAULT_VARIABLES,
    list_scenarios,
    run_scenario,
)
from define_uk.upstream import UPSTREAM_COMMIT, cache_dir

_HAS_CACHE = (
    Path(cache_dir()) / UPSTREAM_COMMIT / "output/tables"
).is_dir()

needs_cache = pytest.mark.skipif(
    not _HAS_CACHE, reason="no cached upstream run (define_uk.runner.run)"
)

ALL_NAMES = [s["name"] for s in list_scenarios()]
# Cached solves that break stock-flow consistency; run_scenario refuses them
# (tests/test_scenario_sweep.py). Every other registered scenario is served.
REFUSED = {
    "fossil_fuel_ban__no_forward_guidance",
    "fossil_fuel_ban__unexpected_enforcement",
}
SERVED = [n for n in ALL_NAMES if n not in REFUSED]


def test_registry_shape():
    assert len(ALL_NAMES) == 22
    assert len(set(ALL_NAMES)) == 22
    blocks = {s["block"] for s in list_scenarios()}
    assert blocks == {
        "gvt_investment",
        "housing_regulation",
        "power_sector_regulation",
        "mixed",
    }
    for s in list_scenarios():
        assert s["description"]


def test_identical_scenarios_are_declared():
    """Six registered names are the same cached solve as another name
    (docs/scenario-notes.md). Hermetic: the mapping is well-formed and the
    descriptions say so; tests/test_scenario_sweep.py checks it against the
    cached files."""
    from define_uk.scenarios import EXPECTATION_REGIMES, IDENTICAL_TO

    listed = {s["name"]: s for s in list_scenarios()}
    assert len(IDENTICAL_TO) == 6
    for name, other in IDENTICAL_TO.items():
        assert name in listed and other in listed
        assert other not in IDENTICAL_TO  # points at a solve of its own
        assert listed[name]["identical_to"] == other
        assert other in listed[name]["description"]
    assert sum(s["identical_to"] is None for s in listed.values()) == 16
    # The subsidy-only scenario has no regime of its own in the cached run.
    subsidy = [n for n in IDENTICAL_TO if n.startswith("power_sector_subsidy__")]
    assert len(subsidy) == 4
    assert set(EXPECTATION_REGIMES) == {
        "mutual_trust", "poor_credibility", "false_confidence",
        "no_forward_guidance", "unexpected_enforcement",
    }


def test_unknown_scenario_raises():
    with pytest.raises(KeyError):
        run_scenario("not_a_scenario")


@needs_cache
@pytest.mark.parametrize("name", SERVED)
def test_deltas_finite_and_framed(name):
    r = run_scenario(name)
    assert r["result_type"] == "scenario deltas"
    assert r["delta_convention"].startswith("scenario minus baseline")
    assert any("Deltas only" in c for c in r["caveats"])
    assert any("demand-led" in c.lower() for c in r["caveats"])
    assert any("vintage" in c for c in r["caveats"])
    assert any("xperimental" in c for c in r["caveats"])
    assert r["provenance"]["upstream_commit"] == UPSTREAM_COMMIT
    # Policy start (2027Q1, read from the cache) to the end of the run.
    assert r["years"] == list(range(2027, 2041))
    assert r["policy_start_year"] == 2027
    assert all(r["policy_active"])
    assert r["baseline_parameter_mismatch"]["parameter"] == "alpha_PPLR"
    for var in DEFAULT_VARIABLES:
        block = r["variables"][var]
        assert len(block["delta_level"]) == len(r["years"])
        for v in block["delta_level"] + block["delta_pct"]:
            assert v is None or math.isfinite(v)
        # A scenario must actually depart from baseline somewhere.
    assert any(
        v not in (None, 0.0)
        for v in r["variables"]["GDP_R"]["delta_level"]
    )


@needs_cache
def test_baseline_consistent_across_blocks():
    """Every block folder's Variables_Baseline.csv is the SAME baseline.

    Implied level = delta_level / (delta_pct/100) recovers each folder's
    baseline annual mean; compare it across one scenario per block.
    """
    per_block = {}
    for name in (
        "green_public_investment",
        "housing_regulation",
        "fossil_fuel_ban",
        "mixed_both_regulations_subsidies",
    ):
        r = run_scenario(name)
        lev = r["variables"]["GDP_R"]["delta_level"]
        pct = r["variables"]["GDP_R"]["delta_pct"]
        # Keyed by year: a year where the delta is ~0 cannot recover the
        # level and is skipped, so positions differ across blocks.
        base = {
            y: 100 * l / p
            for y, l, p in zip(r["years"], lev, pct)
            if l is not None and p not in (None, 0.0) and abs(p) > 1e-9
        }
        per_block[r["block"]] = base
    ref = per_block.pop("gvt_investment")
    for block, base in per_block.items():
        common = set(ref) & set(base)
        assert len(common) >= 10, block
        for y in common:
            assert ref[y] == pytest.approx(base[y], rel=1e-6), (block, y)


def _delta(name, var, year):
    # include_pre_policy: the pinned points reproduce the cached run,
    # including one pre-policy year (2026).
    r = run_scenario(name, include_pre_policy=True)
    return dict(zip(r["years"], r["variables"][var]["delta_level"]))[year]


@needs_cache
def test_sign_sanity_green_public_investment():
    """GPI: strong medium-run GDP gain; emissions fall.

    Cached numbers: GDP_R delta +4.075 (2030), +7.75 (2035); EMIS delta
    -12.28 (2030), -13.54 (2035); unemployment delta negative by 2035
    (-0.2195). The 2026 GDP dip (-1.125) is the alpha_PP mismatch, not the
    policy, so it is not a sign-sanity claim: it is outside the default
    path and flagged policy_active=False.
    """
    pre = run_scenario("green_public_investment", include_pre_policy=True)
    flags = dict(zip(pre["years"], pre["policy_active"]))
    assert flags[2026] is False and flags[2027] is True
    assert 2026 not in run_scenario("green_public_investment")["years"]
    assert _delta("green_public_investment", "GDP_R", 2030) > 0
    assert _delta("green_public_investment", "GDP_R", 2035) > 0
    assert _delta("green_public_investment", "EMIS", 2030) < 0
    assert _delta("green_public_investment", "EMIS", 2035) < 0
    assert _delta("green_public_investment", "UPLOT", 2035) < 0


@needs_cache
def test_sign_sanity_housing_regulation():
    """Housing regulation: contractionary for GDP, emissions-reducing.

    Cached numbers: GDP_R delta -1.625 (2030), -2.3 (2035); EMIS delta
    -1.68 (2030), -5.375 (2035); unemployment delta positive throughout.
    """
    for year in (2028, 2030, 2035):
        assert _delta("housing_regulation", "GDP_R", year) < 0
        assert _delta("housing_regulation", "UPLOT", year) > 0
    assert _delta("housing_regulation", "EMIS", 2030) < 0
    assert _delta("housing_regulation", "EMIS", 2035) < 0
    # Adding the subsidy cuts emissions further than regulation alone.
    assert _delta("housing_regulation_subsidy", "EMIS", 2035) < _delta(
        "housing_regulation", "EMIS", 2035
    )


@needs_cache
def test_sign_sanity_emissions_fall_everywhere_by_2035():
    for name in SERVED:
        assert _delta(name, "EMIS", 2035) < 0, name


@needs_cache
def test_mixed_policy_cuts_most_emissions():
    """The combined-policy scenario dominates single policies on EMIS at
    2035 (cached: -23.10 vs -13.54 GPI, -10.65 ffb, -10.14 housing+sub)."""
    mixed = _delta("mixed_both_regulations_subsidies", "EMIS", 2035)
    for other in (
        "green_public_investment",
        "fossil_fuel_ban",
        "housing_regulation_subsidy",
    ):
        assert mixed < _delta(other, "EMIS", 2035)


# Pinned oracle values: exact annual-mean deltas from the cached run at
# commit 846081a (CSV precision ~4 sig figs), committed as the reference
# artifact validation/reference_outputs.json (single source of truth,
# hermetically gated by tests/test_committed_artifacts.py). Any silent
# change to the cache, the delta convention, or the calendar anchoring
# fails here.
import json

_REF = json.loads(
    (Path(__file__).resolve().parents[1] / "validation"
     / "reference_outputs.json").read_text()
)
PINNED = [
    (p["scenario"], p["variable"], p["year"], p["delta_level"])
    for p in _REF["pinned_scenario_deltas"]["points"]
]
_PINNED_RTOL = _REF["pinned_scenario_deltas"]["tolerance"]["rel"]


@needs_cache
@pytest.mark.parametrize("name,var,year,value", PINNED)
def test_pinned_delta_points(name, var, year, value):
    assert _delta(name, var, year) == pytest.approx(value, rel=_PINNED_RTOL)


def test_every_default_variable_states_its_units():
    """Hermetic: delta_level is an annual mean of QUARTERLY values, so an
    EMIS level read as MtCO2e/yr is wrong by a factor of 4 unless the
    result says so."""
    from define_uk import scenarios
    for var in scenarios.DEFAULT_VARIABLES:
        assert var in scenarios.VARIABLE_UNITS, var
    assert "by 4" in scenarios.VARIABLE_UNITS["EMIS"]
    assert "percentage points" in scenarios.VARIABLE_UNITS["UPLOT"]


@needs_cache
def test_policy_start_is_read_from_the_cache_and_starts_a_year():
    """The policy start is the first quarter the cached policy files stop
    being identical: 2027Q1, the first quarter of its year, so no served
    year mixes pre-policy and policy quarters."""
    from define_uk import scenarios
    root = str(scenarios._run_root())
    assert scenarios._policy_start_year(root) == 2027
    paths = {
        scenarios._run_root() / scenarios._TABLES / folder / f"Variables_{label}.csv"
        for _, _, folder, label, _ in scenarios._REGISTRY
    }
    rows = [list(csv.reader(p.open()))[1:] for p in sorted(paths)]
    t = next(t for t in range(216) if len({tuple(r[t]) for r in rows}) > 1)
    assert t % 4 == 0 and scenarios.START_YEAR + t // 4 == 2027


@needs_cache
@pytest.mark.parametrize("name", SERVED)
def test_pre_policy_years_are_opt_in_and_flagged(name):
    full = run_scenario(name, include_pre_policy=True, horizon_years=18)
    served = run_scenario(name)
    assert full["years"][0] == 2023
    assert [y for y, a in zip(full["years"], full["policy_active"]) if not a] \
        == [2023, 2024, 2025, 2026]
    # The served path is the policy-active tail of the full one, value for value.
    tail = dict(zip(full["years"], full["variables"]["GDP_R"]["delta_level"]))
    assert served["variables"]["GDP_R"]["delta_level"] == [
        tail[y] for y in served["years"]]



@needs_cache
def test_capacity_constrained_years_are_flagged():
    """Generation at the capacity ceiling (the regime that breaks stock-flow
    consistency in the two refused solves) is flagged per year and in a
    leading caveat; green public investment never reaches it."""
    r = run_scenario("fossil_fuel_ban_subsidy__no_forward_guidance")
    flagged = [y for y, c in zip(r["years"], r["capacity_constrained"]) if c]
    assert flagged == [2032]
    assert r["caveats"][0].startswith("Capacity-constrained years")
    gdp = dict(zip(r["years"], r["variables"]["GDP_R"]["delta_pct"]))
    assert gdp[2032] < -5  # the crash the 2030/2035 snapshots hide
    g = run_scenario("green_public_investment")
    assert not any(g["capacity_constrained"])


@needs_cache
def test_every_subsidy_scenario_lowers_real_gdp_cumulatively():
    """Pins the served 'Subsidies lower real GDP' caveat (2027-2040 sums of
    the quarterly GDP_R delta, cached run)."""
    from define_uk import scenarios as sc

    base = sc._read_column(
        sc._run_root() / sc._TABLES / "gvt_investment" / "Variables_Baseline.csv",
        "GDP_R")

    def cum(name):
        _, _, folder, label, _ = sc._BY_NAME[name]
        s = sc._read_column(
            sc._run_root() / sc._TABLES / folder / f"Variables_{label}.csv", "GDP_R")
        return sum(s[t] - base[t] for t in range(160, 216))

    for name in sc._BY_NAME:
        if "subsid" in name:
            assert cum(name) < 0, name
    assert cum("green_power_subsidy") == pytest.approx(-47.3, abs=0.5)
    assert cum("green_public_investment") == pytest.approx(252.2, abs=0.5)
    assert cum("housing_regulation_subsidy") < cum("housing_regulation") < 0
