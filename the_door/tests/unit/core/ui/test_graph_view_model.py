"""Unit tests for graph_view_model.py — Phase UI-3 Interactive Graph.

These tests are written TDD-first: they define the expected behaviour of
build_l1_graph_view_model, build_l1_graph_view_model_from_snapshot,
build_l2_graph_view_model, build_l3_graph_view_model,
build_diff_graph_view_model, sort_diff_nodes_by_risk, and
sort_diff_nodes_by_semantic_diff before the implementation exists.

All tests will fail with ImportError until Task 1.2 is complete.
"""
from __future__ import annotations

import pytest

from the_door.core.ui.graph_view_model import (
    build_diff_graph_view_model,
    build_l1_graph_view_model,
    build_l1_graph_view_model_from_snapshot,
    build_l2_graph_view_model,
    build_l3_graph_view_model,
    sort_diff_nodes_by_risk,
    sort_diff_nodes_by_semantic_diff,
)
from the_door.models import (
    ASTNode,
    Anomaly,
    Edge,
    Feature,
    FeatureRelation,
    L1Output,
    L2Module,
    L2Output,
    ModuleInteraction,
    StructureJSON,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_feature(
    feature_id: str,
    label: str = "Label",
    description: str = "Desc",
    confidence: str = "high",
    trigger_description: str = "Trigger",
) -> Feature:
    return Feature(
        feature_id=feature_id,
        label=label,
        description=description,
        trigger="user_action",
        trigger_description=trigger_description,
        confidence=confidence,
        confidence_reason="reason",
    )


def _make_relation(
    from_feature: str,
    to_feature: str,
    relation: str = "calls",
) -> FeatureRelation:
    return FeatureRelation(
        from_feature=from_feature,
        to_feature=to_feature,
        relation=relation,
        relation_type="static",
    )


def _make_module(
    module_id: str,
    label: str = "Module",
    confidence: str = "medium",
    source_nodes: list[str] | None = None,
) -> L2Module:
    return L2Module(
        module_id=module_id,
        label=label,
        confidence=confidence,
        source_nodes=source_nodes or [],
    )


def _make_interaction(
    from_module: str,
    to_module: str,
    description: str = "interacts",
    relation_type: str = "static",
) -> ModuleInteraction:
    return ModuleInteraction(
        from_module=from_module,
        to_module=to_module,
        description=description,
        relation_type=relation_type,
    )


def _make_ast_node(
    node_id: str,
    name: str = "func",
    node_type: str = "function",
    file: str = "src/a.py",
) -> ASTNode:
    return ASTNode(
        node_id=node_id,
        type=node_type,
        name=name,
        file=file,
        language="python",
    )


# ---------------------------------------------------------------------------
# L1 Graph ViewModel tests
# ---------------------------------------------------------------------------


def test_build_l1_empty_features():
    """Empty features list → zero nodes, zero edges."""
    l1 = L1Output(features=[], feature_relations=[])
    vm = build_l1_graph_view_model(l1)

    assert vm["nodes"] == []
    assert vm["edges"] == []


def test_build_l1_empty_relations():
    """Features present but no relations → nodes present, zero edges."""
    l1 = L1Output(
        features=[_make_feature("feat-a"), _make_feature("feat-b")],
        feature_relations=[],
    )
    vm = build_l1_graph_view_model(l1)

    node_ids = [n["id"] for n in vm["nodes"]]
    assert sorted(node_ids) == ["feat-a", "feat-b"]
    assert vm["edges"] == []


def test_build_l1_dangling_edge_omitted():
    """A FeatureRelation referencing an unknown feature_id is omitted; a warning is recorded."""
    l1 = L1Output(
        features=[_make_feature("feat-a")],
        feature_relations=[
            _make_relation("feat-a", "feat-missing"),
        ],
    )
    vm = build_l1_graph_view_model(l1)

    assert vm["edges"] == []
    assert len(vm["warnings"]) >= 1
    assert any("feat-missing" in w for w in vm["warnings"])


def test_build_l1_all_confidence_levels():
    """Nodes for high, medium, and low confidence features are all present with correct confidence values."""
    l1 = L1Output(
        features=[
            _make_feature("feat-high", confidence="high"),
            _make_feature("feat-medium", confidence="medium"),
            _make_feature("feat-low", confidence="low"),
        ],
        feature_relations=[],
    )
    vm = build_l1_graph_view_model(l1)

    by_id = {n["id"]: n for n in vm["nodes"]}
    assert by_id["feat-high"]["confidence"] == "high"
    assert by_id["feat-medium"]["confidence"] == "medium"
    assert by_id["feat-low"]["confidence"] == "low"


def test_build_l1_trigger_description_present():
    """trigger_description from Feature is preserved in the node."""
    l1 = L1Output(
        features=[
            _make_feature("feat-a", trigger_description="User clicks submit")
        ],
        feature_relations=[],
    )
    vm = build_l1_graph_view_model(l1)

    node = vm["nodes"][0]
    assert node["trigger_description"] == "User clicks submit"


def test_build_l1_from_snapshot_trigger_description_null_for_legacy_summary():
    """Legacy FeatureSummary dicts (without trigger_description) map to null."""
    l1_snapshot = {
        "feat-a": {
            "feature_id": "feat-a",
            "label": "Feature A",
            "description": "Does A",
            "source_node_count": 2,
            "confidence": "high",
        }
    }
    feature_relations_snapshot = [
        {"from_feature": "feat-a", "to_feature": "feat-a", "relation": "self"}
    ]

    vm = build_l1_graph_view_model_from_snapshot(l1_snapshot, feature_relations_snapshot)

    assert len(vm["nodes"]) == 1
    node = vm["nodes"][0]
    assert node["id"] == "feat-a"
    assert node["trigger_description"] is None


def test_build_l1_from_snapshot_forwards_trigger_description_when_present():
    """When the snapshot's FeatureSummary carries trigger_description, it propagates
    to the L1_Graph_ViewModel — used by manually-edited snapshots and any future
    schema that records the field."""
    l1_snapshot = {
        "feat-a": {
            "label": "Feature A",
            "description": "Does A",
            "source_node_count": 2,
            "confidence": "high",
            "trigger_description": "Triggered on /api/foo POST request",
        }
    }
    feature_relations_snapshot = []

    vm = build_l1_graph_view_model_from_snapshot(l1_snapshot, feature_relations_snapshot)

    assert vm["nodes"][0]["trigger_description"] == "Triggered on /api/foo POST request"


def test_build_l1_from_snapshot_dangling_edge_omitted():
    """build_l1_graph_view_model_from_snapshot omits dangling edges and records a warning."""
    l1_snapshot = {
        "feat-a": {
            "feature_id": "feat-a",
            "label": "Feature A",
            "description": "Does A",
            "source_node_count": 2,
            "confidence": "high",
        }
    }
    feature_relations_snapshot = [
        {"from_feature": "feat-a", "to_feature": "feat-missing", "relation": "calls"}
    ]

    vm = build_l1_graph_view_model_from_snapshot(l1_snapshot, feature_relations_snapshot)

    assert vm["edges"] == []
    assert len(vm["warnings"]) >= 1
    assert any("feat-missing" in w for w in vm["warnings"])


# ---------------------------------------------------------------------------
# L2 Graph ViewModel tests
# ---------------------------------------------------------------------------


def test_build_l2_empty_modules():
    """Empty modules list → zero nodes, zero edges, empty anomalies."""
    l2 = L2Output(modules=[], module_interactions=[], anomalies=[])
    vm = build_l2_graph_view_model(l2)

    assert vm["nodes"] == []
    assert vm["edges"] == []
    assert vm["anomalies"] == []


def test_build_l2_anomalies_with_multiple_affected_nodes():
    """Anomaly with multiple affected_node_ids is preserved in the output."""
    anomaly = Anomaly(
        anomaly_type="dead_code",
        affected_node_ids=["node-1", "node-2", "node-3"],
        explanation="Three dead nodes",
        confidence="medium",
    )
    l2 = L2Output(
        modules=[_make_module("mod-a")],
        module_interactions=[],
        anomalies=[anomaly],
    )
    vm = build_l2_graph_view_model(l2)

    assert len(vm["anomalies"]) == 1
    a = vm["anomalies"][0]
    assert a["anomaly_type"] == "dead_code"
    assert a["affected_node_ids"] == ["node-1", "node-2", "node-3"]
    assert a["explanation"] == "Three dead nodes"
    assert a["confidence"] == "medium"


def test_build_l2_dangling_interaction_omitted():
    """A ModuleInteraction referencing an unknown module_id is omitted; a warning is recorded."""
    l2 = L2Output(
        modules=[_make_module("mod-a")],
        module_interactions=[
            _make_interaction("mod-a", "mod-missing"),
        ],
        anomalies=[],
    )
    vm = build_l2_graph_view_model(l2)

    assert vm["edges"] == []
    assert len(vm["warnings"]) >= 1
    assert any("mod-missing" in w for w in vm["warnings"])


# ---------------------------------------------------------------------------
# L3 Graph ViewModel tests
# ---------------------------------------------------------------------------


def test_build_l3_empty_source_nodes():
    """Empty source_node_ids → zero nodes, zero edges."""
    structure = StructureJSON(
        nodes=[_make_ast_node("node-a"), _make_ast_node("node-b")],
        edges=[Edge(from_node="node-a", to_node="node-b", type="calls")],
    )
    vm = build_l3_graph_view_model(structure, source_node_ids=[])

    assert vm["nodes"] == []
    assert vm["edges"] == []


def test_build_l3_non_existent_source_nodes():
    """source_node_ids referencing non-existent AST nodes → zero nodes, zero edges."""
    structure = StructureJSON(
        nodes=[_make_ast_node("node-a")],
        edges=[],
    )
    vm = build_l3_graph_view_model(structure, source_node_ids=["node-x", "node-y"])

    assert vm["nodes"] == []
    assert vm["edges"] == []


def test_build_l3_mixed_node_types():
    """Nodes of different types (function, class, method) are all included when in source_node_ids."""
    structure = StructureJSON(
        nodes=[
            _make_ast_node("node-func", name="my_func", node_type="function"),
            _make_ast_node("node-class", name="MyClass", node_type="class"),
            _make_ast_node("node-method", name="my_method", node_type="method"),
        ],
        edges=[],
    )
    vm = build_l3_graph_view_model(
        structure,
        source_node_ids=["node-func", "node-class", "node-method"],
    )

    by_id = {n["id"]: n for n in vm["nodes"]}
    assert by_id["node-func"]["type"] == "function"
    assert by_id["node-class"]["type"] == "class"
    assert by_id["node-method"]["type"] == "method"
    assert len(vm["nodes"]) == 3


def test_build_l3_edges_filtered_to_source_nodes():
    """Only edges where both from_node and to_node are in source_node_ids are included."""
    structure = StructureJSON(
        nodes=[
            _make_ast_node("node-a"),
            _make_ast_node("node-b"),
            _make_ast_node("node-c"),
        ],
        edges=[
            Edge(from_node="node-a", to_node="node-b", type="calls"),
            Edge(from_node="node-a", to_node="node-c", type="calls"),  # node-c excluded
            Edge(from_node="node-c", to_node="node-b", type="calls"),  # node-c excluded
        ],
    )
    vm = build_l3_graph_view_model(
        structure,
        source_node_ids=["node-a", "node-b"],
    )

    assert len(vm["nodes"]) == 2
    assert len(vm["edges"]) == 1
    edge = vm["edges"][0]
    assert edge["source"] == "node-a"
    assert edge["target"] == "node-b"


# ---------------------------------------------------------------------------
# Diff Graph ViewModel tests
# ---------------------------------------------------------------------------


def _make_l1_change(
    feature_id: str,
    change_type: str,
    current_label: str = "Current",
    baseline_label: str | None = "Baseline",
    current_description: str = "Current desc",
    baseline_description: str | None = "Baseline desc",
    risk_flags: list[str] | None = None,
) -> dict:
    return {
        "feature_id": feature_id,
        "change_type": change_type,
        "current_label": current_label,
        "baseline_label": baseline_label,
        "current_description": current_description,
        "baseline_description": baseline_description,
        "risk_flags": risk_flags or [],
    }


def test_build_diff_all_change_types():
    """All four change_type values produce nodes with correct change_type field."""
    update_report = {
        "l1_changes": [
            _make_l1_change("feat-added", "added", baseline_label=None, baseline_description=None),
            _make_l1_change("feat-removed", "removed", current_label="", current_description=""),
            _make_l1_change("feat-attr", "attribute_changed"),
            _make_l1_change("feat-dep", "dependency_changed"),
        ]
    }
    vm = build_diff_graph_view_model(update_report, diff_result=None)

    by_id = {n["id"]: n for n in vm["nodes"]}
    assert by_id["feat-added"]["change_type"] == "added"
    assert by_id["feat-removed"]["change_type"] == "removed"
    assert by_id["feat-attr"]["change_type"] == "attribute_changed"
    assert by_id["feat-dep"]["change_type"] == "dependency_changed"


def test_build_diff_empty_l1_changes():
    """Empty l1_changes → zero nodes, zero edges."""
    update_report = {"l1_changes": []}
    vm = build_diff_graph_view_model(update_report, diff_result=None)

    assert vm["nodes"] == []
    assert vm["edges"] == []


def test_build_diff_edges_between_different_change_types():
    """Edges between nodes of different change_types are included when both nodes are in the changed set."""
    update_report = {
        "l1_changes": [
            _make_l1_change("feat-added", "added"),
            _make_l1_change("feat-removed", "removed"),
        ]
    }
    diff_result = {
        "edge_diffs": [
            {"from_node": "feat-added", "to_node": "feat-removed", "diff_state": "added"},
        ]
    }
    vm = build_diff_graph_view_model(update_report, diff_result=diff_result)

    assert len(vm["edges"]) == 1
    edge = vm["edges"][0]
    assert edge["source"] == "feat-added"
    assert edge["target"] == "feat-removed"


def test_build_diff_no_diff_result_no_edges():
    """When diff_result is None, the ViewModel contains nodes but no edges."""
    update_report = {
        "l1_changes": [
            _make_l1_change("feat-a", "added"),
            _make_l1_change("feat-b", "removed"),
        ]
    }
    vm = build_diff_graph_view_model(update_report, diff_result=None)

    assert len(vm["nodes"]) == 2
    assert vm["edges"] == []


# ---------------------------------------------------------------------------
# sort_diff_nodes_by_risk tests
# ---------------------------------------------------------------------------


def _make_diff_node(
    node_id: str,
    change_type: str,
    risk_flags: list[str] | None = None,
    current_label: str = "Label",
    baseline_label: str | None = "Old",
    current_description: str = "Desc",
    baseline_description: str | None = "Old desc",
) -> dict:
    return {
        "id": node_id,
        "label": current_label or baseline_label or "",
        "change_type": change_type,
        "current_label": current_label,
        "baseline_label": baseline_label,
        "current_description": current_description,
        "baseline_description": baseline_description,
        "risk_flags": risk_flags or [],
    }


def test_sort_risk_first_order():
    """Risk-first sort: out_of_scope → vulnerability → semantic_drift → added → attribute_changed → dependency_changed → removed."""
    nodes = [
        _make_diff_node("n-removed", "removed"),
        _make_diff_node("n-dep", "dependency_changed"),
        _make_diff_node("n-attr", "attribute_changed"),
        _make_diff_node("n-added", "added"),
        _make_diff_node("n-semantic", "added", risk_flags=["semantic_drift"]),
        _make_diff_node("n-vuln", "removed", risk_flags=["vulnerability"]),
        _make_diff_node("n-oos", "attribute_changed", risk_flags=["out_of_scope"]),
    ]

    sorted_nodes = sort_diff_nodes_by_risk(nodes)
    ids = [n["id"] for n in sorted_nodes]

    # out_of_scope first
    assert ids[0] == "n-oos"
    # vulnerability second
    assert ids[1] == "n-vuln"
    # semantic_drift third
    assert ids[2] == "n-semantic"
    # then by change_type: added → attribute_changed → dependency_changed → removed
    assert ids[3] == "n-added"
    assert ids[4] == "n-attr"
    assert ids[5] == "n-dep"
    assert ids[6] == "n-removed"


# ---------------------------------------------------------------------------
# sort_diff_nodes_by_semantic_diff tests
# ---------------------------------------------------------------------------


def test_sort_semantic_diff_three_nodes_varying_magnitude():
    """Nodes with larger combined edit distance rank higher (descending order)."""
    # node-big: large label + description change
    # node-medium: medium change
    # node-small: tiny change
    nodes = [
        _make_diff_node(
            "node-small",
            "attribute_changed",
            current_label="Hello",
            baseline_label="Hello",
            current_description="World",
            baseline_description="World!",
        ),
        _make_diff_node(
            "node-big",
            "attribute_changed",
            current_label="Completely Different Title",
            baseline_label="Original",
            current_description="A very long new description that differs greatly",
            baseline_description="Short old desc",
        ),
        _make_diff_node(
            "node-medium",
            "attribute_changed",
            current_label="New Label",
            baseline_label="Old Label",
            current_description="New description here",
            baseline_description="Old description here",
        ),
    ]

    sorted_nodes = sort_diff_nodes_by_semantic_diff(nodes)
    ids = [n["id"] for n in sorted_nodes]

    # node-big has the largest edit distance, should be first
    assert ids[0] == "node-big"
    # node-small has the smallest edit distance, should be last
    assert ids[-1] == "node-small"


def test_sort_semantic_diff_null_fields_treated_as_empty():
    """None values in current_label, baseline_label, current_description, baseline_description
    are treated as empty strings when computing edit distance."""
    nodes = [
        _make_diff_node(
            "node-null",
            "added",
            current_label="New Feature",
            baseline_label=None,
            current_description="New description",
            baseline_description=None,
        ),
        _make_diff_node(
            "node-empty",
            "added",
            current_label="New Feature",
            baseline_label="",
            current_description="New description",
            baseline_description="",
        ),
    ]

    # Both nodes should have the same edit distance (None == "")
    # The sort should not raise an exception and should return a list of the same length
    sorted_nodes = sort_diff_nodes_by_semantic_diff(nodes)

    assert len(sorted_nodes) == 2
    # Both have the same magnitude, so order may vary — but no exception should be raised
    ids = {n["id"] for n in sorted_nodes}
    assert ids == {"node-null", "node-empty"}
