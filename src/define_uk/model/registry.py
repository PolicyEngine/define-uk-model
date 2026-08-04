"""Equation registry: every model equation declares its manual provenance."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterator, Mapping

# kind mirrors the manual's own taxonomy (§2.3): accounting identities,
# econometrically estimated behavioural equations, and calibrated relations.
KINDS = ("identity", "behavioural", "calibrated")


@dataclass(frozen=True)
class Equation:
    """One endogenous variable's equation for the current period.

    ``func`` maps (state, lag) -> value, where ``state`` holds this period's
    values so far (Gauss–Seidel: within-period values already updated this
    sweep are visible) and ``lag`` holds last period's solved values.
    """

    name: str  # endogenous variable it determines
    manual_ref: str  # e.g. "§3.4.5 eq. 112" — REQUIRED, see REIMPLEMENTATION.md
    kind: str
    func: Callable[[Mapping[str, float], Mapping[str, float]], float]

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"{self.name}: kind must be one of {KINDS}")
        if not self.manual_ref.strip():
            raise ValueError(f"{self.name}: manual_ref is required")


@dataclass
class Registry:
    """Ordered collection of equations; one per endogenous variable."""

    _equations: dict[str, Equation] = field(default_factory=dict)

    def add(self, equation: Equation) -> None:
        if equation.name in self._equations:
            raise ValueError(f"duplicate equation for {equation.name}")
        self._equations[equation.name] = equation

    def __iter__(self) -> Iterator[Equation]:
        return iter(self._equations.values())

    def __len__(self) -> int:
        return len(self._equations)

    def names(self) -> list[str]:
        return list(self._equations)
