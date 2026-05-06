"""CLI command: the-door ui <project-path>

Starts a local HTTP server and opens the frontend viewer in the browser.
"""
from __future__ import annotations

import sys
import threading
import webbrowser
from pathlib import Path

import click

from the_door.core.ui.server import UIServer


def _resolve_viewer_dir() -> Path:
    """Resolve the viewer directory relative to this file's location.

    Path: cli/ui_cmd.py → src/the_door/ → src/ → the_door/ → workspace_root
    → docs/frontend-local-version-viewer/viewer/

    NOTE: This assumes editable install (development environment).
    """
    return (
        Path(__file__).parent  # cli/
        .parent                # the_door/
        .parent                # src/
        .parent                # the_door/ (project)
        .parent                # workspace root
        / "docs"
        / "frontend-local-version-viewer"
        / "viewer"
    )


@click.command("ui")
@click.argument("project_path", type=click.Path())
@click.option("--port", default=8765, show_default=True, help="監聽端口")
@click.option("--no-browser", is_flag=True, help="不自動開啟瀏覽器")
def ui_cmd(project_path: str, port: int, no_browser: bool) -> None:
    """啟動本地 UI server，在瀏覽器中開啟版本驗核工作台。

    PROJECT_PATH 應指向含有 .the-door/ 目錄的專案根目錄。
    若 .the-door/ 不存在，server 仍會啟動，API 端點回傳空狀態。

    啟動後按 Ctrl+C 關閉 server。
    """
    # 1. Validate project_path
    root = Path(project_path)
    if not root.exists() or not root.is_dir():
        click.echo(f"錯誤：路徑不存在或不是目錄：{project_path}", err=True)
        sys.exit(1)

    # 2. Resolve viewer_dir
    viewer_dir = _resolve_viewer_dir()
    if not viewer_dir.exists():
        click.echo(
            f"警告：找不到 viewer 目錄：{viewer_dir}（API 仍可用）",
            err=True,
        )
        # Create a minimal placeholder so UIServer doesn't crash
        viewer_dir.mkdir(parents=True, exist_ok=True)

    # 3. Create UIServer
    try:
        server = UIServer(project_root=root, viewer_dir=viewer_dir, port=port)
    except Exception as exc:
        click.echo(f"錯誤：無法建立 server：{exc}", err=True)
        sys.exit(1)

    # 4. Print URL
    click.echo(server.url)

    # 5. Open browser (after a short delay to let server start)
    if not no_browser:
        threading.Timer(0.5, webbrowser.open, [server.url]).start()

    # 6. Start server (blocks until Ctrl+C)
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
