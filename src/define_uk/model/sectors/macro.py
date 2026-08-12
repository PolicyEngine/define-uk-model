"""DEFINE-UK Model Manual v1.1 §3.2 High-level macroeconomic variables.

Equations (21)-(43): the demand-determined income/expenditure core, the
nominal-to-real conversion, the Leontief labour/capital supply constraints,
and the labour-market ratios.

Clean-room implementation from the published manual. Every equation carries
the manual section and equation number it implements; the upstream R code is
an output oracle only and is never read to write equations here (see
REIMPLEMENTATION.md).

Structure of the section
------------------------
The manual's closure is post-Keynesian: output is demand-determined (Eq.
(21) is an accounting identity on expenditure, not a market-clearing
condition), while supply enters through a *ceiling* — GDP_RMAX, Eq. (38) —
and through prices, rather than by forcing output to potential. Nothing in
this section makes GDP_R respect GDP_RMAX; the constraint bites via the
price and wage blocks in §3.3-§3.4. Implementing (38) as a binding cap here
would silently convert the model to a supply-determined one, so it is
computed and reported, not imposed.

Exogenous to this section
-------------------------
These are read from ``state`` but determined elsewhere in the manual; a
§3.2-only solve must supply them:

  CONS_HH, CONS_GVT   household/government consumption   (§3.4.5, §3.4.4)
  GCF_NFC, GCF_PS     NFC / power-sector capital formation (§3.4.1, §3.3.2)
  GCF_GVT, GCF_HH     government / household capital formation
  GCF_HHR             real household capital formation
  EXP, IMP            nominal exports and imports         (§3.4.6)
  EXP_R, IMP_R        real exports and imports            (§3.4.6)
  GO_P, GO_PS         gross output, production and power  (§3.3.1, §3.3.2)
  P_P                 production price deflator           (§3.3.1 eq. (49))
  K_PR                real productive capital stock       (§3.3.1 eq. (67))
  g_LFOBR, POP_OBR    OBR labour-force growth and population projections

Known manual gap
----------------
Eq. (31) contains an intercept α_0λ, but manual §5 Table 5 does not list it:
the α_0 block runs α_0GCFFF, α_0GCFNB, α_0GCFNFC, α_0GCFNFF, α_0IMP, α_0PH,
α_0SOCB, α_0WS and then goes straight to α_1βHH. Only α_1lambda (0.725) and
α_2lambda (0.025) are tabulated. Rather than invent a value, the intercept
is read from PARAMETERS under ``alpha0_lambda`` and defaults to 0.0, which
is the only choice that leaves productivity growth entirely explained by the
two tabulated terms. This is recorded in ``MANUAL_GAPS`` and pinned by a
test so it cannot be silently forgotten if the parameter is later published.
"""

from __future__ import annotations

import math
from typing import Mapping

from ..calibration import PARAMETERS
from ..registry import Equation, Registry

# Variables this section reads but does not determine. Kept explicit so a
# §3.2-only solve can assert it has been given everything it needs.
EXOGENOUS_TO_SECTION = (
    "CONS_HH", "CONS_GVT",
    "GCF_NFC", "GCF_PS", "GCF_GVT", "GCF_HH", "GCF_HHR",
    "EXP", "IMP", "EXP_R", "IMP_R",
    "GO_P", "GO_PS",
    "P_P", "K_PR",
    "g_LFOBR", "POP_OBR",
)

# Documented divergences between the manual's printed text and its own
# tables. Pinned in tests/test_macro.py rather than silently patched.
MANUAL_GAPS = {
    "alpha0_lambda": (
        "Eq. (31) uses an intercept α_0λ that manual §5 Table 5 never "
        "tabulates (the α_0 block ends at α_0WS). Defaulted to 0.0 here; "
        "if the DEFINE team publishes a value, set it in PARAMETERS and "
        "this default stops applying."
    ),
}

# The manual tabulates α_1lambda / α_2lambda but not α_0lambda; see above.
_A0_LAMBDA = PARAMETERS.get("alpha0_lambda", 0.0)
_A1_LAMBDA = PARAMETERS["alpha1_lambda"]
_A2_LAMBDA = PARAMETERS["alpha2_lambda"]


def _productive_gcf_r(values: Mapping[str, float]) -> float:
    """Real gross capital formation excluding housing, Eq. (31)'s second term.

    The manual writes GCF_Rt - GCF_HHRt: productivity is driven by *productive*
    investment, so household (housing) capital formation is netted out.
    """
    return values["GCF_R"] - values["GCF_HHR"]


def _log_growth(current: float, previous: float, what: str) -> float:
    """Δ(L(x)) — the manual's first difference of a natural log.

    Raises rather than returning a nan: Eq. (31) is only defined on positive
    values, and a nan here would propagate silently through λ into employment
    and the whole supply block.
    """
    if current <= 0.0 or previous <= 0.0:
        raise ValueError(
            f"Eq. (31): Δ(L({what})) needs strictly positive values, "
            f"got current={current!r}, previous={previous!r}"
        )
    return math.log(current) - math.log(previous)


def register(registry: Registry) -> None:
    """Register the §3.2 equations, manual Eqs. (21)-(43)."""

    def add(name: str, number: int, kind: str, func) -> None:
        registry.add(Equation(name, f"§3.2 eq. ({number})", kind, func))

    # --- Nominal expenditure aggregates, Eqs. (21)-(24) ------------------
    add("GDP", 21, "identity",
        lambda s, l: s["CONS"] + s["GCF"] + s["EXP"] - s["IMP"])
    add("CONS", 22, "identity",
        lambda s, l: s["CONS_HH"] + s["CONS_GVT"])
    add("GCF", 23, "identity",
        lambda s, l: s["GCF_NFC"] + s["GCF_PS"] + s["GCF_GVT"] + s["GCF_HH"])
    add("GO", 24, "identity",
        lambda s, l: s["GO_P"] + s["GO_PS"])

    # --- Real aggregates and prices, Eqs. (25)-(30) ----------------------
    # Nominal behavioural equations are deflated by the *production* price
    # P_P (manual §3.2, p. 14); the overall GDP deflator P, Eq. (30), is a
    # residual of the nominal and real aggregates, not an input to them.
    add("GDP_R", 25, "identity",
        lambda s, l: s["CONS_R"] + s["GCF_R"] + s["EXP_R"] - s["IMP_R"])
    add("CONS_R", 26, "identity", lambda s, l: s["CONS"] / s["P_P"])
    add("GCF_R", 27, "identity", lambda s, l: s["GCF"] / s["P_P"])
    add("GO_R", 28, "identity", lambda s, l: s["GO"] / s["P_P"])

    # Eq. (29) is printed as a gross ratio, not a growth *rate*: the manual's
    # own initial value is g = 1.019. Implemented exactly as printed.
    add("g", 29, "identity", lambda s, l: s["GDP"] / l["GDP"])
    add("P", 30, "identity", lambda s, l: s["GDP"] / s["GDP_R"])

    # --- Productivity, Eqs. (31)-(32) ------------------------------------
    # Kaldor-Verdoorn: productivity growth responds to real demand growth
    # (α_1λ) and to growth in productive investment (α_2λ), the latter a la
    # Thirlwall — capital deepening on top of the demand channel.
    def lam(s, l):
        return l["lam"] * math.exp(
            _A0_LAMBDA
            + _A1_LAMBDA * _log_growth(s["GDP_R"], l["GDP_R"], "GDP_R")
            + _A2_LAMBDA * _log_growth(
                _productive_gcf_r(s), _productive_gcf_r(l),
                "GCF_R - GCF_HHR",
            )
        )

    add("lam", 31, "behavioural", lam)

    # Δν = 0: real capital productivity is constant at its initial value, so
    # the capital ceiling Eq. (37) moves only through investment in new
    # capital (manual §3.2, p. 15).
    add("nu", 32, "calibrated", lambda s, l: l["nu"])

    # --- Employment, Eqs. (33)-(35) --------------------------------------
    # Leontief in labour: employment is output divided by productivity, with
    # no substitution margin.
    add("EMP", 33, "identity", lambda s, l: s["GDP_R"] / s["lam"])
    # Public-sector employment is a policy variable held at a constant share
    # of the labour force, so it grows at the labour force's rate.
    add("EMP_PUB", 34, "calibrated",
        lambda s, l: (s["LF"] / l["LF"]) * l["EMP_PUB"])
    add("EMP_PRI", 35, "identity", lambda s, l: s["EMP"] - s["EMP_PUB"])

    # --- Supply constraints, Eqs. (36)-(38) ------------------------------
    add("GDP_RFE", 36, "identity", lambda s, l: s["lam"] * s["LF"])
    add("GDP_RFK", 37, "identity", lambda s, l: s["nu"] * s["K_PR"])
    # Reported, not imposed — see the module docstring.
    add("GDP_RMAX", 38, "identity",
        lambda s, l: min(s["GDP_RFE"], s["GDP_RFK"]))

    # --- Demography and rates, Eqs. (39)-(43) ----------------------------
    add("LF", 39, "calibrated", lambda s, l: s["g_LFOBR"] * l["LF"])
    add("POP", 40, "calibrated", lambda s, l: s["POP_OBR"])
    add("re", 41, "identity", lambda s, l: s["EMP"] / s["LF"])
    add("ru", 42, "identity", lambda s, l: 1.0 - s["re"])
    # Utilisation is measured against the *capital* ceiling only, Eq. (43) —
    # not against GDP_RMAX.
    add("u", 43, "identity", lambda s, l: s["GDP_R"] / s["GDP_RFK"])
