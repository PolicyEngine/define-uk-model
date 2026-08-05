"""Calibration comparators are computed, committed, and pinned.

Recomputing from the cached pinned run must match the committed artifact
exactly — calibration drift (a changed cache, a changed computation) fails
here instead of silently aging in VALIDATION.md prose.
"""

import csv
from pathlib import Path

import pytest

try:
    from define_uk import validation
    from define_uk.scenarios import _run_root
    _run_root()
    HAVE_RUN = True
except Exception:
    HAVE_RUN = False

ARTIFACT = Path(__file__).resolve().parents[1] / "validation" / "baseline_vs_external.csv"

pytestmark = pytest.mark.skipif(
    not HAVE_RUN, reason="no cached DEFINE-UK run"
)


def test_committed_artifact_matches_recomputation():
    computed = validation.baseline_calibration()
    with ARTIFACT.open() as fh:
        committed = list(csv.DictReader(fh))
    assert len(committed) == len(computed)
    for got, want in zip(computed, committed):
        for k, v in want.items():
            assert str(got[k]) == v, (got["quantity"], k, got[k], v)


def test_baseline_divergence_is_material_and_directional():
    rows = {r["quantity"]: r for r in validation.baseline_calibration()}
    # The reason the adapter is deltas-only, quantified:
    assert rows["real_gdp_growth_2025"]["gap"] > 3.0
    assert rows["unemployment_2025"]["gap"] < -0.5
    assert rows["emissions_2024"]["gap"] > 25.0
    # And the one row expected to be consistent stays consistent:
    assert abs(rows["population_16plus_2025"]["gap"]) < 0.5


def test_gpi_multiplier_pinned():
    m = validation.gpi_multiplier()
    assert m["multiplier"] == pytest.approx(1.78, abs=0.01)
    assert m["cum_delta_gdp_real"] == pytest.approx(250.6, abs=0.5)
    # If either total drifts, the cached run changed — investigate, then
    # re-pin deliberately.
    assert m["cum_delta_gdp"] == pytest.approx(209.9, abs=0.5)
    assert m["cum_delta_spend"] == pytest.approx(118.2, abs=0.5)


def test_upstream_multiplier_table_is_flagged_unusable():
    m = validation.gpi_multiplier()
    assert "identical across all 8 scenarios" in m["upstream_table_unusable"]
