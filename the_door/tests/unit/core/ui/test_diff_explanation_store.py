"""Unit tests for DiffExplanationStore.

Run: pytest tests/unit/core/ui/test_diff_explanation_store.py -v
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from the_door.core.ui.diff_explanation_store import DiffExplanationStore


def _make_entry(**overrides) -> dict:
    base = {
        "feature_id": "feat-auth",
        "change_type": "attribute_changed",
        "impact_summary": "影響登入流程。",
        "possible_purpose": "可能為了改善安全性。",
        "linked_resources": ["登入模組"],
        "caution": "推論依據有限。",
        "confidence": "medium",
        "language": "zh-Hant",
        "generated_at": "2026-05-11T00:00:00Z",
        "baseline_version_id": "v1",
        "current_version_id": "v2",
    }
    base.update(overrides)
    return base


class TestDiffExplanationStoreWrite:
    def test_save_creates_jsonl_file(self, tmp_path):
        store = DiffExplanationStore(tmp_path)
        store.save(_make_entry())
        path = tmp_path / ".the-door" / "diff-explanations" / "cache.jsonl"
        assert path.exists()

    def test_save_appends_to_jsonl(self, tmp_path):
        store = DiffExplanationStore(tmp_path)
        store.save(_make_entry())
        store.save(_make_entry(confidence="high"))
        path = tmp_path / ".the-door" / "diff-explanations" / "cache.jsonl"
        lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 2

    def test_save_persists_all_fields(self, tmp_path):
        store = DiffExplanationStore(tmp_path)
        entry = _make_entry()
        store.save(entry)
        path = tmp_path / ".the-door" / "diff-explanations" / "cache.jsonl"
        saved = json.loads(path.read_text(encoding="utf-8").strip())
        assert saved["feature_id"] == "feat-auth"
        assert saved["confidence"] == "medium"
        assert saved["linked_resources"] == ["登入模組"]


class TestDiffExplanationStoreGet:
    def test_get_returns_none_when_file_missing(self, tmp_path):
        store = DiffExplanationStore(tmp_path)
        result = store.get("feat-auth", "v1", "v2", "zh-Hant")
        assert result is None

    def test_get_returns_latest_matching_entry(self, tmp_path):
        store = DiffExplanationStore(tmp_path)
        store.save(_make_entry(impact_summary="first"))
        store.save(_make_entry(impact_summary="second"))
        result = store.get("feat-auth", "v1", "v2", "zh-Hant")
        assert result is not None
        assert result["impact_summary"] == "second"

    def test_get_returns_none_when_key_does_not_match(self, tmp_path):
        store = DiffExplanationStore(tmp_path)
        store.save(_make_entry())
        assert store.get("feat-auth", "v1", "v3", "zh-Hant") is None
        assert store.get("feat-other", "v1", "v2", "zh-Hant") is None
        assert store.get("feat-auth", "v1", "v2", "en") is None

    def test_get_skips_corrupted_lines(self, tmp_path):
        path = tmp_path / ".the-door" / "diff-explanations" / "cache.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        good = json.dumps(_make_entry())
        path.write_text("BAD_JSON\n" + good + "\n", encoding="utf-8")
        store = DiffExplanationStore(tmp_path)
        result = store.get("feat-auth", "v1", "v2", "zh-Hant")
        assert result is not None
        assert result["feature_id"] == "feat-auth"
