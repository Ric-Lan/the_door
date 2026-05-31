"""MCP tool: localize_data_model — Tier 0 local localization (zero token)."""
from __future__ import annotations

from pathlib import Path

from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.datamodel.datamodel_localizer import DataModelLocalizer
from the_door.mcp.tools._response_envelope import wrap

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path"],
    "properties": {
        "codebase_path": {
            "type": "string",
            "description": "Path to the codebase root.",
        },
    },
}


async def execute(arguments: dict) -> dict:
    codebase_path = arguments.get("codebase_path")
    if not codebase_path:
        return {"error": "codebase_path is required"}
    result = ASTExtractor().extract(codebase_path)
    loc = DataModelLocalizer().localize(result, codebase_path)
    payload = {
        "code_candidates": [
            {"node_id": c.node_id, "file": c.file, "flagged_reason": c.flagged_reason}
            for c in loc.code_candidates
        ],
        "schema_candidates": [
            {"file": c.file, "flagged_reason": c.flagged_reason}
            for c in loc.schema_candidates
        ],
    }
    return wrap(payload, Path(codebase_path))
