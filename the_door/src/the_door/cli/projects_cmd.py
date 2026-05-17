"""CLI command: the-door projects — list all registered projects."""
from __future__ import annotations

import click

from the_door.core.registry import ProjectRegistry


@click.command("projects")
def projects_cmd() -> None:
    """列出所有已在 The Door 登記的專案。"""
    from pathlib import Path
    from the_door.cli.post_run_hook import cli_post_run_hook

    projects = ProjectRegistry().list_projects()
    if not projects:
        click.echo("尚無登記的專案。執行 the-door ui <path> 或 the-door analyze <path> 後自動登記。")
        cli_post_run_hook(Path.cwd(), json_mode_active=False)
        return

    click.echo(f"{'ID':<6} {'名稱':<20} 路徑")
    click.echo("─" * 60)
    for p in projects:
        click.echo(f"{p['id']:<6} {p['name']:<20} {p['path']}")

    cli_post_run_hook(Path.cwd(), json_mode_active=False)
