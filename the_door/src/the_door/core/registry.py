"""ProjectRegistry — persist and discover analyzed projects."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_REGISTRY_PATH = Path.home() / ".the-door" / "registry.json"


class ProjectRegistry:
    """Manage ~/.the-door/registry.json.

    IDs are zero-padded 3-digit strings: '001', '002', ...
    Group IDs are 'g001', 'g002', ...
    Registration is idempotent: same resolved path → same id.
    Groups stored under '__groups__' key (never treated as a project id).
    """

    def __init__(self, registry_path: Path = DEFAULT_REGISTRY_PATH):
        self._path = Path(registry_path)

    # ------------------------------------------------------------------ projects

    def register(self, codebase_path: str) -> str:
        """Register a project. Returns its id. No-op if already registered."""
        resolved = str(Path(codebase_path).resolve())
        data = self._load()

        for pid, info in data.items():
            if pid.startswith("__"):
                continue
            if info["path"] == resolved:
                return pid

        next_id = f"{max((int(k) for k in data if not k.startswith('__')), default=0) + 1:03d}"
        data[next_id] = {
            "name": Path(resolved).name,
            "path": resolved,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "last_opened_at": None,
        }
        self._save(data)
        return next_id

    def list_projects(self) -> list[dict]:
        """Return all projects sorted by id ascending (skips __groups__ key)."""
        data = self._load()
        return [
            {"id": pid, **info}
            for pid, info in sorted(data.items())
            if not pid.startswith("__")
        ]

    def get_by_id(self, project_id: str) -> dict | None:
        """Return project dict for given id, or None if not found."""
        data = self._load()
        info = data.get(project_id)
        if info is None or project_id.startswith("__"):
            return None
        return {"id": project_id, **info}

    def get_by_path(self, codebase_path: str) -> dict | None:
        """Return project dict for given path, or None if not registered."""
        resolved = str(Path(codebase_path).resolve())
        data = self._load()
        for pid, info in data.items():
            if pid.startswith("__"):
                continue
            if info.get("path") == resolved:
                return {"id": pid, **info}
        return None

    def update_last_opened(self, codebase_path: str) -> None:
        """Write last_opened_at (UTC now) for the project at this path. No-op if unregistered."""
        resolved = str(Path(codebase_path).resolve())
        data = self._load()
        for pid, info in data.items():
            if pid.startswith("__"):
                continue
            if info.get("path") == resolved:
                data[pid]["last_opened_at"] = datetime.now(timezone.utc).isoformat()
                self._save(data)
                return

    def get_most_recently_opened(self) -> dict | None:
        """Return the project with the latest last_opened_at, or None if all are null."""
        data = self._load()
        best: dict | None = None
        best_ts: str | None = None
        for pid, info in data.items():
            if pid.startswith("__"):
                continue
            ts = info.get("last_opened_at")
            if ts is not None and (best_ts is None or ts > best_ts):
                best = {"id": pid, **info}
                best_ts = ts
        return best

    def find_active_project(self, stale_threshold_seconds: int = 1800) -> dict | None:
        """Return the project most likely being actively analyzed.

        Checks if checklist.json mtime > last_opened_at (analysis happened since
        last UI session). Falls back to mtime within stale_threshold_seconds of
        now when last_opened_at is null.
        stale_threshold_seconds=1800: extract_structure on large Python projects
        runs at most ~20 minutes; 1800s (30 min) adds comfortable headroom.
        """
        now = time.time()
        data = self._load()
        best: dict | None = None
        best_mtime: float | None = None
        for pid, info in data.items():
            if pid.startswith("__"):
                continue
            path = info.get("path")
            if not path:
                continue
            checklist = Path(path) / ".the-door" / "checklist.json"
            try:
                mtime = checklist.stat().st_mtime
            except OSError:
                continue
            last_opened = info.get("last_opened_at")
            if last_opened is not None:
                lo_ts = datetime.fromisoformat(last_opened).timestamp()
                if mtime <= lo_ts:
                    continue
            else:
                if now - mtime > stale_threshold_seconds:
                    continue
            if best_mtime is None or mtime > best_mtime:
                best = {"id": pid, **info}
                best_mtime = mtime
        return best

    # ------------------------------------------------------------------ groups

    def create_group(self, name: str) -> str:
        """Create a new group. Returns group_id. Raises ValueError if name exists."""
        data = self._load()
        groups = data.get("__groups__") or {}
        for ginfo in groups.values():
            if ginfo.get("name") == name:
                raise ValueError(f"群組名稱已存在：{name!r}")
        next_id = f"g{max((int(gid[1:]) for gid in groups), default=0) + 1:03d}"
        groups[next_id] = {
            "name": name,
            "member_ids": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        data["__groups__"] = groups
        self._save(data)
        return next_id

    def add_to_group(self, group_name_or_id: str, codebase_path: str) -> dict:
        """Add path to group. Auto-registers the path if not yet registered.

        Raises ValueError if the project is already in a different group.
        Returns {"group_id": ..., "project_id": ..., "project_name": ...}.
        """
        pid = self.register(codebase_path)
        data = self._load()
        groups = data.get("__groups__") or {}
        gid = self._resolve_group_id(group_name_or_id, groups)
        for other_gid, ginfo in groups.items():
            if pid in (ginfo.get("member_ids") or []) and other_gid != gid:
                raise ValueError(
                    f"專案 '{data[pid]['name']}' 已在群組 '{ginfo['name']}'（一個專案只能屬於一個群組）。\n"
                    f"如需移動，請先執行：the-door group remove {ginfo['name']} <path>"
                )
        members = groups[gid].setdefault("member_ids", [])
        if pid not in members:
            members.append(pid)
        data["__groups__"] = groups
        self._save(data)
        return {"group_id": gid, "project_id": pid, "project_name": data[pid]["name"]}

    def remove_from_group(self, group_name_or_id: str, codebase_path: str) -> None:
        """Remove path from group. Raises ValueError if path not in group."""
        resolved = str(Path(codebase_path).resolve())
        data = self._load()
        groups = data.get("__groups__") or {}
        gid = self._resolve_group_id(group_name_or_id, groups)
        pid = None
        for p_id, info in data.items():
            if p_id.startswith("__"):
                continue
            if info.get("path") == resolved:
                pid = p_id
                break
        if pid is None:
            raise ValueError(f"路徑未登記：{codebase_path}")
        members = groups[gid].get("member_ids") or []
        if pid not in members:
            raise ValueError(f"路徑不在群組 '{groups[gid]['name']}' 中：{codebase_path}")
        members.remove(pid)
        groups[gid]["member_ids"] = members
        data["__groups__"] = groups
        self._save(data)

    def list_groups(self) -> list[dict]:
        """Return all groups sorted by id, each with member details."""
        data = self._load()
        groups = data.get("__groups__") or {}
        result = []
        for gid, ginfo in sorted(groups.items()):
            members = []
            for mid in (ginfo.get("member_ids") or []):
                p = data.get(mid, {})
                members.append({"id": mid, "name": p.get("name", ""), "path": p.get("path", "")})
            result.append({
                "id": gid,
                "name": ginfo["name"],
                "created_at": ginfo.get("created_at"),
                "members": members,
            })
        return result

    def get_group_for_project(self, project_id: str) -> dict | None:
        """Return the group dict for this project, or None if ungrouped."""
        data = self._load()
        groups = data.get("__groups__") or {}
        for gid, ginfo in groups.items():
            if project_id in (ginfo.get("member_ids") or []):
                return {"id": gid, "name": ginfo["name"]}
        return None

    # ------------------------------------------------------------------ internal

    def _resolve_group_id(self, group_name_or_id: str, groups: dict) -> str:
        if group_name_or_id in groups:
            return group_name_or_id
        for gid, ginfo in groups.items():
            if ginfo.get("name") == group_name_or_id:
                return gid
        raise ValueError(f"群組不存在：{group_name_or_id!r}\n試試：the-door group create {group_name_or_id}")

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


UNGROUPED_HINT = "此專案尚未加入群組。執行 `the-door group add <name> <path>` 建立比較群組。"
