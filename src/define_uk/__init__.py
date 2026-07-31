"""DEFINE-UK adapter for the PolicyEngine Macro suite (pre-replication)."""

from .upstream import UPSTREAM_COMMIT, UPSTREAM_URL, fetch
from .runner import check_r, run

__version__ = "0.0.1"
__all__ = [
    "UPSTREAM_COMMIT", "UPSTREAM_URL", "fetch", "check_r", "run",
    "__version__",
]
