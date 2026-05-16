"""MCP tool: snapshot_write — write L1 analysis results from an AI caller directly into snapshot store."""
from __future__ import annotations

from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import FeatureSummary, RelationSummary

VALID_CONFIDENCE = {"high", "medium", "low"}

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path", "l1_features"],
    "properties": {
        "codebase_path": {
            "type": "string",
            "description": "Path to the codebase root (snapshot saved under <codebase_path>/.the-door/snapshots/)",
        },
        "l1_features": {
            "type": "array",
            "description": (
                "L1 features produced by the calling AI. Each item must have: "
                "feature_id (str, slug format e.g. 'feat-auth'), label (str), "
                "description (str), confidence ('high'|'medium'|'low'). "
                "Optionally provide source_nodes (list of structure.json node_ids) "
                "so the viewer can drill into L2/L3 without re-inferring which AST "
                "nodes belong to this feature; source_node_count is derived from "
                "source_nodes and may be omitted. Optionally provide "
                "trigger_description (str) so the viewer can show the trigger "
                "summary in the L1 detail panel."
            ),
            "items": {
                "type": "object",
                "required": ["feature_id", "label", "description", "confidence"],
                "properties": {
                    "feature_id": {"type": "string"},
                    "label": {"type": "string"},
                    "description": {"type": "string"},
                    "source_node_count": {"type": "integer"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "trigger_description": {"type": "string"},
                    "source_nodes": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "relations": {
            "type": "array",
            "description": "Feature-level dependency relations. Each item: from_feature, to_feature, relation (str).",
            "items": {
                "type": "object",
                "required": ["from_feature", "to_feature", "relation"],
                "properties": {
                    "from_feature": {"type": "string"},
                    "to_feature": {"type": "string"},
                    "relation": {"type": "string"},
                },
            },
        },
        "label": {"type": "string", "description": "Human-readable snapshot label (e.g. 'v1.0.0')."},
        "commit_hash": {"type": "string", "description": "Git commit SHA at analysis time (optional)."},
        "git_tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Git tags associated with this snapshot (e.g. ['v1.0.0']).",
        },
        "analyzed_files": {
            "type": "array",
            "items": {"type": "string"},
            "description": "File paths scanned during extract_structure.",
        },
    },
}


async def execute(arguments: dict) -> dict:
    """Write caller-provided L1 analysis into the snapshot store."""
    codebase_path = arguments["codebase_path"]
    raw_features: list[dict] = arguments.get("l1_features", [])
    raw_relations: list[dict] = arguments.get("relations", [])
    label = arguments.get("label")
    commit_hash = arguments.get("commit_hash")
    git_tags = arguments.get("git_tags", [])
    analyzed_files = arguments.get("analyzed_files", [])

    if not raw_features:
        return {"error": "l1_features must not be empty — provide at least one feature"}

    for feat in raw_features:
        if feat.get("confidence") not in VALID_CONFIDENCE:
            fid = feat.get("feature_id", "?")
            return {
                "error": (
                    f"Feature '{fid}' has invalid confidence '{feat.get('confidence')}'. "
                    f"Must be one of: high, medium, low"
                )
            }

    l1_snapshot: dict[str, FeatureSummary] = {}
    for feat in raw_features:
        fid = feat["feature_id"]
        if fid in l1_snapshot:
            return {"error": f"Duplicate feature_id '{fid}' — each feature_id must be unique"}
        l1_snapshot[fid] = FeatureSummary(
            feature_id=fid,
            label=feat["label"],
            description=feat["description"],
            source_node_count=len(feat.get("source_nodes", []) or []),
            confidence=feat["confidence"],
            trigger_description=feat.get("trigger_description"),
            source_nodes=tuple(feat.get("source_nodes", ())),
        )

    known_ids = set(l1_snapshot.keys())
    for rel in raw_relations:
        for fld in ("from_feature", "to_feature"):
            fid = rel.get(fld)
            if fid and fid not in known_ids:
                return {"error": f"Relation references unknown feature_id '{fid}'"}

    relations = [
        RelationSummary(
            from_feature=r["from_feature"],
            to_feature=r["to_feature"],
            relation=r["relation"],
        )
        for r in raw_relations
    ]

    store = SnapshotStore(Path(codebase_path))
    snapshot = store.create_snapshot(
        l1_snapshot=l1_snapshot,
        feature_relations=relations,
        analyzed_files=analyzed_files,
        commit_hash=commit_hash,
        git_tags=git_tags if git_tags else [],
        trigger="manual",
        label=label,
    )

    from the_door.core.registry import ProjectRegistry
    ProjectRegistry().register(codebase_path)
    return {
        "version_id": snapshot.version_id,
        "label": snapshot.label,
        "timestamp": snapshot.timestamp,
        "feature_count": len(l1_snapshot),
        "relation_count": len(relations),
    }
