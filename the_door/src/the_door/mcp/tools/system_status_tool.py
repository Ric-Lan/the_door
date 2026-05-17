"""system_status MCP tool — report current project state + next-action suggestions."""
from __future__ import annotations

from pathlib import Path

from the_door.core.guidance.state import StateInspector, to_json_dict as state_to_json
from the_door.core.guidance.suggester import NextActionSuggester
from the_door.core.guidance.actions import to_json_dict as action_to_json


TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "project_path": {"type": "string", "description": "Defaults to CWD if omitted."},
    },
    "required": [],
}


async def execute(arguments: dict) -> dict:
    project_path = Path(arguments.get("project_path", "."))
    state = StateInspector(project_path).inspect()
    actions = NextActionSuggester().suggest(state, context="mcp")
    return {
        "state": state_to_json(state),
        "next_actions": [action_to_json(a) for a in actions],
    }
