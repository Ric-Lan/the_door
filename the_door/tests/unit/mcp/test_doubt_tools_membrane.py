"""S1 characterization + 膜投影：先釘兩工具 output bare 現狀（本 commit），
Task 4 投影後改為 {value, position}（見證契約變更）。"""
from __future__ import annotations

import asyncio

from the_door.core.scope.doubt_store import DoubtStore
from the_door.mcp.tools.doubt_transition_tool import execute as transition_exec
from the_door.mcp.tools.doubt_list_tool import execute as list_exec


def _seed_explained(tmp_path):
    store = DoubtStore(tmp_path)
    d = store.create_doubt(source_node="feat-x", doubt_type="anomaly", created_by="t")
    store.assign(d.doubt_id, "alice", actor="a")
    return store, d


def test_transition_output_current_state_is_bare(tmp_path):
    """CHARACTERIZATION（Task 2 現狀）：current_state 為 bare str。"""
    store, d = _seed_explained(tmp_path)
    out = asyncio.run(transition_exec({
        "doubt_id": d.doubt_id, "target_state": "explained", "actor": "a",
        "reason": "fp", "codebase_path": str(tmp_path),
    }))
    assert out["current_state"] == "explained"
    assert out["doubt_type"] == "anomaly"
    assert out["resolution"]["type"] == "explained"


from the_door.mcp.tools import doubt_transition_tool, doubt_list_tool
from the_door.core.scope.doubt_lifecycle import DoubtLifecycle


def test_transition_target_state_has_enum():
    sch = doubt_transition_tool.TOOL_SCHEMA["properties"]["target_state"]
    assert set(sch["enum"]) == {"investigating", "explained", "fixed", "escalated", "accepted_risk"}
    assert "investigating" in sch["description"]


def test_list_state_and_type_have_enum():
    props = doubt_list_tool.TOOL_SCHEMA["properties"]
    assert set(props["state"]["enum"]) == set(DoubtLifecycle.VALID_TRANSITIONS.keys())
    assert set(props["type"]["enum"]) == {"out_of_scope", "in_scope_incomplete", "anomaly", "low_confidence"}
