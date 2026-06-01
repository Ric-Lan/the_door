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
