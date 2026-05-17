"""MCP tool: snapshot_prune — compute snapshot retention decisions based on retention policy."""
from __future__ import annotations

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path"],
    "properties": {
        "codebase_path": {"type": "string", "description": "Codebase root directory path"},
        "dry_run": {"type": "boolean", "description": "Only compute, don't delete", "default": True},
        "max_snapshots": {"type": "integer", "description": "Override max_snapshots setting"},
    },
}


async def execute(arguments: dict) -> dict:
    """Execute the snapshot_prune MCP tool.

    Default dry_run=True for MCP safety.
    Returns RetentionDecision JSON (to_retain + to_remove lists).
    """
    import json
    import logging
    from pathlib import Path

    from the_door.core.diff.snapshot_store import SnapshotStore
    from the_door.core.timeline.retention_engine import RetentionEngine
    from the_door.mcp.tools._response_envelope import wrap

    logger = logging.getLogger(__name__)

    codebase_path = arguments["codebase_path"]
    project_root = Path(arguments.get("codebase_path") or arguments.get("project_path") or Path.cwd())
    dry_run = arguments.get("dry_run", True)
    max_snapshots_override = arguments.get("max_snapshots")

    store = SnapshotStore(Path(codebase_path))
    snapshots = store.list_snapshots()

    if not snapshots:
        return {"error": "No snapshots found. Run analyze first."}

    # Load retention config from .the-door/retention-config.json
    default_max = 50
    default_enabled = True
    config_path = Path(codebase_path) / ".the-door" / "retention-config.json"

    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            config_max = data.get("max_snapshots", default_max)
            config_enabled = data.get("enabled", default_enabled)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to parse retention-config.json: %s — using defaults",
                exc,
            )
            config_max = default_max
            config_enabled = default_enabled
    else:
        config_max = default_max
        config_enabled = default_enabled

    # max_snapshots argument overrides config value
    effective_max = max_snapshots_override if max_snapshots_override is not None else config_max

    engine = RetentionEngine()
    decision = engine.compute_retention(
        snapshots, max_snapshots=effective_max, enabled=config_enabled
    )

    result: dict = {
        "to_retain": decision.to_retain,
        "to_remove": decision.to_remove,
        "dry_run": dry_run,
    }

    # Actually delete if not dry_run
    if not dry_run and decision.to_remove:
        for vid in decision.to_remove:
            store.delete_snapshot(vid)
        result["deleted_count"] = len(decision.to_remove)

    return wrap(result, project_path=project_root, context="mcp")
