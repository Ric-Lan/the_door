"""Main CLI entry point using click. Registers all commands."""

import click

from the_door.cli.next_action_renderer import render_remediation
from the_door.core.guidance.remediation import Remediation

from the_door.cli.extract_cmd import extract_cmd
from the_door.cli.validate_cmd import validate_cmd
from the_door.cli.mcp_serve_cmd import mcp_serve_cmd
from the_door.cli.analyze_cmd import analyze_cmd
from the_door.cli.regenerate_cmd import regenerate_cmd
from the_door.cli.render_cmd import render_cmd
from the_door.cli.estimate_cmd import estimate_cmd
from the_door.cli.history_cmd import history_cmd
from the_door.cli.config_cmd import config_cmd
from the_door.cli.diff_cmd import diff_cmd
from the_door.cli.snapshot_cmd import snapshot_group
from the_door.cli.scan_cmd import scan_cmd
from the_door.cli.scope_cmd import scope_group
from the_door.cli.doubt_cmd import doubt_group
from the_door.cli.timeline_cmd import timeline_cmd
from the_door.cli.update_cmd import update_cmd
from the_door.cli.ui_cmd import ui_cmd
from the_door.cli.projects_cmd import projects_cmd
from the_door.cli.status_cmd import status_cmd
from the_door.cli.wizard_cmd import wizard_cmd
from the_door.cli.verify_datamodel_cmd import verify_datamodel_cmd


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


@click.group()
def main():
    """The Door — LLM constraint pipeline for code structure extraction and validation."""
    pass


main.add_command(extract_cmd)
main.add_command(validate_cmd)
main.add_command(mcp_serve_cmd)
main.add_command(analyze_cmd)
main.add_command(regenerate_cmd)
main.add_command(render_cmd)
main.add_command(estimate_cmd)
main.add_command(history_cmd)
main.add_command(config_cmd)
main.add_command(diff_cmd)
main.add_command(snapshot_group)
main.add_command(scan_cmd)
main.add_command(scope_group)
main.add_command(doubt_group)
main.add_command(timeline_cmd)
main.add_command(update_cmd)
main.add_command(ui_cmd)
main.add_command(projects_cmd)
main.add_command(status_cmd)
main.add_command(wizard_cmd)
main.add_command(verify_datamodel_cmd)
