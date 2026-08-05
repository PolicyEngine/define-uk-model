"""Gate the curated scenario surface against the cached pinned run.

Skips when no cached upstream run exists. All assertions are on DELTAS
(scenario minus the same folder's baseline) — the only outputs this repo
presents as meaningful (VALIDATION.md).

Sign-sanity notes (grounded in the cached numbers, not priors): every
policy scenario REDUCES emissions relative to baseline by 2030 and beyond.
Green public investment DEPRESSES real GDP slightly in the first years
(delta -1.125 in 2026) before turning strongly positive (+4.08 in 2030,
+7.75 in 2035) — the naive "raises GDP immediately" prior is false in the
cached run and is gated as observed. Housing regulation is contractionary
for GDP throughout (-1.6 in 2030, -2.3 in 2035) while cutting emissions.
"""

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


def test_unknown_scenario_raises():
    with pytest.raises(KeyError):
        run_scenario("not_a_scenario")


@needs_cache
@pytest.mark.parametrize("name", ALL_NAMES)
def test_deltas_finite_and_framed(name):
    r = run_scenario(name)
    assert r["result_type"] == "scenario deltas"
    assert r["delta_convention"].startswith("scenario minus baseline")
    assert any("Deltas only" in c for c in r["caveats"])
    assert any("demand-led" in c.lower() for c in r["caveats"])
    assert any("vintage" in c for c in r["caveats"])
    assert any("xperimental" in c for c in r["caveats"])
    assert r["provenance"]["upstream_commit"] == UPSTREAM_COMMIT
    assert r["years"] == list(range(2023, 2038))  # policy start + 15y
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
        base = [
            100 * l / p
            for l, p in zip(lev, pct)
            if l is not None and p not in (None, 0.0) and abs(p) > 1e-9
        ]
        per_block[r["block"]] = base
    ref = per_block.pop("gvt_investment")
    for block, base in per_block.items():
        for a, b in zip(ref, base):
            assert a == pytest.approx(b, rel=1e-6), block


def _delta(name, var, year):
    r = run_scenario(name)
    return dict(zip(r["years"], r["variables"][var]["delta_level"]))[year]


@needs_cache
def test_sign_sanity_green_public_investment():
    """GPI: early-year GDP dip, strong medium-run gain; emissions fall.

    Cached numbers: GDP_R delta -1.125 (2026), +4.075 (2030), +7.75
    (2035); EMIS delta -12.28 (2030), -13.54 (2035); unemployment delta
    negative by 2035 (-0.2195).
    """
    assert _delta("green_public_investment", "GDP_R", 2026) < 0
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
    for name in ALL_NAMES:
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
# commit 846081a (CSV precision ~4 sig figs). Any silent change to the
# cache, the delta convention, or the calendar anchoring fails here.
PINNED = [
    ("green_public_investment", "GDP_R", 2026, -1.125),
    ("green_public_investment", "GDP_R", 2030, 4.075),
    ("green_public_investment", "GDP_R", 2035, 7.75),
    ("green_public_investment", "EMIS", 2035, -13.5425),
    ("green_public_investment", "UPLOT", 2035, -0.2195),
    ("housing_regulation", "GDP_R", 2035, -2.3),
    ("housing_regulation", "EMIS", 2035, -5.375),
    ("fossil_fuel_ban", "GDP_R", 2030, -3.85),
    ("fossil_fuel_ban", "EMIS", 2035, -10.6475),
    ("mixed_both_regulations_subsidies", "EMIS", 2035, -23.0975),
    ("mixed_both_regulations_subsidies", "UPLOT", 2030, 0.141),
]


@needs_cache
@pytest.mark.parametrize("name,var,year,value", PINNED)
def test_pinned_delta_points(name, var, year, value):
    assert _delta(name, var, year) == pytest.approx(value, rel=1e-6)
