"""Main CLI entry point using click. Registers all commands."""

import sys

import click

from the_door.cli.next_action_renderer import render_remediation
from the_door.core.guidance.remediation import Remediation

from the_door.cli.extract_cmd import extract_cmd
from the_door.cli.validate_cmd import validate_cmd
from the_door.cli.mcp_serve_cmd import mcp_serve_cmd
from the_door.cli.render_cmd import render_cmd
from the_door.cli.history_cmd import history_cmd
from the_door.cli.diff_cmd import diff_cmd
from the_door.cli.snapshot_cmd import snapshot_group
from the_door.cli.scan_cmd import scan_cmd
from the_door.cli.scope_cmd import scope_group
from the_door.cli.doubt_cmd import doubt_group
from the_door.cli.timeline_cmd import timeline_cmd
from the_door.cli.ui_cmd import ui_cmd
from the_door.cli.projects_cmd import projects_cmd
from the_door.cli.group_cmd import group_group
from the_door.cli.status_cmd import status_cmd
from the_door.cli.verify_datamodel_cmd import verify_datamodel_cmd
from the_door.cli.locate_cmd import locate_group


class CliRemediableError(click.ClickException):
    """A CLI error carrying a Remediation envelope (Task 04.4, S1.3 + F3).

    Click invokes ``.show()`` on uncaught ``ClickException`` instances; we route
    that through ``render_remediation`` so every domain error renders as the
    same F3-style ``Error: <msg>`` + optional ``Try: <next-action>`` block to
    stderr.
    """

    exit_code = 1

    def __init__(self, remediation: Remediation):
        super().__init__(remediation.message)
        self.remediation = remediation

    def show(self, file=None):  # noqa: ARG002 — click signature
        render_remediation(self.remediation)


def _force_utf8_io() -> None:
    """Make stdout/stderr UTF-8 so the CLI's non-ASCII output (✓ ⚠ 中文…) never
    raises UnicodeEncodeError on a legacy code-page stream (e.g. Windows cp950 /
    Big5 when stdout is piped). The Door's CLI emits bilingual + symbol output;
    on a redirected cp950 stream ``click.echo`` would crash (handoff #1).

    Reconfiguring at this single entry funnel fixes all subcommand-dispatched
    echo sites at once. ``errors="backslashreplace"`` is a belt-and-suspenders
    fallback so output degrades instead of crashing if utf-8 ever can't apply.
    Streams that are not a reconfigurable ``TextIOWrapper`` (pytest capture,
    certain redirections) are skipped — the fix itself never raises. Called from
    the group callback (runtime), not import time, so importing this module
    during test collection does not mutate captured streams.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError):
            pass


@click.group()
def main():
    """The Door — LLM constraint pipeline for code structure extraction and validation."""
    _force_utf8_io()


main.add_command(extract_cmd)
main.add_command(validate_cmd)
main.add_command(mcp_serve_cmd)
main.add_command(render_cmd)
main.add_command(history_cmd)
main.add_command(diff_cmd)
main.add_command(snapshot_group)
main.add_command(scan_cmd)
main.add_command(scope_group)
main.add_command(doubt_group)
main.add_command(timeline_cmd)
main.add_command(ui_cmd)
main.add_command(projects_cmd)
main.add_command(group_group)
main.add_command(status_cmd)
main.add_command(verify_datamodel_cmd)
main.add_command(locate_group)
