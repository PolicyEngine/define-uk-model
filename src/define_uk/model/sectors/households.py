"""DEFINE-UK Model Manual v1.1 §3.4.5 Households.

Equations (310)-(366): income, consumption (the error-correction Eq. (318)
on lagged disposable income and financial assets), housing investment and
the energy-retrofit split, net lending, transfers, revaluations, stocks,
the three-way housing stock (inefficient / efficient non-electric /
efficient electric) and house prices.

Clean-room implementation from the published manual (pp. 40-45). The
upstream R code is an output oracle only and is never read to write
equations here (see REIMPLEMENTATION.md).

Symbol reading (see ``MANUAL_GAPS``): Eq. (318)'s adjustment speed
epsilon_CHHP is Table 5's alpha3_CHHP (the only CHHP coefficient the
equation does not otherwise use); Eq. (323)'s GCF_HHHIS is the GCF_HHHI of
Eq. (325); Eq. (331)'s TREND_betaHH_t is TREND_betaHH * (quarters since
2022Q4); Eq. (331)'s PDT is Table 6's P_NELECT.
"""

from __future__ import annotations

import math

from ..calibration import PARAMETERS as P
from ..registry import Equation, Registry

L = math.log
SIM_ORIGIN = 143  # 2022Q4, the initial period of Table 6

# Eq. (324) reads GCF_HHNB two quarters back (the solver's GCF_HHNB_LAG).
SECOND_LAG_KEYS = ("GCF_HHNB_LAG",)

MANUAL_GAPS = {
    "epsilon_CHHP": "Eq. (318) epsilon_CHHP is not tabulated; alpha3_CHHP is read.",
    "GCF_HHHIS": (
        "Eq. (323) sums GCF_HHHIS, which no equation defines; Eq. (325) "
        "defines GCF_HHHI. Read as GCF_HHHI."
    ),
    "TREND_betaHH": (
        "Eq. (331) has a time-indexed TREND_betaHH_t; Table 5 gives one "
        "number. Read as a linear trend from 2022Q4."
    ),
}


def register(registry: Registry) -> None:
    """Register the §3.4.5 equations, manual Eqs. (310)-(366)."""

    def add(name: str, number: int, kind: str, func) -> None:
        registry.add(Equation(name, f"§3.4.5 eq. ({number})", kind, func))

    add("YP_HH", 310, "identity",
        lambda s, l: s["W"] + (s["INTR_HH"] + s["DIVR_HH"]) - s["INTP_HH"])
    add("INTR_HH", 311, "identity", lambda s, l: s["r_IBA_HH"] * l["IBA_HH"])
    add("INTP_HH", 312, "identity", lambda s, l: s["r_IBL_HH"] * l["IBL_HH"])
    add("DIVR_HH", 313, "behavioural",
        lambda s, l: P["beta_dhh"] * s["EQA_HH"] / s["EQL_NMFI"] * s["DIVP_NMFI"])
    add("YD_HH", 314, "identity",
        lambda s, l: s["YP_HH"] + s["SOCB"] - (s["SOCC"] + s["INTAX_HH"]))
    add("SOCC", 315, "identity", lambda s, l: s["SOCC_NMFI"] + s["SOCC_GVT"])
    add("SOCB", 316, "identity", lambda s, l: s["SOCB_NMFI"] + s["SOCB_GVT"])
    add("CONS_HH", 317, "identity", lambda s, l: s["CONS_HHP"] + s["CONS_HHPS"])
    add("CONS_HHP", 318, "behavioural",
        lambda s, l: l["CONS_HHP"] * math.exp(P["alpha3_CHHP"] * (
            P["alpha0_CHHP"] + P["alpha1_CHHP"] * L(l["YD_HH"])
            + P["alpha2_CHHP"] * L(l["FA_HH"]) - L(l["CONS_HHP"]))))
    add("CONS_HHPR", 319, "identity", lambda s, l: s["CONS_HHP"] / s["P_P"])
    add("CONS_HHPS", 320, "identity", lambda s, l: s["CONS_HHPSR"] * s["P_ELEC"])
    add("CONS_HHPSR", 321, "identity", lambda s, l: s["E_ELECH"])
    add("SAV_HH", 322, "identity", lambda s, l: s["YD_HH"] - s["CONS_HH"])
    add("GCF_HH", 323, "identity", lambda s, l: s["GCF_HHNB"] + s["GCF_HHHI"])
    add("GCF_HHNB", 324, "behavioural",
        lambda s, l: l["GCF_HHNB"] * math.exp(
            P["epsilon_GCFNB"] * (-P["alpha0_GCFNB"] + P["alpha1_GCFNB"] * L(l["HVAL"])
                                  - L(l["GCF_HHNB"]))
            - P["delta1_GCFNB"] * (L(l["GCF_HHNB"]) - L(l["GCF_HHNB_LAG"]))))
    add("GCF_HHHI", 325, "calibrated", lambda s, l: P["alpha_HHHI"] * l["GDP"])
    add("GCF_HHR", 326, "identity", lambda s, l: s["GCF_HH"] / s["P_P"])
    add("GCF_HHNBR", 327, "identity", lambda s, l: s["GCF_HHNB"] / s["P_P"])
    add("GCF_HHHIR", 328, "identity", lambda s, l: s["GCF_HHHI"] / s["P_P"])
    add("GCF_HHHIER", 329, "identity", lambda s, l: s["beta_GCFHH"] * s["GCF_HHHIR"])
    add("GCF_HHHINR", 330, "identity", lambda s, l: s["GCF_HHHIR"] - s["GCF_HHHIER"])
    add("beta_GCFHH", 331, "behavioural",
        lambda s, l: P["alpha0_betaHH"] + P["TREND_betaHH"] * (s["t_PS"] - SIM_ORIGIN)
        + P["alpha1_betaHH"] * (l["P_NELECT"] - l["P_ELEC"]))
    add("GCF_HHHIENR", 332, "identity",
        lambda s, l: s["GCF_HHHIER"] * P["kappa_hie"] * l["H_I"]
        / (P["kappa_hie"] * l["H_I"] + l["H_EN"]))
    add("GCF_HHHIEER", 333, "identity", lambda s, l: s["GCF_HHHIER"] - s["GCF_HHHIENR"])
    add("LENDM_HH", 334, "identity",
        lambda s, l: s["SAV_HH"] - s["GCF_HH"] + s["INSR"] + s["PENSR"] + s["PENS_ADJ"])
    add("DISC_HH", 335, "calibrated", lambda s, l: P["eta_HHT"] * l["GDP"])
    add("LEND_HH", 336, "identity", lambda s, l: s["LENDM_HH"] + s["DISC_HH"])
    add("IBATR_HH", 337, "identity",
        lambda s, l: s["LEND_HH"] + s["IBLTR_HH"]
        - (s["EQATR_HH"] + s["RESTR_HH"] + s["PENSTR"] + s["INSTR_"]))
    add("EQATR_HH", 338, "calibrated", lambda s, l: -P["alpha_EQAHH"] * l["EQA_HH"])
    add("PENSTR", 339, "identity", lambda s, l: s["PENS_ADJ"])
    add("INSTR_", 340, "identity", lambda s, l: s["INSR"] - P["alpha_INSTR"] * l["INS"])
    add("IBLTR_HH", 341, "calibrated", lambda s, l: P["alpha_IBLTR"] * s["HVAL"])
    add("RESTR_HH", 342, "calibrated", lambda s, l: P["eta_HHB"] * l["GDP"])
    add("OTIBA_HH", 343, "calibrated", lambda s, l: P["delta_IBAHH"] * l["IBA_HH"])
    add("OTEQA_HH", 344, "calibrated", lambda s, l: P["delta_EQAHH"] * l["EQA_HH"])
    add("OTIBL_HH", 345, "calibrated", lambda s, l: P["delta_IBLHH"] * l["IBL_HH"])
    add("OTRES_HH", 346, "calibrated", lambda s, l: P["delta_RESHH"] * l["RES_HH"])
    add("IBA_HH", 347, "identity", lambda s, l: l["IBA_HH"] + s["IBATR_HH"] + s["OTIBA_HH"])
    add("EQA_HH", 348, "identity", lambda s, l: l["EQA_HH"] + s["EQATR_HH"] + s["OTEQA_HH"])
    add("PENS", 349, "identity", lambda s, l: l["PENS"] + s["PENSTR"] + s["OTPENS"])
    add("INS", 350, "identity", lambda s, l: l["INS"] + s["INSTR_"] + s["OTINS"])
    add("IBL_HH", 351, "identity", lambda s, l: l["IBL_HH"] + s["IBLTR_HH"] + s["OTIBL_HH"])
    add("FA_HH", 352, "identity",
        lambda s, l: s["IBA_HH"] + s["EQA_HH"] + s["PENS"] + s["INS"])
    add("FL_HH", 353, "identity", lambda s, l: s["IBL_HH"])
    add("FNWM_HH", 354, "identity", lambda s, l: s["FA_HH"] - s["FL_HH"])
    add("RES_HH", 355, "identity", lambda s, l: l["RES_HH"] + s["RESTR_HH"] + s["OTRES_HH"])
    add("FNW_HH", 356, "identity", lambda s, l: s["FNWM_HH"] + s["RES_HH"])
    add("H", 357, "identity", lambda s, l: s["H_I"] + s["H_EN"] + s["H_EE"])
    add("HB", 358, "calibrated", lambda s, l: P["alpha_HB"] * s["GCF_HHNBR"])
    add("H_I", 359, "identity", lambda s, l: l["H_I"] - s["GCF_HHHIENR"] / s["CHI_ENR"])
    add("H_EN", 360, "identity",
        lambda s, l: l["H_EN"] + (1.0 - P["beta_HBE"]) * s["HB"]
        + s["GCF_HHHIENR"] / s["CHI_ENR"] - s["GCF_HHHIEER"] / s["CHI_EER"])
    add("H_EE", 361, "identity",
        lambda s, l: l["H_EE"] + P["beta_HBE"] * s["HB"] + s["GCF_HHHIEER"] / s["CHI_EER"])
    add("CHI_ENR", 362, "identity", lambda s, l: l["CHI_ENR"])
    add("CHI_EER", 363, "identity", lambda s, l: l["CHI_EER"])
    add("HVAL", 364, "identity", lambda s, l: s["H"] * s["PH"])
    # Eq. (365): error correction in log(PH*H/LF); solve for PH.
    add("PH", 365, "behavioural",
        lambda s, l: math.exp(L(l["PH"] * l["H"] / l["LF"]) + P["epsilon_PH"] * (
            P["alpha0_PH"] + P["alpha1_PH"] * L(l["YD_HH"] / l["LF"])
            + P["alpha2_PH"] * L(l["IBL_HH"] / l["LF"])
            - L(l["PH"] * l["H"] / l["LF"]))) * s["LF"] / s["H"])
    add("NW_HH", 366, "identity", lambda s, l: s["FNW_HH"] + s["HVAL"])
