"""region_partition 單元測試：決定性、流向計數、退化案例。"""
from the_door.core.structure_view.region_partition import Region, partition
from the_door.models import ASTNode, Edge


def _node(node_id: str) -> ASTNode:
    return ASTNode(node_id=node_id, type="function", name=node_id.rsplit("::", 1)[-1],
                   file="", language="python")


def _edges_fixture() -> tuple[list[ASTNode], list[Edge]]:
    nodes = [
        _node("src/a.py::f1"), _node("src/a.py::f2"),
        _node("tests/test_a.py::t1"), _node("tests/test_a.py::t2"),
    ]
    edges = [
        Edge(from_node="src/a.py::f1", to_node="src/a.py::f2", type="calls"),          # internal src
        Edge(from_node="tests/test_a.py::t1", to_node="src/a.py::f1", type="calls"),   # tests -> src
        Edge(from_node="tests/test_a.py::t2", to_node="src/a.py::f1", type="calls"),   # tests -> src
        Edge(from_node="tests/test_a.py::t1", to_node="tests/test_a.py::t2", type="calls"),  # internal tests
    ]
    return nodes, edges


def test_partition_flow_matrix_counts():
    nodes, edges = _edges_fixture()
    regions = {r.region_id: r for r in partition(nodes, edges)}
    assert set(regions) == {"src", "tests"}
    src, tests = regions["src"], regions["tests"]
    assert src.internal_edges == 1 and src.inbound_edges == 2 and src.outbound_edges == 0
    assert tests.internal_edges == 1 and tests.inbound_edges == 0 and tests.outbound_edges == 2
    assert tests.flow_to == {"src": 2} and src.flow_from == {"tests": 2}


def test_partition_is_deterministic():
    nodes, edges = _edges_fixture()
    a = partition(nodes, edges)
    b = partition(list(reversed(nodes)), list(reversed(edges)))
    assert a == b  # frozen dataclass 等值＝排序穩定


def test_partition_degenerate_single_root():
    nodes = [_node("src/a.py::f1"), _node("src/b.py::f2")]
    edges = [Edge(from_node="src/a.py::f1", to_node="src/b.py::f2", type="calls")]
    regions = partition(nodes, edges)
    assert len(regions) == 1 and regions[0].region_id == "src"
    assert regions[0].outbound_edges == 0 and regions[0].inbound_edges == 0
    assert regions[0].internal_edges == 1


def test_partition_rootlevel_node_gets_safe_region_id():
    nodes = [_node("setup.py::main")]
    regions = partition(nodes, [])
    assert regions[0].region_id == "_root_"  # 無 "/" → fs-safe 桶名
