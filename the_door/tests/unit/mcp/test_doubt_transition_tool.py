"""Characterization tests: pin doubt_transition MCP tool routing + error
messages BEFORE the refactor. Success paths are verified by reloading the doubt
via DoubtStore (avoids coupling to the response envelope shape)."""
from __future__ import annotations

import asyncio

from the_door.core.scope.doubt_store import DoubtStore
from the_door.mcp.tools.doubt_transition_tool import execute


def _run(args):
    return asyncio.run(execute(args))


def _new(tmp_path):
    store = DoubtStore(tmp_path)
    d = store.create_doubt(source_node="feat-x", doubt_type="anomaly", created_by="t")
    return store, d


def _args(tmp_path, doubt_id, target, **kw):
    base = {"doubt_id": doubt_id, "target_state": target, "actor": "agent",
            "codebase_path": str(tmp_path)}
    base.update(kw)
    return base


def test_assign_path(tmp_path):
    store, d = _new(tmp_path)
    _run(_args(tmp_path, d.doubt_id, "investigating", assignee="alice"))
    r = store.get_doubt(d.doubt_id)
    assert r.current_state == "investigating"
    assert r.assigned_to == "alice"


def test_explained_from_investigating(tmp_path):
    store, d = _new(tmp_path)
    store.assign(d.doubt_id, "a", actor="a")
    _run(_args(tmp_path, d.doubt_id, "explained", reason="fp"))
    r = store.get_doubt(d.doubt_id)
    assert r.current_state == "explained"
    assert r.resolution.type == "explained"
    assert r.resolution.description == "fp"


def test_explained_from_escalated_branch(tmp_path):
    store, d = _new(tmp_path)
    store.escalate(d.doubt_id, "r", actor="a")
    _run(_args(tmp_path, d.doubt_id, "explained", reason="fp"))
    r = store.get_doubt(d.doubt_id)
    assert r.current_state == "explained"
    assert r.resolution.type == "explained"


def test_fixed_from_escalated_branch(tmp_path):
    store, d = _new(tmp_path)
    store.escalate(d.doubt_id, "r", actor="a")
    _run(_args(tmp_path, d.doubt_id, "fixed", reason="done"))
    assert store.get_doubt(d.doubt_id).current_state == "fixed"


def test_escalated_path(tmp_path):
    store, d = _new(tmp_path)
    _run(_args(tmp_path, d.doubt_id, "escalated", reason="up"))
    assert store.get_doubt(d.doubt_id).current_state == "escalated"


def test_accepted_risk_path(tmp_path):
    store, d = _new(tmp_path)
    store.escalate(d.doubt_id, "r", actor="a")
    _run(_args(tmp_path, d.doubt_id, "accepted_risk", reason="tolerate"))
    r = store.get_doubt(d.doubt_id)
    assert r.current_state == "accepted_risk"
    assert r.resolution.type == "accepted_risk"


def test_missing_assignee_error(tmp_path):
    store, d = _new(tmp_path)
    out = _run(_args(tmp_path, d.doubt_id, "investigating"))
    assert out == {"error": True, "message": "assignee is required for investigating transition"}


def test_missing_reason_error(tmp_path):
    store, d = _new(tmp_path)
    store.assign(d.doubt_id, "a", actor="a")
    out = _run(_args(tmp_path, d.doubt_id, "explained"))
    assert out == {"error": True, "message": "reason is required for explained transition"}


def test_unknown_target_state_error(tmp_path):
    store, d = _new(tmp_path)
    out = _run(_args(tmp_path, d.doubt_id, "bogus"))
    assert out == {"error": True, "message": "Unknown target_state: bogus"}


def test_invalid_transition_error_message(tmp_path):
    store, d = _new(tmp_path)
    # discovered -> explained is illegal; tool returns str(InvalidTransitionError)
    out = _run(_args(tmp_path, d.doubt_id, "explained", reason="x"))
    assert out["error"] is True
    assert "explained" in out["message"]
