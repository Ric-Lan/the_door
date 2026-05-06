"""Property-based tests for graph_view_model.py — Phase UI-3 Interactive Graph.

Uses Hypothesis with ASCII-only strategies (min_codepoint=32, max_codepoint=126)
for cross-platform compatibility.

**Validates: Requirements 2.4, 2.5, 5.5, 5.6, 9.3, 9.5, 10.4, 10.5, 12.1, 12.2, 12.3, 12.4, 12.5**
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.strategies import composite

from the_door.core.ui.graph_view_model import (
    build_diff_graph_view_model,
    build_l1_graph_view_model,
    build_l2_graph_view_model,
    sort_diff_nodes_by_semantic_diff,
)
from the_door.models import (
    Anomaly,
    Feature,
    FeatureRelation,
    L1Output,
    L2Module,
    L2Output,
    ModuleInteraction,
)

# ============================================================================
# Strategies
# ============================================================================

ASCII_TEXT = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
    min_size=1,
    max_size=20,
)

ASCII_TEXT_OPTIONAL = st.one_of(
    st.none(),
    st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
        min_size=1,
        max_size=30,
    ),
)

CONFIDENCE_ST = st.sampled_from(["high", "medium", "low"])

CHANGE_TYPE_ST = st.sampled_from(
    ["added", "removed", "attribute_changed", "dependency_changed"]
)

RISK_FLAG_ST = st.lists(
    st.sampled_from(["out_of_scope", "vulnerability", "semantic_drift"]),
    unique=True,
    max_size=3,
)


@composite
def l1_outputs(draw):
    """Generate valid L1Output objects with arbitrary features and relations.

    Relations may include dangling edges (referencing non-existent feature_ids)
    to test that the converter correctly omits them.
    """
    # Generate unique feature IDs
    feature_ids = draw(
        st.lists(
            st.text(
                alphabet=st.characters(min_codepoint=32, max_codepoint=126),
                min_size=1,
                max_size=10,
            ),
            min_size=0,
            max_size=5,
            unique=True,
        )
    )
    features = [
        Feature(
            feature_id=fid,
            label=draw(
                st.text(
                    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
                    min_size=1,
                    max_size=20,
                )
            ),
            description=draw(
                st.text(
                    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
                    max_size=50,
                )
            ),
            trigger="user_action",
            trigger_description=draw(
                st.one_of(
                    st.just(""),
                    st.text(
                        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
                        max_size=30,
                    ),
                )
            ),
            confidence=draw(st.sampled_from(["high", "medium", "low"])),
            confidence_reason="reason",
        )
        for fid in feature_ids
    ]

    # Generate relations — may include dangling edges (extra IDs not in features)
    extra_ids = draw(
        st.lists(
            st.text(
                alphabet=st.characters(min_codepoint=32, max_codepoint=126),
                min_size=1,
                max_size=10,
            ),
            min_size=0,
            max_size=3,
        )
    )
    all_ids = feature_ids + extra_ids

    num_relations = draw(st.integers(min_value=0, max_value=5))
    relations = []
    for _ in range(num_relations):
        if all_ids:
            relations.append(
                FeatureRelation(
                    from_feature=draw(st.sampled_from(all_ids)),
                    to_feature=draw(st.sampled_from(all_ids)),
                    relation=draw(
                        st.text(
                            alphabet=st.characters(min_codepoint=32, max_codepoint=126),
                            min_size=1,
                            max_size=10,
                        )
                    ),
                    relation_type="static",
                )
            )

    return L1Output(features=features, feature_relations=relations)


@composite
def l2_outputs(draw):
    """Generate valid L2Output objects with arbitrary modules and interactions.

    Interactions may include dangling edges (referencing non-existent module_ids)
    to test that the converter correctly omits them.
    """
    # Generate unique module IDs
    module_ids = draw(
        st.lists(
            st.text(
                alphabet=st.characters(min_codepoint=32, max_codepoint=126),
                min_size=1,
                max_size=10,
            ),
            min_size=0,
            max_size=5,
            unique=True,
        )
    )
    modules = [
        L2Module(
            module_id=mid,
            label=draw(
                st.text(
                    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
                    min_size=1,
                    max_size=20,
                )
            ),
            confidence=draw(st.sampled_from(["high", "medium", "low"])),
            source_nodes=[],
        )
        for mid in module_ids
    ]

    # Generate interactions — may include dangling edges
    extra_ids = draw(
        st.lists(
            st.text(
                alphabet=st.characters(min_codepoint=32, max_codepoint=126),
                min_size=1,
                max_size=10,
            ),
            min_size=0,
            max_size=3,
        )
    )
    all_ids = module_ids + extra_ids

    num_interactions = draw(st.integers(min_value=0, max_value=5))
    interactions = []
    for _ in range(num_interactions):
        if all_ids:
            interactions.append(
                ModuleInteraction(
                    from_module=draw(st.sampled_from(all_ids)),
                    to_module=draw(st.sampled_from(all_ids)),
                    description=draw(
                        st.text(
                            alphabet=st.characters(min_codepoint=32, max_codepoint=126),
                            max_size=30,
                        )
                    ),
                    relation_type="static",
                )
            )

    # Generate anomalies
    num_anomalies = draw(st.integers(min_value=0, max_value=3))
    anomalies = [
        Anomaly(
            anomaly_type=draw(
                st.text(
                    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
                    min_size=1,
                    max_size=15,
                )
            ),
            affected_node_ids=[],
            explanation=draw(
                st.text(
                    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
                    max_size=30,
                )
            ),
            confidence=draw(st.sampled_from(["high", "medium", "low"])),
        )
        for _ in range(num_anomalies)
    ]

    return L2Output(modules=modules, module_interactions=interactions, anomalies=anomalies)


L1_CHANGE_ST = st.fixed_dictionaries({
    "feature_id": st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
        min_size=1,
        max_size=10,
    ),
    "change_type": CHANGE_TYPE_ST,
    "risk_flags": RISK_FLAG_ST,
    "current_label": ASCII_TEXT_OPTIONAL,
    "baseline_label": ASCII_TEXT_OPTIONAL,
    "current_description": ASCII_TEXT_OPTIONAL,
    "baseline_description": ASCII_TEXT_OPTIONAL,
})

UPDATE_REPORT_ST = st.fixed_dictionaries({
    "l1_changes": st.lists(L1_CHANGE_ST, min_size=0, max_size=10),
})

DIFF_NODE_ST = st.fixed_dictionaries({
    "id": st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
        min_size=1,
        max_size=10,
    ),
    "label": st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
        max_size=20,
    ),
    "change_type": CHANGE_TYPE_ST,
    "current_label": ASCII_TEXT_OPTIONAL,
    "baseline_label": ASCII_TEXT_OPTIONAL,
    "current_description": ASCII_TEXT_OPTIONAL,
    "baseline_description": ASCII_TEXT_OPTIONAL,
    "risk_flags": RISK_FLAG_ST,
})


# ============================================================================
# Property 1: L1 no dangling edges
# **Validates: Requirements 2.4, 12.1**
# ============================================================================

@settings(max_examples=100)
@given(l1=l1_outputs())
def test_prop_l1_no_dangling_edges(l1):
    """For all valid L1Output, build_l1_graph_view_model output contains no dangling edges.

    Every edge source and target must reference an existing node id.

    **Validates: Requirements 2.4, 12.1**
    """
    vm = build_l1_graph_view_model(l1)
    node_ids = {n["id"] for n in vm["nodes"]}
    for edge in vm["edges"]:
        assert edge["source"] in node_ids, (
            f"Dangling edge source: {edge['source']} not in node_ids={node_ids}"
        )
        assert edge["target"] in node_ids, (
            f"Dangling edge target: {edge['target']} not in node_ids={node_ids}"
        )


# ============================================================================
# Property 2: L1 node count equals feature count
# **Validates: Requirements 2.5, 12.3**
# ============================================================================

@settings(max_examples=100)
@given(l1=l1_outputs())
def test_prop_l1_node_count_equals_feature_count(l1):
    """For all valid L1Output, node count equals feature count (one-to-one mapping).

    **Validates: Requirements 2.5, 12.3**
    """
    vm = build_l1_graph_view_model(l1)
    assert len(vm["nodes"]) == len(l1.features), (
        f"Expected {len(l1.features)} nodes, got {len(vm['nodes'])}"
    )


# ============================================================================
# Property 3: L1 node ids unique
# **Validates: Requirements 2.5**
# ============================================================================

@settings(max_examples=100)
@given(l1=l1_outputs())
def test_prop_l1_node_ids_unique(l1):
    """For all valid L1Output, all node ids in the output are unique.

    **Validates: Requirements 2.5**
    """
    vm = build_l1_graph_view_model(l1)
    node_ids = [n["id"] for n in vm["nodes"]]
    assert len(node_ids) == len(set(node_ids)), (
        f"Duplicate node ids found: {node_ids}"
    )


# ============================================================================
# Property 4: L2 no dangling edges
# **Validates: Requirements 5.5, 12.2**
# ============================================================================

@settings(max_examples=100)
@given(l2=l2_outputs())
def test_prop_l2_no_dangling_edges(l2):
    """For all valid L2Output, build_l2_graph_view_model output contains no dangling edges.

    Every edge source and target must reference an existing node id.

    **Validates: Requirements 5.5, 12.2**
    """
    vm = build_l2_graph_view_model(l2)
    node_ids = {n["id"] for n in vm["nodes"]}
    for edge in vm["edges"]:
        assert edge["source"] in node_ids, (
            f"Dangling edge source: {edge['source']} not in node_ids={node_ids}"
        )
        assert edge["target"] in node_ids, (
            f"Dangling edge target: {edge['target']} not in node_ids={node_ids}"
        )


# ============================================================================
# Property 5: L2 node ids unique
# **Validates: Requirements 5.6**
# ============================================================================

@settings(max_examples=100)
@given(l2=l2_outputs())
def test_prop_l2_node_ids_unique(l2):
    """For all valid L2Output, all node ids in the output are unique.

    **Validates: Requirements 5.6**
    """
    vm = build_l2_graph_view_model(l2)
    node_ids = [n["id"] for n in vm["nodes"]]
    assert len(node_ids) == len(set(node_ids)), (
        f"Duplicate node ids found: {node_ids}"
    )


# ============================================================================
# Property 6: Diff valid change types
# **Validates: Requirements 9.5, 12.4**
# ============================================================================

VALID_CHANGE_TYPES = {"added", "removed", "attribute_changed", "dependency_changed"}


@settings(max_examples=100)
@given(report=UPDATE_REPORT_ST)
def test_prop_diff_valid_change_types(report):
    """For all valid UpdateReport, every node's change_type is one of the four valid values.

    **Validates: Requirements 9.5, 12.4**
    """
    vm = build_diff_graph_view_model(report, diff_result=None)
    for node in vm["nodes"]:
        assert node["change_type"] in VALID_CHANGE_TYPES, (
            f"Invalid change_type: {node['change_type']!r}, "
            f"expected one of {VALID_CHANGE_TYPES}"
        )


# ============================================================================
# Property 7: Diff no dangling edges
# **Validates: Requirements 9.3**
# ============================================================================

@composite
def update_report_with_diff_result(draw):
    """Generate an UpdateReport dict paired with a matching diff_result dict.

    The diff_result may contain edges referencing both existing and non-existing nodes.
    """
    report = draw(UPDATE_REPORT_ST)
    changed_ids = [c["feature_id"] for c in report["l1_changes"]]

    # Generate extra IDs that may appear in edge_diffs (dangling)
    extra_ids = draw(
        st.lists(
            st.text(
                alphabet=st.characters(min_codepoint=32, max_codepoint=126),
                min_size=1,
                max_size=10,
            ),
            min_size=0,
            max_size=3,
        )
    )
    all_ids = changed_ids + extra_ids

    num_edges = draw(st.integers(min_value=0, max_value=5))
    edge_diffs = []
    for _ in range(num_edges):
        if all_ids:
            edge_diffs.append({
                "from_node": draw(st.sampled_from(all_ids)),
                "to_node": draw(st.sampled_from(all_ids)),
                "diff_state": draw(st.sampled_from(["added", "removed", "modified"])),
            })

    diff_result = {"edge_diffs": edge_diffs} if edge_diffs else None
    return report, diff_result


@settings(max_examples=100)
@given(data=update_report_with_diff_result())
def test_prop_diff_no_dangling_edges(data):
    """For all valid UpdateReport + DiffResult, Diff ViewModel contains no dangling edges.

    Every edge source and target must reference an existing node id.

    **Validates: Requirements 9.3**
    """
    report, diff_result = data
    vm = build_diff_graph_view_model(report, diff_result=diff_result)
    node_ids = {n["id"] for n in vm["nodes"]}
    for edge in vm["edges"]:
        assert edge["source"] in node_ids, (
            f"Dangling edge source: {edge['source']} not in node_ids={node_ids}"
        )
        assert edge["target"] in node_ids, (
            f"Dangling edge target: {edge['target']} not in node_ids={node_ids}"
        )


# ============================================================================
# Property 8: L1 node required fields
# **Validates: Requirements 2.2**
# ============================================================================

@settings(max_examples=100)
@given(l1=l1_outputs())
def test_prop_l1_node_required_fields(l1):
    """Every L1 node has id, label, confidence, description, trigger_description fields.

    **Validates: Requirements 2.2**
    """
    vm = build_l1_graph_view_model(l1)
    required_fields = {"id", "label", "confidence", "description", "trigger_description"}
    for node in vm["nodes"]:
        for field in required_fields:
            assert field in node, (
                f"Node missing required field '{field}': {node}"
            )


# ============================================================================
# Property 9: L2 node required fields
# **Validates: Requirements 5.2**
# ============================================================================

@settings(max_examples=100)
@given(l2=l2_outputs())
def test_prop_l2_node_required_fields(l2):
    """Every L2 node has id, label, confidence, source_nodes fields.

    **Validates: Requirements 5.2**
    """
    vm = build_l2_graph_view_model(l2)
    required_fields = {"id", "label", "confidence", "source_nodes"}
    for node in vm["nodes"]:
        for field in required_fields:
            assert field in node, (
                f"Node missing required field '{field}': {node}"
            )


# ============================================================================
# Property 10: sort_semantic_diff idempotent
# **Validates: Requirements 10.4, 12.5**
# ============================================================================

@settings(max_examples=100)
@given(nodes=st.lists(DIFF_NODE_ST, min_size=0, max_size=10))
def test_prop_sort_semantic_diff_idempotent(nodes):
    """Applying sort_diff_nodes_by_semantic_diff twice produces the same result as once.

    **Validates: Requirements 10.4, 12.5**
    """
    once = sort_diff_nodes_by_semantic_diff(nodes)
    twice = sort_diff_nodes_by_semantic_diff(once)
    assert once == twice, (
        f"sort_diff_nodes_by_semantic_diff is not idempotent.\n"
        f"Once:  {[n['id'] for n in once]}\n"
        f"Twice: {[n['id'] for n in twice]}"
    )


# ============================================================================
# Property 11: sort risk first — out_of_scope nodes before others
# **Validates: Requirements 10.1**
# ============================================================================

from the_door.core.ui.graph_view_model import sort_diff_nodes_by_risk


@settings(max_examples=100)
@given(nodes=st.lists(DIFF_NODE_ST, min_size=0, max_size=10))
def test_prop_sort_risk_first_out_of_scope_before_others(nodes):
    """After sort_diff_nodes_by_risk, all out_of_scope nodes appear before non-out_of_scope nodes.

    **Validates: Requirements 10.1**
    """
    sorted_nodes = sort_diff_nodes_by_risk(nodes)

    # Find the last out_of_scope node index and first non-out_of_scope node index
    out_of_scope_indices = [
        i for i, n in enumerate(sorted_nodes)
        if "out_of_scope" in n.get("risk_flags", [])
    ]
    non_out_of_scope_indices = [
        i for i, n in enumerate(sorted_nodes)
        if "out_of_scope" not in n.get("risk_flags", [])
    ]

    if out_of_scope_indices and non_out_of_scope_indices:
        last_oos = max(out_of_scope_indices)
        first_non_oos = min(non_out_of_scope_indices)
        assert last_oos < first_non_oos, (
            f"out_of_scope node at index {last_oos} appears after "
            f"non-out_of_scope node at index {first_non_oos}.\n"
            f"Sorted order: {[(n['id'], n.get('risk_flags', [])) for n in sorted_nodes]}"
        )


# ============================================================================
# Property 12: sort_semantic_diff monotone (non-increasing magnitude)
# **Validates: Requirements 10.4**
# ============================================================================

import difflib


def _magnitude(node: dict) -> int:
    """Calculate semantic change magnitude for a node (mirrors graph_view_model._edit_distance)."""
    def _edit_distance(a, b):
        a = a or ""
        b = b or ""
        ratio = difflib.SequenceMatcher(None, a, b).ratio()
        max_len = max(len(a), len(b))
        return int(max_len * (1 - ratio))

    return (
        _edit_distance(node.get("current_label"), node.get("baseline_label"))
        + _edit_distance(node.get("current_description"), node.get("baseline_description"))
    )


@settings(max_examples=100)
@given(nodes=st.lists(DIFF_NODE_ST, min_size=0, max_size=10))
def test_prop_sort_semantic_diff_monotone(nodes):
    """After sort_diff_nodes_by_semantic_diff, adjacent nodes have non-increasing magnitude.

    **Validates: Requirements 10.4**
    """
    sorted_nodes = sort_diff_nodes_by_semantic_diff(nodes)

    for i in range(len(sorted_nodes) - 1):
        mag_current = _magnitude(sorted_nodes[i])
        mag_next = _magnitude(sorted_nodes[i + 1])
        assert mag_current >= mag_next, (
            f"Magnitude not non-increasing at index {i}: "
            f"node[{i}]={sorted_nodes[i]['id']} magnitude={mag_current} > "
            f"node[{i+1}]={sorted_nodes[i+1]['id']} magnitude={mag_next}"
        )
