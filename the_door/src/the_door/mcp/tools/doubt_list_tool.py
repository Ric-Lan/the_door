"""MCP tool: doubt_list — list doubt records with optional filters."""
from __future__ import annotations

from the_door.core.scope import doubt_membrane

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "codebase_path": {
            "type": "string",
            "description": "Codebase 根目錄路徑（預設 '.'）",
        },
        "state": doubt_membrane.state_filter_schema(),
        "type": doubt_membrane.type_filter_schema(),
    },
}


async def execute(arguments: dict) -> dict:
    from pathlib import Path
    from the_door.core.scope.doubt_store import DoubtStore
    from the_door.mcp.tools._response_envelope import wrap

    codebase_path = arguments.get("codebase_path", ".")
    state_filter = arguments.get("state")
    type_filter = arguments.get("type")

    project_root = Path(codebase_path)
    store = DoubtStore(project_root)

    states = [state_filter] if state_filter else None
    types = [type_filter] if type_filter else None

    doubts = store.list_doubts(states=states, types=types)

    from the_door.core.scope.doubt_membrane import project_doubt

    return wrap({
        "doubts": [project_doubt(d) for d in doubts],
        "total": len(doubts),
    }, project_path=project_root, context="mcp")
