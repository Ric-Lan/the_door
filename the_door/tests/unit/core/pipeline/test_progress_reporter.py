"""Tests for ProgressReporter abstraction (file-level progress channel)."""
from __future__ import annotations

import pytest

from the_door.core.pipeline.progress_reporter import (
    ProgressReporter,
    NoOpProgressReporter,
)


def test_reporter_default_state_is_none():
    captured = []
    r = ProgressReporter(sink=lambda d: captured.append(dict(d)))
    assert captured == []  # no auto-emit on construction


def test_report_file_emits_full_payload():
    captured = []
    r = ProgressReporter(sink=lambda d: captured.append(dict(d)))
    r.set_total(247, root="new")
    r.report_file("src/foo.py")
    assert captured[-1] == {
        "files_done": 1, "files_total": 247,
        "current_file": "src/foo.py", "current_root": "new",
    }


def test_report_file_increments_done():
    captured = []
    r = ProgressReporter(sink=lambda d: captured.append(dict(d)))
    r.set_total(10, root="new")
    r.report_file("a.py")
    r.report_file("b.py")
    assert [d["files_done"] for d in captured] == [1, 2]


def test_report_file_without_set_total_uses_zero_total():
    captured = []
    r = ProgressReporter(sink=lambda d: captured.append(dict(d)))
    r.report_file("a.py")
    assert captured[-1]["files_total"] == 0
    assert captured[-1]["files_done"] == 1


def test_switch_root_resets_done():
    captured = []
    r = ProgressReporter(sink=lambda d: captured.append(dict(d)))
    r.set_total(10, root="old")
    r.report_file("a.py")
    r.set_total(20, root="new")
    r.report_file("b.py")
    assert captured[-1] == {
        "files_done": 1, "files_total": 20,
        "current_file": "b.py", "current_root": "new",
    }


def test_noop_reporter_swallows_calls():
    r = NoOpProgressReporter()
    r.set_total(10, root="new")
    r.report_file("a.py")  # must not raise


def test_done_never_exceeds_total():
    captured = []
    r = ProgressReporter(sink=lambda d: captured.append(dict(d)))
    r.set_total(2, root="new")
    r.report_file("a.py")
    r.report_file("b.py")
    r.report_file("c.py")  # overflow
    assert captured[-1]["files_done"] == 2
    assert captured[-1]["files_total"] == 2


def test_current_root_invalid_raises():
    r = ProgressReporter(sink=lambda d: None)
    with pytest.raises(ValueError, match="root must be 'new' or 'old'"):
        r.set_total(10, root="bogus")
