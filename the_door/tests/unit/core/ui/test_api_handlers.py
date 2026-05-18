"""Unit tests for APIHandlers — all 30 tests.

All core modules (SnapshotStore, DoubtStore, TimelineEngine,
PipelineOrchestrator, ReportRenderer) are mocked.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from the_door.core.ui.api_handlers import APIHandlers
from the_door.core.ui.job_store import JobStore, UpdateJob
from the_door.models import (
    DoubtRecord,
    FeatureTimeline,
    TimelineResult,
    TimelineSummary,
    VersionSnapshot,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snapshot(version_id: str = "v1", timestamp: str = "2024-01-01T00:00:00Z") -> VersionSnapshot:
    return VersionSnapshot(
        version_id=version_id,
        timestamp=timestamp,
        trigger="manual",
        label=None,
        git_tags=[],
    )


def _make_doubt(doubt_id: str = "d1") -> DoubtRecord:
    return DoubtRecord(
        doubt_id=doubt_id,
        source_node="feat-1",
        doubt_type="out_of_scope",
        current_state="discovered",
        created_by="test",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        assigned_to=None,
    )


def _make_handlers(tmp_path: Path) -> APIHandlers:
    job_store = JobStore()
    return APIHandlers(project_root=tmp_path, job_store=job_store)


def _make_handlers_with_dot_dir(tmp_path: Path) -> APIHandlers:
    (tmp_path / ".the-door").mkdir()
    return _make_handlers(tmp_path)


# ---------------------------------------------------------------------------
# GET /api/project
# ---------------------------------------------------------------------------


class TestGetProject:
    def test_get_project_dot_dir_exists(self, tmp_path):
        (tmp_path / ".the-door").mkdir()
        handlers = _make_handlers(tmp_path)
        with (
            patch("the_door.core.ui.api_handlers.SnapshotStore") as mock_ss,
            patch("the_door.core.ui.api_handlers.DoubtStore") as mock_ds,
        ):
            mock_ss.return_value.list_snapshots.return_value = []
            mock_ds.return_value.list_doubts.return_value = []
            status, body = handlers.handle_get_project()
        assert status == 200
        assert body["dot_the_door_exists"] is True

    def test_get_project_dot_dir_missing(self, tmp_path):
        handlers = _make_handlers(tmp_path)
        status, body = handlers.handle_get_project()
        assert status == 200
        assert body["dot_the_door_exists"] is False
        ad = body["available_data"]
        assert ad["has_snapshots"] is False
        assert ad["has_latest_report"] is False
        assert ad["has_doubts"] is False
        assert ad["has_scope_config"] is False

    def test_get_project_available_data_fields(self, tmp_path):
        dot = tmp_path / ".the-door"
        dot.mkdir()
        (dot / "scope-config.json").write_text("{}", encoding="utf-8")
        # Create a report file so has_latest_report is True
        report = {"generated_at": "2024-01-01T00:00:00Z"}
        (dot / "update-report-2024-01-01T00-00-00Z.json").write_text(
            json.dumps(report), encoding="utf-8"
        )
        handlers = _make_handlers(tmp_path)
        with (
            patch("the_door.core.ui.api_handlers.SnapshotStore") as mock_ss,
            patch("the_door.core.ui.api_handlers.DoubtStore") as mock_ds,
        ):
            mock_ss.return_value.list_snapshots.return_value = [_make_snapshot()]
            mock_ds.return_value.list_doubts.return_value = []
            status, body = handlers.handle_get_project()
        assert status == 200
        ad = body["available_data"]
        assert ad["has_snapshots"] is True
        assert ad["has_doubts"] is False
        assert ad["has_scope_config"] is True
        assert ad["has_latest_report"] is True

    def test_get_project_exception_returns_500(self, tmp_path):
        (tmp_path / ".the-door").mkdir()
        handlers = _make_handlers(tmp_path)
        with patch("the_door.core.ui.api_handlers.SnapshotStore") as mock_ss:
            mock_ss.return_value.list_snapshots.side_effect = RuntimeError("boom")
            status, body = handlers.handle_get_project()
        assert status == 500
        assert "error" in body


# ---------------------------------------------------------------------------
# GET /api/snapshots
# ---------------------------------------------------------------------------


class TestGetSnapshots:
    def test_get_snapshots_returns_sorted_list(self, tmp_path):
        handlers = _make_handlers(tmp_path)
        s1 = _make_snapshot("v1", "2024-01-01T00:00:00Z")
        s2 = _make_snapshot("v2", "2024-06-01T00:00:00Z")
        with patch("the_door.core.ui.api_handlers.SnapshotStore") as mock_ss:
            mock_ss.return_value.list_snapshots.return_value = [s1, s2]
            status, body = handlers.handle_get_snapshots()
        assert status == 200
        snapshots = body["snapshots"]
        assert len(snapshots) == 2
        # Newest first
        assert snapshots[0]["version_id"] == "v2"
        assert snapshots[1]["version_id"] == "v1"

    def test_get_snapshots_empty(self, tmp_path):
        handlers = _make_handlers(tmp_path)
        with patch("the_door.core.ui.api_handlers.SnapshotStore") as mock_ss:
            mock_ss.return_value.list_snapshots.return_value = []
            status, body = handlers.handle_get_snapshots()
        assert status == 200
        assert body == {"snapshots": []}

    def test_get_snapshots_exception_returns_500(self, tmp_path):
        handlers = _make_handlers(tmp_path)
        with patch("the_door.core.ui.api_handlers.SnapshotStore") as mock_ss:
            mock_ss.return_value.list_snapshots.side_effect = RuntimeError("disk error")
            status, body = handlers.handle_get_snapshots()
        assert status == 500
        assert body["error"]["code"] == "snapshot_read_error"


# ---------------------------------------------------------------------------
# GET /api/report/latest
# ---------------------------------------------------------------------------


class TestGetReportLatest:
    def test_get_report_latest_found(self, tmp_path):
        dot = tmp_path / ".the-door"
        dot.mkdir()
        report = {"generated_at": "2024-01-01T00:00:00Z", "l0_summary": "ok"}
        (dot / "update-report-2024-01-01T00-00-00Z.json").write_text(
            json.dumps(report), encoding="utf-8"
        )
        handlers = _make_handlers(tmp_path)
        status, body = handlers.handle_get_report_latest()
        assert status == 200
        assert body["l0_summary"] == "ok"

    def test_get_report_latest_not_found(self, tmp_path):
        handlers = _make_handlers(tmp_path)
        status, body = handlers.handle_get_report_latest()
        assert status == 404
        assert body["error"]["code"] == "no_report_found"

    def test_get_report_latest_invalid_json(self, tmp_path):
        dot = tmp_path / ".the-door"
        dot.mkdir()
        (dot / "update-report-bad.json").write_text("NOT JSON", encoding="utf-8")
        handlers = _make_handlers(tmp_path)
        status, body = handlers.handle_get_report_latest()
        assert status == 500
        assert body["error"]["code"] == "report_parse_error"

    def test_get_report_latest_selects_newest_by_generated_at(self, tmp_path):
        dot = tmp_path / ".the-door"
        dot.mkdir()
        old_report = {"generated_at": "2024-01-01T00:00:00Z", "label": "old"}
        new_report = {"generated_at": "2024-06-01T00:00:00Z", "label": "new"}
        (dot / "update-report-old.json").write_text(json.dumps(old_report), encoding="utf-8")
        (dot / "update-report-new.json").write_text(json.dumps(new_report), encoding="utf-8")
        handlers = _make_handlers(tmp_path)
        status, body = handlers.handle_get_report_latest()
        assert status == 200
        assert body["label"] == "new"

    def test_get_report_latest_fallback_to_mtime(self, tmp_path):
        dot = tmp_path / ".the-door"
        dot.mkdir()
        # File with invalid/missing generated_at — mtime fallback
        report_a = {"label": "a"}  # no generated_at
        report_b = {"label": "b"}  # no generated_at
        path_a = dot / "update-report-a.json"
        path_b = dot / "update-report-b.json"
        path_a.write_text(json.dumps(report_a), encoding="utf-8")
        time.sleep(0.05)  # ensure different mtime
        path_b.write_text(json.dumps(report_b), encoding="utf-8")
        handlers = _make_handlers(tmp_path)
        status, body = handlers.handle_get_report_latest()
        assert status == 200
        # b was written later, so it should be selected
        assert body["label"] == "b"


# ---------------------------------------------------------------------------
# POST /api/update
# ---------------------------------------------------------------------------


class TestPostUpdate:
    def test_post_update_missing_field(self, tmp_path):
        handlers = _make_handlers(tmp_path)
        status, body = handlers.handle_post_update({"old_path": str(tmp_path)})
        assert status == 400
        assert body["error"]["code"] == "missing_required_field"

    def test_post_update_invalid_path(self, tmp_path):
        handlers = _make_handlers(tmp_path)
        status, body = handlers.handle_post_update({
            "old_path": str(tmp_path / "nonexistent"),
            "new_path": str(tmp_path),
        })
        assert status == 400
        assert body["error"]["code"] == "invalid_path"

    def test_post_update_same_path(self, tmp_path):
        handlers = _make_handlers(tmp_path)
        status, body = handlers.handle_post_update({
            "old_path": str(tmp_path),
            "new_path": str(tmp_path),
        })
        assert status == 400
        assert body["error"]["code"] == "same_path"

    def test_post_update_job_already_running(self, tmp_path):
        old_dir = tmp_path / "old"
        new_dir = tmp_path / "new"
        old_dir.mkdir()
        new_dir.mkdir()
        job_store = JobStore()
        job_store.try_create_job()  # simulate running job
        handlers = APIHandlers(project_root=tmp_path, job_store=job_store)
        status, body = handlers.handle_post_update({
            "old_path": str(old_dir),
            "new_path": str(new_dir),
        })
        assert status == 409
        assert body["error"]["code"] == "job_already_running"

    def test_post_update_path_outside_project_root(self, tmp_path):
        import tempfile
        with tempfile.TemporaryDirectory() as outside:
            outside_path = Path(outside)
            old_dir = tmp_path / "old"
            old_dir.mkdir()
            handlers = _make_handlers(tmp_path)
            status, body = handlers.handle_post_update({
                "old_path": str(old_dir),
                "new_path": str(outside_path),
            })
        assert status == 400
        assert body["error"]["code"] == "invalid_path"

    def test_post_update_success_returns_202_with_job_id(self, tmp_path):
        old_dir = tmp_path / "old"
        new_dir = tmp_path / "new"
        old_dir.mkdir()
        new_dir.mkdir()
        handlers = _make_handlers(tmp_path)
        with patch("threading.Thread") as mock_thread:
            mock_thread.return_value = MagicMock()
            status, body = handlers.handle_post_update({
                "old_path": str(old_dir),
                "new_path": str(new_dir),
            })
        assert status == 202
        assert "job_id" in body
        assert isinstance(body["job_id"], str)

    def test_post_update_pipeline_runs_in_background(self, tmp_path):
        old_dir = tmp_path / "old"
        new_dir = tmp_path / "new"
        old_dir.mkdir()
        new_dir.mkdir()
        handlers = _make_handlers(tmp_path)
        with patch("threading.Thread") as mock_thread_cls:
            mock_thread_instance = MagicMock()
            mock_thread_cls.return_value = mock_thread_instance
            status, body = handlers.handle_post_update({
                "old_path": str(old_dir),
                "new_path": str(new_dir),
            })
        assert status == 202
        mock_thread_instance.start.assert_called_once()

    def test_post_update_persists_report_on_completion(self, tmp_path):
        old_dir = tmp_path / "old"
        new_dir = tmp_path / "new"
        old_dir.mkdir()
        new_dir.mkdir()
        (tmp_path / ".the-door").mkdir()
        job_store = JobStore()
        handlers = APIHandlers(project_root=tmp_path, job_store=job_store)
        job = job_store.try_create_job()
        report = {"generated_at": "2024-01-01T12:00:00Z", "l0_summary": "done"}
        with (
            patch("the_door.core.ui.api_handlers.PipelineOrchestrator") as mock_orch,
            patch("the_door.core.ui.api_handlers.ReportRenderer") as mock_rr,
        ):
            mock_orch.return_value.run.return_value = MagicMock()
            mock_rr.return_value.render_json.return_value = report
            handlers._run_pipeline_job(job, old_dir, new_dir)
        dot = tmp_path / ".the-door"
        report_files = list(dot.glob("update-report-*.json"))
        assert len(report_files) == 1
        saved = json.loads(report_files[0].read_text(encoding="utf-8"))
        assert saved["l0_summary"] == "done"

    def test_post_update_passes_output_language_to_pipeline(self, tmp_path):
        """output_language in body is forwarded as the 4th arg to _run_pipeline_job."""
        old_dir = tmp_path / "old"
        new_dir = tmp_path / "new"
        old_dir.mkdir()
        new_dir.mkdir()
        handlers = _make_handlers(tmp_path)
        with patch("threading.Thread") as mock_thread_cls:
            mock_thread_cls.return_value = MagicMock()
            handlers.handle_post_update({
                "old_path": str(old_dir),
                "new_path": str(new_dir),
                "output_language": "en",
            })
        _, kwargs = mock_thread_cls.call_args
        assert "en" in kwargs.get("args", ())

    def test_post_update_default_output_language_is_zh_hant(self, tmp_path):
        """When output_language is omitted, _run_pipeline_job receives 'zh-Hant'."""
        old_dir = tmp_path / "old"
        new_dir = tmp_path / "new"
        old_dir.mkdir()
        new_dir.mkdir()
        handlers = _make_handlers(tmp_path)
        with patch("threading.Thread") as mock_thread_cls:
            mock_thread_cls.return_value = MagicMock()
            handlers.handle_post_update({
                "old_path": str(old_dir),
                "new_path": str(new_dir),
            })
        _, kwargs = mock_thread_cls.call_args
        assert "zh-Hant" in kwargs.get("args", ())


# ---------------------------------------------------------------------------
# GET /api/update/status/<job_id>
# ---------------------------------------------------------------------------


class TestGetUpdateStatus:
    def test_get_update_status_running(self, tmp_path):
        job_store = JobStore()
        job = job_store.try_create_job()
        job.current_step = "DiffEngine"
        handlers = APIHandlers(project_root=tmp_path, job_store=job_store)
        status, body = handlers.handle_get_update_status(job.job_id)
        assert status == 200
        assert body["status"] == "running"
        assert body["current_step"] is not None

    def test_get_update_status_completed(self, tmp_path):
        job_store = JobStore()
        job = job_store.try_create_job()
        job.steps.append({"step_name": "DiffEngine", "status": "completed", "duration_ms": 100, "error_message": None})
        job_store.complete_job(job.job_id)
        handlers = APIHandlers(project_root=tmp_path, job_store=job_store)
        status, body = handlers.handle_get_update_status(job.job_id)
        assert status == 200
        assert body["status"] == "completed"
        assert body["current_step"] is None
        assert len(body["steps"]) > 0

    def test_get_update_status_failed(self, tmp_path):
        job_store = JobStore()
        job = job_store.try_create_job()
        job_store.fail_job(job.job_id, "something went wrong")
        handlers = APIHandlers(project_root=tmp_path, job_store=job_store)
        status, body = handlers.handle_get_update_status(job.job_id)
        assert status == 200
        assert body["status"] == "failed"
        assert body["error_message"] is not None

    def test_get_update_status_unknown_job(self, tmp_path):
        handlers = _make_handlers(tmp_path)
        status, body = handlers.handle_get_update_status("nonexistent-job-id")
        assert status == 404
        assert body["error"]["code"] == "job_not_found"


# ---------------------------------------------------------------------------
# GET /api/doubts
# ---------------------------------------------------------------------------


class TestGetDoubts:
    def test_get_doubts_returns_list(self, tmp_path):
        handlers = _make_handlers(tmp_path)
        doubt = _make_doubt()
        with patch("the_door.core.ui.api_handlers.DoubtStore") as mock_ds:
            mock_ds.return_value.list_doubts.return_value = [doubt]
            status, body = handlers.handle_get_doubts()
        assert status == 200
        assert len(body["doubts"]) == 1
        assert body["summary"]["total"] == 1

    def test_get_doubts_empty(self, tmp_path):
        handlers = _make_handlers(tmp_path)
        with patch("the_door.core.ui.api_handlers.DoubtStore") as mock_ds:
            mock_ds.return_value.list_doubts.return_value = []
            status, body = handlers.handle_get_doubts()
        assert status == 200
        assert body == {"doubts": [], "summary": {"total": 0}}

    def test_get_doubts_exception_returns_500(self, tmp_path):
        handlers = _make_handlers(tmp_path)
        with patch("the_door.core.ui.api_handlers.DoubtStore") as mock_ds:
            mock_ds.return_value.list_doubts.side_effect = RuntimeError("io error")
            status, body = handlers.handle_get_doubts()
        assert status == 500
        assert body["error"]["code"] == "doubt_read_error"


# ---------------------------------------------------------------------------
# GET /api/timeline
# ---------------------------------------------------------------------------


class TestGetTimeline:
    def test_get_timeline_with_snapshots(self, tmp_path):
        handlers = _make_handlers(tmp_path)
        snapshot = _make_snapshot()
        timeline_result = TimelineResult(
            snapshot_count=1,
            time_range_start="2024-01-01T00:00:00Z",
            time_range_end="2024-01-01T00:00:00Z",
            feature_timelines=[],
            summary=TimelineSummary(active_count=0, removed_count=0, total_drift_events=0),
        )
        with (
            patch("the_door.core.ui.api_handlers.SnapshotStore") as mock_ss,
            patch("the_door.core.ui.api_handlers.TimelineEngine") as mock_te,
        ):
            mock_ss.return_value.list_snapshots.return_value = [snapshot]
            mock_te.return_value.analyze.return_value = timeline_result
            status, body = handlers.handle_get_timeline()
        assert status == 200
        mock_te.return_value.analyze.assert_called_once()

    def test_get_timeline_no_snapshots(self, tmp_path):
        handlers = _make_handlers(tmp_path)
        with (
            patch("the_door.core.ui.api_handlers.SnapshotStore") as mock_ss,
            patch("the_door.core.ui.api_handlers.TimelineEngine") as mock_te,
        ):
            mock_ss.return_value.list_snapshots.return_value = []
            status, body = handlers.handle_get_timeline()
        assert status == 200
        assert body["snapshot_count"] == 0
        assert body["feature_timelines"] == []
        mock_te.return_value.analyze.assert_not_called()

    def test_get_timeline_exception_returns_500(self, tmp_path):
        handlers = _make_handlers(tmp_path)
        with patch("the_door.core.ui.api_handlers.SnapshotStore") as mock_ss:
            mock_ss.return_value.list_snapshots.side_effect = RuntimeError("timeline boom")
            status, body = handlers.handle_get_timeline()
        assert status == 500
        assert body["error"]["code"] == "timeline_error"


# ---------------------------------------------------------------------------
# Task 05.3 — GET /api/status
# ---------------------------------------------------------------------------


def test_api_status_returns_state_and_next_actions(tmp_path):
    """GET /api/status returns 200 with state + next_actions keys (S3-T9)."""
    handlers = _make_handlers(tmp_path)
    status, body = handlers.handle_get_status()
    assert status == 200
    assert "state" in body
    assert "next_actions" in body
    # next_actions is a list of action dicts
    assert isinstance(body["next_actions"], list)
    # state carries the keys the viewer onboarding card consumes
    assert "project_path" in body["state"]
    assert "has_dot_the_door" in body["state"]
