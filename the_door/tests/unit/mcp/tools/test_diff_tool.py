"""S6 characterization：diff_tool json emit 的 diff_state 膜投影（C3）。

對應 spec §3.2／§6：diff_tool（format="json"）的 node_diffs/edge_diffs 的 diff_state
由裸 enum 升為膜投影 {value, position(signal)}。fixture＝真實 SnapshotStore 兩 snapshot
（diff 的輸入）＋真實 diff_tool.execute（產 diff 結果），不 hand-build DiffResult。
store-population 範本＝store.create_snapshot（生產寫入路徑）。
"""
from __future__ import annotations

import asyncio

import pytest

from the_door.core.diff.diff_membrane import EDGE_DIFF_CONTRASTS, NODE_DIFF_CONTRASTS
from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.mcp.tools import diff_tool
from the_door.models import FeatureSummary, RelationSummary


def _fs(fid: str, label: str, desc: str) -> FeatureSummary:
    return FeatureSummary(
        feature_id=fid, label=label, description=desc,
        source_node_count=1, confidence="high",
    )


@pytest.fixture
def diffable_project(tmp_path):
    """Populate a store with baseline + current so diff_tool resolves both.

    Yields varied diff_states: feat-a (attr+edge→dependency_changed),
    feat-b (unchanged+edge→dependency_changed), feat-old (removed),
    feat-new (added); edge feat-a→feat-b modified.
    """
    store = SnapshotStore(tmp_path)
    store.create_snapshot(
        l1_snapshot={"feat-a": _fs("feat-a", "A", "A"),
                     "feat-b": _fs("feat-b", "B", "B"),
                     "feat-old": _fs("feat-old", "O", "O")},
        feature_relations=[RelationSummary(from_feature="feat-a", to_feature="feat-b", relation="r1")],
        analyzed_files=[], trigger="manual", label="baseline-v1",
    )
    current = store.create_snapshot(
        l1_snapshot={"feat-a": _fs("feat-a", "A2", "A2"),
                     "feat-b": _fs("feat-b", "B", "B"),
                     "feat-new": _fs("feat-new", "N", "N")},
        feature_relations=[RelationSummary(from_feature="feat-a", to_feature="feat-b", relation="r2")],
        analyzed_files=[], trigger="manual", label="current-v2",
    )
    # sanity：current 必為 get_latest（diff_tool 取 current=get_latest）
    assert store.get_latest().version_id == current.version_id
    return tmp_path


def test_diff_tool_json_projects_diff_state_to_membrane(diffable_project):
    result = asyncio.run(diff_tool.execute(
        {"codebase_path": str(diffable_project), "baseline": "baseline-v1", "format": "json"}
    ))

    assert result.get("error") is None, result
    node_diffs = result["node_diffs"]
    edge_diffs = result["edge_diffs"]
    assert node_diffs and edge_diffs  # fixture 確有 node 與 edge diff

    # node：每筆 diff_state＝膜投影 {value, position(signal, 5-set)}、無裸 enum
    for nd in node_diffs:
        ds = nd["diff_state"]
        assert isinstance(ds, dict), f"diff_state 仍裸 enum：{ds!r}"
        assert ds["value"] in NODE_DIFF_CONTRASTS
        assert ds["position"]["kind"] == "signal"
        assert ds["position"]["contrasts"] == list(NODE_DIFF_CONTRASTS)
        assert ds["position"]["gloss"]
        assert "node_id" in nd  # 其餘鍵不變

    # edge：每筆 diff_state＝膜投影 {value, position(signal, 3-set)}
    for ed in edge_diffs:
        ds = ed["diff_state"]
        assert isinstance(ds, dict)
        assert ds["value"] in EDGE_DIFF_CONTRASTS
        assert ds["position"]["kind"] == "signal"
        assert ds["position"]["contrasts"] == list(EDGE_DIFF_CONTRASTS)
        assert "from_node" in ed and "to_node" in ed


def test_diff_tool_mermaid_format_unaffected(diffable_project):
    """投影隔離於 json 分支：mermaid 分支仍回純文字（人類面 out）。"""
    result = asyncio.run(diff_tool.execute(
        {"codebase_path": str(diffable_project), "baseline": "baseline-v1", "format": "mermaid"}
    ))
    assert result.get("error") is None, result
    assert isinstance(result["mermaid"], str)
