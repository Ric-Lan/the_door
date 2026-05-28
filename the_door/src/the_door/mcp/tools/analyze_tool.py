"""MCP tool: analyze — execute complete one-click pipeline."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.topology.topology_analyzer import TopologyAnalyzer
from the_door.core.llm.config_manager import ConfigManager
from the_door.core.llm.provider import create_provider
from the_door.core.reading.batch_reader import BatchReader
from the_door.mcp.tools._response_envelope import wrap
from the_door.models import StructureJSON


TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path"],
    "properties": {
        "codebase_path": {"type": "string", "description": "Path to the codebase root directory"},
        "provider": {"type": "string", "description": "LLM provider override (openai/anthropic/ollama)"},
        "model": {"type": "string", "description": "Model name override"},
        "context_mode": {
            "type": "string",
            "enum": ["detail", "minimal"],
            "default": "detail",
            "description": (
                "LLM 接收節點資訊的詳細度。"
                "'detail'（預設）：送節點完整 signature/docstring/decorators，翻譯品質較高。"
                "'minimal'：只送 node_id 字串，token 用量低但翻譯品質會回到 v1.3.6 前的水準。"
            ),
        },
    },
}


async def execute(arguments: dict) -> dict:
    """Execute the analyze tool."""
    codebase_path = arguments.get("codebase_path", "")
    project_root = Path(arguments.get("codebase_path") or arguments.get("project_path") or Path.cwd())

    config = ConfigManager.load()
    if arguments.get("provider"):
        config.default_provider = arguments["provider"]

    extractor = ASTExtractor()
    extraction = extractor.extract(Path(codebase_path))

    analyzer = TopologyAnalyzer()
    topo_result = analyzer.analyze(extraction.nodes, extraction.edges)

    structure = StructureJSON(
        files=extraction.files,
        nodes=extraction.nodes,
        edges=extraction.edges,
        topology=topo_result.entries,
    )

    context_mode = arguments.get("context_mode", "detail")
    if context_mode not in ("detail", "minimal"):
        raise ValueError(
            f"context_mode must be 'detail' or 'minimal', got {context_mode!r}"
        )

    llm_provider = create_provider(config)
    reader = BatchReader(llm_provider=llm_provider, structure=structure, context_mode=context_mode)
    from the_door.core.rendering.mermaid_renderer import build_confidence_marker

    result = await reader.read()

    from the_door.core.registry import ProjectRegistry
    ProjectRegistry().register(codebase_path)
    return wrap({
        "l1": {
            "summary": result.l1_output.summary,
            "features": [
                {
                    "feature_id": f.feature_id,
                    "label": f.label,
                    "description": f.description,
                    "confidence": f.confidence,
                    "source_nodes": list(f.source_nodes),
                    "confidence_marker": build_confidence_marker(f),
                }
                for f in result.l1_output.features
            ],
        },
        "meta": {
            "total_batches": result.total_batches,
            "total_tokens": result.total_tokens_used,
            "pruned_nodes": result.pruned_node_count,
        },
    }, project_path=project_root, context="mcp")
