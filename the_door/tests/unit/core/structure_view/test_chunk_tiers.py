from the_door.core.structure_view import chunk_planner as cp


def test_slice_by_order_fills_to_budget():
    est = {"a": 40, "b": 40, "c": 40}
    chunks = cp._slice_by_order(["a", "b", "c"], est, target=100)
    # a+b=80 ≤100；加 c=120>100 → 斷。第二塊 c。
    assert [c["node_ids"] for c in chunks] == [["a", "b"], ["c"]]
    assert chunks[0]["est_tokens"] == 80
    assert all(c["oversized"] is False for c in chunks)


def test_slice_by_order_oversized_node_own_chunk():
    est = {"a": 10, "big": 500, "b": 10}
    chunks = cp._slice_by_order(["a", "big", "b"], est, target=100)
    # a(10) 一塊；big 超標自成 oversized 塊；b(10) 一塊
    assert chunks[0]["node_ids"] == ["a"]
    assert chunks[1]["node_ids"] == ["big"] and chunks[1]["oversized"] is True
    assert chunks[2]["node_ids"] == ["b"]


def test_slice_by_order_empty():
    assert cp._slice_by_order([], {}, target=100) == []


def test_bfs_order_starts_at_highest_indegree_and_covers_component():
    # 鏈 a-b-c-d；indeg 設成 c 最高 → 從 c 起 BFS
    adj = {"a": {"b"}, "b": {"a", "c"}, "c": {"b", "d"}, "d": {"c"}}
    indeg = {"a": 0, "b": 1, "c": 9, "d": 0}
    order = cp._bfs_order(["a", "b", "c", "d"], adj, indeg)
    assert order[0] == "c"                 # 從最高 in_degree 起
    assert sorted(order) == ["a", "b", "c", "d"]   # 涵蓋整個分量
    assert len(order) == 4                 # 不重複


def test_bfs_order_deterministic():
    adj = {"a": {"b", "c"}, "b": {"a"}, "c": {"a"}}
    indeg = {"a": 5, "b": 0, "c": 0}
    assert cp._bfs_order(["a", "b", "c"], adj, indeg) == \
           cp._bfs_order(["a", "b", "c"], adj, indeg)


def test_pack_combines_components_under_budget():
    # 三個分量 60/30/30，target=100：first-fit-decreasing → [60+30], [30]
    fitting = [(["a"], 60), (["b"], 30), (["c"], 30)]
    bins = cp._pack(fitting, target=100)
    assert len(bins) == 2
    assert bins[0]["est_tokens"] == 90 and sorted(bins[0]["node_ids"]) == ["a", "b"]
    assert bins[1]["est_tokens"] == 30 and bins[1]["node_ids"] == ["c"]
    assert all(b["oversized"] is False for b in bins)


def test_pack_node_ids_sorted_and_deterministic():
    fitting = [(["z::2", "a::1"], 50), (["m::3"], 50)]
    bins = cp._pack(fitting, target=100)
    assert bins[0]["node_ids"] == ["a::1", "m::3", "z::2"]   # 合併後排序
    assert cp._pack(fitting, 100) == cp._pack(fitting, 100)
