"""Hermetic: the baseline/policy parameter gate on a synthetic cached run.

Issue #20: a scenario-minus-baseline delta is a policy effect only if the
two solves share every parameter except the policy levers. In the pinned
run they do not (alpha_PPLR, see test_alpha_pp_confound.py), and nothing in
this package can change that: the mismatch is in the upstream run's own
parameter files. What is ours is the check that reads those files and what
``run_scenario`` does with the answer, tested here on synthetic
``Parameters-sorted_*.csv`` files; none uses upstream data.
"""

from __future__ import annotations

import csv

import pytest

from define_uk import scenarios
from define_uk.scenarios import (
    BaselineParameterMismatch,
    KNOWN_PARAMETER_MISMATCHES,
    POLICY_LEVERS,
    parameter_check,
    run_scenario,
)
from test_sfc_gate_hermetic import LABEL, NAME, cache  # noqa: F401

BASE = {"alpha_PPLR": "0.2762", "beta_1": "0.5", "GVT_INVEST": "0",
        "GREEN_BONDS": "0", "CRED": "0.9"}
LEVERS_ON = {"GVT_INVEST": "1", "GREEN_BONDS": "1", "CRED": "1"}


def _write_params(folder, label, values):
    with (folder / f"Parameters-sorted_{label}.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([""] + [f" {k} " for k in values])  # upstream pads names
        w.writerow(["1"] + list(values.values()))


def _params(cache, scenario, baseline=BASE):  # noqa: F811
    _write_params(cache, "Baseline", baseline)
    _write_params(cache, LABEL, scenario)
    return parameter_check(cache / f"Parameters-sorted_{LABEL}.csv",
                           cache / "Parameters-sorted_Baseline.csv")


def test_the_known_mismatch_is_not_a_lever():
    assert not set(KNOWN_PARAMETER_MISMATCHES) & POLICY_LEVERS
    assert KNOWN_PARAMETER_MISMATCHES == {
        "alpha_PPLR": "PolicyEngine/define-uk-model#20"}


def test_levers_alone_pass_and_drop_the_issue_20_record(cache):  # noqa: F811
    """A matched Baseline: only levers differ, so the delta is the policy."""
    c = _params(cache, {**BASE, **LEVERS_ON})
    assert c["checked"] and c["passed"] and c["shared_except_levers"]
    assert set(c["levers"]) == set(LEVERS_ON) and c["non_lever"] == {}
    assert c["levers"]["CRED"] == {"baseline": "0.9", "scenario": "1"}
    r = run_scenario(NAME)
    assert r["parameter_check"] == c
    assert r["baseline_parameter_mismatch"] is None
    assert not any("issue #20" in x for x in r["caveats"])


def test_the_documented_mismatch_is_served_with_its_record(cache):  # noqa: F811
    """The pinned run's case: alpha_PPLR differs. Served, flagged, and the
    record carries the values the files print, not constants."""
    c = _params(cache, {**BASE, **LEVERS_ON, "alpha_PPLR": "0.2770"},
                {**BASE, "alpha_PPLR": "0.2748"})
    assert c["passed"] and c["shared_except_levers"] is False
    assert c["non_lever"] == {
        "alpha_PPLR": {"baseline": "0.2748", "scenario": "0.2770"}}
    r = run_scenario(NAME)
    m = r["baseline_parameter_mismatch"]
    assert (m["parameter"], m["baseline_files"], m["policy_files"]) == (
        "alpha_PPLR", 0.2748, 0.277)
    assert any("issue #20" in x for x in r["caveats"])


@pytest.mark.parametrize("scenario,baseline,name", [
    ({**BASE, **LEVERS_ON, "beta_1": "0.6"}, BASE, "beta_1"),
    # a parameter printed by one file only is a difference, not a pass
    ({**BASE, **LEVERS_ON, "gamma_new": "1"}, BASE, "gamma_new"),
    ({k: v for k, v in {**BASE, **LEVERS_ON}.items() if k != "beta_1"},
     BASE, "beta_1"),
])
def test_an_undocumented_mismatch_is_refused(cache, scenario, baseline, name):  # noqa: F811
    c = _params(cache, scenario, baseline)
    assert c["undocumented"] == [name] and c["passed"] is False
    with pytest.raises(BaselineParameterMismatch, match=name) as e:
        run_scenario(NAME)
    assert e.value.scenario == NAME
    assert e.value.parameter_check == c
    assert isinstance(e.value, ValueError)  # what callers already catch
    r = run_scenario(NAME, allow_parameter_mismatch=True)
    assert r["caveats"][0].startswith("BASELINE AND SCENARIO PARAMETERS DIFFER")
    assert name in r["caveats"][0]


def test_print_format_is_not_a_difference(cache):  # noqa: F811
    c = _params(cache, {**BASE, "beta_1": "0.50", "CRED": "0.90"})
    assert c["levers"] == {} and c["non_lever"] == {}


def test_missing_parameter_files_are_unknown_not_a_pass(cache):  # noqa: F811
    """No parameter file: the property is unknown, the issue #20 record is
    kept, and the result says the comparison was not made."""
    r = run_scenario(NAME)
    c = r["parameter_check"]
    assert c["checked"] is False
    assert c["passed"] is None and c["shared_except_levers"] is None
    assert r["baseline_parameter_mismatch"]["parameter"] == "alpha_PPLR"
    assert any(x.startswith("Parameters not compared") for x in r["caveats"])
