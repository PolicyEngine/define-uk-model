"""Clean-room Python implementation of DEFINE-UK 1.1.

Implemented from the published Model Manual v1.1 (George & Dafermos, 2026)
only; the upstream R code is used exclusively as an output oracle. See
REIMPLEMENTATION.md for the protocol.
"""

from .registry import Equation, Registry
from .solver import solve_period

__all__ = ["Equation", "Registry", "solve_period"]
