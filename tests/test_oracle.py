"""Oracle comparison: our implementation vs the pinned upstream run.

The upstream R code (unlicensed, fetched at a pinned commit by
``define_uk.upstream``) is used here strictly as a numerical oracle per
REIMPLEMENTATION.md. These tests activate as milestones land; until the
first model slice exists they skip.
"""

import shutil

import pytest

from define_uk.model.sectors import build_registry

requires_r = pytest.mark.skipif(
    shutil.which("Rscript") is None, reason="R not installed"
)


@requires_r
def test_baseline_gdp_path_matches_oracle():
    if len(build_registry()) == 0:
        pytest.skip("milestone 2 (macro + production) not implemented yet")
    raise NotImplementedError(
        "run define_uk.runner.run for the S1 baseline, solve our registry "
        "over the same horizon, compare GDP paths within the tolerance "
        "recorded in VALIDATION.md"
    )
