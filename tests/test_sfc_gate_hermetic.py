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
COLUMNS = ("LEND",) + scenarios.DEFAULT_VARIABLES + ("GO_PS", "GO_PSR", "P_ELEC")
SIM_START = 144  # 2023Q1


def _write(path: Path, *, shocked: bool, lend: dict[int, float] | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(("",) + COLUMNS)
        for t in range(N_QUARTERS):
            bump = 1.0 if shocked and t >= SIM_START else 0.0
            row = [(lend or {}).get(t, 0.0)]
            row += [100.0 + bump, 50.0 - bump, 5.0, 60.0 + bump]
            row += [10.0, 10.0, 1.0]
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
