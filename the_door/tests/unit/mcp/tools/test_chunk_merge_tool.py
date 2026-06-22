import asyncio
import pytest

from the_door.mcp import server
from the_door.mcp.tools import chunk_merge_tool


@pytest.fixture()
def simple(fixtures_dir):
    return str(fixtures_dir / "sample_codebases" / "python_simple")


def _feat(fid, nodes):
    return {"feature_id": fid, "label": fid, "description": "d",
            "confidence": "high", "source_nodes": list(nodes)}


def test_chunk_merge_registered():
    assert "chunk_merge" in server.REGISTERED_TOOL_NAMES


def test_execute_normal(simple):
    chunks = [
        {"chunk_id": "c001", "features": [_feat("feat-c001-login", ["app.py::login"])]},
        {"chunk_id": "c002", "features": [_feat("feat-c002-auth", ["auth.py::authenticate_user"])]},
    ]
    out = asyncio.run(chunk_merge_tool.execute({"codebase_path": simple, "chunks": chunks}))
    assert "error" not in out
    assert out["rollup"]["feature_count"] == 2
    assert "next_actions" in out          # wrap 注入
    assert any(r["relation_type"] == "static" for r in out["relations"])


def test_execute_missing_codebase_path():
    out = asyncio.run(chunk_merge_tool.execute({"chunks": [{"chunk_id": "c", "features": []}]}))
    assert out["error"] == "codebase_path is required"


def test_execute_empty_chunks(simple):
    out = asyncio.run(chunk_merge_tool.execute({"codebase_path": simple, "chunks": []}))
    assert "chunks is required" in out["error"]


def test_execute_duplicate_feature_id(simple):
    chunks = [
        {"chunk_id": "c001", "features": [_feat("feat-dup", ["app.py::login"])]},
        {"chunk_id": "c002", "features": [_feat("feat-dup", ["auth.py::generate_token"])]},
    ]
    out = asyncio.run(chunk_merge_tool.execute({"codebase_path": simple, "chunks": chunks}))
    assert "duplicate feature_id" in out["error"]
