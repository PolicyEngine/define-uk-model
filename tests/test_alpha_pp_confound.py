"""The Baseline/policy alpha_PP mismatch: what the cached run itself shows.

Every Baseline file of the pinned run uses alpha_PPLR = 0.2748; every policy
file uses Table 5's 0.2762. It is the only parameter outside the published
policy switches that differs (``Parameters-sorted_*.csv``), and the printed
gap (0.0014) is 28 times the CSV's half-unit of rounding (0.00005), so it is
not a print artefact. No policy switch acts before 2027Q1: all 16 distinct
policy files are identical through 2026Q4. The 2023Q1-2026Q4 policy-minus-
baseline deltas are therefore the alpha_PP effect alone, and the same
effect sits unobserved inside every later delta. Evidence and the size of
the bias per published number: issue "Published deltas carry an alpha_PP
change" and VALIDATION.md (2026-11-06, round 5).

Reads cached CSVs only; skips in CI like test_oracle.py.
"""
from __future__ import annotations

import csv
import itertools

import pytest
from test_oracle import requires_cached_run

POLICY_START = 160  # 2027Q1 (row 0 = 1987Q1)
SIM_START = 144     # 2023Q1


def _tables():
    from define_uk.scenarios import _TABLES, _run_root
    return _run_root() / _TABLES


def _params(path):
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))
    return dict(zip((h.strip() for h in rows[0][1:]), rows[1][1:]))


def _rows(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def _policy_files():
    return sorted(p for p in _tables().rglob("Variables_*.csv")
                  if p.name != "Variables_Baseline.csv")


@requires_cached_run
def test_alpha_pplr_is_the_only_non_switch_parameter_that_differs():
    files = sorted(_tables().rglob("Parameters-sorted_*.csv"))
    assert len(files) == 30
    params = {f: _params(f) for f in files}
    base = {f: p for f, p in params.items() if f.name.endswith("_Baseline.csv")}
    pol = {f: p for f, p in params.items() if f not in base}
    assert {p["alpha_PPLR"] for p in base.values()} == {"0.2748"}
    assert {p["alpha_PPLR"] for p in pol.values()} == {"0.2762"}
    # Every other parameter that varies is a policy switch, never set away
    # from the Baseline value in a Baseline file.
    varying = {k for k in next(iter(params.values()))
               if len({p[k] for p in params.values()}) > 1}
    switches = varying - {"alpha_PPLR"}
    assert all(len({p[k] for p in base.values()}) == 1 for k in switches)
    assert abs(0.2762 - 0.2748) / 0.00005 > 20  # far beyond print rounding


@requires_cached_run
def test_no_policy_acts_before_2027q1():
    """All policy files are identical, every column, through 2026Q4."""
    files = _policy_files()
    data = {f: _rows(f) for f in files}
    first = {}
    for a, b in itertools.combinations(files, 2):
        for t in range(len(data[a])):
            if data[a][t] != data[b][t]:
                first[(a, b)] = t
                break
    assert min(first.values()) == POLICY_START


@requires_cached_run
def test_2023_26_deltas_are_the_alpha_pp_effect_alone():
    """So the pinned GPI 2026 real-GDP delta (-1.125, test_scenarios.py) is
    no policy effect: every scenario carries the same number."""
    base = _rows(_tables() / "gvt_investment" / "Variables_Baseline.csv")
    for f in _policy_files():
        s = _rows(f)
        d = [float(s[t]["GDP_R"]) - float(base[t]["GDP_R"])
             for t in range(POLICY_START - 4, POLICY_START)]
        assert sum(d) / 4 == pytest.approx(-1.125, abs=1e-9), f.name
    # Nonzero from the first simulated quarter, before any switch acts.
    s = _rows(_tables() / "gvt_investment" / "Variables_GPI + Green Bonds.csv")
    assert float(s[SIM_START]["GDP_R"]) - float(base[SIM_START]["GDP_R"]) == pytest.approx(3.1)
    # Mark-up calibrated on the last data row already differs (0.176 vs 0.1704).
    assert float(s[SIM_START - 1]["MU"]) - float(base[SIM_START - 1]["MU"]) == pytest.approx(-0.0056)
