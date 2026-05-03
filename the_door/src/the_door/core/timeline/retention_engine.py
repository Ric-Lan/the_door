"""Retention Engine — snapshot retention policy computation.

Pure functions, no I/O, no side effects. Computes which snapshots to
retain and which to remove based on a count-based policy. Manual
snapshots (trigger="manual") and tagged snapshots (git_tags non-empty)
are always protected.
"""
from __future__ import annotations

from the_door.models import RetentionDecision, VersionSnapshot


class RetentionEngine:
    """版本保留策略計算引擎。Pure function — 無 I/O。

    以快照數量為單位，根據 max_snapshots 上限決定保留/清理。
    手動快照（trigger="manual"）和有 git_tags 的快照受保護。
    """

    def compute_retention(
        self,
        snapshots: list[VersionSnapshot],
        max_snapshots: int = 50,
        enabled: bool = True,
    ) -> RetentionDecision:
        """計算保留決策。

        Algorithm:
        1. If enabled=False → all in to_retain, to_remove empty
        2. Classify: protected (trigger=="manual" OR git_tags non-empty) vs unprotected
        3. Protected always in to_retain
        4. Unprotected sorted by timestamp descending (newest first)
        5. Keep first max_snapshots unprotected, rest in to_remove
        6. Return RetentionDecision(to_retain, to_remove)

        Edge cases:
        - max_snapshots <= 0 → all unprotected in to_remove
        - Empty list → empty RetentionDecision

        Guarantee: to_retain ∪ to_remove = all input, to_retain ∩ to_remove = ∅
        """
        if not snapshots:
            return RetentionDecision(to_retain=[], to_remove=[])

        # Disabled → retain everything
        if not enabled:
            return RetentionDecision(
                to_retain=[s.version_id for s in snapshots],
                to_remove=[],
            )

        # Classify into protected vs unprotected
        protected: list[VersionSnapshot] = []
        unprotected: list[VersionSnapshot] = []
        for snap in snapshots:
            if self._is_protected(snap):
                protected.append(snap)
            else:
                unprotected.append(snap)

        # Protected always retained
        to_retain: list[str] = [s.version_id for s in protected]
        to_remove: list[str] = []

        # Unprotected sorted by timestamp descending (newest first)
        unprotected_sorted = sorted(
            unprotected, key=lambda s: s.timestamp, reverse=True
        )

        # Keep first max_snapshots unprotected, rest in to_remove
        if max_snapshots <= 0:
            # All unprotected go to to_remove
            to_remove = [s.version_id for s in unprotected_sorted]
        else:
            to_retain.extend(
                s.version_id for s in unprotected_sorted[:max_snapshots]
            )
            to_remove = [
                s.version_id for s in unprotected_sorted[max_snapshots:]
            ]

        return RetentionDecision(to_retain=to_retain, to_remove=to_remove)

    def _is_protected(self, snapshot: VersionSnapshot) -> bool:
        """Protected if trigger=="manual" OR git_tags is non-empty list."""
        return snapshot.trigger == "manual" or bool(snapshot.git_tags)
