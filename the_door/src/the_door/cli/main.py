"""Main CLI entry point using click. Registers all commands."""

import click

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
