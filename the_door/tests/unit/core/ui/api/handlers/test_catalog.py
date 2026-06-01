"""Unit tests for CatalogHandlers."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.handlers.catalog import CatalogHandlers
from the_door.core.ui.job_store import JobStore


def _ctx(tmp_path: Path) -> APIContext:
    return APIContext(lambda: tmp_path, lambda: JobStore(), lambda p, f: {})


class TestSnapshots:
    def test_returns_200_with_empty_list(self, tmp_path):
        h = CatalogHandlers(_ctx(tmp_path))
        with patch("the_door.core.ui.api.handlers.catalog.SnapshotStore") as mock_ss:
            mock_ss.return_value.list_snapshots.return_value = []
            status, body = h.snapshots()
        assert status == 200
        assert body["snapshots"] == []

    def test_returns_sorted_snapshots(self, tmp_path):
        h = CatalogHandlers(_ctx(tmp_path))
        snap1 = MagicMock(); snap1.timestamp = "2024-01-01T00:00:00Z"
        snap2 = MagicMock(); snap2.timestamp = "2024-06-01T00:00:00Z"
        with patch("the_door.core.ui.api.handlers.catalog.SnapshotStore") as mock_ss:
            mock_ss.return_value.list_snapshots.return_value = [snap1, snap2]
            with patch("the_door.core.ui.api.handlers.catalog.serialize_snapshot", side_effect=lambda s: {"ts": s.timestamp}):
                status, body = h.snapshots()
        assert status == 200
        assert body["snapshots"][0]["ts"] == "2024-06-01T00:00:00Z"


class TestTimeline:
    def test_no_snapshots_returns_empty(self, tmp_path):
        h = CatalogHandlers(_ctx(tmp_path))
        with patch("the_door.core.ui.api.handlers.catalog.SnapshotStore") as mock_ss:
            mock_ss.return_value.list_snapshots.return_value = []
            status, body = h.timeline()
        assert status == 200

    def test_snapshots_calls_timeline_engine(self, tmp_path):
        h = CatalogHandlers(_ctx(tmp_path))
        snap = MagicMock()
        with (
            patch("the_door.core.ui.api.handlers.catalog.SnapshotStore") as mock_ss,
            patch("the_door.core.ui.api.handlers.catalog.TimelineEngine") as mock_te,
            patch("the_door.core.ui.api.handlers.catalog.serialize_timeline_result", return_value={"ok": True}),
        ):
            mock_ss.return_value.list_snapshots.return_value = [snap]
            mock_te.return_value.analyze.return_value = MagicMock()
            status, body = h.timeline()
        assert status == 200
        assert body == {"ok": True}


class TestReportLatest:
    def test_no_report_returns_404(self, tmp_path):
        h = CatalogHandlers(_ctx(tmp_path))
        status, body = h.report_latest()
        assert status == 404
        assert body["error"]["code"] == "no_report_found"

    def test_valid_report_returns_200(self, tmp_path):
        dot = tmp_path / ".the-door"; dot.mkdir()
        report = {"generated_at": "2024-01-01T00:00:00Z", "summary": {}}
        report_file = dot / "update-report-2024-01-01T00-00-00Z.json"
        report_file.write_text(json.dumps(report), encoding="utf-8")
        h = CatalogHandlers(_ctx(tmp_path))
        status, body = h.report_latest()
        assert status == 200
        assert body["generated_at"] == "2024-01-01T00:00:00Z"

    def test_report_parse_error_returns_500(self, tmp_path):
        dot = tmp_path / ".the-door"; dot.mkdir()
        # generated_at present so find_latest sorts it, but body is invalid JSON
        report_file = dot / "update-report-2024-01-01T00-00-00Z.json"
        report_file.write_text("not json", encoding="utf-8")
        h = CatalogHandlers(_ctx(tmp_path))
        status, body = h.report_latest()
        assert status == 500
        assert body["error"]["code"] == "report_parse_error"

    def test_report_read_error_returns_500(self, tmp_path):
        dot = tmp_path / ".the-door"; dot.mkdir()
        report_file = dot / "update-report-2024-01-01T00-00-00Z.json"
        report_file.write_text('{"generated_at": "x"}', encoding="utf-8")
        h = CatalogHandlers(_ctx(tmp_path))
        with patch("the_door.core.ui.api.handlers.catalog.find_latest_report_path", return_value=report_file):
            with patch.object(Path, "read_text", side_effect=OSError("io")):
                status, body = h.report_latest()
        assert status == 500
        assert body["error"]["code"] == "report_read_error"


class TestCatalogErrorBranches:
    def test_snapshots_exception_returns_500(self, tmp_path):
        h = CatalogHandlers(_ctx(tmp_path))
        with patch("the_door.core.ui.api.handlers.catalog.SnapshotStore", side_effect=RuntimeError("x")):
            status, body = h.snapshots()
        assert status == 500
        assert body["error"]["code"] == "snapshot_read_error"

    def test_timeline_exception_returns_500(self, tmp_path):
        h = CatalogHandlers(_ctx(tmp_path))
        with patch("the_door.core.ui.api.handlers.catalog.SnapshotStore", side_effect=RuntimeError("x")):
            status, body = h.timeline()
        assert status == 500
        assert body["error"]["code"] == "timeline_error"
