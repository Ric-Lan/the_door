"""Tests for the `the-door ui` CLI command."""
from __future__ import annotations

import socket
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from the_door.cli.ui_cmd import _resolve_project_choice

# ---------------------------------------------------------------------------
# Unit tests for _resolve_project_choice (pure function)
# ---------------------------------------------------------------------------

_PROJECTS = [
    {"id": "001", "name": "web-app", "path": "/projects/web-app", "registered_at": ""},
    {"id": "002", "name": "api",     "path": "/projects/api",     "registered_at": ""},
]


def test_resolve_by_first_id():
    assert _resolve_project_choice(_PROJECTS, "001") == "/projects/web-app"


def test_resolve_by_second_id():
    assert _resolve_project_choice(_PROJECTS, "002") == "/projects/api"


def test_resolve_direct_path_fallback():
    assert _resolve_project_choice(_PROJECTS, "/custom/path") == "/custom/path"


def test_resolve_unknown_id_treated_as_path():
    assert _resolve_project_choice(_PROJECTS, "999") == "999"


def test_resolve_empty_projects_returns_choice_as_path():
    assert _resolve_project_choice([], "/some/path") == "/some/path"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_ui_cmd_invalid_path_exits_nonzero(tmp_path):
    from the_door.cli.ui_cmd import ui_cmd
    runner = CliRunner()
    result = runner.invoke(ui_cmd, [str(tmp_path / "nonexistent"), "--no-browser"])
    assert result.exit_code != 0
    # Error message is in Chinese: "錯誤：路徑不存在..."
    assert len(result.output) > 0


def test_ui_cmd_port_in_use_exits_nonzero(tmp_path):
    from the_door.cli.ui_cmd import ui_cmd
    # Occupy a port
    port = _find_free_port()
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    try:
        blocker.bind(("127.0.0.1", port))
        blocker.listen(1)
        runner = CliRunner()
        with patch("the_door.cli.ui_cmd._resolve_viewer_dir") as mock_vd:
            mock_vd.return_value = tmp_path
            result = runner.invoke(ui_cmd, [str(tmp_path), "--port", str(port), "--no-browser"])
        assert result.exit_code != 0
    finally:
        blocker.close()


def test_ui_cmd_no_browser_flag(tmp_path):
    from the_door.cli.ui_cmd import ui_cmd
    runner = CliRunner()
    with (
        patch("the_door.cli.ui_cmd._resolve_viewer_dir") as mock_vd,
        patch("the_door.core.ui.server.UIServer.start") as mock_start,
        patch("webbrowser.open") as mock_browser,
    ):
        mock_vd.return_value = tmp_path
        mock_start.side_effect = KeyboardInterrupt  # stop immediately
        result = runner.invoke(ui_cmd, [str(tmp_path), "--no-browser"])
    mock_browser.assert_not_called()


def test_ui_cmd_prints_url_to_stdout(tmp_path):
    from the_door.cli.ui_cmd import ui_cmd
    runner = CliRunner()
    with (
        patch("the_door.cli.ui_cmd._resolve_viewer_dir") as mock_vd,
        patch("the_door.core.ui.server.UIServer.start") as mock_start,
        patch("webbrowser.open"),
    ):
        mock_vd.return_value = tmp_path
        mock_start.side_effect = KeyboardInterrupt
        result = runner.invoke(ui_cmd, [str(tmp_path), "--no-browser"])
    assert "http://127.0.0.1:" in result.output


def test_ui_cmd_dot_dir_missing_still_starts(tmp_path):
    """Server should start even when .the-door/ doesn't exist."""
    from the_door.cli.ui_cmd import ui_cmd
    assert not (tmp_path / ".the-door").exists()
    runner = CliRunner()
    with (
        patch("the_door.cli.ui_cmd._resolve_viewer_dir") as mock_vd,
        patch("the_door.core.ui.server.UIServer.start") as mock_start,
        patch("webbrowser.open"),
    ):
        mock_vd.return_value = tmp_path
        mock_start.side_effect = KeyboardInterrupt
        result = runner.invoke(ui_cmd, [str(tmp_path), "--no-browser"])
    # Should not exit with error due to missing .the-door/
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Unit tests for _pick_project_interactively — dynamic default logic
# ---------------------------------------------------------------------------


def test_pick_returns_active_project_path_without_prompting(tmp_path, monkeypatch):
    """_pick_project_interactively returns active project path directly, no prompt."""
    proj = tmp_path / "active-proj"
    proj.mkdir()

    fake_reg = MagicMock()
    fake_reg.list_projects.return_value = [
        {"id": "001", "name": "active-proj", "path": str(proj)}
    ]
    fake_reg.find_active_project.return_value = {
        "id": "001", "name": "active-proj", "path": str(proj)
    }
    monkeypatch.setattr("the_door.cli.ui_cmd.ProjectRegistry", lambda: fake_reg)

    from the_door.cli.ui_cmd import _pick_project_interactively
    result = _pick_project_interactively()

    assert result == str(proj)
    fake_reg.find_active_project.assert_called_once()


def test_pick_uses_most_recently_opened_as_default(tmp_path, monkeypatch):
    """When no active project, most recently opened becomes the default choice."""
    proj_a = tmp_path / "old"
    proj_b = tmp_path / "recent"
    proj_a.mkdir()
    proj_b.mkdir()

    fake_reg = MagicMock()
    fake_reg.list_projects.return_value = [
        {"id": "001", "name": "old",    "path": str(proj_a)},
        {"id": "002", "name": "recent", "path": str(proj_b)},
    ]
    fake_reg.find_active_project.return_value = None
    fake_reg.get_most_recently_opened.return_value = {
        "id": "002", "name": "recent", "path": str(proj_b)
    }
    fake_reg.list_groups.return_value = []
    monkeypatch.setattr("the_door.cli.ui_cmd.ProjectRegistry", lambda: fake_reg)
    # patch click.prompt to simulate user pressing Enter (accepting default)
    monkeypatch.setattr("click.prompt", lambda *a, **kw: kw.get("default", ""))

    from the_door.cli.ui_cmd import _pick_project_interactively
    result = _pick_project_interactively()

    assert result == str(proj_b)


def test_pick_returns_none_when_no_projects(monkeypatch):
    """When no projects registered, _pick_project_interactively returns None."""
    fake_reg = MagicMock()
    fake_reg.list_projects.return_value = []
    monkeypatch.setattr("the_door.cli.ui_cmd.ProjectRegistry", lambda: fake_reg)

    from the_door.cli.ui_cmd import _pick_project_interactively
    result = _pick_project_interactively()
    assert result is None
