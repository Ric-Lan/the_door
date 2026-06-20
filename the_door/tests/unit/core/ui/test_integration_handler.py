"""IntegrationHandlers.get_integration：有 gap 的 snapshot → 正確 payload；空狀態誠實。"""
import gzip
import json
import tempfile
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.handlers.integration import IntegrationHandlers
from the_door.models import FeatureSummary, RelationSummary


def _feat(fid, nodes):
    return FeatureSummary(feature_id=fid, label=fid, description="d",
                          source_node_count=len(nodes), confidence="high",
                          source_nodes=tuple(nodes))


def _ctx(root):
    return APIContext(lambda: Path(root), lambda *_a, **_k: None)


def _seed(cp):
    p = Path(cp) / ".the-door" / "structure-view"
    p.mkdir(parents=True, exist_ok=True)
    with gzip.open(p / "structure.full.json.gz", "wt", encoding="utf-8") as fh:
        json.dump({"nodes": [{"node_id": "U.save"}, {"node_id": "DB.q"}],
                   "edges": []}, fh)
    store = SnapshotStore(Path(cp))
    return store.create_snapshot(
        l1_snapshot={"feat-user": _feat("feat-user", ["U.save"]),
                     "feat-db": _feat("feat-db", ["DB.q"])},
        feature_relations=[RelationSummary("feat-user", "feat-db", "depends_on",
                                           relation_type="static")],
        analyzed_files=[], commit_hash=None, git_tags=[], trigger="manual", label="v1")


def test_get_integration_returns_payload():
    cp = tempfile.mkdtemp()
    snap = _seed(cp)
    status, body = IntegrationHandlers(_ctx(cp)).get_integration(version_id=snap.version_id)
    assert status == 200
    assert body["features"]["feat-user"] == "gap"
    assert body["rollup"]["gap"] == 1


def test_get_integration_latest_when_no_version():
    cp = tempfile.mkdtemp()
    _seed(cp)
    status, body = IntegrationHandlers(_ctx(cp)).get_integration()
    assert status == 200
    assert "rollup" in body
