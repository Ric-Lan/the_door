# Task 1: ProjectRegistry — group CRUD + helper methods

**Files:**
- Modify: `the_door/src/the_door/core/registry.py`
- Modify: `the_door/tests/unit/core/test_registry.py`

---

- [ ] **Step 1: 寫失敗測試 — 在 test_registry.py 末尾加入 TestProjectRegistryGroups**

```python
# the_door/tests/unit/core/test_registry.py 末尾加入

class TestProjectRegistryGroups:

    def test_list_projects_skips_groups_key(self, registry):
        """list_projects must not include __groups__ as a project entry."""
        registry._save({
            "001": {"name": "proj-a", "path": "/a", "registered_at": "2026-01-01T00:00:00+00:00"},
            "__groups__": {"g001": {"name": "grp", "member_ids": ["001"], "created_at": "2026-01-01T00:00:00+00:00"}},
        })
        projects = registry.list_projects()
        assert len(projects) == 1
        assert projects[0]["id"] == "001"

    def test_create_group_returns_sequential_gid(self, registry):
        gid = registry.create_group("frontend")
        assert gid == "g001"
        gid2 = registry.create_group("backend")
        assert gid2 == "g002"

    def test_create_group_duplicate_name_raises(self, registry):
        registry.create_group("frontend")
        with pytest.raises(ValueError, match="群組名稱已存在"):
            registry.create_group("frontend")

    def test_add_to_group_auto_registers_path(self, registry, tmp_path):
        registry.create_group("my-group")
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        result = registry.add_to_group("my-group", str(project_dir))
        assert result["project_name"] == "proj"
        assert result["group_id"] == "g001"
        assert len(registry.list_projects()) == 1

    def test_add_to_group_idempotent(self, registry, tmp_path):
        """Adding same project twice is a no-op."""
        registry.create_group("grp")
        d = tmp_path / "p"
        d.mkdir()
        registry.add_to_group("grp", str(d))
        registry.add_to_group("grp", str(d))
        groups = registry.list_groups()
        assert len(groups[0]["members"]) == 1

    def test_add_to_group_already_in_another_raises(self, registry, tmp_path):
        registry.create_group("grp-a")
        registry.create_group("grp-b")
        d = tmp_path / "p"
        d.mkdir()
        registry.add_to_group("grp-a", str(d))
        with pytest.raises(ValueError, match="已在群組"):
            registry.add_to_group("grp-b", str(d))

    def test_remove_from_group(self, registry, tmp_path):
        registry.create_group("grp")
        d = tmp_path / "p"
        d.mkdir()
        registry.add_to_group("grp", str(d))
        registry.remove_from_group("grp", str(d))
        assert registry.list_groups()[0]["members"] == []

    def test_remove_not_in_group_raises(self, registry, tmp_path):
        registry.create_group("grp")
        d = tmp_path / "p"
        d.mkdir()
        registry.register(str(d))
        with pytest.raises(ValueError, match="不在群組"):
            registry.remove_from_group("grp", str(d))

    def test_list_groups_returns_members_with_details(self, registry, tmp_path):
        registry.create_group("samples")
        d = tmp_path / "ms-ts"
        d.mkdir()
        registry.add_to_group("samples", str(d))
        groups = registry.list_groups()
        assert len(groups) == 1
        assert groups[0]["name"] == "samples"
        assert groups[0]["members"][0]["name"] == "ms-ts"

    def test_get_group_for_project_returns_group(self, registry, tmp_path):
        registry.create_group("g")
        d = tmp_path / "p"
        d.mkdir()
        registry.add_to_group("g", str(d))
        pid = registry.get_by_path(str(d))["id"]
        group = registry.get_group_for_project(pid)
        assert group["name"] == "g"

    def test_get_group_for_project_returns_none_when_ungrouped(self, registry, tmp_path):
        d = tmp_path / "p"
        d.mkdir()
        registry.register(str(d))
        assert registry.get_group_for_project("001") is None

    def test_get_by_path_returns_project(self, registry, tmp_path):
        d = tmp_path / "my-app"
        d.mkdir()
        registry.register(str(d))
        result = registry.get_by_path(str(d))
        assert result is not None
        assert result["name"] == "my-app"

    def test_get_by_path_returns_none_for_unknown(self, registry, tmp_path):
        assert registry.get_by_path(str(tmp_path / "nope")) is None

    def test_update_last_opened_writes_timestamp(self, registry, tmp_path):
        d = tmp_path / "p"
        d.mkdir()
        registry.register(str(d))
        registry.update_last_opened(str(d))
        projects = registry.list_projects()
        assert projects[0]["last_opened_at"] is not None

    def test_get_most_recently_opened_returns_latest(self, registry, tmp_path):
        for name in ["a", "b"]:
            d = tmp_path / name
            d.mkdir()
            registry.register(str(d))
        registry.update_last_opened(str(tmp_path / "b"))
        result = registry.get_most_recently_opened()
        assert result["name"] == "b"

    def test_get_most_recently_opened_returns_none_when_all_null(self, registry, tmp_path):
        d = tmp_path / "p"
        d.mkdir()
        registry.register(str(d))
        assert registry.get_most_recently_opened() is None

    def test_find_active_project_detects_checklist_newer_than_last_opened(self, registry, tmp_path):
        import time
        d = tmp_path / "proj"
        d.mkdir()
        (d / ".the-door").mkdir()
        registry.register(str(d))
        registry.update_last_opened(str(d))
        time.sleep(0.05)
        (d / ".the-door" / "checklist.json").write_text("{}")
        result = registry.find_active_project()
        assert result is not None
        assert result["name"] == "proj"

    def test_find_active_project_returns_none_when_checklist_older_than_last_opened(self, registry, tmp_path):
        import time
        d = tmp_path / "proj"
        d.mkdir()
        (d / ".the-door").mkdir()
        (d / ".the-door" / "checklist.json").write_text("{}")
        time.sleep(0.05)
        registry.register(str(d))
        registry.update_last_opened(str(d))
        result = registry.find_active_project()
        assert result is None

    def test_backward_compat_no_groups_key(self, registry, tmp_path):
        """Old registry.json without __groups__ works transparently."""
        d = tmp_path / "old-proj"
        d.mkdir()
        registry._save({"001": {"name": "old-proj", "path": str(d), "registered_at": "2026-01-01T00:00:00+00:00"}})
        assert registry.list_groups() == []
        assert registry.get_most_recently_opened() is None
        assert len(registry.list_projects()) == 1
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/test_registry.py::TestProjectRegistryGroups -v 2>&1 | head -20
```

Expected: `AttributeError: 'ProjectRegistry' object has no attribute 'create_group'`

- [ ] **Step 3: 完整替換 registry.py**

```python
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
```

- [ ] **Step 4: 確認測試通過**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/test_registry.py -v 2>&1 | tail -15
```

Expected: 全部 PASSED（含原有測試 + 新 TestProjectRegistryGroups）

- [ ] **Step 5: Commit**

```bash
cd the_door && git add the_door/src/the_door/core/registry.py the_door/tests/unit/core/test_registry.py
git commit -m "feat(registry): add group CRUD, get_by_path, update_last_opened, find_active_project"
```
