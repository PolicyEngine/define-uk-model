"""Milestone 1 gate: §2.2 accounting matrices hold on the §5 initial values.

Tolerance convention: the manual prints Table 6 values to (at most) four
significant figures, so an identity over entries x_i can only be verified
up to the accumulated rounding, sum_i 0.5 * ulp4(x_i) where
ulp4(x) = 10^(floor(log10|x|) - 3). We allow a safety factor of 2 on that
bound. A strict 1e-6 relative check is impossible against 4-s.f. printed
values; this is the manual's own precision.

Known manual inconsistency (documented in calibration.py): Table 6's
LENDM_ROW (10.96) omits the DIVN_ROW term of §3.4.6 Eq. (383) — the manual
itself records the economy-wide LENDM as 5.44 where it "should equal 0 by
definition" (Table 6, p. 73). Because DISC_MFI is defined as minus the sum
of the other discrepancies (Eq. (211)), the MFI and RoW transaction columns
miss their national-accounts net lending by -DIVN_ROW and +DIVN_ROW
respectively. We pin that gap exactly so any drift fails loudly.
"""

from __future__ import annotations

import math

import pytest

from define_uk.model.accounting import (
    BALANCE_SHEET_MATRIX,
    FINANCIAL_NET_WORTH,
    NET_LENDING,
    SECTORS,
    TRANSACTIONS_MATRIX,
    balance_sheet_residuals,
    transactions_residuals,
)
from define_uk.model.calibration import INITIAL_VALUES

STATE = INITIAL_VALUES
SAFETY = 2.0


def _ulp4(x: float) -> float:
    """Unit in the last place of a 4-significant-figure printed value."""
    if x == 0.0:
        return 0.0
    return 10.0 ** (math.floor(math.log10(abs(x))) - 3)


def _tol(entries: list[float]) -> float:
    return SAFETY * sum(0.5 * _ulp4(x) for x in entries)


def _row_entries(matrix, name: str) -> list[float]:
    (row,) = [r for r in matrix if r.name == name]
    return [STATE[var] for cell in row.cells.values() for _, var in cell]


def _column_entries(matrix, sector: str, extra: list[str] = []) -> list[float]:
    values = [
        STATE[var]
        for row in matrix
        if sector in row.cells
        for _, var in row.cells[sector]
    ]
    return values + [STATE[v] for v in extra]


# ---------------------------------------------------------------------------
# Transactions flow matrix (manual §2.2 Table 1)
# ---------------------------------------------------------------------------
TRANS = transactions_residuals(STATE)


@pytest.mark.parametrize("row", [r.name for r in TRANSACTIONS_MATRIX])
def test_transactions_row_sums_to_zero(row: str) -> None:
    """Every monetary outflow has a matching inflow (§2.2, p. 5)."""
    tol = _tol(_row_entries(TRANSACTIONS_MATRIX, row))
    assert abs(TRANS["rows"][row]) <= tol, (row, TRANS["rows"][row], tol)


@pytest.mark.parametrize(
    "sector", [s for s in SECTORS if s not in ("MFI", "ROW")]
)
def test_transactions_column_equals_net_lending(sector: str) -> None:
    """Column sums to the sector's net-lending position (§2.2, p. 5)."""
    extra = [NET_LENDING[sector]] if NET_LENDING[sector] else []
    tol = _tol(_column_entries(TRANSACTIONS_MATRIX, sector, extra))
    assert abs(TRANS["columns"][sector]) <= tol, (
        sector,
        TRANS["columns"][sector],
        tol,
    )


@pytest.mark.parametrize(
    ("sector", "sign"), [("MFI", -1.0), ("ROW", +1.0)]
)
def test_transactions_mfi_row_columns_gap_is_divn_row(
    sector: str, sign: float
) -> None:
    """The MFI/RoW columns miss LEND by exactly -/+DIVN_ROW.

    This is the manual's own Table 6 inconsistency (LENDM_ROW omits the
    DIVN_ROW term of Eq. (383); LENDM tabulated as 5.44 where the manual
    says it should be 0). Pinned so any further drift fails.
    """
    expected = sign * STATE["DIVN_ROW"]
    tol = _tol(
        _column_entries(TRANSACTIONS_MATRIX, sector, [NET_LENDING[sector]])
    )
    assert abs(TRANS["columns"][sector] - expected) <= tol, (
        sector,
        TRANS["columns"][sector],
        expected,
        tol,
    )


def test_lend_row_sums_to_zero() -> None:
    """Table 1 bottom row: national-accounts net lending sums to zero."""
    entries = [STATE[v] for v in NET_LENDING.values() if v]
    assert abs(sum(entries)) <= _tol(entries)


# ---------------------------------------------------------------------------
# Balance-sheet matrix (manual §2.2 Table 2)
# ---------------------------------------------------------------------------
BS = balance_sheet_residuals(STATE)


@pytest.mark.parametrize("row", list(BS["rows"]))
def test_balance_sheet_row_sums_to_zero(row: str) -> None:
    """Every financial asset has a corresponding liability (§2.2, p. 5)."""
    tol = _tol(_row_entries(BALANCE_SHEET_MATRIX, row))
    assert abs(BS["rows"][row]) <= tol, (row, BS["rows"][row], tol)


@pytest.mark.parametrize("sector", list(FINANCIAL_NET_WORTH))
def test_balance_sheet_column_fnw(sector: str) -> None:
    """Financial rows net to FNW_s via the residual instrument.

    §3 Eqs. (194)-(196) NFC, (124)-(126) PS, (215)-(217) MFI, (249)-(251)
    NMFI, (298)-(302) GVT, (352)-(356) HH, (394)-(396) RoW.
    """
    tol = _tol(
        _column_entries(
            BALANCE_SHEET_MATRIX, sector, [FINANCIAL_NET_WORTH[sector]]
        )
    )
    assert abs(BS["columns_fnw"][sector]) <= tol, (
        sector,
        BS["columns_fnw"][sector],
        tol,
    )


@pytest.mark.parametrize("sector", ["NFC", "PS", "GVT", "HH"])
def test_balance_sheet_column_net_worth(sector: str) -> None:
    """Full column (real + financial) sums to the manual's NW_s.

    §3 Eqs. (203) NFC, (134) PS, (309) GVT, (366) HH.
    """
    nw = {"NFC": "NW_NFC", "PS": "NW_PS", "GVT": "NW_GVT", "HH": "NW_HH"}
    tol = _tol(_column_entries(BALANCE_SHEET_MATRIX, sector, [nw[sector]]))
    assert abs(BS["columns_nw"][sector]) <= tol, (
        sector,
        BS["columns_nw"][sector],
        tol,
    )


def test_overall_financial_net_worth_is_zero() -> None:
    """Sum of sectoral FNW is zero (Table 6 'FNW', 'should equal 0')."""
    entries = [STATE[v] for v in FINANCIAL_NET_WORTH.values()]
    assert abs(BS["totals"]["fnw_total"]) <= _tol(entries)


# ---------------------------------------------------------------------------
# Residual definitions: RES_s = FNW_s - FNWM_s and FNWM_s = FA_s - FL_s
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("sector", list(FINANCIAL_NET_WORTH))
def test_residual_instrument_definition(sector: str) -> None:
    """RES_s = FNW_s - FNWM_s (§3 Eqs. (196), (126), (217), (251), (302),
    (356), (396) rearranged)."""
    entries = [
        STATE[f"RES_{sector}"],
        STATE[f"FNW_{sector}"],
        STATE[f"FNWM_{sector}"],
    ]
    residual = entries[1] - entries[2] - entries[0]
    assert abs(residual) <= _tol(entries), (sector, residual)


@pytest.mark.parametrize(
    "sector", ["NFC", "PS", "MFI", "NMFI", "GVT", "HH"]
)
def test_model_financial_net_worth_definition(sector: str) -> None:
    """FNWM_s = FA_s - FL_s (§3 Eqs. (194), (124), (215), (249), (300),
    (354))."""
    entries = [
        STATE[f"FA_{sector}"],
        STATE[f"FL_{sector}"],
        STATE[f"FNWM_{sector}"],
    ]
    residual = entries[0] - entries[1] - entries[2]
    assert abs(residual) <= _tol(entries), (sector, residual)


def test_row_model_financial_net_worth() -> None:
    """FNWM_ROW = IBN_ROW + EQN_ROW + IBL_GVT_ROW (§3.4.6 Eq. (394))."""
    entries = [
        STATE["IBN_ROW"],
        STATE["EQN_ROW"],
        STATE["IBL_GVT_ROW"],
        STATE["FNWM_ROW"],
    ]
    residual = entries[0] + entries[1] + entries[2] - entries[3]
    assert abs(residual) <= _tol(entries)
