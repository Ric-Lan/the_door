"""Snapshot persistence + projection data models (and snapshot exceptions)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .vulnerability import DatabaseFreshness, VulnerabilityEntry


@dataclass(frozen=True)
class FeatureSummary:
    """Summarized feature data stored in a version snapshot.

    Projects :class:`Feature` to the minimum needed for diff comparison plus
    the bits the viewer needs to drill down. ``trigger_description`` is the
    user-facing trigger text and ``source_nodes`` is the AST node ids the
    LLM attributed to this feature — without it, L2 generation has no way
    to know which subset of structure.json to cluster. Both default to
    empty/None so legacy snapshots deserialize unchanged.

    ``source_nodes`` is a tuple (not list) so the dataclass stays hashable
    under ``frozen=True``; callers serialize it as a JSON list at boundaries.
    Diff comparison (:mod:`core.diff.diff_engine`) only keys on label and
    description, so adding/removing nodes here does not flip a feature into
    ``attribute_changed``.
    """

    feature_id: str
    label: str
    description: str
    source_node_count: int
    confidence: str | None  # "high" | "medium" | "low" | None（未評估）
    trigger_description: str | None = None
    source_nodes: tuple[str, ...] = ()
    confidence_reason: str | None = None


@dataclass(frozen=True)
class BlockSummary:
    """Summarized block data stored in a version snapshot (L1.5)."""

    block_id: str
    label: str
    responsibility: str
    confidence: str | None = None


@dataclass(frozen=True)
class RelationSummary:
    """Summarized feature relation stored in a version snapshot."""

    from_feature: str
    to_feature: str
    relation: str


@dataclass(frozen=True)
class BaselineInfo:
    """Metadata about a comparison baseline or current version."""

    version_id: str
    timestamp: str  # ISO8601
    trigger: str  # "commit" | "manual"
    commit_hash: str | None = None
    git_tags: list[str] = field(default_factory=list)
    label: str | None = None
    resolved_from: str | None = None  # Original query string used to resolve this baseline


@dataclass(frozen=True)
class VersionSnapshot:
    """A persisted record of L1/L1.5 output at a specific point in time."""

    version_id: str
    timestamp: str  # ISO8601
    trigger: str  # "commit" | "manual"
    l1_snapshot: dict[str, FeatureSummary] = field(default_factory=dict)
    analyzed_files: list[str] = field(default_factory=list)
    commit_hash: str | None = None
    git_tags: list[str] = field(default_factory=list)
    label: str | None = None
    l1_5_snapshot: dict[str, BlockSummary] = field(default_factory=dict)
    feature_relations_snapshot: list[RelationSummary] = field(default_factory=list)
    vulnerabilities_snapshot: list[VulnerabilityEntry] = field(default_factory=list)
    vulnerability_db_freshness: DatabaseFreshness | None = None
    codebase_path: Path | None = None


class SnapshotError(Exception):
    """Base exception for snapshot operations."""

    pass


class SnapshotNotFoundError(SnapshotError):
    """Raised when a baseline reference cannot be resolved."""

    def __init__(self, reference: str, available: list[dict]):
        self.reference = reference
        self.available = available
        super().__init__(f"No snapshot matches '{reference}'")
