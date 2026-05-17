"""MCP tool: diff — compare current analysis against a baseline version."""
from __future__ import annotations

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path", "baseline"],
    "properties": {
        "codebase_path": {"type": "string", "description": "Path to the codebase root"},
        "baseline": {"type": "string", "description": "Baseline reference (git tag, SHA, date, or label)"},
        "format": {"type": "string", "enum": ["mermaid", "json"], "default": "mermaid", "description": "Output format"},
        "layer": {"type": "string", "enum": ["l1", "l1.5"], "default": "l1", "description": "Layer to diff"},
    },
}


async def execute(arguments: dict) -> dict:
    """Execute the diff tool."""
    from pathlib import Path
    from the_door.core.diff.snapshot_store import SnapshotStore
    from the_door.core.diff.diff_engine import DiffEngine
    from the_door.core.diff.diff_renderer import DiffRenderer
    from the_door.mcp.tools._response_envelope import wrap
    from the_door.models import SnapshotNotFoundError, DiffError, BaselineInfo, DiffResult

    codebase_path = arguments["codebase_path"]
    project_root = Path(arguments.get("codebase_path") or arguments.get("project_path") or Path.cwd())
    baseline_ref = arguments["baseline"]
    output_format = arguments.get("format", "mermaid")
    layer = arguments.get("layer", "l1")

    store = SnapshotStore(Path(codebase_path))

    current = store.get_latest()
    if current is None:
        return {"error": "No snapshots found. Run analysis first."}

    try:
        baseline_snap = store.resolve_baseline(baseline_ref)
    except SnapshotNotFoundError as e:
        return {"error": f"No snapshot matches '{baseline_ref}'", "available": e.available}

    engine = DiffEngine()
    try:
        if layer == "l1":
            diff_result = engine.compute_l1_diff(baseline_snap, current)
        else:
            diff_result = engine.compute_l1_5_diff(baseline_snap, current)
    except DiffError as e:
        return {"error": str(e)}

    # Patch resolved_from
    patched_baseline = BaselineInfo(
        version_id=diff_result.baseline_info.version_id,
        timestamp=diff_result.baseline_info.timestamp,
        trigger=diff_result.baseline_info.trigger,
        commit_hash=diff_result.baseline_info.commit_hash,
        git_tags=diff_result.baseline_info.git_tags,
        label=diff_result.baseline_info.label,
        resolved_from=baseline_ref,
    )
    diff_result = DiffResult(
        baseline_info=patched_baseline,
        current_info=diff_result.current_info,
        node_diffs=diff_result.node_diffs,
        edge_diffs=diff_result.edge_diffs,
        summary=diff_result.summary,
        layer=diff_result.layer,
    )

    if output_format == "json":
        # Return structured diff result
        return wrap({
            "baseline_info": {"version_id": diff_result.baseline_info.version_id, "timestamp": diff_result.baseline_info.timestamp},
            "current_info": {"version_id": diff_result.current_info.version_id, "timestamp": diff_result.current_info.timestamp},
            "summary": {
                "added_count": diff_result.summary.added_count,
                "removed_count": diff_result.summary.removed_count,
                "dependency_changed_count": diff_result.summary.dependency_changed_count,
                "attribute_changed_count": diff_result.summary.attribute_changed_count,
                "total_changed_count": diff_result.summary.total_changed_count,
            },
            "node_diffs": [{"node_id": nd.node_id, "diff_state": nd.diff_state} for nd in diff_result.node_diffs],
            "edge_diffs": [{"from_node": ed.from_node, "to_node": ed.to_node, "diff_state": ed.diff_state} for ed in diff_result.edge_diffs],
        }, project_path=project_root, context="mcp")
    else:
        renderer = DiffRenderer()
        if layer == "l1":
            mermaid_text = renderer.render_l1_diff(diff_result)
        else:
            mermaid_text = renderer.render_l1_5_diff(diff_result)
        return wrap({"mermaid": mermaid_text}, project_path=project_root, context="mcp")
