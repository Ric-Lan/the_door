"""Unit tests for snapshot_patch MCP tool."""
from __future__ import annotations

import pytest
from pathlib import Path

from the_door.mcp.tools import snapshot_patch_tool
from the_door.models import FeatureSummary
from tests._seed_helpers import seed_baseline_snapshot


@pytest.fixture
def seeded_project(tmp_path):
    seed_baseline_snapshot(
        tmp_path,
        label="v1.0.0",
        features={
            "feat-cli": FeatureSummary(
                feature_id="feat-cli",
                label="CLI",
                description="CLI entry",
                source_node_count=0,
                confidence="high",
                source_nodes=(),
            ),
        },
    )
    return tmp_path


class TestSnapshotPatchToolHappyPath:
    def test_returns_version_id_and_label(self, seeded_project):
        import asyncio
        result = asyncio.run(snapshot_patch_tool.execute({
            "codebase_path": str(seeded_project),
            "version_ref": "v1.0.0",
            "source_nodes_by_feature": {"feat-cli": ["main", "analyze_cmd"]},
        }))
        assert result["version_id"]
        assert result["label"] == "v1.0.0"

    def test_returns_patched_features_count(self, seeded_project):
        import asyncio
        result = asyncio.run(snapshot_patch_tool.execute({
            "codebase_path": str(seeded_project),
            "version_ref": "v1.0.0",
            "source_nodes_by_feature": {"feat-cli": ["main"]},
        }))
        assert result["patched_features"] == 1

    def test_returns_skipped_for_unknown_feature(self, seeded_project):
        import asyncio
        result = asyncio.run(snapshot_patch_tool.execute({
            "codebase_path": str(seeded_project),
            "version_ref": "v1.0.0",
            "source_nodes_by_feature": {
                "feat-cli": ["main"],
                "feat-ghost": ["ghost_node"],
            },
        }))
        assert result["skipped_features"] == ["feat-ghost"]
        assert result["patched_features"] == 1

    def test_with_analyzed_files(self, seeded_project):
        import asyncio
        result = asyncio.run(snapshot_patch_tool.execute({
            "codebase_path": str(seeded_project),
            "version_ref": "v1.0.0",
            "source_nodes_by_feature": {"feat-cli": ["main"]},
            "analyzed_files": ["src/cli/main.py"],
        }))
        assert "error" not in result


class TestSnapshotPatchToolErrorPath:
    def test_unknown_version_ref_returns_error_envelope(self, seeded_project):
        import asyncio
        result = asyncio.run(snapshot_patch_tool.execute({
            "codebase_path": str(seeded_project),
            "version_ref": "v-nonexistent",
            "source_nodes_by_feature": {"feat-cli": ["main"]},
        }))
        assert "error" in result
        assert result["error"]["code"] == "snapshot_not_found"
