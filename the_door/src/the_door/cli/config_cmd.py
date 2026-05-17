"""CLI command: config — configuration management."""
from __future__ import annotations

import click


@click.group("config")
def config_cmd():
    """Manage The Door configuration."""
    pass


@config_cmd.command("init")
@click.option("--path", type=click.Path(), default=None, help="Custom config file path")
def config_init(path: str | None):
    """Create default config.toml file."""
    from pathlib import Path
    from the_door.core.llm.config_manager import ConfigManager

    config_path = Path(path) if path else None
    created_path = ConfigManager.init_default(config_path)

    click.echo(f"Created config file at: {created_path}")
    click.echo("")
    click.echo("Next steps:")
    click.echo("  1. Edit the config file to add your API key")
    click.echo("  2. Or set environment variables:")
    click.echo("     THE_DOOR_OPENAI_KEY=sk-your-key")
    click.echo("     THE_DOOR_ANTHROPIC_KEY=your-key")
    click.echo("     THE_DOOR_OLLAMA_URL=http://localhost:11434")

    from the_door.cli.post_run_hook import cli_post_run_hook
    cli_post_run_hook(Path.cwd(), json_mode_active=False)
