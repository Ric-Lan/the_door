"""Unit tests for snapshot_write MCP tool."""
from __future__ import annotations

import json
import pytest
from pathlib import Path


@pytest.fixture
def tmp_project(tmp_path):
    """A temporary project directory with no existing snapshots."""
    return tmp_path


VALID_FEATURES = [
    {
        "feature_id": "feat-auth",
        "label": "Authentication",
        "description": "Handles user login and session management.",
        "source_node_count": 5,
        "confidence": "high",
        "source_nodes": ["UserAuth.login", "SessionManager.create"],
    },
    {
        "feature_id": "feat-data",
        "label": "Data Access",
        "description": "Reads and writes persistent data.",
        "source_node_count": 3,
        "confidence": "medium",
        "source_nodes": ["DataStore.read"],
    },
]

VALID_RELATIONS = [
    {"from_feature": "feat-auth", "to_feature": "feat-data", "relation": "depends_on"}
]


class TestSnapshotWriteTool:

    @pytest.mark.asyncio
    async def test_creates_snapshot_from_l1_features(self, tmp_project):
        """snapshot_write creates a snapshot file given valid l1_features."""
        from the_door.mcp.tools.snapshot_write_tool import execute

        result = await execute({
            "codebase_path": str(tmp_project),
            "l1_features": VALID_FEATURES,
            "relations": VALID_RELATIONS,
            "label": "v1.0.0-test",
        })

        assert "error" not in result
        assert "version_id" in result
        assert result["label"] == "v1.0.0-test"

        snapshots_dir = tmp_project / ".the-door" / "snapshots"
        assert snapshots_dir.exists()
        files = list(snapshots_dir.glob("*.json"))
        assert len(files) == 1

        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert "feat-auth" in data["l1_snapshot"]
        assert data["l1_snapshot"]["feat-auth"]["label"] == "Authentication"
        assert data["l1_snapshot"]["feat-auth"]["confidence"] == "high"

    @pytest.mark.asyncio
    async def test_relations_stored_correctly(self, tmp_project):
        """Relations are persisted in feature_relations_snapshot."""
        from the_door.mcp.tools.snapshot_write_tool import execute

        result = await execute({
            "codebase_path": str(tmp_project),
            "l1_features": VALID_FEATURES,
            "relations": VALID_RELATIONS,
        })

        snapshots_dir = tmp_project / ".the-door" / "snapshots"
        data = json.loads(list(snapshots_dir.glob("*.json"))[0].read_text(encoding="utf-8"))
        assert len(data["feature_relations_snapshot"]) == 1
        assert data["feature_relations_snapshot"][0]["from_feature"] == "feat-auth"
        assert data["feature_relations_snapshot"][0]["relation"] == "depends_on"

    @pytest.mark.asyncio
    async def test_empty_features_rejected(self, tmp_project):
        """Empty l1_features list returns an error."""
        from the_door.mcp.tools.snapshot_write_tool import execute

        result = await execute({
            "codebase_path": str(tmp_project),
            "l1_features": [],
        })

        assert "error" in result
        assert "empty" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_confidence_rejected(self, tmp_project):
        """Features with invalid confidence value return an error."""
        from the_door.mcp.tools.snapshot_write_tool import execute

        bad_features = [{
            "feature_id": "feat-x",
            "label": "X",
            "description": "...",
            "source_node_count": 1,
            "confidence": "very_high",  # invalid
        }]

        result = await execute({
            "codebase_path": str(tmp_project),
            "l1_features": bad_features,
        })

        assert "error" in result

    @pytest.mark.asyncio
    async def test_duplicate_feature_id_rejected(self, tmp_project):
        """Duplicate feature_id in l1_features returns an error."""
        from the_door.mcp.tools.snapshot_write_tool import execute

        dup_features = [
            {"feature_id": "feat-dup", "label": "A", "description": ".", "source_node_count": 1, "confidence": "high"},
            {"feature_id": "feat-dup", "label": "B", "description": ".", "source_node_count": 1, "confidence": "low"},
        ]

        result = await execute({
            "codebase_path": str(tmp_project),
            "l1_features": dup_features,
        })

        assert "error" in result
        assert "feat-dup" in result["error"]

    @pytest.mark.asyncio
    async def test_git_tags_optional(self, tmp_project):
        """git_tags and commit_hash are optional; absent = empty list and None."""
        from the_door.mcp.tools.snapshot_write_tool import execute

        result = await execute({
            "codebase_path": str(tmp_project),
            "l1_features": VALID_FEATURES,
        })

        assert "error" not in result
        snapshots_dir = tmp_project / ".the-door" / "snapshots"
        data = json.loads(list(snapshots_dir.glob("*.json"))[0].read_text(encoding="utf-8"))
        assert data["git_tags"] == []
        assert data["commit_hash"] is None

    @pytest.mark.asyncio
    async def test_git_tags_stored_when_provided(self, tmp_project):
        """git_tags provided by caller are stored in the snapshot."""
        from the_door.mcp.tools.snapshot_write_tool import execute

        result = await execute({
            "codebase_path": str(tmp_project),
            "l1_features": VALID_FEATURES,
            "git_tags": ["v1.0.0"],
            "commit_hash": "abc1234",
        })

        assert "error" not in result
        snapshots_dir = tmp_project / ".the-door" / "snapshots"
        data = json.loads(list(snapshots_dir.glob("*.json"))[0].read_text(encoding="utf-8"))
        assert data["git_tags"] == ["v1.0.0"]
        assert data["commit_hash"] == "abc1234"

    @pytest.mark.asyncio
    async def test_relation_with_unknown_feature_rejected(self, tmp_project):
        """Relation referencing unknown feature_id returns an error."""
        from the_door.mcp.tools.snapshot_write_tool import execute

        result = await execute({
            "codebase_path": str(tmp_project),
            "l1_features": VALID_FEATURES,
            "relations": [{"from_feature": "feat-nonexistent", "to_feature": "feat-auth", "relation": "depends_on"}],
        })

        assert "error" in result
        assert "feat-nonexistent" in result["error"]

    @pytest.mark.asyncio
    async def test_analyzed_files_stored_when_provided(self, tmp_project):
        """analyzed_files provided by caller are stored in the snapshot."""
        from the_door.mcp.tools.snapshot_write_tool import execute

        result = await execute({
            "codebase_path": str(tmp_project),
            "l1_features": VALID_FEATURES,
            "analyzed_files": ["src/auth.py", "src/data.py"],
        })

        assert "error" not in result
        snapshots_dir = tmp_project / ".the-door" / "snapshots"
        data = json.loads(list(snapshots_dir.glob("*.json"))[0].read_text(encoding="utf-8"))
        assert data["analyzed_files"] == ["src/auth.py", "src/data.py"]
