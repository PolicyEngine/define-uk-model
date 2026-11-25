"""Hermetic: the stock-flow gate on a synthetic cached run (runs in CI).

The sweep in test_scenario_sweep.py runs only where the pinned upstream run
is cached (the upstream is unlicensed, so CI never has it). The code that
turns that sweep into a gate -- ``sfc_check`` and ``run_scenario``'s refusal
of an inconsistent solve -- is ours, so it is tested here on small synthetic
``Variables_*.csv`` files written to a temporary cache. Each test perturbs one
cell and shows the gate turns it away; none uses upstream data.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from define_uk import scenarios
from define_uk.scenarios import (
    N_QUARTERS,
    SFC_TOLERANCE,
    StockFlowInconsistent,
    run_scenario,
    sfc_check,
)
from define_uk.upstream import UPSTREAM_COMMIT

REFERENCE = json.loads(
    (Path(__file__).resolve().parents[1] / "validation"
     / "reference_outputs.json").read_text()
)["stock_flow_consistency"]
NAME = "green_public_investment"
_, _, FOLDER, LABEL, _ = scenarios._BY_NAME[NAME]
# GO_PS, GO_PSR, P_ELEC: sfc_check reads them to report the electricity
# valuation gap (manual Eq. (74)) in failing quarters; zero gap here.
# FNW: the stock side of the check (sum of sectoral financial net worth).
COLUMNS = (("LEND",) + scenarios.DEFAULT_VARIABLES
           + ("GO_PS", "GO_PSR", "P_ELEC", "FNW"))
SIM_START = 144  # 2023Q1


def _write(path: Path, *, shocked: bool, lend: dict | None = None,
           fnw: dict | None = None, stock_column: bool = True):
    """``lend`` / ``fnw`` map a row to the value printed there ("NA" for a
    missing one); every other quarter prints 0."""
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = COLUMNS if stock_column else COLUMNS[:-1]
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(("",) + columns)
        for t in range(N_QUARTERS):
            bump = 1.0 if shocked and t >= SIM_START else 0.0
            row = [(lend or {}).get(t, 0.0)]
            row += [100.0 + bump, 50.0 - bump, 5.0, 60.0 + bump]
            row += [10.0, 10.0, 1.0]
            if stock_column:
                row += [(fnw or {}).get(t, 0.0)]
            w.writerow([t + 1] + row)


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(scenarios, "cache_dir", lambda: tmp_path)
    folder = tmp_path / UPSTREAM_COMMIT / scenarios._TABLES / FOLDER
    _write(folder / "Variables_Baseline.csv", shocked=False)
    _write(folder / f"Variables_{LABEL}.csv", shocked=True)
    return folder


def test_tolerance_is_the_recorded_one():
    assert SFC_TOLERANCE == REFERENCE["tolerance_abs"]


def test_consistent_solve_is_served_with_a_passed_check(cache):
    r = run_scenario(NAME)
    assert r["sfc_check"]["scenario"]["passed"]
    assert r["sfc_check"]["baseline"]["passed"]
    assert not r["caveats"][0].startswith("NOT STOCK-FLOW CONSISTENT")
    assert r["variables"]["GDP_R"]["delta_level"][0] == pytest.approx(1.0)


def test_check_names_the_failing_quarters(cache):
    path = cache / f"Variables_{LABEL}.csv"
    _write(path, shocked=True, lend={SIM_START: 0.5, SIM_START + 6: -0.02})
    c = sfc_check(path)
    assert not c["passed"]
    assert c["failing_quarters"] == ["2023Q1", "2024Q3"]
    assert c["max_abs"] == pytest.approx(0.5)


def test_tolerance_boundary(cache):
    path = cache / f"Variables_{LABEL}.csv"
    _write(path, shocked=True, lend={SIM_START: 0.99 * SFC_TOLERANCE})
    assert sfc_check(path)["passed"]
    _write(path, shocked=True, lend={SIM_START: 1.01 * SFC_TOLERANCE})
    assert not sfc_check(path)["passed"]


@pytest.mark.parametrize("which", ["scenario", "baseline"])
def test_inconsistent_solve_is_refused(cache, which):
    target = (f"Variables_{LABEL}.csv" if which == "scenario"
              else "Variables_Baseline.csv")
    _write(cache / target, shocked=which == "scenario",
           lend={SIM_START + 40: 74.56})
    with pytest.raises(StockFlowInconsistent, match="2033Q1"):
        run_scenario(NAME)
    r = run_scenario(NAME, allow_inconsistent=True)
    assert not r["sfc_check"][which]["passed"]
    assert r["caveats"][0].startswith("NOT STOCK-FLOW CONSISTENT")


def test_inconsistent_solve_error_carries_the_checks(cache):
    _write(cache / f"Variables_{LABEL}.csv", shocked=True,
           lend={SIM_START + 40: 74.56})
    with pytest.raises(StockFlowInconsistent) as e:
        run_scenario(NAME)
    assert e.value.scenario == NAME
    assert e.value.sfc_check["scenario"]["failing_quarters"] == ["2033Q1"]
    assert e.value.sfc_check["baseline"]["passed"]


# --- stock side: sectoral financial net worth sums to zero -------------------

def test_stock_side_passes_on_a_consistent_solve(cache):
    c = sfc_check(cache / f"Variables_{LABEL}.csv")
    assert c["passed"] and c["flow_passed"]
    assert c["stock"] == {
        "variable": "FNW (sum of sectoral financial net worth)",
        "available": True, "max_abs": 0.0, "failing_from": None,
        "n_failing_quarters": 0, "passed": True,
    }


@pytest.mark.parametrize("which", ["scenario", "baseline"])
def test_a_stock_break_alone_is_refused(cache, which):
    """Net lending sums to zero in every quarter, but the balance sheets do
    not from 2033Q1 on: the flow check alone would have served this."""
    target = (f"Variables_{LABEL}.csv" if which == "scenario"
              else "Variables_Baseline.csv")
    broken = {t: 182.4 for t in range(SIM_START + 40, N_QUARTERS)}
    _write(cache / target, shocked=which == "scenario", fnw=broken)
    c = sfc_check(cache / target)
    assert c["flow_passed"] and c["failing_quarters"] == [] and not c["passed"]
    assert c["stock"]["failing_from"] == "2033Q1"
    assert c["stock"]["n_failing_quarters"] == N_QUARTERS - SIM_START - 40
    with pytest.raises(StockFlowInconsistent, match=r"\|FNW\| up to 182.40 from 2033Q1"):
        run_scenario(NAME)
    r = run_scenario(NAME, allow_inconsistent=True)
    assert r["caveats"][0].startswith("NOT STOCK-FLOW CONSISTENT")
    assert "FNW" in r["caveats"][0]


def test_stock_tolerance_boundary(cache):
    path = cache / f"Variables_{LABEL}.csv"
    _write(path, shocked=True, fnw={SIM_START: 0.99 * SFC_TOLERANCE})
    assert sfc_check(path)["passed"]
    _write(path, shocked=True, fnw={SIM_START: -1.01 * SFC_TOLERANCE})
    assert not sfc_check(path)["passed"]


@pytest.mark.parametrize("column", ["lend", "fnw"])
def test_a_missing_value_in_a_simulated_quarter_fails(cache, column):
    """An unprinted LEND or FNW cannot be shown to be zero. Before
    2026-11-24 a missing value was skipped, so it passed. The data years,
    where the upstream prints none, are not checked."""
    path = cache / f"Variables_{LABEL}.csv"
    _write(path, shocked=True, **{column: {0: "NA", SIM_START - 1: "NA"}})
    assert sfc_check(path)["passed"]
    _write(path, shocked=True, **{column: {SIM_START + 3: "NA"}})
    c = sfc_check(path)
    assert not c["passed"]
    if column == "lend":
        assert c["failing_quarters"] == ["2023Q4"]
    else:
        assert c["stock"]["failing_from"] == "2023Q4"
    with pytest.raises(StockFlowInconsistent):
        run_scenario(NAME)


def test_a_file_without_the_stock_column_is_flagged_not_passed_silently(cache):
    for f in ("Variables_Baseline.csv", f"Variables_{LABEL}.csv"):
        _write(cache / f, shocked=f != "Variables_Baseline.csv",
               stock_column=False)
    r = run_scenario(NAME)
    stock = r["sfc_check"]["scenario"]["stock"]
    assert stock["available"] is False and stock["passed"] is None
    assert r["sfc_check"]["scenario"]["passed"]  # on the flow side alone
    assert any(c.startswith("Stock side not checked") for c in r["caveats"])


def test_unknown_policy_start_is_flagged_not_assumed(cache):
    """With one policy file cached the policy start cannot be read, so the
    path is not trimmed and policy_active is None (unknown), never True."""
    scenarios._policy_start_year.cache_clear()
    r = run_scenario(NAME)
    assert r["policy_start_year"] is None
    assert r["policy_active"] and all(a is None for a in r["policy_active"])
    assert r["caveats"][0].startswith("Policy start unknown")
