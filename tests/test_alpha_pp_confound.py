"""The Baseline/policy alpha_PP mismatch: what the cached run itself shows.

Every Baseline file of the pinned run uses alpha_PPLR = 0.2748; every policy
file uses Table 5's 0.2762. It is the only parameter outside the published
policy switches that differs (``Parameters-sorted_*.csv``), and the printed
gap (0.0014) is 28 times the CSV's half-unit of rounding (0.00005), so it is
not a print artefact. No policy switch acts before 2027Q1: all 16 distinct
policy files are identical through 2026Q4. The 2023Q1-2026Q4 policy-minus-
baseline deltas are therefore the alpha_PP effect alone, and the same
effect sits unobserved inside every later delta. Evidence and the size of
the bias per published number: issue "Published deltas carry an alpha_PP
change" and VALIDATION.md (2026-11-06, round 5).

Reads cached CSVs only; skips in CI like test_oracle.py.
"""
from __future__ import annotations

import csv
import itertools

import pytest
from test_oracle import requires_cached_run

POLICY_START = 160  # 2027Q1 (row 0 = 1987Q1)
SIM_START = 144     # 2023Q1


def _tables():
    from define_uk.scenarios import _TABLES, _run_root
    return _run_root() / _TABLES


def _params(path):
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))
    return dict(zip((h.strip() for h in rows[0][1:]), rows[1][1:]))


def _rows(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def _policy_files():
    return sorted(p for p in _tables().rglob("Variables_*.csv")
                  if p.name != "Variables_Baseline.csv")


@requires_cached_run
def test_alpha_pplr_is_the_only_non_switch_parameter_that_differs():
    files = sorted(_tables().rglob("Parameters-sorted_*.csv"))
    assert len(files) == 30
    params = {f: _params(f) for f in files}
    base = {f: p for f, p in params.items() if f.name.endswith("_Baseline.csv")}
    pol = {f: p for f, p in params.items() if f not in base}
    assert {p["alpha_PPLR"] for p in base.values()} == {"0.2748"}
    assert {p["alpha_PPLR"] for p in pol.values()} == {"0.2762"}
    # Every other parameter that varies is a policy switch, never set away
    # from the Baseline value in a Baseline file.
    varying = {k for k in next(iter(params.values()))
               if len({p[k] for p in params.values()}) > 1}
    switches = varying - {"alpha_PPLR"}
    assert all(len({p[k] for p in base.values()}) == 1 for k in switches)
    assert abs(0.2762 - 0.2748) / 0.00005 > 20  # far beyond print rounding


@requires_cached_run
def test_no_policy_acts_before_2027q1():
    """All policy files are identical, every column, through 2026Q4."""
    files = _policy_files()
    data = {f: _rows(f) for f in files}
    first = {}
    for a, b in itertools.combinations(files, 2):
        for t in range(len(data[a])):
            if data[a][t] != data[b][t]:
                first[(a, b)] = t
                break
    assert min(first.values()) == POLICY_START


@requires_cached_run
def test_2023_26_deltas_are_the_alpha_pp_effect_alone():
    """So the pinned GPI 2026 real-GDP delta (-1.125, test_scenarios.py) is
    no policy effect: every scenario carries the same number."""
    base = _rows(_tables() / "gvt_investment" / "Variables_Baseline.csv")
    for f in _policy_files():
        s = _rows(f)
        d = [float(s[t]["GDP_R"]) - float(base[t]["GDP_R"])
             for t in range(POLICY_START - 4, POLICY_START)]
        assert sum(d) / 4 == pytest.approx(-1.125, abs=1e-9), f.name
    # Nonzero from the first simulated quarter, before any switch acts.
    s = _rows(_tables() / "gvt_investment" / "Variables_GPI + Green Bonds.csv")
    assert float(s[SIM_START]["GDP_R"]) - float(base[SIM_START]["GDP_R"]) == pytest.approx(3.1)
    # Mark-up calibrated on the last data row already differs (0.176 vs 0.1704).
    assert float(s[SIM_START - 1]["MU"]) - float(base[SIM_START - 1]["MU"]) == pytest.approx(-0.0056)


@requires_cached_run
def test_alpha_pp_range_for_both_multiplier_definitions():
    """The policy-only range each GPI multiplier carries in its caveat.
    After 2026 the alpha_PP effect is unobserved; extrapolate it as zero,
    as its 2026Q4 level, or as its 2026Q4 share of baseline, in numerator
    and denominator alike. Headline (SPEND_GVTPS, issue #16): 2.08-2.25,
    where 2.25, the "zero" case, is the headline itself since 2026-11-18
    (measured from the policy start; 2.30 over the full simulation).
    Secondary (SPEND_GVT): 1.73-1.75, top = the secondary 1.75 (1.78 over
    the full simulation) (round 5)."""
    gv = _tables() / "gvt_investment"
    b = _rows(gv / "Variables_Baseline.csv")
    s = _rows(gv / "Variables_GPI + Green Bonds.csv")
    n = len(b)

    def d(v, t):
        return float(s[t][v]) - float(b[t][v])

    def adjusted(den):
        g = sum(d("GDP", t) for t in range(SIM_START, n))
        x = sum(d(den, t) for t in range(SIM_START, n))
        pg = sum(d("GDP", t) for t in range(SIM_START, POLICY_START))
        px = sum(d(den, t) for t in range(SIM_START, POLICY_START))
        q = POLICY_START - 1
        sg = d("GDP", q) / float(b[q]["GDP"])
        # SPEND_GVTPS is zero in the 2026Q4 Baseline (its delta is zero too).
        sx = d(den, q) / float(b[q][den]) if float(b[q][den]) else 0.0
        return [
            (g - pg) / (x - px),
            (g - pg - d("GDP", q) * (n - POLICY_START))
            / (x - px - d(den, q) * (n - POLICY_START)),
            (g - pg - sum(sg * float(b[t]["GDP"]) for t in range(POLICY_START, n)))
            / (x - px - sum(sx * float(b[t][den]) for t in range(POLICY_START, n))),
        ]

    head, sec = adjusted("SPEND_GVTPS"), adjusted("SPEND_GVT")
    assert (round(min(head), 2), round(max(head), 2)) == (2.08, 2.25)
    assert (round(min(sec), 2), round(max(sec), 2)) == (1.73, 1.75)
    # The top of each range is the "zero after 2026" case, which is what
    # measuring from the policy start computes: the published headline and
    # secondary.
    from define_uk import validation

    m = validation.gpi_multiplier()
    assert round(head[0], 2) == m["multiplier"] == 2.25
    assert round(sec[0], 2) == m["secondary"]["multiplier"] == 1.75


# --- The gate run_scenario applies (issue #20) -------------------------------
# The mismatch is in the upstream run's own parameter files, so nothing here
# can remove it; these tests pin what the package does about it.

@requires_cached_run
def test_policy_levers_are_exactly_the_other_parameters_that_vary():
    """POLICY_LEVERS is not a permissive list: it is every parameter that
    varies across the 30 cached parameter files, less alpha_PPLR."""
    from define_uk.scenarios import KNOWN_PARAMETER_MISMATCHES, POLICY_LEVERS

    params = [_params(f) for f in sorted(_tables().rglob("Parameters-sorted_*.csv"))]
    varying = {k for k in params[0] if len({p[k] for p in params}) > 1}
    assert varying - set(KNOWN_PARAMETER_MISMATCHES) == POLICY_LEVERS
    assert all(set(p) == set(params[0]) for p in params)


@requires_cached_run
def test_every_registered_scenario_differs_from_its_baseline_only_in_levers_and_alpha_pplr():
    from define_uk import scenarios as sc

    for name, _, folder, label, _ in sc._REGISTRY:
        d = _tables() / folder
        c = sc.parameter_check(d / f"Parameters-sorted_{label}.csv",
                               d / "Parameters-sorted_Baseline.csv")
        assert c["checked"] and c["passed"] and c["undocumented"] == [], name
        assert c["non_lever"] == {
            "alpha_PPLR": {"baseline": "0.2748", "scenario": "0.2762"}}, name
        assert set(c["levers"]) <= sc.POLICY_LEVERS, name


@requires_cached_run
def test_served_results_carry_the_computed_check():
    from define_uk import scenarios as sc

    r = sc.run_scenario("green_public_investment")
    assert r["parameter_check"]["shared_except_levers"] is False
    assert set(r["parameter_check"]["levers"]) == {
        "CO_NFF", "CRED", "GREEN_BONDS", "GREEN_POWER", "GVT_CRED",
        "GVT_INVEST", "sh_rGVTNMFIG"}
    m = r["baseline_parameter_mismatch"]
    assert (m["baseline_files"], m["policy_files"]) == (0.2748, 0.2762)


@requires_cached_run
@pytest.mark.xfail(strict=True, reason="issue #20: the pinned upstream run's "
                   "Baseline files use alpha_PPLR = 0.2748, its policy files "
                   "0.2762. Passes only against a matched Baseline, which "
                   "needs an upstream re-run")
def test_baseline_and_policy_share_every_parameter_except_the_levers():
    """The property a scenario-minus-baseline delta needs to be a policy
    effect. Strict xfail: when a cache with a matched Baseline is pinned this
    passes, the xfail turns red, and the issue #20 caveats and ranges must
    be withdrawn in the same change."""
    from define_uk import scenarios as sc

    for name, _, folder, label, _ in sc._REGISTRY:
        d = _tables() / folder
        c = sc.parameter_check(d / f"Parameters-sorted_{label}.csv",
                               d / "Parameters-sorted_Baseline.csv")
        assert c["shared_except_levers"], (name, c["non_lever"])


# --- What happens to the alpha_PP effect after 2026? -------------------------

@requires_cached_run
def test_clean_room_alpha_pp_counterfactual_persists_after_2026():
    """The cached run cannot show the alpha_PP effect after 2026Q4 (it is
    mixed with the policies). The clean-room model can be solved twice on
    the Baseline's inputs, with alpha_PP = 0.2748 and 0.2762 and nothing
    else changed. Diagnostic only: its baseline is within 3.7% of the
    oracle on GDP, not 1% (issue #17), so two closures are run: every
    equation solved, and the nine undiagnosed ones held at the oracle.

    Real GDP: in 2026 the clean-room effect is -1.16 / -0.91 a quarter
    against the cached run's -1.125, and it does not fade: -1.30 / -1.21 in
    2040Q4. Summed over 2027-2040 it is -77 / -58, the size of the
    "constant share of baseline" extrapolation (-74). So "the effect stops
    in 2027", the assumption behind the top of every published range (2.25
    for the multiplier, +252 for cumulative real GDP), is the case this
    evidence does not support; the policy-only cumulative real GDP effect
    of green public investment is nearer +310 to +330 than +252.

    What it does not reproduce is the transition. The cached run opens
    with real GDP +3.1 and the price level -0.7% in 2023Q1 (its mark-up on
    the last data quarter differs too, 0.176 against 0.1704) and reaches
    the negative level only in 2024Q4; the clean-room starts at zero and
    builds. By 2025-26 the two agree on real GDP, the price level (+0.2%)
    and the unemployment rate (+0.04pp). The support is for the level the
    effect settles at, not for its path.

    Nominal GDP: the clean-room effect in 2026 is 2 to 4 times the cached
    run's (+0.52 / +1.03 against +0.25) and rises where the cached run's
    falls (+0.8 to +0.2 over 2025-26), and the two closures disagree by
    60% on its 2027-2040 sum. It is not validated, so it does not size the
    multiplier, a ratio of nominal sums. It does show that the published
    2.08-2.25 range is not a bound: that range holds the nominal effect at
    its small 2026 level or share, and a price effect that builds, as here,
    would put the policy-only multiplier well below 2.08. Measured
    2026-11-24.
    """
    from define_uk.model.scenario import load_reference, scenario_inputs, solve_path
    from define_uk.model.sectors import build_registry
    from test_full_model import UNDIAGNOSED

    gv = _tables() / "gvt_investment"
    base = scenario_inputs(load_reference(gv / "Variables_Baseline.csv"))
    gpi = scenario_inputs(load_reference(gv / "Variables_GPI + Green Bonds.csv"))
    y2026 = range(POLICY_START - 4, POLICY_START)
    policy = range(POLICY_START, len(base))
    d_gdp = sum(gpi[t]["GDP"] - base[t]["GDP"] for t in policy)
    d_spend = sum(gpi[t]["SPEND_GVTPS"] - base[t]["SPEND_GVTPS"] for t in policy)
    assert d_gdp / d_spend == pytest.approx(2.248, abs=1e-3)
    assert sum(gpi[t]["GDP_R"] - base[t]["GDP_R"] for t in policy) == pytest.approx(252.2)

    def oracle(v):
        return sum(gpi[t][v] - base[t][v] for t in y2026) / 4

    assert oracle("GDP_R") == pytest.approx(-1.125) and oracle("GDP") == pytest.approx(0.25)

    want = {  # hold: (real 2026, real 2040Q4, real 2027-40 sum, nominal 2026)
        (): (-1.16, -1.30, -76.7, 0.52),
        UNDIAGNOSED: (-0.91, -1.21, -58.0, 1.03),
    }
    nominal_sums = []
    for hold, (r26, r40, rsum, n26) in want.items():
        def solve(alpha):
            over = {"alpha_PP": alpha, **{n: [r[n] for r in base] for n in hold}}
            return solve_path(build_registry("empirical"), base, overrides=over,
                              max_iter=5000)

        lo, hi = solve(0.2748), solve(0.2762)

        def effect(v, t):
            return hi[t][v] - lo[t][v]

        real26 = sum(effect("GDP_R", t) for t in y2026) / 4
        nom26 = sum(effect("GDP", t) for t in y2026) / 4
        assert real26 == pytest.approx(r26, abs=0.01)
        assert 0.8 < real26 / oracle("GDP_R") < 1.05   # the observed effect
        assert all(effect("GDP_R", t) < -0.85 for t in policy)  # no fading
        assert effect("GDP_R", len(base) - 1) == pytest.approx(r40, abs=0.01)
        assert sum(effect("GDP_R", t) for t in policy) == pytest.approx(rsum, abs=0.5)
        # The transition is not reproduced: +3.1 in the cached run's first
        # quarter, about zero here.
        assert gpi[SIM_START]["GDP_R"] - base[SIM_START]["GDP_R"] == pytest.approx(3.1)
        assert abs(effect("GDP_R", SIM_START)) < 0.01
        # ... but the settled unemployment-rate effect is (+0.0004).
        assert effect("ru", POLICY_START - 1) == pytest.approx(
            gpi[POLICY_START - 1]["ru"] - base[POLICY_START - 1]["ru"], abs=1.5e-4)
        assert nom26 == pytest.approx(n26, abs=0.01)
        assert nom26 / oracle("GDP") > 2.0             # not the observed one
        nominal_sums.append(sum(effect("GDP", t) for t in policy))
        # A building price effect: far more than the 20.5 the published
        # range allows for in the multiplier's numerator.
        assert nominal_sums[-1] > 100
    assert max(nominal_sums) / min(nominal_sums) > 1.6  # closures disagree
