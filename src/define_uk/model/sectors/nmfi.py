"""DEFINE-UK Model Manual v1.1 §3.4.3 Non-monetary financial institutions.

Equations (218)-(251): income and dividends (NMFIs are the counterpart of
every dividend flow and equity asset), pension and insurance income, social
contributions and benefits, net lending, transfers, revaluations, stocks.

Clean-room implementation from the published manual (pp. 33-36). The
upstream R code is an output oracle only and is never read to write
equations here (see REIMPLEMENTATION.md).

Eq. (229) prints DISC_NMFI on GDP_t; every other lending discrepancy
(Eqs. (175), (282), (335), (384)) uses GDP_{t-1}. Implemented as printed.
"""

from __future__ import annotations

from ..calibration import PARAMETERS as P
from ..registry import Equation, Registry


def _pens_share(l) -> float:
    return l["PENS"] / (l["PENS"] + l["INS"])


def register(registry: Registry) -> None:
    """Register the §3.4.3 equations, manual Eqs. (218)-(251)."""

    def add(name: str, number: int, kind: str, func) -> None:
        registry.add(Equation(name, f"§3.4.3 eq. ({number})", kind, func))

    add("YD_NMFI", 218, "identity",
        lambda s, l: (s["INTR_NMFI"] + s["DIVR_NMFI"])
        - (s["INTP_NMFI"] + s["DIVP_NMFI"]))
    add("INTR_NMFI", 219, "identity",
        lambda s, l: s["r_IBA_NMFI"] * l["IBA_NMFI"]
        + s["r_IBL_GVT"] * l["IBL_GVT_NMFI"])
    add("INTP_NMFI", 220, "identity", lambda s, l: s["r_IBL_NMFI"] * l["IBL_NMFI"])
    add("DIVR_NMFI", 221, "identity", lambda s, l: s["DIVP_NFC"] + s["DIVP_PS"])
    add("DIVP_NMFI", 222, "behavioural",
        lambda s, l: P["alpha_DIVP_NMFI"]
        * (s["DIVR_NMFI"] + s["INTR_NMFI"] - s["INTP_NMFI"]))
    add("PENSR", 223, "behavioural",
        lambda s, l: P["alpha_PENSR"] * l["YD_NMFI"] * _pens_share(l))
    add("INSR", 224, "behavioural",
        lambda s, l: P["alpha_INSR"] * l["YD_NMFI"] * (1.0 - _pens_share(l)))
    add("SOCC_NMFI", 225, "behavioural",
        lambda s, l: s["PENSR"] + P["alpha_SOCCW"] * s["W"])
    add("SOCB_NMFI", 226, "behavioural", lambda s, l: P["alpha_SOCBPENS"] * l["PENS"])
    add("PENS_ADJ", 227, "identity", lambda s, l: s["SOCC_NMFI"] - s["SOCB_NMFI"])
    add("LENDM_NMFI", 228, "identity",
        lambda s, l: s["YD_NMFI"] - s["INSR"] - s["PENSR"] + s["SOCC_NMFI"]
        - s["SOCB_NMFI"] - s["PENS_ADJ"])
    add("DISC_NMFI", 229, "calibrated", lambda s, l: P["eta_NMFIT"] * s["GDP"])
    add("LEND_NMFI", 230, "identity", lambda s, l: s["LENDM_NMFI"] + s["DISC_NMFI"])
    add("IBATR_NMFI", 231, "calibrated", lambda s, l: P["alpha_IBANMFI"] * s["GO"])
    add("EQLTR_NMFI", 232, "identity",
        lambda s, l: s["EQATR_NFC"] + s["EQATR_PS"] + s["EQATR_HH"]
        + s["EQNTR_ROW"])
    add("EQATR_NMFI", 233, "calibrated",
        lambda s, l: P["psi_EQNMFI"] * s["EQLTR_NMFI"])
    add("IBLTR_NMFI", 234, "identity",
        lambda s, l: (s["IBATR_NMFI"] + s["EQATR_NMFI"] + s["IBLTR_GVT_NMFI"]
                      + s["RESTR_NMFI"])
        - (s["LEND_NMFI"] + s["EQLTR_NMFI"] + s["PENSTR"] + s["INSTR_"]))
    add("RESTR_NMFI", 235, "calibrated", lambda s, l: P["eta_NMFIB"] * l["GDP"])
    add("OTIBA_NMFI", 236, "calibrated", lambda s, l: P["delta_IBANMFI"] * l["IBA_NMFI"])
    add("OTIBL_NMFI", 237, "calibrated", lambda s, l: P["delta_IBLNMFI"] * l["IBL_NMFI"])
    add("OTRES_NMFI", 238, "calibrated", lambda s, l: P["delta_RESNMFI"] * l["RES_NMFI"])
    add("OTEQA_NMFI", 239, "identity", lambda s, l: s["OTEQL_NFC"] + s["OTEQL_PS"])
    add("OTEQL_NMFI", 240, "behavioural",
        lambda s, l: s["DIVP_NMFI"] / (s["r_IBL_GVT"] + P["beta_EQLNMFI"])
        - l["EQL_NMFI"])

    def _ot_net(s):
        return (s["OTIBA_NMFI"] + P["beta_IBLGVTNMFI"] * s["OTIBL_GVT"]
                + s["OTEQA_NMFI"] - s["OTIBL_NMFI"] - s["OTEQL_NMFI"])

    add("OTPENS", 241, "identity", lambda s, l: _ot_net(s) * _pens_share(l))
    add("OTINS", 242, "identity", lambda s, l: _ot_net(s) * (1.0 - _pens_share(l)))
    add("IBA_NMFI", 243, "identity",
        lambda s, l: l["IBA_NMFI"] + s["IBATR_NMFI"] + s["OTIBA_NMFI"])
    add("EQA_NMFI", 244, "identity",
        lambda s, l: l["EQA_NMFI"] + s["EQATR_NMFI"] + s["OTEQA_NMFI"])
    add("IBL_NMFI", 245, "identity",
        lambda s, l: l["IBL_NMFI"] + s["IBLTR_NMFI"] + s["OTIBL_NMFI"])
    add("EQL_NMFI", 246, "identity",
        lambda s, l: s["EQA_HH"] + s["EQA_NFC"] + s["EQA_PS"] + s["EQN_ROW"])
    add("FA_NMFI", 247, "identity",
        lambda s, l: s["IBA_NMFI"] + s["IBL_GVT_NMFI"] + s["EQA_NMFI"])
    add("FL_NMFI", 248, "identity",
        lambda s, l: s["IBL_NMFI"] + s["EQL_NMFI"] + s["PENS"] + s["INS"])
    add("FNWM_NMFI", 249, "identity", lambda s, l: s["FA_NMFI"] - s["FL_NMFI"])
    add("RES_NMFI", 250, "identity",
        lambda s, l: l["RES_NMFI"] + s["RESTR_NMFI"] + s["OTRES_NMFI"])
    add("FNW_NMFI", 251, "identity", lambda s, l: s["FNWM_NMFI"] + s["RES_NMFI"])
