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
