"""MCP tool: snapshot_list — list all available snapshots."""
from __future__ import annotations

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path"],
    "properties": {
        "codebase_path": {"type": "string", "description": "Path to the codebase root"},
    },
}


async def execute(arguments: dict) -> dict:
    """Execute the snapshot_list tool."""
    from pathlib import Path
    from the_door.core.diff.snapshot_store import SnapshotStore

    codebase_path = arguments["codebase_path"]
    store = SnapshotStore(Path(codebase_path))
    snapshots = store.list_snapshots()

    return {
        "snapshots": [
            {
                "version_id": s.version_id,
                "timestamp": s.timestamp,
                "trigger": s.trigger,
                "commit_hash": s.commit_hash,
                "git_tags": s.git_tags,
                "label": s.label,
            }
            for s in snapshots
        ]
    }
