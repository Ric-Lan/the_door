"""Unit tests for DoubtLifecycle — pure transition policy, no I/O."""
from __future__ import annotations

import pytest

from the_door.core.scope.doubt_lifecycle import DoubtLifecycle, TransitionPlan
from the_door.models import DoubtTerminalError, InvalidTransitionError


def test_check_transition_legal_pairs_pass():
    lc = DoubtLifecycle()
    for frm, tos in lc.VALID_TRANSITIONS.items():
        for to in tos:
            lc.check_transition(frm, to, "id")  # must not raise


def test_check_transition_terminal_raises():
    lc = DoubtLifecycle()
    with pytest.raises(DoubtTerminalError):
        lc.check_transition("explained", "fixed", "id")


def test_check_transition_illegal_raises():
    lc = DoubtLifecycle()
    with pytest.raises(InvalidTransitionError):
        lc.check_transition("discovered", "explained", "id")


def test_plan_investigating_sets_assignee():
    lc = DoubtLifecycle()
    p = lc.plan(doubt_id="id", from_state="discovered", to_state="investigating",
                actor="bob", assignee="alice")
    assert isinstance(p, TransitionPlan)
    assert p.set_assigned_to is True
    assert p.assigned_to == "alice"
    assert p.resolution is None
    assert p.transition.to_state == "investigating"
    assert p.transition.actor == "bob"


def test_plan_escalated_records_reason_no_resolution():
    lc = DoubtLifecycle()
    p = lc.plan(doubt_id="id", from_state="discovered", to_state="escalated",
                actor="a", reason="up")
    assert p.resolution is None
    assert p.set_assigned_to is False
    assert p.transition.reason == "up"


def test_plan_resolving_states_build_resolution():
    lc = DoubtLifecycle()
    for to in ("explained", "fixed", "accepted_risk"):
        frm = "investigating" if to in ("explained", "fixed") else "escalated"
        p = lc.plan(doubt_id="id", from_state=frm, to_state=to,
                    actor="mgr", description="d")
        assert p.resolution is not None
        assert p.resolution.type == to
        assert p.resolution.description == "d"
        assert p.resolution.resolved_by == "mgr"
        assert p.set_assigned_to is False


def test_plan_explained_same_resolution_via_two_paths():
    """§2.2 equivalence: type/description/resolved_by identical regardless of from_state."""
    lc = DoubtLifecycle()
    a = lc.plan(doubt_id="id", from_state="investigating", to_state="explained",
                actor="m", description="fp")
    b = lc.plan(doubt_id="id", from_state="escalated", to_state="explained",
                actor="m", description="fp")
    assert (a.resolution.type, a.resolution.description, a.resolution.resolved_by) == \
           (b.resolution.type, b.resolution.description, b.resolution.resolved_by)


def test_plan_illegal_raises_before_building():
    lc = DoubtLifecycle()
    with pytest.raises(InvalidTransitionError):
        lc.plan(doubt_id="id", from_state="discovered", to_state="explained",
                actor="a", description="x")
