"""Round-trip tests for the snapshot store's optional FeatureSummary fields.

``trigger_description`` and ``source_nodes`` were added to FeatureSummary to
support viewer drill-down. These tests pin the on-disk representation
(absent vs present, list serialization) so future refactors don't silently
drop the data again — which is the exact bug that surfaced in the viewer's
L1 detail panel showing an empty 觸發方式 section.
"""
from __future__ import annotations

import json

import pytest

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import (
    FeatureSummary,
    RelationSummary,
    VersionSnapshot,
)


@pytest.fixture
def store(tmp_path):
    return SnapshotStore(tmp_path)


def _write_via_create_snapshot(store, l1_snapshot, **kwargs):
    """Use create_snapshot (the production write path) and return the new
    snapshot's version_id so callers can reload via get_snapshot."""
    snap = store.create_snapshot(
        l1_snapshot=l1_snapshot,
        feature_relations=[],
        analyzed_files=[],
        trigger="manual",
        **kwargs,
    )
    return snap.version_id


class TestFeatureSummaryOnDiskShape:
    def test_minimal_summary_omits_optional_keys(self, store, tmp_path):
        fs = FeatureSummary(
            feature_id="feat-a",
            label="Auth",
            description="...",
            source_node_count=3,
            confidence="high",
        )
        vid = _write_via_create_snapshot(store, {"feat-a": fs}, label="min")

        snap_file = tmp_path / ".the-door" / "snapshots" / f"{vid}.json"
        raw = json.loads(snap_file.read_text(encoding="utf-8"))
        entry = raw["l1_snapshot"]["feat-a"]
        assert "trigger_description" not in entry, \
            "absent trigger_description must be omitted, not serialized as null"
        assert "source_nodes" not in entry, \
            "empty source_nodes must be omitted to keep the on-disk file small"

    def test_populated_summary_round_trips(self, store):
        fs = FeatureSummary(
            feature_id="feat-a",
            label="Auth",
            description="Authentication flow",
            source_node_count=2,
            confidence="high",
            trigger_description="User submits login form",
            source_nodes=("src/auth.py::login", "src/auth.py::Session"),
        )
        vid = _write_via_create_snapshot(store, {"feat-a": fs}, label="full")

        loaded = store.get_snapshot(vid)
        assert loaded is not None
        round_fs = loaded.l1_snapshot["feat-a"]
        assert round_fs.trigger_description == "User submits login form"
        assert round_fs.source_nodes == (
            "src/auth.py::login", "src/auth.py::Session",
        )
        # tuple, not list — preserves frozen-dataclass hashability
        assert isinstance(round_fs.source_nodes, tuple)

    def test_legacy_snapshot_without_new_fields_still_loads(self, tmp_path):
        """A snapshot file produced by an older version of the codebase
        (no trigger_description, no source_nodes keys) must deserialize
        with trigger_description=None and source_nodes=()."""
        snapdir = tmp_path / ".the-door" / "snapshots"
        snapdir.mkdir(parents=True)
        legacy = {
            "version_id": "v-legacy",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "trigger": "manual",
            "commit_hash": None,
            "git_tags": [],
            "label": "legacy",
            "l1_snapshot": {
                "feat-a": {
                    "label": "Auth",
                    "description": "...",
                    "source_node_count": 3,
                    "confidence": "high",
                }
            },
            "l1_5_snapshot": {},
            "feature_relations_snapshot": [],
            "vulnerabilities_snapshot": [],
            "analyzed_files": [],
        }
        (snapdir / "v-legacy.json").write_text(json.dumps(legacy), encoding="utf-8")

        store = SnapshotStore(tmp_path)
        loaded = store.get_snapshot("v-legacy")
        assert loaded is not None
        fs = loaded.l1_snapshot["feat-a"]
        assert fs.trigger_description is None
        assert fs.source_nodes == ()

    def test_create_snapshot_overrides_caller_source_node_count(self, store, tmp_path):
        fs = FeatureSummary(
            feature_id="feat-x",
            label="x",
            description="d",
            confidence="high",
            source_node_count=99,
            source_nodes=("a", "b"),
        )
        snapshot = store.create_snapshot(
            l1_snapshot={"feat-x": fs},
            feature_relations=[],
            analyzed_files=[],
        )
        on_disk = json.loads((tmp_path / ".the-door" / "snapshots" / f"{snapshot.version_id}.json").read_text())
        assert on_disk["l1_snapshot"]["feat-x"]["source_node_count"] == 2


def test_deserialize_legacy_drift_warns_and_normalizes(tmp_path):
    snap_dir = tmp_path / ".the-door" / "snapshots"
    snap_dir.mkdir(parents=True)
    vid = "abc12345-0000-0000-0000-000000000000"
    (snap_dir / f"{vid}.json").write_text(json.dumps({
        "version_id": vid,
        "timestamp": "2026-01-01T00:00:00Z",
        "trigger": "manual",
        "label": None,
        "git_tags": [],
        "commit_hash": None,
        "analyzed_files": [],
        "feature_relations_snapshot": [],
        "l1_snapshot": {
            "feat-x": {
                "feature_id": "feat-x", "label": "x", "description": "d",
                "trigger_description": "td",
                "confidence": "high",
                "source_node_count": 5,
                "source_nodes": [],
            }
        },
    }))
    with pytest.warns(UserWarning, match=r"source_nodes_drift.*feat-x"):
        snap = SnapshotStore(tmp_path).get_snapshot(vid)
    fs = snap.l1_snapshot["feat-x"]
    assert fs.source_node_count == 0
    assert fs.source_nodes == ()


class TestSourceNodesNotInDiff:
    """source_nodes is a viewer-display field, not a diff signal. Adding,
    removing, or reordering nodes must NOT classify the feature as
    attribute_changed — that should only happen for label/description.
    """

    def test_source_nodes_difference_does_not_trigger_attribute_changed(self):
        from the_door.core.diff.diff_engine import DiffEngine

        baseline_fs = FeatureSummary(
            feature_id="feat-a",
            label="Auth",
            description="Login flow",
            source_node_count=2,
            confidence="high",
            source_nodes=("src/a.py::x", "src/a.py::y"),
        )
        current_fs = FeatureSummary(
            feature_id="feat-a",
            label="Auth",
            description="Login flow",  # same!
            source_node_count=3,
            confidence="high",
            source_nodes=("src/a.py::x", "src/a.py::y", "src/a.py::z"),
        )
        baseline = VersionSnapshot(
            version_id="base", timestamp="2026-05-16T00:00:00+00:00",
            trigger="manual", l1_snapshot={"feat-a": baseline_fs},
        )
        current = VersionSnapshot(
            version_id="curr", timestamp="2026-05-16T01:00:00+00:00",
            trigger="manual", l1_snapshot={"feat-a": current_fs},
        )

        engine = DiffEngine()
        result = engine.compute_l1_diff(baseline, current)

        node_diff = next(nd for nd in result.node_diffs if nd.node_id == "feat-a")
        assert node_diff.diff_state == "unchanged", (
            f"source_nodes change leaked into diff state: {node_diff.diff_state}"
        )
