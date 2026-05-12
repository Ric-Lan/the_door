"""Unit tests for APIHandlers diff explanation endpoints.

Run: pytest tests/unit/core/ui/test_api_handlers_diff_explanation.py -v
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from the_door.core.ui.api_handlers import APIHandlers
from the_door.core.ui.job_store import JobStore


def _make_handlers(tmp_path: Path) -> APIHandlers:
    return APIHandlers(project_root=tmp_path, job_store=JobStore())


class TestGetDiffExplanation:
    def test_missing_baseline_version_id_returns_400(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_get_diff_explanation(
            feature_id="feat-x",
            baseline_version_id=None,
            current_version_id="v2",
            output_language="zh-Hant",
        )
        assert status == 400
        assert body["error"]["code"] == "missing_params"

    def test_missing_current_version_id_returns_400(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_get_diff_explanation(
            feature_id="feat-x",
            baseline_version_id="v1",
            current_version_id=None,
            output_language="zh-Hant",
        )
        assert status == 400

    def test_missing_output_language_returns_400(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_get_diff_explanation(
            feature_id="feat-x",
            baseline_version_id="v1",
            current_version_id="v2",
            output_language=None,
        )
        assert status == 400

    def test_returns_empty_state_when_no_cache(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_get_diff_explanation(
            feature_id="feat-x",
            baseline_version_id="v1",
            current_version_id="v2",
            output_language="zh-Hant",
        )
        assert status == 200
        assert body["explanation"] is None

    def test_returns_cached_explanation_when_present(self, tmp_path):
        from the_door.core.ui.diff_explanation_store import DiffExplanationStore
        entry = {
            "feature_id": "feat-x",
            "change_type": "attribute_changed",
            "impact_summary": "影響登入。",
            "possible_purpose": "改善安全性。",
            "linked_resources": [],
            "caution": "",
            "confidence": "medium",
            "language": "zh-Hant",
            "generated_at": "2026-05-11T00:00:00Z",
            "baseline_version_id": "v1",
            "current_version_id": "v2",
        }
        DiffExplanationStore(tmp_path).save(entry)
        h = _make_handlers(tmp_path)
        status, body = h.handle_get_diff_explanation("feat-x", "v1", "v2", "zh-Hant")
        assert status == 200
        assert body["explanation"] is not None
        assert body["explanation"]["impact_summary"] == "影響登入。"

    def test_get_does_not_trigger_llm(self, tmp_path):
        h = _make_handlers(tmp_path)
        with patch("the_door.core.ui.api_handlers.create_provider") as mock_provider:
            h.handle_get_diff_explanation("feat-x", "v1", "v2", "zh-Hant")
            mock_provider.assert_not_called()


class TestPostDiffExplanationGenerate:
    def _valid_body(self):
        return {
            "baseline_version_id": "v1",
            "current_version_id": "v2",
            "output_language": "zh-Hant",
        }

    def test_missing_baseline_version_id_returns_400(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_post_diff_explanation_generate(
            feature_id="feat-x",
            body={"current_version_id": "v2", "output_language": "zh-Hant"},
        )
        assert status == 400

    def test_missing_current_version_id_returns_400(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_post_diff_explanation_generate(
            feature_id="feat-x",
            body={"baseline_version_id": "v1", "output_language": "zh-Hant"},
        )
        assert status == 400

    def test_no_diff_data_returns_low_confidence_explanation(self, tmp_path):
        """When no diff data is available, a low-confidence explanation is still produced."""
        h = _make_handlers(tmp_path)
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=json.dumps({
            "impact_summary": "無足夠資料推論。",
            "possible_purpose": "無法判斷。",
            "linked_resources": [],
            "caution": "推論依據不足，請謹慎參考。",
            "confidence": "low",
        }))
        with (
            patch("the_door.core.ui.api_handlers.ConfigManager") as mock_cm,
            patch("the_door.core.ui.api_handlers.create_provider", return_value=mock_llm),
        ):
            mock_cm.load.return_value = MagicMock()
            status, body = h.handle_post_diff_explanation_generate(
                feature_id="feat-unknown", body=self._valid_body()
            )
        assert status == 200
        assert body["explanation"]["confidence"] == "low"

    def test_generate_saves_to_cache(self, tmp_path):
        h = _make_handlers(tmp_path)
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=json.dumps({
            "impact_summary": "影響登入。",
            "possible_purpose": "改善安全性。",
            "linked_resources": ["登入模組"],
            "caution": "",
            "confidence": "medium",
        }))
        with (
            patch("the_door.core.ui.api_handlers.ConfigManager") as mock_cm,
            patch("the_door.core.ui.api_handlers.create_provider", return_value=mock_llm),
        ):
            mock_cm.load.return_value = MagicMock()
            h.handle_post_diff_explanation_generate("feat-x", self._valid_body())
        from the_door.core.ui.diff_explanation_store import DiffExplanationStore
        cached = DiffExplanationStore(tmp_path).get("feat-x", "v1", "v2", "zh-Hant")
        assert cached is not None
        assert cached["impact_summary"] == "影響登入。"

    def test_generate_does_not_overwrite_update_report(self, tmp_path):
        """Generating via UI must not modify any update-report-*.json file."""
        report_path = tmp_path / ".the-door" / "update-report-test.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        original = '{"generated_at": "2026-05-11T00:00:00Z"}'
        report_path.write_text(original, encoding="utf-8")
        h = _make_handlers(tmp_path)
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=json.dumps({
            "impact_summary": "x", "possible_purpose": "y",
            "linked_resources": [], "caution": "", "confidence": "low",
        }))
        with (
            patch("the_door.core.ui.api_handlers.ConfigManager") as mock_cm,
            patch("the_door.core.ui.api_handlers.create_provider", return_value=mock_llm),
        ):
            mock_cm.load.return_value = MagicMock()
            h.handle_post_diff_explanation_generate("feat-x", self._valid_body())
        assert report_path.read_text(encoding="utf-8") == original

    def test_provider_not_configured_returns_503(self, tmp_path):
        from the_door.core.llm.config_manager import ConfigError
        h = _make_handlers(tmp_path)
        with patch("the_door.core.ui.api_handlers.ConfigManager") as mock_cm:
            mock_cm.load.side_effect = ConfigError("no config")
            status, body = h.handle_post_diff_explanation_generate(
                "feat-x", self._valid_body()
            )
        assert status == 503
        assert body["error"]["code"] == "provider_not_configured"
