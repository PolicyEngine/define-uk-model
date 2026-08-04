"""Sector modules, one per Model Manual v1.1 section (§3.1–§3.4.7)."""

from ..registry import Registry
from . import (ecosystem, macro, production, nfc, mfi, nmfi,
               government, households, row, returns)

ALL = (ecosystem, macro, production, nfc, mfi, nmfi,
       government, households, row, returns)


def build_registry() -> Registry:
    """Assemble the full model registry from every sector module."""
    registry = Registry()
    for module in ALL:
        module.register(registry)
    return registry
