"""Tests for ui_cmd wizard.html entry point."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest


def _setup_viewer(tmp_path):
    viewer_path = tmp_path / "viewer"
    viewer_path.mkdir()
    (viewer_path / "wizard.html").write_text("<html></html>", encoding="utf-8")
    (viewer_path / "index.html").write_text("<html></html>", encoding="utf-8")
    return viewer_path


def test_ui_cmd_opens_wizard_html(tmp_path):
    """ui_cmd should schedule webbrowser.open with a URL containing wizard.html."""
    from the_door.cli.ui_cmd import ui_cmd
    from click.testing import CliRunner

    viewer_path = _setup_viewer(tmp_path)
    mock_server = MagicMock()
    mock_server.url = "http://127.0.0.1:19999"
    mock_server.start.side_effect = KeyboardInterrupt

    with patch("the_door.cli.ui_cmd.UIServer", return_value=mock_server), \
         patch("the_door.cli.ui_cmd._resolve_viewer_dir", return_value=viewer_path), \
         patch("the_door.cli.ui_cmd.ProjectRegistry"), \
         patch("the_door.cli.ui_cmd.threading.Timer") as mock_timer:
        mock_timer.return_value = MagicMock()
        runner = CliRunner()
        runner.invoke(ui_cmd, [str(tmp_path)])

    assert mock_timer.called, "threading.Timer was not called (no browser open scheduled)"
    timer_url_arg = mock_timer.call_args.args[2][0]
    assert "wizard.html" in timer_url_arg, f"Expected wizard.html in URL, got: {timer_url_arg}"


def test_ui_cmd_wizard_url_contains_server_base(tmp_path):
    """The wizard URL must use the server's base URL."""
    from the_door.cli.ui_cmd import ui_cmd
    from click.testing import CliRunner

    viewer_path = _setup_viewer(tmp_path)
    mock_server = MagicMock()
    mock_server.url = "http://127.0.0.1:8765"
    mock_server.start.side_effect = KeyboardInterrupt

    with patch("the_door.cli.ui_cmd.UIServer", return_value=mock_server), \
         patch("the_door.cli.ui_cmd._resolve_viewer_dir", return_value=viewer_path), \
         patch("the_door.cli.ui_cmd.ProjectRegistry"), \
         patch("the_door.cli.ui_cmd.threading.Timer") as mock_timer:
        mock_timer.return_value = MagicMock()
        runner = CliRunner()
        runner.invoke(ui_cmd, [str(tmp_path)])

    timer_url_arg = mock_timer.call_args.args[2][0]
    assert timer_url_arg.startswith("http://127.0.0.1:8765"), \
        f"Expected URL to start with server base, got: {timer_url_arg}"
    assert "wizard.html" in timer_url_arg
