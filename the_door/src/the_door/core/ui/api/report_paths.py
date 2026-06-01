"""Shared helper: locate the most recent update-report JSON under a project root."""
import json
from pathlib import Path


def find_latest_report_path(project_root: Path) -> Path | None:
    """Find the newest update-report-*.json by generated_at (fallback: mtime)."""
    dot_dir = project_root / ".the-door"
    if not dot_dir.exists():
        return None
    candidates = list(dot_dir.glob("update-report-*.json"))
    if not candidates:
        return None

    def sort_key(p: Path):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            val = data.get("generated_at", "")
            if val:
                return (1, val)
            return (0, p.stat().st_mtime_ns)
        except Exception:
            return (0, p.stat().st_mtime_ns)

    return max(candidates, key=sort_key)
