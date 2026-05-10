"""ProjectRegistry — persist and discover analyzed projects."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_REGISTRY_PATH = Path.home() / ".the-door" / "registry.json"


class ProjectRegistry:
    """Manage ~/.the-door/registry.json.

    IDs are zero-padded 3-digit strings: '001', '002', ...
    Registration is idempotent: same resolved path → same id.
    """

    def __init__(self, registry_path: Path = DEFAULT_REGISTRY_PATH):
        self._path = Path(registry_path)

    def register(self, codebase_path: str) -> str:
        """Register a project. Returns its id. No-op if already registered."""
        resolved = str(Path(codebase_path).resolve())
        data = self._load()

        for pid, info in data.items():
            if info["path"] == resolved:
                return pid

        next_id = f"{max((int(k) for k in data.keys()), default=0) + 1:03d}"
        data[next_id] = {
            "name": Path(resolved).name,
            "path": resolved,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save(data)
        return next_id

    def list_projects(self) -> list[dict]:
        """Return all projects sorted by id ascending."""
        data = self._load()
        return [{"id": pid, **info} for pid, info in sorted(data.items())]

    def get_by_id(self, project_id: str) -> dict | None:
        """Return project dict for given id, or None if not found."""
        data = self._load()
        info = data.get(project_id)
        if info is None:
            return None
        return {"id": project_id, **info}

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _save(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
