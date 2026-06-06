"""S7 P5 characterization：snapshot_list 每筆帶 provenance 膜投影。

每筆 snapshot 的 provenance 由 contract_version 衍生升膜（signal、無裸值）。
fixture＝真實 SnapshotStore.create_snapshot（生產寫入路徑）。
"""
from __future__ import annotations

import asyncio

import pytest

from the_door.core.diff.provenance_membrane import PROVENANCE_CONTRASTS
from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.mcp.tools import snapshot_list_tool


@pytest.fixture
def listed_project(tmp_path):
    store = SnapshotStore(tmp_path)
    store.create_snapshot(
        l1_snapshot={}, feature_relations=[], analyzed_files=[],
        trigger="manual", label="v1",
    )
    store.create_snapshot(
        l1_snapshot={}, feature_relations=[], analyzed_files=[],
        trigger="manual", label="v2",
    )
    return tmp_path


def test_snapshot_list_projects_provenance_to_membrane(listed_project):
    result = asyncio.run(snapshot_list_tool.execute(
        {"codebase_path": str(listed_project)}
    ))
    snapshots = result["snapshots"]
    assert snapshots, "fixture 應產出至少一筆 snapshot"
    for s in snapshots:
        prov = s["provenance"]
        assert isinstance(prov, dict), f"provenance 仍裸值：{prov!r}"
        assert prov["value"] in PROVENANCE_CONTRASTS
        assert prov["position"]["kind"] == "signal"
        assert prov["position"]["contrasts"] == list(PROVENANCE_CONTRASTS)
        # 其餘鍵不變
        assert "version_id" in s and "label" in s
    # 經 create_snapshot 蓋戳 ⟹ current
    assert all(s["provenance"]["value"] == "current" for s in snapshots)
