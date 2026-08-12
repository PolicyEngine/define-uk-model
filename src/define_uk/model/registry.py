"""Equation registry: every model equation declares its manual provenance."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterator, Mapping

# kind mirrors the manual's own taxonomy (§2.3): accounting identities,
# econometrically estimated behavioural equations, and calibrated relations.
KINDS = ("identity", "behavioural", "calibrated")

# The one citation format the whole package uses: "§3.3.2 eq. (84)". Enforcing
# it here rather than by convention is what lets the section tests parse an
# equation number out of every ref and assert the section is *contiguous* — a
# ref that silently failed to parse would drop an equation out of that check
# without failing anything. Test fixtures opt out with the TEST_REF sentinel.
MANUAL_REF = re.compile(r"^§(\d+(?:\.\d+)*) eq\. \((\d+)\)$")
TEST_REF = "test fixture"


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
        if self.manual_ref != TEST_REF and not MANUAL_REF.match(self.manual_ref):
            raise ValueError(
                f"{self.name}: manual_ref {self.manual_ref!r} is not of the "
                f"form '§3.3.2 eq. (84)' (see REIMPLEMENTATION.md)"
            )

    @property
    def section(self) -> str | None:
        """Manual section, e.g. ``'§3.3.2'``; None for test fixtures."""
        m = MANUAL_REF.match(self.manual_ref)
        return f"§{m.group(1)}" if m else None

    @property
    def number(self) -> int | None:
        """Manual equation number, e.g. ``84``; None for test fixtures."""
        m = MANUAL_REF.match(self.manual_ref)
        return int(m.group(2)) if m else None


@dataclass
class Registry:
    """Ordered collection of equations; one per endogenous variable."""

    _equations: dict[str, Equation] = field(default_factory=dict)

    def add(self, equation: Equation) -> None:
        if equation.name in self._equations:
            raise ValueError(f"duplicate equation for {equation.name}")
        # One manual equation determines one endogenous variable, so two
        # registrations citing the same ref means a copy-pasted provenance —
        # which would make an equation *look* transcribed while implementing
        # something else. The per-section contiguity tests cannot see this on
        # their own: a duplicated ref shows up there only as a hole elsewhere.
        if equation.manual_ref != TEST_REF:
            clash = next(
                (e for e in self._equations.values()
                 if e.manual_ref == equation.manual_ref),
                None,
            )
            if clash is not None:
                raise ValueError(
                    f"{equation.name}: manual_ref {equation.manual_ref!r} is "
                    f"already cited by {clash.name}"
                )
        self._equations[equation.name] = equation

    def __iter__(self) -> Iterator[Equation]:
        return iter(self._equations.values())

    def __len__(self) -> int:
        return len(self._equations)

    def names(self) -> list[str]:
        return list(self._equations)
