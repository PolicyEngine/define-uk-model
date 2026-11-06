"""Sector modules, one per Model Manual v1.1 section (§3.1–§3.4.7)."""

from ..registry import Registry
from . import (ecosystem, macro, production, power, io, nfc, mfi, nmfi,
               government, households, row, returns)

ALL = (ecosystem, macro, production, power, io, nfc, mfi, nmfi,
       government, households, row, returns)


def build_registry(forms: str = "manual") -> Registry:
    """Assemble the full model registry from every sector module.

    ``forms="manual"`` (the default) is the Model Manual as printed.
    ``forms="empirical"`` swaps in the 18 forms the oracle's numbers follow
    where it departs from the printed manual (``define_uk.model.empirical``,
    found from the cached output CSVs alone, 2026-11-06).
    """
    if forms not in ("manual", "empirical"):
        raise ValueError(f"forms must be 'manual' or 'empirical', not {forms!r}")
    registry = Registry()
    for module in ALL:
        module.register(registry)
    if forms == "empirical":
        from ..empirical import apply
        apply(registry)
    return registry
