"""Structural validation of an L1.5 block tree (max two levels).

Pure functions, no I/O. Called by snapshot_store.patch_snapshot before
persisting blocks. Enforces the STRUCTURAL invariants from
docs/superpowers/specs/2026-06-21-feature-classification-blocks-design.md §5.
Semantic correctness (歸得準不準) and naming are NOT checked here (C7 boundary;
naming is a prompt-level soft constraint).
"""
from __future__ import annotations

from the_door.models import BlockSummary

UNCLASSIFIED_BLOCK_ID = "blk-unclassified"


class BlockValidationError(Exception):
    """Raised when a block tree violates a structural invariant."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def validate_blocks(
    blocks: dict[str, BlockSummary],
    feature_ids: set[str],
) -> None:
    """Validate a block tree. Raises BlockValidationError on first violation.

    feature_ids = the current snapshot's l1_snapshot keys (the universe that
    must be exhaustively classified).
    """
    # 1. two-level cap: a child's parent must exist and be top-level
    for bid, b in blocks.items():
        if b.parent_block_id is not None:
            parent = blocks.get(b.parent_block_id)
            if parent is None:
                raise BlockValidationError(
                    "block.dangling_parent",
                    f"block {bid!r} parent {b.parent_block_id!r} not found",
                )
            if parent.parent_block_id is not None:
                raise BlockValidationError(
                    "block.too_deep",
                    f"block {bid!r} is nested 3+ levels (max two)",
                )

    # 2. features only on leaf blocks
    parents = {b.parent_block_id for b in blocks.values() if b.parent_block_id}
    for bid, b in blocks.items():
        if bid in parents and b.related_features:
            raise BlockValidationError(
                "block.parent_has_features",
                f"block {bid!r} has children, so related_features must be empty",
            )

    # 3. single membership + cross-ref existence
    seen: dict[str, str] = {}
    for bid, b in blocks.items():
        for fid in b.related_features:
            if fid not in feature_ids:
                raise BlockValidationError(
                    "block.unknown_feature",
                    f"block {bid!r} references unknown feature {fid!r}",
                )
            if fid in seen:
                raise BlockValidationError(
                    "block.duplicate_membership",
                    f"feature {fid!r} in both {seen[fid]!r} and {bid!r}",
                )
            seen[fid] = bid

    # 4. exhaustiveness
    missing = feature_ids - set(seen)
    if missing:
        raise BlockValidationError(
            "block.unclassified",
            f"{len(missing)} feature(s) not in any block: {sorted(missing)}; "
            f"put them in {UNCLASSIFIED_BLOCK_ID!r}",
        )
