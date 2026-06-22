import pytest
from the_door.core.structure_view import chunk_merge as cm


def _feat(fid, nodes):
    return {"feature_id": fid, "label": fid, "description": "d",
            "confidence": "high", "source_nodes": list(nodes)}


def test_collect_features_unions_across_chunks():
    chunks = [
        {"chunk_id": "c001", "features": [_feat("feat-c001-a", ["x.py::a"])]},
        {"chunk_id": "c002", "features": [_feat("feat-c002-b", ["y.py::b"])]},
    ]
    feats = cm._collect_features(chunks)
    assert {f["feature_id"] for f in feats} == {"feat-c001-a", "feat-c002-b"}


def test_collect_features_duplicate_id_raises():
    chunks = [
        {"chunk_id": "c001", "features": [_feat("feat-dup", ["x.py::a"])]},
        {"chunk_id": "c002", "features": [_feat("feat-dup", ["y.py::b"])]},
    ]
    with pytest.raises(cm.ChunkMergeError, match="duplicate feature_id"):
        cm._collect_features(chunks)


def test_collect_features_missing_feature_id_raises():
    chunks = [{"chunk_id": "c001", "features": [{"label": "no id"}]}]
    with pytest.raises(cm.ChunkMergeError, match="feature_id"):
        cm._collect_features(chunks)


def test_node_to_feature_maps_each_node():
    feats = [_feat("feat-a", ["x.py::a", "x.py::b"]), _feat("feat-b", ["y.py::c"])]
    mapping, warns = cm._node_to_feature(feats)
    assert mapping == {"x.py::a": "feat-a", "x.py::b": "feat-a", "y.py::c": "feat-b"}
    assert warns == []


def test_node_to_feature_double_claim_lexicographic_first_plus_warning():
    # 同一 node 被兩 feature 認領 → 取字典序首者 (feat-a < feat-z)、記 warning
    feats = [_feat("feat-z", ["x.py::n"]), _feat("feat-a", ["x.py::n"])]
    mapping, warns = cm._node_to_feature(feats)
    assert mapping["x.py::n"] == "feat-a"
    assert warns == ["x.py::n"]


def _view(node_id, out=()):
    return {"node_id": node_id, "name": node_id.split("::")[-1],
            "out_edges": [{"to_node_id": t, "type": ty} for (t, ty) in out],
            "in_edges": []}


def test_derive_relations_crosses_feature_boundary():
    views = {
        "x.py::a": _view("x.py::a", out=[("y.py::c", "calls")]),
        "y.py::c": _view("y.py::c"),
    }
    n2f = {"x.py::a": "feat-a", "y.py::c": "feat-b"}
    rels, skipped = cm._derive_relations(views, n2f)
    assert rels == [{"from_feature": "feat-a", "to_feature": "feat-b",
                     "relation": "calls", "relation_type": "static"}]
    assert skipped == 0


def test_derive_relations_aggregates_duplicate_pairs():
    views = {
        "x.py::a": _view("x.py::a", out=[("y.py::c", "calls")]),
        "x.py::b": _view("x.py::b", out=[("y.py::d", "calls")]),
        "y.py::c": _view("y.py::c"), "y.py::d": _view("y.py::d"),
    }
    n2f = {"x.py::a": "feat-a", "x.py::b": "feat-a", "y.py::c": "feat-b", "y.py::d": "feat-b"}
    rels, _ = cm._derive_relations(views, n2f)
    assert rels == [{"from_feature": "feat-a", "to_feature": "feat-b",
                     "relation": "calls", "relation_type": "static"}]  # 聚合成一條


def test_derive_relations_skips_intrafeature_and_no_feature():
    views = {
        "x.py::a": _view("x.py::a", out=[("x.py::b", "calls"),   # 同 feature → 不產
                                          ("ext::z", "calls")]),  # 端點無 feature → skip+計數
        "x.py::b": _view("x.py::b"),
    }
    n2f = {"x.py::a": "feat-a", "x.py::b": "feat-a"}
    rels, skipped = cm._derive_relations(views, n2f)
    assert rels == []
    assert skipped == 1   # ext::z 那條


def test_derive_relations_keeps_edge_type():
    views = {"x.py::a": _view("x.py::a", out=[("y.py::c", "imports")]), "y.py::c": _view("y.py::c")}
    n2f = {"x.py::a": "feat-a", "y.py::c": "feat-b"}
    rels, _ = cm._derive_relations(views, n2f)
    assert rels[0]["relation"] == "imports"


@pytest.fixture()
def simple(fixtures_dir):
    return fixtures_dir / "sample_codebases" / "python_simple"


def test_merge_real_fixture_derives_cross_feature_calls(simple):
    chunks = [
        {"chunk_id": "c001", "features": [_feat("feat-c001-login", ["app.py::login"])]},
        {"chunk_id": "c002", "features": [
            _feat("feat-c002-auth", ["auth.py::authenticate_user", "auth.py::generate_token"])]},
    ]
    out = cm.merge(simple, chunks)
    assert out["rollup"]["feature_count"] == 2
    # login → authenticate_user 是跨 feature calls → 推出 c001→c002 static relation
    assert {"from_feature": "feat-c001-login", "to_feature": "feat-c002-auth",
            "relation": "calls", "relation_type": "static"} in out["relations"]
    # authenticate_user → generate_token 同 feature(c002) → 不產
    assert all(not (r["from_feature"] == r["to_feature"]) for r in out["relations"])


def test_merge_empty_chunks_raises(simple):
    with pytest.raises(cm.ChunkMergeError, match="must not be empty"):
        cm.merge(simple, [])


def test_merge_missing_structure_view_raises(tmp_path):
    from the_door.core.structure_view.locator import LocateError
    chunks = [{"chunk_id": "c001", "features": [_feat("feat-a", ["x::a"])]}]
    with pytest.raises(LocateError):
        cm.merge(tmp_path, chunks)
