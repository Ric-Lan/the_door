"""DiffExplanationStore — read-only JSONL cache for diff explanations.

Storage: <project_root>/.the-door/diff-explanations/cache.jsonl
Cache key: feature_id + baseline_version_id + current_version_id + language
On read, returns the last (most recent) matching entry.
Corrupted lines are skipped — does not raise.

Note (T5-V): diff-explanation generation was retired (丙案 D1). This store is now
read-only — `get` serves the GET /api/diff-explanations display path; the `save`
write path was removed with the generation handler. Existing cached entries
continue to be readable.
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path


class DiffExplanationStore:
    """Read-only local cache for previously-generated diff explanations."""

    def __init__(self, project_root: Path) -> None:
        self._store_path = (
            project_root / ".the-door" / "diff-explanations" / "cache.jsonl"
        )

    def get(
        self,
        feature_id: str,
        baseline_version_id: str,
        current_version_id: str,
        language: str,
    ) -> dict | None:
        """Return the most recent matching entry, or None if not found."""
        if not self._store_path.exists():
            return None
        last_match: dict | None = None
        for raw_line in self._store_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                warnings.warn(
                    f"DiffExplanationStore: skipping corrupted line in {self._store_path}",
                    stacklevel=2,
                )
                continue
            if (
                entry.get("feature_id") == feature_id
                and entry.get("baseline_version_id") == baseline_version_id
                and entry.get("current_version_id") == current_version_id
                and entry.get("language") == language
            ):
                last_match = entry
        return last_match
