"""MCP tool: locate — symbol 定位點查 over 既有 structure-view（secondary，非主打）。"""
from __future__ import annotations

from pathlib import Path

from the_door.core.structure_view import locator
from the_door.mcp.tools._response_envelope import wrap

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path", "action"],
    "properties": {
        "codebase_path": {"type": "string", "description": "Path to the codebase root."},
        "action": {
            "type": "string",
            "enum": ["search", "node"],
            "description": "search=find symbols by name/path substring; node=detail of one node_id.",
        },
        "query": {"type": "string", "description": "search: substring matched against name and node_id."},
        "node_id": {"type": "string", "description": "node: the node_id to inspect (format file::symbol)."},
        "limit": {"type": "integer", "description": "search: max results (default 20)."},
    },
}


async def execute(arguments: dict) -> dict:
    codebase_path = arguments.get("codebase_path")
    if not codebase_path:
        return {"error": "codebase_path is required"}
    action = arguments.get("action")
    try:
        if action == "search":
            payload = locator.search(
                codebase_path,
                arguments.get("query", ""),
                arguments.get("limit") or locator.SEARCH_DEFAULT_LIMIT,
            )
        elif action == "node":
            node_id = arguments.get("node_id")
            if not node_id:
                return {"error": "node_id is required for action=node"}
            payload = locator.node(codebase_path, node_id)
        else:
            return {"error": f"unknown action: {action!r} (expected 'search' or 'node')"}
    except locator.LocateError as exc:
        return {"error": str(exc)}
    return wrap(payload, Path(codebase_path))
