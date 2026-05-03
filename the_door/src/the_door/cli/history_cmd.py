"""CLI command: history — display narrative chain."""
from __future__ import annotations

import click


@click.command("history")
@click.argument("codebase_path", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path")
def history_cmd(codebase_path: str, output: str | None):
    """Display narrative chain in human-readable format."""
    from pathlib import Path
    from the_door.core.reading.narrative_chain import NarrativeChain

    # Look for narrative chain file in the codebase directory
    chain_path = Path(codebase_path) / ".the-door" / "narrative.jsonl"

    if not chain_path.exists():
        click.echo(f"No narrative chain found at {chain_path}")
        click.echo("Run 'the-door analyze' first to create a narrative chain.")
        return

    chain = NarrativeChain(chain_path)
    readable = chain.format_human_readable()

    if output:
        Path(output).write_text(readable, encoding="utf-8")
        click.echo(f"History written to {output}")
    else:
        click.echo(readable)
