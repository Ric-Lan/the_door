"""MCP tool: project_list — list all projects registered in ProjectRegistry."""
from __future__ import annotations

from pathlib import Path

from the_door.core.registry import ProjectRegistry
from the_door.mcp.tools._response_envelope import wrap

TOOL_SCHEMA = {
    "type": "object",
    "properties": {},
}


async def execute(arguments: dict) -> dict:
    """Return all registered projects from ~/.the-door/registry.json."""
    projects = ProjectRegistry().list_projects()
    return wrap({
        "projects": projects,
        "count": len(projects),
    }, project_path=Path.cwd(), context="mcp")
