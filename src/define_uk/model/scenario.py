"""Period-by-period scenario solver for the clean-room registry.

``solve_path`` solves the registered equations quarter by quarter: within
each quarter it runs the Gauss-Seidel sweep of ``solver.solve_period`` to a
fixed point (relative tolerance ``tol``, at most ``max_iter`` sweeps); the
solved quarter becomes the next quarter's lag. A quarter that does not
converge raises ``ConvergenceError`` naming the quarter; nothing is ever
returned from a non-converged sweep.

Closure: the whole model (since 2026-11-06, round 4)
----------------------------------------------------
The registry implements every printed equation of the manual, §3.1 to
§3.4.7 (Eqs. (1)-(401)). The reference path supplies only (a) the lags at
the start quarter and (b) exogenous inputs no equation determines: policy
paths (GCF_GVTBASE = the reference GCF_GVT, P_ETSRB, SPEND_GVTPS,
SUBS_PS), demography and OBR inputs, and parameters the manual leaves
undefined. Before round 4 §3.1 and §3.4 were read from the reference and a
shock moved only §3.2-§3.3.3.

Stock-flow closure is not imposed: MFIs are the residual sector (Eqs.
(211), (213), (214), (216)) and Σ_s LEND_s = 0 is the model's redundant
equation, checked on solved paths. As printed it fails in the dividend
row (empirical.py, "Dividend closure"); forms="empirical" closes it.

``overrides`` exogenises variables: a name given there is taken off the
registry for the solve and set to the given value (scalar, or one value per
quarter of the reference) — a shock if the name is exogenous anyway, a
counterfactual equation if it is endogenous.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Mapping, Sequence

from .calibration import INITIAL_VALUES
from .registry import Registry
from .sectors import power
from .solver import solve_period

# Cached-CSV column -> registry name (the manual §5 Table 6 spelling), where
# the two spell a variable differently. Used to seed lags and exogenous
# inputs and to compare solved paths. Covers every Table 6 key the CSVs print
# under another name (tests/test_scenario_solver.py checks completeness);
# Table 6's SUBS_GVT is the one key the CSVs do not print at all.
#
# Before 2026-11-06 this map held only lambda and MU, so every other
# differently-spelled input (e.g. r_IBA_PS, r_IBL_PS, r_IBL_GVT, OTEQL_NMFI,
# WS) was never read from the reference: the solver's guess started from
# Table 6 and carried the 2022Q4 value forward unchanged every quarter.
CSV_ALIASES = {
    "C_HIEER": "CHI_EER", "C_HIENR": "CHI_ENR", "DISC_RoW": "DISC_ROW",
    "DIVN_RoW": "DIVN_ROW", "EQNTR_RoW": "EQNTR_ROW", "EQN_RoW": "EQN_ROW",
    "FNW_GVTM": "FNWM_GVT", "FNW_HHM": "FNWM_HH", "FNW_M": "FNWM",
    "FNW_MFIM": "FNWM_MFI", "FNW_NFCM": "FNWM_NFC", "FNW_NMFIM": "FNWM_NMFI",
    "FNW_PSM": "FNWM_PS", "FNW_RoW": "FNW_ROW", "FNW_RoWM": "FNWM_ROW",
    "IBLTR_GVTMFI": "IBLTR_GVT_MFI", "IBLTR_GVTNMFI": "IBLTR_GVT_NMFI",
    "IBLTR_GVTRoW": "IBLTR_GVT_ROW", "IBL_GVTMFI": "IBL_GVT_MFI",
    "IBL_GVTNMFI": "IBL_GVT_NMFI", "IBL_GVTRoW": "IBL_GVT_ROW",
    "IBNTR_RoW": "IBNTR_ROW", "IBN_RoW": "IBN_ROW", "INSTR": "INSTR_",
    "INTN_RoW": "INTN_ROW", "I_ADJ": "IADJ", "LEND_GVTM": "LENDM_GVT",
    "LEND_HHM": "LENDM_HH", "LEND_M": "LENDM", "LEND_MFIM": "LENDM_MFI",
    "LEND_NFCM": "LENDM_NFC", "LEND_NMFIM": "LENDM_NMFI",
    "LEND_RoW": "LEND_ROW", "LEND_RoWM": "LENDM_ROW", "MU": "mu",
    "OT_EQAHH": "OTEQA_HH", "OT_EQANFC": "OTEQA_NFC",
    "OT_EQANMFI": "OTEQA_NMFI", "OT_EQAPS": "OTEQA_PS",
    "OT_EQLNFC": "OTEQL_NFC", "OT_EQLNMFI": "OTEQL_NMFI",
    "OT_EQLPS": "OTEQL_PS", "OT_EQNRoW": "OTEQN_ROW",
    "OT_IBAGVT": "OTIBA_GVT", "OT_IBAHH": "OTIBA_HH",
    "OT_IBANFC": "OTIBA_NFC", "OT_IBANMFI": "OTIBA_NMFI",
    "OT_IBAPS": "OTIBA_PS", "OT_IBARoW": "OTIBA_ROW",
    "OT_IBLGVT": "OTIBL_GVT", "OT_IBLHH": "OTIBL_HH",
    "OT_IBLNFC": "OTIBL_NFC", "OT_IBLNMFI": "OTIBL_NMFI",
    "OT_IBLPS": "OTIBL_PS", "OT_INS": "OTINS", "OT_PENS": "OTPENS",
    "OT_RESGVT": "OTRES_GVT", "OT_RESHH": "OTRES_HH",
    "OT_RESNFC": "OTRES_NFC", "OT_RESNMFI": "OTRES_NMFI",
    "OT_RESPS": "OTRES_PS", "OT_RESRoW": "OTRES_ROW", "P_E": "PE",
    "P_F": "PF", "P_H": "PH", "P_I": "PI", "RESTR_RoW": "RESTR_ROW",
    "RES_RoW": "RES_ROW", "RoW_DR": "ROW_DR", "W_S": "WS", "YP_RoW": "YP_ROW",
    "lambda": "lam", "r_IBAGVT": "r_IBA_GVT", "r_IBAGVTLR": "r_IBA_GVTLR",
    "r_IBAHH": "r_IBA_HH", "r_IBAHHLR": "r_IBA_HHLR", "r_IBANFC": "r_IBA_NFC",
    "r_IBANFCLR": "r_IBA_NFCLR", "r_IBANMFI": "r_IBA_NMFI",
    "r_IBANMFILR": "r_IBA_NMFILR", "r_IBAPS": "r_IBA_PS",
    "r_IBAPSLR": "r_IBA_PSLR", "r_IBLGVT": "r_IBL_GVT", "r_IBLHH": "r_IBL_HH",
    "r_IBLNFC": "r_IBL_NFC", "r_IBLNMFI": "r_IBL_NMFI", "r_IBLPS": "r_IBL_PS",
    "r_IBNRoW": "r_IBN_ROW", "r_IBNRoWLR": "r_IBN_ROWLR",
    # Not Table 6 keys, but printed by the CSVs under another spelling: the
    # long-run liability rates of Eq. (401) and world price growth (376).
    "r_IBLNFCLR": "r_IBL_NFCLR", "r_IBLPSLR": "r_IBL_PSLR",
    "r_IBLNMFILR": "r_IBL_NMFILR", "r_IBLGVTLR": "r_IBL_GVTLR",
    "r_IBLHHLR": "r_IBL_HHLR", "RoW_Pg": "ROW_Pg",
}

# Variables some equation reads two quarters back: name -> carried key.
SECOND_LAGS = {"K_PS": "K_PS_LAG", "K_NFC": "K_NFC_LAG", "GCF_HHNB": "GCF_HHNB_LAG"}

START_YEAR = 1987  # cached runs are anchored 1987Q1-2040Q4
SIM_START = 144  # 2023Q1, the first simulated quarter


def quarter_label(t: int) -> str:
    return f"{START_YEAR + t // 4}Q{t % 4 + 1}"


class ConvergenceError(RuntimeError):
    """A quarter of a scenario solve did not reach the fixed point."""

    def __init__(self, t: int, cause: Exception):
        self.t = t
        self.quarter = quarter_label(t)
        super().__init__(f"{self.quarter} (row {t}): {cause}")


def load_reference(path: Path | str) -> list[dict[str, float]]:
    """Read a cached ``Variables_*.csv`` into one float dict per quarter."""
    with Path(path).open() as fh:
        rows = list(csv.DictReader(fh))
    return [
        {k: (float(v) if v not in ("", "NA") else math.nan)
         for k, v in r.items() if k}
        for r in rows
    ]


def scenario_inputs(
    reference: Sequence[Mapping[str, float]],
) -> list[dict[str, float]]:
    """The reference path plus the exogenous inputs it does not print.

    Adds, per quarter: the registry spellings of ``CSV_ALIASES``; the
    §3.3.2 policy switches at their inert baseline values
    (``power.POLICY_DEFAULTS``, unless the reference prints them); the OBR
    labour-force growth factor g_LFOBR = LF_t / LF_{t-1}, recovered from
    the reference's own LF by inverting Eq. (39) (the OBR series is an input
    the CSVs do not print); the power-sector depreciation rate δ_KPS from
    δ_KPSFF (power.MANUAL_GAPS["delta_KPS"]); and seeds for the two §3.3.2
    expectation variables the CSVs do not print, Eu_PS = Fu_PS = u_PS (what
    Eqs. (88)-(89) return with CRED = 0 and no ban).
    """
    out = []
    for t, row in enumerate(reference):
        r = dict(row)
        for csv_name, name in CSV_ALIASES.items():
            if csv_name in r and name not in r:
                r[name] = r[csv_name]
        for k, v in power.POLICY_DEFAULTS.items():
            r.setdefault(k, v)
        r["t_PS"] = float(t)
        if t > 0 and "LF" in r and "g_LFOBR" not in row:
            r["g_LFOBR"] = r["LF"] / reference[t - 1]["LF"]
        if "delta_KPSFF" in r:
            r.setdefault("delta_KPS", r["delta_KPSFF"])
        if "u_PS" in r:
            r.setdefault("Eu_PS", r["u_PS"])
            r.setdefault("Fu_PS", r["u_PS"])
        for name, key in SECOND_LAGS.items():
            if t > 1 and name in reference[t - 2]:
                r[key] = reference[t - 2][name]
        # §3.4 exogenous inputs the CSVs do not print under the manual name.
        if "GCF_GVT" in r:  # Eq. (272): the OBR baseline path
            r.setdefault("GCF_GVTBASE", r["GCF_GVT"])
        r.setdefault("GCF_GVTNFFR", 0.0)  # Eq. (276), government.MANUAL_GAPS
        r.setdefault("SUBS_GVT", 0.0)  # Eq. (281), Table 6 value
        if "ROW_DR" in r and "PF" in r:  # Eq. (369), not printed
            r.setdefault("ROW_D", r["ROW_DR"] * r["PF"])
        out.append(r)
    return out


def _value(spec, t: int) -> float:
    if isinstance(spec, (int, float)):
        return float(spec)
    return float(spec[t])


def solve_path(
    registry: Registry,
    reference: Sequence[Mapping[str, float]],
    start: int = SIM_START,
    end: int | None = None,
    *,
    overrides: Mapping[str, float | Sequence[float]] | None = None,
    tol: float = 1e-10,
    max_iter: int = 2_000,
) -> list[dict[str, float]]:
    """Solve quarters ``start``..``end`` (inclusive; default: last row).

    Returns one state dict per row of ``reference``: rows before ``start``
    are the reference history, unchanged; solved rows hold every exogenous
    value used and every endogenous value found. Lags at ``start`` come from
    ``reference[start - 1]``, falling back to the manual's Table 6 initial
    values for endogenous variables the reference does not print.
    """
    overrides = dict(overrides or {})
    end = len(reference) - 1 if end is None else end
    if not 0 < start <= end < len(reference):
        raise ValueError(f"bad solve window {start}..{end}")

    active = Registry()
    for eq in registry:
        if eq.name not in overrides:
            active.add(eq)
    endogenous = set(active.names())

    path: list[dict[str, float]] = [dict(r) for r in reference[:start]]
    lag = dict(INITIAL_VALUES)
    lag.update({k: v for k, v in reference[start - 1].items()
                if not math.isnan(v)})
    for name, spec in overrides.items():
        lag[name] = _value(spec, start - 1)
    path[start - 1] = lag

    for t in range(start, end + 1):
        exo = {k: v for k, v in reference[t].items() if k not in endogenous}
        for name, spec in overrides.items():
            exo[name] = _value(spec, t)
        guess = {**lag, **exo}
        try:
            state = solve_period(active, lag, exogenous=exo, tol=tol,
                                 max_iter=max_iter, guess=guess)
        except (RuntimeError, ZeroDivisionError, ValueError, OverflowError) as e:
            raise ConvergenceError(t, e) from e
        # Eqs. (96), (166), (324) read two quarters back (SECOND_LAGS).
        for name, key in SECOND_LAGS.items():
            state[key] = lag[name]
        path.append(state)
        lag = state
    path.extend(dict(r) for r in reference[end + 1:])
    return path
