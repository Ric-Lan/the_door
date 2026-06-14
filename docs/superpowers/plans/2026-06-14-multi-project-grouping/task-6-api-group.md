# Task 6: API — `GET /api/group` endpoint

**Depends on:** Task 1 (registry.py 新方法)

**Files:**
- Create: `the_door/src/the_door/core/ui/api/handlers/group.py`
- Modify: `the_door/src/the_door/core/ui/api/router.py`
- Modify: `the_door/src/the_door/core/ui/server.py`
- Modify: `the_door/src/the_door/core/ui/api/_gen_docs.py`
- Create: `the_door/tests/unit/core/ui/api/handlers/test_group_handler.py`

---

- [ ] **Step 1: 確認 handlers test 目錄存在**

```bash
cd the_door && ls tests/unit/core/ui/api/handlers/ 2>/dev/null || (mkdir -p tests/unit/core/ui/api/handlers && touch tests/unit/core/ui/api/handlers/__init__.py)
```

- [ ] **Step 2: 新建失敗測試 `the_door/tests/unit/core/ui/api/handlers/test_group_handler.py`**

```python
"""Unit tests for GET /api/group handler."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from the_door.core.registry import ProjectRegistry
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.handlers.group import GroupHandlers


def _make_ctx(project_root: Path) -> APIContext:
    ctx = MagicMock(spec=APIContext)
    ctx.project_root = project_root
    return ctx


def test_get_group_returns_group_when_project_is_grouped(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    proj = tmp_path / "ms-ts"
    proj.mkdir()
    reg.create_group("samples")
    reg.add_to_group("samples", str(proj))
    monkeypatch.setattr("the_door.core.ui.api.handlers.group.ProjectRegistry", lambda: reg)
    ctx = _make_ctx(proj)
    handler = GroupHandlers(ctx)
    status, body = handler.get_group()
    assert status == 200
    assert body["group"]["name"] == "samples"
    assert len(body["group"]["members"]) == 1
    assert body["group"]["members"][0]["is_current"] is True
    assert body["current_project"]["name"] == "ms-ts"


def test_get_group_returns_null_group_when_ungrouped(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    proj = tmp_path / "solo"
    proj.mkdir()
    reg.register(str(proj))
    monkeypatch.setattr("the_door.core.ui.api.handlers.group.ProjectRegistry", lambda: reg)
    ctx = _make_ctx(proj)
    handler = GroupHandlers(ctx)
    status, body = handler.get_group()
    assert status == 200
    assert body["group"] is None
    assert "hint" in body
    assert "the-door group add" in body["hint"]


def test_get_group_unregistered_project_returns_null(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    monkeypatch.setattr("the_door.core.ui.api.handlers.group.ProjectRegistry", lambda: reg)
    proj = tmp_path / "unknown"
    proj.mkdir()
    ctx = _make_ctx(proj)
    handler = GroupHandlers(ctx)
    status, body = handler.get_group()
    assert status == 200
    assert body["group"] is None


def test_get_group_shows_all_members_with_is_current_flag(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    proj_a = tmp_path / "proj-a"
    proj_b = tmp_path / "proj-b"
    proj_a.mkdir()
    proj_b.mkdir()
    reg.create_group("grp")
    reg.add_to_group("grp", str(proj_a))
    reg.add_to_group("grp", str(proj_b))
    monkeypatch.setattr("the_door.core.ui.api.handlers.group.ProjectRegistry", lambda: reg)
    ctx = _make_ctx(proj_a)
    handler = GroupHandlers(ctx)
    status, body = handler.get_group()
    members = body["group"]["members"]
    assert len(members) == 2
    current = [m for m in members if m["is_current"]]
    other = [m for m in members if not m["is_current"]]
    assert len(current) == 1 and current[0]["name"] == "proj-a"
    assert len(other) == 1 and other[0]["name"] == "proj-b"
```

- [ ] **Step 3: 確認測試失敗**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/ui/api/handlers/test_group_handler.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'the_door.core.ui.api.handlers.group'`

- [ ] **Step 4: 新建 `the_door/src/the_door/core/ui/api/handlers/group.py`**

```python
"""GroupHandlers — GET /api/group."""
from __future__ import annotations

from the_door.core.registry import ProjectRegistry, UNGROUPED_HINT
from the_door.core.ui.api.context import APIContext


class GroupHandlers:
    def __init__(self, ctx: APIContext) -> None:
        self._ctx = ctx

    def get_group(self, ctx=None, **_) -> tuple[int, dict]:
        """GET /api/group — return current project's group membership and sibling members."""
        reg = ProjectRegistry()
        project_root = str(self._ctx.project_root.resolve())
        project = reg.get_by_path(project_root)

        if project is None:
            return 200, {
                "current_project": {"name": self._ctx.project_root.name, "path": project_root},
                "group": None,
                "hint": UNGROUPED_HINT,
            }

        group_info = reg.get_group_for_project(project["id"])

        current_project = {
            "id": project["id"],
            "name": project["name"],
            "path": project["path"],
        }

        if group_info is None:
            return 200, {
                "current_project": current_project,
                "group": None,
                "hint": UNGROUPED_HINT,
            }

        groups = reg.list_groups()
        target_group = next((g for g in groups if g["id"] == group_info["id"]), None)
        members = []
        if target_group:
            for m in target_group["members"]:
                members.append({
                    "id": m["id"],
                    "name": m["name"],
                    "path": m["path"],
                    "is_current": m["id"] == project["id"],
                })

        return 200, {
            "current_project": current_project,
            "group": {
                "id": group_info["id"],
                "name": group_info["name"],
                "members": members,
            },
        }
```

- [ ] **Step 5: 更新 `router.py` — 加第六個參數 `gr` + 新 route**

在 `the_door/src/the_door/core/ui/api/router.py` 找到 `def build_routes(p, c, g, d, n)` 這行，改為：

```python
def build_routes(p, c, g, d, n, gr) -> list[Route]:
    """p/c/g/d/n/gr = Project/Catalog/Graph/Diff/Annotation/Group handler instances."""
```

在 routes list 最後的 `Route("POST", "/api/notes", ...)` 之後加：

```python
        Route("GET",  "/api/group",  gr.get_group,  summary="讀取當前專案的群組與成員資訊"),
```

- [ ] **Step 6: 更新 `server.py`**

在 `the_door/src/the_door/core/ui/server.py` 找到其他 handler imports，在其後加：

```python
from the_door.core.ui.api.handlers.group import GroupHandlers
```

找到 `build_routes(` 呼叫，加第六個參數：

```python
routes = build_routes(
    ProjectHandlers(ctx),
    CatalogHandlers(ctx),
    GraphHandlers(ctx),
    DiffHandlers(ctx),
    AnnotationHandlers(ctx),
    GroupHandlers(ctx),
)
```

- [ ] **Step 7: 更新 `_gen_docs.py`**

在 `the_door/src/the_door/core/ui/api/_gen_docs.py` 找到：

```python
from the_door.core.ui.api.handlers.annotation import AnnotationHandlers
from the_door.core.ui.api.handlers.catalog import CatalogHandlers
from the_door.core.ui.api.handlers.diff import DiffHandlers
from the_door.core.ui.api.handlers.graph import GraphHandlers
from the_door.core.ui.api.handlers.project import ProjectHandlers
from the_door.core.ui.api.router import build_routes
```

替換為：

```python
from the_door.core.ui.api.handlers.annotation import AnnotationHandlers
from the_door.core.ui.api.handlers.catalog import CatalogHandlers
from the_door.core.ui.api.handlers.diff import DiffHandlers
from the_door.core.ui.api.handlers.graph import GraphHandlers
from the_door.core.ui.api.handlers.group import GroupHandlers
from the_door.core.ui.api.handlers.project import ProjectHandlers
from the_door.core.ui.api.router import build_routes
```

找到：

```python
    routes = build_routes(
        ProjectHandlers(ctx),
        CatalogHandlers(ctx),
        GraphHandlers(ctx),
        DiffHandlers(ctx),
        AnnotationHandlers(ctx),
    )
```

替換為：

```python
    routes = build_routes(
        ProjectHandlers(ctx),
        CatalogHandlers(ctx),
        GraphHandlers(ctx),
        DiffHandlers(ctx),
        AnnotationHandlers(ctx),
        GroupHandlers(ctx),
    )
```

- [ ] **Step 8: 確認測試通過 + 回歸**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/ui/api/handlers/test_group_handler.py tests/unit/core/ui/api/test_router.py -v 2>&1 | tail -15
```

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/ -x -q 2>&1 | tail -10
```

Expected: 全部 PASSED（無 regression）

- [ ] **Step 9: Commit**

```bash
cd the_door && git add \
  the_door/src/the_door/core/ui/api/handlers/group.py \
  the_door/src/the_door/core/ui/api/router.py \
  the_door/src/the_door/core/ui/server.py \
  the_door/src/the_door/core/ui/api/_gen_docs.py \
  the_door/tests/unit/core/ui/api/handlers/
git commit -m "feat(api): add GET /api/group endpoint — current project group membership"
```
