"""DEFINE-UK Model Manual v1.1 §3.4.1 Non-financial corporations.

Equations (159)-(207): income, dividends and retained profit, Kaleckian
desired investment rationed by credit, the green/conventional split, net
lending and its discrepancy, financial transfers, revaluations (incl. the
logistic default rate), stocks, capital, net worth, and the leverage,
illiquidity, debt-service and credit-rationing ratios.

Clean-room implementation from the published manual (pp. 28-32). The
upstream R code is an output oracle only and is never read to write
equations here (see REIMPLEMENTATION.md).

Manual gaps (``MANUAL_GAPS``): GOS_P has no equation in the §3 body; the
dividend share beta_dnfc of Eq. (163) is not in Table 5.
"""

from __future__ import annotations

import math

from ..calibration import PARAMETERS as P
from ..registry import Equation, Registry

# Eq. (166) reads K_NFC two quarters back; the solver carries it as K_NFC_LAG.
SECOND_LAG_KEYS = ("K_NFC_LAG",)

# beta_dnfc is not tabulated. The cached baseline does not pin a constant:
# DIVR_NFC / (EQA_NFC / EQL_NMFI * DIVP_NMFI) drifts 0.74 -> 1.06 over
# 2023Q1-2040Q4, so the oracle's Eq. (163) has another form. 1.0 (dividends
# in proportion to the equity share, the text's reading) is used.
BETA_DNFC = 1.0

MANUAL_GAPS = {
    "GOS_P": (
        "Eq. (159) reads the production module's gross operating surplus "
        "GOS_P, which no §3 equation defines (Table 6 cites a stale "
        "'Eq. (53)'). Implemented as the production column residual "
        "GO_P - COST_P (Eq. (48) cost bill)."
    ),
    "beta_dnfc": (
        "Eq. (163) uses beta_dnfc, which §5 Table 5 does not list "
        f"(beta_dhh and beta_dps are listed). {BETA_DNFC} is used: the plain "
        "equity share the text describes. The oracle's ratio is not constant "
        "(0.74-1.06), so its form differs."
    ),
}


def gos_p(s) -> float:
    """MANUAL_GAPS["GOS_P"]: production gross operating surplus GO_P - COST_P."""
    return s["GO_P"] - s["COST_P"]


def register(registry: Registry) -> None:
    """Register the §3.4.1 equations, manual Eqs. (159)-(207)."""

    def add(name: str, number: int, kind: str, func) -> None:
        registry.add(Equation(name, f"§3.4.1 eq. ({number})", kind, func))

    add("YP_NFC", 159, "identity",
        lambda s, l: gos_p(s) + s["INTR_NFC"] - s["INTP_NFC"])
    add("INTR_NFC", 160, "identity", lambda s, l: s["r_IBA_NFC"] * l["IBA_NFC"])
    add("INTP_NFC", 161, "identity", lambda s, l: s["r_IBL_NFC"] * l["IBL_NFC"])
    add("YD_NFC", 162, "identity", lambda s, l: s["YP_NFC"] - s["INTAX_NFC"])
    add("DIVR_NFC", 163, "behavioural",
        lambda s, l: BETA_DNFC * s["EQA_NFC"] / s["EQL_NMFI"] * s["DIVP_NMFI"])
    add("DIVP_NFC", 164, "behavioural", lambda s, l: P["alpha_DIVP_NFC"] * s["YD_NFC"])
    add("RP_NFC", 165, "identity",
        lambda s, l: s["YD_NFC"] + s["DIVR_NFC"] - s["DIVP_NFC"])
    add("GCF_NFCD", 166, "behavioural",
        lambda s, l: l["K_NFC"] * (
            P["alpha0_GCFNFC"] + P["alpha1_GCFNFC"] * (s["u"] - P["u_T"])
            + P["alpha2_GCFNFC"] * l["GCF_NFCD"] / l["K_NFC_LAG"]))
    add("GCF_NFC", 167, "identity", lambda s, l: (1.0 - s["CR_NFC"]) * s["GCF_NFCD"])
    add("beta_nfc", 168, "behavioural",
        lambda s, l: P["alpha0_betaNFC"]
        + P["alpha1_betaNFC"] * math.tanh(s["P_NELEC"] / s["P_ELEC"])
        + P["alpha2_betaNFC"] * l["COST_ER"] / l["E"])
    add("GCF_NFCG", 169, "identity", lambda s, l: s["beta_nfc"] * s["GCF_NFC"])
    add("GCF_NFCC", 170, "identity", lambda s, l: s["GCF_NFC"] - s["GCF_NFCG"])
    add("GCF_NFCR", 171, "identity", lambda s, l: s["GCF_NFCGR"] + s["GCF_NFCCR"])
    add("GCF_NFCGR", 172, "identity", lambda s, l: s["GCF_NFCG"] / s["P_P"])
    add("GCF_NFCCR", 173, "identity", lambda s, l: s["GCF_NFCC"] / s["P_P"])
    add("LENDM_NFC", 174, "identity", lambda s, l: s["RP_NFC"] - s["GCF_NFC"])
    add("DISC_NFC", 175, "calibrated", lambda s, l: P["eta_NFCT"] * l["GDP"])
    add("LEND_NFC", 176, "identity", lambda s, l: s["LENDM_NFC"] + s["DISC_NFC"])
    add("IBATR_NFC", 177, "calibrated", lambda s, l: P["alpha_IBANFC"] * s["GO_P"])
    add("EQATR_NFC", 178, "calibrated", lambda s, l: P["alpha_EQANFC"] * s["GO_P"])
    add("EQLTR_NFC", 179, "identity",
        lambda s, l: (1.0 - P["theta_psb"]) * s["EQATR_NMFI"])
    add("IBLTR_NFC", 180, "identity",
        lambda s, l: (s["IBATR_NFC"] + s["EQATR_NFC"] + s["RESTR_NFC"])
        - (s["LEND_NFC"] + s["EQLTR_NFC"]))
    add("RESTR_NFC", 181, "calibrated", lambda s, l: P["eta_NFCB"] * l["GDP"])
    add("OTIBA_NFC", 182, "calibrated", lambda s, l: P["delta_IBANFC"] * l["IBA_NFC"])
    add("OTEQA_NFC", 183, "identity",
        lambda s, l: s["OTEQL_NMFI"] - (s["OTEQA_HH"] + s["OTEQA_PS"]))
    add("OTEQL_NFC", 184, "behavioural",
        lambda s, l: s["DIVP_NFC"] / (s["r_IBL_GVT"] + P["beta_EQLNFC"])
        - l["EQL_NFC"])
    add("OTIBL_NFC", 185, "identity", lambda s, l: -s["DEF_NFC"] * l["IBL_NFC"])
    add("DEF_NFC", 186, "behavioural",
        lambda s, l: P["def_max"] / (1.0 + P["def0_NFC"] * math.exp(
            P["def1"] - P["def2"] * l["ILLIQ_NFC"])))
    add("OTRES_NFC", 187, "calibrated", lambda s, l: P["delta_RESNFC"] * l["RES_NFC"])
    add("IBA_NFC", 188, "identity",
        lambda s, l: l["IBA_NFC"] + s["IBATR_NFC"] + s["OTIBA_NFC"])
    add("EQA_NFC", 189, "identity",
        lambda s, l: l["EQA_NFC"] + s["EQATR_NFC"] + s["OTEQA_NFC"])
    add("IBL_NFC", 190, "identity",
        lambda s, l: l["IBL_NFC"] + s["IBLTR_NFC"] + s["OTIBL_NFC"])
    add("EQL_NFC", 191, "identity",
        lambda s, l: l["EQL_NFC"] + s["EQLTR_NFC"] + s["OTEQL_NFC"])
    add("FA_NFC", 192, "identity", lambda s, l: s["IBA_NFC"] + s["EQA_NFC"])
    add("FL_NFC", 193, "identity", lambda s, l: s["IBL_NFC"] + s["EQL_NFC"])
    add("FNWM_NFC", 194, "identity", lambda s, l: s["FA_NFC"] - s["FL_NFC"])
    add("RES_NFC", 195, "identity",
        lambda s, l: l["RES_NFC"] + s["RESTR_NFC"] + s["OTRES_NFC"])
    add("FNW_NFC", 196, "identity", lambda s, l: s["FNWM_NFC"] + s["RES_NFC"])
    add("K_NFCCR", 197, "identity",
        lambda s, l: (1.0 - s["delta_KP"]) * l["K_NFCCR"] + s["GCF_NFCCR"])
    add("K_NFCGR", 198, "identity",
        lambda s, l: (1.0 - s["delta_KP"]) * l["K_NFCGR"] + s["GCF_NFCGR"])
    add("K_NFCR", 199, "identity", lambda s, l: s["K_NFCCR"] + s["K_NFCGR"])
    add("K_NFC", 200, "identity", lambda s, l: s["K_NFCC"] + s["K_NFCG"])
    add("K_NFCC", 201, "identity", lambda s, l: s["K_NFCCR"] * s["P_P"])
    add("K_NFCG", 202, "identity", lambda s, l: s["K_NFCGR"] * s["P_P"])
    add("NW_NFC", 203, "identity", lambda s, l: s["FNW_NFC"] + s["K_NFC"])
    add("LEV_NFC", 204, "identity", lambda s, l: s["IBL_NFC"] / s["K_NFC"])
    add("ILLIQ_NFC", 205, "identity",
        lambda s, l: (s["INTP_NFC"] + s["INTAX_NFC"] + s["DIVP_NFC"]
                      + s["GCF_NFC"] + s["delta_KP"] * s["K_NFC"]
                      + s["IBATR_NFC"] + s["EQATR_NFC"])
        / (gos_p(s) + s["INTR_NFC"] + s["DIVR_NFC"] + s["EQLTR_NFC"]
           + s["IBLTR_NFC"]))
    add("DSR_NFC", 206, "identity",
        lambda s, l: (s["YD_NFC"] - s["delta_KP"] * l["K_NFC"] + s["INTP_NFC"])
        / s["INTP_NFC"])
    add("CR_NFC", 207, "behavioural",
        lambda s, l: 1.0 / (1.0 + math.exp(-(
            P["alpha0_CRNFC"] + P["alpha1_CRNFC"] * l["CR_NFC"]
            - P["alpha2_CRNFC"] * l["DSR_NFC"]
            + P["alpha3_CRNFC"] * l["FL_MFI"] / l["FA_MFI"]))))
