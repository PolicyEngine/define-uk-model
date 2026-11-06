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
  ``REPRODUCED``, ``DIVERGENT`` or ``NOT_EVALUABLE``. A new equation that is
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

from define_uk.model.sectors import build_registry
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

# Equations that reproduce the oracle within TOL in every file above.
REPRODUCED = {
    # §3.2 high-level macro, Eqs. (21)-(43). GCF, Eq. (23), only in the
    # scenarios without on-balance-sheet green public investment: see
    # SCENARIO_SPECIFIC below.
    "GDP", "CONS", "GO", "GDP_R", "CONS_R", "GCF_R", "GO_R", "g", "P",
    "EMP_PRI", "GDP_RFK", "GDP_RMAX", "re", "ru", "u", "nu", "EMP_PUB", "POP",
    # §3.3.1 production
    "F_P", "F_PR", "GO_PR", "GO_P", "COST_P", "UC", "W_PRI", "W_PUB", "W",
    "P_NELECT", "COST_NELEC", "COST_ER", "K_P", "K_PG", "K_PC", "K_PR",
    "K_PGR", "K_PCR", "WR_PRI", "WR_PUB", "P_NELEC", "P_FUEL", "delta_KP",
    # §3.3.2 power sector
    "F_PS", "F_PSR", "GO_PSR", "GO_PS", "COST_PS", "beta_NFF", "AC_NFF",
    "AC_FF", "u_FF", "u_NFF", "u_PS", "GCF_PSR", "GCF_PSFF", "GCF_PSFFR",
    "LEND_PS", "IBLTR_PS", "MC_ELEC", "DIVP_PS", "IBATR_PS", "EQATR_PS",
    "FA_PS", "FL_PS", "K_PSR", "K_PS", "K_PSFF", "K_PSNFF", "LEV_PS",
}

# Reproduced only in some files; value = files where the equation diverges
# and why. Pinned so the divergence cannot grow or vanish unnoticed.
SCENARIO_SPECIFIC = {
    "GCF": (
        {"gvt_investment/Variables_GPI + Green Bonds.csv"},
        "Eq. (23) as printed omits SPEND_GVTPS; the oracle adds it to GCF "
        "when green public investment is on the balance sheet. Oracle GCF "
        "minus Eq. (23) equals SPEND_GVTPS to 4e-4 (relative).",
    ),
}

# Diverge by more than TOL in at least one file; not yet diagnosed against
# the manual. Each is milestone-2/3 work (see the milestone-2 issue).
DIVERGENT = {
    "GOS_PS", "MC_FF", "P_ELEC", "YD_PS", "DIVR_PS", "RP_PS", "GCF_PSFFD",
    "GCF_PSNFFD", "GCF_PSNFF", "GCF_PS", "GCF_PSNFFR", "prop_NFF", "EQLTR_PS",
    "RESTR_PS", "DEF_PS", "NW_PS", "CR_PS",
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


def _max_residual(eq, data) -> float:
    worst = 0.0
    for t in range(SIM_START, len(data)):
        try:
            model = eq.func(data[t], data[t - 1])
        except ValueError:
            # A documented manual gap (e.g. Eq. (85) at zero fossil
            # capacity, power.MANUAL_GAPS): the manual defines no value.
            continue
        oracle = data[t][eq.name]
        if math.isnan(oracle) or math.isnan(model):
            continue
        scale = abs(oracle) if abs(oracle) > 1e-6 else 1.0
        worst = max(worst, abs(model - oracle) / scale)
    return worst


def test_every_equation_is_classified():
    """Hermetic: runs in CI. Every registered equation sits in one class."""
    names = set(build_registry().names())
    classes = [REPRODUCED, set(SCENARIO_SPECIFIC), DIVERGENT, NOT_EVALUABLE]
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
        n for n, (bad, _) in SCENARIO_SPECIFIC.items() if rel not in bad
    }
    failures = {
        n: _max_residual(by_name[n], data) for n in sorted(expected)
    }
    failures = {n: r for n, r in failures.items() if r > TOL}
    assert failures == {}, f"{rel}: max relative residual above {TOL}"


@requires_cached_run
def test_gcf_divergence_is_exactly_the_public_green_investment():
    data = _load("gvt_investment/Variables_GPI + Green Bonds.csv")
    eq = next(e for e in build_registry() if e.name == "GCF")
    assert _max_residual(eq, data) > 0.02  # the divergence is real
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
        if any(_max_residual(by_name[n], d) > TOL for d in files)
    }
    assert still == DIVERGENT


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
