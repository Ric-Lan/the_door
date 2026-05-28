"""Tests for context_mode parameter in analyze_tool MCP surface."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from the_door.mcp.tools import analyze_tool


class TestToolSchema:
    def test_schema_declares_context_mode_property(self):
        props = analyze_tool.TOOL_SCHEMA.get("properties", {})
        assert "context_mode" in props

    def test_context_mode_enum_is_detail_or_minimal(self):
        props = analyze_tool.TOOL_SCHEMA["properties"]
        ctx = props["context_mode"]
        assert ctx.get("type") == "string"
        assert sorted(ctx.get("enum", [])) == ["detail", "minimal"]

    def test_context_mode_default_is_detail(self):
        props = analyze_tool.TOOL_SCHEMA["properties"]
        assert props["context_mode"].get("default") == "detail"

    def test_context_mode_not_in_required(self):
        required = analyze_tool.TOOL_SCHEMA.get("required", [])
        assert "context_mode" not in required


def _patch_execute_deps():
    """Context manager stack that stubs out all I/O so execute() reaches BatchReader."""
    mock_structure = MagicMock()
    mock_structure.files = []
    mock_structure.nodes = []
    mock_structure.edges = []
    mock_structure.topology = []

    mock_extractor = MagicMock()
    mock_extractor.extract.return_value = mock_structure

    mock_topo = MagicMock()
    mock_topo.entries = []

    mock_topo_analyzer = MagicMock()
    mock_topo_analyzer.analyze.return_value = mock_topo

    return mock_extractor, mock_topo_analyzer


class TestExecuteForwardsToBatchReader:
    def _invoke(self, arguments: dict):
        import asyncio
        mock_extractor, mock_topo_analyzer = _patch_execute_deps()
        with patch.object(analyze_tool, "ASTExtractor", return_value=mock_extractor), \
             patch.object(analyze_tool, "TopologyAnalyzer", return_value=mock_topo_analyzer), \
             patch.object(analyze_tool, "ConfigManager") as mock_cfg, \
             patch.object(analyze_tool, "create_provider", return_value=MagicMock()), \
             patch.object(analyze_tool, "BatchReader") as MockBR:
            mock_cfg.load.return_value = MagicMock()
            mock_reader = MagicMock()
            mock_reader.read = AsyncMock(return_value=MagicMock(
                l1_output=MagicMock(
                    summary="", features=[], feature_relations=[],
                    unclassified_nodes=[], infrastructure_nodes=[],
                ),
                total_batches=0, total_tokens_used=0, pruned_node_count=0,
            ))
            MockBR.return_value = mock_reader
            with patch("the_door.core.registry.ProjectRegistry"):
                try:
                    asyncio.run(analyze_tool.execute(arguments))
                except Exception:
                    pass
            return MockBR

    def test_passes_minimal_when_input_says_minimal(self):
        MockBR = self._invoke({"codebase_path": ".", "context_mode": "minimal"})
        assert MockBR.called
        assert MockBR.call_args.kwargs.get("context_mode") == "minimal"

    def test_defaults_to_detail_when_field_absent(self):
        MockBR = self._invoke({"codebase_path": "."})
        assert MockBR.called
        assert MockBR.call_args.kwargs.get("context_mode") == "detail"

    def test_rejects_invalid_context_mode(self):
        import asyncio
        mock_extractor, mock_topo_analyzer = _patch_execute_deps()
        with patch.object(analyze_tool, "ASTExtractor", return_value=mock_extractor), \
             patch.object(analyze_tool, "TopologyAnalyzer", return_value=mock_topo_analyzer), \
             patch.object(analyze_tool, "ConfigManager") as mock_cfg, \
             patch.object(analyze_tool, "create_provider", return_value=MagicMock()):
            mock_cfg.load.return_value = MagicMock()
            with pytest.raises((ValueError, Exception)):
                asyncio.run(analyze_tool.execute({"codebase_path": ".", "context_mode": "weird"}))
