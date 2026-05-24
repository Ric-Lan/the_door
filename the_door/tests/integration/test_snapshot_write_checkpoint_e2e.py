"""E2E tests: snapshot_write CHECKPOINT flow — all three choice branches."""
from __future__ import annotations

import pytest
from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import FeatureSummary
from tests._seed_helpers import seed_baseline_snapshot
from the_door.mcp.tools.snapshot_write_tool import execute


def _make_fs(fid: str) -> FeatureSummary:
    return FeatureSummary(
        feature_id=fid,
        label=fid,
        description=f"desc {fid}",
        source_node_count=1,
        confidence="high",
        source_nodes=(f"Node.{fid}",),
    )


@pytest.fixture
def project_with_baseline(tmp_path):
    seed_baseline_snapshot(
        tmp_path,
        label="v1.0.0",
        features={"feat-old": _make_fs("feat-old")},
    )
    return tmp_path


NEW_FEATURE = {
    "feature_id": "feat-new",
    "label": "New",
    "description": "newly added feature",
    "confidence": "high",
    "source_nodes": ["NewModule.run"],
}
OLD_FEATURE = {
    "feature_id": "feat-old",
    "label": "Old",
    "description": "desc feat-old",
    "confidence": "high",
    "source_nodes": ["Node.feat-old"],
}


@pytest.mark.asyncio
async def test_checkpoint_triggers_when_new_feature_detected(project_with_baseline):
    """First call without choice must return checkpoint (result=None)."""
    result = await execute({
        "codebase_path": str(project_with_baseline),
        "inherit_from": "v1.0.0",
        "l1_features": [OLD_FEATURE, NEW_FEATURE],
    })
    assert result.get("result") is None, f"Expected checkpoint, got: {result}"
    assert "checkpoint" in result
    option_keys = {o["key"] for o in result.get("options", [])}
    assert {"A", "B", "C"} == option_keys


@pytest.mark.asyncio
async def test_choice_a_includes_new_feature(project_with_baseline):
    """choice=A must write snapshot containing both old and new features."""
    result = await execute({
        "codebase_path": str(project_with_baseline),
        "inherit_from": "v1.0.0",
        "l1_features": [OLD_FEATURE, NEW_FEATURE],
        "choice": "A",
        "label": "v1.0.1-a",
    })
    assert "error" not in result
    snap = SnapshotStore(project_with_baseline).get_snapshot(result["version_id"])
    assert "feat-new" in snap.l1_snapshot
    assert "feat-old" in snap.l1_snapshot


@pytest.mark.asyncio
async def test_choice_b_drops_new_feature(project_with_baseline):
    """choice=B must write snapshot with only baseline features."""
    result = await execute({
        "codebase_path": str(project_with_baseline),
        "inherit_from": "v1.0.0",
        "l1_features": [OLD_FEATURE, NEW_FEATURE],
        "choice": "B",
        "label": "v1.0.1-b",
    })
    assert "error" not in result
    snap = SnapshotStore(project_with_baseline).get_snapshot(result["version_id"])
    assert "feat-new" not in snap.l1_snapshot
    assert "feat-old" in snap.l1_snapshot


@pytest.mark.asyncio
async def test_choice_c_aborts_no_snapshot_written(project_with_baseline):
    """choice=C must abort and not write any new snapshot."""
    store = SnapshotStore(project_with_baseline)
    count_before = len(store.list_snapshots())
    result = await execute({
        "codebase_path": str(project_with_baseline),
        "inherit_from": "v1.0.0",
        "l1_features": [OLD_FEATURE, NEW_FEATURE],
        "choice": "C",
    })
    assert result.get("aborted") is True
    assert len(store.list_snapshots()) == count_before
