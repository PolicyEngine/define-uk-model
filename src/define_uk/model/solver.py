"""Per-period Gauss–Seidel solver for the SFC system."""

from __future__ import annotations

from typing import Mapping

from .registry import Registry


def solve_period(
    registry: Registry,
    lag: Mapping[str, float],
    exogenous: Mapping[str, float] | None = None,
    tol: float = 1e-8,
    max_iter: int = 5_000,
) -> dict[str, float]:
    """Solve one period: sweep all equations until convergence.

    ``lag`` is the previous period's full solved state (also the initial
    guess); ``exogenous`` values are held fixed. Raises if the sweep does
    not converge — a non-converging SFC period is a model error, never a
    result to return.
    """
    state: dict[str, float] = dict(lag)
    if exogenous:
        state.update(exogenous)

    for _ in range(max_iter):
        max_delta = 0.0
        for eq in registry:
            new = eq.func(state, lag)
            old = state.get(eq.name, 0.0)
            scale = max(abs(old), abs(new), 1.0)
            max_delta = max(max_delta, abs(new - old) / scale)
            state[eq.name] = new
        if max_delta < tol:
            return state
    raise RuntimeError(
        f"period did not converge after {max_iter} sweeps (max_delta={max_delta:.3e})"
    )
