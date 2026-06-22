import pytest

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


@pytest.fixture()
def simple(fixtures_dir):
    return fixtures_dir / "sample_codebases" / "python_simple"


def _all_node_ids(out):
    ids = []
    for c in out["chunks"]:
        ids.extend(c["node_ids"])
    return ids


def _node(node_id, out=(), indeg=0, pad=""):
    return {
        "node_id": node_id, "name": node_id.split("::")[-1],
        "language": "python", "file": node_id.split("::")[0],
        "start_line": 1, "end_line": 2,
        "topology": {"in_degree": indeg, "out_degree": len(out),
                     "topology_rank": 0.0, "is_entry_point": False},
        "in_edges": [],
        "out_edges": [{"to_node_id": t, "type": "calls", "resolution": "scope_rule"} for t in out],
        "docstring": pad,
    }


# --- 合成 views 精確測各 tier（不依賴磁碟、估值由估計器推導不寫死） ---

def test_plan_from_views_cohesion_two_components_cut_free():
    views = {
        "m/a.py::a": _node("m/a.py::a", out=("m/a.py::b",)),
        "m/a.py::b": _node("m/a.py::b"),
        "n/x.py::x": _node("n/x.py::x", out=("n/x.py::y",)),
        "n/x.py::y": _node("n/x.py::y"),
    }
    est = {k: cp.estimate_tokens(v) for k, v in views.items()}
    comp1 = est["m/a.py::a"] + est["m/a.py::b"]
    total = sum(est.values())
    target = max(comp1, total - comp1)   # 各分量塞得下、兩者併不下 → 兩塊、cut-free
    out = cp._plan_from_views(views, target_tokens=target)
    assert out["needs_split"] is True
    assert out["rollup"]["cross_chunk_edges"] == 0
    assert all(c["tier"] == "cohesion" for c in out["chunks"])


def test_plan_from_views_zero_edge_packing_cut_free():
    views = {f"f.py::n{i}": _node(f"f.py::n{i}") for i in range(6)}
    est = {k: cp.estimate_tokens(v) for k, v in views.items()}
    total = sum(est.values())
    out = cp._plan_from_views(views, target_tokens=total // 2)  # 強制 >1 塊
    assert out["needs_split"] is True
    assert out["rollup"]["cross_chunk_edges"] == 0
    ids = [n for c in out["chunks"] for n in c["node_ids"]]
    assert sorted(ids) == sorted(views)


def test_plan_from_views_bisect_single_oversized_component():
    views = {
        "c.py::a": _node("c.py::a", out=("c.py::b",), indeg=0),
        "c.py::b": _node("c.py::b", out=("c.py::c",), indeg=1),
        "c.py::c": _node("c.py::c", indeg=1),
    }
    est = {k: cp.estimate_tokens(v) for k, v in views.items()}
    total = sum(est.values())
    out = cp._plan_from_views(views, target_tokens=total - 1)   # 容不下整條 → 切
    assert out["needs_split"] is True
    assert len(out["chunks"]) >= 2
    assert any(c["tier"] == "bisect" for c in out["chunks"])
    ids = [n for c in out["chunks"] for n in c["node_ids"]]
    assert sorted(ids) == sorted(views)


def test_plan_from_views_oversized_single_node():
    views = {
        "big.py::huge": _node("big.py::huge", pad="說" * 500),  # 大 docstring → 高估值
        "s.py::s": _node("s.py::s"),
    }
    est = {k: cp.estimate_tokens(v) for k, v in views.items()}
    target = est["s.py::s"] + 1     # 容得下 small、容不下 huge
    out = cp._plan_from_views(views, target_tokens=target)
    assert out["needs_split"] is True
    huge = [c for c in out["chunks"] if c["node_ids"] == ["big.py::huge"]]
    assert len(huge) == 1 and huge[0]["tier"] == "oversized"
    assert "big.py::huge" in out["rollup"]["oversized_node_warnings"]


def test_plan_small_regime_single_chunk(simple):
    # 預設大預算 → 整個 6 節點專案 ≤ 預算 → 不切
    out = cp.plan(simple)   # 預設 target=100_000
    assert out["regime"] == "small"
    assert out["needs_split"] is False
    assert len(out["chunks"]) == 1
    assert out["chunks"][0]["tier"] == "whole"
    assert len(out["chunks"][0]["node_ids"]) == 6


def test_plan_split_covers_all_nodes_and_respects_budget(simple):
    # 極小預算強制切分
    out = cp.plan(simple, target_tokens=80)
    assert out["needs_split"] is True
    assert out["regime"] in ("medium", "large")
    # 窮盡且不重：所有節點恰好出現一次
    ids = _all_node_ids(out)
    assert sorted(ids) == sorted(set(ids))          # 不重
    assert set(ids) == set(cp.load_views(simple))   # 窮盡（= 全部 6 節點）
    # 預算遵守：每塊 ≤ 預算，除非該塊是 oversized 單節點
    for c in out["chunks"]:
        assert c["est_tokens"] <= 80 or (c["tier"] == "oversized" and len(c["node_ids"]) == 1)
    # rollup 欄位齊
    assert out["rollup"]["chunk_count"] == len(out["chunks"])
    assert out["rollup"]["cross_chunk_edges"] >= 0


def test_plan_deterministic(simple):
    assert cp.plan(simple, target_tokens=80) == cp.plan(simple, target_tokens=80)


def test_plan_missing_structure_view_raises(tmp_path):
    from the_door.core.structure_view.locator import LocateError
    with pytest.raises(LocateError):
        cp.plan(tmp_path)
