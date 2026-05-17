"""Compute which baseline L1 features are affected by structural changes.

Pure function ``compute_affected_features`` compares two ``StructureJSON``
snapshots (baseline vs current) plus a baseline ``VersionSnapshot`` and returns
an :class:`IncrementalDiff` describing:

* ``inherited_features`` — baseline features whose owned nodes are unchanged
* ``affected_features`` — baseline features touched by added/removed/modified nodes
* ``unmapped_nodes`` — node-level changes not owned by any feature

No I/O, no LLM calls — safe to unit test deterministically.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from the_door.models import (
    ASTNode,
    FeatureSummary,
    StructureJSON,
    VersionSnapshot,
)


@dataclass(frozen=True)
class NodeDelta:
    """Node-id buckets describing added / removed / modified nodes."""

    added: tuple[str, ...]
    removed: tuple[str, ...]
    modified: tuple[str, ...]


@dataclass(frozen=True)
class AffectedFeature:
    """A baseline feature whose owned node set was touched by the diff."""

    feature_id: str
    current_label: str
    current_description: str
    current_trigger_description: str | None
    delta: NodeDelta


@dataclass(frozen=True)
class IncrementalDiff:
    """Result of attributing a structural diff back to baseline features."""

    baseline_version_id: str
    inherited_features: tuple[FeatureSummary, ...]
    affected_features: tuple[AffectedFeature, ...]
    unmapped_nodes: NodeDelta


def _signature(node: ASTNode) -> str:
    """Deterministic content signature for a node.

    Uses ``parameters`` (real ASTNode field) rather than spec's placeholder
    ``params``. All fields fetched defensively so future ASTNode shape
    changes don't crash this function.
    """
    payload = (
        getattr(node, "name", None),
        tuple(getattr(node, "parameters", ()) or ()),
        getattr(node, "return_type", None),
        tuple(getattr(node, "decorators", ()) or ()),
        getattr(node, "docstring", None),
    )
    return hashlib.md5(repr(payload).encode("utf-8")).hexdigest()


def compute_affected_features(
    baseline_structure: StructureJSON,
    current_structure: StructureJSON,
    baseline: VersionSnapshot,
) -> IncrementalDiff:
    """Attribute node-level structural changes back to baseline L1 features."""
    baseline_sig = {n.node_id: _signature(n) for n in baseline_structure.nodes}
    current_sig = {n.node_id: _signature(n) for n in current_structure.nodes}

    added = set(current_sig.keys()) - set(baseline_sig.keys())
    removed = set(baseline_sig.keys()) - set(current_sig.keys())
    common = set(baseline_sig.keys()) & set(current_sig.keys())
    modified = {k for k in common if baseline_sig[k] != current_sig[k]}

    inherited: list[FeatureSummary] = []
    affected: list[AffectedFeature] = []
    all_owned_nodes: set[str] = set()

    for fs in baseline.l1_snapshot.values():
        owned = set(fs.source_nodes)
        all_owned_nodes |= owned
        f_added = tuple(sorted(added & owned))
        f_removed = tuple(sorted(removed & owned))
        f_modified = tuple(sorted(modified & owned))
        if f_added or f_removed or f_modified:
            affected.append(
                AffectedFeature(
                    feature_id=fs.feature_id,
                    current_label=fs.label,
                    current_description=fs.description,
                    current_trigger_description=fs.trigger_description,
                    delta=NodeDelta(f_added, f_removed, f_modified),
                )
            )
        else:
            inherited.append(fs)

    unmapped = NodeDelta(
        added=tuple(sorted(added - all_owned_nodes)),
        removed=tuple(sorted(removed - all_owned_nodes)),
        modified=tuple(sorted(modified - all_owned_nodes)),
    )

    return IncrementalDiff(
        baseline_version_id=baseline.version_id,
        inherited_features=tuple(inherited),
        affected_features=tuple(affected),
        unmapped_nodes=unmapped,
    )
