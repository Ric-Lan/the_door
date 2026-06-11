"""Contract: IncrementalDiff shape from Task 03 (analyze_changes MCP tool +
compute_affected_features) matches what Task 05 displays in the viewer.

Producer side: 03-pipeline-mcp.md Task 03.5 — analyze_changes JSON output.
Consumer side: 05-viewer-frontend.md (not yet — viewer doesn't display affected_features
list directly today, but a future task will). Until then this contract pins the
producer-to-MCP-agent shape.
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


def _seed_project(tmp_path: Path, *, baseline_label: str) -> VersionSnapshot:
    """Seed ``tmp_path`` with a baseline snapshot + persisted structure.

    Contract tests are self-contained per spec convention; this duplicates the
    helper from tests/unit/mcp/test_analyze_changes_tool.py intentionally.
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


def _fake_extraction() -> ExtractionResult:
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
                node_id="file.py::new",
                type="function",
                name="new",
                file="file.py",
                language="python",
                parameters=[],
            ),
        ],
        edges=[],
    )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_analyze_changes_response_shape(tmp_path, monkeypatch):
    from the_door.core.extraction import ast_extractor as ast_extractor_mod
    from the_door.mcp.tools import analyze_changes_tool

    _seed_project(tmp_path, baseline_label="v1.0.0")
    monkeypatch.setattr(
        ast_extractor_mod.ASTExtractor,
        "extract",
        lambda self, codebase_path: _fake_extraction(),
    )

    response = await analyze_changes_tool.execute({
        "codebase_path": str(tmp_path),
        "baseline": "v1.0.0",
    })

    # MCP-AGENT CONSUMER — what an LLM agent reading the response needs:
    required_top_level = {
        "baseline_version_id",
        "baseline_label",
        "inherited_features",
        "affected_features",
        "unmapped_nodes",
        "next_actions",
    }
    assert required_top_level <= set(response.keys()) or "error" in response

    # Each affected feature exposes the delta:
    for af in response.get("affected_features", []):
        assert "feature_id" in af
        assert "delta" in af
        assert set(af["delta"].keys()) >= {"added", "removed", "modified"}

    # Cut 1: unmapped_nodes' three buckets are summarized, not bare lists. Each
    # bucket is {operational: [ids], non_operational: {by_category, total}}.
    unmapped = response["unmapped_nodes"]
    for bucket in ("added", "removed", "modified"):
        b = unmapped[bucket]
        assert isinstance(b["operational"], list)
        assert set(b["non_operational"].keys()) == {"by_category", "total"}
        assert isinstance(b["non_operational"]["by_category"], dict)
        assert isinstance(b["non_operational"]["total"], int)
