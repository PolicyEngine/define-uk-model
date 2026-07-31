"""Fetch the upstream DEFINE-UK code at a pinned commit.

The upstream repository (DEFINE-model/DEFINE_UK_1.1) is public on GitHub but
carries no license, so this package never vendors or redistributes it.
Instead it is cloned into a local cache at run time and executed in place.
Pinning a commit keeps runs reproducible; bumping the pin is an explicit,
reviewed change.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

UPSTREAM_URL = "https://github.com/DEFINE-model/DEFINE_UK_1.1"
# DEFINE_UK_1.1@main as of 2026-08-01. Bump deliberately; the validation
# targets in VALIDATION.md are tied to this revision.
UPSTREAM_COMMIT = "846081a580a6033159d5c421632ad8f0b30d0ded"
MODEL_RMD = "DEFINE-UK V1_1.Rmd"

CACHE_ENV = "DEFINE_UK_CACHE"


def cache_dir() -> Path:
    env = os.environ.get(CACHE_ENV)
    if env:
        return Path(env).expanduser()
    return Path.home() / ".cache" / "define-uk-model"


def fetch(commit: str = UPSTREAM_COMMIT) -> Path:
    """Clone (or reuse) the upstream repo at ``commit``; return its path.

    The checkout is verified to be at exactly ``commit`` — a cache directory
    left at another revision is reset, never silently reused.
    """
    dest = cache_dir() / commit
    marker = dest / ".git"
    if not marker.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--no-checkout", UPSTREAM_URL, str(dest)],
            check=True,
        )
        subprocess.run(["git", "checkout", commit], cwd=dest, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=dest, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    if head != commit:
        raise RuntimeError(
            f"cached DEFINE-UK checkout at {dest} is at {head}, expected "
            f"{commit}; remove the cache directory and retry"
        )
    rmd = dest / MODEL_RMD
    if not rmd.exists():
        raise FileNotFoundError(
            f"upstream checkout has no {MODEL_RMD!r}; the pinned commit no "
            "longer matches this adapter"
        )
    return dest
