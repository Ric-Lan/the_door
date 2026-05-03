"""Unit tests for DiffRenderer."""
from __future__ import annotations

import pytest

from the_door.core.diff.diff_renderer import DiffRenderer
from the_door.models import (
    BaselineInfo,
    DiffResult,
    DiffSummary,
    EdgeDiff,
    NodeDiff,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_baseline_info(**overrides) -> BaselineInfo:
    defaults = {
        "version_id": "base-001",
        "timestamp": "2024-01-01T00:00:00",
        "trigger": "commit",
    }
    defaults.update(overrides)
    return BaselineInfo(**defaults)


def _make_diff_result(
    node_diffs: list[NodeDiff] | None = None,
    edge_diffs: list[EdgeDiff] | None = None,
    summary: DiffSummary | None = None,
    baseline_info: BaselineInfo | None = None,
    current_info: BaselineInfo | None = None,
    layer: str = "l1",
) -> DiffResult:
    return DiffResult(
        baseline_info=baseline_info or _make_baseline_info(
            version_id="base-001",
            commit_hash="abc1234def",
            git_tags=["v1.0.0"],
        ),
        current_info=current_info or _make_baseline_info(
            version_id="curr-001",
            commit_hash="def5678abc",
            git_tags=["v2.0.0"],
        ),
        node_diffs=node_diffs or [],
        edge_diffs=edge_diffs or [],
        summary=summary or DiffSummary(),
        layer=layer,
    )


# ---------------------------------------------------------------------------
# Test: All 5 classDef definitions present in output
# ---------------------------------------------------------------------------

class TestClassDefDefinitions:
    """All 5 diff classDef definitions must appear in rendered output."""

    def test_all_classdefs_present_in_l1(self):
        renderer = DiffRenderer()
        result = _make_diff_result()
        output = renderer.render_l1_diff(result)

        assert "classDef diff_added" in output
        assert "classDef diff_removed" in output
        assert "classDef diff_dep_changed" in output
        assert "classDef diff_attr_changed" in output
        assert "classDef unchanged" in output

    def test_all_classdefs_present_in_l1_5(self):
        renderer = DiffRenderer()
        result = _make_diff_result(layer="l1.5")
        output = renderer.render_l1_5_diff(result)

        assert "classDef diff_added" in output
        assert "classDef diff_removed" in output
        assert "classDef diff_dep_changed" in output
        assert "classDef diff_attr_changed" in output
        assert "classDef unchanged" in output

    def test_classdef_styles_match_spec(self):
        renderer = DiffRenderer()
        result = _make_diff_result()
        output = renderer.render_l1_diff(result)

        assert "fill:#d4edda,stroke:#28a745,stroke-width:2" in output
        assert "fill:#f8d7da,stroke:#dc3545,stroke-width:2" in output
        assert "fill:#f5c6a0,stroke:#e67e22,stroke-width:2" in output
        assert "fill:#ffe0cc,stroke:#fd7e14,stroke-width:2" in output
        assert "fill:#f8f9fa,stroke:#dee2e6,color:#6c757d,stroke-dasharray:2 2" in output


# ---------------------------------------------------------------------------
# Test: Correct diff symbols in node labels
# ---------------------------------------------------------------------------

class TestDiffSymbols:
    """Changed nodes must have the correct diff symbol prefix."""

    def test_added_node_has_plus_symbol(self):
        renderer = DiffRenderer()
        node = NodeDiff(
            node_id="feat_new",
            diff_state="added",
            current_label="New Feature",
            current_confidence="high",
        )
        result = _make_diff_result(
            node_diffs=[node],
            summary=DiffSummary(added_count=1, total_changed_count=1),
        )
        output = renderer.render_l1_diff(result)
        # Should contain + symbol in the label
        assert "+ New Feature" in output

    def test_removed_node_has_minus_symbol(self):
        renderer = DiffRenderer()
        node = NodeDiff(
            node_id="feat_old",
            diff_state="removed",
            baseline_label="Old Feature",
        )
        result = _make_diff_result(
            node_diffs=[node],
            summary=DiffSummary(removed_count=1, total_changed_count=1),
        )
        output = renderer.render_l1_diff(result)
        # Should contain − (minus sign U+2212)
        assert "\u2212 Old Feature" in output

    def test_dependency_changed_node_has_neq_symbol(self):
        renderer = DiffRenderer()
        node = NodeDiff(
            node_id="feat_dep",
            diff_state="dependency_changed",
            current_label="Dep Feature",
            current_confidence="medium",
        )
        result = _make_diff_result(
            node_diffs=[node],
            summary=DiffSummary(dependency_changed_count=1, total_changed_count=1),
        )
        output = renderer.render_l1_diff(result)
        # Should contain ≠ (not equal sign U+2260)
        assert "\u2260 Dep Feature" in output

    def test_attribute_changed_node_has_tilde_symbol(self):
        renderer = DiffRenderer()
        node = NodeDiff(
            node_id="feat_attr",
            diff_state="attribute_changed",
            current_label="Attr Feature",
            current_confidence="low",
        )
        result = _make_diff_result(
            node_diffs=[node],
            summary=DiffSummary(attribute_changed_count=1, total_changed_count=1),
        )
        output = renderer.render_l1_diff(result)
        assert "~ Attr Feature" in output

    def test_unchanged_node_has_no_symbol(self):
        renderer = DiffRenderer()
        node = NodeDiff(
            node_id="feat_same",
            diff_state="unchanged",
            current_label="Same Feature",
            current_confidence="high",
        )
        result = _make_diff_result(node_diffs=[node])
        output = renderer.render_l1_diff(result)
        # Label should not have any diff symbol prefix
        # It should just be the confidence icon + label
        assert 'feat_same["' in output
        # No diff symbol between icon and label
        assert "+ Same Feature" not in output
        assert "\u2212 Same Feature" not in output
        assert "\u2260 Same Feature" not in output
        assert "~ Same Feature" not in output


# ---------------------------------------------------------------------------
# Test: Summary panel format (3 trigger types)
# ---------------------------------------------------------------------------

class TestSummaryPanel:
    """Summary panel must format correctly for all trigger types."""

    def test_git_ref_baseline_format(self):
        renderer = DiffRenderer()
        result = _make_diff_result(
            baseline_info=_make_baseline_info(
                commit_hash="abc1234def5678",
                git_tags=["v1.2.0"],
            ),
            current_info=_make_baseline_info(
                version_id="curr-001",
                commit_hash="def5678abc1234",
                git_tags=["v1.3.0"],
            ),
            summary=DiffSummary(added_count=2, total_changed_count=2),
            node_diffs=[
                NodeDiff(node_id="f1", diff_state="added", current_label="F1"),
                NodeDiff(node_id="f2", diff_state="added", current_label="F2"),
            ],
        )
        output = renderer.render_l1_diff(result)
        assert "v1.2.0 (abc1234)" in output
        assert "v1.3.0 (def5678)" in output
        assert "版本比較" in output

    def test_date_baseline_format(self):
        renderer = DiffRenderer()
        result = _make_diff_result(
            baseline_info=_make_baseline_info(
                resolved_from="2024-01-15",
            ),
        )
        output = renderer.render_l1_diff(result)
        assert "2024-01-15 的快照" in output

    def test_manual_label_baseline_format(self):
        renderer = DiffRenderer()
        result = _make_diff_result(
            baseline_info=_make_baseline_info(
                label="Sprint 12 結束快照",
            ),
        )
        output = renderer.render_l1_diff(result)
        assert "Sprint 12 結束快照" in output

    def test_summary_counts_format(self):
        renderer = DiffRenderer()
        result = _make_diff_result(
            summary=DiffSummary(
                added_count=2,
                removed_count=1,
                dependency_changed_count=1,
                attribute_changed_count=2,
                total_changed_count=6,
            ),
            node_diffs=[
                NodeDiff(node_id=f"f{i}", diff_state="added", current_label=f"F{i}")
                for i in range(6)
            ],
        )
        output = renderer.render_l1_diff(result)
        assert "新增 2 個功能" in output
        assert "移除 1 個功能" in output
        assert "修改 3 個功能" in output
        assert "1 個依賴關係變更" in output
        assert "2 個屬性變更" in output

    def test_summary_uses_functional_language(self):
        """Summary must use 功能, not 節點 or 模組."""
        renderer = DiffRenderer()
        result = _make_diff_result(
            summary=DiffSummary(added_count=1, total_changed_count=1),
            node_diffs=[
                NodeDiff(node_id="f1", diff_state="added", current_label="F1"),
            ],
        )
        output = renderer.render_l1_diff(result)
        assert "功能" in output
        assert "節點" not in output
        assert "模組" not in output

    def test_summary_as_mermaid_comments(self):
        """Summary lines must start with %%."""
        renderer = DiffRenderer()
        result = _make_diff_result(
            summary=DiffSummary(added_count=1, total_changed_count=1),
            node_diffs=[
                NodeDiff(node_id="f1", diff_state="added", current_label="F1"),
            ],
        )
        output = renderer.render_l1_diff(result)
        for line in output.split("\n"):
            if "版本比較" in line or "功能" in line or "無變更" in line:
                assert line.startswith("%%")


# ---------------------------------------------------------------------------
# Test: No-change message when zero changes
# ---------------------------------------------------------------------------

class TestNoChangeMessage:
    """When total_changed_count is 0, summary should show 無變更."""

    def test_no_changes_message(self):
        renderer = DiffRenderer()
        result = _make_diff_result(
            summary=DiffSummary(total_changed_count=0),
            node_diffs=[
                NodeDiff(
                    node_id="f1",
                    diff_state="unchanged",
                    current_label="Feature 1",
                    current_confidence="high",
                ),
            ],
        )
        output = renderer.render_l1_diff(result)
        assert "無變更" in output

    def test_no_changes_omits_count_lines(self):
        renderer = DiffRenderer()
        result = _make_diff_result(
            summary=DiffSummary(total_changed_count=0),
        )
        output = renderer.render_l1_diff(result)
        assert "新增" not in output
        assert "移除" not in output
        assert "修改" not in output


# ---------------------------------------------------------------------------
# Test: Confidence icon + diff symbol coexistence
# ---------------------------------------------------------------------------

class TestConfidenceAndDiffCoexistence:
    """Labels should show both confidence icon and diff symbol."""

    def test_high_confidence_added_node(self):
        renderer = DiffRenderer()
        node = NodeDiff(
            node_id="feat_new",
            diff_state="added",
            current_label="New Feature",
            current_confidence="high",
        )
        result = _make_diff_result(
            node_diffs=[node],
            summary=DiffSummary(added_count=1, total_changed_count=1),
        )
        output = renderer.render_l1_diff(result)
        # Should have: ✓ + New Feature
        assert "\u2713 + New Feature" in output

    def test_medium_confidence_dependency_changed(self):
        renderer = DiffRenderer()
        node = NodeDiff(
            node_id="feat_dep",
            diff_state="dependency_changed",
            current_label="Dep Feature",
            current_confidence="medium",
        )
        result = _make_diff_result(
            node_diffs=[node],
            summary=DiffSummary(dependency_changed_count=1, total_changed_count=1),
        )
        output = renderer.render_l1_diff(result)
        # Should have: ? ≠ Dep Feature
        assert "? \u2260 Dep Feature" in output

    def test_low_confidence_attribute_changed(self):
        renderer = DiffRenderer()
        node = NodeDiff(
            node_id="feat_attr",
            diff_state="attribute_changed",
            current_label="Attr Feature",
            current_confidence="low",
        )
        result = _make_diff_result(
            node_diffs=[node],
            summary=DiffSummary(attribute_changed_count=1, total_changed_count=1),
        )
        output = renderer.render_l1_diff(result)
        # Should have: ⚠ ~ Attr Feature
        assert "\u26a0 ~ Attr Feature" in output

    def test_removed_node_no_confidence_icon(self):
        """Removed nodes should not have a confidence icon."""
        renderer = DiffRenderer()
        node = NodeDiff(
            node_id="feat_old",
            diff_state="removed",
            baseline_label="Old Feature",
        )
        result = _make_diff_result(
            node_diffs=[node],
            summary=DiffSummary(removed_count=1, total_changed_count=1),
        )
        output = renderer.render_l1_diff(result)
        # Should have just: − Old Feature (no confidence icon)
        assert '"\u2212 Old Feature"' in output

    def test_unchanged_node_has_confidence_icon_only(self):
        """Unchanged nodes should have confidence icon but no diff symbol."""
        renderer = DiffRenderer()
        node = NodeDiff(
            node_id="feat_same",
            diff_state="unchanged",
            current_label="Same Feature",
            current_confidence="high",
        )
        result = _make_diff_result(node_diffs=[node])
        output = renderer.render_l1_diff(result)
        # Should have: ✓ Same Feature (no diff symbol)
        assert "\u2713 Same Feature" in output


# ---------------------------------------------------------------------------
# Test: Unchanged nodes get unchanged classDef
# ---------------------------------------------------------------------------

class TestUnchangedClassDef:
    """Unchanged nodes must be assigned the 'unchanged' classDef."""

    def test_unchanged_node_classdef(self):
        renderer = DiffRenderer()
        node = NodeDiff(
            node_id="feat_same",
            diff_state="unchanged",
            current_label="Same Feature",
            current_confidence="high",
        )
        result = _make_diff_result(node_diffs=[node])
        output = renderer.render_l1_diff(result)
        assert "class feat_same unchanged" in output

    def test_added_node_classdef(self):
        renderer = DiffRenderer()
        node = NodeDiff(
            node_id="feat_new",
            diff_state="added",
            current_label="New Feature",
        )
        result = _make_diff_result(
            node_diffs=[node],
            summary=DiffSummary(added_count=1, total_changed_count=1),
        )
        output = renderer.render_l1_diff(result)
        assert "class feat_new diff_added" in output

    def test_removed_node_classdef(self):
        renderer = DiffRenderer()
        node = NodeDiff(
            node_id="feat_old",
            diff_state="removed",
            baseline_label="Old Feature",
        )
        result = _make_diff_result(
            node_diffs=[node],
            summary=DiffSummary(removed_count=1, total_changed_count=1),
        )
        output = renderer.render_l1_diff(result)
        assert "class feat_old diff_removed" in output

    def test_dep_changed_node_classdef(self):
        renderer = DiffRenderer()
        node = NodeDiff(
            node_id="feat_dep",
            diff_state="dependency_changed",
            current_label="Dep Feature",
        )
        result = _make_diff_result(
            node_diffs=[node],
            summary=DiffSummary(dependency_changed_count=1, total_changed_count=1),
        )
        output = renderer.render_l1_diff(result)
        assert "class feat_dep diff_dep_changed" in output

    def test_attr_changed_node_classdef(self):
        renderer = DiffRenderer()
        node = NodeDiff(
            node_id="feat_attr",
            diff_state="attribute_changed",
            current_label="Attr Feature",
        )
        result = _make_diff_result(
            node_diffs=[node],
            summary=DiffSummary(attribute_changed_count=1, total_changed_count=1),
        )
        output = renderer.render_l1_diff(result)
        assert "class feat_attr diff_attr_changed" in output


# ---------------------------------------------------------------------------
# Test: Edge rendering
# ---------------------------------------------------------------------------

class TestEdgeRendering:
    """Edge diffs should use correct Mermaid syntax and linkStyle."""

    def test_added_edge_dashed_green(self):
        renderer = DiffRenderer()
        edge = EdgeDiff(
            from_node="f1", to_node="f2", diff_state="added",
        )
        result = _make_diff_result(
            edge_diffs=[edge],
            node_diffs=[
                NodeDiff(node_id="f1", diff_state="unchanged", current_label="F1"),
                NodeDiff(node_id="f2", diff_state="unchanged", current_label="F2"),
            ],
        )
        output = renderer.render_l1_diff(result)
        assert "f1 -.->" in output
        assert "stroke:#28a745" in output

    def test_removed_edge_dashed_red(self):
        renderer = DiffRenderer()
        edge = EdgeDiff(
            from_node="f1", to_node="f2", diff_state="removed",
        )
        result = _make_diff_result(
            edge_diffs=[edge],
            node_diffs=[
                NodeDiff(node_id="f1", diff_state="unchanged", current_label="F1"),
                NodeDiff(node_id="f2", diff_state="unchanged", current_label="F2"),
            ],
        )
        output = renderer.render_l1_diff(result)
        assert "f1 -.-x" in output
        assert "stroke:#dc3545" in output

    def test_modified_edge_solid_orange(self):
        renderer = DiffRenderer()
        edge = EdgeDiff(
            from_node="f1", to_node="f2", diff_state="modified",
        )
        result = _make_diff_result(
            edge_diffs=[edge],
            node_diffs=[
                NodeDiff(node_id="f1", diff_state="unchanged", current_label="F1"),
                NodeDiff(node_id="f2", diff_state="unchanged", current_label="F2"),
            ],
        )
        output = renderer.render_l1_diff(result)
        assert "f1 -->" in output
        assert "stroke:#fd7e14" in output


# ---------------------------------------------------------------------------
# Test: L1.5 rendering
# ---------------------------------------------------------------------------

class TestL15Rendering:
    """L1.5 rendering should work the same as L1 for nodes."""

    def test_l1_5_nodes_rendered(self):
        renderer = DiffRenderer()
        nodes = [
            NodeDiff(
                node_id="block_a",
                diff_state="added",
                current_label="Block A",
                current_confidence="high",
            ),
            NodeDiff(
                node_id="block_b",
                diff_state="unchanged",
                current_label="Block B",
                current_confidence="medium",
            ),
        ]
        result = _make_diff_result(
            node_diffs=nodes,
            summary=DiffSummary(added_count=1, total_changed_count=1),
            layer="l1.5",
        )
        output = renderer.render_l1_5_diff(result)
        assert "block_a" in output
        assert "block_b" in output
        assert "class block_a diff_added" in output
        assert "class block_b unchanged" in output


# ---------------------------------------------------------------------------
# Test: Summary panel omits zero-count categories
# ---------------------------------------------------------------------------

class TestSummaryOmitsZero:
    """Categories with zero count should be omitted from summary."""

    def test_only_added(self):
        renderer = DiffRenderer()
        result = _make_diff_result(
            summary=DiffSummary(added_count=3, total_changed_count=3),
            node_diffs=[
                NodeDiff(node_id=f"f{i}", diff_state="added", current_label=f"F{i}")
                for i in range(3)
            ],
        )
        output = renderer.render_l1_diff(result)
        assert "新增 3 個功能" in output
        assert "移除" not in output
        assert "修改" not in output

    def test_only_removed(self):
        renderer = DiffRenderer()
        result = _make_diff_result(
            summary=DiffSummary(removed_count=2, total_changed_count=2),
            node_diffs=[
                NodeDiff(node_id=f"f{i}", diff_state="removed", baseline_label=f"F{i}")
                for i in range(2)
            ],
        )
        output = renderer.render_l1_diff(result)
        assert "移除 2 個功能" in output
        assert "新增" not in output
        assert "修改" not in output

    def test_only_attribute_changed(self):
        renderer = DiffRenderer()
        result = _make_diff_result(
            summary=DiffSummary(attribute_changed_count=1, total_changed_count=1),
            node_diffs=[
                NodeDiff(node_id="f1", diff_state="attribute_changed", current_label="F1"),
            ],
        )
        output = renderer.render_l1_diff(result)
        assert "修改 1 個功能" in output
        assert "1 個屬性變更" in output
        assert "新增" not in output
        assert "移除" not in output


# ---------------------------------------------------------------------------
# Test: _format_baseline_label edge cases
# ---------------------------------------------------------------------------

class TestFormatBaselineLabel:
    """Test _format_baseline_label with various inputs."""

    def test_fallback_to_version_id(self):
        renderer = DiffRenderer()
        info = _make_baseline_info(version_id="some-uuid-123")
        label = renderer._format_baseline_label(info)
        assert label == "some-uuid-123"

    def test_commit_hash_only_abbreviated(self):
        renderer = DiffRenderer()
        info = _make_baseline_info(commit_hash="abcdef1234567890")
        label = renderer._format_baseline_label(info)
        assert label == "abcdef1"

    def test_git_tag_with_hash(self):
        renderer = DiffRenderer()
        info = _make_baseline_info(
            commit_hash="abcdef1234567890",
            git_tags=["v2.0.0", "release-2"],
        )
        label = renderer._format_baseline_label(info)
        assert label == "v2.0.0 (abcdef1)"

    def test_date_resolved_from(self):
        renderer = DiffRenderer()
        info = _make_baseline_info(resolved_from="2024-06-15")
        label = renderer._format_baseline_label(info)
        assert label == "2024-06-15 的快照"

    def test_manual_label(self):
        renderer = DiffRenderer()
        info = _make_baseline_info(label="Sprint 12 結束快照")
        label = renderer._format_baseline_label(info)
        assert label == "Sprint 12 結束快照"


# ---------------------------------------------------------------------------
# Test: Marker context override
# ---------------------------------------------------------------------------

class TestMarkerContext:
    """marker_context should override confidence from NodeDiff."""

    def test_marker_context_overrides_confidence(self):
        renderer = DiffRenderer()
        node = NodeDiff(
            node_id="feat_a",
            diff_state="added",
            current_label="Feature A",
            current_confidence="low",
        )
        # marker_context says confidence is "high"
        marker_ctx = {"feat_a": {"confidence": "high"}}
        result = _make_diff_result(
            node_diffs=[node],
            summary=DiffSummary(added_count=1, total_changed_count=1),
        )
        output = renderer.render_l1_diff(result, marker_context=marker_ctx)
        # Should use high confidence icon ✓ instead of low ⚠
        assert "\u2713 + Feature A" in output

    def test_no_marker_context_uses_node_confidence(self):
        renderer = DiffRenderer()
        node = NodeDiff(
            node_id="feat_a",
            diff_state="added",
            current_label="Feature A",
            current_confidence="low",
        )
        result = _make_diff_result(
            node_diffs=[node],
            summary=DiffSummary(added_count=1, total_changed_count=1),
        )
        output = renderer.render_l1_diff(result)
        # Should use low confidence icon ⚠
        assert "\u26a0 + Feature A" in output
