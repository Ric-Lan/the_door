"""Unit tests for NoteStore.

Run: pytest tests/unit/core/ui/test_note_store.py -v
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from the_door.core.ui.note_store import NoteStore


class TestNoteStoreAddAndList:
    def test_add_note_returns_dict_with_required_keys(self, tmp_path):
        store = NoteStore(tmp_path)
        note = store.add_note(
            mode="diff",
            feature_id="feat-auth",
            version_a="v1",
            version_b="v2",
            name_input="Ric",
            comment="This change looks correct.",
        )
        assert note["mode"] == "diff"
        assert note["feature_id"] == "feat-auth"
        assert note["version_a"] == "v1"
        assert note["version_b"] == "v2"
        assert note["name_input"] == "Ric"
        assert note["comment"] == "This change looks correct."
        assert "note_id" in note
        assert "display_name" in note
        assert "created_at" in note

    def test_display_name_format_is_name_plus_date(self, tmp_path):
        store = NoteStore(tmp_path)
        note = store.add_note("diff", "feat-x", "v1", "v2", "PM確認", "ok")
        # display_name starts with name_input and ends with 8-digit date
        assert note["display_name"].startswith("PM確認")
        suffix = note["display_name"][len("PM確認"):]
        assert len(suffix) == 8
        assert suffix.isdigit()

    def test_display_name_uses_local_date_not_utc(self, tmp_path):
        import datetime
        store = NoteStore(tmp_path)
        note = store.add_note("diff", "feat-x", "v1", "v2", "Test", "msg")
        expected_date = datetime.date.today().strftime("%Y%m%d")
        assert note["display_name"].endswith(expected_date)

    def test_add_note_persists_to_jsonl(self, tmp_path):
        store = NoteStore(tmp_path)
        store.add_note("diff", "feat-x", "v1", "v2", "A", "note")
        jsonl_path = tmp_path / ".the-door" / "user-notes" / "notes.jsonl"
        assert jsonl_path.exists()
        lines = [l for l in jsonl_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["feature_id"] == "feat-x"

    def test_multiple_notes_append_to_jsonl(self, tmp_path):
        store = NoteStore(tmp_path)
        store.add_note("diff", "feat-x", "v1", "v2", "A", "first")
        store.add_note("diff", "feat-x", "v1", "v2", "B", "second")
        jsonl_path = tmp_path / ".the-door" / "user-notes" / "notes.jsonl"
        lines = [l for l in jsonl_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 2

    def test_list_notes_returns_matching_diff_notes(self, tmp_path):
        store = NoteStore(tmp_path)
        store.add_note("diff", "feat-x", "v1", "v2", "A", "for diff")
        store.add_note("diff", "feat-x", "v1", "v3", "B", "different v2")
        store.add_note("baseline", "feat-x", "v1", None, "C", "for baseline")
        results = store.list_notes("diff", "feat-x", "v1", "v2")
        assert len(results) == 1
        assert results[0]["comment"] == "for diff"

    def test_list_notes_baseline_matches_only_version_a(self, tmp_path):
        store = NoteStore(tmp_path)
        store.add_note("baseline", "feat-x", "v1", None, "A", "baseline note")
        store.add_note("baseline", "feat-x", "v2", None, "B", "other baseline")
        results = store.list_notes("baseline", "feat-x", "v1", None)
        assert len(results) == 1
        assert results[0]["comment"] == "baseline note"

    def test_list_notes_current_matches_only_version_b(self, tmp_path):
        store = NoteStore(tmp_path)
        store.add_note("current", "feat-x", None, "v2", "A", "current note")
        store.add_note("current", "feat-x", None, "v3", "B", "other current")
        results = store.list_notes("current", "feat-x", None, "v2")
        assert len(results) == 1
        assert results[0]["comment"] == "current note"

    def test_list_notes_empty_when_no_file(self, tmp_path):
        store = NoteStore(tmp_path)
        assert store.list_notes("diff", "feat-x", "v1", "v2") == []

    def test_list_notes_skips_corrupted_lines(self, tmp_path):
        jsonl_path = tmp_path / ".the-door" / "user-notes" / "notes.jsonl"
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        good = json.dumps({
            "note_id": "1", "mode": "diff", "feature_id": "feat-x",
            "version_a": "v1", "version_b": "v2",
            "display_name": "A20260511", "name_input": "A", "comment": "ok",
            "created_at": "2026-05-11T00:00:00Z",
        })
        jsonl_path.write_text("NOT_JSON\n" + good + "\n", encoding="utf-8")
        store = NoteStore(tmp_path)
        results = store.list_notes("diff", "feat-x", "v1", "v2")
        assert len(results) == 1
        assert results[0]["comment"] == "ok"

    def test_name_input_is_stripped(self, tmp_path):
        store = NoteStore(tmp_path)
        note = store.add_note("diff", "feat-x", "v1", "v2", "  Ric  ", "msg")
        assert note["name_input"] == "Ric"
        assert note["display_name"].startswith("Ric")

    def test_comment_is_stripped(self, tmp_path):
        store = NoteStore(tmp_path)
        note = store.add_note("diff", "feat-x", "v1", "v2", "A", "  msg  ")
        assert note["comment"] == "msg"
