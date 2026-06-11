"""Unit tests for `the-door status` CLI command (Task 04.2 / S1)."""
from __future__ import annotations

import json

from click.testing import CliRunner


def test_status_on_empty_dir_suggests_first_extract(tmp_path, monkeypatch):
    # Zero-key terminal state (T5-A): the first-time rule surfaces the
    # agent-as-LLM extract_structure path (no API key, no `analyze` command).
    from the_door.cli.main import main  # adapted from spec's `import cli`

    result = CliRunner().invoke(main, ["status", str(tmp_path)])
    assert result.exit_code == 0, (result.output or "") + (result.stderr or "")
    assert "Next:" in result.stderr
    assert "extract_structure" in result.stderr


def test_status_json_mode_emits_json(tmp_path, monkeypatch):
    monkeypatch.setenv("THE_DOOR_NEXT_FORMAT", "json")
    from the_door.cli.main import main

    result = CliRunner().invoke(main, ["status", str(tmp_path)])
    assert result.exit_code == 0, result.output + (result.stderr or "")
    payload = json.loads(result.stderr)
    assert "next_actions" in payload


def test_force_utf8_io_is_safe_on_non_reconfigurable_streams():
    """`_force_utf8_io()` must never raise — including when stdout/stderr are not
    a reconfigurable TextIOWrapper (pytest capture, redirected non-text). This
    is a secondary, helper-local guard: the real cp950 regression is gated by
    tests/unit/cli/test_status_cp950_output.py (the wiring into main()).
    Replaces the former test_status_sets_pythonioencoding_utf8, which asserted a
    dead mechanism (os.environ mutation cannot re-encode a live stream)."""
    import io
    import sys
    from the_door.cli.main import _force_utf8_io

    # Idempotent / non-raising on whatever the test harness installed.
    _force_utf8_io()
    _force_utf8_io()

    # Non-reconfigurable streams (plain BytesIO-backed / no reconfigure attr)
    # must be tolerated, not raise.
    orig_out, orig_err = sys.stdout, sys.stderr
    try:
        sys.stdout = io.BytesIO()  # has no .reconfigure
        sys.stderr = io.BytesIO()
        _force_utf8_io()  # must not raise
    finally:
        sys.stdout, sys.stderr = orig_out, orig_err


def test_status_outputs_project_path_to_stdout(tmp_path, monkeypatch):
    """Project path line must appear in stdout (not stderr) for scriptability."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    from the_door.cli.main import main
    result = CliRunner().invoke(main, ["status", str(tmp_path)])
    assert result.exit_code == 0
    assert tmp_path.as_posix() in result.output
