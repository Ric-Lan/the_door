"""Shared helpers for seeding minimal snapshot stores in tests.

Consolidates the boilerplate ``SnapshotStore.create_snapshot(...)`` call that
five+ test files were independently repeating. Each caller still supplies its
own ``l1_snapshot`` shape — only the kwargs-pass-through is centralised.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import FeatureSummary, VersionSnapshot


def seed_baseline_snapshot(
    project_root: Path,
    *,
    label: str,
    features: Mapping[str, FeatureSummary] | None = None,
    analyzed_files: Sequence[str] | None = None,
) -> VersionSnapshot:
    """Persist a baseline snapshot at ``project_root/.the-door/snapshots/``.

    Parameters mirror ``SnapshotStore.create_snapshot`` with sensible defaults
    for the common test shape (empty relations, manual trigger). Pass
    ``features=None`` for an empty L1 (parse-error tests don't need features).
    """
    store = SnapshotStore(project_root)
    return store.create_snapshot(
        l1_snapshot=dict(features or {}),
        feature_relations=[],
        analyzed_files=list(analyzed_files or []),
        trigger="manual",
        label=label,
    )
