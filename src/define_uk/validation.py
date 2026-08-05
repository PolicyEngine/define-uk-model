"""Computed calibration comparators for the DEFINE-UK baseline.

Turns VALIDATION.md's external-comparator table into numbers computed from
the cached pinned run, compared against pinned external observations, so
calibration drift fails tests instead of aging in prose.

Two kinds of quantity live here:

* ``baseline_calibration()`` — baseline levels vs external observations
  (ONS/DESNZ/OBR).  The model's own manual says the baseline "should not
  be seen as a prediction"; these rows quantify exactly how far the
  baseline sits from observed reality, which is why the adapter serves
  scenario DELTAS only.
* ``gpi_multiplier()`` — our own cumulative green-public-investment
  multiplier.  The upstream ``Multiplier_Summary.csv`` is not usable: its
  M_Impact/M_4Q/M_8Q columns are identical across all eight scenarios
  (M_Impact = −32.22 everywhere) and its TotalDeltaG (104.22) matches the
  cumulative delta of no variable in the scenario file, so we recompute
  from the delta paths with an explicit, reproducible definition.

External values are pinned with source and date; update them only with a
newer official release, never to make a comparison look better.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .scenarios import _TABLES, _annual_means, _read_column, _run_root

_BASE_FOLDER = "gvt_investment"  # baselines are identical across folders

# Pinned external observations. (quantity, value, units, source)
EXTERNAL = {
    "real_gdp_growth_2025": (
        1.0, "% y/y",
        "ONS quarterly national accounts vintage 2026 (uk_gdp_cvm; 2026Q1 "
        "y/y 0.9%); OBR March 2026 EFO near-term 1-2%",
    ),
    "real_gdp_growth_mean_2025_2040": (
        1.65, "% y/y mean",
        "OBR long-run growth assumption ~1.5-1.8% (March 2026 EFO)",
    ),
    "unemployment_2025": (
        5.2, "%", "ONS MGSX outturn, 2025Q4",
    ),
    "population_16plus_2025": (
        56.0, "millions", "ONS 16+ population estimate ~56m",
    ),
    "labour_force_2025": (
        34.5, "millions", "ONS labour force ~34-35m",
    ),
    "emissions_2024": (
        371.0, "MtCO2e/yr",
        "DESNZ UK territorial greenhouse gas emissions, 2024 provisional "
        "(2023 final: 384)",
    ),
    "emissions_2030_ndc": (
        260.0, "MtCO2e/yr",
        "UK NDC: 68% below 1990 by 2030 (~260 MtCO2e); the manual itself "
        "notes the current-policies baseline falls short by design",
    ),
}


def _baseline_path() -> Path:
    return _run_root() / _TABLES / _BASE_FOLDER / "Variables_Baseline.csv"


def baseline_calibration() -> list[dict]:
    """Baseline levels from the cached run vs pinned external observations.

    Returns rows of {quantity, model, external, units, source, gap,
    verdict}. ``verdict`` is a fixed editorial judgement (kept in sync with
    VALIDATION.md), not a pass/fail: the baseline is expected to diverge
    and the point of this table is to quantify by how much.
    """
    base = _baseline_path()
    gdp = _annual_means(_read_column(base, "GDP_R"))
    uplot = _annual_means(_read_column(base, "UPLOT"))
    pop = _annual_means(_read_column(base, "POP"))
    lf = _annual_means(_read_column(base, "LF"))
    emis = _annual_means(_read_column(base, "EMIS"))  # quarterly rate

    growth = {y: 100.0 * (gdp[y] / gdp[y - 1] - 1.0) for y in range(2024, 2041)}
    model = {
        "real_gdp_growth_2025": round(growth[2025], 2),
        "real_gdp_growth_mean_2025_2040": round(
            sum(growth[y] for y in range(2025, 2041)) / 16.0, 2
        ),
        "unemployment_2025": round(uplot[2025], 2),
        "population_16plus_2025": round(pop[2025], 2),
        "labour_force_2025": round(lf[2025], 2),
        # EMIS is a quarterly flow; annual total = 4 x annual mean.
        "emissions_2024": round(4.0 * emis[2024], 1),
        "emissions_2030_ndc": round(4.0 * emis[2030], 1),
    }
    verdicts = {
        "real_gdp_growth_2025": "far above outturn; never a forecast",
        "real_gdp_growth_mean_2025_2040": "high vs official long-run",
        "unemployment_2025": "below outturn",
        "population_16plus_2025": "consistent",
        "labour_force_2025": "slightly high",
        "emissions_2024": "above the actuals it should start from",
        "emissions_2030_ndc": "short of the NDC by design "
                              "(current-policies baseline)",
    }
    rows = []
    for q, (ext, units, source) in EXTERNAL.items():
        rows.append({
            "quantity": q,
            "model": model[q],
            "external": ext,
            "units": units,
            "gap": round(model[q] - ext, 2),
            "verdict": verdicts[q],
            "source": source,
        })
    return rows


def gpi_multiplier() -> dict:
    """Cumulative green-public-investment multiplier, computed by us.

    Definition: cumulative nominal GDP delta divided by cumulative nominal
    total government spending delta (SPEND_GVT), GPI + Green Bonds scenario
    vs baseline, summed over the full simulation. Reported alongside the
    real-GDP cumulative delta so the number is reproducible from the
    scenario file alone.
    """
    root = _run_root() / _TABLES / _BASE_FOLDER
    scen = root / "Variables_GPI + Green Bonds.csv"
    base = root / "Variables_Baseline.csv"

    def cum_delta(var: str) -> float:
        b = _read_column(base, var)
        s = _read_column(scen, var)
        return sum(sv - bv for sv, bv in zip(s, b)
                   if sv is not None and bv is not None)

    d_gdp = cum_delta("GDP")
    d_spend = cum_delta("SPEND_GVT")
    return {
        "definition": "cum dGDP / cum dSPEND_GVT, nominal, full simulation",
        "cum_delta_gdp": round(d_gdp, 1),
        "cum_delta_spend": round(d_spend, 1),
        "multiplier": round(d_gdp / d_spend, 2),
        "cum_delta_gdp_real": round(cum_delta("GDP_R"), 1),
        "comparators": {
            "imf_green_spending_multiplier": "1.1-1.5 (Batini et al. 2021)",
            "obr_capital_spending_impact_multiplier": "~1.0",
        },
        "upstream_table_unusable": (
            "Multiplier_Summary.csv M_Impact/M_4Q/M_8Q identical across all "
            "8 scenarios (M_Impact=-32.22); TotalDeltaG=104.22 matches no "
            "variable's cumulative delta in the scenario file"
        ),
    }


def write_artifact(path: str | Path) -> Path:
    """Write baseline_vs_external.csv (committed, regression-tested)."""
    path = Path(path)
    rows = baseline_calibration()
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return path
