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


def test_connected_components_dense_component_ordering_fixed():
    # 稠密分量（多邊）→ 考驗 set 迭代序是否影響輸出；comp 排序應吸收之
    views = {
        "p::a": _v("p::a", out=("p::b", "p::c")),
        "p::b": _v("p::b", out=("p::c",)),
        "p::c": _v("p::c", out=("p::a",)),          # 三角 + 回邊
        "q::x": _v("q::x"),                          # 獨立節點
    }
    adj = cp.build_adjacency(views)
    comps = cp.connected_components(adj, views.keys())
    # 整個三角為一分量、排序固定；q::x 獨立
    assert comps == [["p::a", "p::b", "p::c"], ["q::x"]]


def test_build_adjacency_skips_self_loop():
    # 守住 tid != nid guard：自環不應出現在鄰接
    views = {"s::f": _v("s::f", out=("s::f",))}
    adj = cp.build_adjacency(views)
    assert adj["s::f"] == set()
