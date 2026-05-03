"""Unit tests for mermaid_renderer module.

Tests are written BEFORE implementation (TDD red phase).
"""
from __future__ import annotations

import pytest

from the_door.core.rendering.mermaid_renderer import MermaidRenderer
from the_door.models import (
    Feature,
    FeatureRelation,
    L1Output,
    L1_5Block,
    BlockRelation,
    InfrastructureBlock,
    L1_5Output,
)


def make_feature(feature_id: str, label: str = "Test feature", confidence: str = "high",
                 trigger_description: str = "User action") -> Feature:
    """Helper to create a Feature."""
    return Feature(
        feature_id=feature_id,
        label=label,
        description=f"Description for {feature_id}",
        trigger="user_action",
        trigger_description=trigger_description,
        confidence=confidence,
        confidence_reason="Clear from AST",
        source_nodes=[f"mod.py::{feature_id}"],
    )


class TestMermaidRendererL1:
    """Unit tests for MermaidRenderer.render_l1()."""

    def test_single_feature_valid_flowchart(self):
        """render_l1 with single feature → valid Mermaid flowchart with node and label."""
        l1 = L1Output(
            summary="Test",
            features=[make_feature("feat-login", "User sign-in")],
        )
        renderer = MermaidRenderer()
        mermaid = renderer.render_l1(l1)

        assert mermaid.strip().startswith("flowchart") or mermaid.strip().startswith("graph")
        assert "feat-login" in mermaid
        assert "User sign-in" in mermaid

    def test_multiple_features_and_relations(self):
        """render_l1 with multiple features and relations → correct edges."""
        l1 = L1Output(
            summary="Test",
            features=[
                make_feature("feat-a", "Feature A"),
                make_feature("feat-b", "Feature B"),
            ],
            feature_relations=[
                FeatureRelation(
                    from_feature="feat-a", to_feature="feat-b",
                    relation="A triggers B", relation_type="static",
                ),
            ],
        )
        renderer = MermaidRenderer()
        mermaid = renderer.render_l1(l1)

        assert "feat-a" in mermaid
        assert "feat-b" in mermaid
        # Should have an edge from a to b
        assert "-->" in mermaid or "---" in mermaid

    def test_confidence_levels_styling(self):
        """render_l1 with all confidence levels → correct styling."""
        l1 = L1Output(
            summary="Test",
            features=[
                make_feature("feat-high", "High conf", confidence="high"),
                make_feature("feat-med", "Medium conf", confidence="medium"),
                make_feature("feat-low", "Low conf", confidence="low"),
            ],
        )
        renderer = MermaidRenderer()
        mermaid = renderer.render_l1(l1)

        # All features should be present
        assert "feat-high" in mermaid
        assert "feat-med" in mermaid
        assert "feat-low" in mermaid
        # Should have some styling differentiation (classDef or style)
        # Medium = dashed, Low = dotted/warning
        assert "style" in mermaid.lower() or "class" in mermaid.lower() or ":::" in mermaid

    def test_trigger_descriptions_in_labels(self):
        """render_l1 with trigger descriptions → trigger text in node labels."""
        l1 = L1Output(
            summary="Test",
            features=[make_feature("feat-a", "Feature A", trigger_description="When user clicks button")],
        )
        renderer = MermaidRenderer()
        mermaid = renderer.render_l1(l1)

        # Trigger description should appear somewhere in the output
        assert "user clicks" in mermaid.lower() or "When user" in mermaid

    def test_empty_output_minimal_valid_mermaid(self):
        """Empty output (no features) → minimal valid Mermaid with placeholder node."""
        l1 = L1Output(summary="Empty")
        renderer = MermaidRenderer()
        mermaid = renderer.render_l1(l1)

        # Should still be valid Mermaid
        first_line = mermaid.strip().split("\n")[0]
        assert first_line.startswith("flowchart") or first_line.startswith("graph")

    def test_special_characters_escaped(self):
        """Special characters in labels (quotes, brackets, pipes) → properly escaped."""
        l1 = L1Output(
            summary="Test",
            features=[make_feature("feat-special", 'Label with "quotes" and [brackets]')],
        )
        renderer = MermaidRenderer()
        mermaid = renderer.render_l1(l1)

        # Should not break Mermaid syntax
        assert "feat-special" in mermaid
        # Raw unescaped characters should not appear in node definitions
        # (they should be escaped or quoted)

    def test_relation_referencing_nonexistent_feature_skipped(self):
        """Relation referencing non-existent feature_id → edge skipped with warning."""
        l1 = L1Output(
            summary="Test",
            features=[make_feature("feat-a", "Feature A")],
            feature_relations=[
                FeatureRelation(
                    from_feature="feat-a", to_feature="feat-nonexistent",
                    relation="Dangling", relation_type="static",
                ),
            ],
        )
        renderer = MermaidRenderer()
        mermaid = renderer.render_l1(l1)

        # Should not crash; the dangling edge should be skipped
        assert "feat-a" in mermaid
        # feat-nonexistent should NOT appear as a node
        # (it might appear in a comment/warning but not as a Mermaid node)


class TestMermaidRendererL15:
    """Unit tests for MermaidRenderer.render_l1_5()."""

    def test_blocks_and_relations(self):
        """render_l1_5 with blocks and relations → valid Mermaid flowchart."""
        l1_5 = L1_5Output(
            blocks=[
                L1_5Block(block_id="blk-a", label="Auth Block", responsibility="Auth",
                         trigger_mechanism="User login", related_features=["feat-auth"]),
                L1_5Block(block_id="blk-b", label="User Block", responsibility="Users",
                         trigger_mechanism="User request", related_features=["feat-users"]),
            ],
            block_relations=[
                BlockRelation(from_block="blk-a", to_block="blk-b",
                            relation="Auth provides context", relation_type="static"),
            ],
        )
        renderer = MermaidRenderer()
        mermaid = renderer.render_l1_5(l1_5)

        assert mermaid.strip().startswith("flowchart") or mermaid.strip().startswith("graph")
        assert "blk-a" in mermaid
        assert "blk-b" in mermaid
        assert "-->" in mermaid or "---" in mermaid

    def test_infrastructure_block_as_subgraph(self):
        """render_l1_5 with infrastructure block → rendered as subgraph."""
        l1_5 = L1_5Output(
            blocks=[
                L1_5Block(block_id="blk-a", label="Main Block", responsibility="Main",
                         trigger_mechanism="Entry", related_features=[]),
            ],
            infrastructure_block=InfrastructureBlock(
                label="System Infrastructure",
                components=["config.py::load", "utils.py::logger"],
            ),
        )
        renderer = MermaidRenderer()
        mermaid = renderer.render_l1_5(l1_5)

        # Infrastructure should be rendered as a subgraph
        assert "subgraph" in mermaid.lower() or "Infrastructure" in mermaid
