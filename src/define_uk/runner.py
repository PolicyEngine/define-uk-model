"""Run the upstream DEFINE-UK Rmd with R.

Pre-replication scaffold: this runner executes the upstream notebook as-is
and reports where its outputs land. It deliberately does NOT parse or
reinterpret results yet — that begins only once VALIDATION.md records a
passing replication of the published scenarios.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .upstream import MODEL_RMD, fetch

# R packages the upstream README lists; checked up front so a missing
# dependency fails with a shopping list instead of mid-notebook.
R_PACKAGES = (
    "zoo", "tidyverse", "readxl", "httr", "dynamac", "tseries", "lmtest",
    "urca", "dyn", "tsDyn", "dplyr", "dLagM", "openxlsx", "car", "seasonal",
    "ggplot2", "ggthemes", "showtext", "sysfonts", "showtextdb", "xtable",
    "data.table", "Cairo", "mFilter", "rmarkdown", "knitr",
)


def check_r() -> list[str]:
    """Return the list of missing R packages (empty = ready to run)."""
    if shutil.which("Rscript") is None:
        raise EnvironmentError(
            "Rscript not found on PATH — DEFINE-UK is an R model; install "
            "R >= 4.0 (https://cran.r-project.org/)"
        )
    script = (
        "cat(setdiff(c(" +
        ",".join(f'"{p}"' for p in R_PACKAGES) +
        "), rownames(installed.packages())), sep='\\n')"
    )
    out = subprocess.run(
        ["Rscript", "-e", script], check=True, capture_output=True, text=True
    )
    return [line for line in out.stdout.splitlines() if line.strip()]


def run(workdir: Path | None = None) -> Path:
    """Render the upstream notebook; return the output directory.

    Runs in the pinned upstream checkout (the notebook writes to ./output).
    Expect a long runtime: the notebook estimates, simulates every policy
    scenario, and renders all published figures and tables.
    """
    missing = check_r()
    if missing:
        raise EnvironmentError(
            "missing R packages: " + ", ".join(missing) +
            ' — install with install.packages(c(' +
            ", ".join(f'"{p}"' for p in missing) + "))"
        )
    repo = fetch()
    cwd = workdir or repo
    subprocess.run(
        ["Rscript", "-e", f'rmarkdown::render("{MODEL_RMD}")'],
        cwd=cwd, check=True,
    )
    out = cwd / "output"
    if not out.exists():
        raise RuntimeError(
            "the notebook completed but wrote no output/ directory — "
            "upstream layout changed; re-pin and revisit the adapter"
        )
    return out
