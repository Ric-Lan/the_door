"""MCP tool: scope_verify — run scope verification against a scope definition."""
from __future__ import annotations

TOOL_SCHEMA = {
    "type": "object",
    "required": ["scope_file"],
    "properties": {
        "scope_file": {
            "type": "string",
            "description": "Scope definition 檔案路徑",
        },
        "codebase_path": {
            "type": "string",
            "description": "Codebase 根目錄路徑（預設 '.'）",
        },
    },
}


async def execute(arguments: dict) -> dict:
    from pathlib import Path
    from the_door.core.scope.scope_verifier import (
        ScopeVerifier,
        parse_scope_definition,
    )
    from the_door.core.scope.doubt_store import DoubtStore
    from the_door.core.diff.snapshot_store import SnapshotStore
    from the_door.mcp.tools._response_envelope import wrap
    from the_door.models import ScopeDefinitionError

    scope_file = arguments["scope_file"]
    codebase_path = arguments.get("codebase_path", ".")
    project_root = Path(codebase_path)

    # Parse scope definition
    try:
        scope_def = parse_scope_definition(Path(scope_file))
    except ScopeDefinitionError as e:
        return {"error": True, "message": str(e)}

    # Load latest L1 analysis output via SnapshotStore
    store = SnapshotStore(project_root)
    snapshot = store.get_latest()
    if snapshot is None:
        return {"error": True, "message": "No L1 analysis output found. Run `the-door analyze` first."}

    # Convert VersionSnapshot to L1Output
    l1_output = _snapshot_to_l1_output(snapshot)

    # Execute scope verification with auto doubt creation
    verifier = ScopeVerifier()
    doubt_store = DoubtStore(project_root)
    scope_result, new_doubts = verifier.verify_and_create_doubts(
        scope_def, l1_output, doubt_store
    )

    # Serialize ScopeResult
    return wrap({
        "scope_name": scope_result.scope_name,
        "entries": [
            {
                "feature_id": e.feature_id,
                "scope_state": e.scope_state,
                "feature_label": e.feature_label,
                "expected_label": e.expected_label,
            }
            for e in scope_result.entries
        ],
        "counts": {
            "in_scope_complete": scope_result.counts.in_scope_complete,
            "out_of_scope": scope_result.counts.out_of_scope,
            "in_scope_incomplete": scope_result.counts.in_scope_incomplete,
        },
        "new_doubts": len(new_doubts),
    }, project_path=project_root, context="mcp")


def _snapshot_to_l1_output(snapshot):
    """Convert a VersionSnapshot's l1_snapshot to an L1Output for the verifier."""
    from the_door.models import L1Output, Feature, FeatureRelation

    features = []
    for fid, summary in snapshot.l1_snapshot.items():
        features.append(
            Feature(
                feature_id=summary.feature_id,
                label=summary.label,
                description=summary.description,
                trigger="auto_triggered",
                trigger_description="",
                confidence=summary.confidence,
                confidence_reason="",
                source_nodes=[],
            )
        )

    relations = []
    for rel in snapshot.feature_relations_snapshot:
        relations.append(
            FeatureRelation(
                from_feature=rel.from_feature,
                to_feature=rel.to_feature,
                relation=rel.relation,
                relation_type="static",
            )
        )

    return L1Output(
        summary="",
        features=features,
        feature_relations=relations,
    )
