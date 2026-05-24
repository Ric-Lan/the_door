"""Unit tests for the-door wizard command."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from pathlib import Path


def _invoke_wizard(tmp_path, inputs=""):
    from the_door.cli.main import main
    return CliRunner().invoke(main, ["wizard", str(tmp_path)], input=inputs)


def test_wizard_is_registered():
    """wizard must be a registered CLI command."""
    from the_door.cli.main import main
    assert "wizard" in main.commands


def test_wizard_shows_discovered_files(tmp_path):
    """wizard must display top-level directory/file summary."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1")
    # skip exclusion (Enter), then abort at Checkpoint 1
    result = _invoke_wizard(tmp_path, inputs="\nB\n")
    assert result.exit_code == 0
    assert "src" in result.output or "app.py" in result.output


def test_wizard_excludes_specified_directory(tmp_path):
    """Directories entered at exclusion prompt must reduce the file count."""
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "lib.py").write_text("x = 1")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("y = 2")
    # First discover: 2 files. After excluding vendor: 1 file.
    result = _invoke_wizard(tmp_path, inputs="vendor\nB\n")
    assert result.exit_code == 0
    # Must report reduced file count after exclusion
    assert "排除後剩餘 1 個檔案" in result.output


def test_wizard_checkpoint1_b_aborts(tmp_path):
    """Choosing B at Checkpoint 1 must exit cleanly."""
    (tmp_path / "app.py").write_text("x = 1")
    result = _invoke_wizard(tmp_path, inputs="\nB\n")
    assert result.exit_code == 0
    assert "中止" in result.output


def test_wizard_no_api_key_prints_mcp_hint(tmp_path, monkeypatch):
    """Without API key, wizard must print MCP instructions instead of running analysis."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    (tmp_path / "app.py").write_text("x = 1")
    with patch("the_door.core.llm.config_manager.ConfigManager.load") as mock_load:
        cfg = MagicMock()
        cfg.api_key = None
        mock_load.return_value = cfg
        # skip exclusion, confirm Checkpoint 1
        result = _invoke_wizard(tmp_path, inputs="\nA\n")
    assert "extract_structure" in result.output or "MCP" in result.output
