"""MCP tool: snapshot_create — create a manual snapshot."""
from __future__ import annotations

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path"],
    "properties": {
        "codebase_path": {"type": "string", "description": "Path to the codebase root"},
        "label": {"type": "string", "description": "Optional snapshot label"},
    },
}


async def execute(arguments: dict) -> dict:
    """Execute the snapshot_create tool."""
    from pathlib import Path
    from the_door.core.diff.snapshot_store import SnapshotStore
    from the_door.models import SnapshotError

    codebase_path = arguments["codebase_path"]
    label = arguments.get("label")

    store = SnapshotStore(Path(codebase_path))
    latest = store.get_latest()
    if latest is None:
        return {"error": "No analysis output found. Run analysis first."}

    try:
        snapshot = store.create_snapshot(
            l1_snapshot=latest.l1_snapshot,
            feature_relations=latest.feature_relations_snapshot,
            analyzed_files=latest.analyzed_files,
            commit_hash=latest.commit_hash,
            git_tags=latest.git_tags,
            trigger="manual",
            label=label,
            l1_5_snapshot=latest.l1_5_snapshot if latest.l1_5_snapshot else None,
        )
    except SnapshotError as e:
        return {"error": str(e)}

    return {"version_id": snapshot.version_id, "label": snapshot.label}
