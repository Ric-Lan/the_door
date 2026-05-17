"""Shared response envelope helper for MCP tools.

Injects ``next_actions`` (computed via StateInspector + NextActionSuggester)
into a tool's response payload so callers always receive forward guidance.
"""
from pathlib import Path

from the_door.core.guidance.actions import ActionContext, to_json_dict as action_to_json
from the_door.core.guidance.state import StateInspector
from the_door.core.guidance.suggester import NextActionSuggester


def wrap(payload: dict, project_path: Path, context: ActionContext = "mcp") -> dict:
    """Inject ``next_actions`` into ``payload`` and return it.

    Mutates ``payload`` in place (also returns it for convenience).
    ``next_actions`` is a list of plain JSON-serializable dicts.
    """
    state = StateInspector(Path(project_path)).inspect()
    actions = NextActionSuggester().suggest(state, context=context)
    payload["next_actions"] = [action_to_json(a) for a in actions]
    return payload
