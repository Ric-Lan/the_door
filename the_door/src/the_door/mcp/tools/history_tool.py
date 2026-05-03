"""MCP tool: history — return narrative chain for a codebase."""
from __future__ import annotations

from pathlib import Path

from the_door.core.reading.narrative_chain import NarrativeChain

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
    chain_path = Path(codebase_path) / ".the-door" / "narrative.jsonl"

    if not chain_path.exists():
        return {"records": [], "message": "No narrative chain found. Run analyze first."}

    chain = NarrativeChain(chain_path)
    records = chain.read_all()

    return {
        "record_count": len(records),
        "human_readable": chain.format_human_readable(),
    }
