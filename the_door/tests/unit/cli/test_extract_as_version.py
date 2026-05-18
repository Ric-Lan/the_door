"""Unit tests for `the-door extract --as-version` flag (Task 04.6 / O1.3).

The flag backfills `.the-door/structures/<version_id>.json.gz` for an existing
snapshot — no LLM call needed. Useful when a snapshot was created before the
gzipped-structure persistence landed (or was lost on disk).

The fixture seeds a minimal snapshot with label "v1.0.0" pointing at a tiny
extractable Python source tree, then drives the CLI.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner


def _seed_snapshot(project_root: Path, label: str = "v1.0.0") -> str:
    """Persist a minimal VersionSnapshot and return its version_id."""
    from tests._seed_helpers import seed_baseline_snapshot

    return seed_baseline_snapshot(project_root, label=label).version_id


@pytest.fixture
def seeded_v100_baseline(tmp_path: Path):
    """Create a project root with both a seeded v1.0.0 snapshot and an
    extractable .py source file. Returns (project_path, source_path).

    For this command, project_path == source_path: the snapshot lives under
    <source>/.the-door/ and `extract --as-version` writes the gz file there.
    """
    project = tmp_path / "proj"
    project.mkdir()
    # A tiny extractable Python file so ASTExtractor produces non-empty output.
    (project / "hello.py").write_text(
        "def greet(name: str) -> str:\n    return f'hi {name}'\n",
        encoding="utf-8",
    )
    vid = _seed_snapshot(project, label="v1.0.0")
    return project, project, vid


def test_extract_as_version_writes_gzipped_structure(seeded_v100_baseline):
    """Happy path: --as-version v1.0.0 backfills the per-version gz file."""
    from the_door.cli.main import main

    project_path, source_path, vid = seeded_v100_baseline
    result = CliRunner().invoke(
        main, ["extract", "--as-version", "v1.0.0", str(source_path)]
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    gz_path = project_path / ".the-door" / "structures" / f"{vid}.json.gz"
    assert gz_path.is_file(), f"expected {gz_path} to exist; CLI output: {result.output}"


def test_extract_as_version_unknown_baseline_returns_remediation(seeded_v100_baseline):
    """Non-existent ref → baseline_not_found remediation, non-zero exit."""
    from the_door.cli.main import main

    project_path, source_path, _vid = seeded_v100_baseline
    result = CliRunner().invoke(
        main, ["extract", "--as-version", "nonexistent", str(source_path)]
    )
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert (
        "baseline_not_found" in combined
        or "找不到" in combined
        or "Cannot resolve" in combined
    ), combined


def test_extract_as_version_conflicts_with_stdout(seeded_v100_baseline):
    """--as-version + --stdout → conflicting_flags remediation."""
    from the_door.cli.main import main

    project_path, source_path, _vid = seeded_v100_baseline
    result = CliRunner().invoke(
        main,
        [
            "extract",
            "--as-version",
            "v1.0.0",
            "--stdout",
            str(source_path),
        ],
    )
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert (
        "conflicting_flags" in combined
        or "cannot be combined" in combined
        or "互斥" in combined
    ), combined
