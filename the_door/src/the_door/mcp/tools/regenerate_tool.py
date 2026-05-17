"""MCP tool: regenerate — per-node re-analysis."""
from __future__ import annotations

from pathlib import Path

from the_door.mcp.tools._response_envelope import wrap

TOOL_SCHEMA = {
    "type": "object",
    "required": ["feature_id"],
    "properties": {
        "feature_id": {"type": "string", "description": "Feature ID to regenerate"},
        "codebase_path": {"type": "string", "description": "Path to the codebase"},
    },
}


async def execute(arguments: dict) -> dict:
    """Execute the regenerate tool."""
    feature_id = arguments.get("feature_id", "")
    project_root = Path(arguments.get("codebase_path") or arguments.get("project_path") or Path.cwd())
    return wrap({
        "feature_id": feature_id,
        "status": "requires_prior_analysis",
        "message": "Run analyze first, then regenerate specific features.",
    }, project_path=project_root, context="mcp")
