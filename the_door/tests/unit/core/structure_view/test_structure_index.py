"""structure_index：索引完整性（基數/比例/位址/大小）、artifact round-trip、標註不過濾。"""
import gzip
import json

from the_door.core.structure_view.structure_index import write_artifacts
from the_door.models import ASTNode, Edge, StructureJSON, TopologyEntry


def _structure(n_tests: int = 60) -> StructureJSON:
    """src 2 nodes；tests n_tests nodes，全部單向打進 src（觸發撥離）。"""
    nodes = [
        ASTNode(node_id="src/a.py::f1", type="function", name="f1", file="src/a.py", language="python"),
        ASTNode(node_id="src/a.py::f2", type="function", name="f2", file="src/a.py", language="python"),
    ]
    edges = [Edge(from_node="src/a.py::f1", to_node="src/a.py::f2", type="calls")]
    topo = [
        TopologyEntry(node_id="src/a.py::f1", in_degree=n_tests, out_degree=1,
                      topology_rank=1, is_entry_point=True, batch_assignment=1),
        TopologyEntry(node_id="src/a.py::f2", in_degree=1, out_degree=0,
                      topology_rank=2, is_entry_point=False, batch_assignment=2),
    ]
    for i in range(n_tests):
        nid = f"tests/test_a.py::t{i}"
        nodes.append(ASTNode(node_id=nid, type="function", name=f"t{i}",
                             file="tests/test_a.py", language="python"))
        edges.append(Edge(from_node=nid, to_node="src/a.py::f1", type="calls"))
        topo.append(TopologyEntry(node_id=nid, in_degree=0, out_degree=1,
                                  topology_rank=10 + i, is_entry_point=True, batch_assignment=1))
    return StructureJSON(files=[], nodes=nodes, edges=edges, topology=topo)


_EMPTY_RESIDUE = {"indeterminate": [], "low_confidence_ambiguous": []}


def test_index_entries_complete(tmp_path):
    index = write_artifacts(str(tmp_path), _structure(), _EMPTY_RESIDUE)
    assert index["totals"] == {"files": 0, "nodes": 62, "edges": 61, "regions": 2}
    by_id = {r["region_id"]: r for r in index["regions"]}
    tests = by_id["tests"]
    assert tests["node_count"] == 60 and tests["share_pct"] == 96.8
    assert tests["edges"] == {"internal": 0, "inbound": 0, "outbound": 60}
    assert tests["batches"] == {"1": 60}
    assert tests["artifact_path"].endswith("tests.json.gz")
    assert tests["size_bytes"] > 0
    assert tests["peel"]["reason"]["value"] == "one_way_consumer"
    assert by_id["src"]["peel"] is None


def test_artifacts_roundtrip_and_no_filtering(tmp_path):
    write_artifacts(str(tmp_path), _structure(), _EMPTY_RESIDUE)
    view_dir = tmp_path / ".the-door" / "structure-view"
    assert (view_dir / "index.json").is_file()
    # 被撥離區資料完整在檔（標註不過濾的結構性證明）
    with gzip.open(view_dir / "regions" / "tests.json.gz", "rt", encoding="utf-8") as f:
        region = json.load(f)
    assert region["region_id"] == "tests" and len(region["nodes"]) == 60
    assert region["nodes"][0]["node_id"].startswith("tests/")
    # 全量 raw structure round-trip（供 validate_output 接縫）
    with gzip.open(view_dir / "structure.full.json.gz", "rt", encoding="utf-8") as f:
        full = json.load(f)
    assert len(full["nodes"]) == 62 and len(full["edges"]) == 61 and len(full["topology"]) == 62


def test_index_has_consumption_guide(tmp_path):
    index = write_artifacts(str(tmp_path), _structure(), _EMPTY_RESIDUE)
    guide = index["consumption_guide"]
    assert "batch" in guide["batch_semantics"]  # 批次語義必須被解釋（F-d 教訓）
    assert guide["addressing"] == "node_id"
    assert index["artifact_dir"].endswith("structure-view")
