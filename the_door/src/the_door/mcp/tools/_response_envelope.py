"""Shared response envelope helper for MCP tools.

Injects ``next_actions`` (computed via StateInspector + NextActionSuggester)
into a tool's response payload so callers always receive forward guidance.
"""
from pathlib import Path

from the_door.core.flow_guard import Decision
from the_door.core.guidance.actions import ActionContext, to_json_dict as action_to_json
from the_door.core.guidance.state import StateInspector
from the_door.core.guidance.suggester import NextActionSuggester


def wrap(payload: dict, project_path: Path, context: ActionContext = "mcp") -> dict:
    """Inject ``next_actions`` into ``payload`` and return it.

    If payload contains a ``_decision`` key with an unresolved Decision,
    returns a CHECKPOINT envelope (result=None) instead of the normal response.

    Mutates ``payload`` in place (also returns it for convenience).
    ``next_actions`` is a list of plain JSON-serializable dicts.
    """
    decision: Decision | None = payload.pop("_decision", None)
    if decision is not None and not decision.is_resolved:
        return {
            "checkpoint": decision.checkpoint_name,
            "status": decision.status,
            "options": [
                {"key": o.key, "label": o.label, "next_call": o.next_call}
                for o in decision.options
            ],
            "result": None,
        }

    state = StateInspector(Path(project_path)).inspect()
    actions = NextActionSuggester().suggest(state, context=context)
    payload["next_actions"] = [action_to_json(a) for a in actions]
    return payload
