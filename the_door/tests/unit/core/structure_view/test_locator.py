import pytest

from the_door.core.structure_view import locator


def test_load_views_missing_artifacts_raises(tmp_path):
    with pytest.raises(locator.LocateError, match="extract_structure"):
        locator.load_views(tmp_path)


def _view(node_id, name, in_degree):
    return {
        "node_id": node_id, "name": name, "type": "function",
        "file": node_id.split("::")[0], "start_line": 1, "end_line": 2,
        "topology": {"in_degree": in_degree, "out_degree": 0,
                     "topology_rank": 0.0, "is_entry_point": False},
        "in_edges": [], "out_edges": [],
    }


def test_search_views_name_match_ranks_before_path_match():
    views = {
        # path 命中（檔名含 user）且 in_degree 高
        "user_service.py::handle": _view("user_service.py::handle", "handle", 99),
        # name 命中（叫 user）但 in_degree 低
        "x.py::user": _view("x.py::user", "user", 1),
    }
    out = locator.search_views(views, "user")
    assert [r["node_id"] for r in out["results"]] == ["x.py::user", "user_service.py::handle"]
    assert out["results"][0]["match_kind"] == "name"
    assert out["results"][1]["match_kind"] == "path"


def test_search_views_empty_query_raises():
    with pytest.raises(locator.LocateError, match="query is required"):
        locator.search_views({}, "   ")


def test_search_views_limit_truncates():
    views = {f"f.py::n{i}": _view(f"f.py::n{i}", f"n{i}", i) for i in range(5)}
    out = locator.search_views(views, "n", limit=2)
    assert out["total_matched"] == 5
    assert out["returned"] == 2
    assert len(out["results"]) == 2


def test_search_views_no_match_returns_empty():
    out = locator.search_views({"f.py::a": _view("f.py::a", "a", 0)}, "zzz")
    assert out["results"] == []
    assert out["total_matched"] == 0


def test_in_degree_handles_none_topology():
    v = {"node_id": "f.py::a", "name": "a", "type": "function", "file": "f.py",
         "start_line": 1, "end_line": 2, "topology": None, "in_edges": [], "out_edges": []}
    out = locator.search_views({"f.py::a": v}, "a")
    assert out["results"][0]["in_degree"] == 0
