"""MCP tool: snapshot_patch — update fields of an existing snapshot in-place."""
from __future__ import annotations

from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.guidance.remediation import make_error_envelope
from the_door.mcp.tools._response_envelope import wrap
from the_door.models import SnapshotNotFoundError

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path", "version_ref"],
    "properties": {
        "codebase_path": {
            "type": "string",
            "description": "Path to the codebase root.",
        },
        "version_ref": {
            "type": "string",
            "description": (
                "Snapshot to patch: label (e.g. 'v1.0.0'), git tag, date (YYYY-MM-DD), "
                "commit SHA (≥7 chars), or version_id UUID."
            ),
        },
        "source_nodes_by_feature": {
            "type": "object",
            "description": (
                "Optional. Map of feature_id → list of node_id strings from extract_structure. "
                "Unknown feature_ids are skipped and reported in skipped_features."
            ),
            "additionalProperties": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "feature_metadata_by_feature": {
            "type": "object",
            "description": (
                "Optional. Map of feature_id → metadata dict with optional keys "
                "'trigger_description' and 'confidence_reason' (both strings). "
                "Only provided keys are written; omitted keys are not cleared. "
                "Unknown feature_ids are skipped and reported in skipped_features."
            ),
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "trigger_description": {"type": "string"},
                    "confidence_reason": {"type": "string"},
                },
            },
        },
        "analyzed_files": {
            "type": "array",
            "items": {"type": "string"},
            "description": "If provided, replaces the snapshot's analyzed_files list.",
        },
        "project_summary": {
            "type": "string",
            "description": (
                "Optional. 若提供，覆寫此 snapshot 的非技術專案簡介（project_summary）；"
                "未提供則不動原有值。"
            ),
        },
    },
}


async def execute(arguments: dict) -> dict:
    """Patch source_nodes and/or metadata of an existing snapshot without changing version_id."""
    codebase_path = arguments["codebase_path"]
    store = SnapshotStore(Path(codebase_path))
    try:
        snap, skipped = store.patch_snapshot(
            version_ref=arguments["version_ref"],
            source_nodes_by_feature=arguments.get("source_nodes_by_feature") or {},
            analyzed_files=arguments.get("analyzed_files"),
            feature_metadata_by_feature=arguments.get("feature_metadata_by_feature"),
            project_summary=arguments.get("project_summary"),
        )
    except SnapshotNotFoundError as e:
        return make_error_envelope(
            code="snapshot_not_found",
            message=str(e),
            remediation=None,
            source="snapshot_patch_tool.execute",
        )

    all_input_fids = set(
        list((arguments.get("source_nodes_by_feature") or {}).keys())
        + list((arguments.get("feature_metadata_by_feature") or {}).keys())
    )
    patched = sorted(all_input_fids - set(skipped))

    payload = {
        "version_id": snap.version_id,
        "label": snap.label,
        "patched_features": patched,
        "skipped_features": skipped,
        "project_summary": snap.project_summary,
    }
    return wrap(payload, project_path=Path(codebase_path), context="mcp")
