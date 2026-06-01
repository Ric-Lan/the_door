"""Unit tests for DiffHandlers."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.handlers.diff import DiffHandlers
from the_door.core.ui.job_store import JobStore


def _ctx(tmp_path: Path) -> APIContext:
    return APIContext(lambda: tmp_path, lambda: JobStore(), lambda p, f: {})


class TestVersions:
    def test_baseline_not_found_returns_404(self, tmp_path):
        h = DiffHandlers(_ctx(tmp_path))
        with patch("the_door.core.ui.api.handlers.diff.SnapshotStore") as mock_ss:
            mock_ss.return_value.resolve_baseline.return_value = None
            mock_ss.return_value.get_snapshot.return_value = None
            status, body = h.versions(baseline="v0", current="v1")
        assert status == 404
        assert body["error"]["code"] == "snapshot_not_found"

    def test_current_not_found_returns_404(self, tmp_path):
        h = DiffHandlers(_ctx(tmp_path))
        baseline_snap = MagicMock()
        with patch("the_door.core.ui.api.handlers.diff.SnapshotStore") as mock_ss:
            # resolve_baseline returns baseline for first call, None for current
            mock_ss.return_value.resolve_baseline.side_effect = [baseline_snap, None]
            mock_ss.return_value.get_snapshot.return_value = None
            status, body = h.versions(baseline="v0", current="v1")
        assert status == 404

    def test_valid_diff_returns_200(self, tmp_path):
        h = DiffHandlers(_ctx(tmp_path))
        baseline_snap = MagicMock()
        baseline_snap.version_id = "vid-a"
        baseline_snap.label = "v0"
        current_snap = MagicMock()
        current_snap.version_id = "vid-b"
        current_snap.label = "v1"
        diff_result = MagicMock()
        diff_result.node_diffs = []
        diff_result.summary.added_count = 0
        diff_result.summary.removed_count = 0
        diff_result.summary.attribute_changed_count = 0
        diff_result.summary.dependency_changed_count = 0
        diff_result.summary.total_changed_count = 0
        with (
            patch("the_door.core.ui.api.handlers.diff.SnapshotStore") as mock_ss,
            patch("the_door.core.ui.api.handlers.diff.DiffEngine") as mock_de,
            patch("the_door.core.ui.api.handlers.diff.StateInspector") as mock_si,
            patch("the_door.core.ui.api.handlers.diff.NextActionSuggester") as mock_nas,
        ):
            mock_ss.return_value.resolve_baseline.side_effect = [baseline_snap, current_snap]
            mock_de.return_value.compute_l1_diff.return_value = diff_result
            mock_si.return_value.inspect.return_value = MagicMock()
            mock_nas.return_value.suggest.return_value = []
            status, body = h.versions(baseline="v0", current="v1")
        assert status == 200
        assert "summary" in body


    def test_missing_params_returns_400(self, tmp_path):
        h = DiffHandlers(_ctx(tmp_path))
        status, body = h.versions(baseline=None, current="v1")
        assert status == 400
        assert body["error"]["code"] == "missing_params"

    def test_diff_engine_exception_returns_500(self, tmp_path):
        h = DiffHandlers(_ctx(tmp_path))
        with (
            patch("the_door.core.ui.api.handlers.diff.SnapshotStore") as mock_ss,
            patch("the_door.core.ui.api.handlers.diff.DiffEngine") as mock_de,
        ):
            mock_ss.return_value.resolve_baseline.side_effect = [MagicMock(), MagicMock()]
            mock_de.return_value.compute_l1_diff.side_effect = RuntimeError("kaboom")
            status, body = h.versions(baseline="v0", current="v1")
        assert status == 500
        assert body["error"]["code"] == "diff_error"

    def test_resolve_falls_back_to_get_snapshot(self, tmp_path):
        from the_door.models import SnapshotNotFoundError
        h = DiffHandlers(_ctx(tmp_path))
        snap = MagicMock()
        with patch("the_door.core.ui.api.handlers.diff.SnapshotStore") as mock_ss:
            store = mock_ss.return_value
            store.resolve_baseline.side_effect = SnapshotNotFoundError("nope", [])
            store.get_snapshot.return_value = snap
            result = h._resolve_snapshot(store, "v1")
        assert result is snap


class TestGetExplanation:
    def test_missing_params_returns_400(self, tmp_path):
        h = DiffHandlers(_ctx(tmp_path))
        status, body = h.get_explanation(
            feature_id="feat-x",
            baseline_version_id=None,
            current_version_id="v2",
            output_language="zh-Hant",
        )
        assert status == 400
        assert body["error"]["code"] == "missing_params"

    def test_no_cache_returns_200_with_none(self, tmp_path):
        h = DiffHandlers(_ctx(tmp_path))
        status, body = h.get_explanation(
            feature_id="feat-x",
            baseline_version_id="v1",
            current_version_id="v2",
            output_language="zh-Hant",
        )
        assert status == 200
        assert "explanation" in body


class TestGenerateExplanation:
    def test_missing_params_returns_400(self, tmp_path):
        h = DiffHandlers(_ctx(tmp_path))
        status, body = h.generate_explanation(
            feature_id="feat-x",
            body={"current_version_id": "v2"},
        )
        assert status == 400

    def test_provider_not_configured_returns_503(self, tmp_path):
        from the_door.core.llm.config_manager import ConfigError
        h = DiffHandlers(_ctx(tmp_path))
        with patch("the_door.core.ui.api.handlers.diff.ConfigManager") as mock_cm:
            mock_cm.load.side_effect = ConfigError("no config")
            status, body = h.generate_explanation(
                feature_id="feat-x",
                body={"baseline_version_id": "v1", "current_version_id": "v2"},
            )
        assert status == 503

    def test_valid_returns_200_with_entry(self, tmp_path):
        h = DiffHandlers(_ctx(tmp_path))
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=json.dumps({
            "impact_summary": "test",
            "possible_purpose": "test",
            "linked_resources": [],
            "caution": "none",
            "confidence": "high",
        }))
        with (
            patch("the_door.core.ui.api.handlers.diff.ConfigManager") as mock_cm,
            patch("the_door.core.ui.api.handlers.diff.create_provider", return_value=mock_provider),
        ):
            mock_cm.load.return_value = MagicMock()
            status, body = h.generate_explanation(
                feature_id="feat-x",
                body={"baseline_version_id": "v1", "current_version_id": "v2"},
            )
        assert status == 200
        assert "explanation" in body

    def test_body_none_returns_400(self, tmp_path):
        h = DiffHandlers(_ctx(tmp_path))
        status, body = h.generate_explanation(feature_id="feat-x")
        assert status == 400
        assert body["error"]["code"] == "missing_params"

    def test_non_json_llm_output_falls_back(self, tmp_path):
        h = DiffHandlers(_ctx(tmp_path))
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value="plain text, not json")
        with (
            patch("the_door.core.ui.api.handlers.diff.ConfigManager") as mock_cm,
            patch("the_door.core.ui.api.handlers.diff.create_provider", return_value=mock_provider),
        ):
            mock_cm.load.return_value = MagicMock()
            status, body = h.generate_explanation(
                feature_id="feat-x",
                body={"baseline_version_id": "v1", "current_version_id": "v2"},
            )
        assert status == 200
        assert body["explanation"]["confidence"] == "low"
        assert "plain text" in body["explanation"]["impact_summary"]

    def test_llm_call_failure_returns_500(self, tmp_path):
        h = DiffHandlers(_ctx(tmp_path))
        with (
            patch("the_door.core.ui.api.handlers.diff.ConfigManager") as mock_cm,
            patch("the_door.core.ui.api.handlers.diff.create_provider", return_value=MagicMock()),
            patch("the_door.core.ui.api.handlers.diff.asyncio.run", side_effect=RuntimeError("network down")),
        ):
            mock_cm.load.return_value = MagicMock()
            status, body = h.generate_explanation(
                feature_id="feat-x",
                body={"baseline_version_id": "v1", "current_version_id": "v2"},
            )
        assert status == 500
        assert body["error"]["code"] == "llm_error"


class TestCollectDiffContext:
    def test_context_from_l2_details(self, tmp_path):
        dot = tmp_path / ".the-door"; dot.mkdir()
        report = {
            "generated_at": "2024-01-01T00:00:00Z",
            "l2_details": [
                {
                    "feature_id": "feat-x",
                    "change_type": "attribute_changed",
                    "current_label": "New",
                    "current_description": "desc",
                    "baseline_label": "Old",
                    "baseline_description": "olddesc",
                    "affected_relations": [],
                }
            ],
        }
        (dot / "update-report-2024-01-01T00-00-00Z.json").write_text(
            json.dumps(report), encoding="utf-8"
        )
        h = DiffHandlers(_ctx(tmp_path))
        context = h._collect_diff_context("feat-x", "v1", "v2")
        assert context["change_type"] == "attribute_changed"
        assert context["current_label"] == "New"

    def test_context_from_l1_changes(self, tmp_path):
        dot = tmp_path / ".the-door"; dot.mkdir()
        report = {
            "generated_at": "2024-01-01T00:00:00Z",
            "l2_details": [],
            "l1_changes": [
                {"feature_id": "feat-y", "change_type": "added", "current_label": "Added"}
            ],
        }
        (dot / "update-report-2024-01-01T00-00-00Z.json").write_text(
            json.dumps(report), encoding="utf-8"
        )
        h = DiffHandlers(_ctx(tmp_path))
        context = h._collect_diff_context("feat-y", "v1", "v2")
        assert context["change_type"] == "added"
        assert context["current_label"] == "Added"

    def test_corrupt_report_returns_empty(self, tmp_path):
        dot = tmp_path / ".the-door"; dot.mkdir()
        (dot / "update-report-2024-01-01T00-00-00Z.json").write_text(
            "not json", encoding="utf-8"
        )
        h = DiffHandlers(_ctx(tmp_path))
        assert h._collect_diff_context("feat-x", "v1", "v2") == {}
