"""Unit tests for BaselineResolver — pure reference resolution, no file I/O."""
from __future__ import annotations

import pytest

from the_door.core.diff.baseline_resolver import BaselineResolver
from the_door.models import SnapshotNotFoundError, VersionSnapshot


def _snap(version_id, timestamp, *, label=None, git_tags=None, commit_hash=None):
    return VersionSnapshot(
        version_id=version_id, timestamp=timestamp, trigger="manual",
        label=label, git_tags=git_tags or [], commit_hash=commit_hash,
    )


def test_resolve_by_date_returns_most_recent_on_or_before():
    r = BaselineResolver()
    snaps = [
        _snap("a", "2026-05-01T00:00:00+00:00"),
        _snap("b", "2026-05-05T00:00:00+00:00"),
        _snap("c", "2026-05-10T00:00:00+00:00"),
    ]
    assert r.resolve("2026-05-06", snaps).version_id == "b"


def test_resolve_by_git_tag_exact():
    r = BaselineResolver()
    snaps = [_snap("a", "2026-05-01T00:00:00+00:00", git_tags=["v1.0.0"])]
    assert r.resolve("v1.0.0", snaps).version_id == "a"


def test_resolve_by_commit_sha_prefix():
    r = BaselineResolver()
    snaps = [_snap("a", "2026-05-01T00:00:00+00:00", commit_hash="8de9b18abc123")]
    assert r.resolve("8de9b18", snaps).version_id == "a"


def test_resolve_by_label_exact():
    r = BaselineResolver()
    snaps = [_snap("a", "2026-05-01T00:00:00+00:00", label="my-label")]
    assert r.resolve("my-label", snaps).version_id == "a"


def test_resolve_by_version_id_exact():
    r = BaselineResolver()
    snaps = [_snap("uuid-xyz", "2026-05-01T00:00:00+00:00")]
    assert r.resolve("uuid-xyz", snaps).version_id == "uuid-xyz"


def test_tie_break_most_recent_wins_for_label():
    r = BaselineResolver()
    snaps = [
        _snap("old", "2026-05-01T00:00:00+00:00", label="dup"),
        _snap("new", "2026-05-09T00:00:00+00:00", label="dup"),
    ]
    assert r.resolve("dup", snaps).version_id == "new"


def test_label_wins_over_version_id_when_string_collides():
    """version_id grammar is placed AFTER label (behaviour-preserving)."""
    r = BaselineResolver()
    snaps = [
        _snap("collide", "2026-05-01T00:00:00+00:00"),                  # version_id == "collide"
        _snap("other", "2026-05-02T00:00:00+00:00", label="collide"),  # label == "collide"
    ]
    assert r.resolve("collide", snaps).version_id == "other"  # label branch first


def test_no_match_raises_with_available_list():
    r = BaselineResolver()
    snaps = [_snap("a", "2026-05-01T00:00:00+00:00", label="x")]
    with pytest.raises(SnapshotNotFoundError) as exc:
        r.resolve("nope", snaps)
    assert exc.value.reference == "nope"
    assert any(e["version_id"] == "a" for e in exc.value.available)


def test_store_resolve_baseline_accepts_version_id(tmp_path):
    """B expansion: a raw version_id now resolves through the unified resolver
    (proves the 4 previously-UUID-rejecting entry points are fixed)."""
    from the_door.core.diff.snapshot_store import SnapshotStore
    from the_door.models import FeatureSummary
    store = SnapshotStore(tmp_path, store_root=tmp_path)
    snap = store.create_snapshot(
        l1_snapshot={"f": FeatureSummary(
            feature_id="f", label="L", description="D",
            source_node_count=0, confidence="low")},
        feature_relations=[], analyzed_files=[], trigger="commit",
    )
    assert store.resolve_baseline(snap.version_id).version_id == snap.version_id
