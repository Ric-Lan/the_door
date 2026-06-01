"""Unit tests for the shared find_latest_report_path helper."""
import json

from the_door.core.ui.api.report_paths import find_latest_report_path


def test_returns_none_when_no_dot_dir(tmp_path):
    assert find_latest_report_path(tmp_path) is None


def test_returns_none_when_no_reports(tmp_path):
    (tmp_path / ".the-door").mkdir()
    assert find_latest_report_path(tmp_path) is None


def test_picks_newest_by_generated_at(tmp_path):
    dot = tmp_path / ".the-door"
    dot.mkdir()
    older = dot / "update-report-a.json"
    newer = dot / "update-report-b.json"
    older.write_text(json.dumps({"generated_at": "2026-01-01T00:00:00"}), encoding="utf-8")
    newer.write_text(json.dumps({"generated_at": "2026-06-01T00:00:00"}), encoding="utf-8")

    assert find_latest_report_path(tmp_path) == newer


def test_falls_back_to_mtime_when_no_generated_at(tmp_path):
    dot = tmp_path / ".the-door"
    dot.mkdir()
    first = dot / "update-report-a.json"
    second = dot / "update-report-b.json"
    first.write_text(json.dumps({}), encoding="utf-8")
    second.write_text(json.dumps({}), encoding="utf-8")
    # Make `second` newer by mtime.
    import os
    os.utime(first, ns=(1_000_000_000, 1_000_000_000))
    os.utime(second, ns=(2_000_000_000, 2_000_000_000))

    assert find_latest_report_path(tmp_path) == second


def test_falls_back_to_mtime_when_json_corrupt(tmp_path):
    dot = tmp_path / ".the-door"
    dot.mkdir()
    good = dot / "update-report-a.json"
    bad = dot / "update-report-b.json"
    good.write_text(json.dumps({"generated_at": "2026-01-01T00:00:00"}), encoding="utf-8")
    bad.write_text("not valid json", encoding="utf-8")
    import os
    os.utime(bad, ns=(2_000_000_000, 2_000_000_000))
    # The corrupt file hits the except branch -> sorts by mtime (0, ...);
    # the good file with generated_at sorts as (1, ...) and wins.
    assert find_latest_report_path(tmp_path) == good
