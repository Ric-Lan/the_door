from the_door.core.structure_view import chunk_planner as cp


def _v(node_id, out=(), indeg=0):
    return {
        "node_id": node_id, "name": node_id.split("::")[-1],
        "topology": {"in_degree": indeg, "out_degree": len(out)},
        "in_edges": [], "out_edges": [{"to_node_id": t, "type": "calls"} for t in out],
    }


def test_in_degree_handles_none_topology():
    assert cp._in_degree({"topology": None}) == 0
    assert cp._in_degree({"topology": {"in_degree": 5}}) == 5
    assert cp._in_degree({}) == 0


def test_build_adjacency_is_undirected_and_skips_external():
    views = {
        "a::f": _v("a::f", out=("b::g", "ext::x")),   # ext::x 不在 views → 略過
        "b::g": _v("b::g"),
    }
    adj = cp.build_adjacency(views)
    assert adj["a::f"] == {"b::g"}
    assert adj["b::g"] == {"a::f"}        # 無向：反向也有
    assert "ext::x" not in adj


def test_connected_components_groups_and_isolates():
    views = {
        "a::f": _v("a::f", out=("b::g",)),
        "b::g": _v("b::g"),
        "z::lone": _v("z::lone"),          # 零邊 → 自成一分量
    }
    adj = cp.build_adjacency(views)
    comps = cp.connected_components(adj, views.keys())
    # 每分量已排序、分量間按首元素排序（決定性）
    assert comps == [["a::f", "b::g"], ["z::lone"]]


def test_connected_components_deterministic():
    views = {f"m::n{i}": _v(f"m::n{i}") for i in range(20)}
    adj = cp.build_adjacency(views)
    assert cp.connected_components(adj, views.keys()) == \
           cp.connected_components(adj, views.keys())
