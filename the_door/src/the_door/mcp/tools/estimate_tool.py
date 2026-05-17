"""MCP tool: estimate — return cost estimation for a codebase."""
from __future__ import annotations

from pathlib import Path

from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.topology.topology_analyzer import TopologyAnalyzer
from the_door.core.llm.config_manager import ConfigManager
from the_door.core.rendering.cost_estimator import CostEstimator
from the_door.mcp.tools._response_envelope import wrap
from the_door.models import StructureJSON

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path"],
    "properties": {
        "codebase_path": {"type": "string", "description": "Path to the codebase root directory"},
        "provider": {"type": "string", "description": "LLM provider override"},
    },
}


async def execute(arguments: dict) -> dict:
    """Execute the estimate tool."""
    codebase_path = arguments.get("codebase_path", "")
    project_root = Path(arguments.get("codebase_path") or arguments.get("project_path") or Path.cwd())

    config = ConfigManager.load()
    if arguments.get("provider"):
        config.default_provider = arguments["provider"]

    provider_name = config.default_provider
    model_name = getattr(config, f"{provider_name}_model", "")

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

    estimator = CostEstimator(provider_name=provider_name, model_name=model_name)
    estimate = estimator.estimate(structure)

    return wrap({
        "provider": estimate.provider,
        "model": estimate.model,
        "batch_count": estimate.batch_count,
        "total_input_tokens": estimate.total_input_tokens,
        "total_output_tokens": estimate.total_output_tokens,
        "estimated_cost_usd": estimate.estimated_cost_usd,
        "is_local": estimate.is_local,
        "node_count": len(structure.nodes),
    }, project_path=project_root, context="mcp")
