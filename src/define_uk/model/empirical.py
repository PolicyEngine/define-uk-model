"""Opt-in empirically derived equation forms (NOT the manual as printed).

Thirty-nine equations where the pinned upstream run's numbers depart from
the DEFINE-UK Model Manual v1.1 as printed, with the form those numbers do
follow, and two the manual uses but never defines. Each form was found from
the cached output CSVs alone (lag swaps, one-column and ratio searches over
every printed variable; round 2 of the 6 Nov 2026 review; consumption and
the equity revaluations on 24 Nov 2026; the run's own parameter values and
five more forms on 27 Nov 2026) and is pinned against the oracle in
``tests/test_oracle.py::ORACLE_FORMS``. None was taken from the upstream
source code.

The default registry is the manual as printed. ``build_registry(
forms="empirical")`` replaces these 39 equations in place (same variable,
same manual_ref, same solve order) and adds the two of ``ADDED_FORMS``, so
a solve can be run both ways and the difference attributed equation by
equation.

Eight of the 39 are not a different form at all. They are the manual's
printed equation evaluated at the parameter values the run itself prints
(``RUN_PARAMETERS``), where those differ from Table 5 or Table 5 omits
them, or, for world demand growth, at the value its printed path implies
(``ROW_DG_IMPLIED``).

The fossil-fuel ban branch of Eqs. (97)-(98) reads an exogenous switch
``FF_BAN`` (1 from the quarter the ban binds, else 0; default 0): the
manual prints no ban branch, so there is no manual variable to read.
"""

from __future__ import annotations

from typing import Callable, Mapping

import math

from .calibration import PARAMETERS as _P
from .registry import Equation, Registry
from .sectors import ecosystem, power

State = Mapping[str, float]

# Parameter values the cached run prints in its own parameter files
# (``Parameters-sorted_*.csv``, the same in all 30) where they differ from
# the manual's Table 5 or Table 5 does not list them. Keys are spelled as
# in ``calibration.PARAMETERS``; the comment gives Table 5's value.
# ``calibration.PARAMETERS`` stays the manual: only the forms below read
# these. alpha_PPLR also differs, in the Baseline files alone (issue #20),
# and is handled as an override, not here.
# tests/test_oracle.py::test_run_parameters_are_what_the_cached_files_print
# checks every entry, and that no other shared parameter differs.
RUN_PARAMETERS = {
    "CF_min": 0.6,           # Table 5: 0.5
    "pi2": -1.084,           # Table 5: -1.164
    "def_max": 0.04664,      # Table 5: 0.2
    "def0_NFC": 2909.0,      # Table 5: 12580
    "def0_PS": 5737.0,       # Table 5: 24820
    "alpha0_SOCB": 0.0601,   # Table 5: 0.05561
    "alpha1_SOCB": 0.5317,   # Table 5: 0.5263
    "alpha2_SOCB": 0.1392,   # Table 5: 0.151
    "alpha0_GCFPS": 0.02129,  # not in Table 5 (power.MANUAL_GAPS)
    "alpha0_bNFF": 1.347,     # not in Table 5
    "alpha1_bNFF": 10.0,      # not in Table 5
}
_R = RUN_PARAMETERS

# Quarterly growth of real rest-of-world demand, Eq. (372), as the cached
# ROW_DR path implies it: (ROW_DR_2040Q4 / ROW_DR_2022Q4)^(1/72) = 1.00742
# in every one of the 30 files. Table 5 and the run's parameter file print
# it to 4 significant figures, 1.007. One quarter at a time the two cannot
# be told apart (both are inside the printing bound), but over 72 quarters
# 1.007 leaves world demand 3.0% low and exports with it.
ROW_DG_IMPLIED = 1.00742


def _ban(s: State) -> bool:
    return s.get("FF_BAN", 0.0) >= 0.5


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _default_rate(def0: float, illiq: float) -> float:
    return _R["def_max"] / (
        1.0 + def0 * math.exp(_P["def1"] - _P["def2"] * illiq))


def _liability_rate(j: str, spr: str, sigma: str, delta: str):
    """Eq. (401) with delta_jt = -delta_IBL_j (the sector's write-off rate:
    OTIBL_j = delta_IBL_j IBL_j(-1) is a write-off when negative)."""
    return lambda s, l: s[f"r_IBA_{j}LR"] + (_P[spr] - _P[delta]) * (
        1.0 + _P[sigma] * s["r_BOEQ"]) * l["FL_MFI"] / l["FA_MFI"]


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
    # The run's own parameter values (2026-11-27): the manual's printed
    # equation, evaluated at RUN_PARAMETERS.
    "SOCB_GVT": (
        "Eq. (269) as printed, with the three alpha_SOCB the run prints "
        "(0.0601, 0.5317, 0.1392) in place of Table 5's (0.05561, 0.5263, "
        "0.151). With Table 5's the level is 3.3% low in every quarter.",
        lambda s, l: s["GDP"] * (_R["alpha0_SOCB"]
                                 + _R["alpha1_SOCB"] * l["SOCB_GVT"] / l["GDP"]
                                 + _R["alpha2_SOCB"] * s["ru"]),
    ),
    "CF_NFF": (
        "Eq. (17) as printed, with the run's CF_min = 0.6 and pi2 = -1.084 "
        "(Table 5: 0.5 and -1.164). With Table 5's the capacity factor "
        "drifts to 0.5 where the run floors at 0.6.",
        lambda s, l: ecosystem._logistic(
            _R["CF_min"], _P["CF_max"], _R["pi2"], _P["kappa2"],
            ecosystem._ratio(l["E_ELECNFF"], l["E_ELECFF"])),
    ),
    "DEF_NFC": (
        "Eq. (186) as printed, with the run's def_max = 0.04664 and "
        "def0_NFC = 2909 (Table 5: 0.2 and 12580). The two sets give nearly "
        "the same rate while defaults are small (def_max / def0 is 1.60e-5 "
        "against 1.59e-5), so Table 5's miss by only 2 printing bounds.",
        lambda s, l: _default_rate(_R["def0_NFC"], l["ILLIQ_NFC"]),
    ),
    "DEF_PS": (
        "Eq. (117) as printed, with the run's def_max = 0.04664 and "
        "def0_PS = 5737 (Table 5: 0.2 and 24820). Table 5's miss by up to "
        "35 bounds at the 2030 illiquidity spike of GPI + Green Bonds, "
        "where the lower ceiling binds.",
        lambda s, l: _default_rate(_R["def0_PS"], l["ILLIQ_PS"]),
    ),
    "GCF_PSD": (
        "Eq. (96) as printed, with the intercept alpha_0GCFPS = 0.02129 "
        "the run prints. Table 5 does not list it (power.MANUAL_GAPS "
        "defaults it to 0).",
        lambda s, l: l["K_PS"] * (
            _R["alpha0_GCFPS"]
            + _P["alpha1_GCFNFC"] * (l["Fu_PS"] - _P["u_T"])
            + _P["alpha2_GCFNFC"] * l["GCF_PSD"] / l["K_PS_LAG"]),
    ),
    "prop_NFF": (
        "Eq. (99) as printed, with alpha_0bNFF = 1.347 and alpha_1bNFF = "
        "10 from the run's parameter file (not in Table 5, defaulted to 0, "
        "which fixes the split at 0.5). The profit rates r_KNFF and r_KFF "
        "are ADDED_FORMS.",
        lambda s, l: _logistic(_R["alpha0_bNFF"] + _R["alpha1_bNFF"]
                               * (l["r_KNFF"] - l["r_KFF"])),
    ),
    "CR_PS": (
        "Eq. (138) with Table 5's alpha_0CRPS and the NFC slopes "
        "alpha_1-3CRNFC of Eq. (207). Table 5 and the run's parameter file "
        "both list alpha_0CRPS and no power-sector slopes (defaulted to 0, "
        "which fixes CR_PS at 0.94; the run's is 0.06-0.59).",
        lambda s, l: _logistic(
            _P["alpha0_CRPS"] + _P["alpha1_CRNFC"] * l["CR_PS"]
            - _P["alpha2_CRNFC"] * l["DSR_PS"]
            + _P["alpha3_CRNFC"] * l["FL_MFI"] / l["FA_MFI"]),
    ),
    "ROW_DR": (
        "Eq. (372) as printed, with the growth factor the cached path "
        "implies over the whole horizon, 1.00742, in place of the 4 s.f. "
        "1.007 that Table 5 and the run's parameter file print (see "
        "ROW_DG_IMPLIED). Not a different form: the printed parameter is "
        "too coarse to compound.",
        lambda s, l: ROW_DG_IMPLIED * l["ROW_DR"],
    ),
    # Forms (2026-11-27).
    "GCF_NFCD": (
        "Eq. (166) with utilisation lagged: u(-1) - u_T where the manual "
        "prints u - u_T. Everything else as printed, Table 5 coefficients.",
        lambda s, l: l["K_NFC"] * (
            _P["alpha0_GCFNFC"] + _P["alpha1_GCFNFC"] * (l["u"] - _P["u_T"])
            + _P["alpha2_GCFNFC"] * l["GCF_NFCD"] / l["K_NFC_LAG"]),
    ),
    "beta_nfc": (
        "Eq. (168) with the tax-inclusive non-electric energy price "
        "P_NELECT in the relative price, where the manual prints P_NELEC.",
        lambda s, l: _P["alpha0_betaNFC"]
        + _P["alpha1_betaNFC"] * math.tanh(s["P_NELECT"] / s["P_ELEC"])
        + _P["alpha2_betaNFC"] * l["COST_ER"] / l["E"],
    ),
    "E_ELECNFF": (
        "Eq. (6) with government non-fossil capital in the cap: "
        "CF_NFF (K_PSNFFR + K_GVTNFFR), as Eq. (5) already counts it in "
        "maximum generation. Differs only where K_GVTNFFR > 0 (GPI).",
        lambda s, l: min(s["E_ELEC"] * _P["sigma_ELEC"],
                         s["CF_NFF"] * (s["K_PSNFFR"] + s["K_GVTNFFR"])),
    ),
    "r_IBA_PSLR": (
        "Eq. (399) for the power sector with the NFC floor and spread "
        "(minr_nfc, spr_nfca): Table 5 gives the power sector neither, and "
        "the run's r_IBA_PSLR equals its r_IBA_NFCLR in every quarter.",
        lambda s, l: max(_P["minr_nfc"], s["r_BOEQ"] - _P["spr_nfca"]),
    ),
    "r_IBL_NMFILR": (
        "Eq. (401) with the undefined delta_jt = -delta_IBLNMFI (the "
        "write-off rate, the sign DEF_NFC and DEF_PS carry for the two "
        "sectors that default). Read as +delta_IBLNMFI it misses by 30%.",
        _liability_rate("NMFI", "spr_nmfil", "sigma_nmfi", "delta_IBLNMFI"),
    ),
    "r_IBL_GVTLR": (
        "Eq. (401) with delta_jt = -delta_IBLGVT, as for NMFIs.",
        _liability_rate("GVT", "spr_gvtl", "sigma_gvt", "delta_IBLGVT"),
    ),
}


def _profit_rate(s: State, revenue: float, cost: float, capital: float) -> float:
    return (revenue - cost) / capital if capital else 0.0


# Variables the manual reads but never defines, so the manual registry has
# no equation to replace: name -> (manual_ref, kind, why, func). The
# empirical registry adds them; under the manual as printed they stay
# exogenous (and inert, since alpha_1bNFF defaults to 0).
ADDED_FORMS: dict[str, tuple[str, str, str, Callable[[State, State], float]]] = {
    "r_KNFF": (
        "§3.3.2 eq. (99)[NFF]", "identity",
        "Profit rate of non-fossil generation, read by Eq. (99) and defined "
        "nowhere in the manual. In the run it is (P_ELEC E_ELECNFF - "
        "COST_PSNFF) / (K_PSNFF + P_P K_GVTNFFR): operating surplus over "
        "the nominal non-fossil capital that generates it, the "
        "government's included.",
        lambda s, l: _profit_rate(
            s, s["P_ELEC"] * s["E_ELECNFF"], s["COST_PSNFF"],
            s["K_PSNFF"] + s["P_P"] * s["K_GVTNFFR"]),
    ),
    "r_KFF": (
        "§3.3.2 eq. (99)[FF]", "identity",
        "Profit rate of fossil generation: (P_ELEC E_ELECFF - COST_PSFF) / "
        "K_PSFF, and 0 once the fossil capital stock is zero (the run "
        "prints 0 from the capital ban).",
        lambda s, l: _profit_rate(
            s, s["P_ELEC"] * s["E_ELECFF"], s["COST_PSFF"], s["K_PSFF"]),
    ),
}


def apply(registry: Registry) -> None:
    """Replace the 39 manual equations with their empirical forms in place
    and add the two of ``ADDED_FORMS``."""
    by_name = {eq.name: eq for eq in registry}
    for name, (_why, func) in EMPIRICAL_FORMS.items():
        old = by_name[name]
        if name == "GCF":
            func = (lambda s, l, base=old.func, extra=func:
                    base(s, l) + extra(s, l))
        registry.replace(Equation(name, old.manual_ref, old.kind, func))
    for name, (ref, kind, _why, func) in ADDED_FORMS.items():
        registry.add(Equation(name, ref, kind, func))
