"""Scenario design integrity + published coarse anchors.

No machine-readable numeric scenario RESULTS are published for DEFINE-UK
1.1 (the manual stops at the baseline; the George/Dafermos SSRN paper is
paywalled and its scenario set predates v1.1's regulation policies), so
targets 2/3 in VALIDATION.md are gated at the two levels that ARE
verifiable:

1. Scenario design: each cached scenario run toggles exactly the policy
   switches the manual's scenario descriptions claim, with the pinned
   settings (e.g. the 40% housing retrofit subsidy rate). A scenario whose
   parameter diff drifts fails loudly.
2. Coarse published anchors from the open FMM 2023 conference version of
   the paper (pre-1.0 model vintage — tolerances are deliberately wide and
   these are sanity anchors, not replications): green public investment
   peaks around +1% of GDP; the current-policies baseline emits just under
   350 MtCO2e/yr in 2030.
"""

import csv
from pathlib import Path

import pytest

try:
    from define_uk import scenarios as sc
    from define_uk.scenarios import _run_root
    _run_root()
    HAVE_RUN = True
except Exception:
    HAVE_RUN = False

pytestmark = pytest.mark.skipif(not HAVE_RUN, reason="no cached DEFINE-UK run")

# alpha_PPLR shifts in every scenario (a recalibrated pricing parameter),
# so it is expected everywhere and asserted separately.
_COMMON = {"alpha_PPLR"}

# folder -> scenario csv label -> exact set of changed parameters
# (vs the same folder's Parameters-sorted_Baseline.csv) and pinned values
# for the policy-defining ones.
EXPECTED = {
    ("gvt_investment", "GPI + Green Bonds"): (
        {"CO_NFF", "CRED", "GREEN_BONDS", "GREEN_POWER", "GVT_CRED",
         "GVT_INVEST", "sh_rGVTNMFIG"},
        {"GREEN_BONDS": "1", "GVT_INVEST": "1", "GREEN_POWER": "1"},
    ),
    ("gvt_investment", "Green Power Subsidy"): (
        {"CRED", "GREEN_POWER", "GVT_CRED"},
        {"GREEN_POWER": "1"},
    ),
    ("housing_regulation", "Housing Regulation"): (
        {"CRED", "GVT_CRED", "HENBAN", "HIBAN", "HSELL", "THENBAN",
         "THIBAN", "TTRANSH"},
        {"HENBAN": "1", "HIBAN": "1"},
    ),
    ("housing_regulation", "Housing Regulation + Subsidy"): (
        {"CRED", "GVT_CRED", "HENBAN", "HIBAN", "HOUSING_SUB",
         "HOUSING_SUB_RATE", "HSELL", "THENBAN", "THIBAN", "TTRANSH"},
        {"HOUSING_SUB": "1", "HOUSING_SUB_RATE": "0.4"},
    ),
    ("power_sector_regulation/mutual_trust", "Fossil Fuel Ban"): (
        {"FF_BAN", "FF_CAP_BAN", "FF_INV_BAN", "TRANS_PASS", "TTRANS"},
        {"FF_BAN": "1"},
    ),
    ("power_sector_regulation/mutual_trust", "Power Sector Subsidy"): (
        set(),
        {"POWER_SUB": "1"},
    ),
    ("power_sector_regulation/mutual_trust", "Fossil Fuel Ban + Subsidy"): (
        {"FF_BAN", "FF_CAP_BAN", "FF_INV_BAN", "POWER_SUB", "TRANS_PASS",
         "TTRANS"},
        {"FF_BAN": "1", "POWER_SUB": "1"},
    ),
    ("mixed/mutual_trust", "Both Regulations + Subsidies"): (
        {"FF_BAN", "FF_CAP_BAN", "FF_INV_BAN", "HENBAN", "HIBAN",
         "HOUSING_SUB", "HOUSING_SUB_RATE", "HSELL", "POWER_SUB",
         "THENBAN", "THIBAN", "TRANS_PASS", "TTRANS", "TTRANSH"},
        {"FF_BAN": "1", "HOUSING_SUB": "1", "POWER_SUB": "1",
         "HOUSING_SUB_RATE": "0.4"},
    ),
}
# Power Sector Subsidy toggles only POWER_SUB (+ the common param).
EXPECTED[("power_sector_regulation/mutual_trust", "Power Sector Subsidy")] = (
    {"POWER_SUB"},
    {"POWER_SUB": "1"},
)


def _param_diff(folder: str, label: str) -> dict:
    d = _run_root() / sc._TABLES / folder
    base = list(csv.DictReader((d / "Parameters-sorted_Baseline.csv").open()))[0]
    row = list(csv.DictReader((d / f"Parameters-sorted_{label}.csv").open()))[0]
    return {
        k.strip(): row[k].strip()
        for k in base
        if base[k] != row[k]
    }


@pytest.mark.parametrize("folder,label", sorted(EXPECTED))
def test_scenario_toggles_exactly_its_published_policy_switches(folder, label):
    changed_want, values_want = EXPECTED[(folder, label)]
    diff = _param_diff(folder, label)
    assert set(diff) - _COMMON == changed_want, (folder, label, diff)
    for k, v in values_want.items():
        assert diff[k] == v, (folder, label, k, diff.get(k))


def test_fmm2023_anchor_gpi_gdp_peak_about_one_percent():
    res = sc.run_scenario("green_public_investment")
    pct = [p for p in res["variables"]["GDP_R"]["delta_pct"] if p is not None]
    assert 0.7 <= max(pct) <= 1.3, max(pct)


def test_fmm2023_anchor_baseline_2030_emissions_just_under_350():
    base = sc._annual_means(
        sc._read_column(
            _run_root() / sc._TABLES / "gvt_investment" / "Variables_Baseline.csv",
            "EMIS",
        )
    )
    annual_2030 = 4.0 * base[2030]
    assert 330.0 <= annual_2030 <= 352.0, annual_2030
