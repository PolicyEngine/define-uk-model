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


def test_full_registry_builds_from_every_sector_module():
    """Every sector module registers cleanly; the count grows per milestone.

    Milestone 2 landed §3.2 (Eqs. 21-43, 23 equations). The remaining sector
    modules are still stubs, so the total is exactly §3.2 for now — update
    this as each milestone lands, and keep it exact rather than a lower
    bound: a silently-dropped `register()` call should fail here, not pass.
    """
    registry = build_registry()
    assert len(registry) == 23

    sections = {eq.manual_ref.split(" eq.")[0] for eq in registry}
    assert sections == {"§3.2"}

    # No sector module may register the same endogenous variable twice; the
    # Registry raises on collision, so reaching here already proves it.
    assert len(set(registry.names())) == len(registry)
