"""Unit tests for analyze_changes MCP tool (O1-T8, T11).

Covers happy path (seeded baseline + persisted structure → IncrementalDiff JSON)
and the ``no_persisted_structure_for_baseline`` error-envelope branch.
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
    persist_structure: bool = True,
) -> VersionSnapshot:
    """Seed ``tmp_path`` with a baseline snapshot (and optional persisted structure).

    Mirrors the helper used in tests/unit/core/pipeline/test_incremental_pipeline.py
    but kept local per spec convention (tests self-contained).
    """
    store = SnapshotStore(tmp_path)

    nodes = [("file.py::a", 1), ("file.py::b", 2)]
    source_nodes = tuple(node_id for node_id, _ in nodes)
    l1_snapshot: dict[str, FeatureSummary] = {
        "feat-seeded": FeatureSummary(
            feature_id="feat-seeded",
            label="seeded feature",
            description="baseline feature owning the seeded nodes",
            source_node_count=len(source_nodes),
            confidence="high",
            source_nodes=source_nodes,
        )
    }

    snapshot = store.create_snapshot(
        l1_snapshot=l1_snapshot,
        feature_relations=[],
        analyzed_files=["file.py"],
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


def _fake_extraction(extra_node_id: str) -> ExtractionResult:
    """Build an ExtractionResult that adds one new node to the baseline."""
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


@pytest.fixture
def seeded_v105_fixture(tmp_path, monkeypatch):
    """A tmp_path-based project with baseline ``v1.0.0`` + persisted structure.

    Monkeypatches ASTExtractor.extract to return a synthetic current-state
    extraction so we don't need on-disk source files.
    """
    from the_door.core.extraction import ast_extractor as ast_extractor_mod

    _seed_project(tmp_path, baseline_label="v1.0.0")
    monkeypatch.setattr(
        ast_extractor_mod.ASTExtractor,
        "extract",
        lambda self, codebase_path: _fake_extraction("file.py::new"),
    )
    return tmp_path


@pytest.mark.asyncio
async def test_analyze_changes_returns_incremental_diff(seeded_v105_fixture):
    from the_door.mcp.tools import analyze_changes_tool

    result = await analyze_changes_tool.execute({
        "codebase_path": str(seeded_v105_fixture),
        "baseline": "v1.0.0",
    })

    assert "baseline_version_id" in result
    assert "inherited_features" in result
    assert "affected_features" in result
    assert "unmapped_nodes" in result
    assert "next_actions" in result
    # Spot-check delta shape
    assert "file.py::new" in result["unmapped_nodes"]["added"]


@pytest.mark.asyncio
async def test_analyze_changes_missing_structure_returns_error_envelope(tmp_path):
    _seed_project(tmp_path, baseline_label="v1.0.0", persist_structure=False)

    from the_door.mcp.tools import analyze_changes_tool

    result = await analyze_changes_tool.execute({
        "codebase_path": str(tmp_path),
        "baseline": "v1.0.0",
    })

    assert "error" in result
    assert result["error"]["remediation"]["code"] == "no_persisted_structure_for_baseline"
    assert result["error"]["remediation"]["next_action"]["id"] == "extract.backfill_structure"
