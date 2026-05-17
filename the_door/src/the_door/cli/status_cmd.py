"""`the-door status` — report current project state + suggested next actions."""
from __future__ import annotations

import sys
from pathlib import Path

import click

from the_door.cli.next_action_renderer import render_next_block
from the_door.core.guidance.state import StateInspector
from the_door.core.guidance.suggester import NextActionSuggester


@click.command("status")
@click.argument(
    "path",
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
    default=".",
)
def status_cmd(path: str) -> None:
    """Report current project state + suggested next actions."""
    project = Path(path).resolve()
    state = StateInspector(project).inspect()

    sys.stdout.write(f"Project: {project.as_posix()}\n")
    if state.has_dot_the_door:
        sys.stdout.write(f"  ✓ {len(state.snapshots)} snapshots\n")
        for s in state.snapshots:
            marker = "✓ has structure" if s.has_persisted_structure else "○ no structure"
            label = s.label or s.version_id
            sys.stdout.write(f"    • {label}  ({marker})\n")
    else:
        sys.stdout.write("  ○ not yet initialized\n")
    for warning in state.warnings:
        sys.stdout.write(f"  ⚠ {warning.code}: {warning.message}\n")
    sys.stdout.write("\n")

    actions = NextActionSuggester().suggest(state, context="cli")
    render_next_block(actions)
