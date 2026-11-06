"""Per-period Gauss–Seidel solver for the SFC system."""

from __future__ import annotations

import math
from typing import Mapping

from .registry import Registry


def solve_period(
    registry: Registry,
    lag: Mapping[str, float],
    exogenous: Mapping[str, float] | None = None,
    tol: float = 1e-8,
    max_iter: int = 5_000,
    guess: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """Solve one period: sweep all equations until convergence.

    ``lag`` is the previous period's full solved state; the initial guess is
    ``guess`` if given, else ``lag``. ``exogenous`` values are held fixed.
    Raises if the sweep does not converge — a non-converging SFC period is a
    model error, never a result to return. A non-finite value (NaN or inf)
    from any equation also raises: before 2026-11-06 a NaN made the
    relative change compare false, so a sweep that produced NaN "converged"
    and returned it.
    """
    state: dict[str, float] = dict(lag if guess is None else guess)
    if exogenous:
        state.update(exogenous)

    max_delta = math.inf
    worst = None
    for _ in range(max_iter):
        max_delta = 0.0
        for eq in registry:
            new = eq.func(state, lag)
            if not math.isfinite(new):
                raise RuntimeError(
                    f"{eq.name} ({eq.manual_ref}) is not finite: {new}"
                )
            old = state.get(eq.name, 0.0)
            scale = max(abs(old), abs(new), 1.0)
            delta = abs(new - old) / scale
            if delta > max_delta:
                max_delta, worst = delta, eq.name
            state[eq.name] = new
        if max_delta < tol:
            return state
    raise RuntimeError(
        f"period did not converge after {max_iter} sweeps "
        f"(max_delta={max_delta:.3e} in {worst})"
    )
