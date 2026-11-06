"""Whole-model checks after §3.1 and §3.4 landed (2026-11-06, round 4).

Hermetic half (runs in CI): the CSV alias map, the sector-indexed refs of
§3.4.7, the MFI residual-sector closure and the dividend closure on the
manual's own §5 Table 6 values. Cached-run half (skips in CI; see
test_oracle.py for the convention): the whole registry solved over
2023Q1-2040Q4 with nothing read from the oracle but exogenous inputs.
"""

from __future__ import annotations

import math

import pytest

from define_uk.model.calibration import INITIAL_VALUES as T6
from define_uk.model.calibration import PARAMETERS
from define_uk.model.scenario import CSV_ALIASES
from define_uk.model.sectors import build_registry

# Table 6 keys the cached CSVs do not print under any spelling.
NOT_PRINTED = {"SUBS_GVT"}
# Registry names the CSV_ALIASES map that are not Table 6 keys.
ALIAS_EXTRAS = {"r_IBL_NFCLR", "r_IBL_PSLR", "r_IBL_NMFILR", "r_IBL_GVTLR",
                "r_IBL_HHLR", "ROW_Pg"}
SECTOR_LEND = ("LEND_NFC", "LEND_PS", "LEND_MFI", "LEND_NMFI", "LEND_GVT",
               "LEND_HH", "LEND_ROW")
DIVIDENDS = ("DIVR_NFC", "DIVR_PS", "DIVR_HH", "DIVR_NMFI")


def _eq(forms="manual"):
    return {e.name: e for e in build_registry(forms)}


def test_csv_aliases_map_onto_table_6_names():
    """Every alias target is a Table 6 key (or a listed non-Table-6 name),
    so a differently spelled CSV column always lands on the name the
    equations read. Before 2026-11-06 the map held only lambda and MU, and
    r_IBA_PS, r_IBL_PS, r_IBL_GVT, OTEQL_NMFI and WS were held at their
    2022Q4 Table 6 values in every solved quarter."""
    targets = set(CSV_ALIASES.values())
    assert targets - set(T6) == ALIAS_EXTRAS
    assert len(targets) == len(CSV_ALIASES), "two CSV names alias one variable"


def test_every_printed_equation_is_registered_and_indexed_refs_parse():
    reg = build_registry()
    assert sorted({e.number for e in reg}) == list(range(1, 402))
    tagged = [e for e in reg if e.manual_ref.endswith("]")]
    assert {e.number for e in tagged} == {397, 398, 399, 400, 401}
    assert len(tagged) == 1 + 6 + 6 + 5 + 5  # r_BOEQ [Q]; 6 asset, 5 liability


def test_mfi_discrepancy_is_minus_the_sum_of_the_others():
    """Eq. (211): the MFI lending discrepancy closes Σ DISC to zero."""
    eqs = _eq()
    s = dict(T6)
    for n in ("DISC_NFC", "DISC_NMFI", "DISC_GVT", "DISC_HH", "DISC_ROW"):
        s[n] = eqs[n].func(s, T6)
    s["DISC_MFI"] = eqs["DISC_MFI"].func(s, T6)
    total = sum(s[n] for n in ("DISC_NFC", "DISC_NMFI", "DISC_GVT", "DISC_HH",
                               "DISC_ROW", "DISC_MFI"))
    assert total == pytest.approx(0.0, abs=1e-12)


def _dividend_gap(forms):
    """Σ dividends received + RoW net dividends - Σ dividends paid, with the
    four receipt equations evaluated on Table 6 (payments as tabulated)."""
    eqs = _eq(forms)
    s = dict(T6)
    for _ in range(3):  # DIVR_NFC (empirical) reads DIVR_HH and DIVR_PS
        for n in DIVIDENDS:
            s[n] = eqs[n].func(s, T6)
    received = s["DIVR_NFC"] + s["DIVR_PS"] + s["DIVR_HH"] + s["DIVR_NMFI"]
    paid = s["DIVP_NFC"] + s["DIVP_PS"] + s["DIVP_NMFI"]
    return received + s["DIVN_ROW"] - paid


def test_manual_dividend_allocation_does_not_close():
    """As printed, Eqs. (93), (163), (313) give each holder beta_j times its
    equity share of DIVP_NMFI (beta_dhh = 1.333, beta_dps = 0.773, beta_dnfc
    untabulated) and Eq. (221) omits the RoW, so the dividend row of the
    transactions matrix does not sum to zero: Σ LEND != 0 by construction."""
    assert abs(_dividend_gap("manual")) > 1.0


def test_empirical_dividend_forms_close_the_dividend_row_exactly():
    """The oracle's forms (empirical.py): DIVR_NFC is the residual, DIVR_HH
    and DIVR_PS divide by EQL_NMFI - EQN_RoW, NMFIs pay the RoW's DIVN."""
    assert _dividend_gap("empirical") == pytest.approx(0.0, abs=1e-9)
