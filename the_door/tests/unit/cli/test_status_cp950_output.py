"""Regression gate for the cp950 CLI crash (handoff_2026_06_11 §4 #1).

`the-door status` emits the symbol `✓` (U+2713), which is NOT in the cp950 /
Big5 code page. On a redirected/piped stdout whose encoding is cp950,
`click.echo` raised `UnicodeEncodeError` and the command crashed — and `status`
is the command CLAUDE.md mandates running first.

This is THE regression gate: it is the only test that exercises the real cp950
stream end to end (click's `CliRunner` captures into its own StringIO and can
never reproduce the crash). It must not be skipped. The fix is a single
UTF-8 reconfigure at the CLI entry funnel (`the_door.cli.main:main`).

Platform-independent: the cp950 codec is bundled in CPython on every OS.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import FeatureSummary

# <worktree>/the_door/src — the edited source we must exercise, not the
# installed wheel that also lives in site-packages.
_SRC = Path(__file__).resolve().parents[3] / "src"


def _make_project_with_snapshot(tmp_path: Path) -> Path:
    """Create a .the-door with one snapshot so `status` reaches the `✓` line
    (status_cmd.py, guarded by `if state.has_dot_the_door`). Mirrors the
    production write call in test_snapshot_store_roundtrip.py."""
    SnapshotStore(tmp_path).create_snapshot(
        l1_snapshot={
            "feat-a": FeatureSummary(
                feature_id="feat-a",
                label="Auth",
                description="...",
                source_node_count=1,
                confidence="high",
            )
        },
        feature_relations=[],
        analyzed_files=[],
        trigger="manual",
        label="v1",
    )
    return tmp_path


def _cp950_env() -> dict:
    return {**os.environ, "PYTHONIOENCODING": "cp950", "PYTHONPATH": str(_SRC)}


def test_subprocess_loads_edited_source() -> None:
    """Provenance guard: prove the subprocess imports `the_door` from <src>,
    not the installed wheel — otherwise the red→green signal below is unreliable
    (it could be exercising old installed code)."""
    probe = subprocess.run(
        [sys.executable, "-c", "import the_door, sys; sys.stdout.write(the_door.__file__)"],
        cwd=str(_SRC),
        env={**os.environ, "PYTHONPATH": str(_SRC)},
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0, probe.stderr
    loaded = Path(probe.stdout.strip()).resolve()
    assert loaded.is_relative_to(_SRC.resolve()), (
        f"subprocess loaded the_door from {loaded}, not {_SRC}"
    )


def test_status_cp950_does_not_crash_and_emits_utf8(tmp_path) -> None:
    target = _make_project_with_snapshot(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "the_door", "status", str(target)],
        cwd=str(_SRC),
        env=_cp950_env(),
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert "✓".encode("utf-8") in result.stdout, (
        "stdout must carry the ✓ as UTF-8 bytes (proves the stream was "
        "reconfigured to utf-8, not crashed on cp950): "
        + result.stdout.decode("utf-8", "replace")
    )
