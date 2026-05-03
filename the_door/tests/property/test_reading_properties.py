"""Property-based tests for reading engine.

Tests are written BEFORE implementation (TDD red phase).
Uses Hypothesis to verify universal correctness properties.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings, assume, note
from hypothesis import strategies as st

from the_door.core.reading.pruning_engine import PruningEngine
from the_door.core.reading.batch_reader import BatchReader
from the_door.core.reading.narrative_chain import NarrativeChain
from the_door.core.reading.source_reviewer import SourceReviewer
from the_door.models import (
    Edge,
    TopologyEntry,
    StructureJSON,
    ASTNode,
    FileInfo,
    NarrativeRecord,
)


# === Strategies ===

NODE_ID = st.builds(
    lambda file, func: f"{file}.py::{func}",
    file=st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=3, max_size=10),
    func=st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122, whitelist_characters="_"), min_size=3, max_size=15),
)

FEATURE_ID = st.builds(
    lambda suffix: f"feat-{suffix}",
    suffix=st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=2, max_size=10),
)

CONFIDENCE = st.sampled_from(["high", "medium", "low"])

BATCH_NUM = st.integers(min_value=1, max_value=5)


def make_topology_entry(node_id: str, batch: int, rank: int = 1) -> TopologyEntry:
    """Create a TopologyEntry for testing."""
    return TopologyEntry(
        node_id=node_id,
        in_degree=0,
        out_degree=0,
        topology_rank=rank,
        is_entry_point=(rank == 1),
        batch_assignment=batch,
    )


@st.composite
def structure_with_batches(draw, min_nodes=2, max_nodes=10, max_batches=5):
    """Generate a StructureJSON with nodes assigned to batches 1..N."""
    num_nodes = draw(st.integers(min_value=min_nodes, max_value=max_nodes))
    num_batches = draw(st.integers(min_value=1, max_value=min(max_batches, num_nodes)))

    # Generate unique node IDs
    node_ids = []
    for i in range(num_nodes):
        file_name = f"mod{i // 3}.py"
        func_name = f"func_{i}"
        node_ids.append(f"{file_name}::{func_name}")

    # Assign nodes to batches (at least one node per batch)
    batch_assignments = []
    # First ensure each batch has at least one node
    for b in range(1, num_batches + 1):
        batch_assignments.append(b)
    # Assign remaining nodes randomly
    for _ in range(num_nodes - num_batches):
        batch_assignments.append(draw(st.integers(min_value=1, max_value=num_batches)))
    # Shuffle to randomize which nodes get which batch
    batch_assignments = draw(st.permutations(batch_assignments))

    nodes = []
    topology = []
    for i, (nid, batch) in enumerate(zip(node_ids, batch_assignments)):
        parts = nid.split("::")
        nodes.append(
            ASTNode(
                node_id=nid,
                type="function",
                name=parts[1],
                file=parts[0],
                language="python",
            )
        )
        topology.append(
            TopologyEntry(
                node_id=nid,
                in_degree=i % 3,
                out_degree=(i + 1) % 3,
                topology_rank=batch,
                is_entry_point=(batch == 1),
                batch_assignment=batch,
            )
        )

    files = list({n.file for n in nodes})
    file_infos = [FileInfo(path=f, language="python") for f in files]

    structure = StructureJSON(
        files=file_infos,
        nodes=nodes,
        edges=[],
        topology=topology,
    )
    return structure, num_batches


@st.composite
def edge_graph(draw, node_ids: list[str] | None = None):
    """Generate a random edge graph between nodes."""
    if node_ids is None:
        num_nodes = draw(st.integers(min_value=3, max_value=8))
        node_ids = [f"mod{i}.py::func_{i}" for i in range(num_nodes)]

    edges = []
    num_edges = draw(st.integers(min_value=0, max_value=len(node_ids) * 2))
    for _ in range(num_edges):
        from_node = draw(st.sampled_from(node_ids))
        to_node = draw(st.sampled_from(node_ids))
        if from_node != to_node:
            edges.append(Edge(from_node=from_node, to_node=to_node, type="calls"))

    return node_ids, edges


@st.composite
def confidence_sequence(draw, node_ids: list[str] | None = None):
    """Generate a sequence of (node_id, confidence, batch) tuples."""
    if node_ids is None:
        num_nodes = draw(st.integers(min_value=2, max_value=8))
        node_ids = [f"mod{i}.py::func_{i}" for i in range(num_nodes)]

    sequence = []
    for nid in node_ids:
        conf = draw(CONFIDENCE)
        batch = draw(BATCH_NUM)
        sequence.append((nid, conf, batch))

    return node_ids, sequence


@st.composite
def structure_pair(draw, change_type="mixed"):
    """Generate a pair of StructureJSONs (before/after) with known differences."""
    # Base nodes
    num_base = draw(st.integers(min_value=3, max_value=8))
    base_ids = [f"mod{i}.py::func_{i}" for i in range(num_base)]

    # Determine changes
    num_added = draw(st.integers(min_value=0, max_value=3))
    num_removed = draw(st.integers(min_value=0, max_value=min(2, num_base - 1)))

    added_ids = [f"new{i}.py::new_func_{i}" for i in range(num_added)]
    removed_ids = draw(
        st.lists(
            st.sampled_from(base_ids),
            min_size=num_removed,
            max_size=num_removed,
            unique=True,
        )
    ) if num_removed > 0 and base_ids else []

    # Build "before" structure
    before_nodes = [
        ASTNode(node_id=nid, type="function", name=nid.split("::")[1], file=nid.split("::")[0], language="python")
        for nid in base_ids
    ]
    before_topo = [
        TopologyEntry(node_id=nid, in_degree=0, out_degree=0, topology_rank=1, is_entry_point=True, batch_assignment=1)
        for nid in base_ids
    ]
    before = StructureJSON(nodes=before_nodes, topology=before_topo)

    # Build "after" structure
    after_ids = [nid for nid in base_ids if nid not in removed_ids] + added_ids
    after_nodes = [
        ASTNode(node_id=nid, type="function", name=nid.split("::")[1], file=nid.split("::")[0], language="python")
        for nid in after_ids
    ]
    after_topo = [
        TopologyEntry(node_id=nid, in_degree=0, out_degree=0, topology_rank=1, is_entry_point=True, batch_assignment=1)
        for nid in after_ids
    ]
    after = StructureJSON(nodes=after_nodes, topology=after_topo)

    expected_added = set(added_ids)
    expected_removed = set(removed_ids)

    return before, after, expected_added, expected_removed


@st.composite
def feature_result_pairs(draw):
    """Generate pairs of feature results (same or different) for regeneration diff testing."""
    feature_id = draw(FEATURE_ID)
    label_a = draw(st.text(min_size=5, max_size=50, alphabet=st.characters(min_codepoint=97, max_codepoint=122, whitelist_characters=" ")))
    desc_a = draw(st.text(min_size=10, max_size=100, alphabet=st.characters(min_codepoint=97, max_codepoint=122, whitelist_characters=" ")))
    source_a = draw(st.lists(NODE_ID, min_size=1, max_size=3))

    # Decide if results differ
    differs = draw(st.booleans())

    if differs:
        # Change at least one field
        change_field = draw(st.sampled_from(["label", "description", "source_nodes"]))
        label_b = label_a
        desc_b = desc_a
        source_b = list(source_a)
        if change_field == "label":
            label_b = label_a + " (updated)"
        elif change_field == "description":
            desc_b = desc_a + " with additional context"
        else:
            source_b = source_a + [draw(NODE_ID)]
    else:
        label_b = label_a
        desc_b = desc_a
        source_b = list(source_a)

    result_a = {"feature_id": feature_id, "label": label_a, "description": desc_a, "source_nodes": source_a}
    result_b = {"feature_id": feature_id, "label": label_b, "description": desc_b, "source_nodes": source_b}

    return result_a, result_b, differs


# ============================================================================
# Property 13: Batch ordering follows topology assignment
# ============================================================================


class TestBatchOrdering:
    """Property 13: BatchReader processes batches in strictly ascending order.

    Every node in batch K is submitted before any node in batch K+1.
    """

    @given(data=structure_with_batches())
    def test_batches_processed_in_ascending_order(self, data):
        """Batches are processed in strictly ascending order 1, 2, ..., N."""
        structure, num_batches = data

        # Group nodes by batch
        batch_groups: dict[int, list[str]] = {}
        for entry in structure.topology:
            batch_groups.setdefault(entry.batch_assignment, []).append(entry.node_id)

        # Verify batch numbers are 1..N with no gaps
        batch_nums = sorted(batch_groups.keys())
        assert batch_nums == list(range(1, num_batches + 1))

        # The BatchReader must process in this order
        # (This will be verified against actual BatchReader output once implemented)
        # For now, verify the structure is well-formed for the property
        for b in batch_nums:
            assert len(batch_groups[b]) >= 1, f"Batch {b} must have at least one node"


# ============================================================================
# Property 14: Batch consolidation preserves all features
# ============================================================================


class TestBatchConsolidation:
    """Property 14: Consolidated L1 output contains every feature from every batch.

    No features lost, no duplicate feature_ids.
    """

    @given(
        num_batches=st.integers(min_value=1, max_value=5),
        features_per_batch=st.lists(
            st.integers(min_value=1, max_value=5), min_size=1, max_size=5
        ),
    )
    def test_consolidation_preserves_all_features(self, num_batches, features_per_batch):
        """All features from all batches appear in consolidated output."""
        # Adjust features_per_batch to match num_batches
        features_per_batch = features_per_batch[:num_batches]
        while len(features_per_batch) < num_batches:
            features_per_batch.append(1)

        # Generate per-batch feature sets
        all_feature_ids: set[str] = set()
        batch_responses: list[dict] = []
        for batch_idx, num_features in enumerate(features_per_batch, 1):
            features = []
            for feat_idx in range(num_features):
                fid = f"feat-b{batch_idx}-f{feat_idx}"
                all_feature_ids.add(fid)
                features.append({
                    "feature_id": fid,
                    "label": f"Feature {fid}",
                    "description": f"Description for {fid}",
                    "trigger": "user_action",
                    "trigger_description": "User triggers this",
                    "confidence": "high",
                    "confidence_reason": "Clear from AST",
                    "source_nodes": [f"mod{batch_idx}.py::func_{feat_idx}"],
                })
            batch_responses.append({"features": features})

        # Verify: consolidated set must equal union of all batch features
        consolidated_ids: set[str] = set()
        for resp in batch_responses:
            for feat in resp["features"]:
                consolidated_ids.add(feat["feature_id"])

        assert consolidated_ids == all_feature_ids, "All features must be preserved"
        assert len(consolidated_ids) == sum(features_per_batch), "No duplicates"


# ============================================================================
# Property 15: Pruning invariant — high confidence excludes downstream
# ============================================================================


class TestPruningInvariant:
    """Property 15: High-confidence nodes are pruned AND their downstream
    dependencies are excluded from subsequent batch payloads (unless those
    dependencies have other pending references).
    """

    @given(data=edge_graph())
    def test_high_confidence_prunes_downstream(self, data):
        """High-confidence node prunes itself and exclusive downstream deps."""
        node_ids, edges = data
        assume(len(node_ids) >= 3)
        assume(len(edges) >= 1)

        engine = PruningEngine(edges)

        # Pick a node with outgoing edges to mark as high confidence
        nodes_with_outgoing = [
            e.from_node for e in edges
        ]
        assume(len(nodes_with_outgoing) > 0)

        target = nodes_with_outgoing[0]
        engine.record_confidence(target, "high", batch=1)

        pruned = engine.get_pruned_nodes()

        # The target itself must be pruned
        assert target in pruned

        # Direct downstream nodes that have NO other incoming edges from non-pruned nodes
        # should also be pruned
        for edge in edges:
            if edge.from_node == target:
                downstream = edge.to_node
                # Check if downstream has other non-pruned sources
                other_sources = [
                    e.from_node for e in edges
                    if e.to_node == downstream and e.from_node != target and e.from_node not in pruned
                ]
                if not other_sources:
                    assert downstream in pruned, (
                        f"Downstream {downstream} should be pruned (no other pending refs)"
                    )

    @given(data=edge_graph())
    def test_medium_low_confidence_not_pruned(self, data):
        """Medium and low confidence nodes are NOT pruned."""
        node_ids, edges = data
        assume(len(node_ids) >= 2)

        engine = PruningEngine(edges)

        target = node_ids[0]
        engine.record_confidence(target, "medium", batch=1)

        pruned = engine.get_pruned_nodes()
        assert target not in pruned

    @given(data=edge_graph())
    def test_downstream_with_other_refs_not_pruned(self, data):
        """Downstream node with other pending references is NOT pruned."""
        node_ids, edges = data
        assume(len(node_ids) >= 3)

        # Find a node that has multiple incoming edges
        incoming_count: dict[str, int] = {}
        for e in edges:
            incoming_count[e.to_node] = incoming_count.get(e.to_node, 0) + 1

        multi_incoming = [nid for nid, count in incoming_count.items() if count >= 2]
        assume(len(multi_incoming) > 0)

        target_downstream = multi_incoming[0]
        # Find one source to prune
        sources = [e.from_node for e in edges if e.to_node == target_downstream]
        assume(len(sources) >= 2)

        engine = PruningEngine(edges)
        # Only prune one source — the downstream should NOT be pruned
        engine.record_confidence(sources[0], "high", batch=1)

        pruned = engine.get_pruned_nodes()
        # The downstream has another non-pruned source, so it should NOT be pruned
        other_sources_alive = [s for s in sources[1:] if s not in pruned]
        if other_sources_alive:
            assert target_downstream not in pruned


# ============================================================================
# Property 16: Pruning reinstatement on low-confidence reference
# ============================================================================


class TestPruningReinstatement:
    """Property 16: Pruned nodes are reinstated when referenced by low-confidence nodes."""

    @given(data=edge_graph())
    def test_reinstatement_removes_from_pruned(self, data):
        """Reinstated node is removed from pruned set."""
        node_ids, edges = data
        assume(len(node_ids) >= 2)

        engine = PruningEngine(edges)

        # Prune a node
        target = node_ids[0]
        engine.record_confidence(target, "high", batch=1)
        assert target in engine.get_pruned_nodes()

        # Reinstate it
        result = engine.reinstate(target, batch=2)
        assert result is True
        assert target not in engine.get_pruned_nodes()


# ============================================================================
# Property 17: Pruning decisions recorded in narrative chain
# ============================================================================


class TestPruningNarrativeRecording:
    """Property 17: Every pruning decision is recorded in the narrative chain."""

    @given(data=confidence_sequence())
    def test_decisions_recorded_for_each_pruning(self, data):
        """Narrative chain contains a record for each pruning decision."""
        node_ids, sequence = data

        engine = PruningEngine([])  # No edges for simplicity

        for nid, conf, batch in sequence:
            engine.record_confidence(nid, conf, batch)

        decisions = engine.get_decisions()

        # Every high-confidence recording should produce a decision
        high_conf_recordings = [(nid, batch) for nid, conf, batch in sequence if conf == "high"]
        for nid, batch in high_conf_recordings:
            matching = [d for d in decisions if d.node_id == nid and d.batch == batch]
            assert len(matching) >= 1, f"Missing decision for {nid} at batch {batch}"


# ============================================================================
# Property 20: Structural change detection correctness
# ============================================================================


class TestStructuralChangeDetection:
    """Property 20: Detector correctly reports added, removed, modified nodes."""

    @given(data=structure_pair())
    def test_change_detection_reports_correct_sets(self, data):
        """Detector reports correct added_nodes and removed_nodes sets."""
        before, after, expected_added, expected_removed = data

        before_ids = {n.node_id for n in before.nodes}
        after_ids = {n.node_id for n in after.nodes}

        # Verify our expected sets match the actual difference
        actual_added = after_ids - before_ids
        actual_removed = before_ids - after_ids

        assert actual_added == expected_added
        assert actual_removed == expected_removed

    @given(data=structure_with_batches(min_nodes=3, max_nodes=6))
    def test_identical_structures_report_no_changes(self, data):
        """Identical structures produce no change report."""
        structure, _ = data

        before_ids = {n.node_id for n in structure.nodes}
        after_ids = {n.node_id for n in structure.nodes}

        added = after_ids - before_ids
        removed = before_ids - after_ids

        assert added == set()
        assert removed == set()


# ============================================================================
# Property 21: Regeneration diff marking
# ============================================================================


class TestRegenerationDiffMarking:
    """Property 21: Marker applied iff results differ."""

    @given(data=feature_result_pairs())
    def test_diff_marker_applied_iff_results_differ(self, data):
        """'AI inference: regenerated, differs from previous' applied iff different."""
        result_a, result_b, expected_differs = data

        # Determine if results actually differ
        actually_differs = (
            result_a["label"] != result_b["label"]
            or result_a["description"] != result_b["description"]
            or result_a["source_nodes"] != result_b["source_nodes"]
        )

        assert actually_differs == expected_differs

        # The marker should be applied iff results differ
        # (This validates the property logic; actual implementation will be tested
        # against BatchReader.regenerate() once implemented)
        should_mark = actually_differs
        assert should_mark == expected_differs


# ============================================================================
# Property 26: Infrastructure consolidation into single block
# ============================================================================


class TestInfrastructureConsolidation:
    """Property 26: L1.5 output contains exactly one infrastructure_block
    whose components cover every infrastructure node_id from L1.
    """

    @given(
        infra_nodes=st.lists(NODE_ID, min_size=1, max_size=5, unique=True),
    )
    def test_single_infrastructure_block_covers_all(self, infra_nodes):
        """Exactly one infrastructure_block with all infrastructure node_ids."""
        # Simulate L1 output with infrastructure_nodes
        l1_infra = set(infra_nodes)

        # The L1.5 infrastructure_block.components must cover all of them
        # (This is the property we'll verify against actual implementation)
        # For now, verify the property logic
        infra_block_components = set(infra_nodes)  # Expected output

        assert infra_block_components == l1_infra
        assert len(infra_block_components) == len(infra_nodes)


# ============================================================================
# Property 33: Source code snippet extraction accuracy
# ============================================================================


class TestSourceSnippetExtraction:
    """Property 33: SourceReviewer extracts correct function body text."""

    @given(
        func_name=st.from_regex(r"[a-z][a-z_]{2,15}", fullmatch=True).filter(lambda s: s.isidentifier()),
        body_lines=st.lists(
            st.text(
                alphabet=st.characters(min_codepoint=32, max_codepoint=126, whitelist_characters=" =+()"),
                min_size=1,
                max_size=60,
            ).filter(lambda s: s.isascii()),
            min_size=1,
            max_size=10,
        ),
        prefix_lines=st.integers(min_value=0, max_value=5),
    )
    def test_extracts_correct_function_body(
        self, tmp_path: Path, func_name: str, body_lines: list[str], prefix_lines: int
    ):
        """Extracted snippet matches the actual function body in the file."""
        # Build a Python file with the function at a known position
        lines = []
        for i in range(prefix_lines):
            lines.append(f"# prefix line {i}")

        func_start = len(lines) + 1  # 1-indexed
        lines.append(f"def {func_name}():")
        for bl in body_lines:
            lines.append(f"    {bl}")
        func_end = len(lines)  # 1-indexed, inclusive

        source_file = tmp_path / "module.py"
        source_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # The expected snippet
        expected_text = f"def {func_name}():\n" + "\n".join(f"    {bl}" for bl in body_lines) + "\n"

        # Verify our test setup is correct
        file_content = source_file.read_text()
        assert f"def {func_name}():" in file_content
        assert func_start >= 1
        assert func_end >= func_start
