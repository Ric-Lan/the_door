"""MCP tool: render — generate Mermaid text from L1 or L1.5 JSON."""
from __future__ import annotations

from pathlib import Path

from the_door.core.rendering.mermaid_renderer import MermaidRenderer
from the_door.mcp.tools._response_envelope import wrap
from the_door.models import (
    Feature, FeatureRelation, L1Output,
    L1_5Block, BlockRelation, InfrastructureBlock, L1_5Output,
)

TOOL_SCHEMA = {
    "type": "object",
    "required": ["output_json"],
    "properties": {
        "output_json": {"type": "object", "description": "L1 or L1.5 output JSON to render"},
    },
}


async def execute(arguments: dict) -> dict:
    """Execute the render tool."""
    data = arguments.get("output_json", {})
    project_root = Path(arguments.get("codebase_path") or arguments.get("project_path") or Path.cwd())
    renderer = MermaidRenderer()

    if "l1_5" in data:
        l1_5_data = data["l1_5"]
        blocks = [
            L1_5Block(
                block_id=b["block_id"], label=b["label"],
                responsibility=b["responsibility"],
                trigger_mechanism=b["trigger_mechanism"],
                related_features=b.get("related_features", []),
            )
            for b in l1_5_data.get("blocks", [])
        ]
        relations = [
            BlockRelation(
                from_block=r["from"], to_block=r["to"],
                relation=r["relation"], relation_type=r["relation_type"],
                inferred_reason=r.get("inferred_reason"),
            )
            for r in l1_5_data.get("block_relations", [])
        ]
        infra_data = l1_5_data.get("infrastructure_block")
        infra = InfrastructureBlock(
            label=infra_data["label"], components=infra_data.get("components", [])
        ) if infra_data else None
        l1_5 = L1_5Output(blocks=blocks, block_relations=relations, infrastructure_block=infra)
        mermaid = renderer.render_l1_5(l1_5)
    elif "l1" in data:
        l1_data = data["l1"]
        features = [
            Feature(
                feature_id=f["feature_id"], label=f["label"],
                description=f.get("description", ""), trigger=f.get("trigger", "user_action"),
                trigger_description=f.get("trigger_description", ""),
                confidence=f.get("confidence", "medium"),
                confidence_reason=f.get("confidence_reason", ""),
                source_nodes=f.get("source_nodes", []),
            )
            for f in l1_data.get("features", [])
        ]
        relations = [
            FeatureRelation(
                from_feature=r["from"], to_feature=r["to"],
                relation=r["relation"], relation_type=r["relation_type"],
                inferred_reason=r.get("inferred_reason"),
            )
            for r in l1_data.get("feature_relations", [])
        ]
        l1 = L1Output(summary=l1_data.get("summary", ""), features=features, feature_relations=relations)
        mermaid = renderer.render_l1(l1)
    else:
        return {"error": "Input must contain 'l1' or 'l1_5' key"}

    return wrap({"mermaid": mermaid}, project_path=project_root, context="mcp")
