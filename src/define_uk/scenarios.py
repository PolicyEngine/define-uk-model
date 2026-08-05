"""Curated scenario surface over the cached DEFINE-UK upstream run.

Reads the CACHED outputs of the pinned upstream run (``define_uk.runner.run``)
and exposes scenario *deltas vs the same folder's baseline* — never levels as
forecasts. The registry below enumerates every ``Variables_<Scenario>.csv``
produced by the pinned commit's four scenario blocks; the power-sector block
is run under five expectation regimes (mutual trust, poor credibility, false
confidence, no forward guidance, unexpected enforcement), of which "mutual
trust" is treated as the canonical variant and the others carry an explicit
``__<variant>`` suffix.

Framing is mandatory: every result carries ``result_type="scenario deltas"``
and the caveats recorded in VALIDATION.md. Baseline LEVELS are not validated
against outturns (2025 GDP growth in the baseline is ~5% vs ~1% outturn);
only deltas are meaningful, under the model's demand-led closure.

This module never runs R. If no cached run exists it raises with
instructions to produce one.
"""

from __future__ import annotations

import csv
import datetime
from pathlib import Path

from .upstream import UPSTREAM_COMMIT, cache_dir

START_YEAR = 1987  # run anchored 1987Q1-2040Q4 (216 quarters); see tests.
N_QUARTERS = 216
DEFAULT_VARIABLES = ("GDP_R", "EMIS", "UPLOT", "CONS_R")

CAVEATS = [
    "Experimental: scenario outputs are gated against the pinned oracle "
    "run, the manual's published scenario definitions (exact policy-switch "
    "sets), and two coarse anchors from the FMM 2023 paper vintage; no "
    "numeric scenario results are published for v1.1, so a full published-"
    "figure replication is not possible (VALIDATION.md targets 2/3).",
    "Deltas only: baseline LEVELS are not validated against outturns "
    "(e.g. baseline 2025 real GDP growth ~5% vs ~1% outturn) and must "
    "never be presented as forecasts.",
    "Demand-led closure: DEFINE-UK is a demand-led ecological SFC model; "
    "multipliers sit above mainstream estimates (VALIDATION.md).",
    "Emissions vintage divergence: the pinned commit's baseline EMIS path "
    "runs below the manual's Table 4, widening with horizon "
    "(VALIDATION.md target 1b); emission deltas share that vintage.",
    "Unlicensed upstream: results come from a locally cached run of the "
    "upstream R code at a pinned commit; nothing is redistributed.",
]

_TABLES = "output/tables"

# (public name, block, csv folder relative to output/tables, csv scenario
#  label, description). Folder Baseline is the delta reference.
_REGISTRY: list[tuple[str, str, str, str, str]] = [
    (
        "green_public_investment",
        "gvt_investment",
        "gvt_investment",
        "GPI + Green Bonds",
        "Green public investment programme financed with green bonds.",
    ),
    (
        "green_power_subsidy",
        "gvt_investment",
        "gvt_investment",
        "Green Power Subsidy",
        "Government subsidy to green power-sector investment.",
    ),
    (
        "housing_regulation",
        "housing_regulation",
        "housing_regulation",
        "Housing Regulation",
        "Energy-efficiency regulation of the housing stock.",
    ),
    (
        "housing_regulation_subsidy",
        "housing_regulation",
        "housing_regulation",
        "Housing Regulation + Subsidy",
        "Housing energy-efficiency regulation combined with a retrofit "
        "subsidy.",
    ),
    (
        "mixed_fossil_fuel_ban_subsidy",
        "mixed",
        "mixed/mutual_trust",
        "Fossil Fuel Ban + Subsidy",
        "Power-sector fossil-fuel ban plus subsidy, in the mixed-policy "
        "block (mutual-trust expectations).",
    ),
    (
        "mixed_housing_regulation_subsidy",
        "mixed",
        "mixed/mutual_trust",
        "Housing Regulation + Subsidy",
        "Housing regulation plus subsidy, in the mixed-policy block "
        "(mutual-trust expectations).",
    ),
    (
        "mixed_both_regulations_subsidies",
        "mixed",
        "mixed/mutual_trust",
        "Both Regulations + Subsidies",
        "Combined power-sector and housing regulations with subsidies "
        "(mutual-trust expectations).",
    ),
]

_PSR_SCENARIOS = [
    ("fossil_fuel_ban", "Fossil Fuel Ban",
     "Regulatory ban on fossil-fuel electricity generation"),
    ("power_sector_subsidy", "Power Sector Subsidy",
     "Subsidy to renewable power-sector investment"),
    ("fossil_fuel_ban_subsidy", "Fossil Fuel Ban + Subsidy",
     "Fossil-fuel ban combined with a renewables subsidy"),
]
_PSR_VARIANTS = [
    ("mutual_trust", "mutual-trust expectations (canonical)"),
    ("poor_credibility", "poor-credibility expectations"),
    ("false_confidence", "false-confidence expectations"),
    ("no_forward_guidance", "no forward guidance"),
    ("unexpected_enforcement", "unexpected enforcement"),
]
for _variant, _vdesc in _PSR_VARIANTS:
    _suffix = "" if _variant == "mutual_trust" else f"__{_variant}"
    for _name, _label, _desc in _PSR_SCENARIOS:
        _REGISTRY.append(
            (
                _name + _suffix,
                "power_sector_regulation",
                f"power_sector_regulation/{_variant}",
                _label,
                f"{_desc}, under {_vdesc}.",
            )
        )

_BY_NAME = {entry[0]: entry for entry in _REGISTRY}


def list_scenarios() -> list[dict]:
    """Curated registry: [{name, block, description}, ...]."""
    return [
        {"name": name, "block": block, "description": desc}
        for name, block, _folder, _label, desc in _REGISTRY
    ]


def _run_root() -> Path:
    root = Path(cache_dir()) / UPSTREAM_COMMIT
    if not (root / _TABLES).is_dir():
        raise FileNotFoundError(
            f"no cached DEFINE-UK run at {root / _TABLES}. Produce one "
            "locally with define_uk.runner.run() (requires R and the "
            "upstream dependency set); run_scenario never runs R itself."
        )
    return root


def _read_column(path: Path, variable: str) -> list[float | None]:
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != N_QUARTERS:
        raise ValueError(f"{path}: expected {N_QUARTERS} rows, got {len(rows)}")
    if variable not in rows[0]:
        raise KeyError(f"variable {variable!r} not in {path.name}")
    return [
        float(r[variable]) if r[variable] not in ("", "NA") else None
        for r in rows
    ]


def _annual_means(quarterly: list[float | None]) -> dict[int, float | None]:
    out: dict[int, float | None] = {}
    for i in range(N_QUARTERS // 4):
        vals = [v for v in quarterly[4 * i : 4 * i + 4] if v is not None]
        out[START_YEAR + i] = sum(vals) / len(vals) if len(vals) == 4 else None
    return out


def run_scenario(
    name: str,
    variables: tuple[str, ...] = DEFAULT_VARIABLES,
    horizon_years: int = 15,
) -> dict:
    """Annualised scenario-minus-baseline delta paths from the cached run.

    Returns, per variable, level deltas and % deltas (relative to the same
    folder's baseline annual mean; for rates such as UPLOT the level delta
    is already in the rate's own units). The horizon starts at the first
    calendar year in which any requested variable departs from baseline.
    """
    if name not in _BY_NAME:
        known = ", ".join(sorted(_BY_NAME))
        raise KeyError(f"unknown scenario {name!r}; known: {known}")
    _, block, folder, label, description = _BY_NAME[name]
    root = _run_root()
    scen_path = root / _TABLES / folder / f"Variables_{label}.csv"
    base_path = root / _TABLES / folder / "Variables_Baseline.csv"
    for p in (scen_path, base_path):
        if not p.exists():
            raise FileNotFoundError(
                f"cached run is missing {p}; re-run define_uk.runner.run()"
            )

    annual: dict[str, dict] = {}
    start_year: int | None = None
    for var in variables:
        base = _annual_means(_read_column(base_path, var))
        scen = _annual_means(_read_column(scen_path, var))
        deltas = {
            y: scen[y] - base[y]
            for y in base
            if base[y] is not None and scen[y] is not None
        }
        first = next(
            (y for y in sorted(deltas) if abs(deltas[y]) > 1e-12), None
        )
        if first is not None:
            start_year = first if start_year is None else min(start_year, first)
        annual[var] = {"base": base, "delta": deltas}

    if start_year is None:
        raise ValueError(
            f"scenario {name!r} shows no departure from baseline in "
            f"{variables}; check the cached run"
        )
    years = [
        y
        for y in range(start_year, start_year + horizon_years)
        if y <= START_YEAR + N_QUARTERS // 4 - 1
    ]

    per_variable = {}
    for var in variables:
        delta = annual[var]["delta"]
        base = annual[var]["base"]
        levels = [delta.get(y) for y in years]
        pct = [
            100 * delta[y] / base[y]
            if y in delta and base[y] not in (None, 0)
            else None
            for y in years
        ]
        per_variable[var] = {"delta_level": levels, "delta_pct": pct}

    return {
        "result_type": "scenario deltas",
        "scenario": name,
        "block": block,
        "description": description,
        "delta_convention": "scenario minus baseline (same block folder)",
        "years": years,
        "variables": per_variable,
        "caveats": list(CAVEATS),
        "provenance": {
            "upstream_commit": UPSTREAM_COMMIT,
            "cache_path": str(scen_path),
            "baseline_path": str(base_path),
            "r_run_date": datetime.date.fromtimestamp(
                scen_path.stat().st_mtime
            ).isoformat(),
        },
    }
