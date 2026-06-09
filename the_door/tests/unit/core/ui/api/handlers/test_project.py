"""Unit tests for ProjectHandlers."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.handlers.project import ProjectHandlers


def _ctx(tmp_path: Path, switch_fn=None) -> APIContext:
    if switch_fn is None:
        switch_fn = lambda p, f: {"status": "switched", "path": str(p)}
    return APIContext(lambda: tmp_path, switch_fn)


class TestGetProject:
    def test_no_dot_dir_returns_200_with_false_flags(self, tmp_path):
        h = ProjectHandlers(_ctx(tmp_path))
        status, body = h.get()
        assert status == 200
        assert body["dot_the_door_exists"] is False
        assert body["available_data"]["has_snapshots"] is False

    def test_dot_dir_exists_with_snapshots(self, tmp_path):
        (tmp_path / ".the-door").mkdir()
        h = ProjectHandlers(_ctx(tmp_path))
        with (
            patch("the_door.core.ui.api.handlers.project.SnapshotStore") as mock_ss,
            patch("the_door.core.ui.api.handlers.project.DoubtStore") as mock_ds,
        ):
            mock_ss.return_value.list_snapshots.return_value = [MagicMock()]
            mock_ds.return_value.list_doubts.return_value = []
            status, body = h.get()
        assert status == 200
        assert body["dot_the_door_exists"] is True
        assert body["available_data"]["has_snapshots"] is True


class TestStatus:
    def test_returns_200_with_state_and_next_actions(self, tmp_path):
        h = ProjectHandlers(_ctx(tmp_path))
        status, body = h.status()
        assert status == 200
        assert "state" in body
        assert "next_actions" in body


class TestSetProject:
    def test_missing_path_returns_400(self, tmp_path):
        h = ProjectHandlers(_ctx(tmp_path))
        status, body = h.set_project(body={})
        assert status == 400
        assert body["status"] == "error"

    def test_nonexistent_path_returns_400(self, tmp_path):
        h = ProjectHandlers(_ctx(tmp_path))
        status, body = h.set_project(body={"path": str(tmp_path / "nonexistent")})
        assert status == 400

    def test_valid_path_returns_200_on_switched(self, tmp_path):
        called = []
        def switch(path, force):
            called.append((path, force))
            return {"status": "switched", "path": str(path)}
        h = ProjectHandlers(_ctx(tmp_path, switch_fn=switch))
        status, body = h.set_project(body={"path": str(tmp_path)})
        assert status == 200
        assert body["status"] == "switched"

    def test_conflict_returns_409(self, tmp_path):
        def switch(path, force):
            return {"status": "conflict", "message": "job running"}
        h = ProjectHandlers(_ctx(tmp_path, switch_fn=switch))
        status, body = h.set_project(body={"path": str(tmp_path)})
        assert status == 409

    def test_body_none_returns_400(self, tmp_path):
        h = ProjectHandlers(_ctx(tmp_path))
        status, body = h.set_project()
        assert status == 400
        assert body["status"] == "error"

    def test_invalid_path_value_returns_400(self, tmp_path):
        # A non-string truthy path value makes Path() raise -> 400 "路徑格式無效"
        h = ProjectHandlers(_ctx(tmp_path))
        status, body = h.set_project(body={"path": {"not": "a string"}})
        assert status == 400
        assert body["message"] == "路徑格式無效"

    def test_other_status_returns_400(self, tmp_path):
        def switch(path, force):
            return {"status": "rejected", "message": "nope"}
        h = ProjectHandlers(_ctx(tmp_path, switch_fn=switch))
        status, body = h.set_project(body={"path": str(tmp_path)})
        assert status == 400
        assert body["status"] == "rejected"


class TestGetProjectErrorBranch:
    def test_exception_returns_500(self, tmp_path):
        (tmp_path / ".the-door").mkdir()
        h = ProjectHandlers(_ctx(tmp_path))
        with patch("the_door.core.ui.api.handlers.project.SnapshotStore", side_effect=RuntimeError("x")):
            status, body = h.get()
        assert status == 500
        assert body["error"]["code"] == "project_read_error"
