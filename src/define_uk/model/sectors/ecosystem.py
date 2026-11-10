"""DEFINE-UK Model Manual v1.1 §3.1 Ecosystem.

Equations (1)-(20): energy use (§3.1.1), emissions (§3.1.2) and the five
logistic efficiency/technology relations (§3.1.3). Clean-room
implementation from the published manual (pp. 9-13). The upstream R code is
an output oracle only and is never read to write equations here (see
REIMPLEMENTATION.md).

Symbols: the manual's direct-energy subscript D (E_D, E_DP, E_DH, EMIS_D,
omega_D) is spelled NELEC here, as in §5 Table 6 and the cached CSVs
(E_NELEC, E_NELECP, E_NELECH, EMIS_NELEC, omega_NELEC). The logistic
bounds omega_dmin/max are Table 5's omega_nemin/max.

Exogenous to this section: GO_PR (§3.3.1), K_PSFFR/K_PSNFFR (§3.3.2),
K_GVTNFFR (§3.4.4), K_PG/K_PC (§3.3.1) and the housing stocks H_I, H_EN,
H_EE (§3.4.5).
"""

from __future__ import annotations

import math

from ..calibration import PARAMETERS as P
from ..registry import Equation, Registry

MANUAL_GAPS = {
    "eq_5_reference": (
        "The text before Eq. (5) says non-fossil efficiency evolves by "
        "'Equation (??)' (a broken cross-reference); Eq. (17) is the only "
        "equation that determines CF_NFF and is used."
    ),
}


def _logistic(lo: float, hi: float, pi: float, kappa: float, x: float) -> float:
    """lo + (1 + pi)(hi - lo) / (1 + pi * exp(kappa * x)): Eqs. (16), (17),
    (19), (20). At x = 0 it returns hi."""
    return lo + (1.0 + pi) * (hi - lo) / (1.0 + pi * math.exp(kappa * x))


def _ratio(num: float, den: float) -> float:
    return num / den if den else math.inf


def register(registry: Registry) -> None:
    """Register the §3.1 equations, manual Eqs. (1)-(20)."""

    def add(name: str, number: int, kind: str, func) -> None:
        sec = "§3.1.1" if number <= 12 else ("§3.1.2" if number <= 15 else "§3.1.3")
        registry.add(Equation(name, f"{sec} eq. ({number})", kind, func))

    # --- §3.1.1 Energy, Eqs. (1)-(12) -------------------------------------
    add("E", 1, "identity", lambda s, l: s["E_P"] + s["E_H"])
    add("E_P", 2, "identity", lambda s, l: s["epsilon"] * s["GO_PR"])
    add("E_H", 3, "identity", lambda s, l: s["E_ELECH"] + s["E_NELECH"])
    add("E_ELEC", 4, "identity", lambda s, l: s["E_ELECP"] + s["E_ELECH"])
    add("E_ELECMAX", 5, "identity",
        lambda s, l: P["CF_FF"] * s["K_PSFFR"]
        + s["CF_NFF"] * (s["K_PSNFFR"] + s["K_GVTNFFR"]))
    # Non-fossil generation runs first (merit order), capped at capacity.
    add("E_ELECNFF", 6, "identity",
        lambda s, l: min(s["E_ELEC"] * P["sigma_ELEC"],
                         s["CF_NFF"] * s["K_PSNFFR"]))
    add("E_ELECFF", 7, "identity", lambda s, l: s["E_ELEC"] - s["E_ELECNFF"])
    add("E_ELECP", 8, "identity", lambda s, l: s["theta_P"] * s["E_P"])
    add("E_ELECH", 9, "identity",
        lambda s, l: (P["theta_HI"] * s["H_I"] + P["theta_HEN"] * s["H_EN"])
        * P["beta_ELECH"] + P["theta_HEE"] * s["H_EE"])
    add("E_NELEC", 10, "identity", lambda s, l: s["E_NELECP"] + s["E_NELECH"])
    add("E_NELECP", 11, "identity", lambda s, l: (1.0 - s["theta_P"]) * s["E_P"])
    add("E_NELECH", 12, "identity",
        lambda s, l: (P["theta_HI"] * s["H_I"] + P["theta_HEN"] * s["H_EN"])
        * (1.0 - P["beta_ELECH"]))

    # --- §3.1.2 Emissions, Eqs. (13)-(15) ---------------------------------
    add("EMIS", 13, "identity", lambda s, l: s["EMIS_NELEC"] + s["EMIS_ELEC"])
    add("EMIS_NELEC", 14, "identity", lambda s, l: s["omega_NELEC"] * s["E_NELEC"])
    add("EMIS_ELEC", 15, "identity", lambda s, l: s["omega_ELEC"] * s["E_ELECFF"])

    # --- §3.1.3 Logistic efficiency relations, Eqs. (16)-(20) -------------
    green = lambda l: _ratio(l["K_PG"], l["K_PC"])  # noqa: E731
    nff = lambda l: _ratio(l["E_ELECNFF"], l["E_ELECFF"])  # noqa: E731
    add("epsilon", 16, "calibrated",
        lambda s, l: _logistic(P["epsilon_min"], P["epsilon_max"], P["pi1"],
                               P["kappa1"], green(l)))
    add("CF_NFF", 17, "calibrated",
        lambda s, l: _logistic(P["CF_min"], P["CF_max"], P["pi2"],
                               P["kappa2"], nff(l)))
    add("theta_P", 18, "calibrated",
        lambda s, l: 1.0 - (1.0 + P["pi3"])
        / (1.0 + P["pi3"] * math.exp(-P["kappa3"] * green(l))))
    add("omega_NELEC", 19, "calibrated",
        lambda s, l: _logistic(P["omega_nemin"], P["omega_nemax"], P["pi4"],
                               P["kappa4"], green(l)))
    add("omega_ELEC", 20, "calibrated",
        lambda s, l: _logistic(P["omega_emin"], P["omega_emax"], P["pi5"],
                               P["kappa5"], nff(l)))
