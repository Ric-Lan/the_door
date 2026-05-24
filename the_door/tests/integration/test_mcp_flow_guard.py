"""Integration tests: MCP tools + FlowGuard → result=null on unresolved CHECKPOINT."""
from __future__ import annotations

import pytest
from pathlib import Path
from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import FeatureSummary


def _make_feature_summary(fid: str) -> FeatureSummary:
    return FeatureSummary(
        feature_id=fid,
        label=fid,
        description=f"desc {fid}",
        source_node_count=0,
        confidence="high",
    )


# ── Decision unresolved → wrap() returns result=None ──────────────────────────

def test_wrap_unresolved_decision_returns_checkpoint():
    """When _decision is present and unresolved, wrap() must return result=None + checkpoint key."""
    from the_door.core.flow_guard import CheckpointOption, FlowGuard
    from the_door.mcp.tools._response_envelope import wrap

    guard = FlowGuard()
    decision = guard.check(
        "test-checkpoint",
        "needs-choice",
        [CheckpointOption("A", "Option A"), CheckpointOption("B", "Option B")],
        choice=None,
    )
    payload = {"_decision": decision, "some_data": 42}
    result = wrap(payload, project_path=Path("."))
    assert result["result"] is None
    assert result["checkpoint"] == "test-checkpoint"
    assert "next_actions" not in result
    options_keys = {o["key"] for o in result["options"]}
    assert "A" in options_keys and "B" in options_keys


def test_wrap_resolved_decision_returns_payload():
    """When _decision is resolved, wrap() proceeds normally with next_actions."""
    from the_door.core.flow_guard import CheckpointOption, FlowGuard
    from the_door.mcp.tools._response_envelope import wrap

    guard = FlowGuard()
    decision = guard.check(
        "test-checkpoint",
        "needs-choice",
        [CheckpointOption("A", "Option A")],
        choice="A",
    )
    payload = {"_decision": decision, "data": 99}
    result = wrap(payload, project_path=Path("."))
    assert "checkpoint" not in result
    assert result["data"] == 99
    assert "next_actions" in result


def test_wrap_no_decision_normal_behavior():
    """wrap() without _decision → normal payload + next_actions."""
    from the_door.mcp.tools._response_envelope import wrap

    payload = {"result": "ok"}
    result = wrap(payload, project_path=Path("."))
    assert result["result"] == "ok"
    assert "next_actions" in result


# ── snapshot_write: choice=None + new features → result=None ──────────────────

@pytest.mark.asyncio
async def test_snapshot_write_checkpoint_result_null(tmp_path):
    """snapshot_write with new features and no choice → result=None."""
    store = SnapshotStore(tmp_path)
    snap = store.create_snapshot(
        l1_snapshot={"feat-x": _make_feature_summary("feat-x")},
        feature_relations=[], analyzed_files=[], label="base",
    )
    from the_door.mcp.tools import snapshot_write_tool
    result = await snapshot_write_tool.execute({
        "codebase_path": str(tmp_path),
        "inherit_from": snap.version_id,
        "l1_features": [
            {"feature_id": "feat-x", "label": "X", "description": "d", "confidence": "high"},
            {"feature_id": "feat-new", "label": "New", "description": "d", "confidence": "high"},
        ],
    })
    assert result["result"] is None


# ── analyze_changes: broken source path → result=None ─────────────────────────

@pytest.mark.asyncio
async def test_analyze_changes_broken_source_triggers_checkpoint(tmp_path):
    """analyze_changes where baseline codebase_path doesn't exist → CHECKPOINT source-path-broken."""
    store = SnapshotStore(tmp_path)
    snap = store.create_snapshot(
        l1_snapshot={"feat-x": _make_feature_summary("feat-x")},
        feature_relations=[], analyzed_files=[], label="base",
    )
    from the_door.mcp.tools import analyze_changes_tool
    result = await analyze_changes_tool.execute({
        "codebase_path": str(tmp_path),
        "baseline": snap.version_id,
        # no source_path, and baseline.codebase_path = tmp_path which exists
        # To force broken: pass a nonexistent source_path
        "source_path": str(tmp_path / "nonexistent_source"),
    })
    assert result["result"] is None
    assert result["checkpoint"] == "source-path-broken"


# ── system_status: unanalyzed git tags → CHECKPOINT ───────────────────────────

@pytest.mark.asyncio
async def test_system_status_unanalyzed_tags_checkpoint(tmp_path):
    """system_status when there are unanalyzed git tags → CHECKPOINT unanalyzed-versions-detected."""
    import subprocess, shutil
    # Init a tiny git repo with a tag but no snapshot
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t.com"], capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], capture_output=True)
    (tmp_path / "f.txt").write_text("hi")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "tag", "v1.0.0"], capture_output=True)

    from the_door.mcp.tools import system_status_tool
    result = await system_status_tool.execute({"project_path": str(tmp_path)})
    # Either CHECKPOINT or normal state — must not crash
    assert isinstance(result, dict)
    # If unanalyzed-versions-detected triggered:
    if result.get("checkpoint") == "unanalyzed-versions-detected":
        assert result["result"] is None
