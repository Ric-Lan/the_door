"""Unit tests for APIHandlers notes endpoints.

Run: pytest tests/unit/core/ui/test_api_handlers_notes.py -v
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from the_door.core.ui.api_handlers import APIHandlers
from the_door.core.ui.job_store import JobStore


def _make_handlers(tmp_path: Path) -> APIHandlers:
    return APIHandlers(project_root=tmp_path, job_store=JobStore())


class TestGetNotes:
    def test_missing_mode_returns_400(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_get_notes(
            mode=None, feature_id="feat-x", version_a="v1", version_b="v2"
        )
        assert status == 400
        assert body["error"]["code"] == "missing_params"

    def test_missing_feature_id_returns_400(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_get_notes(
            mode="diff", feature_id=None, version_a="v1", version_b="v2"
        )
        assert status == 400

    def test_invalid_mode_returns_400(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_get_notes(
            mode="unknown", feature_id="feat-x", version_a="v1", version_b="v2"
        )
        assert status == 400
        assert body["error"]["code"] == "invalid_mode"

    def test_baseline_missing_version_a_returns_400(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_get_notes(
            mode="baseline", feature_id="feat-x", version_a=None, version_b=None
        )
        assert status == 400

    def test_current_missing_version_b_returns_400(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_get_notes(
            mode="current", feature_id="feat-x", version_a=None, version_b=None
        )
        assert status == 400

    def test_diff_missing_version_a_returns_400(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_get_notes(
            mode="diff", feature_id="feat-x", version_a=None, version_b="v2"
        )
        assert status == 400

    def test_diff_missing_version_b_returns_400(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_get_notes(
            mode="diff", feature_id="feat-x", version_a="v1", version_b=None
        )
        assert status == 400

    def test_valid_diff_returns_200_with_notes_list(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_get_notes(
            mode="diff", feature_id="feat-x", version_a="v1", version_b="v2"
        )
        assert status == 200
        assert "notes" in body
        assert isinstance(body["notes"], list)

    def test_valid_baseline_returns_200(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_get_notes(
            mode="baseline", feature_id="feat-x", version_a="v1", version_b=None
        )
        assert status == 200

    def test_valid_current_returns_200(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_get_notes(
            mode="current", feature_id="feat-x", version_a=None, version_b="v2"
        )
        assert status == 200

    def test_returns_only_matching_notes(self, tmp_path):
        h = _make_handlers(tmp_path)
        # Pre-add a note directly via NoteStore
        from the_door.core.ui.note_store import NoteStore
        NoteStore(tmp_path).add_note("diff", "feat-x", "v1", "v2", "Ric", "hello")
        NoteStore(tmp_path).add_note("diff", "feat-x", "v1", "v3", "Other", "nope")
        status, body = h.handle_get_notes("diff", "feat-x", "v1", "v2")
        assert status == 200
        assert len(body["notes"]) == 1
        assert body["notes"][0]["comment"] == "hello"


class TestPostNotes:
    def _valid_body(self, **overrides):
        base = {
            "mode": "diff",
            "feature_id": "feat-x",
            "version_a": "v1",
            "version_b": "v2",
            "name_input": "Ric",
            "comment": "looks good",
        }
        base.update(overrides)
        return base

    def test_valid_diff_note_returns_201(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_post_notes(self._valid_body())
        assert status == 201
        assert "note" in body
        assert body["note"]["feature_id"] == "feat-x"

    def test_empty_name_returns_400(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_post_notes(self._valid_body(name_input=""))
        assert status == 400
        assert body["error"]["code"] == "empty_name"

    def test_whitespace_only_name_returns_400(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_post_notes(self._valid_body(name_input="   "))
        assert status == 400

    def test_empty_comment_returns_400(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_post_notes(self._valid_body(comment=""))
        assert status == 400
        assert body["error"]["code"] == "empty_comment"

    def test_name_too_long_returns_400(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_post_notes(self._valid_body(name_input="x" * 41))
        assert status == 400
        assert body["error"]["code"] == "name_too_long"

    def test_comment_too_long_returns_400(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_post_notes(self._valid_body(comment="x" * 2001))
        assert status == 400
        assert body["error"]["code"] == "comment_too_long"

    def test_invalid_mode_returns_400(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_post_notes(self._valid_body(mode="bad"))
        assert status == 400

    def test_baseline_missing_version_a_returns_400(self, tmp_path):
        h = _make_handlers(tmp_path)
        status, body = h.handle_post_notes(
            self._valid_body(mode="baseline", version_a=None, version_b=None)
        )
        assert status == 400

    def test_note_not_persisted_on_validation_failure(self, tmp_path):
        h = _make_handlers(tmp_path)
        h.handle_post_notes(self._valid_body(name_input=""))
        jsonl_path = tmp_path / ".the-door" / "user-notes" / "notes.jsonl"
        assert not jsonl_path.exists()
