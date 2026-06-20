"""RelationSummary 新增 relation_type / inferred_reason 的往返與相容測試。"""
import tempfile
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import FeatureSummary, RelationSummary


def _store():
    d = Path(tempfile.mkdtemp())
    return SnapshotStore(d), d


def _feat(fid):
    return FeatureSummary(
        feature_id=fid, label=fid, description="d",
        source_node_count=1, confidence="high", source_nodes=("X.m",),
    )


def test_relation_type_fields_default_none():
    r = RelationSummary(from_feature="a", to_feature="b", relation="depends_on")
    assert r.relation_type is None
    assert r.inferred_reason is None


def test_typed_relation_roundtrips_through_store():
    store, _ = _store()
    rels = [RelationSummary("feat-a", "feat-b", "depends_on",
                            relation_type="static"),
            RelationSummary("feat-a", "feat-c", "feeds_into",
                            relation_type="inferred", inferred_reason="概念先後")]
    snap = store.create_snapshot(
        l1_snapshot={"feat-a": _feat("feat-a"), "feat-b": _feat("feat-b"), "feat-c": _feat("feat-c")},
        feature_relations=rels, analyzed_files=[], commit_hash=None,
        git_tags=[], trigger="manual", label="v-typed",
    )
    got = store.get_snapshot(snap.version_id).feature_relations_snapshot
    by = {(r.from_feature, r.to_feature): r for r in got}
    assert by[("feat-a", "feat-b")].relation_type == "static"
    assert by[("feat-a", "feat-b")].inferred_reason is None
    assert by[("feat-a", "feat-c")].relation_type == "inferred"
    assert by[("feat-a", "feat-c")].inferred_reason == "概念先後"


def test_legacy_relation_without_type_still_loads():
    """反序列化舊 JSON（無 relation_type 鍵）→ 兩欄為 None，不報錯。"""
    store, _ = _store()
    snap = store.create_snapshot(
        l1_snapshot={"feat-a": _feat("feat-a"), "feat-b": _feat("feat-b")},
        feature_relations=[RelationSummary("feat-a", "feat-b", "depends_on")],
        analyzed_files=[], commit_hash=None, git_tags=[], trigger="manual", label="v-legacy",
    )
    got = store.get_snapshot(snap.version_id).feature_relations_snapshot[0]
    assert got.relation_type is None and got.inferred_reason is None
