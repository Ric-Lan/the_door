"""Tests for local frontend viewer view-model conversion.

These tests define the first UI contract before implementation. The browser
layer should consume this view model instead of recalculating business logic.
"""
from __future__ import annotations

import json
from pathlib import Path

from the_door.core.ui.view_model import (
    MISSING_VALUE,
    build_l1_view_model,
    build_update_report_view_model,
    export_l1_view_model,
    export_update_report_view_model,
)


def test_l1_view_model_uses_only_declared_features():
    data = {
        "l1": {
            "summary": "A local verification tool.",
            "features": [
                {
                    "feature_id": "feat-a",
                    "label": "Feature A",
                    "description": "Does A",
                    "trigger_description": "User runs analysis",
                    "confidence": "high",
                    "confidence_reason": "Mapped to source nodes",
                    "source_nodes": ["core/a.py::run"],
                }
            ],
            "feature_relations": [
                {"from": "feat-a", "to": "feat-missing", "relation": "dangling"}
            ],
            "unclassified_nodes": [],
            "infrastructure_nodes": ["models.py::Feature"],
        }
    }

    view_model = build_l1_view_model(data)

    assert view_model["mode"] == "single-version"
    assert view_model["diff_available"] is False
    assert view_model["summary"] == "A local verification tool."
    assert view_model["stats"]["feature_count"] == 1
    assert view_model["stats"]["unclassified_count"] == 0
    assert view_model["stats"]["infrastructure_count"] == 1
    assert [f["id"] for f in view_model["features"]] == ["feat-a"]
    assert view_model["relations"] == []


def test_update_report_view_model_counts_changes_from_l1_changes():
    report = {
        "l0_summary": "Update summary",
        "pipeline_summary": {
            "old_path": "old",
            "new_path": "new",
            "steps": [{"step_name": "diff", "status": "completed"}],
        },
        "l1_changes": [
            {
                "feature_id": "feat-added",
                "change_type": "added",
                "risk_flags": [],
                "current_label": "Added feature",
                "baseline_label": None,
            },
            {
                "feature_id": "feat-mod",
                "change_type": "attribute_changed",
                "risk_flags": ["out_of_scope"],
                "current_label": "Modified feature",
                "baseline_label": "Old feature",
            },
            {
                "feature_id": "feat-removed",
                "change_type": "removed",
                "risk_flags": [],
                "current_label": "",
                "baseline_label": "Removed feature",
            },
        ],
        "l2_details": [],
        "interrupted": False,
    }

    view_model = build_update_report_view_model(report)

    assert view_model["mode"] == "update-report"
    assert view_model["diff_available"] is True
    assert view_model["change_counts"] == {
        "added": 1,
        "removed": 1,
        "attribute_changed": 1,
        "dependency_changed": 0,
    }
    assert view_model["risk_counts"]["out_of_scope"] == 1
    assert [c["id"] for c in view_model["changes"]] == [
        "feat-mod",
        "feat-added",
        "feat-removed",
    ]


def test_update_report_requires_l1_changes_for_diff_mode():
    report = {
        "l0_summary": "No diff payload",
        "pipeline_summary": {"steps": []},
        "l2_details": [],
    }

    view_model = build_update_report_view_model(report)

    assert view_model["diff_available"] is False
    assert view_model["changes"] == []
    assert view_model["change_counts"]["added"] == 0


def test_detail_values_do_not_backfill_missing_before_after_fields():
    report = {
        "l0_summary": "Update summary",
        "pipeline_summary": {"steps": []},
        "l1_changes": [
            {
                "feature_id": "feat-new",
                "change_type": "added",
                "risk_flags": [],
                "current_label": "New feature",
                "baseline_label": None,
            }
        ],
        "l2_details": [
            {
                "feature_id": "feat-new",
                "change_type": "added",
                "current_label": "New feature",
                "current_description": "New behavior",
                "baseline_label": None,
                "baseline_description": None,
                "scope_state": None,
                "related_vulnerabilities": [],
                "affected_relations": [],
            }
        ],
    }

    view_model = build_update_report_view_model(report)
    detail = view_model["details"]["feat-new"]

    assert detail["before"]["label"] == MISSING_VALUE
    assert detail["before"]["description"] == MISSING_VALUE
    assert detail["after"]["label"] == "New feature"
    assert detail["after"]["description"] == "New behavior"


def test_self_analysis_fixture_builds_single_version_view_model():
    fixture = (
        Path(__file__).resolve().parents[5]
        / "docs"
        / "self-analysis-l1-output.json"
    )
    data = json.loads(fixture.read_text(encoding="utf-8"))

    view_model = build_l1_view_model(data)

    assert view_model["mode"] == "single-version"
    assert view_model["diff_available"] is False
    assert view_model["stats"]["feature_count"] == 13
    assert view_model["stats"]["unclassified_count"] == 0
    assert all(feature["source_nodes"] for feature in view_model["features"])
    assert all(
        relation["from"] != "feat-missing"
        for relation in view_model["relations"]
    )


def test_export_l1_view_model_writes_rebuildable_json(tmp_path):
    input_path = tmp_path / "l1.json"
    output_path = tmp_path / "view-model.json"
    input_path.write_text(
        json.dumps({
            "l1": {
                "summary": "Local fixture",
                "features": [
                    {
                        "feature_id": "feat-a",
                        "label": "Feature A",
                        "description": "Does A",
                        "source_nodes": ["a.py::run"],
                    }
                ],
            }
        }),
        encoding="utf-8",
    )

    view_model = export_l1_view_model(input_path, output_path)
    written = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == view_model
    assert written["stats"]["feature_count"] == 1


def test_diff_available_false_when_l1_changes_empty_list():
    """Req 1 AC2: l1_changes key exists but is empty list → diff_available=False."""
    report = {
        "l0_summary": "Empty diff",
        "pipeline_summary": {"steps": []},
        "l1_changes": [],
        "l2_details": [],
    }

    view_model = build_update_report_view_model(report)

    assert view_model["diff_available"] is False
    assert view_model["changes"] == []


def test_diff_available_true_when_l1_changes_nonempty():
    """Req 1 AC1: l1_changes has 1 entry → diff_available=True."""
    report = {
        "l0_summary": "One change",
        "pipeline_summary": {"steps": []},
        "l1_changes": [
            {
                "feature_id": "feat-x",
                "change_type": "added",
                "risk_flags": [],
                "current_label": "Feature X",
                "baseline_label": None,
            }
        ],
        "l2_details": [],
    }

    view_model = build_update_report_view_model(report)

    assert view_model["diff_available"] is True
    assert len(view_model["changes"]) == 1


def test_export_update_report_view_model_writes_rebuildable_json(tmp_path):
    input_path = tmp_path / "mock-update-report.json"
    output_path = tmp_path / "mock-update-view-model.json"
    input_path.write_text(
        json.dumps({
            "l0_summary": "本次更新新增 1 個功能",
            "pipeline_summary": {
                "old_path": "before",
                "new_path": "after",
                "steps": [{"step_name": "diff", "status": "completed"}],
            },
            "l1_changes": [
                {
                    "feature_id": "feat-ui",
                    "change_type": "added",
                    "risk_flags": [],
                    "current_label": "本地前端工作台",
                    "baseline_label": None,
                }
            ],
            "l2_details": [
                {
                    "feature_id": "feat-ui",
                    "change_type": "added",
                    "current_label": "本地前端工作台",
                    "current_description": "以本地資料呈現版本差異",
                    "baseline_label": None,
                    "baseline_description": None,
                    "scope_state": None,
                    "related_vulnerabilities": [],
                    "affected_relations": [],
                }
            ],
            "interrupted": False,
        }),
        encoding="utf-8",
    )

    view_model = export_update_report_view_model(input_path, output_path)
    written = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == view_model
    assert written["diff_available"] is True
    assert written["change_counts"]["added"] == 1
    assert written["details"]["feat-ui"]["before"]["label"] == MISSING_VALUE


def test_fallback_detail_when_no_l2_entry():
    """Req 1 AC9: no l2_details entry → details[id].source='UpdateReport.l1_changes', before.label=MISSING_VALUE."""
    report = {
        "l0_summary": "Fallback test",
        "pipeline_summary": {"steps": []},
        "l1_changes": [
            {
                "feature_id": "feat-fallback",
                "change_type": "added",
                "risk_flags": [],
                "current_label": "Fallback Feature",
                "baseline_label": None,
            }
        ],
        "l2_details": [],
    }

    view_model = build_update_report_view_model(report)
    detail = view_model["details"]["feat-fallback"]

    assert detail["source"] == "UpdateReport.l1_changes"
    assert detail["before"]["label"] == MISSING_VALUE
    assert detail["before"]["description"] == MISSING_VALUE


def test_sort_tiebreak_by_feature_id():
    """Req 2 AC1(e): same risk_flags + change_type → sort by feature_id ascending."""
    report = {
        "l0_summary": "Tiebreak test",
        "pipeline_summary": {"steps": []},
        "l1_changes": [
            {
                "feature_id": "feat-b",
                "change_type": "added",
                "risk_flags": [],
                "current_label": "Feature B",
                "baseline_label": None,
            },
            {
                "feature_id": "feat-a",
                "change_type": "added",
                "risk_flags": [],
                "current_label": "Feature A",
                "baseline_label": None,
            },
        ],
        "l2_details": [],
    }

    view_model = build_update_report_view_model(report)
    ids = [c["id"] for c in view_model["changes"]]

    assert ids == ["feat-a", "feat-b"]


def test_missing_value_when_current_label_empty_string():
    """Req 1 AC6 edge: current_label='' → after.label=MISSING_VALUE."""
    report = {
        "l0_summary": "Empty string test",
        "pipeline_summary": {"steps": []},
        "l1_changes": [
            {
                "feature_id": "feat-empty",
                "change_type": "attribute_changed",
                "risk_flags": [],
                "current_label": "",
                "baseline_label": "Old Label",
            }
        ],
        "l2_details": [
            {
                "feature_id": "feat-empty",
                "change_type": "attribute_changed",
                "current_label": "",
                "current_description": "Some description",
                "baseline_label": "Old Label",
                "baseline_description": "Old description",
                "scope_state": None,
                "related_vulnerabilities": [],
                "affected_relations": [],
            }
        ],
    }

    view_model = build_update_report_view_model(report)
    detail = view_model["details"]["feat-empty"]

    assert detail["after"]["label"] == MISSING_VALUE
