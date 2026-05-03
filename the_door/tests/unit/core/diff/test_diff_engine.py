"""Unit tests for DiffEngine — L1 and L1.5 diff computation."""
from __future__ import annotations

import pytest

from the_door.core.diff.diff_engine import DiffEngine
from the_door.models import (
    BaselineInfo,
    BlockSummary,
    DiffError,
    FeatureSummary,
    RelationSummary,
    VersionSnapshot,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _snap(
    version_id: str = "snap-1",
    l1: dict[str, FeatureSummary] | None = None,
    l1_5: dict[str, BlockSummary] | None = None,
    relations: list[RelationSummary] | None = None,
    trigger: str = "commit",
    commit_hash: str | None = "abc1234",
    git_tags: list[str] | None = None,
    label: str | None = None,
) -> VersionSnapshot:
    return VersionSnapshot(
        version_id=version_id,
        timestamp="2024-01-15T10:00:00Z",
        trigger=trigger,
        l1_snapshot=l1 or {},
        l1_5_snapshot=l1_5 or {},
        feature_relations_snapshot=relations or [],
        commit_hash=commit_hash,
        git_tags=git_tags or [],
        label=label,
    )


def _feat(fid: str, label: str = "Label", desc: str = "Desc", conf: str = "high") -> FeatureSummary:
    return FeatureSummary(
        feature_id=fid, label=label, description=desc,
        source_node_count=3, confidence=conf,
    )


def _block(bid: str, label: str = "Block", resp: str = "Responsibility") -> BlockSummary:
    return BlockSummary(block_id=bid, label=label, responsibility=resp)


def _rel(frm: str, to: str, relation: str = "calls") -> RelationSummary:
    return RelationSummary(from_feature=frm, to_feature=to, relation=relation)


# ── L1 Diff Tests ────────────────────────────────────────────────────────


class TestL1DiffBasicClassification:
    """Test basic node classification: added, removed, unchanged, attribute_changed."""

    def setup_method(self):
        self.engine = DiffEngine()

    def test_feature_added(self):
        baseline = _snap(l1={})
        current = _snap(l1={"f1": _feat("f1", "New Feature", "New desc")})
        result = self.engine.compute_l1_diff(baseline, current)

        assert len(result.node_diffs) == 1
        nd = result.node_diffs[0]
        assert nd.node_id == "f1"
        assert nd.diff_state == "added"
        assert nd.current_label == "New Feature"
        assert nd.current_description == "New desc"
        assert nd.baseline_label is None
        assert nd.baseline_description is None

    def test_feature_removed(self):
        baseline = _snap(l1={"f1": _feat("f1", "Old Feature", "Old desc")})
        current = _snap(l1={})
        result = self.engine.compute_l1_diff(baseline, current)

        assert len(result.node_diffs) == 1
        nd = result.node_diffs[0]
        assert nd.node_id == "f1"
        assert nd.diff_state == "removed"
        assert nd.baseline_label == "Old Feature"
        assert nd.current_label is None

    def test_feature_unchanged(self):
        feat = _feat("f1", "Same", "Same desc")
        baseline = _snap(l1={"f1": feat})
        current = _snap(l1={"f1": feat})
        result = self.engine.compute_l1_diff(baseline, current)

        assert len(result.node_diffs) == 1
        nd = result.node_diffs[0]
        assert nd.diff_state == "unchanged"
        assert nd.current_label == "Same"
        assert nd.baseline_label == "Same"

    def test_feature_label_changed(self):
        baseline = _snap(l1={"f1": _feat("f1", "Old Label", "Same desc")})
        current = _snap(l1={"f1": _feat("f1", "New Label", "Same desc")})
        result = self.engine.compute_l1_diff(baseline, current)

        nd = result.node_diffs[0]
        assert nd.diff_state == "attribute_changed"
        assert nd.baseline_label == "Old Label"
        assert nd.current_label == "New Label"

    def test_feature_description_changed(self):
        baseline = _snap(l1={"f1": _feat("f1", "Same", "Old desc")})
        current = _snap(l1={"f1": _feat("f1", "Same", "New desc")})
        result = self.engine.compute_l1_diff(baseline, current)

        nd = result.node_diffs[0]
        assert nd.diff_state == "attribute_changed"

    def test_multiple_features_mixed(self):
        baseline = _snap(l1={
            "f1": _feat("f1", "Unchanged", "Same"),
            "f2": _feat("f2", "Removed", "Gone"),
            "f3": _feat("f3", "Old Label", "Same"),
        })
        current = _snap(l1={
            "f1": _feat("f1", "Unchanged", "Same"),
            "f3": _feat("f3", "New Label", "Same"),
            "f4": _feat("f4", "Added", "New"),
        })
        result = self.engine.compute_l1_diff(baseline, current)

        states = {nd.node_id: nd.diff_state for nd in result.node_diffs}
        assert states["f1"] == "unchanged"
        assert states["f2"] == "removed"
        assert states["f3"] == "attribute_changed"
        assert states["f4"] == "added"


class TestL1DiffEdges:
    """Test edge-level diff computation."""

    def setup_method(self):
        self.engine = DiffEngine()

    def test_edge_added(self):
        feat_a = _feat("f1", "A", "A desc")
        feat_b = _feat("f2", "B", "B desc")
        baseline = _snap(l1={"f1": feat_a, "f2": feat_b}, relations=[])
        current = _snap(
            l1={"f1": feat_a, "f2": feat_b},
            relations=[_rel("f1", "f2", "calls")],
        )
        result = self.engine.compute_l1_diff(baseline, current)

        assert len(result.edge_diffs) == 1
        ed = result.edge_diffs[0]
        assert ed.diff_state == "added"
        assert ed.from_node == "f1"
        assert ed.to_node == "f2"
        assert ed.current_relation == "calls"
        assert ed.baseline_relation is None

    def test_edge_removed(self):
        feat_a = _feat("f1", "A", "A desc")
        feat_b = _feat("f2", "B", "B desc")
        baseline = _snap(
            l1={"f1": feat_a, "f2": feat_b},
            relations=[_rel("f1", "f2", "calls")],
        )
        current = _snap(l1={"f1": feat_a, "f2": feat_b}, relations=[])
        result = self.engine.compute_l1_diff(baseline, current)

        assert len(result.edge_diffs) == 1
        ed = result.edge_diffs[0]
        assert ed.diff_state == "removed"
        assert ed.baseline_relation == "calls"
        assert ed.current_relation is None

    def test_edge_modified(self):
        feat_a = _feat("f1", "A", "A desc")
        feat_b = _feat("f2", "B", "B desc")
        baseline = _snap(
            l1={"f1": feat_a, "f2": feat_b},
            relations=[_rel("f1", "f2", "calls")],
        )
        current = _snap(
            l1={"f1": feat_a, "f2": feat_b},
            relations=[_rel("f1", "f2", "depends on")],
        )
        result = self.engine.compute_l1_diff(baseline, current)

        assert len(result.edge_diffs) == 1
        ed = result.edge_diffs[0]
        assert ed.diff_state == "modified"
        assert ed.baseline_relation == "calls"
        assert ed.current_relation == "depends on"

    def test_unchanged_edge_not_in_diffs(self):
        feat_a = _feat("f1", "A", "A desc")
        feat_b = _feat("f2", "B", "B desc")
        rel = _rel("f1", "f2", "calls")
        baseline = _snap(l1={"f1": feat_a, "f2": feat_b}, relations=[rel])
        current = _snap(l1={"f1": feat_a, "f2": feat_b}, relations=[rel])
        result = self.engine.compute_l1_diff(baseline, current)

        assert len(result.edge_diffs) == 0


class TestL1DiffDependencyChanged:
    """Test dependency_changed upgrade and priority rules."""

    def setup_method(self):
        self.engine = DiffEngine()

    def test_unchanged_upgraded_to_dependency_changed(self):
        """Node with unchanged attributes but changed edges → dependency_changed."""
        feat_a = _feat("f1", "A", "A desc")
        feat_b = _feat("f2", "B", "B desc")
        baseline = _snap(l1={"f1": feat_a, "f2": feat_b}, relations=[])
        current = _snap(
            l1={"f1": feat_a, "f2": feat_b},
            relations=[_rel("f1", "f2", "calls")],
        )
        result = self.engine.compute_l1_diff(baseline, current)

        states = {nd.node_id: nd.diff_state for nd in result.node_diffs}
        assert states["f1"] == "dependency_changed"
        assert states["f2"] == "dependency_changed"

    def test_dependency_changed_no_secondary_when_attrs_same(self):
        """When only edges changed (attrs same), secondary_changes should be None."""
        feat_a = _feat("f1", "A", "A desc")
        feat_b = _feat("f2", "B", "B desc")
        baseline = _snap(l1={"f1": feat_a, "f2": feat_b}, relations=[])
        current = _snap(
            l1={"f1": feat_a, "f2": feat_b},
            relations=[_rel("f1", "f2", "calls")],
        )
        result = self.engine.compute_l1_diff(baseline, current)

        for nd in result.node_diffs:
            assert nd.secondary_changes is None

    def test_attribute_changed_upgraded_to_dependency_changed(self):
        """Node with both attribute and edge changes → dependency_changed with secondary_changes."""
        baseline = _snap(
            l1={"f1": _feat("f1", "Old", "Old desc"), "f2": _feat("f2", "B", "B desc")},
            relations=[],
        )
        current = _snap(
            l1={"f1": _feat("f1", "New", "New desc"), "f2": _feat("f2", "B", "B desc")},
            relations=[_rel("f1", "f2", "calls")],
        )
        result = self.engine.compute_l1_diff(baseline, current)

        f1_diff = next(nd for nd in result.node_diffs if nd.node_id == "f1")
        assert f1_diff.diff_state == "dependency_changed"
        assert f1_diff.secondary_changes is not None
        assert "attribute_changed" in f1_diff.secondary_changes
        attr_info = f1_diff.secondary_changes["attribute_changed"]
        assert attr_info["old_label"] == "Old"
        assert attr_info["new_label"] == "New"
        assert attr_info["old_description"] == "Old desc"
        assert attr_info["new_description"] == "New desc"

    def test_added_not_upgraded(self):
        """Added nodes should never be upgraded to dependency_changed."""
        baseline = _snap(
            l1={"f1": _feat("f1", "A", "A desc")},
            relations=[],
        )
        current = _snap(
            l1={"f1": _feat("f1", "A", "A desc"), "f2": _feat("f2", "B", "B desc")},
            relations=[_rel("f1", "f2", "calls")],
        )
        result = self.engine.compute_l1_diff(baseline, current)

        f2_diff = next(nd for nd in result.node_diffs if nd.node_id == "f2")
        assert f2_diff.diff_state == "added"

    def test_removed_not_upgraded(self):
        """Removed nodes should never be upgraded to dependency_changed."""
        baseline = _snap(
            l1={"f1": _feat("f1", "A", "A desc"), "f2": _feat("f2", "B", "B desc")},
            relations=[_rel("f1", "f2", "calls")],
        )
        current = _snap(
            l1={"f1": _feat("f1", "A", "A desc")},
            relations=[],
        )
        result = self.engine.compute_l1_diff(baseline, current)

        f2_diff = next(nd for nd in result.node_diffs if nd.node_id == "f2")
        assert f2_diff.diff_state == "removed"


class TestL1DiffSummary:
    """Test DiffSummary count computation."""

    def setup_method(self):
        self.engine = DiffEngine()

    def test_summary_counts(self):
        baseline = _snap(l1={
            "f1": _feat("f1", "Same", "Same"),
            "f2": _feat("f2", "Removed", "Gone"),
            "f3": _feat("f3", "Old", "Old"),
        })
        current = _snap(l1={
            "f1": _feat("f1", "Same", "Same"),
            "f3": _feat("f3", "New", "New"),
            "f4": _feat("f4", "Added", "New"),
        })
        result = self.engine.compute_l1_diff(baseline, current)

        assert result.summary.added_count == 1
        assert result.summary.removed_count == 1
        assert result.summary.attribute_changed_count == 1
        assert result.summary.total_changed_count == 3

    def test_count_consistency(self):
        """added + removed + dep_changed + attr_changed == total_changed."""
        baseline = _snap(l1={
            "f1": _feat("f1", "A", "A"),
            "f2": _feat("f2", "B", "B"),
        })
        current = _snap(
            l1={
                "f1": _feat("f1", "A", "A"),
                "f2": _feat("f2", "B", "B"),
                "f3": _feat("f3", "C", "C"),
            },
            relations=[_rel("f1", "f2", "calls")],
        )
        result = self.engine.compute_l1_diff(baseline, current)

        s = result.summary
        assert s.added_count + s.removed_count + s.dependency_changed_count + s.attribute_changed_count == s.total_changed_count

    def test_empty_snapshots_zero_counts(self):
        baseline = _snap(l1={})
        current = _snap(l1={})
        result = self.engine.compute_l1_diff(baseline, current)

        assert result.summary.total_changed_count == 0
        assert len(result.node_diffs) == 0


class TestL1DiffBaselineInfo:
    """Test BaselineInfo construction."""

    def setup_method(self):
        self.engine = DiffEngine()

    def test_baseline_info_from_snapshot(self):
        baseline = _snap(
            version_id="v1", trigger="commit",
            commit_hash="abc123", git_tags=["v1.0"],
        )
        current = _snap(version_id="v2", trigger="manual", label="Sprint 12")
        result = self.engine.compute_l1_diff(baseline, current)

        assert result.baseline_info.version_id == "v1"
        assert result.baseline_info.trigger == "commit"
        assert result.baseline_info.commit_hash == "abc123"
        assert result.baseline_info.git_tags == ["v1.0"]
        assert result.current_info.version_id == "v2"
        assert result.current_info.label == "Sprint 12"

    def test_layer_is_l1(self):
        result = self.engine.compute_l1_diff(_snap(l1={}), _snap(l1={}))
        assert result.layer == "l1"


# ── L1.5 Diff Tests ──────────────────────────────────────────────────────


class TestL1_5DiffBasic:
    """Test L1.5 block-level diff computation."""

    def setup_method(self):
        self.engine = DiffEngine()

    def test_block_added(self):
        baseline = _snap(l1_5={"b1": _block("b1")})
        current = _snap(l1_5={"b1": _block("b1"), "b2": _block("b2", "New Block", "New resp")})
        result = self.engine.compute_l1_5_diff(baseline, current)

        states = {nd.node_id: nd.diff_state for nd in result.node_diffs}
        assert states["b2"] == "added"
        assert states["b1"] == "unchanged"

    def test_block_removed(self):
        baseline = _snap(l1_5={"b1": _block("b1"), "b2": _block("b2")})
        current = _snap(l1_5={"b1": _block("b1")})
        result = self.engine.compute_l1_5_diff(baseline, current)

        states = {nd.node_id: nd.diff_state for nd in result.node_diffs}
        assert states["b2"] == "removed"

    def test_block_responsibility_changed(self):
        baseline = _snap(l1_5={"b1": _block("b1", "Block", "Old resp")})
        current = _snap(l1_5={"b1": _block("b1", "Block", "New resp")})
        result = self.engine.compute_l1_5_diff(baseline, current)

        nd = result.node_diffs[0]
        assert nd.diff_state == "attribute_changed"
        assert nd.baseline_description == "Old resp"
        assert nd.current_description == "New resp"

    def test_block_label_changed(self):
        baseline = _snap(l1_5={"b1": _block("b1", "Old Label", "Same")})
        current = _snap(l1_5={"b1": _block("b1", "New Label", "Same")})
        result = self.engine.compute_l1_5_diff(baseline, current)

        nd = result.node_diffs[0]
        assert nd.diff_state == "attribute_changed"

    def test_block_unchanged(self):
        block = _block("b1", "Same", "Same resp")
        baseline = _snap(l1_5={"b1": block})
        current = _snap(l1_5={"b1": block})
        result = self.engine.compute_l1_5_diff(baseline, current)

        nd = result.node_diffs[0]
        assert nd.diff_state == "unchanged"

    def test_layer_is_l1_5(self):
        baseline = _snap(l1_5={"b1": _block("b1")})
        current = _snap(l1_5={"b1": _block("b1")})
        result = self.engine.compute_l1_5_diff(baseline, current)
        assert result.layer == "l1.5"

    def test_no_edge_diffs_for_l1_5(self):
        """L1.5 doesn't have feature_relations, so edge_diffs should be empty."""
        baseline = _snap(l1_5={"b1": _block("b1")})
        current = _snap(l1_5={"b1": _block("b1"), "b2": _block("b2")})
        result = self.engine.compute_l1_5_diff(baseline, current)
        assert result.edge_diffs == []


class TestL1_5DiffErrors:
    """Test error handling for L1.5 diffs."""

    def setup_method(self):
        self.engine = DiffEngine()

    def test_missing_baseline_l1_5_raises(self):
        baseline = _snap(l1_5={})
        current = _snap(l1_5={"b1": _block("b1")})
        with pytest.raises(DiffError, match="Baseline.*L1.5"):
            self.engine.compute_l1_5_diff(baseline, current)

    def test_missing_current_l1_5_raises(self):
        baseline = _snap(l1_5={"b1": _block("b1")})
        current = _snap(l1_5={})
        with pytest.raises(DiffError, match="Current.*L1.5"):
            self.engine.compute_l1_5_diff(baseline, current)


# ── Symmetry Tests ───────────────────────────────────────────────────────


class TestDiffSymmetry:
    """Test that diff(A,B) and diff(B,A) produce symmetric results."""

    def setup_method(self):
        self.engine = DiffEngine()

    def test_added_becomes_removed_in_reverse(self):
        baseline = _snap(l1={})
        current = _snap(l1={"f1": _feat("f1")})

        forward = self.engine.compute_l1_diff(baseline, current)
        reverse = self.engine.compute_l1_diff(current, baseline)

        fwd_state = {nd.node_id: nd.diff_state for nd in forward.node_diffs}
        rev_state = {nd.node_id: nd.diff_state for nd in reverse.node_diffs}

        assert fwd_state["f1"] == "added"
        assert rev_state["f1"] == "removed"

    def test_attribute_changed_same_in_both_directions(self):
        baseline = _snap(l1={"f1": _feat("f1", "Old", "Old")})
        current = _snap(l1={"f1": _feat("f1", "New", "New")})

        forward = self.engine.compute_l1_diff(baseline, current)
        reverse = self.engine.compute_l1_diff(current, baseline)

        fwd_state = {nd.node_id: nd.diff_state for nd in forward.node_diffs}
        rev_state = {nd.node_id: nd.diff_state for nd in reverse.node_diffs}

        assert fwd_state["f1"] == "attribute_changed"
        assert rev_state["f1"] == "attribute_changed"


# ── Self-diff Idempotency ────────────────────────────────────────────────


class TestSelfDiffIdempotency:
    """Test that diff(S, S) produces all unchanged."""

    def setup_method(self):
        self.engine = DiffEngine()

    def test_self_diff_all_unchanged(self):
        snap = _snap(
            l1={
                "f1": _feat("f1", "A", "A desc"),
                "f2": _feat("f2", "B", "B desc"),
            },
            relations=[_rel("f1", "f2", "calls")],
        )
        result = self.engine.compute_l1_diff(snap, snap)

        for nd in result.node_diffs:
            assert nd.diff_state == "unchanged"
        assert result.summary.total_changed_count == 0
        assert result.edge_diffs == []
