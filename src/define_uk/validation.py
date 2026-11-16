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
  (M_Impact = −32.22 everywhere, the common GVT_ENERGY switch) and its
  row labels are shifted by one scenario: TotalDeltaG (104.22) is upstream's
  real G for GPI + Green Bonds, a different impulse from ours (issue #16).
  So we recompute from the delta paths with an explicit, reproducible
  definition. Since 2026-11-15 (issue #16, decided) the headline divides by
  the policy instrument, government power-sector spending SPEND_GVTPS
  (2.30); total non-wage government spending SPEND_GVT (1.78) is kept as a
  secondary ratio.

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
        1.31, "% y/y",
        "ONS quarterly national accounts, uk_gdp_cvm vintage 2026-07-26: "
        "2025 calendar-year mean over 2024 = +1.31%; OBR March 2026 EFO "
        "near-term 1-2%",
    ),
    "real_gdp_growth_mean_2025_2040": (
        1.65, "% y/y mean",
        "OBR long-run growth assumption ~1.5-1.8% (March 2026 EFO)",
    ),
    "unemployment_2025": (
        4.88, "%",
        "ONS MGSX, uk_unemployment_rate vintage 2026-07-26: 2025 quarterly "
        "path 4.6/4.7/5.0/5.2, annual mean 4.88 (annual-mean convention "
        "matches the model column)",
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


# What the multiplier is and is not. Kept as a module constant so the
# hermetic gate can assert it still travels with the number, and so nothing
# quotes 2.30 (or the secondary 1.78) against published multipliers
# without them.
GPI_MULTIPLIER_CAVEATS = (
    "Horizon: this is a CUMULATIVE ratio over the whole simulation to 2040, "
    "not an impact or 1-year multiplier. Published green-spending multipliers "
    "and the OBR capital multiplier (~1.0) are short-horizon figures, so the "
    "comparison is indicative, not like-for-like; a long-horizon cumulative "
    "ratio is expected to sit above them. An IMF range of 1.1-1.5 was "
    "attributed here to 'Batini et al. 2021'; no such publication could be "
    "located, and the only IMF reference this project holds is Batini et al. "
    "(2014), a different paper reporting a different quantity (0-1, first "
    "year, advanced economies). The attribution is withdrawn rather than "
    "repaired, because an unidentifiable citation is worse than none.",
    "Denominator (issue #16, decided 2026-11-15): the headline 2.30 divides "
    "by SPEND_GVTPS, government power-sector spending, which is the variable "
    "the GPI policy switch sets; its cumulative delta is 91.2. It leaves out "
    "the induced responses of other spending, including green public GCF "
    "(GCF_GVTG +17.0, offset by conventional GCF_GVTC -19.3). The secondary "
    "1.78 divides by SPEND_GVT, "
    "total government spending excluding wages, "
    "OCONS_GVT + SOCB_GVT + GCF_GVT + SPEND_GVTPS (Table 6's components "
    "omit SPEND_GVTPS, which is zero at the start: 58.03 + 82.8 + 20.76 = "
    "161.59 against a tabulated 161.6). In the cached GPI + Green Bonds run "
    "its cumulative delta of 118.2 is SPEND_GVTPS +91.2 (government "
    "power-sector spending, most of the policy impulse), OCONS_GVT +21.1, "
    "SOCB_GVT +8.0 and GCF_GVT -2.3 (green GCF_GVTG +17.0 offset by "
    "conventional GCF_GVTC -19.3: the scenario substitutes green for "
    "conventional public investment). The denominator therefore mixes the "
    "impulse with ENDOGENOUS items that RISE in this scenario, so the "
    "direction of its bias against an impulse-based multiplier is not "
    "established. An earlier version of this caveat said social benefits "
    "fall and that 1.78 is upper-leaning; the cached run contradicts both, "
    "and both are withdrawn. cum dGDP / cum dGCF_GVTG is not a usable "
    "impulse ratio either: green GCF is a small, offset share of the "
    "impulse. 1.78 is therefore a ratio per pound of total non-wage "
    "spending, not an impulse multiplier.",
    "Closure: the model is demand-led with a Kaldor-Verdoorn productivity "
    "equation (Eq. (31)), so a demand impulse raises productivity growth "
    "permanently and real GDP is not held to the supply ceiling (Eq. (38)). "
    "A multiplier above 1 over 15 years is what this closure implies rather "
    "than a symptom of an error, which is why the number is labelled and not "
    "corrected.",
    "Parameter mismatch (issue #20): the cached Baseline uses alpha_PPLR = "
    "0.2748 and the GPI + Green Bonds run 0.2762, so the cumulative delta "
    "also carries that parameter change. Treating its effect after 2026 as "
    "zero, as its 2026Q4 level, or as its 2026Q4 share of baseline gives "
    "1.73-1.75 for the policy alone (VALIDATION.md, round 5), and 2.08-2.25 "
    "for the headline 2.30: the SPEND_GVTPS denominator has no pre-2027 "
    "delta to offset the parameter change in the numerator.",
)


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


# Denominators for gpi_multiplier(). Issue #16 (decided 2026-11-15): the
# headline is the impulse definition; total non-wage spending is secondary.
MULTIPLIER_DEFINITIONS = {
    "impulse": (
        "SPEND_GVTPS",
        "cum dGDP / cum dSPEND_GVTPS (government power-sector spending, the "
        "policy instrument), nominal, full simulation",
    ),
    "total_spending": (
        "SPEND_GVT",
        "cum dGDP / cum dSPEND_GVT (total government spending excluding "
        "wages), nominal, full simulation",
    ),
}
HEADLINE_DEFINITION = "impulse"


def gpi_multiplier(definition: str = HEADLINE_DEFINITION) -> dict:
    """Cumulative green-public-investment multiplier, computed by us.

    Cumulative nominal GDP delta over a cumulative nominal spending delta,
    GPI + Green Bonds scenario vs baseline, summed over the full
    simulation. ``definition`` picks the denominator
    (``MULTIPLIER_DEFINITIONS``): "impulse" (the headline since issue #16,
    SPEND_GVTPS, 2.30) or "total_spending" (SPEND_GVT, 1.78). The headline
    result carries the other as ``secondary``. Reported alongside the
    real-GDP cumulative delta so the number is reproducible from the
    scenario file alone.

    Read ``GPI_MULTIPLIER_CAVEATS`` before quoting the number against any
    published figure: this is a full-horizon cumulative ratio (which pushes
    it above a short-horizon multiplier) under a demand-led closure, and
    the cached run's Baseline/policy alpha_PP mismatch (issue #20) sits in
    the numerator.
    """
    if definition not in MULTIPLIER_DEFINITIONS:
        raise ValueError(f"definition must be one of {sorted(MULTIPLIER_DEFINITIONS)}, "
                         f"not {definition!r}")
    root = _run_root() / _TABLES / _BASE_FOLDER
    scen = root / "Variables_GPI + Green Bonds.csv"
    base = root / "Variables_Baseline.csv"

    def cum_delta(var: str) -> float:
        b = _read_column(base, var)
        s = _read_column(scen, var)
        return sum(sv - bv for sv, bv in zip(s, b)
                   if sv is not None and bv is not None)

    d_gdp = cum_delta("GDP")
    var, text = MULTIPLIER_DEFINITIONS[definition]
    d_spend = cum_delta(var)
    out = {
        "definition": text,
        "denominator": var,
        "cum_delta_gdp": round(d_gdp, 1),
        "cum_delta_spend": round(d_spend, 1),
        "multiplier": round(d_gdp / d_spend, 2),
        "cum_delta_gdp_real": round(cum_delta("GDP_R"), 1),
        "comparators": {
            # The IMF "1.1-1.5 (Batini et al. 2021)" entry was withdrawn with
            # the caveat text (no such publication could be located).
            "obr_capital_spending_impact_multiplier": "~1.0",
        },
        "caveats": GPI_MULTIPLIER_CAVEATS,
        "upstream_table_unusable": (
            "Multiplier_Summary.csv M_Impact/M_4Q/M_8Q identical across all "
            "8 scenarios (M_Impact=-32.22: the common GVT_ENERGY switch); its "
            "row labels are shifted by one scenario, so its 'Green Public "
            "Investment' row is GPI + Green Bonds, and TotalDeltaG=104.22 is "
            "upstream's real G (CONS_GVT + GCF_GVT + SPEND_GVTPS at baseline "
            "prices, 104.1 recomputed), a real/real impulse not comparable "
            "with this nominal ratio"
        ),
    }
    if definition == HEADLINE_DEFINITION:
        sec_var, sec_text = MULTIPLIER_DEFINITIONS["total_spending"]
        d_sec = cum_delta(sec_var)
        out["secondary"] = {
            "definition": sec_text,
            "denominator": sec_var,
            "cum_delta_spend": round(d_sec, 1),
            "multiplier": round(d_gdp / d_sec, 2),
        }
    return out


# --- Manual Table 4, all fifteen rows ---------------------------------------
#
# Manual v1.1 Table 4 (p. 50) prints 15 baseline variables at 2025, 2030 and
# 2040 plus their 2025-2040 mean and standard deviation; its note says "All
# quarterly values are annualised and the mean and standard deviation are
# calculated from 2025-2040". Read from the cached run as: annual means of
# the quarterly values; quarterly flows and quarterly rates (EMIS, default
# rates) x 4; mean and SAMPLE sd of the 16 annual values 2025-2040 (this
# reproduces the table's population sd, 1.873 vs 1.87, and labour-force sd,
# 1.003 vs 1.00; the population sd of the same values gives 1.81 and 0.97).
#
# Status per cell (decided 2026-11-16 with the run's decision log, PR body):
#   MATCH          within the stated tolerance;
#   DIVERGENCE     outside any defensible tolerance: pinned at the run's own
#                  observed value so drift fails (a regression pin, NOT
#                  validation);
#   NOT COMPARABLE the table does not state the definition.
TABLE4_YEARS = (2025, 2030, 2040)
TABLE4_STATS = ("2025", "2030", "2040", "mean", "sd")

# row -> (label, published 2025/2030/2040/mean/sd, how to read it from the
#         run, {stat: (status, tolerance_abs)})
_M, _D, _NC = "MATCH", "DIVERGENCE", "NOT COMPARABLE"


def _all(status, tol):
    return {k: (status, tol) for k in TABLE4_STATS}


TABLE4 = {
    "real_gdp_growth_pct": (
        "Real GDP growth (%)", (4.96, 2.35, 2.01, 2.35, 0.71),
        "y/y growth of the annual mean of GDP_R; the +/-0.31pp band was "
        "set at the 2025 miss (0.30pp) in 2026-08, so 2025 is a match only "
        "by construction (2030 exact, 2040 0.06pp)",
        # +/-0.31pp: 2030 is exact, 2040 0.06pp, 2025 0.30pp. No single
        # annualisation convention reproduces all three years (VALIDATION.md
        # target 1a); the band is the 2025 miss, unchanged since 2026-08-04.
        _all(_M, 0.31)),
    "unemployment_pct": (
        "Unemployment (%)", (4.31, 4.73, 4.72, 4.71, 0.14),
        "UPLOT; low-information on the sd: the tolerance exceeds the "
        "series sd (0.14)", _all(_M, 0.2)),
    "population_16plus_m": (
        "Population (millions)", (55.66, 57.74, 61.61, 58.68, 1.87),
        "POP", _all(_M, 0.01)),
    "labour_force_m": (
        "Labour Force (millions)", (35.97, 37.12, 39.13, 37.62, 1.00),
        "LF", _all(_M, 0.01)),
    "non_fossil_electricity_share_pct": (
        "Proportion of non-fossil electricity generation (%)",
        (57.93, 61.77, 77.14, 65.92, 6.35),
        "100 x beta_NFF", _all(_D, None)),
    "emissions_mtco2e_yr": (
        "Total emissions (MtCO2e/year)", (407.32, 381.76, 324.37, 367.10, 25.46),
        "4 x EMIS", _all(_D, None)),
    "emission_price_gbp_t": (
        "Emission price (GBP/tCO2e)", (8.01, 10.58, 15.71, 11.86, 2.44),
        "1000 x P_ETS", _all(_M, 0.01)),
    "green_investment_pct_gdp": (
        "Green investment (% of GDP)", (1.00, 1.07, 1.30, 1.13, 0.10),
        "definition not stated; no combination of the printed green GCF "
        "columns reproduces it", _all(_NC, None)),
    "nfc_default_rate_pct": (
        "NFC default rate (%)", (0.28, 0.33, 0.45, 0.36, 0.05),
        "400 x DEF_NFC (quarterly rate annualised)", _all(_M, 0.02)),
    "nfc_credit_rationing_pct": (
        "NFC credit rationing (%)", (3.81, 2.56, 4.79, 3.49, 0.74),
        "100 x CR_NFC; matches to 2030, diverges after (mean and sd carry "
        "the 2040 miss)",
        {"2025": (_M, 0.25), "2030": (_M, 0.25), "mean": (_D, None),
         "2040": (_D, None), "sd": (_D, None)}),
    "ps_default_rate_pct": (
        "Power sector default rate (%)", (0.16, 0.11, 0.13, 0.12, 0.01),
        "400 x DEF_PS (quarterly rate annualised)", _all(_D, None)),
    "ps_credit_rationing_pct": (
        "Power sector credit rationing (%)", (47.22, 35.44, 21.09, 30.64, 9.04),
        "100 x CR_PS; the means agree (30.15 vs 30.64) but the trends are "
        "opposite, so the mean is not read as a match", _all(_D, None)),
    "imports_pct_gdp": (
        "Imports (% of GDP)", (39.99, 39.97, 41.18, 40.31, 0.51),
        "100 x IMP / GDP", _all(_D, None)),
    "exports_pct_gdp": (
        "Exports (% of GDP)", (38.58, 40.19, 44.15, 41.21, 1.80),
        "100 x EXP / GDP", _all(_D, None)),
    "reer_index": (
        "Real effective exchange rate (index, 2022 = 1)",
        (1.00, 1.00, 0.98, 0.99, 0.01),
        "REER; low-information match: the tolerance is twice the series sd",
        _all(_M, 0.02)),
}


def _table4_series() -> dict[str, dict[int, float] | None]:
    """Annual values 2024-2040 of every Table 4 row, from the cached run."""
    base = _baseline_path()

    def ann(var, scale=1.0):
        a = _annual_means(_read_column(base, var))
        return {y: scale * v for y, v in a.items() if v is not None}

    gdp_r, gdp = ann("GDP_R"), ann("GDP")
    imp, exp_ = ann("IMP"), ann("EXP")
    return {
        "real_gdp_growth_pct": {
            y: 100.0 * (gdp_r[y] / gdp_r[y - 1] - 1.0)
            for y in gdp_r if y - 1 in gdp_r},
        "unemployment_pct": ann("UPLOT"),
        "population_16plus_m": ann("POP"),
        "labour_force_m": ann("LF"),
        "non_fossil_electricity_share_pct": ann("beta_NFF", 100.0),
        "emissions_mtco2e_yr": ann("EMIS", 4.0),
        "emission_price_gbp_t": ann("P_ETS", 1000.0),
        "green_investment_pct_gdp": None,
        "nfc_default_rate_pct": ann("DEF_NFC", 400.0),
        "nfc_credit_rationing_pct": ann("CR_NFC", 100.0),
        "ps_default_rate_pct": ann("DEF_PS", 400.0),
        "ps_credit_rationing_pct": ann("CR_PS", 100.0),
        "imports_pct_gdp": {y: 100.0 * imp[y] / gdp[y] for y in imp if y in gdp},
        "exports_pct_gdp": {y: 100.0 * exp_[y] / gdp[y] for y in exp_ if y in gdp},
        "reer_index": ann("REER"),
    }


def table4_scorecard() -> list[dict]:
    """Every cell of manual Table 4 against the cached run, with a status.

    One row per (variable, statistic): published value, run value, gap
    (run - published), status (MATCH / DIVERGENCE / NOT COMPARABLE),
    tolerance (MATCH cells only) and how the run value is read. The
    committed copy is validation/table4_scorecard.csv; regenerate it with
    ``python -m define_uk.validation --table4`` after a deliberate change.
    """
    import statistics

    series = _table4_series()
    rows = []
    for key, (label, published, how, status) in TABLE4.items():
        s = series[key]
        run = {}
        if s is not None:
            years = [s[y] for y in range(2025, 2041)]
            run = {str(y): s[y] for y in TABLE4_YEARS}
            run["mean"] = statistics.mean(years)
            run["sd"] = statistics.stdev(years)
        for stat, pub in zip(TABLE4_STATS, published):
            st_, tol = status[stat]
            value = run.get(stat)
            rows.append({
                "variable": key,
                "label": label,
                "statistic": stat,
                "published": pub,
                "run": None if value is None else round(value, 3),
                "gap": None if value is None else round(value - pub, 3),
                "status": st_,
                "tolerance_abs": tol,
                "how_read": how,
            })
    return rows


def write_table4_scorecard(path: str | Path) -> Path:
    """Write validation/table4_scorecard.csv (committed, regression-tested)."""
    path = Path(path)
    rows = table4_scorecard()
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: "" if v is None else v for k, v in r.items()})
    return path


def write_artifact(path: str | Path) -> Path:
    """Write baseline_vs_external.csv (committed, regression-tested)."""
    path = Path(path)
    rows = baseline_calibration()
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return path


if __name__ == "__main__":  # explicit regeneration of the committed artifacts
    import sys

    root = Path(__file__).resolve().parents[2] / "validation"
    if "--table4" in sys.argv:
        print(write_table4_scorecard(root / "table4_scorecard.csv"))
    else:
        print("usage: python -m define_uk.validation --table4")
