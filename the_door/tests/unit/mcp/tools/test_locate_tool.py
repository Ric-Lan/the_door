import asyncio

import pytest

from the_door.mcp import server
from the_door.mcp.tools import locate_tool


@pytest.fixture()
def simple(fixtures_dir):
    return fixtures_dir / "sample_codebases" / "python_simple"


def test_locate_registered_in_server():
    assert "locate" in server.REGISTERED_TOOL_NAMES


def test_execute_search(simple):
    out = asyncio.run(locate_tool.execute(
        {"codebase_path": str(simple), "action": "search", "query": "login"}))
    assert "error" not in out
    assert any(r["node_id"] == "app.py::login" for r in out["results"])
    assert "next_actions" in out          # wrap 注入

def test_execute_node(simple):
    out = asyncio.run(locate_tool.execute(
        {"codebase_path": str(simple), "action": "node",
         "node_id": "auth.py::authenticate_user"}))
    assert "error" not in out
    assert any(c["node_id"] == "app.py::login" for c in out["callers"])


def test_execute_missing_codebase_path():
    out = asyncio.run(locate_tool.execute({"action": "search", "query": "x"}))
    assert out["error"] == "codebase_path is required"


def test_execute_unknown_action(simple):
    out = asyncio.run(locate_tool.execute(
        {"codebase_path": str(simple), "action": "bogus"}))
    assert "unknown action" in out["error"]


def test_execute_node_without_node_id(simple):
    out = asyncio.run(locate_tool.execute(
        {"codebase_path": str(simple), "action": "node"}))
    assert "node_id is required" in out["error"]
