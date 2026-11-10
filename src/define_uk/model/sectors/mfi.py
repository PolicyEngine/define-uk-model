"""DEFINE-UK Model Manual v1.1 §3.4.2 Monetary financial institutions.

Equations (208)-(217). MFIs are the model's residual sector: Eq. (211) sets
their lending discrepancy to minus the sum of every other sector's, and
Eqs. (213), (214), (216) make their assets, liabilities and residual
instrument the counterparts of every other sector's. Together with the
transactions-matrix row sums this is what closes the stock-flow accounts:
Σ_s LEND_s = 0 is not imposed anywhere, it is the model's redundant
equation, and ``define_uk.model.accounting`` checks it on solved states.

Clean-room implementation from the published manual (pp. 32-33). The
upstream R code is an output oracle only and is never read to write
equations here (see REIMPLEMENTATION.md).

IBA_RoW / IBL_RoW in Eqs. (213)-(214): the RoW holds one net position,
IBN_ROW (§3.4.6), recorded on the asset side (see accounting.py), so
Eq. (214) reads IBN_ROW and Eq. (213) has no RoW term.
"""

from __future__ import annotations

from ..registry import Equation, Registry


def register(registry: Registry) -> None:
    """Register the §3.4.2 equations, manual Eqs. (208)-(217)."""

    def add(name: str, number: int, kind: str, func) -> None:
        registry.add(Equation(name, f"§3.4.2 eq. ({number})", kind, func))

    add("LENDM_MFI", 208, "identity", lambda s, l: s["INTR_MFI"] - s["INTP_MFI"])
    add("INTR_MFI", 209, "identity",
        lambda s, l: s["INTP_NFC"] + s["INTP_PS"] + s["INTP_NMFI"]
        + s["INTP_GVT"] + s["INTP_HH"])
    add("INTP_MFI", 210, "identity",
        lambda s, l: s["INTR_NFC"] + s["INTR_PS"] + s["INTR_NMFI"]
        + s["INTR_GVT"] + s["INTR_HH"] + s["INTN_ROW"])
    add("DISC_MFI", 211, "identity",
        lambda s, l: -(s["DISC_NFC"] + s["DISC_NMFI"] + s["DISC_GVT"]
                       + s["DISC_HH"] + s["DISC_ROW"]))
    add("LEND_MFI", 212, "identity", lambda s, l: s["LENDM_MFI"] + s["DISC_MFI"])
    add("FA_MFI", 213, "identity",
        lambda s, l: s["IBL_NFC"] + s["IBL_PS"] + s["IBL_NMFI"]
        + s["IBL_GVT_MFI"] + s["IBL_HH"])
    add("FL_MFI", 214, "identity",
        lambda s, l: s["IBA_NFC"] + s["IBA_PS"] + s["IBA_NMFI"]
        + s["IBA_GVT"] + s["IBA_HH"] + s["IBN_ROW"])
    add("FNWM_MFI", 215, "identity", lambda s, l: s["FA_MFI"] - s["FL_MFI"])
    add("RES_MFI", 216, "identity",
        lambda s, l: -(s["RES_HH"] + s["RES_NFC"] + s["RES_NMFI"]
                       + s["RES_PS"] + s["RES_GVT"] + s["RES_ROW"]))
    add("FNW_MFI", 217, "identity", lambda s, l: s["FNWM_MFI"] + s["RES_MFI"])
