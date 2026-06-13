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

    missing = sum(1 for s in snapshots if not s.version_narratives)
    has_narrative = len(snapshots) - missing

    if missing > 0:
        note = (
            f"{missing} 個 snapshot 缺少 version_narrative。"
            "寫入前請向使用者確認要翻譯的 baseline-current 配對，不得自行決定範圍。"
        )
    else:
        note = "所有 snapshot 均已有 version_narrative。"

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
                "has_project_summary": s.project_summary is not None,
                "has_version_narrative": bool(s.version_narratives),
                "narrative_baselines": list(s.version_narratives.keys()),
            }
            for s in snapshots
        ],
        "narrative_summary": {
            "total": len(snapshots),
            "has_narrative": has_narrative,
            "missing_narrative": missing,
            "note": note,
        },
    }, project_path=project_root, context="mcp")
