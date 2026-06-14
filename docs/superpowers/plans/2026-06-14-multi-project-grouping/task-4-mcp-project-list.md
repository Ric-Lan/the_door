# Task 4: MCP — `project_list` 加 group 欄位

**Depends on:** Task 1 (registry.py 新方法)

**Files:**
- Modify: `the_door/src/the_door/mcp/tools/project_list_tool.py`
- Create: `the_door/tests/unit/mcp/tools/test_project_list_tool.py`

---

- [ ] **Step 1: 新建失敗測試 `the_door/tests/unit/mcp/tools/test_project_list_tool.py`**

```python
"""Unit tests for project_list MCP tool — group fields."""
from __future__ import annotations

import asyncio

import pytest

from the_door.core.registry import ProjectRegistry
from the_door.mcp.tools import project_list_tool


def test_project_list_includes_group_id_and_name(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    proj = tmp_path / "ms-ts"
    proj.mkdir()
    reg.create_group("samples")
    reg.add_to_group("samples", str(proj))
    monkeypatch.setattr("the_door.mcp.tools.project_list_tool.ProjectRegistry", lambda: reg)
    result = asyncio.run(project_list_tool.execute({}))
    p = result["projects"][0]
    assert p["group_id"] == "g001"
    assert p["group_name"] == "samples"


def test_project_list_ungrouped_project_has_null_group(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    proj = tmp_path / "solo"
    proj.mkdir()
    reg.register(str(proj))
    monkeypatch.setattr("the_door.mcp.tools.project_list_tool.ProjectRegistry", lambda: reg)
    result = asyncio.run(project_list_tool.execute({}))
    p = result["projects"][0]
    assert p["group_id"] is None
    assert p["group_name"] is None


def test_project_list_includes_groups_list(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    reg.create_group("my-group")
    monkeypatch.setattr("the_door.mcp.tools.project_list_tool.ProjectRegistry", lambda: reg)
    result = asyncio.run(project_list_tool.execute({}))
    assert "groups" in result
    assert result["groups"][0]["name"] == "my-group"


def test_project_list_hint_when_ungrouped_projects(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    proj = tmp_path / "solo"
    proj.mkdir()
    reg.register(str(proj))
    monkeypatch.setattr("the_door.mcp.tools.project_list_tool.ProjectRegistry", lambda: reg)
    result = asyncio.run(project_list_tool.execute({}))
    assert "hint" in result
    assert "the-door group add" in result["hint"]


def test_project_list_no_hint_when_all_grouped(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    proj = tmp_path / "proj"
    proj.mkdir()
    reg.create_group("grp")
    reg.add_to_group("grp", str(proj))
    monkeypatch.setattr("the_door.mcp.tools.project_list_tool.ProjectRegistry", lambda: reg)
    result = asyncio.run(project_list_tool.execute({}))
    assert "hint" not in result


def test_project_list_ungrouped_count(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    for name in ["a", "b"]:
        d = tmp_path / name
        d.mkdir()
        reg.register(str(d))
    monkeypatch.setattr("the_door.mcp.tools.project_list_tool.ProjectRegistry", lambda: reg)
    result = asyncio.run(project_list_tool.execute({}))
    assert result["ungrouped_count"] == 2
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/mcp/tools/test_project_list_tool.py -v 2>&1 | head -15
```

Expected: `KeyError: 'group_id'` 或類似

- [ ] **Step 3: 完整替換 `the_door/src/the_door/mcp/tools/project_list_tool.py`**

```python
"""MCP tool: project_list — list all projects registered in ProjectRegistry."""
from __future__ import annotations

from pathlib import Path

from the_door.core.registry import ProjectRegistry
from the_door.mcp.tools._response_envelope import wrap

TOOL_SCHEMA = {
    "type": "object",
    "properties": {},
}


async def execute(arguments: dict) -> dict:
    """Return all registered projects with group membership from ~/.the-door/registry.json."""
    reg = ProjectRegistry()
    raw_projects = reg.list_projects()
    groups = reg.list_groups()

    # Build group lookup: project_id → {id, name}
    group_by_pid: dict[str, dict] = {}
    for g in groups:
        for m in g["members"]:
            group_by_pid[m["id"]] = {"id": g["id"], "name": g["name"]}

    projects = []
    for p in raw_projects:
        group_info = group_by_pid.get(p["id"])
        projects.append({
            **p,
            "group_id": group_info["id"] if group_info else None,
            "group_name": group_info["name"] if group_info else None,
        })

    ungrouped_count = sum(1 for p in projects if p["group_id"] is None)

    payload: dict = {
        "projects": projects,
        "groups": [
            {"id": g["id"], "name": g["name"], "member_ids": [m["id"] for m in g["members"]]}
            for g in groups
        ],
        "count": len(projects),
        "ungrouped_count": ungrouped_count,
    }

    if ungrouped_count > 0:
        ungrouped_names = [p["name"] for p in projects if p["group_id"] is None]
        payload["hint"] = (
            f"專案 {', '.join(repr(n) for n in ungrouped_names[:3])}"
            + (" 等" if len(ungrouped_names) > 3 else "")
            + " 尚未加入群組。執行 `the-door group add <name> <path>` 建立比較群組。"
        )

    return wrap(payload, project_path=Path.cwd(), context="mcp")
```

- [ ] **Step 4: 確認測試通過**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/mcp/tools/test_project_list_tool.py -v 2>&1 | tail -15
```

Expected: 全部 PASSED

- [ ] **Step 5: Commit**

```bash
cd the_door && git add the_door/src/the_door/mcp/tools/project_list_tool.py the_door/tests/unit/mcp/tools/test_project_list_tool.py
git commit -m "feat(mcp): project_list returns group_id/group_name/groups/ungrouped_count/hint"
```
