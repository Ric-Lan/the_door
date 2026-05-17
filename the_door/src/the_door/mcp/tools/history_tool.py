"""MCP tool: history — return narrative chain for a codebase."""
from __future__ import annotations

from pathlib import Path

from the_door.core.reading.narrative_chain import NarrativeChain
from the_door.mcp.tools._response_envelope import wrap

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path"],
    "properties": {
        "codebase_path": {"type": "string", "description": "Path to the codebase root directory"},
    },
}


async def execute(arguments: dict) -> dict:
    """Execute the history tool."""
    codebase_path = arguments.get("codebase_path", "")
    project_root = Path(arguments.get("codebase_path") or arguments.get("project_path") or Path.cwd())
    chain_path = Path(codebase_path) / ".the-door" / "narrative.jsonl"

    if not chain_path.exists():
        return wrap(
            {"records": [], "message": "No narrative chain found. Run analyze first."},
            project_path=project_root,
            context="mcp",
        )

    chain = NarrativeChain(chain_path)
    records = chain.read_all()

    return wrap({
        "record_count": len(records),
        "human_readable": chain.format_human_readable(),
    }, project_path=project_root, context="mcp")
