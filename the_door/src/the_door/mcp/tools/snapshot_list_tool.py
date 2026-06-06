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
    from the_door.core.diff.provenance_membrane import provenance_element_for
    from the_door.mcp.tools._response_envelope import wrap

    codebase_path = arguments["codebase_path"]
    project_root = Path(arguments.get("codebase_path") or arguments.get("project_path") or Path.cwd())
    store = SnapshotStore(Path(codebase_path))
    snapshots = store.list_snapshots()

    return wrap({
        "snapshots": [
            {
                "version_id": s.version_id,
                "timestamp": s.timestamp,
                "trigger": s.trigger,
                "commit_hash": s.commit_hash,
                "git_tags": s.git_tags,
                "label": s.label,
                "provenance": provenance_element_for(s.contract_version).to_json(),
            }
            for s in snapshots
        ]
    }, project_path=project_root, context="mcp")
