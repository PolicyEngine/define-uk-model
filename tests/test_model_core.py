"""Registry and solver behaviour, exercised on a toy SFC system (not DEFINE)."""

import pytest

from define_uk.model import Equation, Registry, solve_period
from define_uk.model.sectors import build_registry


def _toy_registry():
    # Minimal Keynesian closure: Y = C + G, C = 0.8 * Y. Fixed point with
    # G = 20 is Y = 100, C = 80. Ours, for testing the machinery only.
    r = Registry()
    r.add(Equation("Y", "test fixture", "identity", lambda s, l: s["C"] + s["G"]))
    r.add(Equation("C", "test fixture", "behavioural", lambda s, l: 0.8 * s["Y"]))
    return r


def test_solver_converges_to_fixed_point():
    state = solve_period(_toy_registry(), lag={"Y": 0.0, "C": 0.0}, exogenous={"G": 20.0})
    assert state["Y"] == pytest.approx(100.0, rel=1e-6)
    assert state["C"] == pytest.approx(80.0, rel=1e-6)


def test_solver_raises_on_divergence():
    r = Registry()
    r.add(Equation("X", "test fixture", "identity", lambda s, l: 2.0 * s["X"] + 1.0))
    with pytest.raises(RuntimeError, match="did not converge"):
        solve_period(r, lag={"X": 1.0}, max_iter=50)


def test_equation_requires_manual_ref_and_valid_kind():
    with pytest.raises(ValueError, match="manual_ref"):
        Equation("X", "  ", "identity", lambda s, l: 0.0)
    with pytest.raises(ValueError, match="kind"):
        Equation("X", "§3.2", "guess", lambda s, l: 0.0)


def test_registry_rejects_duplicate_endogenous_variable():
    r = Registry()
    eq = Equation("Y", "test fixture", "identity", lambda s, l: 0.0)
    r.add(eq)
    with pytest.raises(ValueError, match="duplicate"):
        r.add(eq)


def test_manual_ref_must_be_a_parseable_citation():
    """The ref format is load-bearing, not cosmetic.

    Every section test asserts its equation numbers are contiguous by parsing
    them out of ``manual_ref``. A ref that does not parse would silently drop
    that equation from the contiguity check instead of failing it, so the
    format is enforced where the object is built.
    """
    for bad in ("§3.3.2 eq (84)", "eq. (84)", "§3.3.2 equation 84", "§3.3.2"):
        with pytest.raises(ValueError, match="manual_ref"):
            Equation("X", bad, "identity", lambda s, l: 0.0)

    ok = Equation("X", "§3.3.2 eq. (84)", "identity", lambda s, l: 0.0)
    assert ok.section == "§3.3.2" and ok.number == 84


def test_registry_rejects_two_equations_citing_the_same_manual_equation():
    """One manual equation determines one variable.

    A copy-pasted ``manual_ref`` makes an equation look transcribed while
    implementing something else, and the per-section contiguity tests cannot
    catch it on their own — a duplicated ref surfaces there only as a hole
    somewhere else in the range.
    """
    r = Registry()
    r.add(Equation("P_ELEC", "§3.3.2 eq. (84)", "calibrated", lambda s, l: 0.0))
    with pytest.raises(ValueError, match="already cited by P_ELEC"):
        r.add(Equation("MC_ELEC", "§3.3.2 eq. (84)", "behavioural", lambda s, l: 0.0))


def test_every_registered_equation_has_a_parseable_unique_citation():
    """The guarantee, asserted on the real registry rather than a fixture."""
    registry = build_registry()
    refs = [eq.manual_ref for eq in registry]
    assert len(set(refs)) == len(refs)
    for eq in registry:
        assert eq.section is not None and eq.number is not None, eq.manual_ref


def test_full_registry_builds_from_every_sector_module():
    """Every sector module registers cleanly; the count grows per milestone.

    Milestone 2 has landed §3.2 (Eqs. 21-43, 23 equations), §3.3.1
    (Eqs. 44-70, 27 equations) and §3.3.2 (Eqs. 71-138, 68 equations).
    §3.3.3 and the remaining sector modules are still stubs — update this as
    each slice lands, and keep it exact rather than a lower bound: a
    silently-dropped `register()` call should fail here, not pass.
    """
    registry = build_registry()
    assert len(registry) == 23 + 27 + 68

    sections = {eq.manual_ref.split(" eq.")[0] for eq in registry}
    assert sections == {"§3.2", "§3.3.1", "§3.3.2"}

    # No sector module may register the same endogenous variable twice; the
    # Registry raises on collision, so reaching here already proves it.
    assert len(set(registry.names())) == len(registry)
