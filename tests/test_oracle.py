"""Oracle comparison: our implementation vs the pinned upstream run.

The upstream R code (unlicensed, fetched at a pinned commit by
``define_uk.upstream``) is used here strictly as a numerical oracle per
REIMPLEMENTATION.md.

This module must never go green by accident. The comparison it names is the
gate for reimplementation milestone 2, and until it is written the only
honest outcomes are *skip* (the oracle is unavailable here) or *fail* (the
oracle is available and the comparison has not been written). It is a
one-line change to make it pass silently, so the reasons are spelled out:

- The skip is keyed on the **cached run**, not on ``Rscript``. The
  comparison needs upstream *outputs*; an R installation with no cached run
  cannot supply them, and a cached run needs no R. Keying on the interpreter
  meant a developer with R installed but no cache saw a hard failure with the
  reason "R not installed", and one without R saw a skip that claimed the
  cache was the problem.
- Where the oracle *is* available the test raises rather than skips, so the
  outstanding work cannot hide behind an environment condition.
"""

import pytest

from define_uk.model.sectors import build_registry
from define_uk.scenarios import _run_root


def _cached_run_available() -> bool:
    try:
        _run_root()
    except FileNotFoundError:
        return False
    return True


requires_cached_run = pytest.mark.skipif(
    not _cached_run_available(),
    reason=(
        "no cached DEFINE-UK run (define_uk.runner.run first; the upstream "
        "is unlicensed, so CI never fetches or runs it)"
    ),
)


@requires_cached_run
def test_baseline_gdp_path_matches_oracle():
    if len(build_registry()) == 0:
        pytest.skip("milestone 2 (macro + production) not implemented yet")
    raise NotImplementedError(
        "run define_uk.runner.run for the S1 baseline, solve our registry "
        "over the same horizon, compare GDP paths within the tolerance "
        "recorded in VALIDATION.md"
    )


def test_the_oracle_gate_cannot_pass_by_accident():
    """Runs everywhere, including CI: the gate above is still outstanding.

    Milestone 2 is not passed until ``test_baseline_gdp_path_matches_oracle``
    is a real comparison. This test is what makes the *absence* of that
    comparison visible in a green suite — it fails the moment the registry is
    complete enough that a reader might assume the oracle gate has run.
    """
    registry = build_registry()
    assert len(registry) > 0, "sector modules register nothing"

    sections = {eq.section for eq in registry}
    assert "§3.3.3" not in sections, (
        "§3.3.3 has landed — the oracle comparison is now the only thing "
        "between here and milestone 2, so write it and delete this guard"
    )
