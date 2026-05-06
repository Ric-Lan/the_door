"""View-model conversion for the local frontend viewer.

This module is intentionally small and data-oriented. It converts existing
The Door JSON outputs into a browser-friendly structure without inventing
features, risks, or relationships.
"""
from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
from typing import Any


MISSING_VALUE = "未提供"

_CHANGE_TYPES = (
    "added",
    "removed",
    "attribute_changed",
    "dependency_changed",
)

_RISK_PRIORITY = ("out_of_scope", "vulnerability", "semantic_drift")

_CHANGE_PRIORITY = {
    "added": 0,
    "attribute_changed": 1,
    "dependency_changed": 2,
    "removed": 3,
}


def build_l1_view_model(data: Mapping[str, Any]) -> dict[str, Any]:
    """Build a single-version view model from L1 output JSON.

    The function accepts either the repository fixture shape
    ``{"l1": {...}}`` or the direct ``L1Output`` JSON shape.
    """
    l1 = _unwrap_l1(data)
    features_raw = _list(l1.get("features"))
    feature_ids = {
        str(feature.get("feature_id", ""))
        for feature in features_raw
        if feature.get("feature_id")
    }

    features = [_feature_to_view_model(feature) for feature in features_raw]

    relations = []
    for relation in _list(l1.get("feature_relations")):
        source = relation.get("from") or relation.get("from_feature")
        target = relation.get("to") or relation.get("to_feature")
        if source in feature_ids and target in feature_ids:
            relations.append({
                "from": source,
                "to": target,
                "label": _value_or_missing(relation.get("relation")),
                "relation_type": relation.get("relation_type") or "unknown",
                "source": "L1Output.feature_relations",
            })

    return {
        "mode": "single-version",
        "diff_available": False,
        "summary": l1.get("summary") or "",
        "stats": {
            "feature_count": len(features),
            "unclassified_count": len(_list(l1.get("unclassified_nodes"))),
            "infrastructure_count": len(_list(l1.get("infrastructure_nodes"))),
        },
        "features": features,
        "relations": relations,
        "source": "L1Output",
    }


def build_update_report_view_model(report: Mapping[str, Any]) -> dict[str, Any]:
    """Build a diff-capable view model from an UpdateReport JSON dict."""
    changes_raw = _list(report.get("l1_changes"))   # _list(None) 回傳 []，不需要 key 存在判斷
    diff_available = len(changes_raw) > 0
    details_raw = _list(report.get("l2_details"))
    details_by_id = {
        str(detail.get("feature_id")): detail
        for detail in details_raw
        if detail.get("feature_id")
    }

    changes = [_change_to_view_model(change) for change in changes_raw]
    changes.sort(key=_change_sort_key)

    details = {
        change["id"]: _detail_to_view_model(
            details_by_id.get(change["id"], {}),
            fallback_change=change,
        )
        for change in changes
    }

    return {
        "mode": "update-report",
        "diff_available": diff_available,
        "summary": report.get("l0_summary") or "",
        "pipeline": _pipeline_to_view_model(report.get("pipeline_summary")),
        "change_counts": _count_changes(changes),
        "risk_counts": _count_risks(changes),
        "changes": changes,
        "details": details,
        "interrupted": bool(report.get("interrupted", False)),
        "source": "UpdateReport",
    }


def export_l1_view_model(
    input_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Convert an L1 JSON file into static viewer view-model JSON."""
    source = Path(input_path)
    target = Path(output_path)
    data = json.loads(source.read_text(encoding="utf-8"))
    view_model = build_l1_view_model(data)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(view_model, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return view_model


def export_update_report_view_model(
    input_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Convert an UpdateReport JSON file into static viewer view-model JSON."""
    source = Path(input_path)
    target = Path(output_path)
    data = json.loads(source.read_text(encoding="utf-8"))
    view_model = build_update_report_view_model(data)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(view_model, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return view_model


def _unwrap_l1(data: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = data.get("l1")
    if isinstance(nested, Mapping):
        return nested
    return data


def _feature_to_view_model(feature: Mapping[str, Any]) -> dict[str, Any]:
    feature_id = str(feature.get("feature_id") or "")
    return {
        "id": feature_id,
        "label": _value_or_missing(feature.get("label")),
        "description": _value_or_missing(feature.get("description")),
        "trigger_description": _value_or_missing(
            feature.get("trigger_description")
        ),
        "confidence": feature.get("confidence") or "unknown",
        "confidence_reason": _value_or_missing(
            feature.get("confidence_reason")
        ),
        "source_nodes": _list(feature.get("source_nodes")),
        "needs_source_review": bool(feature.get("needs_source_review", False)),
        "source": "L1Output.features",
    }


def _change_to_view_model(change: Mapping[str, Any]) -> dict[str, Any]:
    feature_id = str(change.get("feature_id") or "")
    change_type = change.get("change_type") or "unknown"
    risk_flags = [
        str(flag)
        for flag in _list(change.get("risk_flags"))
        if flag in _RISK_PRIORITY
    ]
    label = (
        change.get("current_label")
        or change.get("baseline_label")
        or feature_id
    )
    return {
        "id": feature_id,
        "label": _value_or_missing(label),
        "change_type": change_type,
        "risk_flags": risk_flags,
        "current_label": _value_or_missing(change.get("current_label")),
        "baseline_label": _value_or_missing(change.get("baseline_label")),
        "source": "UpdateReport.l1_changes",
    }


def _detail_to_view_model(
    detail: Mapping[str, Any],
    *,
    fallback_change: Mapping[str, Any],
) -> dict[str, Any]:
    feature_id = str(
        detail.get("feature_id")
        or fallback_change.get("id")
        or ""
    )
    return {
        "id": feature_id,
        "change_type": (
            detail.get("change_type")
            or fallback_change.get("change_type")
            or "unknown"
        ),
        "before": {
            "label": _value_or_missing(detail.get("baseline_label")),
            "description": _value_or_missing(
                detail.get("baseline_description")
            ),
        },
        "after": {
            "label": _value_or_missing(detail.get("current_label")),
            "description": _value_or_missing(
                detail.get("current_description")
            ),
        },
        "scope_state": detail.get("scope_state") or None,
        "related_vulnerabilities": _list(
            detail.get("related_vulnerabilities")
        ),
        "affected_relations": _list(detail.get("affected_relations")),
        "source": (
            "UpdateReport.l2_details"
            if detail
            else "UpdateReport.l1_changes"
        ),
    }


def _pipeline_to_view_model(pipeline: Any) -> dict[str, Any]:
    if not isinstance(pipeline, Mapping):
        return {"steps": []}
    return {
        "old_path": pipeline.get("old_path") or MISSING_VALUE,
        "new_path": pipeline.get("new_path") or MISSING_VALUE,
        "total_duration_ms": pipeline.get("total_duration_ms"),
        "steps": _list(pipeline.get("steps")),
    }


def _count_changes(changes: list[Mapping[str, Any]]) -> dict[str, int]:
    counts = {change_type: 0 for change_type in _CHANGE_TYPES}
    for change in changes:
        change_type = change.get("change_type")
        if change_type in counts:
            counts[change_type] += 1
    return counts


def _count_risks(changes: list[Mapping[str, Any]]) -> dict[str, int]:
    counts = {risk: 0 for risk in _RISK_PRIORITY}
    for change in changes:
        for risk in _list(change.get("risk_flags")):
            if risk in counts:
                counts[risk] += 1
    return counts


def _change_sort_key(change: Mapping[str, Any]) -> tuple[int, int, int, int, str]:
    risk_flags = set(_list(change.get("risk_flags")))
    return (
        0 if "out_of_scope" in risk_flags else 1,
        0 if "vulnerability" in risk_flags else 1,
        0 if "semantic_drift" in risk_flags else 1,
        _CHANGE_PRIORITY.get(str(change.get("change_type")), 9),
        str(change.get("id") or ""),
    )


def _value_or_missing(value: Any) -> str:
    if value is None:
        return MISSING_VALUE
    if isinstance(value, str) and not value.strip():
        return MISSING_VALUE
    return str(value)


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []
