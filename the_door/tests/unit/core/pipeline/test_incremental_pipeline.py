"""Unit tests for the incremental analysis orchestrator (O1).

T1 covers the happy path: a valid baseline plus a persisted structure produces
an :class:`IncrementalDiff` reachable via :class:`IncrementalResult`.

T8 (from the spec error matrix) covers the "no_persisted_structure_for_baseline"
branch: a known baseline whose ``.the-door/structures/<vid>.json.gz`` is missing
must raise :class:`IncrementalAnalysisError` with a backfill remediation.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import (
    ASTNode,
    ExtractionResult,
    FeatureSummary,
    VersionSnapshot,
)


def _seed_project(
    tmp_path: Path,
    *,
    baseline_label: str,
    nodes: list[tuple[str, int]],
    persist_structure: bool = True,
) -> VersionSnapshot:
    """Seed ``tmp_path`` with a baseline snapshot (and optional structure).

    ``nodes`` is a list of ``(node_id, param_count)`` specs. When provided,
    a single feature ``feat-seeded`` owns every node_id. When empty, the
    snapshot's ``l1_snapshot`` is empty (still valid for T8).

    Setting ``persist_structure=False`` skips writing the gzipped structure
    file — this triggers the ``no_persisted_structure_for_baseline`` branch.
    """
    store = SnapshotStore(tmp_path)

    source_nodes = tuple(node_id for node_id, _ in nodes)
    l1_snapshot: dict[str, FeatureSummary] = {}
    if source_nodes:
        l1_snapshot["feat-seeded"] = FeatureSummary(
            feature_id="feat-seeded",
            label="seeded feature",
            description="baseline feature owning the seeded nodes",
            source_node_count=len(source_nodes),
            confidence="high",
            source_nodes=source_nodes,
        )

    snapshot = store.create_snapshot(
        l1_snapshot=l1_snapshot,
        feature_relations=[],
        analyzed_files=[node_id.split("::", 1)[0] for node_id, _ in nodes] or [],
        trigger="manual",
        label=baseline_label,
    )

    if persist_structure:
        struct_dir = tmp_path / ".the-door" / "structures"
        struct_dir.mkdir(parents=True, exist_ok=True)
        struct_path = struct_dir / f"{snapshot.version_id}.json.gz"
        structure_dict = {
            "files": [],
            "nodes": [
                {
                    "node_id": node_id,
                    "type": "function",
                    "name": node_id.split("::", 1)[-1],
                    "file": node_id.split("::", 1)[0],
                    "language": "python",
                    "decorators": [],
                    "parameters": [f"p{i}" for i in range(param_count)],
                    "return_type": None,
                    "docstring": None,
                    "comments": [],
                }
                for node_id, param_count in nodes
            ],
            "edges": [],
            "topology": [],
        }
        with gzip.open(struct_path, "wt", encoding="utf-8") as f:
            json.dump(structure_dict, f)

    return snapshot


def _fake_extraction_for_current(extra_node_id: str) -> ExtractionResult:
    """Build an ExtractionResult that adds one new node to the baseline.

    The returned result is what we monkeypatch ``ASTExtractor.extract`` to
    yield, so the diff layer sees a real structural delta without us needing
    on-disk source files to parse.
    """
    return ExtractionResult(
        files=[],
        nodes=[
            ASTNode(
                node_id="file.py::a",
                type="function",
                name="a",
                file="file.py",
                language="python",
                parameters=["p0"],
            ),
            ASTNode(
                node_id="file.py::b",
                type="function",
                name="b",
                file="file.py",
                language="python",
                parameters=["p0", "p1"],
            ),
            ASTNode(
                node_id=extra_node_id,
                type="function",
                name=extra_node_id.split("::", 1)[-1],
                file=extra_node_id.split("::", 1)[0],
                language="python",
                parameters=[],
            ),
        ],
        edges=[],
    )


def test_run_incremental_pipeline_returns_diff_for_valid_baseline(tmp_path, monkeypatch):
    from the_door.core.extraction import ast_extractor as ast_extractor_mod
    from the_door.core.pipeline.incremental_pipeline import (
        IncrementalResult,
        run_incremental_pipeline,
    )

    baseline = _seed_project(
        tmp_path,
        baseline_label="v1.0.0",
        nodes=[("file.py::a", 1), ("file.py::b", 2)],
    )

    monkeypatch.setattr(
        ast_extractor_mod.ASTExtractor,
        "extract",
        lambda self, codebase_path: _fake_extraction_for_current("file.py::new"),
    )

    result = run_incremental_pipeline(codebase_path=tmp_path, baseline_ref="v1.0.0")

    assert isinstance(result, IncrementalResult)
    assert result.baseline_label == "v1.0.0"
    # Diff is anchored to the seeded baseline
    assert result.diff.baseline_version_id == baseline.version_id
    # Contract surface required by spec
    assert isinstance(result.diff.inherited_features, tuple)
    assert isinstance(result.diff.affected_features, tuple)
    # New node is owned by no baseline feature → unmapped, not affected
    assert "file.py::new" in result.diff.unmapped_nodes.added


def test_missing_persisted_structure_raises_with_backfill_action(tmp_path):
    from the_door.core.pipeline.incremental_pipeline import (
        IncrementalAnalysisError,
        run_incremental_pipeline,
    )

    _seed_project(
        tmp_path,
        baseline_label="v1.0.0",
        nodes=[],
        persist_structure=False,
    )

    with pytest.raises(IncrementalAnalysisError) as exc:
        run_incremental_pipeline(codebase_path=tmp_path, baseline_ref="v1.0.0")

    rem = exc.value.remediation
    assert rem.code == "no_persisted_structure_for_baseline"
    assert rem.next_action is not None
    assert rem.next_action.id == "extract.backfill_structure"
    assert rem.next_action.cli_command is not None
    assert "extract --as-version" in rem.next_action.cli_command


def test_unknown_baseline_raises_baseline_not_found(tmp_path):
    """Sanity check that the baseline_not_found branch is distinct from T8.

    Guards against T8 ever passing for the wrong reason (e.g. baseline missing
    entirely rather than structure missing).
    """
    from the_door.core.pipeline.incremental_pipeline import (
        IncrementalAnalysisError,
        run_incremental_pipeline,
    )

    # No snapshots seeded at all.
    (tmp_path / ".the-door" / "snapshots").mkdir(parents=True, exist_ok=True)

    with pytest.raises(IncrementalAnalysisError) as exc:
        run_incremental_pipeline(codebase_path=tmp_path, baseline_ref="v-does-not-exist")

    rem = exc.value.remediation
    assert rem.code == "baseline_not_found"
    assert rem.next_action is not None
    assert rem.next_action.id == "system_status.show"
