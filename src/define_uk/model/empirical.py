"""Opt-in empirically derived equation forms (NOT the manual as printed).

Twenty-five equations where the pinned upstream run's numbers depart from the
DEFINE-UK Model Manual v1.1 as printed, with the form those numbers do
follow. Each form was found from the cached output CSVs alone (lag swaps,
one-column and ratio searches over every printed variable; round 2 of the
6 Nov 2026 review; consumption and the equity revaluations on 24 Nov
2026) and is pinned against the oracle in
``tests/test_oracle.py::ORACLE_FORMS``. None was taken from the upstream
source code.

The default registry is the manual as printed. ``build_registry(
forms="empirical")`` replaces these 25 equations in place (same variable,
same manual_ref, same solve order), so a solve can be run both ways and the
difference attributed equation by equation.

The fossil-fuel ban branch of Eqs. (97)-(98) reads an exogenous switch
``FF_BAN`` (1 from the quarter the ban binds, else 0; default 0): the
manual prints no ban branch, so there is no manual variable to read.
"""

from __future__ import annotations

from typing import Callable, Mapping

import math

from .calibration import PARAMETERS as _P
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
    "EQLTR_NFC": (
        "Eq. (179) with share 1 - GO_PS/GO instead of 1 - theta_psb, the "
        "counterpart of the Eq. (109) form: NFC and power-sector equity "
        "issuance then sum to EQATR_NMFI, so the equity row of the balance "
        "sheet closes. Reproduces the cached run within the printing bound "
        "in every quarter of the 28 stock-flow-consistent files (r9, "
        "13 Nov 2026).",
        lambda s, l: (1.0 - s["GO_PS"] / s["GO"]) * s["EQATR_NMFI"],
    ),
    # Found 2026-11-06 (round 4) when §3.1/§3.4 were implemented.
    "theta_P": (
        "Eq. (18) with e^{+kappa3 x}: as printed (e^{-kappa3 x}) theta_P is "
        "negative (-0.23 at Table 6) against 0.171 tabulated; the + sign "
        "reproduces the cached run to 4 s.f. in every quarter.",
        lambda s, l: 1.0 - (1.0 + _P["pi3"]) / (
            1.0 + _P["pi3"] * math.exp(_P["kappa3"] * l["K_PG"] / l["K_PC"])),
    ),
    "K_GVTNFFR": (
        "Eq. (276) with GCF_GVTNFFR = (SPEND_GVTPS - SUBS_PS) / P_P (the "
        "on-balance-sheet part, as in the GCF form) and depreciation "
        "delta_KPSNFF: green public power investment accumulates here "
        "(exact in the GPI file, where SUBS_PS = 0: "
        "tests/test_scenario_sweep.py; in the baseline SPEND_GVTPS = SUBS_PS "
        "and K_GVTNFFR stays at its initial path).",
        lambda s, l: (1.0 - s["delta_KPSNFF"]) * l["K_GVTNFFR"]
        + (s["SPEND_GVTPS"] - s["SUBS_PS"]) / s["P_P"],
    ),
    # Dividend closure (round 4). As printed, Eqs. (93), (163), (313) give
    # each sector beta_j x its equity share of DIVP_NMFI with betas that do
    # not sum to one, and Eq. (221) omits the RoW, so dividends paid and
    # received do not net to zero and Σ LEND_s != 0. The oracle closes it:
    "DIVR_NFC": (
        "Eq. (163) as the dividend residual DIVP_NMFI - DIVR_HH - DIVR_PS "
        "(4 s.f. every quarter): NFCs take whatever NMFI dividends the "
        "other domestic holders do not.",
        lambda s, l: s["DIVP_NMFI"] - s["DIVR_HH"] - s["DIVR_PS"],
    ),
    "DIVR_HH": (
        "Eq. (313) dividing by EQL_NMFI - EQN_RoW (as Eq. (93)): implied "
        "beta_dhh = 1.333 in every quarter against 1.34-1.63 as printed.",
        lambda s, l: _P["beta_dhh"] * s["EQA_HH"]
        / (s["EQL_NMFI"] - s["EQN_ROW"]) * s["DIVP_NMFI"],
    ),
    "DIVR_NMFI": (
        "Eq. (221) net of the rest of the world's net dividends: "
        "DIVP_NFC + DIVP_PS - DIVN_RoW (the RoW's DIVN of Eq. (383) is "
        "paid by NMFIs).",
        lambda s, l: s["DIVP_NFC"] + s["DIVP_PS"] - s["DIVN_ROW"],
    ),
    "LENDM_GVT": (
        "Eq. (281) with SUBS_GVT = SPEND_GVTPS: the government pays for the "
        "power subsidy (baseline, = SUBS_PS) and for on-balance-sheet green "
        "public power investment (GPI); within the printing bound of the "
        "difference of large numbers in every comparison file.",
        lambda s, l: s["YD_GVT"] - (s["CONS_GVT"] + s["GCF_GVT"] + s["SPEND_GVTPS"]),
    ),
    "DIVR_PS": (
        "Eq. (93) dividing by EQL_NMFI - EQN_RoW.",
        lambda s, l: power._BETA_DPS * s["EQA_PS"]
        / (s["EQL_NMFI"] - s["EQN_ROW"]) * s["DIVP_NMFI"],
    ),
    # Household consumption and the equity revaluations (2026-11-24). Found
    # from the cached CSVs alone: a regression of the printed consumption
    # growth on the equation's own three lags returns Table 5's four
    # alpha_CHHP to 3 figures; the equity forms follow from the implied
    # discount rate DIVP / EQL - r_IBL_GVT, which is constant at minus
    # Table 5's beta for NFCs and the power sector.
    "CONS_HHP": (
        "Eq. (318) as a log-linear partial adjustment with all four Table 5 "
        "coefficients: ln C = alpha0 + alpha1 ln C(-1) + alpha2 ln YD(-1) + "
        "alpha3 ln FA(-1). As printed the equation has an error-correction "
        "speed epsilon_CHHP that Table 5 does not give; reading alpha3 as "
        "that speed puts alpha1 and alpha2 on the wrong variables (one-step "
        "miss up to 4%, against 0.02% for this form).",
        lambda s, l: math.exp(_P["alpha0_CHHP"]) * l["CONS_HHP"] ** _P["alpha1_CHHP"]
        * l["YD_HH"] ** _P["alpha2_CHHP"] * l["FA_HH"] ** _P["alpha3_CHHP"],
    ),
    "OTEQL_NFC": (
        "Eq. (184) discounting at r_IBL_GVT - beta_EQLNFC: the cached run's "
        "DIVP_NFC / EQL_NFC - r_IBL_GVT is -0.00168 in every quarter, "
        "Table 5's beta_EQLNFC = 0.001676 with the opposite sign.",
        lambda s, l: s["DIVP_NFC"] / (s["r_IBL_GVT"] - _P["beta_EQLNFC"])
        - l["EQL_NFC"],
    ),
    "OTEQL_PS": (
        "Eq. (114) discounting at r_IBL_GVT - beta_EQLPS, as Eq. (184).",
        lambda s, l: s["DIVP_PS"] / (s["r_IBL_GVT"] - power._BETA_EQLPS)
        - l["EQL_PS"],
    ),
    "OTEQL_NMFI": (
        "Eq. (240) floored at zero: NMFI equity is revalued up to its "
        "dividend-discount value and never down (the cached run prints 0 "
        "in every quarter where the printed form is negative). The sign of "
        "beta_EQLNMFI is as printed.",
        lambda s, l: max(0.0, s["DIVP_NMFI"] / (s["r_IBL_GVT"] + _P["beta_EQLNMFI"])
                         - l["EQL_NMFI"]),
    ),
    "OTEQA_HH": (
        "Eq. (344) as the household share of the NMFI revaluation, "
        "beta_dhh EQA_HH(-1) / (EQL_NMFI(-1) - EQN_RoW(-1)) OTEQL_NMFI, the "
        "same share as the dividend form of Eq. (313). As printed "
        "(delta_EQAHH EQA_HH(-1)) it is unrelated to OTEQL_NMFI.",
        lambda s, l: _P["beta_dhh"] * l["EQA_HH"]
        / (l["EQL_NMFI"] - l["EQN_ROW"]) * s["OTEQL_NMFI"],
    ),
    "OTEQA_PS": (
        "Eq. (113) dividing by EQL_NMFI - EQN_RoW, as Eq. (93).",
        lambda s, l: power._BETA_DPS * l["EQA_PS"]
        / (l["EQL_NMFI"] - l["EQN_ROW"]) * s["OTEQL_NMFI"],
    ),
}


def apply(registry: Registry) -> None:
    """Replace the 25 manual equations with their empirical forms in place."""
    by_name = {eq.name: eq for eq in registry}
    for name, (_why, func) in EMPIRICAL_FORMS.items():
        old = by_name[name]
        if name == "GCF":
            func = (lambda s, l, base=old.func, extra=func:
                    base(s, l) + extra(s, l))
        registry.replace(Equation(name, old.manual_ref, old.kind, func))
