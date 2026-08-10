"""Hermetic validation gate on the committed reference artifacts.

Every numeric gate in this repo ultimately compares the cached run of the
unlicensed upstream (pinned commit) against pinned references — but the
cache cannot exist in CI (the upstream is unlicensed, so it is never
vendored, hosted, or fetched-and-run on shared infrastructure). Without
this module, ALL oracle comparisons skip in CI and a red-flag edit to the
committed artifacts, the pinned commit, or the reference numbers would
ship green.

This module is the part of the gate that runs everywhere, with no cache,
no R, no network:

1. ``validation/reference_outputs.json`` — the single source of truth for
   the pinned reference numbers — is well-formed, internally consistent,
   and pinned to the same upstream commit as ``define_uk.upstream``.
2. ``validation/baseline_vs_external.csv`` — the committed calibration
   artifact quoted by VALIDATION.md — keeps its exact schema, rows, and
   internal arithmetic (gap = model − external), and its external values
   match the pinned observations in ``define_uk.validation.EXTERNAL``.
3. The scenario registry (hermetic — a static table) matches the
   reference, and docs (README/VALIDATION.md) still name the pinned
   commit, so the pin cannot be bumped without touching the references.

The cache-gated half of the gate lives in test_replication_baseline.py,
test_scenarios.py, test_scenario_design.py and test_validation.py, which
now read their pinned values FROM the reference artifact — so a local
oracle run and CI gate the same numbers. Acceptance criteria and
tolerances are documented in VALIDATION.md ("Acceptance criteria").
"""

import csv
import json
import math
from pathlib import Path

import pytest

from define_uk import validation
from define_uk.scenarios import list_scenarios
from define_uk.upstream import UPSTREAM_COMMIT

REPO = Path(__file__).resolve().parents[1]
REFERENCE = REPO / "validation" / "reference_outputs.json"
CSV_ARTIFACT = REPO / "validation" / "baseline_vs_external.csv"


@pytest.fixture(scope="module")
def ref():
    return json.loads(REFERENCE.read_text())


# --- 1. reference_outputs.json ---------------------------------------------


def test_reference_pins_the_same_upstream_commit(ref):
    assert ref["upstream_commit"] == UPSTREAM_COMMIT


def test_reference_table4_shape_and_tolerances(ref):
    t4 = ref["table4_baseline"]
    assert set(t4["years"]) == {"2025", "2030", "2040"}
    for year, vals in t4["years"].items():
        assert len(vals) == len(t4["columns"]) == 6
        assert all(math.isfinite(v) for v in vals)
    # Tolerances documented in VALIDATION.md target 1a must be present
    # and sane (a tolerance of 0 or a huge one is a corrupted gate).
    tol = t4["tolerances"]
    assert 0 < tol["population_16plus_m"]["abs"] <= 0.05
    assert 0 < tol["labour_force_m"]["abs"] <= 0.05
    assert 0 < tol["real_gdp_growth_pct"]["abs"] <= 0.5
    assert 0 < tol["unemployment_pct"]["abs"] <= 0.5


def test_reference_emissions_divergence_ratios(ref):
    div = ref["emissions_divergence"]
    ratios = div["ratio_run_over_table4"]
    assert set(ratios) == {"2025", "2030", "2040"}
    # The recorded divergence is BELOW published and widens with horizon.
    assert 0 < ratios["2040"] < ratios["2030"] < ratios["2025"] < 1
    assert 0 < div["tolerance"]["abs"] <= 0.05


def test_reference_pinned_deltas_shape(ref):
    pts = ref["pinned_scenario_deltas"]["points"]
    assert len(pts) == 11
    names = {s["name"] for s in list_scenarios()}
    for p in pts:
        assert p["scenario"] in names
        assert p["variable"] in {"GDP_R", "EMIS", "UPLOT", "CONS_R"}
        assert isinstance(p["year"], int)
        assert math.isfinite(p["delta_level"]) and p["delta_level"] != 0
    assert 0 < ref["pinned_scenario_deltas"]["tolerance"]["rel"] <= 1e-3
    # Sign structure recorded in VALIDATION.md: every pinned EMIS delta
    # is a reduction.
    for p in pts:
        if p["variable"] == "EMIS":
            assert p["delta_level"] < 0, p


def test_reference_gpi_multiplier_is_consistent(ref):
    g = ref["gpi_multiplier"]
    # The committed multiplier must reproduce from its own committed
    # numerator/denominator (this caught the unusable upstream table).
    assert g["cum_delta_gdp"] / g["cum_delta_spend"] == pytest.approx(
        g["multiplier"], abs=g["multiplier_tolerance_abs"]
    )
    assert 0 < g["multiplier_tolerance_abs"] <= 0.05
    assert 0 < g["cum_tolerance_abs"] <= 1.0


# --- 2. baseline_vs_external.csv --------------------------------------------

EXPECTED_CSV_COLUMNS = [
    "quantity", "model", "external", "units", "gap", "verdict", "source",
]


@pytest.fixture(scope="module")
def csv_rows():
    with CSV_ARTIFACT.open() as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == EXPECTED_CSV_COLUMNS
        return list(reader)


def test_csv_rows_match_pinned_external_observations(csv_rows):
    assert [r["quantity"] for r in csv_rows] == list(validation.EXTERNAL)
    for row in csv_rows:
        ext, units, source = validation.EXTERNAL[row["quantity"]]
        assert float(row["external"]) == ext, row["quantity"]
        assert row["units"] == units, row["quantity"]
        assert row["source"] == source, row["quantity"]


def test_csv_gap_arithmetic_holds(csv_rows):
    for row in csv_rows:
        gap = float(row["model"]) - float(row["external"])
        assert float(row["gap"]) == pytest.approx(gap, abs=0.005), (
            row["quantity"]
        )


def test_csv_headline_divergences_still_recorded(csv_rows):
    """The reason the adapter is deltas-only must stay on the record: a
    silent edit shrinking the recorded baseline-vs-outturn gaps fails."""
    rows = {r["quantity"]: r for r in csv_rows}
    assert float(rows["real_gdp_growth_2025"]["gap"]) > 3.0
    assert float(rows["unemployment_2025"]["gap"]) < -0.4
    assert float(rows["emissions_2024"]["gap"]) > 25.0
    assert abs(float(rows["population_16plus_2025"]["gap"])) < 0.5


# --- 3. registry and docs stay pinned together ------------------------------


def test_scenario_registry_matches_reference(ref):
    scenarios = list_scenarios()
    assert len(scenarios) == ref["scenario_registry"]["count"]
    assert {s["block"] for s in scenarios} == set(
        ref["scenario_registry"]["blocks"]
    )


@pytest.mark.parametrize(
    "doc", ["README.md", "VALIDATION.md", "LICENSE-STATUS.md"]
)
def test_docs_name_the_pinned_commit(doc):
    text = (REPO / doc).read_text()
    assert UPSTREAM_COMMIT[:7] in text, (
        f"{doc} no longer names the pinned upstream commit; bumping the "
        "pin requires updating docs and reference_outputs.json together"
    )


def test_license_status_documents_the_position():
    text = (REPO / "LICENSE-STATUS.md").read_text()
    for needle in ("no license", "pinned", "replication"):
        assert needle in text.lower()
