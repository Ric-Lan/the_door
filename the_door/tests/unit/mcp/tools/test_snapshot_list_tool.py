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


def test_snapshot_list_has_project_summary_false_when_absent(listed_project):
    result = asyncio.run(snapshot_list_tool.execute(
        {"codebase_path": str(listed_project)}
    ))
    for s in result["snapshots"]:
        assert s["has_project_summary"] is False


def test_snapshot_list_has_project_summary_true_when_present(tmp_path):
    store = SnapshotStore(tmp_path)
    store.create_snapshot(
        l1_snapshot={}, feature_relations=[], analyzed_files=[],
        trigger="manual", label="v-with-summary",
        project_summary="這個系統提供 CLI 分析。",
    )
    result = asyncio.run(snapshot_list_tool.execute(
        {"codebase_path": str(tmp_path)}
    ))
    assert result["snapshots"][0]["has_project_summary"] is True


class TestSnapshotListNarrativeFields:
    @pytest.fixture
    def project_with_narratives(self, tmp_path):
        store = SnapshotStore(tmp_path)
        s1 = store.create_snapshot(
            l1_snapshot={}, feature_relations=[], analyzed_files=[],
            trigger="manual", label="v1",
        )
        s2 = store.create_snapshot(
            l1_snapshot={}, feature_relations=[], analyzed_files=[],
            trigger="manual", label="v2",
            version_narratives={s1.version_id: "Added feature A."},
        )
        return tmp_path, s1, s2

    def test_has_version_narrative_false_when_empty(self, tmp_path):
        store = SnapshotStore(tmp_path)
        store.create_snapshot(
            l1_snapshot={}, feature_relations=[], analyzed_files=[],
            trigger="manual", label="v1",
        )
        result = asyncio.run(snapshot_list_tool.execute({"codebase_path": str(tmp_path)}))
        assert result["snapshots"][0]["has_version_narrative"] is False

    def test_has_version_narrative_true_when_nonempty(self, project_with_narratives):
        tmp_path, s1, s2 = project_with_narratives
        result = asyncio.run(snapshot_list_tool.execute({"codebase_path": str(tmp_path)}))
        snaps = {s["label"]: s for s in result["snapshots"]}
        assert snaps["v2"]["has_version_narrative"] is True
        assert snaps["v1"]["has_version_narrative"] is False

    def test_narrative_baselines_lists_keys(self, project_with_narratives):
        tmp_path, s1, s2 = project_with_narratives
        result = asyncio.run(snapshot_list_tool.execute({"codebase_path": str(tmp_path)}))
        snaps = {s["label"]: s for s in result["snapshots"]}
        assert s1.version_id in snaps["v2"]["narrative_baselines"]
        assert snaps["v1"]["narrative_baselines"] == []

    def test_narrative_summary_counts(self, project_with_narratives):
        tmp_path, s1, s2 = project_with_narratives
        result = asyncio.run(snapshot_list_tool.execute({"codebase_path": str(tmp_path)}))
        ns = result["narrative_summary"]
        assert ns["total"] == 2
        assert ns["has_narrative"] == 1
        assert ns["missing_narrative"] == 1

    def test_narrative_summary_note_present(self, project_with_narratives):
        tmp_path, _, _ = project_with_narratives
        result = asyncio.run(snapshot_list_tool.execute({"codebase_path": str(tmp_path)}))
        assert "note" in result["narrative_summary"]
        assert isinstance(result["narrative_summary"]["note"], str)

    def test_narrative_summary_all_present_note(self, tmp_path):
        store = SnapshotStore(tmp_path)
        s1 = store.create_snapshot(
            l1_snapshot={}, feature_relations=[], analyzed_files=[],
            trigger="manual", label="v1",
        )
        store.create_snapshot(
            l1_snapshot={}, feature_relations=[], analyzed_files=[],
            trigger="manual", label="v2",
            version_narratives={s1.version_id: "Some narrative."},
        )
        store.patch_snapshot("v1", version_narratives={s1.version_id: "Also narrative."})
        result = asyncio.run(snapshot_list_tool.execute({"codebase_path": str(tmp_path)}))
        ns = result["narrative_summary"]
        assert ns["missing_narrative"] == 0
