from the_door.core.structure_view import chunk_planner as cp


def test_triage_small_no_split():
    assert cp.triage(50, target=100, large_ratio=8) == ("small", False)
    assert cp.triage(100, target=100, large_ratio=8) == ("small", False)  # 邊界 ≤


def test_triage_medium():
    assert cp.triage(101, target=100, large_ratio=8) == ("medium", True)
    assert cp.triage(800, target=100, large_ratio=8) == ("medium", True)  # 邊界 ≤ ratio×


def test_triage_large():
    assert cp.triage(801, target=100, large_ratio=8) == ("large", True)


def test_cross_chunk_edges_counts_cut_edges_once():
    # 邊 a-b（同塊）、b-c（跨塊）。無向各存兩向，但只算一次。
    adj = {"a": {"b"}, "b": {"a", "c"}, "c": {"b"}}
    chunks = [{"node_ids": ["a", "b"]}, {"node_ids": ["c"]}]
    assert cp._cross_chunk_edges(adj, chunks) == 1


def test_assemble_shape_and_chunk_ids():
    chunks = [
        {"node_ids": ["a::1"], "est_tokens": 10, "oversized": False, "tier": "cohesion"},
        {"node_ids": ["b::2"], "est_tokens": 999, "oversized": True, "tier": "oversized"},
    ]
    out = cp._assemble(target=100, regime="medium", needs_split=True,
                       total=1009, chunks=chunks, cross=0, warnings=["b::2"])
    assert out["target_tokens"] == 100
    assert out["regime"] == "medium" and out["needs_split"] is True
    assert out["total_est_tokens"] == 1009
    assert [c["chunk_id"] for c in out["chunks"]] == ["chunk-001", "chunk-002"]
    assert out["chunks"][0]["tier"] == "cohesion"
    assert out["rollup"]["chunk_count"] == 2
    assert out["rollup"]["oversized_node_warnings"] == ["b::2"]
    # oversized 內部旗標不外洩到輸出 chunk
    assert "oversized" not in out["chunks"][0]
