"""Curated scenario surface over the cached DEFINE-UK upstream run.

Reads the CACHED outputs of the pinned upstream run (``define_uk.runner.run``)
and exposes scenario *deltas vs the same folder's baseline* — never levels as
forecasts. The registry below enumerates every ``Variables_<Scenario>.csv``
produced by the pinned commit's four scenario blocks; the power-sector block
is run under five expectation regimes (mutual trust, poor credibility, false
confidence, no forward guidance, unexpected enforcement), of which "mutual
trust" is treated as the canonical variant and the others carry an explicit
``__<variant>`` suffix.

The regimes are parameter sets, read from the cached
``Parameters-sorted_*.csv`` files (``EXPECTATION_REGIMES``), and they are set
only in the scenarios that contain the fossil-fuel ban. Six of the 22
registered names therefore have no path of their own: they are the same
cached solve as another name (``IDENTICAL_TO``; 16 distinct solves). See
docs/scenario-notes.md.

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
import functools
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
    "Demand-led closure: DEFINE-UK is a demand-led ecological SFC model, "
    "so demand impulses have lasting output effects (Kaldor-Verdoorn "
    "productivity, Eq. (31)). Its cumulative GPI multiplier is back-loaded: "
    "below 1 for the first five years from the policy start, 2.25 by 2040 "
    "(define_uk.validation.gpi_multiplier, horizon_profile).",
    "Subsidies lower real GDP in this run: every scenario with a subsidy "
    "has a negative cumulative real GDP delta over 2027-2040 (green power "
    "subsidy -47 against +252 for green public investment with a similar "
    "spending path; housing regulation with subsidy -150 against -104 "
    "without; GBP bn at 2022 prices, quarterly flows summed). The cached "
    "outputs show the contraction through consumption and imports; the "
    "mechanism is not confirmed and is drafted as a query to the authors "
    "(VALIDATION.md, upstream queries). Treat subsidy GDP deltas with care.",
    "Emissions divergence: the pinned commit's baseline EMIS path runs "
    "below the manual's Table 4 (-23% by 2040), along with the rest of the "
    "power and energy block; consistent with, but not proof of, a different "
    "model vintage (VALIDATION.md target 1b). Emission deltas come from "
    "this run, so % deltas are relative to its lower baseline.",
    "Unlicensed upstream: results come from a locally cached run of the "
    "upstream R code at a pinned commit; nothing is redistributed.",
    "Parameter mismatch (issue #20): the cached run's Baseline files use "
    "alpha_PPLR = 0.2748 and every policy file 0.2762, so every "
    "scenario-minus-baseline delta also carries that parameter change. No "
    "policy acts before 2027Q1, so 2023-2026 deltas are that change alone "
    "(real GDP -0.10% to -0.17% of baseline in 2025-26), not policy effects; "
    "from 2027 the two cannot be separated (VALIDATION.md, round 5). "
    "Served paths therefore start at policy_start_year by default; the "
    "pre-policy years are returned only with include_pre_policy=True and "
    "are flagged policy_active=False. policy_active=True means a policy "
    "switch is on, not that the delta is the policy effect alone "
    "(baseline_parameter_mismatch).",
]

# Machine-readable form of the issue #20 caveat, attached to every result.
BASELINE_PARAMETER_MISMATCH = {
    "parameter": "alpha_PPLR",
    "baseline_files": 0.2748,
    "policy_files": 0.2762,
    "issue": "PolicyEngine/define-uk-model#20",
    "affects": "every served year, including policy_active years; "
               "inseparable from the policy effect from policy_start_year on",
}

_TABLES = "output/tables"

# Parameters a scenario may set away from its Baseline: the policy switches
# of the manual's scenario descriptions and the expectation-regime switches
# (EXPECTATION_REGIMES). The exact set each scenario toggles is gated in
# tests/test_scenario_design.py; this is their union. A delta is a policy
# effect only if nothing outside this set differs between the scenario's
# parameter row and its Baseline's.
POLICY_LEVERS = frozenset({
    # green public investment and its financing
    "GVT_INVEST", "GREEN_BONDS", "GREEN_POWER", "CO_NFF", "sh_rGVTNMFIG",
    # power-sector regulation and subsidy
    "FF_BAN", "FF_CAP_BAN", "FF_INV_BAN", "TRANS_PASS", "TTRANS", "POWER_SUB",
    # housing regulation and subsidy
    "HENBAN", "HIBAN", "HSELL", "THENBAN", "THIBAN", "TTRANSH",
    "HOUSING_SUB", "HOUSING_SUB_RATE",
    # expectation regimes
    "CRED", "GVT_CRED", "ELEC_BUFFER",
})

# Non-lever parameters known to differ between the pinned run's Baseline and
# policy files, each with the issue that sizes it. A scenario whose only
# non-lever differences are listed here is served with the caveat; any other
# non-lever difference is refused (BaselineParameterMismatch), because an
# unsized parameter change inside a delta is not a policy result.
KNOWN_PARAMETER_MISMATCHES = {"alpha_PPLR": "PolicyEngine/define-uk-model#20"}


class BaselineParameterMismatch(ValueError):
    """A scenario and its Baseline differ in a parameter that is neither a
    policy lever nor a documented mismatch, so the scenario-minus-baseline
    delta is not the effect of the policy."""

    def __init__(self, message: str, *, scenario: str, parameter_check: dict):
        super().__init__(message)
        self.scenario = scenario
        self.parameter_check = parameter_check


def _parameter_row(path: Path) -> dict[str, str]:
    """One cached ``Parameters-sorted_*.csv``: {parameter: printed value}."""
    with path.open(newline="") as fh:
        rows = list(csv.reader(fh))
    if len(rows) < 2:
        raise ValueError(f"{path}: expected a header and one parameter row")
    return {h.strip(): v.strip() for h, v in zip(rows[0][1:], rows[1][1:])}


def _same_value(a: str, b: str) -> bool:
    if a == b:
        return True
    try:
        return float(a) == float(b)
    except ValueError:
        return False


def parameter_check(scenario_params: Path, baseline_params: Path) -> dict:
    """Compare a scenario's parameter row with its Baseline's.

    Returns {checked, levers, non_lever, undocumented, shared_except_levers,
    passed}. ``levers`` and ``non_lever`` map each differing parameter to
    {"baseline", "scenario"} (printed values; None where a file does not
    print the parameter). ``shared_except_levers`` is the property a delta
    needs to be a policy effect: nothing outside ``POLICY_LEVERS`` differs.
    ``undocumented`` lists the non-lever differences that are not in
    ``KNOWN_PARAMETER_MISMATCHES``; ``passed`` is False if there are any.

    If either file is missing the comparison cannot be made: ``checked`` is
    False and ``shared_except_levers`` and ``passed`` are None (unknown),
    never True.
    """
    if not (scenario_params.exists() and baseline_params.exists()):
        return {
            "checked": False, "levers": {}, "non_lever": {},
            "undocumented": [], "shared_except_levers": None, "passed": None,
        }
    scen, base = _parameter_row(scenario_params), _parameter_row(baseline_params)
    levers: dict[str, dict] = {}
    non_lever: dict[str, dict] = {}
    for name in sorted(set(scen) | set(base)):
        b, s = base.get(name), scen.get(name)
        if b is not None and s is not None and _same_value(b, s):
            continue
        (levers if name in POLICY_LEVERS else non_lever)[name] = {
            "baseline": b, "scenario": s,
        }
    undocumented = [k for k in non_lever if k not in KNOWN_PARAMETER_MISMATCHES]
    return {
        "checked": True,
        "levers": levers,
        "non_lever": non_lever,
        "undocumented": undocumented,
        "shared_except_levers": not non_lever,
        "passed": not undocumented,
    }

# Stock-flow consistency gate. LEND is the sum of the sectors' net lending
# (households, NFC, MFI, NMFI, government, RoW, power sector), the model's
# redundant equation: in a consistent solve it is zero to rounding (|LEND| <
# 1e-5 in every quarter of 28 of the 30 cached files). Two cached solves break
# it: the fossil-fuel ban under no forward guidance (2035Q3 and 2036Q1, |LEND|
# up to 74.56) and under unexpected enforcement (2033Q1, 14.63). Deltas from
# such a solve are not results, so run_scenario refuses them by default.
#
# Cause (diagnosed 2026-11-06 from the cached outputs alone): in exactly those
# three quarters, and in no other quarter of any of the 30 files, the power
# sector's gross output is not GO_PSR * P_ELEC (manual Eq. (74)). GO_PS is
# valued at the long-run price P_ELECLR while every buyer of electricity
# (households, Eq. (CONS_HHPS); production's intermediate consumption) pays
# P_ELEC. The gap GO_PSR*P_ELEC - GO_PS is 122.54, 81.79 and 24.03, and LEND
# is -0.61 times it in all three. The quarters are the ones where the
# fossil-fuel ban pushes generation against capacity (E_ELEC at or near
# E_ELECMAX), i.e. the electricity price changes regime (manual §3.3.2
# footnote 22), and the upstream solve leaves the seller and the buyers on
# different sides of the switch. The break is in the upstream output, not in
# this check, so the refusal stands; ``sfc_check`` reports the gap.
SFC_TOLERANCE = 0.01  # GBP bn per quarter, far above CSV rounding of a zero


class StockFlowInconsistent(ValueError):
    """A cached solve violates the redundant equation (sectoral net lending
    does not sum to zero) or its stock counterpart (sectoral financial net
    worth does not sum to zero), so its deltas cannot be served as results.
    ``scenario`` and ``sfc_check`` carry the name and both files' checks."""

    def __init__(self, message: str, *, scenario: str | None = None,
                 sfc_check: dict | None = None):
        super().__init__(message)
        self.scenario = scenario
        self.sfc_check = sfc_check


def _sfc_detail(failed: dict) -> str:
    parts = []
    for k, c in failed.items():
        if c["failing_quarters"]:
            parts.append(
                f"{k}: |LEND| up to {c['max_abs']:.2f} in "
                + ", ".join(c["failing_quarters"]))
        if c["stock"]["passed"] is False:
            parts.append(
                f"{k}: |FNW| up to {c['stock']['max_abs']:.2f} from "
                f"{c['stock']['failing_from']} "
                f"({c['stock']['n_failing_quarters']} quarters)")
    return "; ".join(parts)


SIM_START_ROW = 144  # 2023Q1, the first simulated quarter (row 0 = 1987Q1)


def _quarter(i: int) -> str:
    return f"{START_YEAR + i // 4}Q{i % 4 + 1}"


def sfc_check(path: Path, tolerance: float = SFC_TOLERANCE) -> dict:
    """Stock-flow consistency check on one cached Variables CSV.

    Flow side, the redundant equation: |LEND| (the sum of sectoral net
    lending) within the tolerance in every quarter. Stock side: |FNW| (the
    sum of sectoral financial net worth) within the same tolerance in every
    quarter. A simulated quarter that prints neither value fails.

    Returns {variable, tolerance, max_abs, failing_quarters,
    electricity_valuation_gap, stock, flow_passed, passed}.
    failing_quarters are the 'YYYYQn' labels where the flow side fails and
    electricity_valuation_gap maps each of them to GO_PSR*P_ELEC - GO_PS (see
    the note on SFC_TOLERANCE). ``stock`` is {variable, available, max_abs,
    failing_from, n_failing_quarters, passed}: a flow break is carried in
    the stocks of every later quarter, so the stock side reports the first
    failing quarter and how many fail. ``passed`` needs both sides; a file
    with no FNW column passes on the flow side alone (``stock["available"]``
    False).
    """
    lend = _read_column(path, "LEND")
    # A simulated quarter that prints no LEND cannot be shown consistent, so
    # it fails (the data years, where the upstream prints none, are not
    # checked).
    failing_idx = [
        i for i, v in enumerate(lend)
        if (v is None and i >= SIM_START_ROW)
        or (v is not None and abs(v) > tolerance)
    ]
    failing = [_quarter(i) for i in failing_idx]
    # Stock side: the sectors' financial net worth sums to zero (FNW, the
    # balance-sheet matrix's bottom row, manual Table 2), since every
    # financial asset is another sector's liability.
    try:
        fnw = _read_column(path, "FNW")
    except KeyError:
        stock = {"variable": "FNW (sum of sectoral financial net worth)",
                 "available": False, "max_abs": None,
                 "failing_from": None, "n_failing_quarters": None,
                 "passed": None}
    else:
        bad = [
            i for i, v in enumerate(fnw)
            if (v is None and i >= SIM_START_ROW)
            or (v is not None and abs(v) > tolerance)
        ]
        stock = {
            "variable": "FNW (sum of sectoral financial net worth)",
            "available": True,
            "max_abs": max((abs(v) for v in fnw if v is not None), default=None),
            "failing_from": _quarter(bad[0]) if bad else None,
            "n_failing_quarters": len(bad),
            "passed": not bad,
        }
    gap: dict[str, float] = {}
    if failing_idx:
        go, go_r, p = (_read_column(path, v) for v in ("GO_PS", "GO_PSR", "P_ELEC"))
        gap = {
            q: round(go_r[i] * p[i] - go[i], 4)
            for q, i in zip(failing, failing_idx)
            if None not in (go[i], go_r[i], p[i])
        }
    return {
        "variable": "LEND (sum of sectoral net lending)",
        "tolerance": tolerance,
        "max_abs": max((abs(v) for v in lend if v is not None), default=None),
        "failing_quarters": failing,
        # GO_PSR*P_ELEC - GO_PS (manual Eq. (74)) in each failing quarter:
        # the diagnosed source of every break in the pinned run.
        "electricity_valuation_gap": gap,
        # The stock side of the same check (None per field if the file
        # prints no FNW column).
        "stock": stock,
        "flow_passed": not failing,
        "passed": not failing and stock["passed"] is not False,
    }

# Units of ``delta_level``. Every series is the annual MEAN of the quarterly
# values, so flows are per-QUARTER rates: an EMIS delta of -10 is -40
# MtCO2e/yr (define_uk.validation multiplies EMIS by 4 for the same reason).
VARIABLE_UNITS = {
    "GDP_R": "real GDP, GBP billion at 2022 prices per quarter (manual "
             "Table 6; annual mean of the quarterly flow, multiply by 4 for "
             "a yearly total); delta_pct is % of baseline",
    "CONS_R": "real household consumption, GBP billion at 2022 prices per "
              "quarter (manual Table 6; annual mean of the quarterly flow); "
              "delta_pct is % of baseline",
    "EMIS": "MtCO2e per QUARTER (annual mean of the quarterly flow); multiply "
            "delta_level by 4 for MtCO2e per year",
    "EMIS_ELEC": "electricity-generation emissions, MtCO2e per QUARTER (x4 "
                 "per year); EMIS = EMIS_ELEC + EMIS_NELEC",
    "EMIS_NELEC": "non-electricity emissions (direct energy use), MtCO2e per "
                  "QUARTER (x4 per year); EMIS = EMIS_ELEC + EMIS_NELEC",
    "UPLOT": "unemployment rate in %, so delta_level is in percentage points; "
             "delta_pct is % of the baseline RATE, not pp",
}

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

# What each expectation regime is, as the cached Parameters-sorted_*.csv
# files of the two fossil-fuel-ban scenarios print it. CRED is the manual's
# perceived-credibility weight in Eq. (89). GVT_CRED and ELEC_BUFFER are not
# named in the manual; what GVT_CRED does is read from the cached outputs:
# fossil generation capital K_PSFFR is zero from 2032Q1 (the FF_CAP_BAN
# quarter) in every ban file with GVT_CRED = 1 and in none with GVT_CRED = 0
# (tests/test_scenario_sweep.py). Mutual trust is the Baseline's own values.
EXPECTATION_REGIMES = {
    "mutual_trust": {"CRED": 0.9, "GVT_CRED": 1, "ELEC_BUFFER": 0},
    "poor_credibility": {"CRED": 0.3, "GVT_CRED": 0, "ELEC_BUFFER": 0},
    "false_confidence": {"CRED": 0.9, "GVT_CRED": 0, "ELEC_BUFFER": 0},
    "no_forward_guidance": {"CRED": 0.0, "GVT_CRED": 1, "ELEC_BUFFER": 0},
    "unexpected_enforcement": {"CRED": 0.3, "GVT_CRED": 1, "ELEC_BUFFER": 0.05},
}

# Registered names that are the same cached solve as another name: the two
# Variables_*.csv files are byte-identical and so are their parameter rows
# (tests/test_scenario_sweep.py checks both against the cache).
#  - Power Sector Subsidy: the regime switches above are set only in the
#    scenarios that contain the ban, so the subsidy-only row is one parameter
#    set, and one solve, under five folder labels.
#  - The mixed block re-uses the single-policy solves for its two
#    single-policy members.
IDENTICAL_TO = {
    **{
        f"power_sector_subsidy__{variant}": "power_sector_subsidy"
        for variant, _ in _PSR_VARIANTS[1:]
    },
    "mixed_fossil_fuel_ban_subsidy": "fossil_fuel_ban_subsidy",
    "mixed_housing_regulation_subsidy": "housing_regulation_subsidy",
}
_IDENTICAL_NOTE = (
    "Same cached solve as {other!r}: the two output files are byte-identical "
    "and their parameter rows are the same, so this name adds no result "
    "(docs/scenario-notes.md)."
)


def _description(name: str, desc: str) -> str:
    other = IDENTICAL_TO.get(name)
    if other is None:
        return desc
    if name.startswith("power_sector_subsidy__"):
        return (
            f"{desc} The expectation regime is not applied to this scenario "
            f"in the cached run: it is the same solve as {other!r}."
        )
    return f"{desc} The same solve as {other!r}."


def list_scenarios() -> list[dict]:
    """Curated registry: [{name, block, description, identical_to}, ...].

    ``identical_to`` is None, or the name of the scenario whose cached solve
    this one duplicates (``IDENTICAL_TO``).
    """
    return [
        {
            "name": name,
            "block": block,
            "description": _description(name, desc),
            "identical_to": IDENTICAL_TO.get(name),
        }
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


# A quarter is capacity-constrained when generation sits at the power
# sector's capacity ceiling, E_ELEC = E_ELECMAX to printing precision (two
# 4-s.f. values: ratio >= 0.999). That is the regime in which the two
# refused fossil-fuel-ban solves break stock-flow consistency, and served
# scenarios reach it too (fossil_fuel_ban_subsidy__no_forward_guidance,
# 2032: GDP -5.7%, electricity price doubling). Flagged per year.
CAPACITY_RATIO = 0.999


def _capacity_years(path: Path) -> set[int]:
    try:
        gen, cap = _read_column(path, "E_ELEC"), _read_column(path, "E_ELECMAX")
    except KeyError:  # a file without the power block cannot be checked
        return set()
    return {
        START_YEAR + t // 4
        for t, (e, m) in enumerate(zip(gen, cap))
        if e is not None and m and e >= CAPACITY_RATIO * m
    }


@functools.lru_cache(maxsize=4)
def _policy_start_year(root: str) -> int | None:
    """First calendar year in which any policy acts, read from the cache.

    Every policy file of the pinned run shares one pre-policy path (they are
    identical, every column, until a switch acts; see
    tests/test_alpha_pp_confound.py). The first quarter in which they stop
    being identical is the policy start: 2027Q1 in the pinned run, where all
    14 distinct policy families depart at once. Read from the cached files,
    not hard-coded; None if fewer than two policy files are cached (then the
    caller falls back to the first departure from baseline). Returns the
    year of that quarter; the quarter is the first of its year in the
    pinned run, so no served year mixes pre-policy and policy quarters.
    """
    paths = []
    for _, _, folder, label, _ in _REGISTRY:
        path = Path(root) / _TABLES / folder / f"Variables_{label}.csv"
        if path.exists() and path not in paths:
            paths.append(path)
    if len(paths) < 2:
        return None
    rows = []
    for path in paths:
        with path.open(newline="") as fh:
            rows.append(list(csv.reader(fh))[1:])
    for t in range(min(len(r) for r in rows)):
        if len({tuple(r[t]) for r in rows}) > 1:
            return START_YEAR + t // 4
    return None


def run_scenario(
    name: str,
    variables: tuple[str, ...] = DEFAULT_VARIABLES,
    horizon_years: int = 15,
    allow_inconsistent: bool = False,
    include_pre_policy: bool = False,
    allow_parameter_mismatch: bool = False,
) -> dict:
    """Annualised scenario-minus-baseline delta paths from the cached run.

    Returns, per variable, level deltas and % deltas (relative to the same
    folder's baseline annual mean; for rates such as UPLOT the level delta
    is already in the rate's own units).

    The horizon starts at ``policy_start_year``, the first year any policy
    acts (2027 in the pinned run). Every cached scenario departs from its
    baseline earlier, in 2023, but only because of the Baseline/policy
    alpha_PP mismatch (issue #20): those pre-policy years carry no policy.
    ``include_pre_policy=True`` starts at the first departure instead (2023)
    and the result's per-year ``policy_active`` flags mark which years have
    a policy on. ``baseline_parameter_mismatch`` says that the mismatch
    persists in every year.

    Raises ``BaselineParameterMismatch`` if the scenario's cached parameter
    row differs from its Baseline's in a parameter that is neither a policy
    lever (``POLICY_LEVERS``) nor a documented mismatch
    (``KNOWN_PARAMETER_MISMATCHES``, today alpha_PPLR alone); see
    ``parameter_check``, returned under ``parameter_check``.
    ``allow_parameter_mismatch=True`` returns the deltas anyway, for
    diagnosis only, with a leading caveat.

    Raises ``StockFlowInconsistent`` if the scenario or its baseline breaks
    the redundant equation (see ``sfc_check``). ``allow_inconsistent=True``
    returns the deltas anyway, for diagnosis only, with the failed check in
    ``sfc_check`` and a leading caveat.
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
    params = parameter_check(
        scen_path.with_name(f"Parameters-sorted_{label}.csv"),
        base_path.with_name("Parameters-sorted_Baseline.csv"),
    )
    if params["undocumented"] and not allow_parameter_mismatch:
        detail = ", ".join(
            f"{k} (baseline {v['baseline']}, scenario {v['scenario']})"
            for k, v in params["non_lever"].items()
            if k in params["undocumented"]
        )
        raise BaselineParameterMismatch(
            f"scenario {name!r}: its cached parameters differ from the "
            f"Baseline's outside the policy levers: {detail}. The delta "
            "would carry that change as well as the policy, so it is not "
            "served",
            scenario=name, parameter_check=params,
        )
    checks = {"scenario": sfc_check(scen_path), "baseline": sfc_check(base_path)}
    failed = {k: c for k, c in checks.items() if not c["passed"]}
    if failed and not allow_inconsistent:
        raise StockFlowInconsistent(
            f"scenario {name!r}: the cached solve is not stock-flow "
            f"consistent ({_sfc_detail(failed)}); its deltas are not served",
            scenario=name, sfc_check=checks,
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
    policy_start = _policy_start_year(str(root))
    if policy_start is not None and not include_pre_policy:
        start_year = max(start_year, policy_start)
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
        per_variable[var] = {
            "delta_level": levels,
            "delta_pct": pct,
            "units": VARIABLE_UNITS.get(
                var, "model units, annual mean of quarterly values"),
        }

    capacity = _capacity_years(scen_path)
    # The issue #20 caveat and record are dropped only when the cached
    # parameter rows were compared and alpha_PPLR is the same in both (a
    # matched Baseline); an unchecked run keeps them.
    alpha_matched = params["checked"] and "alpha_PPLR" not in params["non_lever"]
    caveats = [
        c for c in CAVEATS
        if not (alpha_matched and c.startswith("Parameter mismatch (issue #20)"))
    ]
    mismatch = None if alpha_matched else dict(BASELINE_PARAMETER_MISMATCH)
    if mismatch and params["checked"]:  # the values this scenario's files print
        printed = params["non_lever"]["alpha_PPLR"]
        mismatch["baseline_files"] = float(printed["baseline"])
        mismatch["policy_files"] = float(printed["scenario"])
    if not params["checked"]:
        caveats.insert(0, (
            "Parameters not compared: the cached run has no "
            "Parameters-sorted file for this scenario or its Baseline, so "
            "whether the two share every parameter except the policy levers "
            "is unknown (parameter_check)."
        ))
    if capacity & set(years):
        caveats.insert(0, (
            "Capacity-constrained years: electricity generation sits at the "
            "power sector's capacity ceiling in "
            + ", ".join(str(y) for y in sorted(capacity & set(years)))
            + " (capacity_constrained). Deltas in those years reflect a "
            "price-regime switch (the regime that breaks stock-flow "
            "consistency in the two refused solves), not a smooth policy "
            "response."
        ))
    if name in IDENTICAL_TO:
        caveats.insert(0, _IDENTICAL_NOTE.format(other=IDENTICAL_TO[name]))
    if policy_start is None:
        caveats.insert(0, (
            "Policy start unknown: fewer than two policy files are cached, so "
            "the pre-policy years (2023-2026 in the pinned run, the alpha_PP "
            "mismatch alone) cannot be told apart and are included; "
            "policy_active is None for every year."
        ))
    if any(c["stock"]["available"] is False for c in checks.values()):
        caveats.insert(0, (
            "Stock side not checked: the cached file prints no FNW column, "
            "so only the flow side of stock-flow consistency (LEND) was "
            "checked (sfc_check, stock)."
        ))
    if params["undocumented"]:
        caveats.insert(0, (
            "BASELINE AND SCENARIO PARAMETERS DIFFER outside the policy "
            "levers (" + ", ".join(params["undocumented"]) + "); diagnostic "
            "output only, not a policy result."
        ))
    if failed:
        caveats.insert(0, (
            "NOT STOCK-FLOW CONSISTENT: sectoral net lending or financial "
            "net worth does not sum to zero (" + _sfc_detail(failed)
            + "); diagnostic output only, not a result."
        ))
    return {
        "result_type": "scenario deltas",
        "scenario": name,
        "block": block,
        "description": _description(name, description),
        "identical_to": IDENTICAL_TO.get(name),
        "delta_convention": "scenario minus baseline (same block folder)",
        "years": years,
        "policy_start_year": policy_start,
        # None per year when the policy start cannot be read from the cache
        # (fewer than two policy files cached): unknown, not "active".
        "policy_active": [
            None if policy_start is None else y >= policy_start for y in years
        ],
        # None when the cached parameter rows were compared and alpha_PPLR
        # is the same in both.
        "baseline_parameter_mismatch": mismatch,
        "parameter_check": params,
        "capacity_constrained": [y in capacity for y in years],
        "variables": per_variable,
        "caveats": caveats,
        "sfc_check": checks,
        "provenance": {
            "upstream_commit": UPSTREAM_COMMIT,
            "cache_path": str(scen_path),
            "baseline_path": str(base_path),
            "r_run_date": datetime.date.fromtimestamp(
                scen_path.stat().st_mtime
            ).isoformat(),
        },
    }
