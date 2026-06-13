"""node_view：單 node 多軸並置（屬性+出入邊+topology+殘餘基數），統一 node_id 定址。"""
from the_door.core.structure_view.node_view import assemble_views
from the_door.models import ASTNode, Edge, TopologyEntry


def _fixture():
    nodes = [
        ASTNode(node_id="src/a.py::f1", type="function", name="f1", file="src/a.py",
                language="python", docstring="calls f2"),
        ASTNode(node_id="src/b.py::f2", type="function", name="f2", file="src/b.py",
                language="python"),
    ]
    edges = [
        Edge(from_node="src/a.py::f1", to_node="src/b.py::f2", type="calls", resolution="scope_rule"),
        Edge(from_node="src/a.py::f1", to_node="src/b.py::f2", type="imports", resolution="import_alias"),
    ]
    topo = [
        TopologyEntry(node_id="src/a.py::f1", in_degree=0, out_degree=2,
                      topology_rank=1, is_entry_point=True, batch_assignment=1),
        TopologyEntry(node_id="src/b.py::f2", in_degree=2, out_degree=0,
                      topology_rank=2, is_entry_point=False, batch_assignment=2),
    ]
    residue = {
        "indeterminate": [],
        "low_confidence_ambiguous": [{"caller": "src/a.py::f1", "methods": {"py::x": 3}, "cardinality": 3}],
    }
    return nodes, edges, topo, residue


def test_view_unified_node_id_addressing():
    nodes, edges, topo, residue = _fixture()
    views = assemble_views(nodes, edges, topo, residue)
    v = views["src/a.py::f1"]
    assert v["node_id"] == "src/a.py::f1"
    assert v["out_edges"] == [
        {"to_node_id": "src/b.py::f2", "type": "calls", "resolution": "scope_rule"},
        {"to_node_id": "src/b.py::f2", "type": "imports", "resolution": "import_alias"},
    ]
    assert views["src/b.py::f2"]["in_edges"] == [
        {"from_node_id": "src/a.py::f1", "type": "calls", "resolution": "scope_rule"},
        {"from_node_id": "src/a.py::f1", "type": "imports", "resolution": "import_alias"},
    ]


def test_view_coalesces_topology_and_attrs():
    nodes, edges, topo, residue = _fixture()
    v = assemble_views(nodes, edges, topo, residue)["src/a.py::f1"]
    assert v["topology"] == {"in_degree": 0, "out_degree": 2, "topology_rank": 1,
                             "is_entry_point": True, "batch_assignment": 1}
    assert v["docstring"] == "calls f2"  # 屬性與拓撲並置＝跨軸矛盾可偵測（F-b 教訓）


def test_view_residue_cardinality_reference_not_copy():
    nodes, edges, topo, residue = _fixture()
    v = assemble_views(nodes, edges, topo, residue)["src/a.py::f1"]
    # 只存基數引用（座標+基數可下鑽），完整條目留在 .the-door/edge-residue.json
    assert v["residue_as_caller"] == {"low_confidence_ambiguous": 1, "indeterminate": 0}


def test_view_deterministic_edge_order():
    nodes, edges, topo, residue = _fixture()
    a = assemble_views(nodes, edges, topo, residue)
    b = assemble_views(nodes, list(reversed(edges)), topo, residue)
    assert a == b


def test_view_includes_start_and_end_line():
    nodes = [
        ASTNode(node_id="src/a.py::f1", type="function", name="f1",
                file="src/a.py", language="python", start_line=3, end_line=7),
        ASTNode(node_id="src/b.py::f2", type="function", name="f2",
                file="src/b.py", language="python"),  # start_line=None
    ]
    views = assemble_views(nodes, [], [], {})
    assert views["src/a.py::f1"]["start_line"] == 3
    assert views["src/a.py::f1"]["end_line"] == 7
    assert views["src/b.py::f2"]["start_line"] is None
    assert views["src/b.py::f2"]["end_line"] is None
