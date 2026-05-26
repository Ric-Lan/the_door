"""CLI command: the-door ui [project-path]

Starts a local HTTP server and opens the frontend viewer in the browser.
If no path is given, shows an interactive project picker from the registry.
"""
from __future__ import annotations

import sys
import threading
import webbrowser
from pathlib import Path

import click

from the_door.core.registry import ProjectRegistry
from the_door.core.ui.server import UIServer


def _resolve_viewer_dir() -> Path:
    return (
        Path(__file__).parent
        .parent
        .parent
        .parent
        .parent
        / "docs"
        / "frontend-local-version-viewer"
        / "viewer"
    )


def _resolve_project_choice(projects: list[dict], choice: str) -> str:
    """Pure: resolve user input to a project path.

    Tries id lookup first; falls back to treating choice as a direct path.
    """
    match = next((p for p in projects if p["id"] == choice), None)
    return match["path"] if match else choice


def _pick_project_interactively() -> str | None:
    """Show registered projects and prompt user to pick one. Returns path or None."""
    projects = ProjectRegistry().list_projects()
    if not projects:
        click.echo("尚無登記的專案。請提供路徑：the-door ui <path>", err=True)
        return None

    click.echo("\nThe Door — 可用專案")
    click.echo("─" * 55)
    for p in projects:
        click.echo(f"  {p['id']}  {p['name']:<20} {p['path']}")
    click.echo("─" * 55)

    default_id = projects[0]["id"]
    choice = click.prompt("輸入序號或直接輸入路徑", default=default_id)
    return _resolve_project_choice(projects, choice)


@click.command("ui")
@click.argument("project_path", required=False, default=None, type=click.Path())
@click.option("--port", default=8765, show_default=True, help="監聽端口")
@click.option("--no-browser", is_flag=True, help="不自動開啟瀏覽器")
def ui_cmd(project_path: str | None, port: int, no_browser: bool) -> None:
    """啟動本地 UI server，在瀏覽器中開啟版本驗核工作台。

    PROJECT_PATH 可省略——省略時從已登記的專案中互動選擇。
    帶路徑時自動登記該專案。啟動後按 Ctrl+C 關閉 server。
    """
    if project_path is None:
        project_path = _pick_project_interactively()
        if project_path is None:
            sys.exit(1)

    root = Path(project_path)
    if not root.exists() or not root.is_dir():
        click.echo(f"錯誤：路徑不存在或不是目錄：{project_path}", err=True)
        sys.exit(1)

    ProjectRegistry().register(str(root))

    viewer_dir = _resolve_viewer_dir()
    if not viewer_dir.exists():
        click.echo(f"警告：找不到 viewer 目錄：{viewer_dir}（API 仍可用）", err=True)
        viewer_dir.mkdir(parents=True, exist_ok=True)

    try:
        server = UIServer(project_root=root, viewer_dir=viewer_dir, port=port)
    except Exception as exc:
        click.echo(f"錯誤：無法建立 server：{exc}", err=True)
        sys.exit(1)

    click.echo(server.url)

    if not no_browser:
        wizard_url = server.url.rstrip("/") + "/wizard.html"
        threading.Timer(0.5, webbrowser.open, [wizard_url]).start()

    try:
        server.start()
    except OSError as exc:
        import errno
        if exc.errno == errno.EADDRINUSE:
            click.echo(f"錯誤：端口 {port} 已被佔用，請使用 --port 指定其他端口", err=True)
        else:
            click.echo(f"錯誤：無法啟動 server：{exc}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        server.shutdown()
        sys.exit(0)
