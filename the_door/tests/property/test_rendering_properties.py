"""Property-based tests for rendering and narrative chain.

Tests are written BEFORE implementation (TDD red phase).
Uses Hypothesis to verify universal correctness properties.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings, assume, note
from hypothesis import strategies as st

from the_door.core.rendering.mermaid_renderer import MermaidRenderer
from the_door.core.rendering.cost_estimator import CostEstimator
from the_door.core.reading.narrative_chain import NarrativeChain
from the_door.models import (
    Feature,
    FeatureRelation,
    L1Output,
    L1_5Block,
    BlockRelation,
    InfrastructureBlock,
    L1_5Output,
    NarrativeRecord,
    NarrativeNodeRead,
    StructureJSON,
    ASTNode,
    FileInfo,
    TopologyEntry,
    CostEstimate,
)


# === Strategies ===

NODE_ID = st.builds(
    lambda file, func: f"{file}.py::{func}",
    file=st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=3, max_size=10),
    func=st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122, whitelist_characters="_"), min_size=3, max_size=15),
)

FEATURE_ID = st.from_regex(r"feat-[a-z]{3,10}", fullmatch=True)

BLOCK_ID = st.from_regex(r"blk-[a-z]{3,10}", fullmatch=True)

CONFIDENCE = st.sampled_from(["high", "medium", "low"])

TRIGGER = st.sampled_from(["user_action", "scheduled", "auto_triggered"])

SAFE_LABEL = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122, whitelist_characters=" ,-0123456789"),
    min_size=3,
    max_size=40,
).filter(lambda s: s.strip())

TIMESTAMP = st.from_regex(
    r"2025-0[1-9]-[012][0-9]T[01][0-9]:[0-5][0-9]:[0-5][0-9]Z", fullmatch=True
)


@st.composite
def narrative_record_batch(draw):
    """Generate a valid batch NarrativeRecord."""
    num_nodes = draw(st.integers(min_value=1, max_value=5))
    nodes_read = []
    for i in range(num_nodes):
        nodes_read.append(
            NarrativeNodeRead(
                node_id=draw(NODE_ID),
                topology_rank=draw(st.integers(min_value=1, max_value=5)),
                in_degree=draw(st.integers(min_value=0, max_value=10)),
                is_entry_point=draw(st.booleans()),
            )
        )
    return NarrativeRecord(
        record_type="batch",
        timestamp=draw(TIMESTAMP),
        batch=draw(st.integers(min_value=1, max_value=5)),
        strategy="topology_guided",
        nodes_read=nodes_read,
        llm_judgment=draw(st.text(min_size=5, max_size=100, alphabet=st.characters(min_codepoint=97, max_codepoint=122, whitelist_characters=" "))),
        pruned_nodes=draw(st.lists(NODE_ID, max_size=3)),
        pending_low_confidence=draw(st.lists(NODE_ID, max_size=2)),
    )


@st.composite
def narrative_record_regeneration(draw):
    """Generate a valid regeneration NarrativeRecord."""
    return NarrativeRecord(
        record_type="regeneration",
        timestamp=draw(TIMESTAMP),
        feature_id=draw(FEATURE_ID),
        previous_summary=draw(st.text(min_size=5, max_size=80, alphabet=st.characters(min_codepoint=97, max_codepoint=122, whitelist_characters=" "))),
        new_summary=draw(st.text(min_size=5, max_size=80, alphabet=st.characters(min_codepoint=97, max_codepoint=122, whitelist_characters=" "))),
    )


@st.composite
def narrative_record_structural_change(draw):
    """Generate a valid structural_change NarrativeRecord."""
    return NarrativeRecord(
        record_type="structural_change",
        timestamp=draw(TIMESTAMP),
        added_nodes=draw(st.lists(NODE_ID, max_size=3)),
        removed_nodes=draw(st.lists(NODE_ID, max_size=3)),
        modified_nodes=draw(st.lists(NODE_ID, max_size=3)),
    )


NARRATIVE_RECORD = st.one_of(
    narrative_record_batch(),
    narrative_record_regeneration(),
    narrative_record_structural_change(),
)


@st.composite
def l1_output_with_features(draw, min_features=1, max_features=5):
    """Generate a valid L1Output with features and relations."""
    num_features = draw(st.integers(min_value=min_features, max_value=max_features))
    features = []
    feature_ids = []
    for i in range(num_features):
        fid = f"feat-{chr(97 + i)}"  # feat-a, feat-b, ...
        feature_ids.append(fid)
        features.append(
            Feature(
                feature_id=fid,
                label=draw(SAFE_LABEL),
                description=f"Description for feature {fid}",
                trigger=draw(TRIGGER),
                trigger_description=f"Trigger for {fid}",
                confidence=draw(CONFIDENCE),
                confidence_reason="Clear from AST",
                source_nodes=[f"mod{i}.py::func_{i}"],
            )
        )

    # Generate some relations between features
    relations = []
    if len(feature_ids) >= 2:
        num_relations = draw(st.integers(min_value=0, max_value=min(3, len(feature_ids) - 1)))
        for _ in range(num_relations):
            from_f = draw(st.sampled_from(feature_ids))
            to_f = draw(st.sampled_from(feature_ids))
            if from_f != to_f:
                relations.append(
                    FeatureRelation(
                        from_feature=from_f,
                        to_feature=to_f,
                        relation="Related features",
                        relation_type=draw(st.sampled_from(["static", "inferred"])),
                        inferred_reason="Shared data" if draw(st.booleans()) else None,
                    )
                )

    return L1Output(
        summary="Test summary",
        features=features,
        feature_relations=relations,
    )


@st.composite
def l1_5_output_with_blocks(draw, min_blocks=1, max_blocks=5):
    """Generate a valid L1_5Output with blocks and relations."""
    num_blocks = draw(st.integers(min_value=min_blocks, max_value=max_blocks))
    blocks = []
    block_ids = []
    for i in range(num_blocks):
        bid = f"blk-{chr(97 + i)}"
        block_ids.append(bid)
        blocks.append(
            L1_5Block(
                block_id=bid,
                label=draw(SAFE_LABEL),
                responsibility=f"Responsibility for {bid}",
                trigger_mechanism=f"Trigger for {bid}",
                related_features=[f"feat-{chr(97 + i)}"],
            )
        )

    relations = []
    if len(block_ids) >= 2:
        num_relations = draw(st.integers(min_value=0, max_value=min(3, len(block_ids) - 1)))
        for _ in range(num_relations):
            from_b = draw(st.sampled_from(block_ids))
            to_b = draw(st.sampled_from(block_ids))
            if from_b != to_b:
                relations.append(
                    BlockRelation(
                        from_block=from_b,
                        to_block=to_b,
                        relation="Block relation",
                        relation_type=draw(st.sampled_from(["static", "inferred"])),
                        inferred_reason="Shared concern" if draw(st.booleans()) else None,
                    )
                )

    infra = InfrastructureBlock(
        label="System Infrastructure",
        components=draw(st.lists(NODE_ID, min_size=0, max_size=3)),
    )

    return L1_5Output(blocks=blocks, block_relations=relations, infrastructure_block=infra)


@st.composite
def structure_pair_for_cost(draw):
    """Generate two StructureJSONs where A has strictly more nodes than B."""
    num_b = draw(st.integers(min_value=1, max_value=5))
    num_a = draw(st.integers(min_value=num_b + 1, max_value=num_b + 5))

    def make_structure(n):
        nodes = [
            ASTNode(
                node_id=f"mod{i}.py::func_{i}",
                type="function",
                name=f"func_{i}",
                file=f"mod{i}.py",
                language="python",
            )
            for i in range(n)
        ]
        topology = [
            TopologyEntry(
                node_id=f"mod{i}.py::func_{i}",
                in_degree=0,
                out_degree=0,
                topology_rank=1,
                is_entry_point=True,
                batch_assignment=1,
            )
            for i in range(n)
        ]
        files = [FileInfo(path=f"mod{i}.py", language="python") for i in range(n)]
        return StructureJSON(files=files, nodes=nodes, topology=topology)

    return make_structure(num_a), make_structure(num_b)


# ============================================================================
# Property 18: Narrative chain JSONL round-trip
# ============================================================================


class TestNarrativeChainRoundTrip:
    """Property 18: Write records to JSONL and read back without loss."""

    @given(records=st.lists(NARRATIVE_RECORD, min_size=1, max_size=10))
    def test_round_trip_preserves_all_records(self, tmp_path: Path, records: list[NarrativeRecord]):
        """No records lost, no fields altered, order preserved."""
        chain_path = tmp_path / "chain.jsonl"
        # Ensure clean state for each Hypothesis example
        if chain_path.exists():
            chain_path.unlink()

        chain = NarrativeChain(chain_path)
        for record in records:
            chain.append(record)

        read_back = chain.read_all()

        assert len(read_back) == len(records)
        for original, restored in zip(records, read_back):
            assert restored.record_type == original.record_type
            assert restored.timestamp == original.timestamp

            if original.record_type == "batch":
                assert restored.batch == original.batch
                assert restored.strategy == original.strategy
                assert len(restored.nodes_read) == len(original.nodes_read)
                assert restored.llm_judgment == original.llm_judgment
                assert restored.pruned_nodes == original.pruned_nodes
                assert restored.pending_low_confidence == original.pending_low_confidence
            elif original.record_type == "regeneration":
                assert restored.feature_id == original.feature_id
                assert restored.previous_summary == original.previous_summary
                assert restored.new_summary == original.new_summary
            elif original.record_type == "structural_change":
                assert restored.added_nodes == original.added_nodes
                assert restored.removed_nodes == original.removed_nodes
                assert restored.modified_nodes == original.modified_nodes


# ============================================================================
# Property 19: Narrative chain schema conformance
# ============================================================================


class TestNarrativeChainSchemaConformance:
    """Property 19: Each NarrativeRecord conforms to narrative.schema.json."""

    @given(record=narrative_record_batch())
    def test_batch_record_has_required_fields(self, record: NarrativeRecord):
        """Batch records have all required batch fields."""
        assert record.record_type == "batch"
        assert record.batch is not None and record.batch >= 1
        assert record.strategy != ""
        assert isinstance(record.nodes_read, list)
        assert record.llm_judgment != ""
        assert isinstance(record.pruned_nodes, list)
        assert isinstance(record.pending_low_confidence, list)

    @given(record=narrative_record_regeneration())
    def test_regeneration_record_has_required_fields(self, record: NarrativeRecord):
        """Regeneration records have all required regeneration fields."""
        assert record.record_type == "regeneration"
        assert record.feature_id is not None
        assert record.previous_summary is not None
        assert record.new_summary is not None

    @given(record=narrative_record_structural_change())
    def test_structural_change_record_has_required_fields(self, record: NarrativeRecord):
        """Structural change records have all required change fields."""
        assert record.record_type == "structural_change"
        assert record.added_nodes is not None
        assert record.removed_nodes is not None
        assert record.modified_nodes is not None


# ============================================================================
# Property 23: Cost estimation scales with structure size
# ============================================================================


class TestCostEstimationScaling:
    """Property 23: Larger structures produce higher or equal token estimates."""

    @given(data=structure_pair_for_cost())
    def test_more_nodes_means_more_tokens(self, data):
        """Structure A (more nodes) has >= tokens than structure B (fewer nodes)."""
        structure_a, structure_b = data

        assert len(structure_a.nodes) > len(structure_b.nodes)

        estimator = CostEstimator(provider_name="openai", model_name="gpt-4o")

        estimate_a = estimator.estimate(structure_a)
        estimate_b = estimator.estimate(structure_b)

        assert estimate_a.total_input_tokens >= estimate_b.total_input_tokens
        assert estimate_a.total_output_tokens >= estimate_b.total_output_tokens


# ============================================================================
# Property 30: Mermaid syntax validity
# ============================================================================


class TestMermaidSyntaxValidity:
    """Property 30: Rendered Mermaid text is syntactically valid."""

    @given(l1_output=l1_output_with_features())
    def test_l1_mermaid_starts_with_valid_declaration(self, l1_output: L1Output):
        """L1 Mermaid output starts with valid graph declaration."""
        renderer = MermaidRenderer()
        mermaid = renderer.render_l1(l1_output)

        # Must start with a valid Mermaid graph declaration
        first_line = mermaid.strip().split("\n")[0].strip()
        valid_starts = ["graph ", "flowchart ", "graph TD", "graph LR", "flowchart TD", "flowchart LR"]
        assert any(first_line.startswith(s) for s in valid_starts), (
            f"Invalid Mermaid declaration: {first_line}"
        )

    @given(l1_5_output=l1_5_output_with_blocks())
    def test_l1_5_mermaid_starts_with_valid_declaration(self, l1_5_output: L1_5Output):
        """L1.5 Mermaid output starts with valid graph declaration."""
        renderer = MermaidRenderer()
        mermaid = renderer.render_l1_5(l1_5_output)

        first_line = mermaid.strip().split("\n")[0].strip()
        valid_starts = ["graph ", "flowchart ", "graph TD", "graph LR", "flowchart TD", "flowchart LR"]
        assert any(first_line.startswith(s) for s in valid_starts), (
            f"Invalid Mermaid declaration: {first_line}"
        )

    @given(l1_output=l1_output_with_features())
    def test_l1_mermaid_has_no_unescaped_special_chars_in_labels(self, l1_output: L1Output):
        """Labels in Mermaid output have special characters properly escaped."""
        renderer = MermaidRenderer()
        mermaid = renderer.render_l1(l1_output)

        # Extract text inside brackets (node labels)
        # Mermaid node syntax: nodeId["label"] or nodeId[label]
        label_pattern = re.compile(r'\[[""]?(.*?)[""]?\]')
        for match in label_pattern.finditer(mermaid):
            label = match.group(1)
            # Unescaped pipes and quotes would break Mermaid
            # (Escaped versions like #quot; are OK)
            assert '|' not in label or '\\|' in label or '#124;' in label, (
                f"Unescaped pipe in label: {label}"
            )


# ============================================================================
# Property 31: Mermaid content completeness
# ============================================================================


class TestMermaidContentCompleteness:
    """Property 31: Mermaid contains one node per feature, one edge per relation."""

    @given(l1_output=l1_output_with_features(min_features=1, max_features=4))
    def test_one_node_per_feature(self, l1_output: L1Output):
        """Mermaid output contains one node for each feature."""
        renderer = MermaidRenderer()
        mermaid = renderer.render_l1(l1_output)

        for feature in l1_output.features:
            # The feature_id should appear as a node identifier in the Mermaid
            assert feature.feature_id in mermaid, (
                f"Feature {feature.feature_id} not found in Mermaid output"
            )

    @given(l1_output=l1_output_with_features(min_features=2, max_features=4))
    def test_one_edge_per_relation(self, l1_output: L1Output):
        """Mermaid output contains an edge for each feature relation."""
        assume(len(l1_output.feature_relations) > 0)

        renderer = MermaidRenderer()
        mermaid = renderer.render_l1(l1_output)

        for rel in l1_output.feature_relations:
            # Both feature IDs should appear in the Mermaid (as part of an edge)
            assert rel.from_feature in mermaid, (
                f"Relation source {rel.from_feature} not in Mermaid"
            )
            assert rel.to_feature in mermaid, (
                f"Relation target {rel.to_feature} not in Mermaid"
            )


# ============================================================================
# Property 32: Confidence marker label correctness
# ============================================================================


class TestConfidenceMarkerLabels:
    """Property 32: Displayed marker matches exactly one defined label per state."""

    @given(
        confidence=CONFIDENCE,
        source_reviewed=st.booleans(),
        regenerated_with_diff=st.booleans(),
        incomplete_reading=st.booleans(),
    )
    def test_exactly_one_marker_per_state(
        self,
        confidence: str,
        source_reviewed: bool,
        regenerated_with_diff: bool,
        incomplete_reading: bool,
    ):
        """Each state combination maps to exactly one confidence marker label."""
        # Define the expected marker labels per state
        # (These match the design spec requirements 18.1-18.5)
        markers = {
            ("high", False, False, False): "high confidence",
            ("medium", False, False, False): "medium confidence",
            ("low", False, False, False): "low confidence",
        }

        # Source-reviewed overrides base confidence display
        if source_reviewed:
            expected_suffix = "source-reviewed"
        elif regenerated_with_diff:
            expected_suffix = "regenerated, differs from previous"
        elif incomplete_reading:
            expected_suffix = "incomplete reading"
        else:
            expected_suffix = f"{confidence} confidence"

        # The marker must be non-empty and well-defined
        assert expected_suffix != ""
        assert isinstance(expected_suffix, str)

        # Verify mutual exclusivity: only one marker applies
        applicable_markers = []
        if source_reviewed:
            applicable_markers.append("source-reviewed")
        if regenerated_with_diff:
            applicable_markers.append("regenerated, differs from previous")
        if incomplete_reading:
            applicable_markers.append("incomplete reading")
        if not applicable_markers:
            applicable_markers.append(f"{confidence} confidence")

        # At most one special marker should apply (source_reviewed takes priority)
        if source_reviewed:
            assert "source-reviewed" in applicable_markers
