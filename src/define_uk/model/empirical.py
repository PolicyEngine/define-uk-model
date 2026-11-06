"""Opt-in empirically derived equation forms (NOT the manual as printed).

Twelve equations where the pinned upstream run's numbers depart from the
DEFINE-UK Model Manual v1.1 as printed, with the form those numbers do
follow. Each form was found from the cached output CSVs alone (lag swaps,
one-column and ratio searches over every printed variable; round 2 of the
6 Nov 2026 review) and is pinned against the oracle in
``tests/test_oracle.py::ORACLE_FORMS``. None was taken from the upstream
source code.

The default registry is the manual as printed. ``build_registry(
forms="empirical")`` replaces these 12 equations in place (same variable,
same manual_ref, same solve order), so a solve can be run both ways and the
difference attributed equation by equation.

The fossil-fuel ban branch of Eqs. (97)-(98) reads an exogenous switch
``FF_BAN`` (1 from the quarter the ban binds, else 0; default 0): the
manual prints no ban branch, so there is no manual variable to read.
"""

from __future__ import annotations

from typing import Callable, Mapping

from .registry import Equation, Registry
from .sectors import power

State = Mapping[str, float]


def _ban(s: State) -> bool:
    return s.get("FF_BAN", 0.0) >= 0.5


# name -> (why, func(state, lag))
EMPIRICAL_FORMS: dict[str, tuple[str, Callable[[State, State], float]]] = {
    "GCF": (
        "Eq. (23) + SPEND_GVTPS - SUBS_PS: on-balance-sheet green public "
        "power investment counts in GCF (the subsidy part is already in "
        "GCF_PS under the empirical Eq. (102)).",
        # Placeholder: ``apply`` wraps the registered (manual) Eq. (23).
        lambda s, l: s["SPEND_GVTPS"] - s["SUBS_PS"],
    ),
    "YD_PS": (
        "Eq. (92) + SUBS_PS.",
        lambda s, l: s["GOS_PS"] + s["INTR_PS"] - s["INTP_PS"] + s["SUBS_PS"],
    ),
    "GCF_PS": (
        "Eq. (102) + SUBS_PS (the subsidy is spent on capital).",
        lambda s, l: s["GCF_PSNFF"] + s["GCF_PSFF"] + s["SUBS_PS"],
    ),
    "GCF_PSNFF": (
        "Eq. (101) with desired investment cut by 0.5 SUBS_PS before "
        "rationing (the 0.5 is not in the manual).",
        lambda s, l: (1.0 - s["CR_PS"]) * (s["GCF_PSNFFD"] - 0.5 * s["SUBS_PS"]),
    ),
    "GCF_PSNFFR": (
        "Eq. (105): (GCF_PSNFF + SUBS_PS)/P_P, so the subsidy builds capacity.",
        lambda s, l: (s["GCF_PSNFF"] + s["SUBS_PS"]) / s["P_P"],
    ),
    "GCF_PSFFD": (
        "Eq. (97) with a ban branch: zero while FF_BAN is on.",
        lambda s, l: 0.0 if _ban(s) else (1.0 - s["prop_NFF"]) * s["GCF_PSD"],
    ),
    "GCF_PSNFFD": (
        "Eq. (98) with a ban branch: all desired investment while FF_BAN is on.",
        lambda s, l: s["GCF_PSD"] if _ban(s) else s["prop_NFF"] * s["GCF_PSD"],
    ),
    "MC_FF": (
        "Eq. (82) dividing by E_ELECFF at t-1, not t.",
        lambda s, l: (s["IC_FUELPS"] + s["COV_ETSPS"] * s["P_ETS"]
                      * s["EMIS_ELEC"]) / l["E_ELECFF"],
    ),
    "P_ELEC": (
        "Eq. (84) as MU_ELEC MC_ELEC (MU_ELEC used as a gross factor), not "
        "(1 + MU_ELEC) MC_ELEC.",
        lambda s, l: power._MU_ELEC * s["MC_ELEC"],
    ),
    "RESTR_PS": (
        "Eq. (111) as eta_PSB GO_PS, not eta_PSB GDP_{t-1}.",
        lambda s, l: power._ETA_PSB * s["GO_PS"],
    ),
    "EQLTR_PS": (
        "Eq. (109) with share GO_PS/GO instead of theta_psb.",
        lambda s, l: s["GO_PS"] / s["GO"] * s["EQATR_NMFI"],
    ),
    "DIVR_PS": (
        "Eq. (93) dividing by EQL_NMFI - EQN_RoW.",
        lambda s, l: power._BETA_DPS * s["EQA_PS"]
        / (s["EQL_NMFI"] - s["EQN_RoW"]) * s["DIVP_NMFI"],
    ),
}


def apply(registry: Registry) -> None:
    """Replace the 12 manual equations with their empirical forms in place."""
    by_name = {eq.name: eq for eq in registry}
    for name, (_why, func) in EMPIRICAL_FORMS.items():
        old = by_name[name]
        if name == "GCF":
            func = (lambda s, l, base=old.func, extra=func:
                    base(s, l) + extra(s, l))
        registry.replace(Equation(name, old.manual_ref, old.kind, func))
