"""Task 04.4 — CLI error rendering with F3 envelope.

When a CLI command hits a domain error, it should render an Error: line +
optional Next: suggestion to stderr (via render_remediation), not a bespoke
click.echo message.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from the_door.cli.main import main
from the_door.core.diff.snapshot_store import SnapshotStore


def _seed_snapshot(project_path: Path) -> None:
    """Create a minimal snapshot so resolve_baseline runs (rather than get_latest returning None)."""
    store = SnapshotStore(project_path)
    store.create_snapshot(
        l1_snapshot={},
        feature_relations=[],
        analyzed_files=[],
        trigger="manual",
        label="seed",
    )


def test_cli_error_renders_remediation(tmp_path):
    """diff --baseline <nonexistent> should fail with Error: + remediation Next: line."""
    _seed_snapshot(tmp_path)
    result = CliRunner().invoke(
        main, ["diff", "--baseline", "nonexistent-ref", str(tmp_path)]
    )
    assert result.exit_code != 0, f"expected nonzero exit, got stdout={result.stdout!r} stderr={result.stderr!r}"
    # Stderr carries the F3-style remediation
    stderr = result.stderr
    # Code surfaces either as the catalogue message ("找不到") or via the remediation code
    assert "snapshot_not_found" in stderr or "找不到" in stderr, (
        f"expected snapshot_not_found / 找不到 in stderr, got: {stderr!r}"
    )
    # Suggests a next action (`Try:` line from render_remediation, or a `the-door status` hint)
    assert "Try:" in stderr or "the-door status" in stderr or "Next:" in stderr, (
        f"expected Next/Try guidance in stderr, got: {stderr!r}"
    )


def test_cli_error_envelope_has_error_prefix(tmp_path):
    """Spec: render_remediation writes 'Error: <msg>\\n' to stderr."""
    _seed_snapshot(tmp_path)
    result = CliRunner().invoke(
        main, ["diff", "--baseline", "no-such-ref", str(tmp_path)]
    )
    assert result.exit_code != 0
    assert "Error:" in result.stderr, f"expected 'Error:' prefix in stderr, got: {result.stderr!r}"
