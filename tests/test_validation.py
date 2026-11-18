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
    assert rows["unemployment_2025"]["gap"] < -0.4
    assert rows["emissions_2024"]["gap"] > 25.0
    # And the one row expected to be consistent stays consistent:
    assert abs(rows["population_16plus_2025"]["gap"]) < 0.5


def test_gpi_multiplier_pinned():
    import json

    ref = json.loads(
        (ARTIFACT.parent / "reference_outputs.json").read_text()
    )["gpi_multiplier"]
    m = validation.gpi_multiplier()
    assert m["multiplier"] == pytest.approx(
        ref["multiplier"], abs=ref["multiplier_tolerance_abs"]
    )
    tol = ref["cum_tolerance_abs"]
    assert m["cum_delta_gdp_real"] == pytest.approx(
        ref["cum_delta_gdp_real"], abs=tol
    )
    # If either total drifts, the cached run changed — investigate, then
    # re-pin deliberately.
    assert m["cum_delta_gdp"] == pytest.approx(ref["cum_delta_gdp"], abs=tol)
    assert m["cum_delta_spend"] == pytest.approx(
        ref["cum_delta_spend"], abs=tol
    )
    # Issue #16 (decided 2026-11-15): the headline divides by the policy
    # instrument SPEND_GVTPS; total non-wage spending is the secondary ratio.
    assert m["denominator"] == "SPEND_GVTPS"
    sec = ref["secondary"]
    assert m["secondary"]["multiplier"] == pytest.approx(
        sec["multiplier"], abs=ref["multiplier_tolerance_abs"]
    )
    assert m["secondary"]["cum_delta_spend"] == pytest.approx(
        sec["cum_delta_spend"], abs=tol
    )
    alt = validation.gpi_multiplier("total_spending")
    assert alt["multiplier"] == m["secondary"]["multiplier"]
    assert "secondary" not in alt
    with pytest.raises(ValueError):
        validation.gpi_multiplier("green_investment")


def test_upstream_multiplier_table_is_flagged_unusable():
    m = validation.gpi_multiplier()
    assert "identical across all 8 scenarios" in m["upstream_table_unusable"]


def test_gpi_multiplier_is_back_loaded_and_pinned():
    """Fable 5.2 review, 2026-11-17: counted from the policy start the ratio
    is below 1 for five years and reaches 2.25 by 2040; 2.30 also carries
    4.8 of pre-policy (alpha_PP) GDP delta."""
    import json

    ref = json.loads(
        (ARTIFACT.parent / "reference_outputs.json").read_text()
    )["gpi_multiplier"]
    m = validation.gpi_multiplier()
    by = m["horizon_profile"]["by_year"]
    for year, value in ref["horizon_profile_checkpoints"].items():
        assert by[int(year)] == pytest.approx(value, abs=0.01), year
    assert m["from_policy_start"] == pytest.approx(ref["from_policy_start"], abs=0.01)
    assert m["pre_policy_cum_delta_gdp"] == pytest.approx(
        ref["pre_policy_cum_delta_gdp"], abs=0.1)
    assert all(v < 1 for y, v in by.items() if y <= 2031)
    assert list(by.values()) == sorted(by.values())  # rises with horizon
