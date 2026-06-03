"""Diff-engine data models (and diff exception)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .snapshot import BaselineInfo


@dataclass(frozen=True)
class NodeDiff:
    """A single node's diff classification."""

    node_id: str  # feature_id or block_id
    diff_state: str  # "added" | "removed" | "attribute_changed" | "dependency_changed" | "unchanged"
    current_label: str | None = None
    current_description: str | None = None
    baseline_label: str | None = None
    baseline_description: str | None = None
    current_confidence: str | None = None
    secondary_changes: dict | None = None


@dataclass(frozen=True)
class EdgeDiff:
    """A single edge's diff classification."""

    from_node: str
    to_node: str
    diff_state: str  # "added" | "removed" | "modified"
    current_relation: str | None = None
    baseline_relation: str | None = None


@dataclass(frozen=True)
class DiffSummary:
    """Aggregate counts for a diff result."""

    added_count: int = 0
    removed_count: int = 0
    dependency_changed_count: int = 0
    attribute_changed_count: int = 0
    total_changed_count: int = 0


@dataclass(frozen=True)
class DiffResult:
    """Complete diff output between two snapshots."""

    baseline_info: BaselineInfo
    current_info: BaselineInfo
    node_diffs: list[NodeDiff] = field(default_factory=list)
    edge_diffs: list[EdgeDiff] = field(default_factory=list)
    summary: DiffSummary = field(default_factory=DiffSummary)
    layer: str = "l1"  # "l1" | "l1.5"


# === Phase 2: Custom exceptions ===


class DiffError(Exception):
    """Exception for diff computation errors."""

    pass


# ============================================================================
# Phase 2.5: Vulnerability Layer models
# ============================================================================


# === Phase 2.5: Vulnerability Layer models ===
