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
from the_door.models import StructureJSON


TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path"],
    "properties": {
        "codebase_path": {"type": "string", "description": "Path to the codebase root directory"},
        "provider": {"type": "string", "description": "LLM provider override (openai/anthropic/ollama)"},
        "model": {"type": "string", "description": "Model name override"},
    },
}


async def execute(arguments: dict) -> dict:
    """Execute the analyze tool."""
    codebase_path = arguments.get("codebase_path", "")

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

    llm_provider = create_provider(config)
    reader = BatchReader(llm_provider=llm_provider, structure=structure)
    from the_door.core.rendering.mermaid_renderer import build_confidence_marker

    result = await reader.read()

    return {
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
    }
