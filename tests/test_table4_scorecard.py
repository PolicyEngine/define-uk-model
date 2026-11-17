"""Manual Table 4, every cell: the committed scorecard and its statuses.

validation/table4_scorecard.csv holds all 75 cells of the manual's Table 4
(15 variables x 2025/2030/2040/mean/sd) against the pinned upstream run,
each marked MATCH (within a stated tolerance), DIVERGENCE (outside any
defensible tolerance; pinned at the run's own value, a regression pin and
not validation) or NOT COMPARABLE (the table does not define the series).

The hermetic half runs in CI from the committed CSV alone. The cached half
recomputes the scorecard from the cached run and fails if the committed copy
is stale; regenerate it deliberately with
``python -m define_uk.validation --table4``.
"""

import csv
import json
from pathlib import Path

import pytest

from define_uk import validation

ROOT = Path(__file__).resolve().parents[1]
SCORECARD = ROOT / "validation" / "table4_scorecard.csv"
STATUSES = {"MATCH", "DIVERGENCE", "NOT COMPARABLE"}


def _committed():
    with SCORECARD.open() as fh:
        return list(csv.DictReader(fh))


def _f(x):
    return None if x == "" else float(x)


# --- hermetic -------------------------------------------------------------

def test_scorecard_covers_every_cell_of_table_4():
    rows = _committed()
    assert len(rows) == 15 * 5
    assert {r["variable"] for r in rows} == set(validation.TABLE4)
    for r in rows:
        assert r["status"] in STATUSES, r


def test_scorecard_published_values_are_the_manual_s():
    by = {(r["variable"], r["statistic"]): r for r in _committed()}
    for key, (_, published, _, status) in validation.TABLE4.items():
        for stat, pub in zip(validation.TABLE4_STATS, published):
            r = by[key, stat]
            assert _f(r["published"]) == pub, (key, stat)
            assert r["status"] == status[stat][0], (key, stat)


def test_scorecard_statuses_hold_on_the_committed_numbers():
    for r in _committed():
        run, pub, gap, tol = (_f(r[k]) for k in ("run", "published", "gap", "tolerance_abs"))
        if r["status"] == "NOT COMPARABLE":
            assert run is None and gap is None and tol is None, r
            continue
        assert gap == pytest.approx(run - pub, abs=1.5e-3), r
        if r["status"] == "MATCH":
            assert tol is not None and abs(gap) <= tol, r
        else:  # DIVERGENCE carries no tolerance: it is pinned, not passed
            assert tol is None, r


def test_scorecard_agrees_with_the_reference_artifact():
    """The five rows gated since 2026-08-04 keep the same published values
    and tolerances in reference_outputs.json."""
    ref = json.loads((ROOT / "validation" / "reference_outputs.json").read_text())
    t4 = ref["table4_baseline"]
    cols = t4["columns"][1:]
    for year, vals in t4["years"].items():
        for col, v in zip(cols, vals[1:]):
            idx = validation.TABLE4_STATS.index(year)
            assert validation.TABLE4[col][1][idx] == v, (col, year)
    for col, tol in t4["tolerances"].items():
        assert validation.TABLE4[col][3]["2025"] == ("MATCH", tol["abs"]), col


def test_the_known_divergences_stay_labelled():
    """Honesty pins: these must never be relabelled MATCH without evidence."""
    status = {(r["variable"], r["statistic"]): r["status"] for r in _committed()}
    for var in ("emissions_mtco2e_yr", "non_fossil_electricity_share_pct",
                "ps_default_rate_pct", "ps_credit_rationing_pct",
                "imports_pct_gdp", "exports_pct_gdp"):
        for stat in validation.TABLE4_STATS:
            assert status[var, stat] == "DIVERGENCE", (var, stat)
    for stat in ("2040", "mean", "sd"):
        assert status["nfc_credit_rationing_pct", stat] == "DIVERGENCE"
    assert status["green_investment_pct_gdp", "2025"] == "NOT COMPARABLE"


# --- cached run -------------------------------------------------------------

try:
    from define_uk.scenarios import _run_root
    _run_root()
    HAVE_RUN = True
except Exception:
    HAVE_RUN = False


@pytest.mark.skipif(not HAVE_RUN, reason="no cached DEFINE-UK run")
def test_committed_scorecard_is_not_stale():
    computed = validation.table4_scorecard()
    committed = _committed()
    assert len(computed) == len(committed)
    for c, k in zip(computed, committed):
        for field in ("variable", "statistic", "status", "how_read"):
            assert str(c[field]) == k[field], (field, c, k)
        for field in ("published", "tolerance_abs"):
            assert c[field] == _f(k[field]), (field, c, k)
        # One unit of the third decimal: Python 3.12's sum() is compensated
        # and 3.11's is not, so a cell on a rounding boundary can differ by
        # 0.001 between interpreters (non_fossil 2030: 75.307 vs 75.308).
        for field in ("run", "gap"):
            if c[field] is None or _f(k[field]) is None:
                assert c[field] is None and _f(k[field]) is None, (field, c, k)
            else:
                assert abs(c[field] - _f(k[field])) <= 1.0001e-3, (field, c, k)


@pytest.mark.skipif(not HAVE_RUN, reason="no cached DEFINE-UK run")
def test_emissions_power_share_accounts_for_about_30pct_of_the_2040_gap():
    """Back-of-envelope, recorded in VALIDATION.md target 1b: rescaling the
    run's electricity emissions to Table 4's fossil share (assuming they
    scale with it) adds ~22 Mt of the ~76 Mt 2040 gap. The rest is in
    non-electricity emissions, which Table 4 does not break down."""
    from define_uk.scenarios import _annual_means, _read_column

    base = validation._baseline_path()
    a = {v: _annual_means(_read_column(base, v))[2040]
         for v in ("EMIS", "EMIS_ELEC", "EMIS_NELEC", "beta_NFF")}
    assert 4 * (a["EMIS_ELEC"] + a["EMIS_NELEC"]) == pytest.approx(4 * a["EMIS"], abs=0.5)
    elec_at_table = 4 * a["EMIS_ELEC"] * (1 - 0.7714) / (1 - a["beta_NFF"])
    added = elec_at_table - 4 * a["EMIS_ELEC"]
    gap = 324.37 - 4 * a["EMIS"]
    assert added == pytest.approx(22.4, abs=1.0)
    assert gap == pytest.approx(75.7, abs=0.2)
    assert 0.25 < added / gap < 0.35
