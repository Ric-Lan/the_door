"""CLI command: regenerate — per-node re-analysis."""
from __future__ import annotations

import asyncio
import json

import click


@click.command("regenerate")
@click.argument("feature_id")
@click.option("--accept", is_flag=True, help="Accept the new result immediately")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path")
def regenerate_cmd(feature_id: str, accept: bool, output: str | None):
    """Re-analyze a specific feature node."""
    click.echo(f"Regenerating feature: {feature_id}")
    click.echo("Note: Full regeneration requires an existing analysis result.")
    click.echo("Use 'the-door analyze' first, then regenerate specific features.")

    result = {"feature_id": feature_id, "status": "requires_prior_analysis"}
    json_output = json.dumps(result, indent=2)

    if output:
        from pathlib import Path
        Path(output).write_text(json_output, encoding="utf-8")
    else:
        click.echo(json_output)

    from pathlib import Path
    from the_door.cli.post_run_hook import cli_post_run_hook
    cli_post_run_hook(Path.cwd(), json_mode_active=False)
