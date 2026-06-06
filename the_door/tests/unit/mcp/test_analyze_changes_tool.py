"""Unit tests for analyze_changes MCP tool (O1-T8, T11).

Covers happy path (seeded baseline + persisted structure → IncrementalDiff JSON)
and the ``no_persisted_structure_for_baseline`` error-envelope branch.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from the_door.models import (
    ASTNode,
    ExtractionResult,
    FeatureSummary,
    VersionSnapshot,
)
from tests._seed_helpers import seed_baseline_snapshot


def _seed_project(
    tmp_path: Path,
    *,
    baseline_label: str,
    persist_structure: bool = True,
) -> VersionSnapshot:
    """Seed ``tmp_path`` with a baseline snapshot (and optional persisted structure)."""
    nodes = [("file.py::a", 1), ("file.py::b", 2)]
    source_nodes = tuple(node_id for node_id, _ in nodes)
    snapshot = seed_baseline_snapshot(
        tmp_path,
        label=baseline_label,
        features={
            "feat-seeded": FeatureSummary(
                feature_id="feat-seeded",
                label="seeded feature",
                description="baseline feature owning the seeded nodes",
                source_node_count=len(source_nodes),
                confidence="high",
                source_nodes=source_nodes,
            )
        },
        analyzed_files=["file.py"],
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
    # C6：inherited feature confidence 經膜投影（值→signal、無裸 enum）
    inh = result["inherited_features"][0]
    assert inh["confidence"]["value"] == "high"
    assert inh["confidence"]["position"]["kind"] == "signal"


@pytest.mark.asyncio
async def test_analyze_changes_payload_carries_baseline_provenance(seeded_v105_fixture):
    """S7 P5：payload 帶 baseline_provenance 膜（signal、無裸值）。"""
    from the_door.core.diff.provenance_membrane import PROVENANCE_CONTRASTS
    from the_door.mcp.tools import analyze_changes_tool

    result = await analyze_changes_tool.execute({
        "codebase_path": str(seeded_v105_fixture),
        "baseline": "v1.0.0",
    })

    prov = result["baseline_provenance"]
    assert prov["value"] in PROVENANCE_CONTRASTS
    assert prov["position"]["kind"] == "signal"
    # seeded baseline 經 create_snapshot 蓋戳 ⟹ current
    assert prov["value"] == "current"


@pytest.mark.asyncio
async def test_analyze_changes_provenance_orthogonal_to_inherited_affected(seeded_v105_fixture):
    """S7 P6：provenance ⊥ inherited/affected——三者同 payload 並存、互不干涉。"""
    from the_door.mcp.tools import analyze_changes_tool

    result = await analyze_changes_tool.execute({
        "codebase_path": str(seeded_v105_fixture),
        "baseline": "v1.0.0",
    })

    assert "baseline_provenance" in result
    assert "inherited_features" in result
    assert "affected_features" in result


@pytest.mark.asyncio
async def test_analyze_changes_provenance_robust_with_explicit_source_path(seeded_v105_fixture):
    """S7 spec §3.6：baseline_provenance 由 diff.baseline_version_id 穩健取得，

    不依賴條件 `snap`（僅在無 source_path 分支綁定）。顯式 source_path 時仍不炸。
    """
    from the_door.mcp.tools import analyze_changes_tool

    result = await analyze_changes_tool.execute({
        "codebase_path": str(seeded_v105_fixture),
        "baseline": "v1.0.0",
        "source_path": str(seeded_v105_fixture),
    })
    assert "baseline_provenance" in result
    assert result["baseline_provenance"]["position"]["kind"] == "signal"


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
