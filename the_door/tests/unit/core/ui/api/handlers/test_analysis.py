"""Unit tests for AnalysisHandlers."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.handlers.analysis import AnalysisHandlers
from the_door.core.ui.job_store import JobStore


def _ctx(tmp_path: Path) -> APIContext:
    return APIContext(lambda: tmp_path, lambda: JobStore(), lambda p, f: {"status": "ok"})


class TestAnalyze:
    def test_job_already_running_returns_409(self, tmp_path):
        store = JobStore()
        store.try_create_job()  # occupy slot
        ctx = APIContext(lambda: tmp_path, lambda: store, lambda p, f: {})
        h = AnalysisHandlers(ctx)
        status, body = h.analyze(body={})
        assert status == 409
        assert body["error"]["code"] == "job_already_running"

    def test_starts_job_and_returns_202(self, tmp_path):
        h = AnalysisHandlers(_ctx(tmp_path))
        with patch.object(h, "_run_analyze_job"):
            status, body = h.analyze(body={})
        # job was created (202 returned before thread even starts in test)
        assert status == 202
        assert "job_id" in body


class TestUpdate:
    def test_missing_old_path_returns_400(self, tmp_path):
        h = AnalysisHandlers(_ctx(tmp_path))
        status, body = h.update(body={"new_path": str(tmp_path)})
        assert status == 400
        assert body["error"]["code"] == "missing_required_field"

    def test_missing_new_path_returns_400(self, tmp_path):
        h = AnalysisHandlers(_ctx(tmp_path))
        status, body = h.update(body={"old_path": str(tmp_path)})
        assert status == 400

    def test_same_path_returns_400(self, tmp_path):
        h = AnalysisHandlers(_ctx(tmp_path))
        status, body = h.update(body={"old_path": str(tmp_path), "new_path": str(tmp_path)})
        assert status == 400
        assert body["error"]["code"] == "same_path"

    def test_path_outside_root_returns_400(self, tmp_path):
        import tempfile
        with tempfile.TemporaryDirectory() as outside:
            old = tmp_path / "old"
            old.mkdir()
            h = AnalysisHandlers(_ctx(tmp_path))
            status, body = h.update(body={"old_path": outside, "new_path": str(old)})
            assert status == 400

    def test_job_already_running_returns_409(self, tmp_path):
        store = JobStore()
        store.try_create_job()
        ctx = APIContext(lambda: tmp_path, lambda: store, lambda p, f: {})
        old = tmp_path / "old"
        new = tmp_path / "new"
        old.mkdir(); new.mkdir()
        h = AnalysisHandlers(ctx)
        status, body = h.update(body={"old_path": str(old), "new_path": str(new)})
        assert status == 409

    def test_valid_returns_202(self, tmp_path):
        old = tmp_path / "old"; new = tmp_path / "new"
        old.mkdir(); new.mkdir()
        h = AnalysisHandlers(_ctx(tmp_path))
        with patch.object(h, "_run_pipeline_job"):
            status, body = h.update(body={"old_path": str(old), "new_path": str(new)})
        assert status == 202
        assert "job_id" in body


    def test_analyze_body_none_defaults(self, tmp_path):
        h = AnalysisHandlers(_ctx(tmp_path))
        with patch.object(h, "_run_analyze_job"):
            status, body = h.analyze()
        assert status == 202

    def test_update_body_none_returns_400(self, tmp_path):
        h = AnalysisHandlers(_ctx(tmp_path))
        status, body = h.update()
        assert status == 400
        assert body["error"]["code"] == "missing_required_field"

    def test_new_path_invalid_returns_400(self, tmp_path):
        old = tmp_path / "old"
        old.mkdir()
        h = AnalysisHandlers(_ctx(tmp_path))
        status, body = h.update(
            body={"old_path": str(old), "new_path": str(tmp_path / "missing")}
        )
        assert status == 400
        assert body["error"]["code"] == "invalid_path"

    def test_new_path_outside_root_returns_400(self, tmp_path):
        import tempfile
        with tempfile.TemporaryDirectory() as outside:
            old = tmp_path / "old"
            old.mkdir()
            h = AnalysisHandlers(_ctx(tmp_path))
            status, body = h.update(body={"old_path": str(old), "new_path": outside})
            assert status == 400
            assert body["error"]["code"] == "invalid_path"


    def test_old_path_invalid_returns_400(self, tmp_path):
        new = tmp_path / "new"
        new.mkdir()
        h = AnalysisHandlers(_ctx(tmp_path))
        status, body = h.update(
            body={"old_path": str(tmp_path / "missing"), "new_path": str(new)}
        )
        assert status == 400
        assert body["error"]["code"] == "invalid_path"


class TestAnalyzeProgressAdapter:
    def test_adapter_emits_skipped_and_step_messages(self):
        from the_door.core.ui.api.handlers.analysis import _make_analyze_progress_adapter
        job = MagicMock()
        adapter = _make_analyze_progress_adapter(job)
        adapter("Extracting structure from /x")
        adapter("Snapshot saved: abc")
        # other messages are ignored after skipped header is emitted once
        adapter("something else")
        msgs = [c.args[0] for c in job.update_step.call_args_list]
        assert any("步驟 1/6" in m for m in msgs)
        assert any("analyze_new..." in m for m in msgs)
        assert any("步驟 6/6" in m for m in msgs)


class TestRunAnalyzeJob:
    def test_success_completes_job(self, tmp_path):
        store = JobStore()
        job = store.try_create_job()
        ctx = APIContext(lambda: tmp_path, lambda: store, lambda p, f: {})
        h = AnalysisHandlers(ctx)
        with patch("the_door.core.pipeline.analyze_pipeline.run_analyze_pipeline") as mock_run:
            h._run_analyze_job(job, None, None)
        assert mock_run.called
        assert store.get_job(job.job_id).status == "completed"

    def test_failure_marks_job_failed(self, tmp_path):
        store = JobStore()
        job = store.try_create_job()
        ctx = APIContext(lambda: tmp_path, lambda: store, lambda p, f: {})
        h = AnalysisHandlers(ctx)
        with patch("the_door.core.pipeline.analyze_pipeline.run_analyze_pipeline", side_effect=RuntimeError("boom")):
            h._run_analyze_job(job, None, None)
        assert store.get_job(job.job_id).status == "failed"


class TestRunPipelineJob:
    def test_persists_report_and_completes(self, tmp_path):
        store = JobStore()
        job = store.try_create_job()
        ctx = APIContext(lambda: tmp_path, lambda: store, lambda p, f: {})
        h = AnalysisHandlers(ctx)
        with (
            patch("the_door.core.ui.api.handlers.analysis.PipelineOrchestrator") as mock_po,
            patch("the_door.core.ui.api.handlers.analysis.ReportRenderer") as mock_rr,
        ):
            mock_po.return_value.run.return_value = MagicMock()
            mock_rr.return_value.render_json.return_value = {"generated_at": "2026-01-01T00:00:00Z"}
            h._run_pipeline_job(job, tmp_path / "old", tmp_path / "new")
        assert store.get_job(job.job_id).status == "completed"
        reports = list((tmp_path / ".the-door").glob("update-report-*.json"))
        assert len(reports) == 1

    def test_failure_marks_job_failed(self, tmp_path):
        store = JobStore()
        job = store.try_create_job()
        ctx = APIContext(lambda: tmp_path, lambda: store, lambda p, f: {})
        h = AnalysisHandlers(ctx)
        with patch("the_door.core.ui.api.handlers.analysis.PipelineOrchestrator") as mock_po:
            mock_po.return_value.run.side_effect = RuntimeError("boom")
            h._run_pipeline_job(job, tmp_path / "old", tmp_path / "new")
        assert store.get_job(job.job_id).status == "failed"


class TestUpdateStatus:
    def test_unknown_job_id_returns_404(self, tmp_path):
        h = AnalysisHandlers(_ctx(tmp_path))
        status, body = h.update_status(job_id="nonexistent")
        assert status == 404
        assert body["error"]["code"] == "job_not_found"

    def test_known_job_returns_200(self, tmp_path):
        store = JobStore()
        job = store.try_create_job()
        ctx = APIContext(lambda: tmp_path, lambda: store, lambda p, f: {})
        h = AnalysisHandlers(ctx)
        status, body = h.update_status(job_id=job.job_id)
        assert status == 200
        assert body["job_id"] == job.job_id
        assert "status" in body

    def test_failed_job_includes_error_message(self, tmp_path):
        store = JobStore()
        job = store.try_create_job()
        store.fail_job(job.job_id, "something broke")
        ctx = APIContext(lambda: tmp_path, lambda: store, lambda p, f: {})
        h = AnalysisHandlers(ctx)
        status, body = h.update_status(job_id=job.job_id)
        assert status == 200
        assert body["status"] == "failed"
        assert body["error_message"] == "something broke"
