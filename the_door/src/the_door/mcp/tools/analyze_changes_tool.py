"""analyze_changes MCP tool — read-only incremental diff against a baseline.

Glue between the orchestrator (:mod:`core.pipeline.incremental_pipeline`) and
the MCP surface. Successful runs return a JSON-serializable IncrementalDiff plus
``next_actions`` injected by :mod:`_response_envelope`. Failed runs return a
standard error envelope built from the orchestrator's ``Remediation``.
"""
from __future__ import annotations

from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.flow_guard import CheckpointOption, FlowGuard
from the_door.core.guidance.remediation import make_error_envelope
from the_door.core.pipeline.incremental_pipeline import (
    IncrementalAnalysisError,
    run_incremental_pipeline,
)
from the_door.mcp.tools._response_envelope import wrap

_flow_guard = FlowGuard()

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "codebase_path": {"type": "string"},
        "baseline": {
            "type": "string",
            "description": "label / tag / SHA / date / version_id",
        },
        "source_path": {
            "type": "string",
            "description": (
                "Source codebase 路徑（當 source 和 store 在不同目錄時使用）。"
                "省略時使用 snapshot.codebase_path。"
            ),
        },
        "choice": {
            "type": "string",
            "description": (
                "CHECKPOINT 選項的 key（'A'、'B'）。"
                "首次呼叫省略；收到 result=null 後帶入選擇重新呼叫。"
            ),
        },
    },
    "required": ["codebase_path", "baseline"],
}


def _feature_to_json(fs) -> dict:
    """Project FeatureSummary to JSON. Optional fields fetched defensively
    so future schema additions (e.g. ``trigger``, ``confidence_reason``)
    serialize automatically without breaking this projection.
    """
    return {
        "feature_id": fs.feature_id,
        "label": fs.label,
        "description": fs.description,
        "trigger": getattr(fs, "trigger", None),
        "trigger_description": fs.trigger_description,
        "confidence": fs.confidence,
        "confidence_reason": getattr(fs, "confidence_reason", None),
        "source_nodes": list(fs.source_nodes),
        "source_node_count": len(fs.source_nodes),
    }


def _affected_to_json(af) -> dict:
    return {
        "feature_id": af.feature_id,
        "current_label": af.current_label,
        "current_description": af.current_description,
        "current_trigger_description": af.current_trigger_description,
        "delta": {
            "added": list(af.delta.added),
            "removed": list(af.delta.removed),
            "modified": list(af.delta.modified),
        },
    }


async def execute(arguments: dict) -> dict:
    codebase_path = Path(arguments["codebase_path"])
    baseline_ref = arguments["baseline"]
    source_path_arg = arguments.get("source_path")
    choice = arguments.get("choice")

    # Resolve source path: explicit arg > snapshot.codebase_path > codebase_path
    if source_path_arg:
        resolved_source = Path(source_path_arg)
    else:
        store = SnapshotStore(codebase_path)
        try:
            from the_door.models import SnapshotNotFoundError
            snap = store.resolve_baseline(baseline_ref)
        except Exception:
            snap = store.get_snapshot(baseline_ref)
        snap_cp = getattr(snap, "codebase_path", None) if snap else None
        resolved_source = snap_cp if snap_cp else codebase_path

    if not resolved_source.exists():
        decision = _flow_guard.check(
            "source-path-broken",
            f"baseline {baseline_ref!r} 的來源路徑 {resolved_source} 不存在",
            options=[
                CheckpointOption(
                    "A", "提供新路徑",
                    f"analyze_changes(baseline='{baseline_ref}', source_path='<填入>')",
                ),
                CheckpointOption("B", "中止"),
            ],
            choice=choice,
        )
        payload: dict = {"_decision": decision}
        return wrap(payload, project_path=codebase_path, context="mcp")

    try:
        result = run_incremental_pipeline(
            codebase_path=resolved_source, baseline_ref=baseline_ref
        )
    except IncrementalAnalysisError as e:
        rem = e.remediation
        return make_error_envelope(
            code=rem.code,
            message=rem.message,
            remediation=rem,
            source="analyze_changes_tool.execute",
        )

    diff = result.diff
    payload = {
        "baseline_version_id": diff.baseline_version_id,
        "baseline_label": result.baseline_label,
        "inherited_features": [_feature_to_json(fs) for fs in diff.inherited_features],
        "affected_features": [_affected_to_json(af) for af in diff.affected_features],
        "unmapped_nodes": {
            "added": list(diff.unmapped_nodes.added),
            "removed": list(diff.unmapped_nodes.removed),
            "modified": list(diff.unmapped_nodes.modified),
        },
    }
    return wrap(payload, project_path=codebase_path, context="mcp")
