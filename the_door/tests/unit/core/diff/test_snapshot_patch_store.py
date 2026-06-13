"""Unit tests for patch_snapshot() version_narratives behaviour."""
from __future__ import annotations

import pytest
from the_door.core.diff.snapshot_store import SnapshotStore


@pytest.fixture
def store_with_snapshot(tmp_path):
    store = SnapshotStore(tmp_path)
    store.create_snapshot(
        l1_snapshot={}, feature_relations=[], analyzed_files=[],
        trigger="manual", label="v1.0.0",
    )
    return store, tmp_path


class TestPatchSnapshotVersionNarratives:
    def test_patch_adds_narrative_to_empty(self, store_with_snapshot):
        store, _ = store_with_snapshot
        snap, _ = store.patch_snapshot(
            version_ref="v1.0.0",
            version_narratives={"base-uuid-aaa": "Added login feature."},
        )
        assert snap.version_narratives == {"base-uuid-aaa": "Added login feature."}

    def test_patch_merges_with_existing(self, store_with_snapshot):
        store, _ = store_with_snapshot
        store.patch_snapshot(
            version_ref="v1.0.0",
            version_narratives={"base-uuid-aaa": "Added login."},
        )
        snap, _ = store.patch_snapshot(
            version_ref="v1.0.0",
            version_narratives={"base-uuid-bbb": "Added logout."},
        )
        assert snap.version_narratives == {
            "base-uuid-aaa": "Added login.",
            "base-uuid-bbb": "Added logout.",
        }

    def test_patch_overwrites_same_key(self, store_with_snapshot):
        store, _ = store_with_snapshot
        store.patch_snapshot(
            version_ref="v1.0.0",
            version_narratives={"base-uuid-aaa": "Old narrative."},
        )
        snap, _ = store.patch_snapshot(
            version_ref="v1.0.0",
            version_narratives={"base-uuid-aaa": "New narrative."},
        )
        assert snap.version_narratives["base-uuid-aaa"] == "New narrative."

    def test_patch_without_narratives_leaves_existing_untouched(self, store_with_snapshot):
        store, _ = store_with_snapshot
        store.patch_snapshot(
            version_ref="v1.0.0",
            version_narratives={"base-uuid-aaa": "Keep me."},
        )
        snap, _ = store.patch_snapshot(
            version_ref="v1.0.0",
            source_nodes_by_feature={},  # unrelated patch, no version_narratives
        )
        assert snap.version_narratives == {"base-uuid-aaa": "Keep me."}

    def test_narratives_persisted_to_disk_and_read_back(self, store_with_snapshot):
        store, tmp_path = store_with_snapshot
        store.patch_snapshot(
            version_ref="v1.0.0",
            version_narratives={"base-uuid-aaa": "Persisted narrative."},
        )
        store2 = SnapshotStore(tmp_path)
        snap = store2.resolve_baseline("v1.0.0")
        assert snap.version_narratives == {"base-uuid-aaa": "Persisted narrative."}
