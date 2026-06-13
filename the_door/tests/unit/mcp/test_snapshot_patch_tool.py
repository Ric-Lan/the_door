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

    def test_returns_patched_features_list(self, seeded_project):
        import asyncio
        result = asyncio.run(snapshot_patch_tool.execute({
            "codebase_path": str(seeded_project),
            "version_ref": "v1.0.0",
            "source_nodes_by_feature": {"feat-cli": ["main"]},
        }))
        assert result["patched_features"] == ["feat-cli"]

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
        assert result["patched_features"] == ["feat-cli"]

    def test_with_analyzed_files(self, seeded_project):
        import asyncio
        result = asyncio.run(snapshot_patch_tool.execute({
            "codebase_path": str(seeded_project),
            "version_ref": "v1.0.0",
            "source_nodes_by_feature": {"feat-cli": ["main"]},
            "analyzed_files": ["src/cli/main.py"],
        }))
        assert "error" not in result

    def test_patch_project_summary_returned_in_response(self, seeded_project):
        import asyncio
        result = asyncio.run(snapshot_patch_tool.execute({
            "codebase_path": str(seeded_project),
            "version_ref": "v1.0.0",
            "project_summary": "這個工具提供 CLI 分析。",
        }))
        assert result["project_summary"] == "這個工具提供 CLI 分析。"

    def test_patch_project_summary_none_when_not_provided(self, seeded_project):
        import asyncio
        result = asyncio.run(snapshot_patch_tool.execute({
            "codebase_path": str(seeded_project),
            "version_ref": "v1.0.0",
            "source_nodes_by_feature": {"feat-cli": ["main"]},
        }))
        assert result["project_summary"] is None


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


class TestSnapshotPatchToolSchema:
    def test_source_nodes_by_feature_is_not_required(self):
        required = snapshot_patch_tool.TOOL_SCHEMA.get("required", [])
        assert "source_nodes_by_feature" not in required

    def test_feature_metadata_by_feature_in_schema(self):
        props = snapshot_patch_tool.TOOL_SCHEMA["properties"]
        assert "feature_metadata_by_feature" in props

    def test_feature_metadata_schema_has_additionalProperties(self):
        meta_schema = snapshot_patch_tool.TOOL_SCHEMA["properties"]["feature_metadata_by_feature"]
        assert "additionalProperties" in meta_schema


class TestSnapshotPatchToolExecuteMetadata:
    @pytest.mark.asyncio
    async def test_execute_with_feature_metadata(self, tmp_path):
        from tests._seed_helpers import seed_baseline_snapshot
        from the_door.models import FeatureSummary

        seed_baseline_snapshot(
            tmp_path,
            label="v1.0.0",
            features={
                "feat-a": FeatureSummary(
                    feature_id="feat-a",
                    label="Feature A",
                    description="desc",
                    source_node_count=0,
                    confidence="high",
                    source_nodes=(),
                )
            },
        )

        result = await snapshot_patch_tool.execute({
            "codebase_path": str(tmp_path),
            "version_ref": "v1.0.0",
            "feature_metadata_by_feature": {
                "feat-a": {
                    "trigger_description": "觸發說明",
                    "confidence_reason": "信心理由",
                }
            },
        })

        assert "feat-a" in result["patched_features"]
        assert result["skipped_features"] == []

    @pytest.mark.asyncio
    async def test_execute_patched_features_is_list_of_ids(self, tmp_path):
        from tests._seed_helpers import seed_baseline_snapshot
        from the_door.models import FeatureSummary

        seed_baseline_snapshot(
            tmp_path,
            label="v1.0.0",
            features={
                "feat-a": FeatureSummary(
                    feature_id="feat-a",
                    label="A",
                    description="d",
                    source_node_count=0,
                    confidence="high",
                    source_nodes=(),
                ),
                "feat-b": FeatureSummary(
                    feature_id="feat-b",
                    label="B",
                    description="d",
                    source_node_count=0,
                    confidence="medium",
                    source_nodes=(),
                ),
            },
        )

        result = await snapshot_patch_tool.execute({
            "codebase_path": str(tmp_path),
            "version_ref": "v1.0.0",
            "source_nodes_by_feature": {"feat-a": ["NodeA"]},
            "feature_metadata_by_feature": {"feat-b": {"confidence_reason": "理由"}},
        })

        assert isinstance(result["patched_features"], list)
        assert "feat-a" in result["patched_features"]
        assert "feat-b" in result["patched_features"]
