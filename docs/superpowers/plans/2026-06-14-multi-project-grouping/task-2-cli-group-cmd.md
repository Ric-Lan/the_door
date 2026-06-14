# Task 2: CLI — `the-door group` 指令群

**Depends on:** Task 1 (registry.py 新方法必須已存在)

**Files:**
- Create: `the_door/src/the_door/cli/group_cmd.py`
- Create: `the_door/tests/unit/cli/test_group_cmd.py`

---

> **前提**：`the_door/tests/unit/cli/` 目錄可能不存在，先建立：
> ```bash
> cd the_door && mkdir -p tests/unit/cli && touch tests/unit/cli/__init__.py
> ```

- [ ] **Step 1: 新建失敗測試 `the_door/tests/unit/cli/test_group_cmd.py`**

```python
"""Unit tests for `the-door group` CLI commands."""
from __future__ import annotations

import pytest
from click.testing import CliRunner
from pathlib import Path

from the_door.cli.group_cmd import group_group
from the_door.core.registry import ProjectRegistry


@pytest.fixture
def runner():
    return CliRunner()


def test_group_create_prints_confirmation(runner, tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    monkeypatch.setattr("the_door.cli.group_cmd.ProjectRegistry", lambda: reg)
    result = runner.invoke(group_group, ["create", "my-group"])
    assert result.exit_code == 0
    assert "my-group" in result.output
    assert "g001" in result.output


def test_group_create_duplicate_prints_error(runner, tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    reg.create_group("my-group")
    monkeypatch.setattr("the_door.cli.group_cmd.ProjectRegistry", lambda: reg)
    result = runner.invoke(group_group, ["create", "my-group"])
    assert result.exit_code != 0
    assert "已存在" in result.output


def test_group_add_prints_confirmation(runner, tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    proj.mkdir()
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    reg.create_group("grp")
    monkeypatch.setattr("the_door.cli.group_cmd.ProjectRegistry", lambda: reg)
    result = runner.invoke(group_group, ["add", "grp", str(proj)])
    assert result.exit_code == 0
    assert "proj" in result.output


def test_group_add_nonexistent_group_prints_error(runner, tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    proj.mkdir()
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    monkeypatch.setattr("the_door.cli.group_cmd.ProjectRegistry", lambda: reg)
    result = runner.invoke(group_group, ["add", "no-such-group", str(proj)])
    assert result.exit_code != 0
    assert "群組不存在" in result.output


def test_group_list_shows_members(runner, tmp_path, monkeypatch):
    proj = tmp_path / "ms-ts"
    proj.mkdir()
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    reg.create_group("samples")
    reg.add_to_group("samples", str(proj))
    monkeypatch.setattr("the_door.cli.group_cmd.ProjectRegistry", lambda: reg)
    result = runner.invoke(group_group, ["list"])
    assert result.exit_code == 0
    assert "samples" in result.output
    assert "ms-ts" in result.output


def test_group_list_shows_ungrouped(runner, tmp_path, monkeypatch):
    proj = tmp_path / "solo-proj"
    proj.mkdir()
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    reg.register(str(proj))
    monkeypatch.setattr("the_door.cli.group_cmd.ProjectRegistry", lambda: reg)
    result = runner.invoke(group_group, ["list"])
    assert "solo-proj" in result.output
    assert "未分群" in result.output


def test_group_remove_prints_confirmation(runner, tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    proj.mkdir()
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    reg.create_group("grp")
    reg.add_to_group("grp", str(proj))
    monkeypatch.setattr("the_door.cli.group_cmd.ProjectRegistry", lambda: reg)
    result = runner.invoke(group_group, ["remove", "grp", str(proj)])
    assert result.exit_code == 0
    assert "移除" in result.output
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/cli/test_group_cmd.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'the_door.cli.group_cmd'`

- [ ] **Step 3: 新建 `the_door/src/the_door/cli/group_cmd.py`**

```python
"""CLI command group: the-door group — manage project comparison groups."""
from __future__ import annotations

import sys

import click

from the_door.core.registry import ProjectRegistry


@click.group("group")
def group_group() -> None:
    """管理專案比較群組。"""


@group_group.command("create")
@click.argument("name")
def group_create(name: str) -> None:
    """建立比較群組。

    範例：the-door group create language-samples
    """
    try:
        gid = ProjectRegistry().create_group(name)
        click.echo(f"✓ 群組建立：{name}（{gid}）")
        click.echo(f"  下一步：the-door group add {name} <path>")
    except ValueError as exc:
        click.echo(f"⛔ {exc}", err=True)
        sys.exit(1)


@group_group.command("add")
@click.argument("name")
@click.argument("path", type=click.Path())
def group_add(name: str, path: str) -> None:
    """將路徑加入群組（路徑未登記則自動登記）。

    範例：the-door group add language-samples ./ms-ts
    """
    try:
        result = ProjectRegistry().add_to_group(name, path)
        click.echo(f"✓ 已加入群組 '{name}'：{result['project_name']}（{result['project_id']}）")
    except ValueError as exc:
        click.echo(f"⛔ {exc}", err=True)
        sys.exit(1)


@group_group.command("remove")
@click.argument("name")
@click.argument("path", type=click.Path())
def group_remove(name: str, path: str) -> None:
    """從群組移除路徑。

    範例：the-door group remove language-samples ./ms-ts
    """
    try:
        ProjectRegistry().remove_from_group(name, path)
        click.echo(f"✓ 已從群組 '{name}' 移除：{path}")
    except ValueError as exc:
        click.echo(f"⛔ {exc}", err=True)
        sys.exit(1)


@group_group.command("list")
def group_list() -> None:
    """列出所有群組與成員。"""
    reg = ProjectRegistry()
    groups = reg.list_groups()
    all_projects = reg.list_projects()

    grouped_ids = {m["id"] for g in groups for m in g["members"]}
    ungrouped = [p for p in all_projects if p["id"] not in grouped_ids]

    click.echo("\nThe Door — 群組\n")
    if groups:
        for g in groups:
            click.echo(f"  {g['id']}  {g['name']}")
            for m in g["members"]:
                click.echo(f"        {m['id']}  {m['name']:<20} {m['path']}")
            click.echo()
    else:
        click.echo("  （無群組）\n")

    if ungrouped:
        click.echo(f"  未分群（{len(ungrouped)} 個）：")
        for p in ungrouped:
            click.echo(f"        {p['id']}  {p['name']:<20} {p['path']}")
        click.echo()
```

- [ ] **Step 4: 確認測試通過**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/cli/test_group_cmd.py -v 2>&1 | tail -15
```

Expected: 全部 PASSED

- [ ] **Step 5: Commit**

```bash
cd the_door && git add the_door/src/the_door/cli/group_cmd.py the_door/tests/unit/cli/
git commit -m "feat(cli): add 'the-door group' command group (create/add/remove/list)"
```
