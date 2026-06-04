"""Characterization tests: pin doubt CLI command behaviour BEFORE the refactor."""
from __future__ import annotations

from click.testing import CliRunner

from the_door.cli.doubt_cmd import doubt_group
from the_door.core.scope.doubt_store import DoubtStore


def _new(tmp_path):
    store = DoubtStore(tmp_path)
    d = store.create_doubt(source_node="feat-x", doubt_type="anomaly", created_by="t")
    return store, d


def _invoke(tmp_path, *cli_args):
    return CliRunner().invoke(doubt_group, [*cli_args, "--codebase-path", str(tmp_path)])


def test_assign(tmp_path):
    store, d = _new(tmp_path)
    res = _invoke(tmp_path, "assign", d.doubt_id, "alice")
    assert res.exit_code == 0
    assert "assigned to alice" in res.output
    assert store.get_doubt(d.doubt_id).current_state == "investigating"


def test_escalate(tmp_path):
    store, d = _new(tmp_path)
    res = _invoke(tmp_path, "escalate", d.doubt_id, "--reason", "up")
    assert res.exit_code == 0
    assert "escalated" in res.output
    assert store.get_doubt(d.doubt_id).current_state == "escalated"


def test_resolve_explained_from_investigating(tmp_path):
    store, d = _new(tmp_path)
    store.assign(d.doubt_id, "a", actor="a")
    res = _invoke(tmp_path, "resolve", d.doubt_id, "--as", "explained", "--reason", "fp")
    assert res.exit_code == 0
    assert "resolved as explained" in res.output
    assert store.get_doubt(d.doubt_id).current_state == "explained"


def test_resolve_accepted_risk_from_escalated(tmp_path):
    store, d = _new(tmp_path)
    store.escalate(d.doubt_id, "r", actor="a")
    res = _invoke(tmp_path, "resolve", d.doubt_id, "--as", "accepted_risk", "--reason", "tol")
    assert res.exit_code == 0
    assert "resolved as accepted_risk" in res.output


def test_resolve_illegal_combo_prints_custom_message(tmp_path):
    """investigating + accepted_risk is illegal -> custom else message, exit 1."""
    store, d = _new(tmp_path)
    store.assign(d.doubt_id, "a", actor="a")
    res = _invoke(tmp_path, "resolve", d.doubt_id, "--as", "accepted_risk", "--reason", "x")
    assert res.exit_code == 1
    assert "Cannot resolve as 'accepted_risk' from state 'investigating'" in res.output


def test_resolve_from_terminal_prints_custom_message(tmp_path):
    """terminal doubt -> custom else message, exit 1 (not 'Error: {e}')."""
    store, d = _new(tmp_path)
    store.assign(d.doubt_id, "a", actor="a")
    store.explain(d.doubt_id, "x", resolved_by="a")  # terminal
    res = _invoke(tmp_path, "resolve", d.doubt_id, "--as", "fixed", "--reason", "x")
    assert res.exit_code == 1
    assert "Cannot resolve as 'fixed' from state 'explained'" in res.output
