"""Cache-roundtrip tests for PipelineOrchestrator._try_cached_analyze.

Commit ``ba39192`` added ``trigger_description`` and commit ``8933100`` added
``source_nodes`` to the snapshot's FeatureSummary so the viewer's L1 detail
panel and downstream L2/L3 generation can access them without re-running the
LLM. ``_try_cached_analyze`` is the fingerprint-cache fast path that
reconstructs an ``AnalyzeResult`` from a snapshot when no source files have
changed. If that path silently drops those fields, the very next snapshot
write that goes through the pipeline will overwrite the on-disk snapshot
with empty values — undoing the two earlier commits.

These tests pin the contract: cache-rebuilt Features must carry forward the
data the snapshot stored.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.pipeline.pipeline_orchestrator import PipelineOrchestrator
from the_door.models import FeatureSummary, RelationSummary


def _seed_snapshot_and_fingerprint(
    path: Path,
    *,
    l1_snapshot: dict[str, FeatureSummary],
    fingerprint: dict[str, tuple[int, float]],
) -> str:
    """Create a snapshot via the production write path and seed a matching
    fingerprint file on disk. Returns the snapshot's version_id."""
    store = SnapshotStore(path)
    snap = store.create_snapshot(
        l1_snapshot=l1_snapshot,
        feature_relations=[],
        analyzed_files=list(fingerprint.keys()),
        trigger="manual",
        label="cache-roundtrip",
    )

    fp_dir = path / ".the-door" / "fingerprints"
    fp_dir.mkdir(parents=True, exist_ok=True)
    fp_file = fp_dir / f"{snap.version_id}.json"
    serializable = {k: list(v) for k, v in fingerprint.items()}
    fp_file.write_text(
        json.dumps(serializable, ensure_ascii=False),
        encoding="utf-8",
    )
    return snap.version_id


class TestCacheRoundtripPreservesSnapshotFields:
    def test_rebuilt_feature_keeps_source_nodes_from_snapshot(self, tmp_path):
        fs = FeatureSummary(
            feature_id="feat-auth",
            label="Auth flow",
            description="User login + session",
            source_node_count=2,
            confidence="high",
            trigger_description="User submits login form",
            source_nodes=("src/auth.py::login", "src/auth.py::Session"),
        )
        fingerprint = {"src/auth.py": (1024, 1700000000.0)}
        _seed_snapshot_and_fingerprint(
            tmp_path,
            l1_snapshot={"feat-auth": fs},
            fingerprint=fingerprint,
        )

        result = PipelineOrchestrator()._try_cached_analyze(tmp_path, fingerprint)

        assert result is not None
        assert len(result.l1_output.features) == 1
        feat = result.l1_output.features[0]
        assert feat.source_nodes == [
            "src/auth.py::login",
            "src/auth.py::Session",
        ]

    def test_rebuilt_feature_keeps_trigger_description_from_snapshot(self, tmp_path):
        fs = FeatureSummary(
            feature_id="feat-auth",
            label="Auth flow",
            description="User login + session",
            source_node_count=2,
            confidence="high",
            trigger_description="User submits login form",
            source_nodes=("src/auth.py::login",),
        )
        fingerprint = {"src/auth.py": (1024, 1700000000.0)}
        _seed_snapshot_and_fingerprint(
            tmp_path,
            l1_snapshot={"feat-auth": fs},
            fingerprint=fingerprint,
        )

        result = PipelineOrchestrator()._try_cached_analyze(tmp_path, fingerprint)

        assert result is not None
        feat = result.l1_output.features[0]
        assert feat.trigger_description == "User submits login form"

    def test_rebuilt_feature_tolerates_legacy_snapshot_without_optional_fields(
        self, tmp_path
    ):
        # Legacy snapshots written before commits ba39192 / 8933100 deserialize
        # with default empty values. Cache rebuild must not raise.
        fs = FeatureSummary(
            feature_id="feat-legacy",
            label="Legacy",
            description="From before trigger_description was added",
            source_node_count=5,
            confidence="medium",
        )
        fingerprint = {"src/legacy.py": (2048, 1700000000.0)}
        _seed_snapshot_and_fingerprint(
            tmp_path,
            l1_snapshot={"feat-legacy": fs},
            fingerprint=fingerprint,
        )

        result = PipelineOrchestrator()._try_cached_analyze(tmp_path, fingerprint)

        assert result is not None
        feat = result.l1_output.features[0]
        assert feat.source_nodes == []
        assert feat.trigger_description == ""

    def test_fingerprint_mismatch_returns_none(self, tmp_path):
        fs = FeatureSummary(
            feature_id="feat-auth",
            label="Auth",
            description="...",
            source_node_count=1,
            confidence="high",
        )
        stored_fp = {"src/auth.py": (1024, 1700000000.0)}
        _seed_snapshot_and_fingerprint(
            tmp_path,
            l1_snapshot={"feat-auth": fs},
            fingerprint=stored_fp,
        )

        # File grew by one byte → fingerprint must not match.
        current_fp = {"src/auth.py": (1025, 1700000000.0)}
        result = PipelineOrchestrator()._try_cached_analyze(tmp_path, current_fp)

        assert result is None
