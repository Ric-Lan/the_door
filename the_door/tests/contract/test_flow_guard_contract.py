"""Contract tests: MCP response envelope shape when FlowGuard triggers a CHECKPOINT.

These tests verify the public contract between FlowGuard/wrap() and MCP callers:
  - result=null when Decision is unresolved
  - checkpoint/status/options keys present
  - no next_actions when CHECKPOINT is active
  - each tool that can CHECKPOINT does so with choice=None
"""
from __future__ import annotations

import pytest
from pathlib import Path
from the_door.core.flow_guard import CheckpointOption, FlowGuard
from the_door.mcp.tools._response_envelope import wrap
from the_door.models import FeatureSummary
from the_door.core.diff.snapshot_store import SnapshotStore


def _make_feature_summary(fid: str) -> FeatureSummary:
    return FeatureSummary(
        feature_id=fid, label=fid, description="d",
        source_node_count=0, confidence="high",
    )


# ── wrap() contract ────────────────────────────────────────────────────────────

def test_wrap_unresolved_result_is_null():
    guard = FlowGuard()
    d = guard.check("cp", "s", [CheckpointOption("A", "opt")], choice=None)
    result = wrap({"_decision": d}, project_path=Path("."))
    assert result["result"] is None


def test_wrap_unresolved_has_checkpoint_key():
    guard = FlowGuard()
    d = guard.check("my-checkpoint", "s", [CheckpointOption("A", "opt")], choice=None)
    result = wrap({"_decision": d}, project_path=Path("."))
    assert result["checkpoint"] == "my-checkpoint"


def test_wrap_unresolved_has_status_key():
    guard = FlowGuard()
    d = guard.check("cp", "my-status", [CheckpointOption("A", "opt")], choice=None)
    result = wrap({"_decision": d}, project_path=Path("."))
    assert result["status"] == "my-status"


def test_wrap_unresolved_options_have_required_fields():
    guard = FlowGuard()
    d = guard.check(
        "cp", "s",
        [CheckpointOption("A", "Label A", "next_a"), CheckpointOption("B", "Label B")],
        choice=None,
    )
    result = wrap({"_decision": d}, project_path=Path("."))
    options = result["options"]
    assert len(options) == 2
    for opt in options:
        assert "key" in opt
        assert "label" in opt
        assert "next_call" in opt


def test_wrap_unresolved_no_next_actions():
    guard = FlowGuard()
    d = guard.check("cp", "s", [CheckpointOption("A", "opt")], choice=None)
    result = wrap({"_decision": d}, project_path=Path("."))
    assert "next_actions" not in result


def test_wrap_resolved_has_no_checkpoint_key():
    guard = FlowGuard()
    d = guard.check("cp", "s", [CheckpointOption("A", "opt")], choice="A")
    result = wrap({"_decision": d, "data": 42}, project_path=Path("."))
    assert "checkpoint" not in result
    assert result["data"] == 42
    assert "next_actions" in result


# ── Per-tool CHECKPOINT contract ──────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name,args_factory", [
    (
        "snapshot_write",
        lambda vid, tmp: {
            "codebase_path": str(tmp),
            "inherit_from": vid,
            "l1_features": [
                {"feature_id": "feat-x", "label": "X", "description": "d", "confidence": "high"},
                {"feature_id": "feat-new", "label": "New", "description": "d", "confidence": "high"},
            ],
        },
    ),
])
async def test_tool_returns_result_null_on_checkpoint(tool_name, args_factory, tmp_path):
    """Each tool that can trigger CHECKPOINT returns result=None with choice=None."""
    store = SnapshotStore(tmp_path)
    snap = store.create_snapshot(
        l1_snapshot={"feat-x": _make_feature_summary("feat-x")},
        feature_relations=[], analyzed_files=[], label="base",
    )
    args = args_factory(snap.version_id, tmp_path)

    if tool_name == "snapshot_write":
        from the_door.mcp.tools import snapshot_write_tool
        result = await snapshot_write_tool.execute(args)
    else:
        raise ValueError(f"Unknown tool: {tool_name}")

    assert result["result"] is None, f"{tool_name} should return result=null on CHECKPOINT"
    assert "checkpoint" in result, f"{tool_name} response must have 'checkpoint' key"
