"""Unit tests for snapshot_write MCP tool."""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import FeatureSummary
from tests._seed_helpers import seed_baseline_snapshot


@pytest.fixture
def tmp_project(tmp_path):
    """A temporary project directory with no existing snapshots."""
    return tmp_path


def _load_snapshot_by_vid(project_path: Path, version_id: str):
    """Reload a snapshot from disk by version_id."""
    return SnapshotStore(Path(project_path)).get_snapshot(version_id)


@pytest.fixture
def seeded_v105_fixture(tmp_path):
    """Seed a project with a v1.0.0 baseline snapshot containing 11 features.

    The baseline intentionally does NOT include ``feat-ui-server`` — the
    inheritance test merges in an ``updated_features`` entry for it, yielding
    11 inherited + 1 new = 12 features.
    """
    seed_baseline_snapshot(
        tmp_path,
        label="v1.0.0",
        features={
            f"feat-baseline-{i}": FeatureSummary(
                feature_id=f"feat-baseline-{i}",
                label=f"Baseline feature {i}",
                description=f"baseline feature {i}",
                source_node_count=1,
                confidence="high",
                source_nodes=(f"node-{i}",),
            )
            for i in range(11)
        },
    )
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
    async def test_project_summary_persisted_when_provided(self, tmp_project):
        """Direct-mode project_summary 落盤並 round-trip。"""
        from the_door.mcp.tools.snapshot_write_tool import execute

        result = await execute({
            "codebase_path": str(tmp_project),
            "l1_features": VALID_FEATURES,
            "project_summary": "這個專案提供登入與資料存取。",
        })
        loaded = _load_snapshot_by_vid(tmp_project, result["version_id"])
        assert loaded.project_summary == "這個專案提供登入與資料存取。"

    @pytest.mark.asyncio
    async def test_project_summary_defaults_none_when_omitted(self, tmp_project):
        """Direct-mode 未給 project_summary → None（誠實缺席、不警告）。"""
        from the_door.mcp.tools.snapshot_write_tool import execute

        result = await execute({
            "codebase_path": str(tmp_project),
            "l1_features": VALID_FEATURES,
        })
        loaded = _load_snapshot_by_vid(tmp_project, result["version_id"])
        assert loaded.project_summary is None

    @pytest.mark.asyncio
    async def test_source_nodes_persisted_when_provided(self, tmp_project):
        """source_nodes from the caller are persisted on disk so the viewer
        can drill from L1 to L2 without re-inferring node ownership."""
        from the_door.mcp.tools.snapshot_write_tool import execute

        await execute({
            "codebase_path": str(tmp_project),
            "l1_features": VALID_FEATURES,
            "relations": VALID_RELATIONS,
        })
        files = list((tmp_project / ".the-door" / "snapshots").glob("*.json"))
        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["l1_snapshot"]["feat-auth"]["source_nodes"] == [
            "UserAuth.login", "SessionManager.create",
        ]
        assert data["l1_snapshot"]["feat-data"]["source_nodes"] == ["DataStore.read"]

    @pytest.mark.asyncio
    async def test_trigger_description_persisted_when_provided(self, tmp_project):
        """Optional trigger_description survives the round trip."""
        from the_door.mcp.tools.snapshot_write_tool import execute

        await execute({
            "codebase_path": str(tmp_project),
            "l1_features": [{
                "feature_id": "feat-auth",
                "label": "Authentication",
                "description": "...",
                "source_node_count": 1,
                "confidence": "high",
                "trigger_description": "User submits POST /login",
            }],
        })
        files = list((tmp_project / ".the-door" / "snapshots").glob("*.json"))
        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["l1_snapshot"]["feat-auth"]["trigger_description"] == (
            "User submits POST /login"
        )

    @pytest.mark.asyncio
    async def test_missing_optional_fields_omitted_from_disk(self, tmp_project):
        """If the caller didn't pass trigger_description / source_nodes,
        the JSON file should omit those keys (not write null/[])."""
        from the_door.mcp.tools.snapshot_write_tool import execute

        await execute({
            "codebase_path": str(tmp_project),
            "l1_features": [{
                "feature_id": "feat-minimal",
                "label": "Minimal",
                "description": "...",
                "source_node_count": 0,
                "confidence": "low",
            }],
        })
        files = list((tmp_project / ".the-door" / "snapshots").glob("*.json"))
        data = json.loads(files[0].read_text(encoding="utf-8"))
        entry = data["l1_snapshot"]["feat-minimal"]
        assert "trigger_description" not in entry
        assert "source_nodes" not in entry

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

    @pytest.mark.asyncio
    async def test_snapshot_write_succeeds_without_source_node_count(self, tmp_project):
        """source_node_count is optional; it is derived from source_nodes when absent."""
        from the_door.mcp.tools.snapshot_write_tool import execute

        args = {
            "codebase_path": str(tmp_project),
            "l1_features": [{
                "feature_id": "feat-a", "label": "A", "description": "d",
                "trigger": "t", "trigger_description": "td",
                "confidence": "high", "confidence_reason": "r",
                "source_nodes": ["n1", "n2", "n3"],
                # source_node_count intentionally absent
            }],
            "relations": [],
        }
        result = await execute(args)
        assert "error" not in result
        on_disk = json.loads((tmp_project / ".the-door" / "snapshots" / f"{result['version_id']}.json").read_text())
        assert on_disk["l1_snapshot"]["feat-a"]["source_node_count"] == 3

    @pytest.mark.asyncio
    async def test_snapshot_write_with_inherit_from_merges_features(self, seeded_v105_fixture):
        """O1-T6: inherit_from + updated_features merges into a new snapshot."""
        from the_door.mcp.tools import snapshot_write_tool
        args = {
            "codebase_path": str(seeded_v105_fixture),
            "inherit_from": "v1.0.0",
            "updated_features": [{
                "feature_id": "feat-ui-server",
                "label": "Local Version Viewer Server (updated)",
                "description": "now serves v1.0.5",
                "trigger": "user runs ui",
                "trigger_description": "td",
                "confidence": "high",
                "confidence_reason": "r",
                "source_nodes": ["node-a", "node-b"],
            }],
        }
        result = await snapshot_write_tool.execute(args)
        assert "error" not in result
        snapshot = _load_snapshot_by_vid(seeded_v105_fixture, result["version_id"])
        assert len(snapshot.l1_snapshot) == 12
        assert snapshot.l1_snapshot["feat-ui-server"].label == "Local Version Viewer Server (updated)"

    @pytest.mark.asyncio
    async def test_snapshot_write_without_inherit_from_unchanged(self, tmp_path):
        """O1-T7: regression — calling snapshot_write the old way still works."""
        from the_door.mcp.tools import snapshot_write_tool
        args = {
            "codebase_path": str(tmp_path),
            "l1_features": [{"feature_id": "feat-a", "label": "A", "description": "d",
                             "trigger": "t", "trigger_description": "td",
                             "confidence": "high", "confidence_reason": "r",
                             "source_nodes": ["n1"]}],
            "relations": [],
        }
        result = await snapshot_write_tool.execute(args)
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_snapshot_write_inherit_from_unknown_returns_error_envelope(self, tmp_project):
        """When inherit_from cannot be resolved, return the baseline_not_found envelope."""
        from the_door.mcp.tools import snapshot_write_tool
        args = {
            "codebase_path": str(tmp_project),
            "inherit_from": "nonexistent-label",
            "updated_features": [],
        }
        result = await snapshot_write_tool.execute(args)
        assert "error" in result
        assert result["error"]["remediation"]["code"] == "baseline_not_found"

    @pytest.mark.asyncio
    async def test_returns_project_summary_in_payload(self, tmp_project):
        from the_door.mcp.tools.snapshot_write_tool import execute

        result = await execute({
            "codebase_path": str(tmp_project),
            "l1_features": VALID_FEATURES,
            "relations": VALID_RELATIONS,
            "label": "v1.0.0-summary-test",
            "project_summary": "這個工具提供 CLI 分析功能。",
        })
        assert result["project_summary"] == "這個工具提供 CLI 分析功能。"

    @pytest.mark.asyncio
    async def test_returns_project_summary_none_when_not_provided(self, tmp_project):
        from the_door.mcp.tools.snapshot_write_tool import execute

        result = await execute({
            "codebase_path": str(tmp_project),
            "l1_features": VALID_FEATURES,
            "relations": VALID_RELATIONS,
            "label": "v1.0.0-no-summary-test",
        })
        assert result["project_summary"] is None


@pytest.mark.asyncio
async def test_confidence_reason_roundtrips(tmp_project):
    """confidence_reason written via snapshot_write must be readable from store."""
    from the_door.mcp.tools.snapshot_write_tool import execute

    result = await execute({
        "codebase_path": str(tmp_project),
        "label": "v-cr-test",
        "l1_features": [
            {
                "feature_id": "feat-auth",
                "label": "Auth",
                "description": "handles auth",
                "confidence": "high",
                "source_nodes": ["AuthModule.login"],
                "confidence_reason": "函式命名清楚且路徑單一",
            }
        ],
    })
    assert "error" not in result
    vid = result["version_id"]
    snap = SnapshotStore(tmp_project).get_snapshot(vid)
    fs = snap.l1_snapshot["feat-auth"]
    assert fs.confidence_reason == "函式命名清楚且路徑單一"


@pytest.mark.asyncio
async def test_empty_source_nodes_returns_warning(tmp_project):
    """When source_nodes is empty, response must include a warnings list."""
    from the_door.mcp.tools.snapshot_write_tool import execute

    result = await execute({
        "codebase_path": str(tmp_project),
        "label": "v-warn-test",
        "l1_features": [
            {
                "feature_id": "feat-x",
                "label": "X",
                "description": "some feature",
                "confidence": "medium",
                "source_nodes": [],
            }
        ],
    })
    assert "error" not in result
    assert "warnings" in result
    assert any("source_nodes" in w for w in result["warnings"])


class TestSnapshotWriteToolVersionNarratives:
    @pytest.mark.asyncio
    async def test_version_narratives_persisted_and_returned(self, tmp_project):
        from the_door.mcp.tools.snapshot_write_tool import execute
        result = await execute({
            "codebase_path": str(tmp_project),
            "l1_features": VALID_FEATURES,
            "version_narratives": {"base-uuid-111": "Added auth feature."},
        })
        assert result["version_narratives"] == {"base-uuid-111": "Added auth feature."}
        loaded = _load_snapshot_by_vid(tmp_project, result["version_id"])
        assert loaded.version_narratives == {"base-uuid-111": "Added auth feature."}

    @pytest.mark.asyncio
    async def test_version_narratives_defaults_empty_when_omitted(self, tmp_project):
        from the_door.mcp.tools.snapshot_write_tool import execute
        result = await execute({
            "codebase_path": str(tmp_project),
            "l1_features": VALID_FEATURES,
        })
        assert result["version_narratives"] == {}
        loaded = _load_snapshot_by_vid(tmp_project, result["version_id"])
        assert loaded.version_narratives == {}
