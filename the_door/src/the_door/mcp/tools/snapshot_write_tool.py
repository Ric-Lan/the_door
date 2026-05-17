"""MCP tool: snapshot_write — write L1 analysis results from an AI caller directly into snapshot store."""
from __future__ import annotations

from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.guidance.actions import NextAction
from the_door.core.guidance.remediation import Remediation, make_error_envelope
from the_door.mcp.tools._response_envelope import wrap
from the_door.models import FeatureSummary, RelationSummary, SnapshotNotFoundError

VALID_CONFIDENCE = {"high", "medium", "low"}

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path"],
    "properties": {
        "codebase_path": {
            "type": "string",
            "description": "Path to the codebase root (snapshot saved under <codebase_path>/.the-door/snapshots/)",
        },
        "l1_features": {
            "type": "array",
            "description": (
                "L1 features produced by the calling AI. Required unless `inherit_from` is set. "
                "Each item must have: feature_id (str, slug format e.g. 'feat-auth'), label (str), "
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
        "inherit_from": {
            "type": "string",
            "description": (
                "Baseline ref (label / git tag / commit SHA / date / version_id) to inherit "
                "features from. When set, the new snapshot starts from the baseline's "
                "l1_snapshot + feature_relations_snapshot, and `updated_features` is "
                "merged on top (overriding by feature_id)."
            ),
        },
        "updated_features": {
            "type": "array",
            "description": "Features to add or override on top of the inherited baseline.",
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


def _feature_dict_to_summary(feat: dict) -> FeatureSummary | dict:
    """Convert an L1 feature dict to FeatureSummary, or return an error dict.

    Returns a plain ``{"error": ...}`` dict on validation failure so callers
    can short-circuit with the legacy error shape.
    """
    if feat.get("confidence") not in VALID_CONFIDENCE:
        fid = feat.get("feature_id", "?")
        return {
            "error": (
                f"Feature '{fid}' has invalid confidence '{feat.get('confidence')}'. "
                f"Must be one of: high, medium, low"
            )
        }
    fid = feat["feature_id"]
    return FeatureSummary(
        feature_id=fid,
        label=feat["label"],
        description=feat["description"],
        source_node_count=len(feat.get("source_nodes", []) or []),
        confidence=feat["confidence"],
        trigger_description=feat.get("trigger_description"),
        source_nodes=tuple(feat.get("source_nodes", ())),
    )


async def execute(arguments: dict) -> dict:
    """Write caller-provided L1 analysis into the snapshot store.

    Two modes:

    * Direct: caller passes ``l1_features`` (+ optional ``relations``).
    * Inherited: caller passes ``inherit_from`` (a baseline ref) +
      ``updated_features``. The new snapshot starts from the resolved
      baseline's ``l1_snapshot`` and ``feature_relations_snapshot``, with
      ``updated_features`` merged on top (overriding by ``feature_id``).
    """
    codebase_path = arguments["codebase_path"]
    label = arguments.get("label")
    commit_hash = arguments.get("commit_hash")
    git_tags = arguments.get("git_tags", [])
    analyzed_files = arguments.get("analyzed_files", [])
    inherit_from = arguments.get("inherit_from")

    store = SnapshotStore(Path(codebase_path))

    if inherit_from:
        # Inheritance mode: start from baseline, merge updated_features.
        try:
            baseline = store.resolve_baseline(inherit_from)
        except SnapshotNotFoundError:
            baseline = None
        if baseline is None:
            baseline = store.get_snapshot(inherit_from)
        if baseline is None:
            rem = Remediation(
                code="baseline_not_found",
                message=f"Cannot resolve baseline {inherit_from!r}",
                next_action=NextAction(
                    id="system_status.show",
                    title="查看可用 snapshot",
                    rationale="列出目前 .the-door/snapshots 內容",
                    priority=1,
                    cli_command=f"the-door status {Path(codebase_path).as_posix()}",
                ),
            )
            return make_error_envelope(
                code="baseline_not_found",
                message=rem.message,
                remediation=rem,
                source="snapshot_write_tool.execute",
            )

        merged: dict[str, FeatureSummary] = dict(baseline.l1_snapshot)
        for feat_dict in arguments.get("updated_features", []):
            fs = _feature_dict_to_summary(feat_dict)
            if isinstance(fs, dict):  # validation error
                return fs
            merged[fs.feature_id] = fs

        l1_snapshot = merged
        relations = list(baseline.feature_relations_snapshot)
    else:
        # Direct mode: existing behaviour.
        raw_features: list[dict] = arguments.get("l1_features", [])
        raw_relations: list[dict] = arguments.get("relations", [])

        if not raw_features:
            return {"error": "l1_features must not be empty — provide at least one feature"}

        l1_snapshot = {}
        for feat in raw_features:
            fs = _feature_dict_to_summary(feat)
            if isinstance(fs, dict):  # validation error
                return fs
            if fs.feature_id in l1_snapshot:
                return {"error": f"Duplicate feature_id '{fs.feature_id}' — each feature_id must be unique"}
            l1_snapshot[fs.feature_id] = fs

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

    payload = {
        "version_id": snapshot.version_id,
        "label": snapshot.label,
        "timestamp": snapshot.timestamp,
        "feature_count": len(l1_snapshot),
        "relation_count": len(relations),
    }
    return wrap(payload, project_path=Path(codebase_path), context="mcp")
