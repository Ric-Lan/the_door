"""snapshot_write 接受 relation_type/inferred_reason 並持久化；舊 payload 仍相容。"""
import tempfile
from pathlib import Path

import pytest

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.mcp.tools import snapshot_write_tool


def _args(relations):
    return {
        "codebase_path": tempfile.mkdtemp(),
        "l1_features": [
            {"feature_id": "feat-a", "label": "A", "description": "d",
             "confidence": "high", "source_nodes": ["X.m"]},
            {"feature_id": "feat-b", "label": "B", "description": "d",
             "confidence": "high", "source_nodes": ["Y.n"]},
        ],
        "relations": relations,
        "label": "v1",
    }


@pytest.mark.asyncio
async def test_snapshot_write_persists_relation_type():
    args = _args([{"from_feature": "feat-a", "to_feature": "feat-b",
                   "relation": "depends_on", "relation_type": "static"}])
    result = await snapshot_write_tool.execute(args)
    assert "error" not in result, result
    snap = SnapshotStore(Path(args["codebase_path"])).get_snapshot(result["version_id"])
    rel = snap.feature_relations_snapshot[0]
    assert rel.relation_type == "static"


@pytest.mark.asyncio
async def test_snapshot_write_legacy_relation_without_type_ok():
    args = _args([{"from_feature": "feat-a", "to_feature": "feat-b",
                   "relation": "depends_on"}])
    result = await snapshot_write_tool.execute(args)
    assert "error" not in result, result
    snap = SnapshotStore(Path(args["codebase_path"])).get_snapshot(result["version_id"])
    assert snap.feature_relations_snapshot[0].relation_type is None
