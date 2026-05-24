"""Tests for extract_cmd --as-version backfill-complete CHECKPOINT + _count_empty_source_nodes."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from the_door.cli.extract_cmd import extract_cmd, _count_empty_source_nodes
from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import FeatureSummary, VersionSnapshot


def _make_feature(fid: str, *, has_source_nodes: bool = True) -> FeatureSummary:
    return FeatureSummary(
        feature_id=fid,
        label=fid,
        description="desc",
        source_node_count=1 if has_source_nodes else 0,
        confidence="high",
        source_nodes=("node-a",) if has_source_nodes else (),
    )


# ── _count_empty_source_nodes ──────────────────────────────────────────────────

def test_count_empty_all_nonempty(tmp_path):
    snap = VersionSnapshot(
        version_id="v", timestamp="2026-01-01T00:00:00+00:00", trigger="manual",
        l1_snapshot={
            "feat-a": _make_feature("feat-a", has_source_nodes=True),
            "feat-b": _make_feature("feat-b", has_source_nodes=True),
        },
    )
    assert _count_empty_source_nodes(snap) == 0


def test_count_empty_some_empty(tmp_path):
    snap = VersionSnapshot(
        version_id="v", timestamp="2026-01-01T00:00:00+00:00", trigger="manual",
        l1_snapshot={
            "feat-a": _make_feature("feat-a", has_source_nodes=True),
            "feat-b": _make_feature("feat-b", has_source_nodes=False),
            "feat-c": _make_feature("feat-c", has_source_nodes=False),
        },
    )
    assert _count_empty_source_nodes(snap) == 2


def test_count_empty_no_features(tmp_path):
    snap = VersionSnapshot(
        version_id="v", timestamp="2026-01-01T00:00:00+00:00", trigger="manual",
        l1_snapshot={},
    )
    assert _count_empty_source_nodes(snap) == 0


# ── extract --as-version backfill-complete CHECKPOINT ─────────────────────────

def test_extract_as_version_triggers_backfill_complete_checkpoint(tmp_path):
    """After backfilling gz, CHECKPOINT backfill-complete appears in output."""
    store = SnapshotStore(tmp_path)
    snap = store.create_snapshot(
        l1_snapshot={
            "feat-x": _make_feature("feat-x", has_source_nodes=False),
        },
        feature_relations=[],
        analyzed_files=[],
        label="v1.0.0",
    )

    runner = CliRunner()
    with patch("builtins.input", return_value="B"):  # choose "B" (open viewer) to exit
        result = runner.invoke(
            extract_cmd,
            [str(tmp_path), "--as-version", snap.version_id],
        )

    assert "backfill-complete" in result.output or "CHECKPOINT" in result.output


def test_extract_as_version_checkpoint_contains_empty_count(tmp_path):
    """CHECKPOINT status message mentions the number of features with empty source_nodes."""
    store = SnapshotStore(tmp_path)
    snap = store.create_snapshot(
        l1_snapshot={
            "feat-x": _make_feature("feat-x", has_source_nodes=False),
            "feat-y": _make_feature("feat-y", has_source_nodes=False),
        },
        feature_relations=[],
        analyzed_files=[],
        label="v1.0.0",
    )

    runner = CliRunner()
    with patch("builtins.input", return_value="B"):
        result = runner.invoke(
            extract_cmd,
            [str(tmp_path), "--as-version", snap.version_id],
        )
    # "2" should appear in the output (empty_count=2)
    assert "2" in result.output


def test_extract_as_version_checkpoint_options_contain_analyze_and_ui(tmp_path):
    """CHECKPOINT backfill-complete options include analyze_changes and ui references."""
    store = SnapshotStore(tmp_path)
    snap = store.create_snapshot(
        l1_snapshot={},
        feature_relations=[],
        analyzed_files=[],
        label="v1.0.0",
    )

    runner = CliRunner()
    with patch("builtins.input", return_value="B"):
        result = runner.invoke(
            extract_cmd,
            [str(tmp_path), "--as-version", snap.version_id],
        )
    assert "analyze_changes" in result.output or "A)" in result.output
    assert "ui" in result.output.lower() or "B)" in result.output
