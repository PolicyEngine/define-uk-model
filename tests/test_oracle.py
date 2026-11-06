"""Oracle comparison: our implementation vs the pinned upstream run.

The upstream R code (unlicensed, fetched at a pinned commit by
``define_uk.upstream``) is used here strictly as a numerical oracle per
REIMPLEMENTATION.md.

What runs where
---------------
- ``test_registered_equations_reproduce_the_oracle`` is the comparison that
  can be made today. Each equation in our registry is evaluated on the
  oracle's OWN values for its inputs (state = quarter t, lag = quarter t-1)
  and must reproduce the oracle's value for its output, over every simulation
  quarter 2023Q1-2040Q4, in the baseline and in the policy scenarios. This
  checks each transcribed equation against the oracle one at a time. It does
  not solve our model, so it is not the milestone-2 gate.
- Every registered equation must be classified in exactly one of
  ``REPRODUCED``, ``ORACLE_FORMS``, ``DIVERGENT`` or ``NOT_EVALUABLE``.
  ``ORACLE_FORMS`` (2026-11-06) holds the equations where the oracle departs
  from the manual as printed, with the form its numbers do follow, found
  from the cached CSVs alone; the registry keeps the manual form.
- "Reproduces" means within the larger of TOL and the propagated
  4-significant-figure rounding of the equation's inputs (``_ratio``). A new equation that is
  not classified fails ``test_every_equation_is_classified``, so nothing can
  join the registry without being compared.
- The milestone-2 gate itself (solve our registry over the oracle horizon and
  compare the GDP path) is not written yet. It is a strict xfail, so it shows
  in every run as outstanding and turns red the moment it passes without the
  marker being removed. ``test_the_oracle_gate_cannot_pass_by_accident``
  keeps guarding the registry.

The cached-run tests skip in CI (the upstream is unlicensed, so CI never
fetches or runs it). The skip is keyed on the cached run, not on
``Rscript``: the comparison needs upstream outputs, and a cached run needs
no R.

Before 2026-11-06 the GDP-path test raised NotImplementedError wherever a
cache existed, so the local suite was red on every machine that could run
the oracle at all, and a real failure there would have been invisible.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest

from define_uk.model.sectors import build_registry, power
from define_uk.scenarios import _TABLES, _run_root

REFERENCE = json.loads(
    (Path(__file__).resolve().parents[1] / "validation"
     / "reference_outputs.json").read_text()
)
TOL = REFERENCE["oracle_identity_residuals"]["tolerance_rel"]
SIM_START = 144  # row of 2023Q1 in the 1987Q1-anchored files

# Oracle files the per-equation comparison runs on: the baseline, both
# green-investment designs, a regulation scenario and the combined policy.
ORACLE_FILES = (
    "gvt_investment/Variables_Baseline.csv",
    "gvt_investment/Variables_GPI + Green Bonds.csv",
    "gvt_investment/Variables_Green Power Subsidy.csv",
    "housing_regulation/Variables_Housing Regulation + Subsidy.csv",
    "mixed/mutual_trust/Variables_Both Regulations + Subsidies.csv",
)

# Equations that reproduce the oracle in every file above, to the CSVs'
# printing precision (see ``_ratio``).
REPRODUCED = {
    # §3.2 high-level macro, Eqs. (21)-(43). GCF, Eq. (23), only in the
    # scenarios without on-balance-sheet green public investment: see
    # ORACLE_FORMS below.
    "GDP", "CONS", "GO", "GDP_R", "CONS_R", "GCF_R", "GO_R", "g", "P",
    "EMP_PRI", "GDP_RFK", "GDP_RMAX", "re", "ru", "u", "nu", "EMP_PUB", "POP",
    # §3.3.1 production
    "F_P", "F_PR", "GO_PR", "GO_P", "COST_P", "UC", "W_PRI", "W_PUB", "W",
    "P_NELECT", "COST_NELEC", "COST_ER", "K_P", "K_PG", "K_PC", "K_PR",
    "K_PGR", "K_PCR", "WR_PRI", "WR_PUB", "P_NELEC", "P_FUEL", "delta_KP",
    # §3.3.2 power sector. GOS_PS, RP_PS and NW_PS joined on 2026-11-06:
    # they are differences of large, nearly equal printed terms, and their
    # round-1 "divergence" was the rounding of those terms (now inside the
    # propagated printing bound in every file, max 0.68 of it).
    "F_PS", "F_PSR", "GO_PSR", "GO_PS", "COST_PS", "beta_NFF", "AC_NFF",
    "AC_FF", "u_FF", "u_NFF", "u_PS", "GCF_PSR", "GCF_PSFF", "GCF_PSFFR",
    "LEND_PS", "IBLTR_PS", "MC_ELEC", "DIVP_PS", "IBATR_PS", "EQATR_PS",
    "FA_PS", "FL_PS", "K_PSR", "K_PS", "K_PSFF", "K_PSNFF", "LEV_PS",
    "GOS_PS", "RP_PS", "NW_PS",
}

ALL_FILES = frozenset(ORACLE_FILES)
_EQ23 = next(e for e in build_registry() if e.name == "GCF")
_SUBSIDY_FILES = ALL_FILES - {"gvt_investment/Variables_GPI + Green Bonds.csv"}
_BAN_FILE = "mixed/mutual_trust/Variables_Both Regulations + Subsidies.csv"
_BAN_FROM = 180  # 2032Q1: first quarter with zero desired fossil investment

# Equations where the oracle departs from the manual as printed, with the
# form the oracle's numbers do follow. Our registry keeps the manual form
# (REIMPLEMENTATION.md: equations come from the manual only); each oracle
# form below was found from the cached CSVs alone (lag swaps and
# one-column / ratio searches over every printed variable, 2026-11-06) and
# is pinned by ``test_oracle_forms_explain_the_departures``: the manual form
# departs in exactly the listed files, the oracle form reproduces in all.
# value = (files where the manual form departs, what the oracle does, form)
ORACLE_FORMS = {
    "GCF": (
        {"gvt_investment/Variables_GPI + Green Bonds.csv"},
        "Eq. (23) as printed omits SPEND_GVTPS; the oracle adds it to GCF "
        "when green public investment is on the balance sheet.",
        lambda s, l, t, f: _EQ23.func(s, l) + s["SPEND_GVTPS"] - s["SUBS_PS"],
    ),
    # Power-sector subsidies. SUBS_PS is positive from 2027Q1 in every file
    # but GPI + Green Bonds, including the baseline (0.65 per quarter).
    "YD_PS": (
        _SUBSIDY_FILES,
        "Eq. (92) has no subsidy term; the oracle adds SUBS_PS to the power "
        "sector's disposable income (Eq. (136) does count it as an inflow).",
        lambda s, l, t, f: s["GOS_PS"] + s["INTR_PS"] - s["INTP_PS"] + s["SUBS_PS"],
    ),
    "GCF_PS": (
        _SUBSIDY_FILES,
        "Eq. (102): the oracle's total power investment is GCF_PSNFF + "
        "GCF_PSFF + SUBS_PS (the subsidy is spent on capital).",
        lambda s, l, t, f: s["GCF_PSNFF"] + s["GCF_PSFF"] + s["SUBS_PS"],
    ),
    "GCF_PSNFF": (
        _SUBSIDY_FILES,
        "Eq. (101): the oracle's privately financed non-fossil investment "
        "is (1 - CR_PS)(GCF_PSNFFD - 0.5 SUBS_PS): each pound of subsidy "
        "displaces half a pound of desired private investment. The 0.5 is "
        "not in the manual.",
        lambda s, l, t, f: (1.0 - s["CR_PS"]) * (s["GCF_PSNFFD"] - 0.5 * s["SUBS_PS"]),
    ),
    "GCF_PSNFFR": (
        _SUBSIDY_FILES,
        "Eq. (105): the oracle's real non-fossil investment includes the "
        "subsidy, (GCF_PSNFF + SUBS_PS)/P_P, so the subsidy builds capacity.",
        lambda s, l, t, f: (s["GCF_PSNFF"] + s["SUBS_PS"]) / s["P_P"],
    ),
    # Fossil-fuel ban. Eqs. (97)-(98) have no ban branch (the ban enters
    # the manual only through expectations, Eq. (88)).
    "GCF_PSFFD": (
        {_BAN_FILE},
        "Eq. (97): under the ban the oracle sets desired fossil investment "
        "to zero from 2032Q1.",
        lambda s, l, t, f: 0.0 if f == _BAN_FILE and t >= _BAN_FROM
        else (1.0 - s["prop_NFF"]) * s["GCF_PSD"],
    ),
    "GCF_PSNFFD": (
        {_BAN_FILE},
        "Eq. (98): under the ban all desired investment goes to non-fossil "
        "from 2032Q1.",
        lambda s, l, t, f: s["GCF_PSD"] if f == _BAN_FILE and t >= _BAN_FROM
        else s["prop_NFF"] * s["GCF_PSD"],
    ),
    # Every file: the printed equation and the oracle differ outright.
    "MC_FF": (
        ALL_FILES,
        "Timing. Eq. (82) divides by E_ELECFF at t; the oracle divides by "
        "E_ELECFF at t-1 (reproduces to 5e-4 in every file).",
        lambda s, l, t, f: (s["IC_FUELPS"] + s["COV_ETSPS"] * s["P_ETS"]
                         * s["EMIS_ELEC"]) / l["E_ELECFF"],
    ),
    "P_ELEC": (
        ALL_FILES,
        "Eq. (84) prints (1 + MU_ELEC) MC_ELEC; the oracle prices at "
        "MU_ELEC MC_ELEC with the same Table 5 MU_ELEC = 1.228, i.e. MU_ELEC "
        "is used as a gross mark-up factor. As printed, the price is 81% "
        "higher. The oracle's P_ELEC equals its P_ELECLR (the long-run rule "
        "§5 calibrates and §3 never prints) in every quarter here.",
        lambda s, l, t, f: power._MU_ELEC * s["MC_ELEC"],
    ),
    "RESTR_PS": (
        ALL_FILES,
        "Eq. (111) prints eta_PSB GDP_{t-1}; with the same Table 5 eta_PSB "
        "the oracle uses eta_PSB GO_PS (the power sector's own gross "
        "output). As printed the flow is about 22x the oracle's.",
        lambda s, l, t, f: power._ETA_PSB * s["GO_PS"],
    ),
    "EQLTR_PS": (
        ALL_FILES,
        "Eq. (109) prints a constant share theta_psb of EQATR_NMFI; the "
        "oracle's share is GO_PS/GO, the power sector's share of gross "
        "output, which moves with the scenario.",
        lambda s, l, t, f: s["GO_PS"] / s["GO"] * s["EQATR_NMFI"],
    ),
    "DIVR_PS": (
        ALL_FILES,
        "Eq. (93) divides by EQL_NMFI; the oracle divides by EQL_NMFI - "
        "EQN_RoW (NMFI equity net of the rest of the world's net holding).",
        lambda s, l, t, f: power._BETA_DPS * s["EQA_PS"]
        / (s["EQL_NMFI"] - s["EQN_RoW"]) * s["DIVP_NMFI"],
    ),
}

# Still diverge in at least one file, and the oracle form is not known.
# value = why
DIVERGENT = {
    "prop_NFF": "Eq. (99): alpha_0bNFF, alpha_1bNFF are not in Table 5 "
                "(power.MANUAL_GAPS, defaulted to 0, so prop_NFF = 0.5); the "
                "oracle's prop_NFF runs 0.90-1.00.",
    "CR_PS": "Eq. (138): alpha_1-3CRPS are not in Table 5 (power.MANUAL_GAPS, "
             "defaulted to 0); the oracle's CR_PS runs 0.06-0.59.",
    "DEF_PS": "Eq. (117) reproduces in the baseline-like files (within 2.2x "
              "the printing bound, which an exponential of a printed lag can "
              "reach) but misses by up to 35x in GPI + Green Bonds and 10x in "
              "the mixed policy, at the 2030 illiquidity spike (oracle 0.0170 "
              "vs 0.0234 in 2030Q3). Not diagnosed.",
}

# Output or an input is not a column of the oracle CSVs, so the equation
# cannot be compared one at a time (only through a full solve).
NOT_EVALUABLE = {
    "lam", "EMP", "GDP_RFE", "LF", "P_P", "mu", "WS", "WR", "Eu_PS", "Fu_PS",
    "COST_PSNFF", "COST_PSFF", "INTR_PS", "INTP_PS", "GCF_PSD", "OTIBA_PS",
    "OTEQA_PS", "OTEQL_PS", "OTIBL_PS", "OTRES_PS", "delta_KPS", "IBA_PS",
    "IBL_PS", "EQA_PS", "EQL_PS", "FNWM_PS", "RES_PS", "FNW_PS", "K_PSFFR",
    "K_PSNFFR", "ILLIQ_PS", "DSR_PS",
}


def _cached_run_available() -> bool:
    try:
        _run_root()
    except FileNotFoundError:
        return False
    return True


requires_cached_run = pytest.mark.skipif(
    not _cached_run_available(),
    reason=(
        "no cached DEFINE-UK run (define_uk.runner.run first; the upstream "
        "is unlicensed, so CI never fetches or runs it)"
    ),
)


def _load(rel: str) -> list[dict[str, float]]:
    path = _run_root() / _TABLES / rel
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    return [
        {k: (float(v) if v not in ("", "NA") else math.nan)
         for k, v in r.items() if k}
        for r in rows
    ]


# Each CSV value is printed to 4 significant figures, so it carries a
# relative rounding error of up to 5e-4.
_PRINT_REL = 5e-4


class _Recorder(dict):
    """A state dict that records which keys an equation reads."""

    def __init__(self, data, seen, tag):
        super().__init__(data)
        self._seen, self._tag = seen, tag

    def __getitem__(self, key):
        self._seen.add((self._tag, key))
        return dict.__getitem__(self, key)


def _ratio(func, name, data, t, rel) -> float:
    """|model - oracle| at quarter t over what printing alone can explain.

    The allowance is the larger of TOL (relative) and the first-order
    propagation of the 4-significant-figure rounding of every input the
    equation reads, plus that of the output. Before 2026-11-06 only the TOL
    test was applied, which flagged identities such as GOS_PS = GO_PS -
    COST_PS (a small difference of two large printed numbers) as divergent
    when the gap was rounding. A ratio <= 1 reproduces. Raises ValueError
    where the manual defines no value (power.MANUAL_GAPS).
    """
    cur, lag = data[t], data[t - 1]
    seen: set = set()
    model = func(_Recorder(cur, seen, "s"), _Recorder(lag, seen, "l"), t, rel)
    oracle = cur[name]
    if math.isnan(oracle) or math.isnan(model):
        return 0.0
    bound = _PRINT_REL * abs(oracle)
    for tag, key in seen:
        src = cur if tag == "s" else lag
        x = src.get(key)
        if not isinstance(x, float) or x == 0.0 or math.isnan(x):
            continue
        bumped = {**src, key: x * (1.0 + _PRINT_REL)}
        moved = (func(bumped, lag, t, rel) if tag == "s"
                 else func(cur, bumped, t, rel))
        bound += abs(moved - model)
    allowed = max(TOL * max(abs(oracle), 1e-6), bound)
    return abs(model - oracle) / allowed


def _manual(eq):
    return lambda s, l, t, f: eq.func(s, l)


def _max_ratio(func, name, data, rel="") -> float:
    worst = 0.0
    for t in range(SIM_START, len(data)):
        try:
            worst = max(worst, _ratio(func, name, data, t, rel))
        except (ValueError, ZeroDivisionError):
            # A documented manual gap (e.g. Eq. (85) at zero fossil
            # capacity, power.MANUAL_GAPS): the manual defines no value.
            continue
    return worst


def _max_residual(eq, data) -> float:
    return _max_ratio(_manual(eq), eq.name, data)


def test_every_equation_is_classified():
    """Hermetic: runs in CI. Every registered equation sits in one class."""
    names = set(build_registry().names())
    classes = [REPRODUCED, set(ORACLE_FORMS), set(DIVERGENT), NOT_EVALUABLE]
    union = set().union(*classes)
    assert names - union == set(), "unclassified equations"
    assert union - names == set(), "classified names not in the registry"
    assert sum(len(c) for c in classes) == len(union), "a name is in two classes"


@requires_cached_run
@pytest.mark.parametrize("rel", ORACLE_FILES)
def test_registered_equations_reproduce_the_oracle(rel):
    data = _load(rel)
    by_name = {eq.name: eq for eq in build_registry()}
    expected = set(REPRODUCED) | {
        n for n, (bad, _, _) in ORACLE_FORMS.items() if rel not in bad
    }
    failures = {
        n: _max_residual(by_name[n], data) for n in sorted(expected)
    }
    failures = {n: r for n, r in failures.items() if r > 1.0}
    assert failures == {}, f"{rel}: residual above the printing allowance"


@requires_cached_run
@pytest.mark.parametrize("rel", ORACLE_FILES)
def test_oracle_forms_explain_the_departures(rel):
    """The manual form departs in exactly the listed files; the oracle form
    reproduces in every file. Pins each diagnosis both ways."""
    data = _load(rel)
    by_name = {eq.name: eq for eq in build_registry()}
    departs = {
        n for n in ORACLE_FORMS if _max_residual(by_name[n], data) > 1.0
    }
    assert departs == {n for n, (bad, _, _) in ORACLE_FORMS.items() if rel in bad}
    unexplained = {
        n: r for n, (_, _, form) in ORACLE_FORMS.items()
        if (r := _max_ratio(form, n, data, rel)) > 1.0
    }
    assert unexplained == {}, f"{rel}: oracle form does not reproduce"


@requires_cached_run
def test_gcf_divergence_is_exactly_the_public_green_investment():
    data = _load("gvt_investment/Variables_GPI + Green Bonds.csv")
    eq = next(e for e in build_registry() if e.name == "GCF")
    assert _max_residual(eq, data) > 1.0  # the divergence is real
    worst = max(
        abs(data[t]["GCF"] - eq.func(data[t], data[t - 1])
            - data[t]["SPEND_GVTPS"]) / abs(data[t]["GCF"])
        for t in range(SIM_START, len(data))
    )
    assert worst < TOL


@requires_cached_run
def test_divergent_equations_still_diverge():
    """If one of these starts to reproduce, move it to REPRODUCED."""
    by_name = {eq.name: eq for eq in build_registry()}
    files = [_load(rel) for rel in ORACLE_FILES]
    still = {
        n for n in DIVERGENT
        if any(_max_residual(by_name[n], d) > 1.0 for d in files)
    }
    assert still == set(DIVERGENT)


@requires_cached_run
@pytest.mark.xfail(
    strict=True, raises=NotImplementedError,
    reason="milestone 2: the solved GDP-path comparison is not written",
)
def test_baseline_gdp_path_matches_oracle():
    raise NotImplementedError(
        "solve our registry over the oracle horizon for the S1 baseline and "
        "compare GDP paths within a tolerance recorded in VALIDATION.md"
    )


def test_the_oracle_gate_cannot_pass_by_accident():
    """Runs everywhere, including CI: the gate above is still outstanding.

    Milestone 2 is not passed until ``test_baseline_gdp_path_matches_oracle``
    is a real comparison. This test is what makes the *absence* of that
    comparison visible in a green suite — it fails the moment the registry is
    complete enough that a reader might assume the oracle gate has run.
    """
    registry = build_registry()
    assert len(registry) > 0, "sector modules register nothing"

    sections = {eq.section for eq in registry}
    assert "§3.3.3" not in sections, (
        "§3.3.3 has landed — the oracle comparison is now the only thing "
        "between here and milestone 2, so write it and delete this guard"
    )
