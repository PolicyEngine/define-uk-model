"""DEFINE-UK Model Manual v1.1 §3.3 Production — §3.3.1 domestic production.

Equations (44)-(70): final demand for production products, the Leontief
gross-output block, mark-up pricing over unit costs, the wage-share/wage-rate
distribution block, direct (non-electric) energy prices and costs, and the
productive capital aggregates.

§3.3.2 (power generation, Eqs. (71)-(138)) and §3.3.3 (input-output, from
Eq. (139)) are separate passes and are not implemented here; this module's
``register`` covers §3.3.1 exactly.

Clean-room implementation from the published manual. Every equation carries
the manual section and equation number it implements; the upstream R code is
an output oracle only and is never read to write equations here (see
REIMPLEMENTATION.md).

Structure of the section
------------------------
Three blocks, and the closure is post-Keynesian in each of them:

1. **Quantities are demand-led.** Final demand F_P, Eq. (44), is whatever
   households, government, investors and foreigners spend; real gross output
   Eq. (46) is the Leontief inverse applied to that final demand. No relative
   price and no capacity term appears — output accommodates demand, and the
   supply ceiling computed in §3.2 (GDP_RMAX, Eq. (38)) is not consulted.

2. **Prices are cost-plus, not market-clearing.** Eq. (49) sets the
   production deflator as a mark-up over *last period's* unit costs, and
   Eq. (50) makes unit costs the whole nominal input bill (wages, indirect
   tax, both intermediate flows and imports) per unit of real output. The
   mark-up itself, Eq. (51), is proportional to capacity utilisation, so it
   is procyclical: unlike EUROGREEN's, this specification has firms *cutting*
   margins in a slump to win back custom (manual §3.3.1, p. 17). The one-period
   lag on UC is what keeps prices from being simultaneous with the costs they
   mark up, and it is load-bearing for the solve order.

3. **Distribution is conflictual, and the wage rate is a residual of it.**
   Eq. (52) is a logistic Phillips-type relation: the wage *share* falls with
   unemployment. Only then does Eq. (53) back out the wage rate as
   W_S·GDP/EMP. Causality therefore runs share -> rate -> wage bill -> costs
   -> prices, never marginal-product -> wage. That is the whole point of the
   block, and it is why Eq. (52) must not be "improved" into a wage equation.

The production module is not a sector: it holds no financial assets or
liabilities (manual §3.3, footnote 14). It is the origin of every wage
payment in the model, including public-sector and power-sector wages
(manual §3.3.1, p. 17), which is why W here is the economy-wide wage bill.

Exogenous to this section
-------------------------
See ``EXOGENOUS_TO_SECTION``. Note that three variables §3.2 treats as
exogenous — P_P, GO_P and K_PR — are determined *here*, by Eqs. (47), (49)
and (67), so §3.2 and §3.3.1 only close jointly.

Known manual gaps (see ``MANUAL_GAPS``)
---------------------------------------
- The body's "direct energy" D-subscript family (P_D, P_DT, ITAX_D, E_D,
  COST_D) is tabulated in §5 under NELEC ("non-electric energy"); neither
  name appears in the other place. We use the tabulated names.
- Table 6 omits K_NFCGR and K_GVTGR, the two components Eq. (68) sums.

Manual inconsistencies measured at the §5 Table 6 initial values
-----------------------------------------------------------------
Nineteen of the section's identities reproduce Table 6 within its
four-significant-figure printing noise (worst 8.1e-4, Eq. (46)). Five do not,
and the gaps are one to three orders of magnitude larger than that noise.
They are implemented exactly as printed and pinned in tests/test_production.py
rather than patched or absorbed into a tolerance:

  Eq. (51)  MU        0.1584 vs 0.1704 tabulated      7.1e-2
  Eq. (52)  WS        0.5997 vs 0.6233 tabulated      3.8e-2
  Eq. (59)  P_NELEC   0.1491 vs 0.09337 tabulated     6.0e-1
  Eq. (61)  P_FUEL    0.6788 vs 1.0 tabulated         3.2e-1
  Eq. (70)  delta_KP  0.02375 (Table 5) vs 0.02149 (Table 6)  1.1e-1

Eqs. (49) and (55) depend on a lagged variable and so cannot be checked
against a single-period snapshot at all; both are consistent with Table 6
being the snapshot of a *growing* economy, and the tests say exactly that
much and no more.
"""

from __future__ import annotations

import math
from typing import Mapping

from ..calibration import PARAMETERS
from ..registry import Equation, Registry

# Variables this section reads but does not determine. Kept explicit so a
# §3.3.1-only solve can assert it has been given everything it needs.
EXOGENOUS_TO_SECTION = (
    # Final demand components, Eqs. (44)-(45).
    "CONS_HHP", "CONS_HHPR",        # household consumption of production
    "CONS_HHPS",                    # household consumption of electricity
    "CONS_GVT", "CONS_GVTR",        # government consumption      (§3.4.4)
    "GCF", "GCF_R",                 # capital formation           (§3.2 (23)/(27))
    "EXP", "EXP_R", "IMP",          # trade                       (§3.4.6)
    # Input-output block, Eqs. (46), (48).
    "F_PSR",                        # real power-sector final demand (§3.3.2)
    "L_PP", "L_PPS",                # Leontief inverse coefficients  (§3.3.3)
    "IC_PP", "IC_PSP",              # intermediate consumption       (§3.3.3)
    "ITAX_P",                       # indirect tax on production     (§3.4.4 (254))
    # Macro aggregates and rates, Eqs. (51)-(53).
    "GDP", "EMP", "EMP_PRI", "EMP_PUB", "u", "ru",   # all §3.2
    # Direct-energy block, Eqs. (59)-(63). Manual subscript D; see MANUAL_GAPS.
    "P_GAS", "P_OIL",               # global fuel prices, OBR projections
    "ITAX_NELEC",                   # the manual's ITAX_D    (§3.4.4 (255))
    "E_NELEC",                      # the manual's E_D       (§3.1 energy block)
    # Productive capital components, Eqs. (64)-(69).
    "K_NFC", "K_NFCG", "K_NFCC",
    "K_NFCR", "K_NFCGR", "K_NFCCR",                  # all §3.4.1
    "K_GVT", "K_GVTG", "K_GVTC",
    "K_GVTR", "K_GVTGR", "K_GVTCR",                  # all §3.4.4
)

# Symbols §3.3.1 needs that manual §5 does not tabulate under the name the
# §3 body uses. Pinned in tests/test_production.py rather than silently
# reconciled.
MANUAL_GAPS = {
    "direct_energy_symbols": (
        "Eqs. (59)-(63) use a 'direct energy' D subscript (P_D, P_DT, "
        "ITAX_D, E_D, COST_D) that appears nowhere in §5 Tables 5-6, while "
        "the tables carry a NELEC ('non-electric energy') family that "
        "appears nowhere in the §3 body. They are the same variables: under "
        "that identification Eq. (60) reproduces the tabulated P_NELECT to "
        "1.1e-5 and Eq. (62) the tabulated COST_NELEC to 5.8e-5, and the "
        "α_D/β_DGAS/β_DOIL of Eq. (59) are Table 5's α_NELEC, β_NELECGAS "
        "and β_NELECOIL. We use the tabulated NELEC names throughout so the "
        "keys match calibration.py."
    ),
    "K_NFCGR_K_GVTGR": (
        "Eq. (68) sums K_NFCGR and K_GVTGR, the real green capital stocks "
        "of NFCs and government, but Table 6 tabulates neither — only their "
        "sum K_PGR (131.4). Nothing is defaulted here: both are exogenous to "
        "this section (§3.4.1 and §3.4.4 determine them), so Eq. (68) is "
        "implemented as printed and the tests check it against K_PGR via "
        "the sector-uniform deflators instead."
    ),
}

_A1_MU = PARAMETERS["alpha1_MU"]
_A0_WS = PARAMETERS["alpha0_WS"]
_A1_WS = PARAMETERS["alpha1_WS"]
_A_NELEC = PARAMETERS["alpha_NELEC"]
_B_NELEC_GAS = PARAMETERS["beta_NELECGAS"]
_B_NELEC_OIL = PARAMETERS["beta_NELECOIL"]
_A_PFUEL = PARAMETERS["alpha_PFUEL"]
_B_WR_PRI = PARAMETERS["beta_WRPRI"]
_B_WR_PUB = PARAMETERS["beta_WRPUB"]
_DELTA_KPC = PARAMETERS["delta_kpc"]

# Manual §5 Table 6 records the mark-up µ as "Calculated from Eq. (54),
# floored at 0.001 for log stability" (Table 6 cross-references a different
# equation numbering from the §3 body — see calibration.py — but µ is the
# production mark-up of Eq. (51) here). The floor is the manual's, not ours:
# MU enters Eq. (49) multiplicatively and prices are logged downstream, so a
# non-positive mark-up would take the price block with it. It never binds in
# the baseline (α_1MU·u = 0.158 at u = 0.815) — only below ~0.5% utilisation.
MU_FLOOR = 0.001


def _logistic(x: float) -> float:
    """1 / (1 + e^-x), Eq. (52)'s functional form, overflow-safe.

    The naive form overflows to OverflowError once x < -709. The wage share
    is a *bounded* object — the whole reason the manual uses a logistic — so
    a saturating result is the right answer at extreme unemployment, and an
    exception there would be an artefact of the arithmetic, not economics.
    """
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def _unit_costs(values: Mapping[str, float]) -> float:
    """COST_P / GO_PR, Eq. (50), guarded against zero real output.

    Returning an inf here would silently poison P_P, and through it every
    nominal aggregate in the model, so a zero-output state is rejected at
    source instead.
    """
    real_output = values["GO_PR"]
    if real_output <= 0.0:
        raise ValueError(
            f"Eq. (50): unit costs need strictly positive real gross output, "
            f"got GO_PR={real_output!r}"
        )
    return values["COST_P"] / real_output


def register(registry: Registry) -> None:
    """Register the §3.3.1 equations, manual Eqs. (44)-(70)."""

    def add(name: str, number: int, kind: str, func) -> None:
        registry.add(Equation(name, f"§3.3.1 eq. ({number})", kind, func))

    # --- Final demand and gross output, Eqs. (44)-(48) -------------------
    # The §3.3.1 prose lists only household consumption, government
    # consumption and exports, but the printed Eq. (44) also carries GCF —
    # and Table 6 confirms the equation, not the prose: the four tabulated
    # components sum to F_P = 805.0 exactly. All capital formation is demand
    # for *production* products; the power sector sells only electricity.
    add("F_P", 44, "identity",
        lambda s, l: s["CONS_HHP"] + s["CONS_GVT"] + s["GCF"] + s["EXP"])
    add("F_PR", 45, "identity",
        lambda s, l: s["CONS_HHPR"] + s["CONS_GVTR"] + s["GCF_R"] + s["EXP_R"])

    # Leontief inverse: real gross output is whatever is needed to deliver
    # final demand, including the electricity sector's draw on production
    # products. Demand-led — there is no price or capacity term.
    add("GO_PR", 46, "identity",
        lambda s, l: s["L_PP"] * s["F_PR"] + s["L_PPS"] * s["F_PSR"])
    add("GO_P", 47, "identity", lambda s, l: s["GO_PR"] * s["P_P"])

    # Total input bill. Imports are a cost of production here, so exchange
    # rate and world price shocks reach domestic prices through Eq. (50).
    add("COST_P", 48, "identity",
        lambda s, l: (s["W"] + s["ITAX_P"] + s["IC_PP"] + s["IC_PSP"]
                      + s["IMP"]))

    # --- Mark-up pricing, Eqs. (49)-(51) ---------------------------------
    # UC is lagged, which is what breaks the price/cost simultaneity: this
    # period's price is set on last period's realised unit costs.
    add("P_P", 49, "behavioural", lambda s, l: (1.0 + s["mu"]) * l["UC"])
    add("UC", 50, "identity", lambda s, l: _unit_costs(s))
    # Procyclical mark-up: margins expand with utilisation and are cut in a
    # slump to draw customers back (manual §3.3.1, p. 17).
    add("mu", 51, "behavioural",
        lambda s, l: max(_A1_MU * s["u"], MU_FLOOR))

    # --- Distribution and wages, Eqs. (52)-(58) --------------------------
    # Conflict/Phillips: the wage share, not the wage level, is what the
    # labour market determines, and it falls as unemployment rises. The
    # logistic keeps it inside (0, 1) by construction.
    add("WS", 52, "behavioural",
        lambda s, l: _logistic(_A0_WS - _A1_WS * s["ru"]))
    # The wage rate is a residual of the share, Eq. (53) — see the module
    # docstring on why the direction of causality matters here.
    add("WR", 53, "identity", lambda s, l: s["WS"] * s["GDP"] / s["EMP"])
    add("WR_PRI", 54, "calibrated", lambda s, l: _B_WR_PRI * s["WR"])
    # Manual §3.3.1, footnote 17: the public wage rate is deliberately set on
    # the *lagged* overall rate, because public wages feed CONS_GVT, which
    # feeds GDP, which feeds WR — the lag is what cuts that loop.
    add("WR_PUB", 55, "calibrated", lambda s, l: _B_WR_PUB * l["WR"])
    add("W_PRI", 56, "identity", lambda s, l: s["WR_PRI"] * s["EMP_PRI"])
    add("W_PUB", 57, "identity", lambda s, l: s["WR_PUB"] * s["EMP_PUB"])
    add("W", 58, "identity", lambda s, l: s["W_PRI"] + s["W_PUB"])

    # --- Direct (non-electric) energy, Eqs. (59)-(63) --------------------
    # Manual subscript D; §5 tabulates the same variables as NELEC. See
    # MANUAL_GAPS["direct_energy_symbols"].
    # A fixed pass-through of global gas and oil prices, with the fuel mix
    # held constant over the simulation (manual §3.3.1, p. 18).
    add("P_NELEC", 59, "behavioural",
        lambda s, l: _A_NELEC * (_B_NELEC_GAS * s["P_GAS"]
                                 + _B_NELEC_OIL * s["P_OIL"]))
    # Tax-inclusive price: the ETS levy per unit of energy, Eq. (60).
    add("P_NELECT", 60, "identity",
        lambda s, l: s["P_NELEC"] + s["ITAX_NELEC"] / s["E_NELEC"])
    # UK fossil generation is entirely gas-based, so the fuel the production
    # module sells to the power sector is priced off wholesale gas alone.
    add("P_FUEL", 61, "calibrated", lambda s, l: _A_PFUEL * s["P_GAS"])
    add("COST_NELEC", 62, "identity", lambda s, l: s["P_NELEC"] * s["E_NELEC"])
    # Real total energy cost of the whole economy: direct energy plus its
    # tax, plus both electricity flows, deflated by the production price.
    add("COST_ER", 63, "identity",
        lambda s, l: (s["COST_NELEC"] + s["ITAX_NELEC"] + s["CONS_HHPS"]
                      + s["IC_PSP"]) / s["P_P"])

    # --- Productive capital, Eqs. (64)-(70) ------------------------------
    # "Productive" capital is all non-housing capital: NFC plus government,
    # split green/conventional because that ratio, not an innovation
    # process, is what drives energy efficiency and emissions in this model
    # (manual §3.3.1, p. 19). Power-sector capital K_PS is tracked
    # separately in §3.3.2 and is not part of K_P.
    add("K_P", 64, "identity", lambda s, l: s["K_NFC"] + s["K_GVT"])
    add("K_PG", 65, "identity", lambda s, l: s["K_NFCG"] + s["K_GVTG"])
    add("K_PC", 66, "identity", lambda s, l: s["K_NFCC"] + s["K_GVTC"])
    add("K_PR", 67, "identity", lambda s, l: s["K_NFCR"] + s["K_GVTR"])
    add("K_PGR", 68, "identity", lambda s, l: s["K_NFCGR"] + s["K_GVTGR"])
    add("K_PCR", 69, "identity", lambda s, l: s["K_NFCCR"] + s["K_GVTCR"])
    # One constant depreciation rate for NFC and government capital alike,
    # Eq. (70) — no differential obsolescence of conventional capital.
    add("delta_KP", 70, "calibrated", lambda s, l: _DELTA_KPC)
