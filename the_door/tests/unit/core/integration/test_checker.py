"""core/integration/checker：per-feature 聚合 + run_integration_check 組裝。"""
import gzip
import json
import tempfile
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.integration import checker
from the_door.models import FeatureSummary, RelationSummary


def test_aggregate_features_precedence():
    rels = [
        {"from_feature": "a", "verdict": "backed"},
        {"from_feature": "a", "verdict": "gap"},       # a 有 gap → gap 優先
        {"from_feature": "b", "verdict": "backed"},
        {"from_feature": "c", "verdict": "undetermined"},
        {"from_feature": "d", "verdict": "conceptual"},  # 只有概念 → none
    ]
    out = checker.aggregate_features(rels)
    assert out == {"a": "gap", "b": "backed", "c": "undetermined", "d": "none"}


def _feat(fid, nodes):
    return FeatureSummary(feature_id=fid, label=fid, description="d",
                          source_node_count=len(nodes), confidence="high",
                          source_nodes=tuple(nodes))


def _write_structure(cp, nodes, edges):
    p = Path(cp) / ".the-door" / "structure-view"
    p.mkdir(parents=True, exist_ok=True)
    data = {"nodes": [{"node_id": n} for n in nodes],
            "edges": [{"from": f, "to": t} for f, t in edges]}
    with gzip.open(p / "structure.full.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(data, fh)


def test_run_integration_check_payload():
    cp = tempfile.mkdtemp()
    _write_structure(cp, ["U.save", "DB.q", "O.create"], [("O.create", "DB.q")])
    store = SnapshotStore(Path(cp))
    snap = store.create_snapshot(
        l1_snapshot={"feat-user": _feat("feat-user", ["U.save"]),
                     "feat-db": _feat("feat-db", ["DB.q"]),
                     "feat-order": _feat("feat-order", ["O.create"])},
        feature_relations=[
            RelationSummary("feat-user", "feat-db", "depends_on", relation_type="static"),
            RelationSummary("feat-order", "feat-db", "depends_on", relation_type="static"),
        ],
        analyzed_files=[], commit_hash=None, git_tags=[], trigger="manual", label="v1",
    )
    out = checker.run_integration_check(snap, cp, max_hops=2)
    assert out["features"]["feat-user"] == "gap"
    assert out["features"]["feat-order"] == "backed"
    assert out["rollup"]["gap"] == 1 and out["rollup"]["backed"] == 1
    assert {r["from_feature"] for r in out["relations"]} == {"feat-user", "feat-order"}


def test_run_integration_check_structure_missing():
    cp = tempfile.mkdtemp()
    store = SnapshotStore(Path(cp))
    snap = store.create_snapshot(l1_snapshot={"feat-a": _feat("feat-a", ["A.m"])},
                                 feature_relations=[], analyzed_files=[], commit_hash=None,
                                 git_tags=[], trigger="manual", label="v1")
    out = checker.run_integration_check(snap, cp, max_hops=2)
    assert out["structure_missing"] is True
    assert out["relations"] == [] and out["rollup"]["gap"] == 0
