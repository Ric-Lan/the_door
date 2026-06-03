"""Resolve a human baseline reference (the 5 grammars) to a concrete snapshot.

Pure: no file I/O. The store loads snapshots and feeds them in; this class only
interprets the reference and matches. Single home of all reference grammars:
date / git tag / commit SHA / manual label / version_id (UUID).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from the_door.models import SnapshotNotFoundError, VersionSnapshot


class BaselineResolver:
    """Maps a signifier (human reference string) to a signified (VersionSnapshot)."""

    def resolve(
        self, reference: str, snapshots: list[VersionSnapshot]
    ) -> VersionSnapshot:
        """Resolve ``reference`` against an already-loaded snapshot list.

        Priority cascade (order is behaviour-preserving — see spec §7.1):
          1. ISO date (YYYY-MM-DD)  -> most recent on or before that date
          2. git tag exact / commit SHA prefix (>=7 chars)
          3. manual label exact
          4. version_id exact (UUID)            # new in B; placed AFTER label
        Raises SnapshotNotFoundError(reference, available) if nothing matches.
        """
        if re.match(r"^\d{4}-\d{2}-\d{2}$", reference):
            return self._resolve_by_date(reference, snapshots)

        result = self._resolve_by_git_ref(reference, snapshots)
        if result is not None:
            return result

        result = self._resolve_by_label(reference, snapshots)
        if result is not None:
            return result

        result = self._resolve_by_version_id(reference, snapshots)
        if result is not None:
            return result

        raise SnapshotNotFoundError(reference, self._build_available_list(snapshots))

    def _resolve_by_date(
        self, reference: str, snapshots: list[VersionSnapshot]
    ) -> VersionSnapshot:
        """Find the most recent snapshot on or before the given date."""
        try:
            query_date = datetime.strptime(reference, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
        except ValueError:
            available = self._build_available_list(snapshots)
            raise SnapshotNotFoundError(reference, available)

        candidates = []
        for s in snapshots:
            try:
                ts = datetime.fromisoformat(s.timestamp)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts <= query_date:
                    candidates.append((ts, s))
            except ValueError:
                continue

        if not candidates:
            available = self._build_available_list(snapshots)
            raise SnapshotNotFoundError(reference, available)

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def _resolve_by_git_ref(
        self, reference: str, snapshots: list[VersionSnapshot]
    ) -> VersionSnapshot | None:
        """Find snapshot by git tag or commit SHA match."""
        candidates: list[VersionSnapshot] = []
        for s in snapshots:
            # Check git tags
            if reference in (s.git_tags or []):
                candidates.append(s)
                continue
            # Check commit SHA (full or abbreviated ≥7 chars)
            if (
                s.commit_hash is not None
                and len(reference) >= 7
                and s.commit_hash.startswith(reference)
            ):
                candidates.append(s)

        if not candidates:
            return None

        return max(candidates, key=lambda s: s.timestamp)

    def _resolve_by_label(
        self, reference: str, snapshots: list[VersionSnapshot]
    ) -> VersionSnapshot | None:
        """Find snapshot by exact label match."""
        candidates = [s for s in snapshots if s.label == reference]
        if not candidates:
            return None
        return max(candidates, key=lambda s: s.timestamp)

    def _resolve_by_version_id(
        self, reference: str, snapshots: list[VersionSnapshot]
    ) -> VersionSnapshot | None:
        """Find snapshot by exact version_id match."""
        for s in snapshots:
            if s.version_id == reference:
                return s
        return None

    def _build_available_list(self, snapshots: list[VersionSnapshot]) -> list[dict]:
        """Build a list of available snapshot summaries for error messages."""
        available = []
        for s in sorted(snapshots, key=lambda x: x.timestamp, reverse=True):
            entry: dict = {
                "version_id": s.version_id,
                "timestamp": s.timestamp,
                "trigger": s.trigger,
            }
            if s.commit_hash:
                entry["commit_hash"] = s.commit_hash
            if s.git_tags:
                entry["git_tags"] = s.git_tags
            if s.label:
                entry["label"] = s.label
            available.append(entry)
        return available
