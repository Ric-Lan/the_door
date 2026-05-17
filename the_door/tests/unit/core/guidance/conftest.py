import json

import pytest


@pytest.fixture
def perf_project_fixture(tmp_path):
    """10 snapshots x ~50KB each + a 1500-node structure.json under .the-door/."""
    dot = tmp_path / ".the-door"
    snap_dir = dot / "snapshots"
    snap_dir.mkdir(parents=True)
    for i in range(10):
        feats = {f"feat-{j}": {
            "feature_id": f"feat-{j}", "label": f"L{j}", "description": "d" * 100,
            "trigger": "t", "trigger_description": "td" * 50,
            "confidence": "high", "confidence_reason": "r" * 50,
            "source_node_count": 3, "source_nodes": ["a", "b", "c"]
        } for j in range(50)}
        snap_data = {
            "version_id": f"vid{i:02d}",
            "label": f"v1.0.{i}",
            "git_tags": [], "commit_hash": None,
            "timestamp": f"2026-01-{i+1:02d}T00:00:00Z",
            "analyzed_files": [], "feature_relations_snapshot": [],
            "l1_snapshot": feats,
        }
        (snap_dir / f"vid{i:02d}.json").write_text(json.dumps(snap_data))
    nodes = [{"id": f"n{i}", "name": f"node_{i}", "type": "function", "file": "x.py", "line": i}
             for i in range(1500)]
    (dot / "structure.json").write_text(json.dumps({"nodes": nodes, "edges": [], "files": []}))
    return tmp_path
