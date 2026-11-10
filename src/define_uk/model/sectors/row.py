"""DEFINE-UK Model Manual v1.1 §3.4.6 Rest of the world.

Equations (367)-(396): trade (nominal import and export equations in logs),
world demand and prices, the exchange rate block, net property income,
net lending, net transfers, revaluations and the net stocks.

Clean-room implementation from the published manual (pp. 45-48). The
upstream R code is an output oracle only and is never read to write
equations here (see REIMPLEMENTATION.md).

Exogenous inputs: ROW_Pg (world price growth, Eq. (376); the CSVs print the
quarterly path as RoW_Pg). Eq. (382)'s alpha_DIVNRoW is Table 5's
beta_DIVNROW (DIVN_RoW / EQN_RoW_{t-1} = 0.00349 in every quarter of the
cached baseline).
"""

from __future__ import annotations

import math

from ..calibration import PARAMETERS as P
from ..registry import Equation, Registry

L = math.log


def register(registry: Registry) -> None:
    """Register the §3.4.6 equations, manual Eqs. (367)-(396)."""

    def add(name: str, number: int, kind: str, func) -> None:
        registry.add(Equation(name, f"§3.4.6 eq. ({number})", kind, func))

    add("YP_ROW", 367, "identity", lambda s, l: s["IMP"] - s["EXP"])
    add("DY", 368, "identity", lambda s, l: s["CONS"] + s["GCF"] + s["EXP"])
    add("ROW_D", 369, "identity", lambda s, l: s["ROW_DR"] * s["PF"])
    add("IMP", 370, "behavioural",
        lambda s, l: math.exp(
            P["alpha0_IMP"] + P["alpha1_IMP"] * L(l["IMP"])
            + P["alpha2_IMP"] * L(l["DY"])
            + P["alpha3_IMP"] * L((P["beta1_IMP"] * s["GCF"]
                                   + P["beta2_IMP"] * s["GCF_PS"]) / s["DY"])
            + P["alpha4_IMP"] * L(s["PI"] / s["P_P"])
            + P["delta1_IMP"] * (L(s["DY"]) - L(l["DY"]))))
    add("EXP", 371, "behavioural",
        lambda s, l: math.exp(
            P["alpha0_EXP"] + P["alpha1_EXP"] * L(l["EXP"])
            + P["alpha2_EXP"] * L(l["ROW_D"]) + P["alpha3_EXP"] * L(l["REER"])
            + P["delta1_EXP"] * (L(s["ROW_D"]) - L(l["ROW_D"]))))
    add("ROW_DR", 372, "calibrated", lambda s, l: P["ROW_Dg"] * l["ROW_DR"])
    add("IMP_R", 373, "identity", lambda s, l: s["IMP"] / s["PI"])
    add("EXP_R", 374, "identity", lambda s, l: s["EXP"] / s["PE"])
    add("ER", 375, "identity", lambda s, l: l["ER"])
    add("PF", 376, "calibrated", lambda s, l: s["ROW_Pg"] * l["PF"])
    add("PE", 377, "identity", lambda s, l: s["P_P"])
    add("PI", 378, "identity", lambda s, l: s["PF"] * s["ER"] * s["IADJ"])
    add("IADJ", 379, "identity", lambda s, l: l["IADJ"])
    add("REER", 380, "identity", lambda s, l: s["PE"] / (s["ER"] * s["PF"]))
    add("INTN_ROW", 381, "identity",
        lambda s, l: s["r_IBL_GVT"] * l["IBL_GVT_ROW"] + s["r_IBN_ROW"] * l["IBN_ROW"])
    add("DIVN_ROW", 382, "calibrated", lambda s, l: P["beta_DIVNROW"] * l["EQN_ROW"])
    add("LENDM_ROW", 383, "identity",
        lambda s, l: s["YP_ROW"] + s["INTN_ROW"] + s["DIVN_ROW"])
    add("DISC_ROW", 384, "calibrated", lambda s, l: P["eta_ROWT"] * l["GDP"])
    add("LEND_ROW", 385, "identity", lambda s, l: s["LENDM_ROW"] + s["DISC_ROW"])
    add("IBNTR_ROW", 386, "identity",
        lambda s, l: s["LEND_ROW"] - (s["IBLTR_GVT_ROW"] + s["EQNTR_ROW"] + s["RESTR_ROW"]))
    add("EQNTR_ROW", 387, "calibrated", lambda s, l: P["alpha_EQNTRROW"] * s["YP_ROW"])
    add("RESTR_ROW", 388, "calibrated", lambda s, l: P["eta_ROWB"] * l["GDP"])
    add("OTIBA_ROW", 389, "calibrated", lambda s, l: P["delta_IBAROW"] * l["IBN_ROW"])
    add("OTEQN_ROW", 390, "calibrated", lambda s, l: P["delta_EQNROW"] * l["EQN_ROW"])
    add("OTRES_ROW", 391, "calibrated", lambda s, l: P["delta_RESROW"] * l["RES_ROW"])
    add("IBN_ROW", 392, "identity",
        lambda s, l: l["IBN_ROW"] + s["IBNTR_ROW"] + s["OTIBA_ROW"])
    add("EQN_ROW", 393, "identity",
        lambda s, l: l["EQN_ROW"] + s["EQNTR_ROW"] + s["OTEQN_ROW"])
    add("FNWM_ROW", 394, "identity",
        lambda s, l: s["IBN_ROW"] + s["EQN_ROW"] + s["IBL_GVT_ROW"])
    add("RES_ROW", 395, "identity",
        lambda s, l: l["RES_ROW"] + s["RESTR_ROW"] + s["OTRES_ROW"])
    add("FNW_ROW", 396, "identity", lambda s, l: s["FNWM_ROW"] + s["RES_ROW"])
