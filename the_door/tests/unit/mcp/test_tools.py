"""Unit tests for MCP tools — extract_structure and validate_output."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp.types import ListToolsRequest
from the_door.mcp.server import TheDoorMCPServer


@pytest.fixture
def server():
    return TheDoorMCPServer()


@pytest.fixture
def fixtures_dir():
    return Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture
def sample_codebase(fixtures_dir):
    return str(fixtures_dir / "sample_codebases" / "python_simple")


async def _list_tools(server):
    """Helper to call the list_tools handler and return the tool list."""
    handler = server._server.request_handlers[ListToolsRequest]
    result = await handler(None)
    return result.root.tools


class TestToolRegistration:
    """Tests for MCP tool registration."""

    @pytest.mark.asyncio
    async def test_extract_structure_registered(self, server):
        """Test: extract_structure tool registered with correct name and parameters."""
        tools = await _list_tools(server)
        tool_names = [t.name for t in tools]
        assert "extract_structure" in tool_names

        extract_tool = next(t for t in tools if t.name == "extract_structure")
        assert "codebase_path" in extract_tool.inputSchema["properties"]
        assert "codebase_path" in extract_tool.inputSchema["required"]

    @pytest.mark.asyncio
    async def test_validate_output_registered(self, server):
        """Test: validate_output tool registered with correct name and parameters."""
        tools = await _list_tools(server)
        tool_names = [t.name for t in tools]
        assert "validate_output" in tool_names

        validate_tool = next(t for t in tools if t.name == "validate_output")
        assert "llm_output" in validate_tool.inputSchema["properties"]
        assert "structure_json" in validate_tool.inputSchema["properties"]

    @pytest.mark.asyncio
    async def test_snapshot_write_registered(self, server):
        """snapshot_write tool is registered with required fields."""
        tools = await _list_tools(server)
        tool_names = [t.name for t in tools]
        assert "snapshot_write" in tool_names

        tool = next(t for t in tools if t.name == "snapshot_write")
        schema = tool.inputSchema
        assert "codebase_path" in schema["required"]
        assert "l1_features" in schema["required"]
        assert "relations" in schema["properties"]
        assert "git_tags" in schema["properties"]

    @pytest.mark.asyncio
    async def test_project_list_registered(self, server):
        """project_list tool is registered."""
        tools = await _list_tools(server)
        tool_names = [t.name for t in tools]
        assert "project_list" in tool_names


class TestExtractStructureTool:
    """Tests for the extract_structure MCP tool."""

    @pytest.mark.asyncio
    async def test_extract_with_invalid_path(self, server):
        """Test: extract_structure with invalid path returns structured error."""
        result = await server._extract_structure({"codebase_path": "/nonexistent/path"})
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_extract_with_valid_path(self, server, sample_codebase):
        """Test: extract_structure with valid path returns Structure JSON."""
        result = await server._extract_structure({"codebase_path": sample_codebase})
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert "files" in data
        assert "nodes" in data
        assert "edges" in data
        assert "topology" in data


class TestExtractStructureOutput:
    """Tests for extract_structure response fields."""

    @pytest.mark.asyncio
    async def test_extract_structure_includes_analyzed_files(self, server, sample_codebase):
        """extract_structure result includes analyzed_files list."""
        result = await server._extract_structure({"codebase_path": sample_codebase})
        data = json.loads(result[0].text)

        assert "analyzed_files" in data
        assert isinstance(data["analyzed_files"], list)
        assert len(data["analyzed_files"]) > 0
        assert all(isinstance(f, str) for f in data["analyzed_files"])


class TestValidateOutputTool:
    """Tests for the validate_output MCP tool."""

    @pytest.mark.asyncio
    async def test_validate_with_malformed_input(self, server):
        """Test: validate_output with malformed input returns structured error."""
        result = await server._validate_output({
            "llm_output": {},
            "structure_json": {},
        })
        assert len(result) == 1
        data = json.loads(result[0].text)
        # Should return a result (possibly with failures) rather than crashing
        assert "passed" in data or "error" in data

    @pytest.mark.asyncio
    async def test_validate_with_valid_input(self, server, fixtures_dir):
        """Test: validate_output with valid input returns structured result."""
        l1_path = fixtures_dir / "sample_l1_output" / "valid_output.json"
        struct_path = fixtures_dir / "sample_structure_json" / "python_simple.json"

        with open(l1_path) as f:
            llm_output = json.load(f)
        with open(struct_path) as f:
            structure_json = json.load(f)

        result = await server._validate_output({
            "llm_output": llm_output,
            "structure_json": structure_json,
        })
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert "passed" in data
        assert "schema" in data
        assert "coverage" in data
        assert "language" in data
        assert "anchor" in data
        assert "relation" in data
