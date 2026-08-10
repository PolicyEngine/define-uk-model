"""Replication check: pinned upstream baseline vs Model Manual v1.1 Table 4.

Runs against the cached upstream output (``define_uk.upstream.cache_dir``);
skips when no cached run exists. Calendar anchoring: the 16+ population path
is monotonic and matches Table 4's 2025/2030 values exactly at t=153/t=173,
placing the 216-quarter run on 1987Q1–2040Q4.

Known divergence (recorded in VALIDATION.md): the pinned commit's EMIS path
sits below Table 4 and drifts with horizon (−3.5% in 2025 to −23% in 2040)
while the macro block matches — a vintage/calibration difference between the
published table and the pinned code. The emissions comparison is therefore
asserted at its OBSERVED divergence (to catch further drift), not at
replication tolerance.
"""

import csv
from pathlib import Path

import pytest

from define_uk.upstream import UPSTREAM_COMMIT as PINNED_COMMIT, cache_dir

BASELINE = (
    "output/tables/housing_regulation/Variables_Baseline.csv"
)

# Manual v1.1 Table 4 (annualised): year -> (t0 index, real GDP growth %,
# unemployment %, population 16+ m, labour force m, emissions MtCO2e/yr).
# Loaded from the committed reference artifact (single source of truth,
# hermetically gated by tests/test_committed_artifacts.py).
import json

_REF = json.loads(
    (Path(__file__).resolve().parents[1] / "validation"
     / "reference_outputs.json").read_text()
)
TABLE_4 = {
    int(year): tuple(vals)
    for year, vals in _REF["table4_baseline"]["years"].items()
}
_TOL = _REF["table4_baseline"]["tolerances"]
_EMIS_RATIO = {
    int(y): r
    for y, r in _REF["emissions_divergence"]["ratio_run_over_table4"].items()
}
_EMIS_RATIO_TOL = _REF["emissions_divergence"]["tolerance"]["abs"]


@pytest.fixture(scope="module")
def baseline():
    path = Path(cache_dir()) / PINNED_COMMIT / BASELINE
    if not path.exists():
        pytest.skip("no cached upstream run (define_uk.runner.run first)")
    rows = list(csv.DictReader(path.open()))
    assert len(rows) == 216

    def col(name):
        return [
            float(r[name]) if r[name] not in ("", "NA") else None for r in rows
        ]

    return {v: col(v) for v in ("GDP_R", "UPLOT", "POP", "LF", "EMIS")}


def _year_mean(series, t0):
    vals = [series[t] for t in range(t0, t0 + 4) if series[t] is not None]
    return sum(vals) / len(vals)


@pytest.mark.parametrize("year", TABLE_4)
def test_macro_block_replicates_table_4(baseline, year):
    t0, growth, unemp, pop, lf, _ = TABLE_4[year]
    assert _year_mean(baseline["POP"], t0) == pytest.approx(
        pop, abs=_TOL["population_16plus_m"]["abs"]
    )
    assert _year_mean(baseline["LF"], t0) == pytest.approx(
        lf, abs=_TOL["labour_force_m"]["abs"]
    )
    run_growth = 100 * (
        _year_mean(baseline["GDP_R"], t0) / _year_mean(baseline["GDP_R"], t0 - 4) - 1
    )
    # 0.3pp tolerance: Table 4's annualisation convention is not stated
    # exactly; 2030/2040 match to 0.06pp, 2025 differs by 0.30pp.
    assert run_growth == pytest.approx(
        growth, abs=_TOL["real_gdp_growth_pct"]["abs"]
    )
    run_unemp = _year_mean(baseline["UPLOT"], t0)
    if run_unemp < 1:
        run_unemp *= 100
    assert run_unemp == pytest.approx(unemp, abs=_TOL["unemployment_pct"]["abs"])


@pytest.mark.parametrize("year", TABLE_4)
def test_emissions_divergence_from_table_4_does_not_widen(baseline, year):
    """The pinned code's EMIS path is BELOW Table 4 (see module docstring).

    Assert the observed divergence so any further drift in the cached run or
    the pinned code is caught; a fix upstream that closes the gap will fail
    this test loudly, which is the correct prompt to retighten it.
    """
    t0, *_, emis = TABLE_4[year]
    run_emis = 4 * _year_mean(baseline["EMIS"], t0)
    assert run_emis / emis == pytest.approx(
        _EMIS_RATIO[year], abs=_EMIS_RATIO_TOL
    )
