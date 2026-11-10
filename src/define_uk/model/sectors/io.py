"""DEFINE-UK Model Manual v1.1 §3.3.3 Input-output calculations.

Equations (139)-(158): the technical coefficients of the two-sector
(production, power) input-output system, the real and nominal intermediate
consumption flows they imply, and the closed-form inverse of the 2x2
(I - A) matrix that §3.3.1 Eq. (46) and §3.3.2 Eq. (73) use as Leontief
multipliers.

Clean-room implementation from the published manual (pp. 26-27). The
upstream R code is an output oracle only and is never read to write
equations here (see REIMPLEMENTATION.md).

Subscript order (manual footnote 23): product first, purchasing sector
second, so alpha_FUELPS is fuel bought by the power sector and alpha_PSP is
electricity bought by production.

Exogenous to this section
-------------------------
epsilon (energy intensity) and theta_P (electrification of production) come
from the §3.1 ecosystem block; beta_NFF (non-fossil share) from §3.3.2;
GO_P/GO_PR/GO_PS/GO_PSR, P_P, P_FUEL and P_ELEC from §3.3.1-§3.3.2.

Known manual gap (see ``MANUAL_GAPS``)
-------------------------------------
Eq. (143) prints the reference coefficient as alpha_FUELPSR; §5 Table 5
tabulates it as alpha_FUELPSLR (0.3233), alongside the other long-run
coefficients alpha_PPLR, alpha_PSPSLR and alpha_OPPSLR. We read the
tabulated name.
"""

from __future__ import annotations

from ..calibration import PARAMETERS
from ..registry import Equation, Registry

EXOGENOUS_TO_SECTION = (
    "epsilon", "theta_P", "beta_NFF",
    "GO_P", "GO_PR", "GO_PS", "GO_PSR",
    "P_P", "P_FUEL", "P_ELEC",
)

MANUAL_GAPS = {
    "alpha_FUELPSR": (
        "Eq. (143) prints alpha_FUELPSR; §5 Table 5 tabulates the same "
        "coefficient as alpha_FUELPSLR = 0.3233. The tabulated value is used."
    ),
}

_A_PPLR = PARAMETERS["alpha_PPLR"]
_A_PSPSLR = PARAMETERS["alpha_PSPSLR"]
_A_OPPSLR = PARAMETERS["alpha_OPPSLR"]
_A_FUELPSR = PARAMETERS["alpha_FUELPSLR"]


def register(registry: Registry) -> None:
    """Register the §3.3.3 equations, manual Eqs. (139)-(158)."""

    def add(name: str, number: int, kind: str, func) -> None:
        registry.add(Equation(name, f"§3.3.3 eq. ({number})", kind, func))

    # --- Technical coefficients, Eqs. (139)-(144) -------------------------
    add("alpha_PP", 139, "calibrated", lambda s, l: _A_PPLR)
    # Electricity per unit of production output: falls with energy
    # intensity, rises with electrification.
    add("alpha_PSP", 140, "calibrated", lambda s, l: s["epsilon"] * s["theta_P"])
    add("alpha_PSPS", 141, "calibrated", lambda s, l: _A_PSPSLR)
    add("alpha_OPPS", 142, "calibrated", lambda s, l: _A_OPPSLR)
    # Fuel input scales with last period's fossil share of generation.
    add("alpha_FUELPS", 143, "calibrated",
        lambda s, l: (1.0 - l["beta_NFF"]) * _A_FUELPSR)
    # Composite production-product input to power, valued at relative prices.
    add("alpha_PPS", 144, "identity",
        lambda s, l: s["alpha_FUELPS"] * s["P_FUEL"] / s["P_P"] + s["alpha_OPPS"])

    # --- Intermediate consumption, Eqs. (145)-(153) -----------------------
    add("IC_PSPR", 145, "identity", lambda s, l: s["alpha_PSP"] * s["GO_PR"])
    add("IC_FUELPSR", 146, "identity", lambda s, l: s["alpha_FUELPS"] * s["GO_PSR"])
    add("IC_OPPSR", 147, "identity", lambda s, l: s["alpha_OPPS"] * s["GO_PSR"])
    add("IC_PP", 148, "identity", lambda s, l: s["alpha_PP"] * s["GO_P"])
    add("IC_PSP", 149, "identity", lambda s, l: s["IC_PSPR"] * s["P_ELEC"])
    add("IC_PSPS", 150, "identity", lambda s, l: s["alpha_PSPS"] * s["GO_PS"])
    add("IC_PPS", 151, "identity", lambda s, l: s["IC_FUELPS"] + s["IC_OPPS"])
    add("IC_FUELPS", 152, "identity", lambda s, l: s["IC_FUELPSR"] * s["P_FUEL"])
    add("IC_OPPS", 153, "identity", lambda s, l: s["IC_OPPSR"] * s["P_P"])

    # --- Leontief inverse of the 2x2 (I - A), Eqs. (154)-(158) ------------
    add("det_IA", 154, "identity",
        lambda s, l: (1.0 - s["alpha_PP"]) * (1.0 - s["alpha_PSPS"])
        - s["alpha_PPS"] * s["alpha_PSP"])
    add("L_PP", 155, "identity", lambda s, l: (1.0 - s["alpha_PSPS"]) / s["det_IA"])
    add("L_PPS", 156, "identity", lambda s, l: s["alpha_PPS"] / s["det_IA"])
    add("L_PSP", 157, "identity", lambda s, l: s["alpha_PSP"] / s["det_IA"])
    add("L_PSPS", 158, "identity", lambda s, l: (1.0 - s["alpha_PP"]) / s["det_IA"])
