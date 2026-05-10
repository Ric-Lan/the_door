"""MCP tool: project_list — list all projects registered in ProjectRegistry."""
from __future__ import annotations

from the_door.core.registry import ProjectRegistry

TOOL_SCHEMA = {
    "type": "object",
    "properties": {},
}


async def execute(arguments: dict) -> dict:
    """Return all registered projects from ~/.the-door/registry.json."""
    projects = ProjectRegistry().list_projects()
    return {
        "projects": projects,
        "count": len(projects),
    }
