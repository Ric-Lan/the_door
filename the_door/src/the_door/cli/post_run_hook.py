"""Post-run hook invoked by every CLI command's success path.

Renders the `Next:` block (or its JSON equivalent) to stderr unless the
caller has activated a machine-output flag (`--json`, `--stdout`, etc.).

The hook is intentionally tolerant: any exception raised while inspecting
state or computing suggestions is swallowed (the command itself already
succeeded — we do not want a guidance failure to flip the exit code or
clutter stderr).
"""
from __future__ import annotations

from pathlib import Path

from the_door.cli.next_action_renderer import render_next_block
from the_door.core.guidance.state import StateInspector
from the_door.core.guidance.suggester import NextActionSuggester


def cli_post_run_hook(
    project_path: Path | str,
    *,
    json_mode_active: bool = False,
) -> None:
    """Emit a `Next:` block (or JSON equivalent) to stderr.

    Args:
        project_path: The project root the command operated on. May be a
            string or Path; falsy/None values are tolerated (treated as cwd).
        json_mode_active: True when the command is producing machine output
            (e.g. ``--json`` / ``--stdout`` flag). Suppresses the hook so
            downstream tooling can parse stdout cleanly.
    """
    if json_mode_active:
        return
    try:
        project = Path(project_path) if project_path else Path.cwd()
        state = StateInspector(project).inspect()
        actions = NextActionSuggester().suggest(state, context="cli")
        if not actions:
            # Don't emit a bare "Next:" header when there's nothing to suggest.
            return
        render_next_block(actions)
    except Exception:  # pragma: no cover - guidance must never break commands
        return
