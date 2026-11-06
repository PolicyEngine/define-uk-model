"""Period-by-period scenario solver for the clean-room registry.

``solve_path`` solves the registered equations quarter by quarter: within
each quarter it runs the Gauss-Seidel sweep of ``solver.solve_period`` to a
fixed point (relative tolerance ``tol``, at most ``max_iter`` sweeps); the
solved quarter becomes the next quarter's lag. A quarter that does not
converge raises ``ConvergenceError`` naming the quarter; nothing is ever
returned from a non-converged sweep.

Closure: block-exogenous, not a full-model solve
------------------------------------------------
The registry implements manual §3.2, §3.3.1, §3.3.2 and §3.3.3. §3.1
(ecosystem) and §3.4.1-§3.4.7 (the sectors: NFC, MFI, NMFI, government,
households, rest of the world, rates of return) are not implemented yet.
Every variable the registry does not determine is therefore read from a
*reference path* (a cached oracle ``Variables_*.csv``) and held there. So:

- a solve on the baseline reference tests the implemented blocks *given*
  the oracle's paths for everything else (a conditional, block-level
  reproduction, not the full milestone-3 baseline);
- a shock to an exogenous variable moves only what the implemented blocks
  determine. Households, firms' investment, government financing and the
  rest of the world do not respond, so there is no consumption multiplier,
  and the economy-wide stock-flow closure (Σ sectoral net lending = 0)
  holds only on the reference path itself. Results from shocked solves are
  diagnostics of the implemented blocks, not model scenarios.

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

# Cached-CSV column -> registry name, where the two spell a variable
# differently. Used to seed lags and to compare solved paths.
CSV_ALIASES = {"lambda": "lam", "MU": "mu"}

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
        if t > 1 and "K_PS" in reference[t - 2]:
            r["K_PS_LAG"] = reference[t - 2]["K_PS"]
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
        # Eq. (96) reads K_PS two quarters back (power.SECOND_LAG_KEYS).
        state["K_PS_LAG"] = lag["K_PS"]
        path.append(state)
        lag = state
    path.extend(dict(r) for r in reference[end + 1:])
    return path
