"""Unit tests for `the-door status` CLI command (Task 04.2 / S1)."""
from __future__ import annotations

import json

from click.testing import CliRunner


def test_status_on_empty_dir_suggests_analyze(tmp_path, monkeypatch):
    # Ensure API key is detected so the suggester surfaces the CLI `analyze`
    # first-time rule. Without this, the CLI surface falls back to status/help.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    from the_door.cli.main import main  # adapted from spec's `import cli`

    result = CliRunner().invoke(main, ["status", str(tmp_path)])
    assert result.exit_code == 0, (result.output or "") + (result.stderr or "")
    assert "Next:" in result.stderr
    assert "the-door analyze" in result.stderr


def test_status_json_mode_emits_json(tmp_path, monkeypatch):
    monkeypatch.setenv("THE_DOOR_NEXT_FORMAT", "json")
    from the_door.cli.main import main

    result = CliRunner().invoke(main, ["status", str(tmp_path)])
    assert result.exit_code == 0, result.output + (result.stderr or "")
    payload = json.loads(result.stderr)
    assert "next_actions" in payload
