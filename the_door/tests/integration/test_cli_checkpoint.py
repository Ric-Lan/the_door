"""Integration tests: CLI commands with FlowGuard CHECKPOINT interaction."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner

from the_door.cli.main import main
from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import FeatureSummary


def _make_feature_summary(fid: str) -> FeatureSummary:
    return FeatureSummary(
        feature_id=fid, label=fid, description="d",
        source_node_count=0, confidence="high",
    )


# T5-A: analyze_cmd + no-api-key CHECKPOINT tests removed — the `analyze` command
# (and the whole API-key concept) was retired; agent-as-LLM is the only path.


# ── status_cmd + project-not-initialized CHECKPOINT ───────────────────────────

def test_status_not_initialized_choice_b_shows_state(tmp_path):
    """status on uninitialized project → CHECKPOINT project-not-initialized → choice B → show state."""
    runner = CliRunner()
    with patch("builtins.input", return_value="B"):
        result = runner.invoke(main, ["status", str(tmp_path)])
    assert "[CHECKPOINT: project-not-initialized]" in result.output


# ── extract --as-version + backfill-complete CHECKPOINT ───────────────────────

def test_extract_as_version_shows_backfill_complete(tmp_path):
    """extract --as-version triggers backfill-complete CHECKPOINT."""
    store = SnapshotStore(tmp_path)
    snap = store.create_snapshot(
        l1_snapshot={"feat-x": _make_feature_summary("feat-x")},
        feature_relations=[], analyzed_files=[], label="v1.0.0",
    )
    runner = CliRunner()
    with patch("builtins.input", return_value="B"):
        result = runner.invoke(
            main,
            ["extract", str(tmp_path), "--as-version", snap.version_id],
        )
    assert "[CHECKPOINT: backfill-complete]" in result.output
    assert "A)" in result.output
    assert "B)" in result.output
