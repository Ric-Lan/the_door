"""Unit tests for compute_affected_features (O1 core)."""
from __future__ import annotations

from the_door.models import (
    ASTNode,
    FeatureSummary,
    StructureJSON,
    VersionSnapshot,
)


def _sample_structure_with_nodes(specs):
    """Build a StructureJSON containing ASTNodes from minimal specs.

    Each spec is a tuple:
        (node_id, param_count) or (node_id, param_count, params_tuple)

    The ``param_count`` arg is kept for spec parity but only ``params_tuple``
    (when given) affects the signature hash. Default params are
    ``("p0", "p1", ...)`` of length ``param_count``.
    """
    nodes: list[ASTNode] = []
    for spec in specs:
        if len(spec) == 2:
            node_id, param_count = spec
            params = [f"p{i}" for i in range(param_count)]
        else:
            node_id, _, params_tuple = spec
            params = list(params_tuple)
        # node_id format: "file.py::name"
        name = node_id.split("::", 1)[-1] if "::" in node_id else node_id
        file_ = node_id.split("::", 1)[0] if "::" in node_id else "anon.py"
        nodes.append(
            ASTNode(
                node_id=node_id,
                type="function",
                name=name,
                file=file_,
                language="python",
                parameters=params,
            )
        )
    return StructureJSON(nodes=nodes)


def _baseline_with_feature(feature_id, *, source_nodes):
    """Build a minimal VersionSnapshot with a single feature."""
    fs = FeatureSummary(
        feature_id=feature_id,
        label=f"label-{feature_id}",
        description=f"desc-{feature_id}",
        source_node_count=len(source_nodes),
        confidence="high",
        trigger_description=f"trigger-{feature_id}",
        source_nodes=tuple(source_nodes),
    )
    return VersionSnapshot(
        version_id=f"ver-{feature_id}",
        timestamp="2026-05-17T00:00:00Z",
        trigger="manual",
        l1_snapshot={feature_id: fs},
    )


def test_identical_structures_no_affected_features():
    from the_door.core.diff.feature_attribution import compute_affected_features

    structure = _sample_structure_with_nodes([("file.py::foo", 1), ("file.py::bar", 5)])
    baseline = _baseline_with_feature(
        "feat-x", source_nodes=("file.py::foo", "file.py::bar")
    )
    result = compute_affected_features(structure, structure, baseline)
    assert result.affected_features == ()
    assert len(result.inherited_features) == 1
    assert result.unmapped_nodes.added == ()
    assert result.unmapped_nodes.removed == ()
    assert result.unmapped_nodes.modified == ()


def test_inherited_union_affected_equals_baseline_exhaustive():
    """C7 invariant: every baseline feature is partitioned into exactly inherited
    OR affected — the partition is exhaustive and disjoint. The C7 gate keys its
    inherited_hashes off `inherited_features`; if some baseline feature were
    omitted from both sets it would have no hash and silently pass the immunity
    check. This pins that hole closed against future refactors of
    compute_affected_features.
    """
    from the_door.core.diff.feature_attribution import compute_affected_features

    # Two features: one whose node changes (affected), one untouched (inherited).
    base_struct = _sample_structure_with_nodes(
        [("a.py::foo", 1), ("b.py::bar", 1)]
    )
    cur_struct = _sample_structure_with_nodes(
        [("a.py::foo", 9), ("b.py::bar", 1)]  # foo's signature changes
    )
    fs_a = FeatureSummary(
        feature_id="feat-a", label="A", description="da",
        source_node_count=1, confidence="high", source_nodes=("a.py::foo",),
    )
    fs_b = FeatureSummary(
        feature_id="feat-b", label="B", description="db",
        source_node_count=1, confidence="high", source_nodes=("b.py::bar",),
    )
    baseline = VersionSnapshot(
        version_id="ver-multi", timestamp="2026-05-17T00:00:00Z",
        trigger="manual", l1_snapshot={"feat-a": fs_a, "feat-b": fs_b},
    )

    diff = compute_affected_features(base_struct, cur_struct, baseline)
    inherited_ids = {fs.feature_id for fs in diff.inherited_features}
    affected_ids = {af.feature_id for af in diff.affected_features}

    baseline_ids = set(baseline.l1_snapshot.keys())
    assert inherited_ids | affected_ids == baseline_ids, "partition not exhaustive"
    assert inherited_ids & affected_ids == set(), "partition not disjoint"
    assert affected_ids == {"feat-a"}
    assert inherited_ids == {"feat-b"}


def test_added_node_in_feature_sources_marks_affected():
    from the_door.core.diff.feature_attribution import compute_affected_features

    base_struct = _sample_structure_with_nodes([("file.py::foo", 1)])
    cur_struct = _sample_structure_with_nodes(
        [("file.py::foo", 1), ("file.py::new", 10)]
    )
    baseline = _baseline_with_feature(
        "feat-x", source_nodes=("file.py::foo", "file.py::new")
    )
    diff = compute_affected_features(base_struct, cur_struct, baseline)
    assert len(diff.affected_features) == 1
    assert diff.affected_features[0].delta.added == ("file.py::new",)


def test_removed_node_marks_affected():
    from the_door.core.diff.feature_attribution import compute_affected_features

    base_struct = _sample_structure_with_nodes(
        [("file.py::foo", 1), ("file.py::gone", 10)]
    )
    cur_struct = _sample_structure_with_nodes([("file.py::foo", 1)])
    baseline = _baseline_with_feature(
        "feat-y", source_nodes=("file.py::foo", "file.py::gone")
    )
    diff = compute_affected_features(base_struct, cur_struct, baseline)
    assert diff.affected_features[0].delta.removed == ("file.py::gone",)


def test_modified_node_signature_marks_affected():
    from the_door.core.diff.feature_attribution import compute_affected_features

    base_struct = _sample_structure_with_nodes([("file.py::foo", 1, ("a",))])
    cur_struct = _sample_structure_with_nodes(
        [("file.py::foo", 1, ("a", "b"))]
    )  # params changed
    baseline = _baseline_with_feature("feat-z", source_nodes=("file.py::foo",))
    diff = compute_affected_features(base_struct, cur_struct, baseline)
    assert diff.affected_features[0].delta.modified == ("file.py::foo",)


def test_unmapped_node_does_not_flag_feature():
    from the_door.core.diff.feature_attribution import compute_affected_features

    base_struct = _sample_structure_with_nodes([])
    cur_struct = _sample_structure_with_nodes([("file.py::orphan", 1)])
    baseline = _baseline_with_feature("feat-w", source_nodes=("file.py::other",))
    diff = compute_affected_features(base_struct, cur_struct, baseline)
    assert diff.affected_features == ()
    assert "file.py::orphan" in diff.unmapped_nodes.added
