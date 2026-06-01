"""Unit tests for AnnotationHandlers."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import pytest

from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.handlers.annotation import AnnotationHandlers
from the_door.core.ui.job_store import JobStore


def _ctx(tmp_path: Path) -> APIContext:
    return APIContext(lambda: tmp_path, lambda: JobStore(), lambda p, f: {})


class TestGetNotes:
    def test_missing_mode_returns_400(self, tmp_path):
        h = AnnotationHandlers(_ctx(tmp_path))
        status, body = h.get_notes(mode=None, feature_id="feat-x", version_a="v1", version_b="v2")
        assert status == 400
        assert body["error"]["code"] == "missing_params"

    def test_invalid_mode_returns_400(self, tmp_path):
        h = AnnotationHandlers(_ctx(tmp_path))
        status, body = h.get_notes(mode="unknown", feature_id="feat-x", version_a="v1", version_b="v2")
        assert status == 400
        assert body["error"]["code"] == "invalid_mode"

    def test_baseline_missing_version_a_returns_400(self, tmp_path):
        h = AnnotationHandlers(_ctx(tmp_path))
        status, body = h.get_notes(mode="baseline", feature_id="feat-x", version_a=None, version_b=None)
        assert status == 400

    def test_diff_mode_returns_notes(self, tmp_path):
        h = AnnotationHandlers(_ctx(tmp_path))
        with patch("the_door.core.ui.api.handlers.annotation.NoteStore") as mock_ns:
            mock_ns.return_value.list_notes.return_value = []
            status, body = h.get_notes(mode="diff", feature_id="feat-x", version_a="v1", version_b="v2")
        assert status == 200
        assert "notes" in body


class TestPostNotes:
    def test_missing_mode_returns_400(self, tmp_path):
        h = AnnotationHandlers(_ctx(tmp_path))
        status, body = h.post_notes(body={"feature_id": "feat-x", "name_input": "Bob", "comment": "hi"})
        assert status == 400

    def test_empty_name_returns_400(self, tmp_path):
        h = AnnotationHandlers(_ctx(tmp_path))
        status, body = h.post_notes(body={"mode": "diff", "feature_id": "feat-x", "name_input": "  ", "comment": "hi", "version_a": "v1", "version_b": "v2"})
        assert status == 400
        assert body["error"]["code"] == "empty_name"

    def test_comment_too_long_returns_400(self, tmp_path):
        h = AnnotationHandlers(_ctx(tmp_path))
        status, body = h.post_notes(body={
            "mode": "diff", "feature_id": "feat-x",
            "name_input": "Bob", "comment": "x" * 2001,
            "version_a": "v1", "version_b": "v2",
        })
        assert status == 400
        assert body["error"]["code"] == "comment_too_long"

    def test_valid_note_returns_201(self, tmp_path):
        h = AnnotationHandlers(_ctx(tmp_path))
        with patch("the_door.core.ui.api.handlers.annotation.NoteStore") as mock_ns:
            mock_ns.return_value.add_note.return_value = {"id": "note-1"}
            status, body = h.post_notes(body={
                "mode": "diff", "feature_id": "feat-x",
                "name_input": "Bob", "comment": "Great change",
                "version_a": "v1", "version_b": "v2",
            })
        assert status == 201
        assert "note" in body


class TestDoubts:
    def test_returns_doubts_and_summary(self, tmp_path):
        (tmp_path / ".the-door").mkdir()
        h = AnnotationHandlers(_ctx(tmp_path))
        with patch("the_door.core.ui.api.handlers.annotation.DoubtStore") as mock_ds:
            mock_ds.return_value.list_doubts.return_value = []
            status, body = h.doubts()
        assert status == 200
        assert body["summary"]["total"] == 0
