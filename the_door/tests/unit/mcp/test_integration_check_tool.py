"""integration_check 分類器與 execute 測試。"""
import gzip
import json
import tempfile
from pathlib import Path

import pytest

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.mcp.tools import integration_check_tool as ic
from the_door.models import FeatureSummary, RelationSummary


# ---- 純函式：分類器（不碰磁碟）----
def _adj(edges):
    a = {}
    for e in edges:
        a.setdefault(e["from"], set()).add(e["to"])
    return a


def test_static_backed_direct_edge():
    l1 = {"a": ["A.m"], "b": ["B.n"]}
    edges = [{"from": "A.m", "to": "B.n"}]
    rel = {"from_feature": "a", "to_feature": "b", "relation_type": "static"}
    out = ic.classify_relation(rel, l1, {"A.m", "B.n"}, _adj(edges), max_hops=2)
    assert out["verdict"] == "backed"
    assert out["evidence_path"] == ["A.m", "B.n"]


def test_static_gap_no_path():
    l1 = {"a": ["A.m"], "b": ["B.n"]}
    rel = {"from_feature": "a", "to_feature": "b", "relation_type": "static"}
    out = ic.classify_relation(rel, l1, {"A.m", "B.n"}, _adj([]), max_hops=2)
    assert out["verdict"] == "gap"


def test_static_gap_when_beyond_max_hops():
    # A.m -> M.x -> B.n 需 2 跳；max_hops=1 時應為 gap
    l1 = {"a": ["A.m"], "b": ["B.n"]}
    edges = [{"from": "A.m", "to": "M.x"}, {"from": "M.x", "to": "B.n"}]
    rel = {"from_feature": "a", "to_feature": "b", "relation_type": "static"}
    nodes = {"A.m", "M.x", "B.n"}
    assert ic.classify_relation(rel, l1, nodes, _adj(edges), max_hops=1)["verdict"] == "gap"
    assert ic.classify_relation(rel, l1, nodes, _adj(edges), max_hops=2)["verdict"] == "backed"


def test_static_undetermined_target_not_in_graph():
    l1 = {"a": ["A.m"], "b": ["B.n"]}  # B.n 不在 graph_nodes
    rel = {"from_feature": "a", "to_feature": "b", "relation_type": "static"}
    out = ic.classify_relation(rel, l1, {"A.m"}, _adj([]), max_hops=2)
    assert out["verdict"] == "undetermined"


def test_inferred_is_conceptual_not_edge_checked():
    l1 = {"a": ["A.m"], "b": ["B.n"]}
    rel = {"from_feature": "a", "to_feature": "b",
           "relation_type": "inferred", "inferred_reason": "概念先後"}
    out = ic.classify_relation(rel, l1, {"A.m", "B.n"}, _adj([]), max_hops=2)
    assert out["verdict"] == "conceptual"
    assert out["inferred_reason"] == "概念先後"


def test_untyped_is_not_assessed():
    l1 = {"a": ["A.m"], "b": ["B.n"]}
    rel = {"from_feature": "a", "to_feature": "b"}  # 無 relation_type
    out = ic.classify_relation(rel, l1, {"A.m", "B.n"}, _adj([]), max_hops=2)
    assert out["verdict"] == "not_assessed"


# ---- execute：整合（建一個有 structure 與 snapshot 的暫時 codebase）----
def _feat(fid, nodes):
    return FeatureSummary(feature_id=fid, label=fid, description="d",
                          source_node_count=len(nodes), confidence="high",
                          source_nodes=tuple(nodes))


def _write_structure(cp, nodes, edges):
    p = Path(cp) / ".the-door" / "structure-view"
    p.mkdir(parents=True, exist_ok=True)
    data = {"nodes": [{"node_id": n} for n in nodes],
            "edges": [{"from": f, "to": t, "type": "calls", "resolution": "scope_rule"}
                      for f, t in edges]}
    with gzip.open(p / "structure.full.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(data, fh)


@pytest.mark.asyncio
async def test_execute_end_to_end_rollup():
    cp = Path(tempfile.mkdtemp())
    _write_structure(cp, nodes=["U.save", "DB.q", "O.create"],
                     edges=[("O.create", "DB.q")])
    store = SnapshotStore(cp)
    snap = store.create_snapshot(
        l1_snapshot={"feat-user": _feat("feat-user", ["U.save"]),
                     "feat-db": _feat("feat-db", ["DB.q"]),
                     "feat-order": _feat("feat-order", ["O.create"])},
        feature_relations=[
            RelationSummary("feat-user", "feat-db", "depends_on", relation_type="static"),
            RelationSummary("feat-order", "feat-db", "depends_on", relation_type="static"),
        ],
        analyzed_files=[], commit_hash=None, git_tags=[], trigger="manual", label="v1",
    )
    out = await ic.execute({"codebase_path": str(cp), "version_ref": "v1"})
    assert "error" not in out, out
    verdicts = {(r["from_feature"], r["to_feature"]): r["verdict"] for r in out["relations"]}
    assert verdicts[("feat-user", "feat-db")] == "gap"
    assert verdicts[("feat-order", "feat-db")] == "backed"
    assert out["rollup"]["gap"] == 1
    assert out["rollup"]["backed"] == 1


@pytest.mark.asyncio
async def test_execute_errors_without_structure():
    cp = Path(tempfile.mkdtemp())
    store = SnapshotStore(cp)
    store.create_snapshot(l1_snapshot={"feat-a": _feat("feat-a", ["A.m"])},
                          feature_relations=[], analyzed_files=[], commit_hash=None,
                          git_tags=[], trigger="manual", label="v1")
    out = await ic.execute({"codebase_path": str(cp), "version_ref": "v1"})
    assert "error" in out
    assert "structure" in out["error"].lower()
