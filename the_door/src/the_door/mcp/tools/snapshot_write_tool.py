"""MCP tool: snapshot_write — write L1 analysis results from an AI caller directly into snapshot store."""
from __future__ import annotations

from pathlib import Path

from the_door.core.checklist import STAGE_SNAPSHOT_WRITE, read_ledger, stamp_stage
from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.registry import ProjectRegistry, UNGROUPED_HINT
from the_door.core.flow_guard import CheckpointOption, FlowGuard
from the_door.core.guidance.actions import NextAction
from the_door.core.guidance.remediation import Remediation, make_error_envelope
from the_door.core.reading.confidence_membrane import CONFIDENCE_CONTRASTS
from the_door.mcp.tools._response_envelope import wrap
from the_door.models import FeatureSummary, RelationSummary, SnapshotNotFoundError
from the_door.models.snapshot import SNAPSHOT_CONTRACT_VERSION

_flow_guard = FlowGuard()


def _ledger_with_snapshot_write(codebase_path, sw_details: dict) -> list[dict]:
    """Return the chain ledger, guaranteeing the just-run snapshot_write stage
    is present even if the disk stamp failed (fail-soft) — the returned ledger
    must never under-report a stage the response's own version_id proves ran."""
    ledger = read_ledger(codebase_path)
    if not any(e["stage"] == STAGE_SNAPSHOT_WRITE for e in ledger):
        ledger.append({"stage": STAGE_SNAPSHOT_WRITE, **sw_details})
    return ledger

VALID_CONFIDENCE = set(CONFIDENCE_CONTRASTS)

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
                    "confidence": {"oneOf": [
                        {"const": "high", "description": "抽取信心高"},
                        {"const": "medium", "description": "抽取信心中"},
                        {"const": "low", "description": "抽取信心低"},
                    ]},
                    "trigger_description": {"type": "string"},
                    "source_nodes": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "confidence_reason": {"type": "string"},
                },
            },
        },
        "relations": {
            "type": "array",
            "description": "Feature-level dependency relations. Each item: from_feature, to_feature, relation (str), 選填 relation_type ('static'|'inferred') 與 inferred_reason。relation_type='static'＝期待此依賴在程式碼有實連（integration_check 會驗證）；'inferred'＝概念/流程關係、附 inferred_reason、不查邊。",
            "items": {
                "type": "object",
                "required": ["from_feature", "to_feature", "relation"],
                "properties": {
                    "from_feature": {"type": "string"},
                    "to_feature": {"type": "string"},
                    "relation": {"type": "string"},
                    "relation_type": {"type": "string", "enum": ["static", "inferred"]},
                    "inferred_reason": {"type": "string"},
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
                    "confidence": {"oneOf": [
                        {"const": "high", "description": "抽取信心高"},
                        {"const": "medium", "description": "抽取信心中"},
                        {"const": "low", "description": "抽取信心低"},
                    ]},
                    "trigger_description": {"type": "string"},
                    "source_nodes": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "confidence_reason": {"type": "string"},
                },
            },
        },
        "project_summary": {
            "type": "string",
            "description": (
                "Non-technical project summary (2-4 sentences) you synthesize from the "
                "l1_features descriptions — what this product does, for a non-technical "
                "reader. Do NOT introduce capabilities beyond what the features describe. "
                "In inherit mode: omit it to carry the baseline's summary unchanged; "
                "provide it only when the feature set changed enough to warrant a rewrite."
            ),
        },
        "version_narratives": {
            "type": "object",
            "description": (
                "Optional. Map of baseline_version_id (UUID) → plain-language narrative "
                "describing what changed in this version relative to that baseline. "
                "Not inherited from baseline even in inherit_from mode — each version's "
                "narratives describe transitions FROM a specific baseline TO this version. "
                "Obtain baseline version_id from snapshot_list (version_id field)."
            ),
            "additionalProperties": {"type": "string"},
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
        "choice": {
            "type": "string",
            "description": (
                "CHECKPOINT 選項的 key（'A'、'B'、'C'）。"
                "首次呼叫省略；收到 result=null 後帶入選擇重新呼叫。"
            ),
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
        confidence_reason=feat.get("confidence_reason"),
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
    choice = arguments.get("choice")
    arg_summary = arguments.get("project_summary")  # 未給＝None；inherit 時退回 baseline
    arg_narratives = dict(arguments.get("version_narratives") or {})

    store = SnapshotStore(Path(codebase_path))

    if inherit_from:
        # Inheritance mode: start from baseline, detect new features, ask agent.
        try:
            baseline_snap = store.resolve_baseline(inherit_from)
        except SnapshotNotFoundError:
            baseline_snap = None
        if baseline_snap is None:
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

        raw_l1: list[dict] = arguments.get("l1_features", [])
        raw_updated: list[dict] = arguments.get("updated_features", [])

        if raw_l1:
            # Full-replacement mode: detect new features, may trigger CHECKPOINT
            new_features: dict[str, FeatureSummary] = {}
            for feat_dict in raw_l1:
                fs = _feature_dict_to_summary(feat_dict)
                if isinstance(fs, dict):
                    return fs
                new_features[fs.feature_id] = fs

            baseline_ids = set(baseline_snap.l1_snapshot.keys())
            new_ids = set(new_features.keys())
            added_ids = new_ids - baseline_ids

            if added_ids:
                if choice == "C":
                    return {"result": None, "aborted": True}

                decision = _flow_guard.check(
                    "new-features-detected",
                    f"偵測到 {len(added_ids)} 個新 feature：{', '.join(sorted(added_ids))}",
                    options=[
                        CheckpointOption("A", "保留新 feature（合併進 snapshot）"),
                        CheckpointOption("B", "捨棄新 feature（只保留 baseline）"),
                        CheckpointOption("C", "中止，不寫入"),
                    ],
                    choice=choice,
                )
                if not decision.is_resolved:
                    payload: dict = {"_decision": decision}
                    return wrap(payload, project_path=Path(codebase_path), context="mcp")

                if decision.chosen == "A":
                    merged = {**baseline_snap.l1_snapshot, **{fid: new_features[fid] for fid in added_ids}}
                else:  # B
                    merged = {fid: baseline_snap.l1_snapshot[fid] for fid in baseline_ids & new_ids}
            else:
                # All features already in baseline: merge on top
                merged = dict(baseline_snap.l1_snapshot)
                for fid, fs in new_features.items():
                    merged[fid] = fs
        else:
            # Incremental-update mode (updated_features): merge on top of baseline, no CHECKPOINT
            merged = dict(baseline_snap.l1_snapshot)
            for feat_dict in raw_updated:
                fs = _feature_dict_to_summary(feat_dict)
                if isinstance(fs, dict):
                    return fs
                merged[fs.feature_id] = fs

        l1_snapshot = merged
        relations = list(baseline_snap.feature_relations_snapshot)
        warnings = []
        # 未給簡介＝沿用 baseline（組成未由本欄判定變動）；給了＝覆寫。
        project_summary = arg_summary if arg_summary is not None else baseline_snap.project_summary
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
                relation_type=r.get("relation_type"),
                inferred_reason=r.get("inferred_reason"),
            )
            for r in raw_relations
        ]

        warnings = [
            f"Feature '{fid}' has empty source_nodes — L2 drill-down will not work"
            for fid, fs in l1_snapshot.items()
            if not fs.source_nodes
        ]
        project_summary = arg_summary  # direct 模式：未給＝None（誠實缺席）

    snapshot = store.create_snapshot(
        l1_snapshot=l1_snapshot,
        feature_relations=relations,
        analyzed_files=analyzed_files,
        commit_hash=commit_hash,
        git_tags=git_tags if git_tags else [],
        trigger="manual",
        label=label,
        project_summary=project_summary,
        version_narratives=arg_narratives,
    )

    ProjectRegistry().register(codebase_path)

    payload = {
        "version_id": snapshot.version_id,
        "label": snapshot.label,
        "timestamp": snapshot.timestamp,
        "feature_count": len(l1_snapshot),
        "relation_count": len(relations),
        "project_summary": snapshot.project_summary,
        "version_narratives": dict(snapshot.version_narratives),
    }
    if warnings:
        payload["warnings"] = warnings

    # C6: stamp the snapshot_write stage (disk best-effort) and embed the
    # whole-chain ledger so the caller can report each stage back to the user.
    # The stamp is fail-soft on I/O (the snapshot already persisted; failing the
    # whole call over a post-hoc ledger record would falsely report the user's
    # real work as failed) — but only OSError is swallowed, so a signature/logic
    # bug still surfaces. The returned ledger is rebuilt from in-memory facts so
    # it never under-reports this stage.
    sw_details = {
        "version_id": snapshot.version_id,
        "label": snapshot.label,
        "feature_count": len(l1_snapshot),
        "relation_count": len(relations),
    }
    try:
        stamp_stage(
            codebase_path, STAGE_SNAPSHOT_WRITE,
            contract_version=SNAPSHOT_CONTRACT_VERSION,
            details=sw_details,
        )
    except OSError:
        pass
    payload["execution_ledger"] = _ledger_with_snapshot_write(codebase_path, sw_details)
    _reg = ProjectRegistry()
    _proj = _reg.get_by_path(codebase_path)
    _grp = _reg.get_group_for_project(_proj["id"]) if _proj else None
    if _grp:
        payload["group"] = _grp
    else:
        payload["group"] = None
        payload["hint"] = UNGROUPED_HINT
    return wrap(payload, project_path=Path(codebase_path), context="mcp")
