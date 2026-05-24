"""`the-door status` — report current project state + suggested next actions."""
from __future__ import annotations

import os
from pathlib import Path

import click

from the_door.cli.next_action_renderer import render_next_block
from the_door.core.guidance.state import StateInspector
from the_door.core.guidance.suggester import NextActionSuggester


def _get_unanalyzed_git_tags(project_path: Path, store) -> list[str]:
    """Return git tags that have no corresponding snapshot."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "tag", "--list"],
            cwd=project_path, capture_output=True, text=True, timeout=5,
        )
        tags = [t.strip() for t in result.stdout.splitlines() if t.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []

    if not tags:
        return []

    try:
        snapshots = store.list_snapshots()
    except Exception:
        return []
    existing_labels = {s.label for s in snapshots if s.label}
    existing_tags = {t for s in snapshots for t in (s.git_tags or [])}
    analyzed = existing_labels | existing_tags
    return [t for t in tags if t not in analyzed]


@click.command("status")
@click.argument(
    "path",
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
    default=".",
)
def status_cmd(path: str) -> None:
    """Report current project state + suggested next actions."""
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    from the_door.core.diff.snapshot_store import SnapshotStore
    from the_door.core.flow_guard import CheckpointOption, FlowGuard
    from the_door.core.project_identity import ProjectIdentity
    from the_door.cli.checkpoint_renderer import CheckpointRenderer

    guard = FlowGuard()
    renderer = CheckpointRenderer(guard)

    project = Path(path).resolve()
    store = SnapshotStore(project)

    # CHECKPOINT: project-not-initialized
    id_result = ProjectIdentity.resolve_store_root(project)
    if id_result.status == "not_found":
        decision = guard.check(
            "project-not-initialized",
            "專案尚未初始化（無 project.id，無舊版 store）",
            options=[
                CheckpointOption("A", "初始化並開始分析（MCP）",
                    "extract_structure(codebase_path='<path>')"),
                CheckpointOption("B", "僅顯示現有狀態，不初始化"),
            ],
        )
        try:
            choice = renderer.prompt(decision)
        except EOFError:
            choice = "B"  # non-interactive: default to show status
        if choice == "A":
            raise SystemExit(0)

    state = StateInspector(project).inspect()

    click.echo(f"Project: {project.as_posix()}")
    if state.has_dot_the_door:
        click.echo(f"  ✓ {len(state.snapshots)} snapshots")
        for s in state.snapshots:
            marker = "✓ has structure" if s.has_persisted_structure else "○ no structure"
            label = s.label or s.version_id
            click.echo(f"    • {label}  ({marker})")
    else:
        click.echo("  ○ not yet initialized")
    for warning in state.warnings:
        click.echo(f"  ⚠ {warning.code}: {warning.message}")
    click.echo("")

    actions = NextActionSuggester().suggest(state, context="cli")
    render_next_block(actions)

    # CHECKPOINT: unanalyzed-versions-detected
    unanalyzed = _get_unanalyzed_git_tags(project, store)
    if unanalyzed:
        decision = guard.check(
            "unanalyzed-versions-detected",
            f"偵測到 {len(unanalyzed)} 個 git tag 尚無 snapshot：{', '.join(unanalyzed[:3])}",
            options=[
                CheckpointOption("A", f"為 {unanalyzed[0]} 建立 snapshot",
                    f"extract_structure(codebase_path='{path}')"),
                CheckpointOption("B", "略過，結束"),
            ],
        )
        try:
            renderer.prompt(decision)
        except EOFError:
            pass  # non-interactive environment: skip CHECKPOINT interaction
