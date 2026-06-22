import pytest

from the_door.core.structure_view import locator


@pytest.fixture()
def simple(fixtures_dir):
    return fixtures_dir / "sample_codebases" / "python_simple"


def test_load_views_real_fixture(simple):
    views = locator.load_views(simple)
    assert "app.py::login" in views
    assert len(views) == 6


def test_search_real_fixture_name_before_path(simple):
    # "auth": authenticate_user 為 name 命中、generate_token 為 path 命中（檔名 auth.py）
    out = locator.search(simple, "auth")
    ids = [r["node_id"] for r in out["results"]]
    assert ids.index("auth.py::authenticate_user") < ids.index("auth.py::generate_token")
    kinds = {r["node_id"]: r["match_kind"] for r in out["results"]}
    assert kinds["auth.py::authenticate_user"] == "name"
    assert kinds["auth.py::generate_token"] == "path"
    assert out["freshness"]["status"] == "unknown"   # fixture 無 checklist.json


def test_node_real_fixture_callers_callees(simple):
    out = locator.node(simple, "auth.py::authenticate_user")
    caller_ids = {c["node_id"] for c in out["callers"]}
    callee_ids = {c["node_id"] for c in out["callees"]}
    assert "app.py::login" in caller_ids
    assert "auth.py::generate_token" in callee_ids
    assert out["file"] == "auth.py"
    assert out["start_line"] == 4
