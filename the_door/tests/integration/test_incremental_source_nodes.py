"""Integration: analyze_changes returns source_nodes; snapshot_write preserves them."""
from __future__ import annotations

import pytest
from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import FeatureSummary
from tests._seed_helpers import seed_baseline_snapshot
from the_door.mcp.tools.snapshot_write_tool import execute as snapshot_write
from the_door.mcp.tools.analyze_changes_tool import _feature_to_json


def _make_fs_with_nodes(fid: str, nodes: tuple[str, ...]) -> FeatureSummary:
    return FeatureSummary(
        feature_id=fid,
        label=fid,
        description=f"desc {fid}",
        source_node_count=len(nodes),
        confidence="high",
        source_nodes=nodes,
    )


def test_feature_to_json_includes_source_nodes():
    """_feature_to_json must serialize source_nodes as a list."""
    fs = _make_fs_with_nodes("feat-a", ("Foo.bar", "Baz.qux"))
    result = _feature_to_json(fs)
    assert result["source_nodes"] == ["Foo.bar", "Baz.qux"]
    assert result["source_node_count"] == 2


@pytest.mark.asyncio
async def test_updated_features_preserves_source_nodes(tmp_path):
    """snapshot_write with updated_features must not drop source_nodes from baseline."""
    seed_baseline_snapshot(
        tmp_path,
        label="v1.0.0",
        features={
            "feat-stable": _make_fs_with_nodes("feat-stable", ("StableModule.run",)),
            "feat-changed": _make_fs_with_nodes("feat-changed", ("OldModule.fn",)),
        },
    )

    result = await snapshot_write({
        "codebase_path": str(tmp_path),
        "inherit_from": "v1.0.0",
        "updated_features": [
            {
                "feature_id": "feat-changed",
                "label": "feat-changed updated",
                "description": "updated description",
                "confidence": "high",
                "source_nodes": ["NewModule.fn"],
            }
        ],
        "label": "v1.0.1",
    })
    assert "error" not in result

    snap = SnapshotStore(tmp_path).get_snapshot(result["version_id"])
    assert snap.l1_snapshot["feat-stable"].source_nodes == ("StableModule.run",)
    assert snap.l1_snapshot["feat-changed"].source_nodes == ("NewModule.fn",)
