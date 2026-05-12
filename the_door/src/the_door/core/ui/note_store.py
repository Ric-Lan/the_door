"""NoteStore — append-only JSONL store for user notes.

Storage: <project_root>/.the-door/user-notes/notes.jsonl
Each line is a JSON object with a single note entry.
Corrupted lines are skipped on read with a warning.
"""
from __future__ import annotations

import datetime
import json
import uuid
import warnings
from pathlib import Path


class NoteStore:
    """Append-only local store for user notes."""

    def __init__(self, project_root: Path) -> None:
        self._store_path = project_root / ".the-door" / "user-notes" / "notes.jsonl"

    def add_note(
        self,
        mode: str,
        feature_id: str,
        version_a: str | None,
        version_b: str | None,
        name_input: str,
        comment: str,
    ) -> dict:
        """Create, persist, and return the new note as a plain dict.

        display_name uses local server date (not UTC) per spec §8.3.
        """
        name_clean = name_input.strip()
        comment_clean = comment.strip()
        today = datetime.date.today().strftime("%Y%m%d")
        entry = {
            "note_id": str(uuid.uuid4()),
            "mode": mode,
            "feature_id": feature_id,
            "version_a": version_a,
            "version_b": version_b,
            "display_name": name_clean + today,
            "name_input": name_clean,
            "comment": comment_clean,
            "created_at": (
                datetime.datetime.now(datetime.timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            ),
        }
        self._append(entry)
        return entry

    def list_notes(
        self,
        mode: str,
        feature_id: str,
        version_a: str | None,
        version_b: str | None,
    ) -> list[dict]:
        """Return all notes matching the given composite key.

        Corrupted lines are skipped with a warning — does not raise.
        """
        if not self._store_path.exists():
            return []
        results: list[dict] = []
        for raw_line in self._store_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                warnings.warn(
                    f"NoteStore: skipping corrupted line in {self._store_path}",
                    stacklevel=2,
                )
                continue
            if self._matches(entry, mode, feature_id, version_a, version_b):
                results.append(entry)
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _matches(
        self,
        entry: dict,
        mode: str,
        feature_id: str,
        version_a: str | None,
        version_b: str | None,
    ) -> bool:
        if entry.get("mode") != mode:
            return False
        if entry.get("feature_id") != feature_id:
            return False
        if mode == "baseline":
            return entry.get("version_a") == version_a
        if mode == "current":
            return entry.get("version_b") == version_b
        # diff: both version keys must match
        return (
            entry.get("version_a") == version_a
            and entry.get("version_b") == version_b
        )

    def _append(self, entry: dict) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        with self._store_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
