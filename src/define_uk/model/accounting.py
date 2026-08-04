"""DEFINE-UK §2.2 accounting core: transactions and balance-sheet matrices.

Machine-readable transcription of the manual's Table 1 (transactions flow
matrix, p. 6) and Table 2 (balance-sheet matrix, p. 7), with each cell
expressed in the model's own variables (§3 equation numbers as printed in
the manual body; note Table 6's cross-references use a different, stale
numbering — see calibration.py).

Conventions (manual §2.2, p. 5):

- Transactions matrix: '+' is a monetary inflow, '-' an outflow. Every flow
  row sums to zero across sectors; every sector column sums to the sector's
  net-lending position (Table 1 bottom row), with a *residual transaction*
  (the DISC lending discrepancies, §3 Eqs. (175), (211), (229), (282),
  (335), (384)) closing the gap between model flows and national-accounts
  net lending. The production module is not a sector and holds no
  assets/liabilities (manual §3.3 fn. 14): its column sums to exactly zero.
- Balance-sheet matrix: '+' is an asset, '-' a liability. Every financial
  instrument row sums to zero; column sums give net worth, with a *residual
  financial instrument* RES_s = FNW_s - FNWM_s (§3 Eqs. (196), (217),
  (251), (302), (356), (396)) reflecting stocks not modelled explicitly.

RoW is recorded in net terms for property income and financial stocks
(manual §3.4.6, p. 47): net interest INTN_ROW sits in the
interest-received row, net dividends DIVN_ROW in the dividends-paid-to-
NMFIs row, and the net stock IBN_ROW in the interest-bearing-assets row
(the manual's IBA_RoW/IBL_RoW of Eqs. (213)-(214) are initialised with the
net position on the asset side and zero on the liability side — the only
split consistent with Table 6's FA_MFI = 7701 and FL_MFI = 7591).

Each cell is a linear combination of state variables: a tuple of
(coefficient, variable-name) pairs evaluated against a state mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

SECTORS = ("PROD", "NFC", "PS", "MFI", "NMFI", "GVT", "HH", "ROW")

Cell = tuple[tuple[float, str], ...]


@dataclass(frozen=True)
class Row:
    """One instrument/flow row of an accounting matrix."""

    name: str
    manual_ref: str
    cells: Mapping[str, Cell]  # sector -> linear combination

    def evaluate(self, state: Mapping[str, float]) -> dict[str, float]:
        return {
            sector: sum(coef * state[var] for coef, var in cell)
            for sector, cell in self.cells.items()
        }


def _c(*terms: tuple[float, str]) -> Cell:
    return tuple(terms)


# ---------------------------------------------------------------------------
# Transactions flow matrix — manual §2.2 Table 1 (p. 6), cell variables from
# the §3 equations cited per row.
# ---------------------------------------------------------------------------
TRANSACTIONS_MATRIX: tuple[Row, ...] = (
    Row(
        "consumption_production",
        "§2.2 Table 1; §3.3.1 Eq. (44) final demand, §3.4.5 Eq. (317)",
        {
            "PROD": _c((+1, "CONS_HHP"), (+1, "CONS_GVT")),
            "GVT": _c((-1, "CONS_GVT")),
            "HH": _c((-1, "CONS_HHP")),
        },
    ),
    Row(
        "consumption_power",
        "§2.2 Table 1; §3.4.5 Eq. (320)",
        {
            "PS": _c((+1, "CONS_HHPS")),
            "HH": _c((-1, "CONS_HHPS")),
        },
    ),
    Row(
        "gross_capital_formation",
        "§2.2 Table 1; §3.2 Eq. (23) (GCF_PS = GCF_PSFF + GCF_PSNFF, §3.4.2)",
        {
            "PROD": _c(
                (+1, "GCF_NFC"),
                (+1, "GCF_PSFF"),
                (+1, "GCF_PSNFF"),
                (+1, "GCF_GVT"),
                (+1, "GCF_HH"),
            ),
            "NFC": _c((-1, "GCF_NFC")),
            "PS": _c((-1, "GCF_PSFF"), (-1, "GCF_PSNFF")),
            "GVT": _c((-1, "GCF_GVT")),
            "HH": _c((-1, "GCF_HH")),
        },
    ),
    Row(
        "exports",
        "§2.2 Table 1; §3.2 Eq. (21)",
        {"PROD": _c((+1, "EXP")), "ROW": _c((-1, "EXP"))},
    ),
    Row(
        "imports",
        "§2.2 Table 1; §3.2 Eq. (21)",
        {"PROD": _c((-1, "IMP")), "ROW": _c((+1, "IMP"))},
    ),
    Row(
        "ic_production_to_power",
        "§2.2 Table 1 'Prod -> PS'; §2.1 p. 3 (IC_PSP: production's "
        "intermediate consumption of power products)",
        {"PROD": _c((-1, "IC_PSP")), "PS": _c((+1, "IC_PSP"))},
    ),
    Row(
        "ic_power_to_production",
        "§2.2 Table 1 'PS -> Prod'; §2.1 p. 3 (IC_PPS: power sector's "
        "intermediate consumption of production products)",
        {"PROD": _c((+1, "IC_PPS")), "PS": _c((-1, "IC_PPS"))},
    ),
    Row(
        "wages",
        "§2.2 Table 1; §3.3.1 Eq. (58) (production module pays all wages, "
        "public and private, p. 17)",
        {"PROD": _c((-1, "W")), "HH": _c((+1, "W"))},
    ),
    Row(
        "indirect_taxes",
        "§2.2 Table 1; §3.4.3 Eq. (253): ITAX = ITAX_P + ITAX_PS",
        {
            "PROD": _c((-1, "ITAX_P")),
            "PS": _c((-1, "ITAX_PS")),
            "GVT": _c((+1, "ITAX_P"), (+1, "ITAX_PS")),
        },
    ),
    Row(
        "gross_operating_surplus",
        "§2.2 Table 1; §3.4.4 Eq. (159): GOS_P accrues to the NFC sector "
        "(PS retains GOS_PS inside its own column, §3.4.2 Eq. (76))",
        {"PROD": _c((-1, "GOS_P")), "NFC": _c((+1, "GOS_P"))},
    ),
    Row(
        "interest_paid_to_mfis",
        "§2.2 Table 1; §3.4.4 Eq. (209): INTR_MFI = INTP_NFC + INTP_PS + "
        "INTP_NMFI + INTP_GVT + INTP_HH",
        {
            "NFC": _c((-1, "INTP_NFC")),
            "PS": _c((-1, "INTP_PS")),
            "MFI": _c((+1, "INTR_MFI")),
            "NMFI": _c((-1, "INTP_NMFI")),
            "GVT": _c((-1, "INTP_GVT")),
            "HH": _c((-1, "INTP_HH")),
        },
    ),
    Row(
        "interest_received_from_mfis",
        "§2.2 Table 1; §3.4.4 Eq. (210): INTP_MFI = INTR_NFC + INTR_PS + "
        "INTR_NMFI + INTR_GVT + INTR_HH + INTN_ROW (RoW in net terms, "
        "§3.4.6 Eq. (381))",
        {
            "NFC": _c((+1, "INTR_NFC")),
            "PS": _c((+1, "INTR_PS")),
            "MFI": _c((-1, "INTP_MFI")),
            "NMFI": _c((+1, "INTR_NMFI")),
            "GVT": _c((+1, "INTR_GVT")),
            "HH": _c((+1, "INTR_HH")),
            "ROW": _c((+1, "INTN_ROW")),
        },
    ),
    Row(
        "dividends_paid_to_nmfis",
        "§2.2 Table 1; §3.4.4 Eq. (221) (DIVR_NMFI = DIVP_NFC + DIVP_PS; "
        "the Table 6 initial DIVR_NMFI additionally includes RoW's net "
        "dividend payment -DIVN_ROW of §3.4.6 Eq. (382), matching Table 1's "
        "RoW cell)",
        {
            "NFC": _c((-1, "DIVP_NFC")),
            "PS": _c((-1, "DIVP_PS")),
            "NMFI": _c((+1, "DIVR_NMFI")),
            "ROW": _c((+1, "DIVN_ROW")),
        },
    ),
    Row(
        "dividends_received_from_nmfis",
        "§2.2 Table 1; §3.4.2 Eq. (93), §3.4.5 Eq. (313); DIVP_NMFI "
        "(§3.4.4 Eq. (222)) is distributed to NFC, PS and HH",
        {
            "NFC": _c((+1, "DIVR_NFC")),
            "PS": _c((+1, "DIVR_PS")),
            "NMFI": _c((-1, "DIVP_NMFI")),
            "HH": _c((+1, "DIVR_HH")),
        },
    ),
    Row(
        "income_taxes",
        "§2.2 Table 1; §3.4.3 Eq. (260): INTAX = INTAX_NFC + INTAX_HH",
        {
            "NFC": _c((-1, "INTAX_NFC")),
            "GVT": _c((+1, "INTAX_NFC"), (+1, "INTAX_HH")),
            "HH": _c((-1, "INTAX_HH")),
        },
    ),
    Row(
        "social_contributions",
        "§2.2 Table 1; §3.4.5 Eq. (315): SOCC = SOCC_NMFI + SOCC_GVT",
        {
            "NMFI": _c((+1, "SOCC_NMFI")),
            "GVT": _c((+1, "SOCC_GVT")),
            "HH": _c((-1, "SOCC_NMFI"), (-1, "SOCC_GVT")),
        },
    ),
    Row(
        "social_benefits",
        "§2.2 Table 1; §3.4.5 Eq. (316): SOCB = SOCB_NMFI + SOCB_GVT",
        {
            "NMFI": _c((-1, "SOCB_NMFI")),
            "GVT": _c((-1, "SOCB_GVT")),
            "HH": _c((+1, "SOCB_NMFI"), (+1, "SOCB_GVT")),
        },
    ),
    Row(
        "other_income",
        "§2.2 Table 1 'Other Income' (OI, §2.1 p. 3: paid by NMFIs to "
        "households) = INSR + PENSR, the income payable on insurance and "
        "pension entitlements, §3.4.4 Eqs. (223)-(224)",
        {
            "NMFI": _c((-1, "INSR"), (-1, "PENSR")),
            "HH": _c((+1, "INSR"), (+1, "PENSR")),
        },
    ),
    Row(
        "pension_adjustment",
        "§2.2 Table 1; §3.4.4 Eq. (227): PENS_ADJ = SOCC_NMFI - SOCB_NMFI",
        {
            "NMFI": _c((-1, "PENS_ADJ")),
            "HH": _c((+1, "PENS_ADJ")),
        },
    ),
    Row(
        "residual_transaction",
        "§2.2 Table 1 (p. 5: residual transaction per sector); §3 Eqs. "
        "(175) NFC, (211) MFI (= minus the sum of all other DISCs, so the "
        "row sums to zero), (229) NMFI, (282) GVT, (335) HH, (384) RoW; "
        "the power sector has no residual transaction (Table 1)",
        {
            "NFC": _c((+1, "DISC_NFC")),
            "MFI": _c((+1, "DISC_MFI")),
            "NMFI": _c((+1, "DISC_NMFI")),
            "GVT": _c((+1, "DISC_GVT")),
            "HH": _c((+1, "DISC_HH")),
            "ROW": _c((+1, "DISC_ROW")),
        },
    ),
)

# Net-lending targets for the column identity (Table 1 bottom row):
# column sum (model flows + residual transaction) = LEND_sector,
# §3 Eqs. (176), (212), (230), (283), (336), (385); LEND_PS Eq. (106).
NET_LENDING: dict[str, str | None] = {
    "PROD": None,  # not a sector; sums to exactly zero (§3.3 fn. 14)
    "NFC": "LEND_NFC",
    "PS": "LEND_PS",
    "MFI": "LEND_MFI",
    "NMFI": "LEND_NMFI",
    "GVT": "LEND_GVT",
    "HH": "LEND_HH",
    "ROW": "LEND_ROW",
}

# ---------------------------------------------------------------------------
# Balance-sheet matrix — manual §2.2 Table 2 (p. 7).
# ---------------------------------------------------------------------------
BALANCE_SHEET_MATRIX: tuple[Row, ...] = (
    Row(
        "capital_firms",
        "§2.2 Table 2; §3.4.4 Eq. (200)",
        {"NFC": _c((+1, "K_NFC"))},
    ),
    Row(
        "capital_public",
        "§2.2 Table 2; §3.4.3 (government capital stock)",
        {"GVT": _c((+1, "K_GVT"))},
    ),
    Row(
        "capital_power",
        "§2.2 Table 2; §3.4.2 (K_PS as used in NW_PS, Eq. (134))",
        {"PS": _c((+1, "K_PS"))},
    ),
    Row(
        "housing",
        "§2.2 Table 2; §3.4.5 Eq. (366) (HVAL in NW_HH)",
        {"HH": _c((+1, "HVAL"))},
    ),
    Row(
        "interest_bearing_assets",
        "§2.2 Table 2; §3.4.4 Eq. (214): FL_MFI = IBA_NFC + IBA_PS + "
        "IBA_NMFI + IBA_GVT + IBA_HH + IBA_ROW (RoW net stock IBN_ROW, "
        "§3.4.6)",
        {
            "NFC": _c((+1, "IBA_NFC")),
            "PS": _c((+1, "IBA_PS")),
            "MFI": _c((-1, "FL_MFI")),
            "NMFI": _c((+1, "IBA_NMFI")),
            "GVT": _c((+1, "IBA_GVT")),
            "HH": _c((+1, "IBA_HH")),
            "ROW": _c((+1, "IBN_ROW")),
        },
    ),
    Row(
        "interest_bearing_liabilities",
        "§2.2 Table 2; §3.4.4 Eq. (213): FA_MFI = IBL_NFC + IBL_PS + "
        "IBL_NMFI + IBL_GVT_MFI + IBL_HH + IBL_ROW (=0 at the initial "
        "values); GVT bonds held outside MFIs appear as NMFI and RoW "
        "holdings (IBL_GVT_NMFI, IBL_GVT_ROW; §3.4.4 Eq. (247), §3.4.6 "
        "Eq. (394))",
        {
            "NFC": _c((-1, "IBL_NFC")),
            "PS": _c((-1, "IBL_PS")),
            "MFI": _c((+1, "FA_MFI")),
            "NMFI": _c((-1, "IBL_NMFI"), (+1, "IBL_GVT_NMFI")),
            "GVT": _c((-1, "IBL_GVT")),
            "HH": _c((-1, "IBL_HH")),
            "ROW": _c((+1, "IBL_GVT_ROW")),
        },
    ),
    Row(
        "equity_assets",
        "§2.2 Table 2; §3.4.4 Eq. (246): EQL_NMFI = EQA_HH + EQA_NFC + "
        "EQA_PS + EQN_ROW (NMFI is the counterpart to all equity assets)",
        {
            "NFC": _c((+1, "EQA_NFC")),
            "PS": _c((+1, "EQA_PS")),
            "NMFI": _c((-1, "EQL_NMFI")),
            "HH": _c((+1, "EQA_HH")),
            "ROW": _c((+1, "EQN_ROW")),
        },
    ),
    Row(
        "equity_liabilities",
        "§2.2 Table 2; Table 6 p. 65: EQA_NMFI is 'the sum of other "
        "sector equity liabilities' (= EQL_NFC + EQL_PS)",
        {
            "NFC": _c((-1, "EQL_NFC")),
            "PS": _c((-1, "EQL_PS")),
            "NMFI": _c((+1, "EQA_NMFI")),
        },
    ),
    Row(
        "pensions",
        "§2.2 Table 2; §3.4.4 Eq. (248), §3.4.5 Eq. (352): asset of HH, "
        "liability of NMFI",
        {"NMFI": _c((-1, "PENS")), "HH": _c((+1, "PENS"))},
    ),
    Row(
        "insurance",
        "§2.2 Table 2; §3.4.4 Eq. (248), §3.4.5 Eq. (352)",
        {"NMFI": _c((-1, "INS")), "HH": _c((+1, "INS"))},
    ),
    Row(
        "residual_instrument",
        "§2.2 Table 2 (p. 5: residual financial instrument per sector); "
        "§3 Eqs. (195) NFC, (125) PS, (216) MFI (= minus the sum of all "
        "other RES, so the row sums to zero), (250) NMFI, (301) GVT, "
        "(355) HH, (395) RoW",
        {
            "NFC": _c((+1, "RES_NFC")),
            "PS": _c((+1, "RES_PS")),
            "MFI": _c((+1, "RES_MFI")),
            "NMFI": _c((+1, "RES_NMFI")),
            "GVT": _c((+1, "RES_GVT")),
            "HH": _c((+1, "RES_HH")),
            "ROW": _c((+1, "RES_ROW")),
        },
    ),
)

# Column identity of Table 2: financial rows + residual instrument sum to the
# sector's financial net worth FNW_s (§3 Eqs. (196), (126), (217), (251),
# (302), (356), (396)); adding real assets gives total net worth NW_s
# (Eqs. (203), (134), (309), (366)). The production module has no column.
FINANCIAL_NET_WORTH: dict[str, str] = {
    "NFC": "FNW_NFC",
    "PS": "FNW_PS",
    "MFI": "FNW_MFI",
    "NMFI": "FNW_NMFI",
    "GVT": "FNW_GVT",
    "HH": "FNW_HH",
    "ROW": "FNW_ROW",
}

_REAL_ASSET_ROWS = ("capital_firms", "capital_public", "capital_power", "housing")


def transactions_residuals(state: Mapping[str, float]) -> dict[str, dict[str, float]]:
    """Residuals of the §2.2 Table 1 identities on ``state``.

    Returns ``{"rows": {...}, "columns": {...}}`` where each row residual is
    the sum of the flow across sectors (zero if the flow is fully accounted
    for) and each column residual is the sector's column sum (model flows
    plus its residual transaction) minus its net-lending position LEND_s
    (minus zero for the production module).
    """
    rows: dict[str, float] = {}
    columns: dict[str, float] = {s: 0.0 for s in SECTORS}
    for row in TRANSACTIONS_MATRIX:
        values = row.evaluate(state)
        rows[row.name] = sum(values.values())
        for sector, value in values.items():
            columns[sector] += value
    column_residuals = {
        sector: total - (state[NET_LENDING[sector]] if NET_LENDING[sector] else 0.0)
        for sector, total in columns.items()
    }
    return {"rows": rows, "columns": column_residuals}


def balance_sheet_residuals(state: Mapping[str, float]) -> dict[str, dict[str, float]]:
    """Residuals of the §2.2 Table 2 identities on ``state``.

    Returns row residuals (each financial instrument row must sum to zero),
    column residuals in two forms — ``columns_fnw`` (financial rows plus
    residual instrument minus FNW_s, §3 Eqs. (196) etc.) and ``columns_nw``
    (full column minus NW_s where the manual defines a total net worth) —
    and the economy-wide closure ``fnw_total`` (sum of FNW_s across sectors,
    zero by definition; Table 6 'FNW').
    """
    rows: dict[str, float] = {}
    fin_columns: dict[str, float] = {s: 0.0 for s in FINANCIAL_NET_WORTH}
    real_columns: dict[str, float] = {s: 0.0 for s in FINANCIAL_NET_WORTH}
    for row in BALANCE_SHEET_MATRIX:
        values = row.evaluate(state)
        if row.name in _REAL_ASSET_ROWS:
            for sector, value in values.items():
                real_columns[sector] += value
        else:
            rows[row.name] = sum(values.values())
            for sector, value in values.items():
                fin_columns[sector] += value
    columns_fnw = {
        sector: total - state[FINANCIAL_NET_WORTH[sector]]
        for sector, total in fin_columns.items()
    }
    # Total net worth NW_s is defined by the manual for NFC (Eq. (203)),
    # PS (Eq. (134)), GVT (Eq. (309)) and HH (Eq. (366)).
    nw_targets = {"NFC": "NW_NFC", "PS": "NW_PS", "GVT": "NW_GVT", "HH": "NW_HH"}
    columns_nw = {
        sector: fin_columns[sector] + real_columns[sector] - state[target]
        for sector, target in nw_targets.items()
    }
    fnw_total = sum(state[v] for v in FINANCIAL_NET_WORTH.values())
    return {
        "rows": rows,
        "columns_fnw": columns_fnw,
        "columns_nw": columns_nw,
        "totals": {"fnw_total": fnw_total},
    }
