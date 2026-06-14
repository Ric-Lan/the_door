"""CLI command: the-door ui [project-path]

Starts a local HTTP server and opens the frontend viewer in the browser.
If no path is given, auto-detects active project or shows an interactive picker.
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
    """Auto-detect or interactively pick a project. Returns path or None.

    Priority:
    1. Active project: checklist.json mtime > last_opened_at (analysis since last UI session)
    2. Most recently opened: last_opened_at timestamp
    3. Interactive picker: grouped view with group structure
    """
    reg = ProjectRegistry()
    projects = reg.list_projects()
    if not projects:
        click.echo("尚無登記的專案。請提供路徑：the-door ui <path>", err=True)
        return None

    # Priority 1: actively being analyzed
    active = reg.find_active_project()
    if active:
        click.echo(f"✓ 偵測到正在分析的專案：{active['name']}（{active['path']}）")
        return active["path"]

    # Priority 2: most recently opened
    recent = reg.get_most_recently_opened()
    default_id = recent["id"] if recent else projects[0]["id"]

    # Priority 3: interactive picker with group structure
    groups = reg.list_groups()
    grouped_ids = {m["id"] for g in groups for m in g["members"]}

    click.echo("\nThe Door — 可用專案\n")
    for g in groups:
        click.echo(f"  群組: {g['name']} [{g['id']}]")
        for m in g["members"]:
            click.echo(f"    {m['id']}  {m['name']:<20} {m['path']}")
        click.echo()

    ungrouped = [p for p in projects if p["id"] not in grouped_ids]
    if ungrouped:
        click.echo("  未分群:")
        for p in ungrouped:
            click.echo(f"    {p['id']}  {p['name']:<20} {p['path']}")
        click.echo()

    click.echo("─" * 55)
    choice = click.prompt("輸入序號或直接輸入路徑", default=default_id)
    return _resolve_project_choice(projects, choice)


@click.command("ui")
@click.argument("project_path", required=False, default=None, type=click.Path())
@click.option("--port", default=8765, show_default=True, help="監聽端口")
@click.option("--no-browser", is_flag=True, help="不自動開啟瀏覽器")
def ui_cmd(project_path: str | None, port: int, no_browser: bool) -> None:
    """啟動本地 UI server，在瀏覽器中開啟版本驗核工作台。

    PROJECT_PATH 可省略——省略時自動偵測或從已登記的專案中互動選擇。
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

    # UIServer.__init__ binds the port; reaching here means the port is available.
    # Record last_opened_at so find_active_project() can detect future analysis.
    ProjectRegistry().update_last_opened(str(root))

    click.echo(server.url)

    if not no_browser:
        landing_url = server.url.rstrip("/") + "/index.html"
        threading.Timer(0.5, webbrowser.open, [landing_url]).start()

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
