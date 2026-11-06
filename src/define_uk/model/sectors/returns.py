"""DEFINE-UK Model Manual v1.1 §3.4.7 Rates of return.

Equations (397)-(401): the log Taylor rule for the base rate and, for each
sector j, the partial-adjustment asset and liability rates. Eqs. (398)-(401)
are printed once with a sector index j; each sector's instance is
registered under the same equation number with an index tag, e.g.
``§3.4.7 eq. (398)[NFC]``.

Clean-room implementation from the published manual (p. 48). The upstream
R code is an output oracle only and is never read to write equations here
(see REIMPLEMENTATION.md).

Manual gaps (``MANUAL_GAPS``): r_BOEQ has no equation; spr_psa, minr_ps and
delta_rlhh are not in Table 5; the "delta_jt" of Eq. (401) is not defined.
"""

from __future__ import annotations

import math

from ..calibration import PARAMETERS as P
from ..registry import Equation, Registry

L = math.log

# sector -> (asset-rate key, tau_a, minr, spr_a) ; liability -> (tau_l, delta_rl, spr_l, sigma, delta_j)
ASSET_SECTORS = {
    "NFC": ("tau_ranfc", "minr_nfc", "spr_nfca"),
    "PS": ("tau_raps", None, None),
    "NMFI": ("tau_ranmfi", "minr_nmfi", "spr_nmfia"),
    "GVT": ("tau_ragvt", "minr_gvt", "spr_gvta"),
    "HH": ("tau_rahh", "minr_hh", "spr_hha"),
}
LIABILITY_SECTORS = {
    "NFC": ("tau_rlnfc", "delta_rlnfc", "spr_nfcl", "sigma_nfc"),
    "PS": ("tau_rlps", "delta_rlps", "spr_psl", "sigma_ps"),
    "NMFI": ("tau_rlnmfi", "delta_rlnmfi", "spr_nmfil", "sigma_nmfi"),
    "GVT": ("tau_rlgvt", "delta_rlgvt", "spr_gvtl", "sigma_gvt"),
    "HH": ("tau_rlhh", None, "spr_hhl", "sigma_hh"),
}

MANUAL_GAPS = {
    "r_BOEQ": (
        "Eqs. (399)-(401) use the quarterly base rate r_BOEQ, which no "
        "equation defines (Table 6 cites a stale 'Eq. (433)'). Implemented "
        "as (1 + r_BOE)^(1/4) - 1: Table 6's 0.005578 from r_BOE = 0.0225, "
        "and every quarter of the cached baseline to 4 s.f."
    ),
    "PS_asset_rate": (
        "Table 5 has tau_raps but no spr_psa or minr_ps, so Eq. (399) cannot "
        "be evaluated for the power sector. r_IBA_PSLR is held at its "
        "lagged value (Table 6 at the start)."
    ),
    "delta_rlhh": "Table 5 has no delta_rlhh; Eq. (400) uses 0 for households.",
    "delta_jt": (
        "Eq. (401)'s delta_jt is called 'the depreciation rate of the "
        "sector's liabilities' and not otherwise defined. Read as the "
        "sector's default rate for NFC and PS (DEF_NFC, DEF_PS: the only "
        "time-varying liability write-off rates) and delta_IBL_j otherwise."
    ),
    "eq_397_taylor_inputs": (
        "Eq. (397) reads inflation INF; the model's inflation variable is "
        "INF_A (Table 6: annual CPI inflation)."
    ),
}

_DELTA_J = {"NFC": lambda s: s["DEF_NFC"], "PS": lambda s: s["DEF_PS"],
            "NMFI": lambda s: P["delta_IBLNMFI"], "GVT": lambda s: P["delta_IBLGVT"],
            "HH": lambda s: P["delta_IBLHH"]}


def register(registry: Registry) -> None:
    """Register the §3.4.7 equations, manual Eqs. (397)-(401)."""

    def add(name: str, number: int, kind: str, func, j: str | None = None) -> None:
        ref = f"§3.4.7 eq. ({number})" + (f"[{j}]" if j else "")
        registry.add(Equation(name, ref, kind, func))

    # MANUAL_GAPS["r_BOEQ"]: no printed equation; registered under the Taylor
    # rule it converts, with index tag Q.
    add("r_BOEQ", 397, "identity", lambda s, l: r_boeq(s, l), "Q")
    add("r_BOE", 397, "behavioural",
        lambda s, l: math.exp(L(l["r_BOE"]) + P["epsilon_rboe"] * (
            P["alpha_rboe"] * L(max(l["INF_A"], P["minr_boe"])) - L(l["r_BOE"]))))

    for j, (tau, minr, spr) in ASSET_SECTORS.items():
        rate, lr = f"r_IBA_{j}", f"r_IBA_{j}LR"
        add(rate, 398, "calibrated",
            lambda s, l, rate=rate, lr=lr, tau=P[tau]: l[rate] + tau * (s[lr] - l[rate]), j)
        if minr is None:
            add(lr, 399, "calibrated", lambda s, l, lr=lr: l[lr], j)
        else:
            add(lr, 399, "calibrated",
                lambda s, l, m=P[minr], sp=P[spr]: max(m, s["r_BOEQ"] - sp), j)
    # RoW net position: same pair with tau_rnrow, minr_row, spr_rowa.
    add("r_IBN_ROW", 398, "calibrated",
        lambda s, l: l["r_IBN_ROW"] + P["tau_rnrow"] * (s["r_IBN_ROWLR"] - l["r_IBN_ROW"]), "ROW")
    add("r_IBN_ROWLR", 399, "calibrated",
        lambda s, l: max(P["minr_row"], s["r_BOEQ"] - P["spr_rowa"]), "ROW")

    for j, (tau, drl, spr, sig) in LIABILITY_SECTORS.items():
        rate, lr = f"r_IBL_{j}", f"r_IBL_{j}LR"
        d_rl = P[drl] if drl else 0.0
        add(rate, 400, "calibrated",
            lambda s, l, rate=rate, lr=lr, tau=P[tau], d=d_rl:
            l[rate] + tau * (s[lr] - l[rate]) + d * (s["r_BOEQ"] - l["r_BOEQ"]), j)
        add(lr, 401, "calibrated",
            lambda s, l, j=j, sp=P[spr], sg=P[sig]:
            s[f"r_IBA_{j}LR"] + (sp + _DELTA_J[j](s)) * (1.0 + sg * s["r_BOEQ"])
            * l["FL_MFI"] / l["FA_MFI"], j)


def r_boeq(s, l) -> float:
    """MANUAL_GAPS["r_BOEQ"]."""
    return (1.0 + s["r_BOE"]) ** 0.25 - 1.0
