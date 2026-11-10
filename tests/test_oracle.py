"""Oracle comparison: our implementation vs the pinned upstream run.

The upstream R code (unlicensed, fetched at a pinned commit by
``define_uk.upstream``) is used here strictly as a numerical oracle per
REIMPLEMENTATION.md.

What runs where
---------------
- ``test_registered_equations_reproduce_the_oracle`` is the comparison that
  can be made today. Each equation in our registry is evaluated on the
  oracle's OWN values for its inputs (state = quarter t, lag = quarter t-1)
  and must reproduce the oracle's value for its output, over every simulation
  quarter 2023Q1-2040Q4, in the baseline and in the policy scenarios. This
  checks each transcribed equation against the oracle one at a time. It does
  not solve our model, so it is not the milestone-2 gate.
- Every registered equation must be classified in exactly one of
  ``REPRODUCED``, ``ORACLE_FORMS``, ``DIVERGENT`` or ``NOT_EVALUABLE``.
  ``ORACLE_FORMS`` (2026-11-06) holds the equations where the oracle departs
  from the manual as printed, with the form its numbers do follow, found
  from the cached CSVs alone; the registry keeps the manual form.
- "Reproduces" means within the larger of TOL and the propagated
  4-significant-figure rounding of the equation's inputs (``_ratio``). A new equation that is
  not classified fails ``test_every_equation_is_classified``, so nothing can
  join the registry without being compared.
- The milestone-2 gate itself (solve our registry over the oracle horizon and
  compare the GDP path) is not written yet. It is a strict xfail, so it shows
  in every run as outstanding and turns red the moment it passes without the
  marker being removed. ``test_the_oracle_gate_cannot_pass_by_accident``
  keeps guarding the registry.

The cached-run tests skip in CI (the upstream is unlicensed, so CI never
fetches or runs it). The skip is keyed on the cached run, not on
``Rscript``: the comparison needs upstream outputs, and a cached run needs
no R.

Before 2026-11-06 the GDP-path test raised NotImplementedError wherever a
cache existed, so the local suite was red on every machine that could run
the oracle at all, and a real failure there would have been invisible.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest

from define_uk.model.calibration import PARAMETERS
from define_uk.model.sectors import build_registry, power
from define_uk.scenarios import _TABLES, _run_root

REFERENCE = json.loads(
    (Path(__file__).resolve().parents[1] / "validation"
     / "reference_outputs.json").read_text()
)
TOL = REFERENCE["oracle_identity_residuals"]["tolerance_rel"]
SIM_START = 144  # row of 2023Q1 in the 1987Q1-anchored files

# Oracle files the per-equation comparison runs on: the baseline, both
# green-investment designs, a regulation scenario and the combined policy.
ORACLE_FILES = (
    "gvt_investment/Variables_Baseline.csv",
    "gvt_investment/Variables_GPI + Green Bonds.csv",
    "gvt_investment/Variables_Green Power Subsidy.csv",
    "housing_regulation/Variables_Housing Regulation + Subsidy.csv",
    "mixed/mutual_trust/Variables_Both Regulations + Subsidies.csv",
)

# Equations that reproduce the oracle in every file above, to the CSVs'
# printing precision (see ``_ratio``).
REPRODUCED = {
    # §3.2 high-level macro, Eqs. (21)-(43). GCF, Eq. (23), only in the
    # scenarios without on-balance-sheet green public investment: see
    # ORACLE_FORMS below.
    "GDP", "CONS", "GO", "GDP_R", "CONS_R", "GCF_R", "GO_R", "g", "P",
    "EMP_PRI", "GDP_RFK", "GDP_RMAX", "re", "ru", "u", "nu", "EMP_PUB", "POP",
    # §3.3.1 production
    "F_P", "F_PR", "GO_PR", "GO_P", "COST_P", "UC", "W_PRI", "W_PUB", "W",
    "P_NELECT", "COST_NELEC", "COST_ER", "K_P", "K_PG", "K_PC", "K_PR",
    "K_PGR", "K_PCR", "WR_PRI", "WR_PUB", "P_NELEC", "P_FUEL", "delta_KP",
    # §3.3.2 power sector. GOS_PS, RP_PS and NW_PS joined on 2026-11-06:
    # they are differences of large, nearly equal printed terms, and their
    # round-1 "divergence" was the rounding of those terms (now inside the
    # propagated printing bound in every file, max 0.68 of it).
    "F_PS", "F_PSR", "GO_PSR", "GO_PS", "COST_PS", "beta_NFF", "AC_NFF",
    "AC_FF", "u_FF", "u_NFF", "u_PS", "GCF_PSR", "GCF_PSFF", "GCF_PSFFR",
    "LEND_PS", "IBLTR_PS", "MC_ELEC", "DIVP_PS", "IBATR_PS", "EQATR_PS",
    "FA_PS", "FL_PS", "K_PSR", "K_PS", "K_PSFF", "K_PSNFF", "LEV_PS",
    "GOS_PS", "RP_PS", "NW_PS",
    # §3.3.3 input-output block (2026-11-06, round 3). alpha_PP, Eq. (139),
    # only in the policy files: see ORACLE_FORMS.
    "alpha_PSP", "alpha_PSPS", "alpha_OPPS", "alpha_FUELPS", "alpha_PPS",
    "IC_PSPR", "IC_FUELPSR", "IC_OPPSR", "IC_PP", "IC_PSP", "IC_PSPS",
    "IC_PPS", "IC_FUELPS", "IC_OPPS", "det_IA", "L_PP", "L_PPS", "L_PSP",
    "L_PSPS",
    # §3.1 and §3.4.1-§3.4.7 (2026-11-06, round 4): reproduce within the
    # printing bound in all five comparison files.
    "E", "E_P", "E_H", "E_ELEC", "E_ELECMAX", "E_ELECFF", "E_ELECP",
    "E_ELECH", "E_NELEC", "E_NELECP", "E_NELECH", "EMIS", "EMIS_NELEC",
    "EMIS_ELEC", "epsilon", "omega_NELEC", "omega_ELEC", "YP_NFC",
    "INTR_NFC", "INTP_NFC", "YD_NFC", "DIVP_NFC", "RP_NFC", "GCF_NFC",
    "GCF_NFCG", "GCF_NFCC", "GCF_NFCR", "GCF_NFCGR", "GCF_NFCCR",
    "LENDM_NFC", "DISC_NFC", "LEND_NFC", "IBATR_NFC", "EQATR_NFC",
    "IBLTR_NFC", "RESTR_NFC", "OTIBA_NFC", "OTEQA_NFC", "OTIBL_NFC",
    "OTRES_NFC", "IBA_NFC", "EQA_NFC", "IBL_NFC", "EQL_NFC", "FA_NFC",
    "FL_NFC", "FNWM_NFC", "RES_NFC", "FNW_NFC", "K_NFCCR", "K_NFCGR",
    "K_NFCR", "K_NFC", "K_NFCC", "K_NFCG", "NW_NFC", "LEV_NFC", "ILLIQ_NFC",
    "DSR_NFC", "CR_NFC", "LENDM_MFI", "INTR_MFI", "INTP_MFI", "DISC_MFI",
    "LEND_MFI", "FA_MFI", "FL_MFI", "FNWM_MFI", "RES_MFI", "FNW_MFI",
    "YD_NMFI", "INTP_NMFI", "DIVP_NMFI", "PENSR", "INSR", "SOCC_NMFI",
    "SOCB_NMFI", "PENS_ADJ", "LENDM_NMFI", "DISC_NMFI", "LEND_NMFI",
    "IBATR_NMFI", "EQLTR_NMFI", "EQATR_NMFI", "RESTR_NMFI", "OTIBA_NMFI",
    "OTIBL_NMFI", "OTRES_NMFI", "OTEQA_NMFI", "OTPENS", "OTINS", "IBA_NMFI",
    "EQA_NMFI", "IBL_NMFI", "EQL_NMFI", "FL_NMFI", "FNWM_NMFI", "RES_NMFI",
    "FNW_NMFI", "YD_GVT", "ITAX", "ITAX_P", "ITAX_NELEC", "ITAXR_P",
    "ITAX_PS", "ITAXR_PS", "P_ETS", "INTAX", "INTAX_NFC", "INTAX_HH",
    "INTAXR_NFC", "INTAXR_HH", "INTR_GVT", "SOCC_GVT", "SOCCR_GVT",
    "CONS_GVT", "OCONS_GVT", "beta_gvt", "GCF_GVTG", "GCF_GVTC",
    "CONS_GVTR", "GCF_GVTR", "GCF_GVTGR", "GCF_GVTCR", "DISC_GVT",
    "LEND_GVT", "IBATR_GVT", "IBLTR_GVT_MFI", "IBLTR_GVT_NMFI",
    "IBLTR_GVT_ROW", "RESTR_GVT", "OTIBA_GVT", "OTIBL_GVT", "OTRES_GVT",
    "IBA_GVT", "IBL_GVT", "IBL_GVT_MFI", "IBL_GVT_NMFI", "IBL_GVT_ROW",
    "FA_GVT", "FNWM_GVT", "RES_GVT", "FNW_GVT", "K_GVTCR", "K_GVTGR",
    "K_GVTR", "K_GVT", "K_GVTC", "K_GVTG", "NW_GVT", "YP_HH", "INTR_HH",
    "INTP_HH", "YD_HH", "SOCC", "SOCB", "CONS_HH", "CONS_HHPR", "CONS_HHPS",
    "CONS_HHPSR", "SAV_HH", "GCF_HHHI", "GCF_HHR", "GCF_HHNBR",
    "GCF_HHHINR", "beta_GCFHH", "GCF_HHHIEER", "DISC_HH", "LEND_HH",
    "IBATR_HH", "EQATR_HH", "PENSTR", "INSTR_", "IBLTR_HH", "RESTR_HH",
    "OTIBA_HH", "OTIBL_HH", "OTRES_HH", "IBA_HH", "EQA_HH", "PENS", "INS",
    "IBL_HH", "FA_HH", "FL_HH", "FNWM_HH", "RES_HH", "FNW_HH", "H", "HB",
    "H_I", "H_EN", "H_EE", "HVAL", "PH", "NW_HH", "YP_ROW", "DY", "ROW_D",
    "IMP", "EXP", "ROW_DR", "IMP_R", "EXP_R", "ER", "PF", "PE", "PI",
    "IADJ", "REER", "INTN_ROW", "DIVN_ROW", "LENDM_ROW", "DISC_ROW",
    "LEND_ROW", "IBNTR_ROW", "EQNTR_ROW", "RESTR_ROW", "OTIBA_ROW",
    "OTEQN_ROW", "OTRES_ROW", "IBN_ROW", "EQN_ROW", "FNWM_ROW", "RES_ROW",
    "FNW_ROW", "r_BOEQ", "r_BOE", "r_IBA_NFC", "r_IBA_NFCLR", "r_IBA_PS",
    "r_IBA_NMFI", "r_IBA_NMFILR", "r_IBA_GVT", "r_IBA_GVTLR", "r_IBA_HH",
    "r_IBA_HHLR", "r_IBN_ROW", "r_IBN_ROWLR", "r_IBL_NFC", "r_IBL_NFCLR",
    "r_IBL_PS", "r_IBL_PSLR", "r_IBL_NMFI", "r_IBL_GVT", "r_IBL_HH",
    "r_IBL_HHLR",
}

ALL_FILES = frozenset(ORACLE_FILES)
_EQ23 = next(e for e in build_registry() if e.name == "GCF")
_SUBSIDY_FILES = ALL_FILES - {"gvt_investment/Variables_GPI + Green Bonds.csv"}
_BAN_FILE = "mixed/mutual_trust/Variables_Both Regulations + Subsidies.csv"
_BAN_FROM = 180  # 2032Q1: first quarter with zero desired fossil investment
_BASELINE_FILE = "gvt_investment/Variables_Baseline.csv"
# Eq. (139)'s alpha_PP in the run's Baseline files (all 7 print 0.2748 in
# every simulated quarter); every policy file prints Table 5's 0.2762.
ALPHA_PP_BASELINE_RUN = 0.2748

# Equations where the oracle departs from the manual as printed, with the
# form the oracle's numbers do follow. Our registry keeps the manual form
# (REIMPLEMENTATION.md: equations come from the manual only); each oracle
# form below was found from the cached CSVs alone (lag swaps and
# one-column / ratio searches over every printed variable, 2026-11-06) and
# is pinned by ``test_oracle_forms_explain_the_departures``: the manual form
# departs in exactly the listed files, the oracle form reproduces in all.
# value = (files where the manual form departs, what the oracle does, form)
ORACLE_FORMS = {
    "GCF": (
        {"gvt_investment/Variables_GPI + Green Bonds.csv"},
        "Eq. (23) as printed omits SPEND_GVTPS; the oracle adds it to GCF "
        "when green public investment is on the balance sheet.",
        lambda s, l, t, f: _EQ23.func(s, l) + s["SPEND_GVTPS"] - s["SUBS_PS"],
    ),
    # Power-sector subsidies. SUBS_PS is positive from 2027Q1 in every file
    # but GPI + Green Bonds, including the baseline (0.65 per quarter).
    "YD_PS": (
        _SUBSIDY_FILES,
        "Eq. (92) has no subsidy term; the oracle adds SUBS_PS to the power "
        "sector's disposable income (Eq. (136) does count it as an inflow).",
        lambda s, l, t, f: s["GOS_PS"] + s["INTR_PS"] - s["INTP_PS"] + s["SUBS_PS"],
    ),
    "GCF_PS": (
        _SUBSIDY_FILES,
        "Eq. (102): the oracle's total power investment is GCF_PSNFF + "
        "GCF_PSFF + SUBS_PS (the subsidy is spent on capital).",
        lambda s, l, t, f: s["GCF_PSNFF"] + s["GCF_PSFF"] + s["SUBS_PS"],
    ),
    "GCF_PSNFF": (
        _SUBSIDY_FILES,
        "Eq. (101): the oracle's privately financed non-fossil investment "
        "is (1 - CR_PS)(GCF_PSNFFD - 0.5 SUBS_PS): each pound of subsidy "
        "displaces half a pound of desired private investment. The 0.5 is "
        "not in the manual.",
        lambda s, l, t, f: (1.0 - s["CR_PS"]) * (s["GCF_PSNFFD"] - 0.5 * s["SUBS_PS"]),
    ),
    "GCF_PSNFFR": (
        _SUBSIDY_FILES,
        "Eq. (105): the oracle's real non-fossil investment includes the "
        "subsidy, (GCF_PSNFF + SUBS_PS)/P_P, so the subsidy builds capacity.",
        lambda s, l, t, f: (s["GCF_PSNFF"] + s["SUBS_PS"]) / s["P_P"],
    ),
    # Fossil-fuel ban. Eqs. (97)-(98) have no ban branch (the ban enters
    # the manual only through expectations, Eq. (88)).
    "GCF_PSFFD": (
        {_BAN_FILE},
        "Eq. (97): under the ban the oracle sets desired fossil investment "
        "to zero from 2032Q1.",
        lambda s, l, t, f: 0.0 if f == _BAN_FILE and t >= _BAN_FROM
        else (1.0 - s["prop_NFF"]) * s["GCF_PSD"],
    ),
    "GCF_PSNFFD": (
        {_BAN_FILE},
        "Eq. (98): under the ban all desired investment goes to non-fossil "
        "from 2032Q1.",
        lambda s, l, t, f: s["GCF_PSD"] if f == _BAN_FILE and t >= _BAN_FROM
        else s["prop_NFF"] * s["GCF_PSD"],
    ),
    # Every file: the printed equation and the oracle differ outright.
    "MC_FF": (
        ALL_FILES,
        "Timing. Eq. (82) divides by E_ELECFF at t; the oracle divides by "
        "E_ELECFF at t-1 (reproduces to 5e-4 in the five comparison "
        "files; not checked in the ban solves, where the price regime "
        "changes).",
        lambda s, l, t, f: (s["IC_FUELPS"] + s["COV_ETSPS"] * s["P_ETS"]
                         * s["EMIS_ELEC"]) / l["E_ELECFF"],
    ),
    "P_ELEC": (
        ALL_FILES,
        "Eq. (84) prints (1 + MU_ELEC) MC_ELEC; the oracle prices at "
        "MU_ELEC MC_ELEC with the same Table 5 MU_ELEC = 1.228, i.e. MU_ELEC "
        "is used as a gross mark-up factor. As printed, the price is 81% "
        "higher. The oracle's P_ELEC equals its P_ELECLR (the long-run rule "
        "§5 calibrates and §3 never prints) in every quarter of the five "
        "comparison files, none of which reaches E_ELECMAX. In the ban "
        "solves generation hits capacity and the price leaves this rule "
        "(footnote 22's average-cost regime; see scenarios.SFC_TOLERANCE).",
        lambda s, l, t, f: power._MU_ELEC * s["MC_ELEC"],
    ),
    "RESTR_PS": (
        ALL_FILES,
        "Eq. (111) prints eta_PSB GDP_{t-1}; with the same Table 5 eta_PSB "
        "the oracle uses eta_PSB GO_PS (the power sector's own gross "
        "output). As printed the flow is about 22x the oracle's.",
        lambda s, l, t, f: power._ETA_PSB * s["GO_PS"],
    ),
    "EQLTR_PS": (
        ALL_FILES,
        "Eq. (109) prints a constant share theta_psb of EQATR_NMFI; the "
        "oracle's share is GO_PS/GO, the power sector's share of gross "
        "output, which moves with the scenario.",
        lambda s, l, t, f: s["GO_PS"] / s["GO"] * s["EQATR_NMFI"],
    ),
    "theta_P": (
        ALL_FILES,
        "Eq. (18) prints e^{-kappa3 KPG/KPC}, which gives theta_P < 0 "
        "(-0.23 at Table 6, tabulated 0.171); the oracle uses e^{+kappa3 ...}.",
        lambda s, l, t, f: 1.0 - (1.0 + PARAMETERS["pi3"]) / (
            1.0 + PARAMETERS["pi3"] * math.exp(PARAMETERS["kappa3"]
                                               * l["K_PG"] / l["K_PC"])),
    ),
    # Dividend closure (round 4): see empirical.py.
    "DIVR_NFC": (
        ALL_FILES,
        "Eq. (163): the oracle's DIVR_NFC is the residual DIVP_NMFI - "
        "DIVR_HH - DIVR_PS (beta_dnfc is not in Table 5).",
        lambda s, l, t, f: s["DIVP_NMFI"] - s["DIVR_HH"] - s["DIVR_PS"],
    ),
    "DIVR_HH": (
        ALL_FILES,
        "Eq. (313) divides by EQL_NMFI; the oracle by EQL_NMFI - EQN_RoW.",
        lambda s, l, t, f: PARAMETERS["beta_dhh"] * s["EQA_HH"]
        / (s["EQL_NMFI"] - s["EQN_ROW"]) * s["DIVP_NMFI"],
    ),
    "DIVR_NMFI": (
        ALL_FILES,
        "Eq. (221) omits the RoW; the oracle's NMFIs pay its net dividends.",
        lambda s, l, t, f: s["DIVP_NFC"] + s["DIVP_PS"] - s["DIVN_ROW"],
    ),
    "DIVR_PS": (
        ALL_FILES,
        "Eq. (93) divides by EQL_NMFI; the oracle divides by EQL_NMFI - "
        "EQN_RoW (NMFI equity net of the rest of the world's net holding).",
        lambda s, l, t, f: power._BETA_DPS * s["EQA_PS"]
        / (s["EQL_NMFI"] - s["EQN_RoW"]) * s["DIVP_NMFI"],
    ),
}

# Not a form but a coefficient: Eq. (139) sets alpha_PP to Table 5's
# alpha_PPLR = 0.2762, which every policy file prints, while all seven
# Baseline files print 0.2748 from 2023Q1. Policy-minus-baseline deltas
# therefore also carry a 0.5% change in production's own-input coefficient.
ORACLE_FORMS["alpha_PP"] = (
    {_BASELINE_FILE},
    "Eq. (139): the run's Baseline files use alpha_PP = 0.2748, not Table "
    "5's alpha_PPLR = 0.2762 (which every policy file uses).",
    lambda s, l, t, f: ALPHA_PP_BASELINE_RUN if f == _BASELINE_FILE else 0.2762,
)

# Still diverge in at least one file, and the oracle form is not known.
# value = why
DIVERGENT = {
    "prop_NFF": "Eq. (99): alpha_0bNFF, alpha_1bNFF are not in Table 5 "
                "(power.MANUAL_GAPS, defaulted to 0, so prop_NFF = 0.5); the "
                "oracle's prop_NFF runs 0.90-1.00.",
    "CR_PS": "Eq. (138): alpha_1-3CRPS are not in Table 5 (power.MANUAL_GAPS, "
             "defaulted to 0); the oracle's CR_PS runs 0.06-0.59.",
    "DEF_PS": "Eq. (117) reproduces in the baseline-like files (within 2.2x "
              "the printing bound, which an exponential of a printed lag can "
              "reach) but misses by up to 35x in GPI + Green Bonds and 10x in "
              "the mixed policy, at the 2030 illiquidity spike (oracle 0.0170 "
              "vs 0.0234 in 2030Q3). Not diagnosed.",
}

# Output or an input is not a column of the oracle CSVs, so the equation
# cannot be compared one at a time (only through a full solve).
NOT_EVALUABLE = {
    "lam", "EMP", "GDP_RFE", "LF", "P_P", "mu", "WS", "WR", "Eu_PS", "Fu_PS",
    "COST_PSNFF", "COST_PSFF", "INTR_PS", "INTP_PS", "GCF_PSD", "OTIBA_PS",
    "OTEQA_PS", "OTEQL_PS", "OTIBL_PS", "OTRES_PS", "delta_KPS", "IBA_PS",
    "IBL_PS", "EQA_PS", "EQL_PS", "FNWM_PS", "RES_PS", "FNW_PS", "K_PSFFR",
    "K_PSNFFR", "ILLIQ_PS", "DSR_PS",
}


# §3.1 / §3.4 (2026-11-06, round 4). Forms not diagnosed unless stated.
_GPI = "only in GPI + Green Bonds: the green-bond gilt stock IBL_GVTNMFIG " \
       "(and its rate r_IBLGVTNMFIG, OT_IBLGVTNMFIG) has no manual equation"
_HOUSING = "only in the two housing-subsidy files: the retrofit subsidy " \
           "(SUBS_HH, lower C_HIENR/C_HIEER) is a policy instrument the " \
           "manual's Eqs. (325), (331)-(334), (362)-(363) do not print"
DIVERGENT.update({
    "E_ELECNFF": "Eq. (6): only in GPI + Green Bonds, the one file with "
                 "government non-fossil capacity K_GVTNFFR > 0. Eq. (5) "
                 "counts it in capacity; Eq. (6)'s cap prints only "
                 "CF_NFF K_PSNFFR.",
    "CF_NFF": "Eq. (17): matches at 2023 (0.4%) but drifts to 0.5 (CF_min) "
              "while the oracle floors at 0.6; median miss 12%.",
    "GCF_NFCD": "Eq. (166): 3% at 2023Q1, 0.4% median.",
    "beta_nfc": "Eq. (168): within 0.5%, 2x the printing bound.",
    "EQLTR_NFC": "Eq. (179): (1 - theta_psb) EQATR_NMFI is ~2% low "
                 "throughout; the oracle's PS share is GO_PS/GO "
                 "(ORACLE_FORMS EQLTR_PS), so the NFC share is 1 - GO_PS/GO.",
    "OTEQL_NFC": "Eq. (184): as printed DIVP_NFC/(r_IBL_GVT + beta_EQLNFC) - "
                 "EQL_NFC_{t-1} is -1460 against +5; the equity-valuation "
                 "form differs (cf. power-sector Eq. (113)).",
    "DEF_NFC": "Eq. (186): within 1.5% (exponential of a printed lag).",
    "INTR_NMFI": _GPI, "IBLTR_NMFI": _GPI, "FA_NMFI": _GPI,
    "INTP_GVT": _GPI, "IBLTR_GVT": _GPI, "FL_GVT": _GPI,
    "OTEQL_NMFI": "Eq. (240): same equity-valuation form gap as Eq. (184); "
                  "the oracle prints 0 in some quarters.",
    "SOCB_GVT": "Eq. (269): 3.3% low in every quarter (constant level gap).",
    "CONS_HHP": "Eq. (318): 2% median, 4% max one-step miss. epsilon_CHHP is "
                "not tabulated (households.MANUAL_GAPS, alpha3_CHHP read).",
    "GCF_HHNB": "Eq. (324): 1% at 2023Q1, 0.3% median.",
    "OTEQA_HH": "Eq. (344): the oracle prints OT_EQAHH = 0 in some quarters "
                "where delta_EQAHH EQA_HH is not 0.",
    "GCF_HH": _HOUSING, "GCF_HHHIR": _HOUSING, "GCF_HHHIER": _HOUSING,
    "GCF_HHHIENR": _HOUSING, "LENDM_HH": _HOUSING, "CHI_ENR": _HOUSING,
    "CHI_EER": _HOUSING,
    "r_IBA_PSLR": "Eq. (399): spr_psa and minr_ps are not in Table 5 "
                  "(returns.MANUAL_GAPS); held at its lag.",
    "r_IBL_NMFILR": "Eq. (401): the undefined delta_jt (returns.MANUAL_GAPS) "
                    "read as delta_IBLNMFI misses by 30%.",
    "r_IBL_GVTLR": "Eq. (401): delta_jt read as delta_IBLGVT misses by 10%.",
})
NOT_EVALUABLE |= {
    # Inputs the CSVs do not print: GCF_GVTBASE (Eq. (272)), GCF_GVTNFFR
    # (Eq. (276)), SUBS_GVT (Eq. (281)).
    "GCF_GVT", "K_GVTNFFR", "LENDM_GVT",
}


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


def _load(rel: str) -> list[dict[str, float]]:
    path = _run_root() / _TABLES / rel
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    data = [
        {k: (float(v) if v not in ("", "NA") else math.nan)
         for k, v in r.items() if k}
        for r in rows
    ]
    # §3.1/§3.4 equations use the manual §5 Table 6 spelling; add it beside
    # the CSV spelling (scenario.CSV_ALIASES), plus the two-quarter lags and
    # world nominal demand (Eq. (369)) the CSVs do not print.
    from define_uk.model.scenario import CSV_ALIASES
    for t, r in enumerate(data):
        for csv_name, name in CSV_ALIASES.items():
            if csv_name in r and name not in r:
                r[name] = r[csv_name]
        if t > 1:
            for name in ("K_NFC", "GCF_HHNB"):
                r[f"{name}_LAG"] = data[t - 2][name]
        if "ROW_DR" in r and "PF" in r:
            r.setdefault("ROW_D", r["ROW_DR"] * r["PF"])
        r.setdefault("t_PS", float(t))
    return data


# Each CSV value is printed to 4 significant figures, so it carries a
# relative rounding error of up to 5e-4.
_PRINT_REL = 5e-4


class _Recorder(dict):
    """A state dict that records which keys an equation reads."""

    def __init__(self, data, seen, tag):
        super().__init__(data)
        self._seen, self._tag = seen, tag

    def __getitem__(self, key):
        self._seen.add((self._tag, key))
        return dict.__getitem__(self, key)


def _ratio(func, name, data, t, rel) -> float:
    """|model - oracle| at quarter t over what printing alone can explain.

    The allowance is the larger of TOL (relative) and the first-order
    propagation of the 4-significant-figure rounding of every input the
    equation reads, plus that of the output. Before 2026-11-06 only the TOL
    test was applied, which flagged identities such as GOS_PS = GO_PS -
    COST_PS (a small difference of two large printed numbers) as divergent
    when the gap was rounding. A ratio <= 1 reproduces. Raises ValueError
    where the manual defines no value (power.MANUAL_GAPS).
    """
    cur, lag = data[t], data[t - 1]
    seen: set = set()
    model = func(_Recorder(cur, seen, "s"), _Recorder(lag, seen, "l"), t, rel)
    oracle = cur[name]
    if math.isnan(oracle) or math.isnan(model):
        return 0.0
    bound = _PRINT_REL * abs(oracle)
    for tag, key in seen:
        src = cur if tag == "s" else lag
        x = src.get(key)
        if not isinstance(x, float) or x == 0.0 or math.isnan(x):
            continue
        bumped = {**src, key: x * (1.0 + _PRINT_REL)}
        moved = (func(bumped, lag, t, rel) if tag == "s"
                 else func(cur, bumped, t, rel))
        bound += abs(moved - model)
    allowed = max(TOL * max(abs(oracle), 1e-6), bound)
    return abs(model - oracle) / allowed


def _manual(eq):
    return lambda s, l, t, f: eq.func(s, l)


def _max_ratio(func, name, data, rel="") -> float:
    worst = 0.0
    for t in range(SIM_START, len(data)):
        try:
            worst = max(worst, _ratio(func, name, data, t, rel))
        except (ValueError, ZeroDivisionError):
            # A documented manual gap (e.g. Eq. (85) at zero fossil
            # capacity, power.MANUAL_GAPS): the manual defines no value.
            continue
    return worst


def _max_residual(eq, data) -> float:
    return _max_ratio(_manual(eq), eq.name, data)


def test_every_equation_is_classified():
    """Hermetic: runs in CI. Every registered equation sits in one class."""
    names = set(build_registry().names())
    classes = [REPRODUCED, set(ORACLE_FORMS), set(DIVERGENT), NOT_EVALUABLE]
    union = set().union(*classes)
    assert names - union == set(), "unclassified equations"
    assert union - names == set(), "classified names not in the registry"
    assert sum(len(c) for c in classes) == len(union), "a name is in two classes"


@requires_cached_run
@pytest.mark.parametrize("rel", ORACLE_FILES)
def test_registered_equations_reproduce_the_oracle(rel):
    data = _load(rel)
    by_name = {eq.name: eq for eq in build_registry()}
    expected = set(REPRODUCED) | {
        n for n, (bad, _, _) in ORACLE_FORMS.items() if rel not in bad
    }
    failures = {
        n: _max_residual(by_name[n], data) for n in sorted(expected)
    }
    failures = {n: r for n, r in failures.items() if r > 1.0}
    assert failures == {}, f"{rel}: residual above the printing allowance"


@requires_cached_run
@pytest.mark.parametrize("rel", ORACLE_FILES)
def test_oracle_forms_explain_the_departures(rel):
    """The manual form departs in exactly the listed files; the oracle form
    reproduces in every file. Pins each diagnosis both ways."""
    data = _load(rel)
    by_name = {eq.name: eq for eq in build_registry()}
    departs = {
        n for n in ORACLE_FORMS if _max_residual(by_name[n], data) > 1.0
    }
    assert departs == {n for n, (bad, _, _) in ORACLE_FORMS.items() if rel in bad}
    unexplained = {
        n: r for n, (_, _, form) in ORACLE_FORMS.items()
        if (r := _max_ratio(form, n, data, rel)) > 1.0
    }
    assert unexplained == {}, f"{rel}: oracle form does not reproduce"


@requires_cached_run
def test_gcf_divergence_is_exactly_the_public_green_investment():
    data = _load("gvt_investment/Variables_GPI + Green Bonds.csv")
    eq = next(e for e in build_registry() if e.name == "GCF")
    assert _max_residual(eq, data) > 1.0  # the divergence is real
    worst = max(
        abs(data[t]["GCF"] - eq.func(data[t], data[t - 1])
            - data[t]["SPEND_GVTPS"]) / abs(data[t]["GCF"])
        for t in range(SIM_START, len(data))
    )
    assert worst < TOL


@requires_cached_run
def test_divergent_equations_still_diverge():
    """If one of these starts to reproduce, move it to REPRODUCED."""
    by_name = {eq.name: eq for eq in build_registry()}
    files = [_load(rel) for rel in ORACLE_FILES]
    still = {
        n for n in DIVERGENT
        if any(_max_residual(by_name[n], d) > 1.0 for d in files)
    }
    assert still == set(DIVERGENT)


@requires_cached_run
@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="milestone 2: with §3.1/§3.4 held at the oracle, solved GDP is "
    "within 0.6% but not within printing precision (price level 1.2% off "
    "from 2023Q1; power-sector investment misses without alpha_0GCFPS)",
)
def test_baseline_gdp_path_matches_oracle():
    """The milestone-2 gate, now a real solve (2026-11-06, round 3):
    ``define_uk.model.scenario.solve_path`` over 2023Q1-2040Q4 on the S1
    baseline, empirical forms, Baseline-run alpha_PP, compared within TOL."""
    from define_uk.model.scenario import load_reference, scenario_inputs, solve_path
    ref = scenario_inputs(load_reference(_run_root() / _TABLES / _BASELINE_FILE))
    path = solve_path(build_registry("empirical"), ref,
                      overrides={"alpha_PP": ALPHA_PP_BASELINE_RUN})
    worst = max(abs(path[t]["GDP"] / ref[t]["GDP"] - 1)
                for t in range(SIM_START, len(ref)))
    assert worst < TOL
