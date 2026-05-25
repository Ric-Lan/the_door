"""Unit tests for SnapshotStore.patch_snapshot()."""
from __future__ import annotations

import dataclasses
import json

import pytest

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import FeatureSummary, SnapshotNotFoundError
from tests._seed_helpers import seed_baseline_snapshot


@pytest.fixture
def store(tmp_path):
    return SnapshotStore(tmp_path)


@pytest.fixture
def seeded(tmp_path):
    """Seed a snapshot with two features; source_nodes intentionally empty."""
    seed_baseline_snapshot(
        tmp_path,
        label="v1.0.0",
        features={
            "feat-a": FeatureSummary(
                feature_id="feat-a",
                label="Feature A",
                description="desc a",
                source_node_count=0,
                confidence="high",
                source_nodes=(),
            ),
            "feat-b": FeatureSummary(
                feature_id="feat-b",
                label="Feature B",
                description="desc b",
                source_node_count=0,
                confidence="medium",
                source_nodes=(),
            ),
        },
    )
    return SnapshotStore(tmp_path)


class TestPatchSnapshotSourceNodes:
    def test_patch_updates_source_nodes(self, seeded):
        snap, skipped = seeded.patch_snapshot(
            version_ref="v1.0.0",
            source_nodes_by_feature={"feat-a": ["ASTExtractor", "ASTExtractor.extract"]},
        )
        assert snap.l1_snapshot["feat-a"].source_nodes == ("ASTExtractor", "ASTExtractor.extract")
        assert snap.l1_snapshot["feat-a"].source_node_count == 2
        assert skipped == []

    def test_patch_preserves_version_id_and_timestamp(self, seeded):
        original = seeded.resolve_baseline("v1.0.0")
        snap, _ = seeded.patch_snapshot(
            version_ref="v1.0.0",
            source_nodes_by_feature={"feat-a": ["NodeA"]},
        )
        assert snap.version_id == original.version_id
        assert snap.timestamp == original.timestamp
        assert snap.label == original.label

    def test_patch_preserves_other_fields_unchanged(self, seeded):
        snap, _ = seeded.patch_snapshot(
            version_ref="v1.0.0",
            source_nodes_by_feature={"feat-a": ["NodeA"]},
        )
        feat_b = snap.l1_snapshot["feat-b"]
        assert feat_b.source_nodes == ()
        assert feat_b.source_node_count == 0
        assert feat_b.label == "Feature B"
        assert feat_b.confidence == "medium"

    def test_patch_skips_unknown_feature_ids(self, seeded):
        snap, skipped = seeded.patch_snapshot(
            version_ref="v1.0.0",
            source_nodes_by_feature={
                "feat-a": ["NodeA"],
                "feat-nonexistent": ["NodeX"],
            },
        )
        assert "feat-nonexistent" in skipped
        assert "feat-a" not in skipped
        assert snap.l1_snapshot["feat-a"].source_nodes == ("NodeA",)

    def test_patch_updates_analyzed_files(self, seeded):
        snap, _ = seeded.patch_snapshot(
            version_ref="v1.0.0",
            source_nodes_by_feature={"feat-a": ["NodeA"]},
            analyzed_files=["src/foo.py", "src/bar.py"],
        )
        assert snap.analyzed_files == ["src/foo.py", "src/bar.py"]

    def test_patch_analyzed_files_none_preserves_original(self, seeded):
        original = seeded.resolve_baseline("v1.0.0")
        snap, _ = seeded.patch_snapshot(
            version_ref="v1.0.0",
            source_nodes_by_feature={"feat-a": ["NodeA"]},
            analyzed_files=None,
        )
        assert snap.analyzed_files == original.analyzed_files

    def test_patch_unknown_version_ref_raises(self, seeded):
        with pytest.raises(SnapshotNotFoundError):
            seeded.patch_snapshot(
                version_ref="v-nonexistent",
                source_nodes_by_feature={"feat-a": ["NodeA"]},
            )

    def test_patch_persisted_to_disk(self, seeded):
        """Reload from disk after patch and verify source_nodes survived serialization."""
        snap, _ = seeded.patch_snapshot(
            version_ref="v1.0.0",
            source_nodes_by_feature={"feat-a": ["ASTExtractor", "ASTExtractor.extract"]},
        )
        reloaded = seeded.get_snapshot(snap.version_id)
        assert reloaded.l1_snapshot["feat-a"].source_nodes == ("ASTExtractor", "ASTExtractor.extract")
        assert reloaded.l1_snapshot["feat-a"].source_node_count == 2

    def test_patch_source_nodes_absent_in_json_when_empty(self, seeded):
        """After patching feat-a but leaving feat-b empty, feat-b should NOT have source_nodes key in JSON."""
        snap, _ = seeded.patch_snapshot(
            version_ref="v1.0.0",
            source_nodes_by_feature={"feat-a": ["NodeA"]},
        )
        snap_file = seeded._snapshots_dir / f"{snap.version_id}.json"
        raw = json.loads(snap_file.read_text(encoding="utf-8"))
        assert "source_nodes" not in raw["l1_snapshot"]["feat-b"]
        assert "source_nodes" in raw["l1_snapshot"]["feat-a"]
