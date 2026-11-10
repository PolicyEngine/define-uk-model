"""DEFINE-UK Model Manual v1.1 §3.4.4 Government.

Equations (252)-(309): disposable income, indirect/carbon/income taxes with
rates converging to long-run values, social contributions and benefits,
consumption and investment, net lending, bond transfers split across MFIs,
NMFIs and RoW, revaluations, stocks, capital and net worth.

Clean-room implementation from the published manual (pp. 36-41). The
upstream R code is an output oracle only and is never read to write
equations here (see REIMPLEMENTATION.md).

Exogenous inputs: GCF_GVTBASE (the OBR baseline path of Eq. (272); read
from the reference path's GCF_GVT when not given), W_PUB (§3.3.1), P_ETSRB,
SUBS_GVT (Eq. (281) subsidy spending; Table 6 0, the CSVs do not print it),
GCF_GVTNFFR (Eq. (276); see MANUAL_GAPS).
"""

from __future__ import annotations

from ..calibration import PARAMETERS as P
from ..registry import Equation, Registry

MANUAL_GAPS = {
    "YD_GVT_power_income": (
        "The text before Eq. (252) says government disposable income "
        "includes its share GVT_ELECS of power-sector gross operating "
        "surplus; the printed Eq. (252) has no such term. Implemented as "
        "printed."
    ),
    "GCF_GVTNFFR": (
        "Eq. (276) accumulates K_GVTNFFR from GCF_GVTNFFR, which no "
        "equation defines and the CSVs do not print. It is an exogenous "
        "input (0 unless given); the green public investment scenarios "
        "move it, so under the manual as printed government power "
        "investment never reaches GCF (Eq. (23)) or the budget (Eq. (281))."
    ),
}


def _converge(name: str, lr: str):
    return lambda s, l: l[name] - P["tau_gvt"] * (l[name] - P[lr])


def register(registry: Registry) -> None:
    """Register the §3.4.4 equations, manual Eqs. (252)-(309)."""

    def add(name: str, number: int, kind: str, func) -> None:
        registry.add(Equation(name, f"§3.4.4 eq. ({number})", kind, func))

    add("YD_GVT", 252, "identity",
        lambda s, l: (s["ITAX"] + s["INTAX"] + s["SOCC_GVT"] + s["INTR_GVT"])
        - (s["SOCB_GVT"] + s["INTP_GVT"]))
    add("ITAX", 253, "identity", lambda s, l: s["ITAX_P"] + s["ITAX_PS"])
    add("ITAX_P", 254, "identity",
        lambda s, l: s["ITAXR_P"] * s["GO_P"] + s["ITAX_NELEC"])
    add("ITAX_NELEC", 255, "identity",
        lambda s, l: s["COV_ETSP"] * s["P_ETS"] * s["EMIS_NELEC"])
    add("ITAXR_P", 256, "calibrated", _converge("ITAXR_P", "ITAXR_PLR"))
    add("ITAX_PS", 257, "identity",
        lambda s, l: s["ITAXR_PS"] * s["GO_PS"]
        + s["COV_ETSPS"] * s["P_ETS"] * s["EMIS_ELEC"])
    add("ITAXR_PS", 258, "calibrated", _converge("ITAXR_PS", "ITAXR_PSLR"))
    add("P_ETS", 259, "identity", lambda s, l: s["P_ETSRB"])
    add("INTAX", 260, "identity", lambda s, l: s["INTAX_NFC"] + s["INTAX_HH"])
    add("INTAX_NFC", 261, "identity", lambda s, l: s["INTAXR_NFC"] * s["W"])
    add("INTAX_HH", 262, "identity", lambda s, l: s["INTAXR_HH"] * s["W"])
    add("INTAXR_NFC", 263, "calibrated", _converge("INTAXR_NFC", "INTAXR_NFCLR"))
    add("INTAXR_HH", 264, "calibrated", _converge("INTAXR_HH", "INTAXR_HHLR"))
    add("INTR_GVT", 265, "identity", lambda s, l: s["r_IBA_GVT"] * l["IBA_GVT"])
    add("INTP_GVT", 266, "identity", lambda s, l: s["r_IBL_GVT"] * l["IBL_GVT"])
    add("SOCC_GVT", 267, "identity", lambda s, l: s["SOCCR_GVT"] * s["W"])
    add("SOCCR_GVT", 268, "calibrated", _converge("SOCCR_GVT", "SOCCR_GVTLR"))
    add("SOCB_GVT", 269, "behavioural",
        lambda s, l: s["GDP"] * (P["alpha0_SOCB"]
                                 + P["alpha1_SOCB"] * l["SOCB_GVT"] / l["GDP"]
                                 + P["alpha2_SOCB"] * s["ru"]))
    add("CONS_GVT", 270, "identity", lambda s, l: s["W_PUB"] + s["OCONS_GVT"])
    add("OCONS_GVT", 271, "calibrated", lambda s, l: P["alpha_OCONSGVT"] * l["GDP"])
    add("GCF_GVT", 272, "identity", lambda s, l: s["GCF_GVTBASE"])
    add("beta_gvt", 273, "identity", lambda s, l: s["beta_nfc"])
    add("GCF_GVTG", 274, "identity", lambda s, l: s["beta_gvt"] * s["GCF_GVT"])
    add("GCF_GVTC", 275, "identity", lambda s, l: s["GCF_GVT"] - s["GCF_GVTG"])
    add("K_GVTNFFR", 276, "identity",
        lambda s, l: (1.0 - s["delta_KPS"]) * l["K_GVTNFFR"] + s["GCF_GVTNFFR"])
    add("CONS_GVTR", 277, "identity", lambda s, l: s["CONS_GVT"] / s["P_P"])
    add("GCF_GVTR", 278, "identity", lambda s, l: s["GCF_GVTGR"] + s["GCF_GVTCR"])
    add("GCF_GVTGR", 279, "identity", lambda s, l: s["GCF_GVTG"] / s["P_P"])
    add("GCF_GVTCR", 280, "identity", lambda s, l: s["GCF_GVTC"] / s["P_P"])
    add("LENDM_GVT", 281, "identity",
        lambda s, l: s["YD_GVT"] - (s["CONS_GVT"] + s["GCF_GVT"] + s["SUBS_GVT"]))
    add("DISC_GVT", 282, "calibrated", lambda s, l: P["eta_GVTT"] * l["GDP"])
    add("LEND_GVT", 283, "identity", lambda s, l: s["LENDM_GVT"] + s["DISC_GVT"])
    add("IBATR_GVT", 284, "calibrated", lambda s, l: P["alpha_IBAGVT"] * s["GO"])
    add("IBLTR_GVT", 285, "identity",
        lambda s, l: s["IBATR_GVT"] + s["RESTR_GVT"] - s["LEND_GVT"])
    for name, n, beta in (("IBLTR_GVT_MFI", 286, "beta_IBLGVTMFI"),
                          ("IBLTR_GVT_NMFI", 287, "beta_IBLGVTNMFI"),
                          ("IBLTR_GVT_ROW", 288, "beta_IBLGVTROW")):
        add(name, n, "calibrated", lambda s, l, b=P[beta]: b * s["IBLTR_GVT"])
    add("RESTR_GVT", 289, "calibrated", lambda s, l: P["eta_GVTB"] * l["GDP"])
    add("OTIBA_GVT", 290, "calibrated", lambda s, l: P["delta_IBAGVT"] * l["IBA_GVT"])
    add("OTIBL_GVT", 291, "calibrated", lambda s, l: P["delta_IBLGVT"] * l["IBL_GVT"])
    add("OTRES_GVT", 292, "calibrated", lambda s, l: P["delta_RESGVT"] * l["RES_GVT"])
    add("IBA_GVT", 293, "identity",
        lambda s, l: l["IBA_GVT"] + s["IBATR_GVT"] + s["OTIBA_GVT"])
    add("IBL_GVT", 294, "identity",
        lambda s, l: s["IBL_GVT_MFI"] + s["IBL_GVT_NMFI"] + s["IBL_GVT_ROW"])
    for name, tr, n, beta in (("IBL_GVT_MFI", "IBLTR_GVT_MFI", 295, "beta_IBLGVTMFI"),
                              ("IBL_GVT_NMFI", "IBLTR_GVT_NMFI", 296, "beta_IBLGVTNMFI"),
                              ("IBL_GVT_ROW", "IBLTR_GVT_ROW", 297, "beta_IBLGVTROW")):
        add(name, n, "identity",
            lambda s, l, k=name, tr=tr, b=P[beta]: l[k] + s[tr] + b * s["OTIBL_GVT"])
    add("FA_GVT", 298, "identity", lambda s, l: s["IBA_GVT"])
    add("FL_GVT", 299, "identity", lambda s, l: s["IBL_GVT"])
    add("FNWM_GVT", 300, "identity", lambda s, l: s["FA_GVT"] - s["FL_GVT"])
    add("RES_GVT", 301, "identity",
        lambda s, l: l["RES_GVT"] + s["RESTR_GVT"] + s["OTRES_GVT"])
    add("FNW_GVT", 302, "identity", lambda s, l: s["FNWM_GVT"] + s["RES_GVT"])
    add("K_GVTCR", 303, "identity",
        lambda s, l: (1.0 - s["delta_KP"]) * l["K_GVTCR"] + s["GCF_GVTCR"])
    add("K_GVTGR", 304, "identity",
        lambda s, l: (1.0 - s["delta_KP"]) * l["K_GVTGR"] + s["GCF_GVTGR"])
    add("K_GVTR", 305, "identity", lambda s, l: s["K_GVTCR"] + s["K_GVTGR"])
    add("K_GVT", 306, "identity", lambda s, l: s["K_GVTC"] + s["K_GVTG"])
    add("K_GVTC", 307, "identity", lambda s, l: s["K_GVTCR"] * s["P_P"])
    add("K_GVTG", 308, "identity", lambda s, l: s["K_GVTGR"] * s["P_P"])
    add("NW_GVT", 309, "identity", lambda s, l: s["FNW_GVT"] + s["K_GVT"])
