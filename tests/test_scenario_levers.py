"""The committed lever data against the cached run (skips in CI).

``scenarios.SCENARIO_LEVERS`` and ``scenarios.BASELINE_POWER_SUBSIDY`` are
data read from the cached run and committed, so that the per-scenario gate
and the generated docs/scenario-levers.md work without it. These tests
check both against the cached files, so the committed data cannot drift
from what the run prints. The hermetic side (the gate's behaviour, and the
docs page against the data) is in tests/test_parameter_gate_hermetic.py.
"""

import hashlib

import pytest

from define_uk import scenarios as sc

try:
    TABLES = sc._run_root() / sc._TABLES
    HAVE_RUN = True
except Exception:
    HAVE_RUN = False

pytestmark = pytest.mark.skipif(not HAVE_RUN, reason="no cached DEFINE-UK run")


def _diff(folder, label):
    base = sc._parameter_row(TABLES / folder / "Parameters-sorted_Baseline.csv")
    scen = sc._parameter_row(TABLES / folder / f"Parameters-sorted_{label}.csv")
    assert set(base) == set(scen)
    return {k: (base[k], scen[k]) for k in base
            if not sc._same_value(base[k], scen[k])}


def test_scenario_levers_are_what_the_cached_parameter_files_print():
    for name, _, folder, label, _ in sc._REGISTRY:
        diff = _diff(folder, label)
        assert diff.pop("alpha_PPLR") == ("0.2748", "0.2762"), name
        assert diff == sc.SCENARIO_LEVERS[name], name


def test_every_registered_scenario_passes_the_exact_lever_gate():
    for name, _, folder, label, _ in sc._REGISTRY:
        c = sc.parameter_check(
            TABLES / folder / f"Parameters-sorted_{label}.csv",
            TABLES / folder / "Parameters-sorted_Baseline.csv",
            expected_levers=sc.SCENARIO_LEVERS[name])
        assert c["levers_exact"] is True and c["passed"], (name, c)


def test_another_scenarios_levers_are_refused_on_the_cached_files():
    """The union gate let this through: the fossil-fuel ban's parameter row
    served under the green-public-investment name moves only levers."""
    folder, label = "power_sector_regulation/mutual_trust", "Fossil Fuel Ban"
    args = (TABLES / folder / f"Parameters-sorted_{label}.csv",
            TABLES / folder / "Parameters-sorted_Baseline.csv")
    assert sc.parameter_check(*args)["passed"]
    c = sc.parameter_check(
        *args, expected_levers=sc.SCENARIO_LEVERS["green_public_investment"])
    assert c["passed"] is False
    assert "FF_BAN" in c["unexpected_levers"]
    assert "GVT_INVEST" in c["missing_levers"]


def test_the_eight_baselines_are_one_file():
    folders = sorted({folder for _, _, folder, _, _ in sc._REGISTRY})
    assert len(folders) == 8
    for stem in ("Variables_Baseline.csv", "Parameters-sorted_Baseline.csv"):
        digests = {hashlib.sha256((TABLES / f / stem).read_bytes()).hexdigest()
                   for f in folders}
        assert len(digests) == 1, stem


def _column(folder, label, variable):
    return [x or 0.0 for x in sc._read_column(
        TABLES / folder / f"Variables_{label}.csv", variable)]


def test_the_baseline_pays_a_power_subsidy_no_switch_names():
    b = sc.BASELINE_POWER_SUBSIDY
    row = sc._parameter_row(
        TABLES / "gvt_investment" / "Parameters-sorted_Baseline.csv")
    assert row["POWER_SUB"] == row["GREEN_POWER"] == row["GVT_INVEST"] == "0"
    subs = _column("gvt_investment", "Baseline", "SUBS_PS")
    spend = _column("gvt_investment", "Baseline", "SPEND_GVTPS")
    assert subs == spend  # the whole of public power spending is subsidy
    first = next(t for t, x in enumerate(subs) if x)
    assert sc._quarter(first) == b["first_quarter"] == "2027Q1"
    assert subs[first] == b["first_quarter_value"]
    assert subs[-1] == b["last_quarter_value"]
    assert round(sum(subs[first:]), 2) == b["cumulative_2027_2040"]


def test_green_public_investment_replaces_the_baseline_subsidy():
    b = sc.BASELINE_POWER_SUBSIDY
    subs = _column("gvt_investment", "GPI + Green Bonds", "SUBS_PS")
    spend = _column("gvt_investment", "GPI + Green Bonds", "SPEND_GVTPS")
    assert sum(subs) == b["gpi_subs_ps_cumulative"] == 0.0
    assert round(sum(spend[160:]), 2) == b["gpi_spend_gvtps_cumulative"]
    assert not any(spend[:160])
    base = _column("gvt_investment", "Baseline", "SPEND_GVTPS")
    net = sum(g - x for g, x in zip(spend, base))
    assert net == pytest.approx(91.2, abs=0.05)
    # every other distinct solve keeps a positive power subsidy
    for name, _, folder, label, _ in sc._REGISTRY:
        if name != "green_public_investment":
            assert sum(_column(folder, label, "SUBS_PS")[160:]) > 15, name
