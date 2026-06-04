"""Characterization tests: pin DoubtStore transition + timeout behaviour BEFORE
the DoubtLifecycle extraction. These must stay green across the refactor."""
from __future__ import annotations

import json

import pytest

from the_door.core.scope.doubt_store import DoubtStore
from the_door.models import DoubtTerminalError, InvalidTransitionError


def _store(tmp_path) -> DoubtStore:
    return DoubtStore(tmp_path)


def _new(store, *, source_node="feat-x", doubt_type="anomaly", created_by="tester"):
    return store.create_doubt(source_node=source_node, doubt_type=doubt_type, created_by=created_by)


def test_create_starts_discovered(tmp_path):
    d = _new(_store(tmp_path))
    assert d.current_state == "discovered"
    assert d.resolution is None
    assert d.assigned_to is None


def test_assign_sets_investigating_and_assignee(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    out = store.assign(d.doubt_id, "alice", actor="bob")
    assert out.current_state == "investigating"
    assert out.assigned_to == "alice"
    reloaded = store.get_doubt(d.doubt_id)
    assert reloaded.current_state == "investigating"
    assert reloaded.assigned_to == "alice"
    assert reloaded.state_history[-1].from_state == "discovered"
    assert reloaded.state_history[-1].to_state == "investigating"
    assert reloaded.state_history[-1].actor == "bob"


def test_explain_from_investigating_sets_resolution(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    store.assign(d.doubt_id, "alice", actor="alice")
    out = store.explain(d.doubt_id, "false positive", resolved_by="alice")
    assert out.current_state == "explained"
    assert out.resolution.type == "explained"
    assert out.resolution.description == "false positive"
    assert out.resolution.resolved_by == "alice"
    assert store.get_doubt(d.doubt_id).resolution.type == "explained"


def test_fix_from_investigating_sets_resolution(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    store.assign(d.doubt_id, "alice", actor="alice")
    out = store.fix(d.doubt_id, "patched", resolved_by="alice")
    assert out.current_state == "fixed"
    assert out.resolution.type == "fixed"
    assert out.resolution.description == "patched"


def test_escalate_records_reason_no_resolution(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    out = store.escalate(d.doubt_id, "needs manager", actor="alice")
    assert out.current_state == "escalated"
    assert out.resolution is None
    assert out.state_history[-1].reason == "needs manager"


def test_resolve_escalation_sets_resolution(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    store.escalate(d.doubt_id, "r", actor="alice")
    out = store.resolve_escalation(d.doubt_id, "accepted_risk", "tolerated", resolved_by="mgr")
    assert out.current_state == "accepted_risk"
    assert out.resolution.type == "accepted_risk"
    assert out.resolution.description == "tolerated"
    assert out.resolution.resolved_by == "mgr"


def test_explain_from_escalated_equals_investigating_resolution(tmp_path):
    """section 2.2: explained via escalated produces the same Resolution shape."""
    store = _store(tmp_path)
    d = _new(store)
    store.escalate(d.doubt_id, "r", actor="a")
    out = store.resolve_escalation(d.doubt_id, "explained", "fp", resolved_by="mgr")
    assert out.current_state == "explained"
    assert out.resolution.type == "explained"
    assert out.resolution.description == "fp"


def test_illegal_transition_raises(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    # discovered -> explained is illegal (valid: investigating/escalated)
    with pytest.raises(InvalidTransitionError):
        store.explain(d.doubt_id, "x", resolved_by="a")


def test_terminal_state_raises(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    store.assign(d.doubt_id, "a", actor="a")
    store.explain(d.doubt_id, "x", resolved_by="a")  # now terminal
    with pytest.raises(DoubtTerminalError):
        store.fix(d.doubt_id, "y", resolved_by="a")


def _write_timeout_config(tmp_path, discovery, investigation):
    cfg = tmp_path / ".the-door" / "scope-config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps(
        {"discovery_timeout_days": discovery, "investigation_timeout_days": investigation}
    ), encoding="utf-8")


def test_check_timeouts_escalates_discovered_when_due(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    _write_timeout_config(tmp_path, 0, 7)  # discovery timeout 0 days -> always due
    out = store.check_timeouts(store.get_doubt(d.doubt_id))
    assert out is not None
    assert out.current_state == "escalated"
    assert out.state_history[-1].actor == "system_timeout"


def test_check_timeouts_escalates_investigating_when_due(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    store.assign(d.doubt_id, "a", actor="a")
    _write_timeout_config(tmp_path, 3, 0)  # investigation timeout 0 -> always due
    out = store.check_timeouts(store.get_doubt(d.doubt_id))
    assert out is not None
    assert out.current_state == "escalated"


def test_check_timeouts_none_when_not_due(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    _write_timeout_config(tmp_path, 999, 999)
    assert store.check_timeouts(store.get_doubt(d.doubt_id)) is None


def test_check_timeouts_none_when_terminal(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    store.assign(d.doubt_id, "a", actor="a")
    store.explain(d.doubt_id, "x", resolved_by="a")
    assert store.check_timeouts(store.get_doubt(d.doubt_id)) is None


def test_has_active_doubt_and_summary(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    assert store.has_active_doubt("feat-x", "anomaly") is True
    store.assign(d.doubt_id, "a", actor="a")
    store.explain(d.doubt_id, "x", resolved_by="a")  # terminal
    assert store.has_active_doubt("feat-x", "anomaly") is False
    summary = store.get_summary()
    assert summary.by_state.get("explained") == 1
    assert summary.total_active == 0
