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
