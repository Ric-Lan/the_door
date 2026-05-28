"""Tests for --minimal-context Click option in `the-door update`."""
from __future__ import annotations

from click.testing import CliRunner

from the_door.cli.update_cmd import update_cmd


class TestUpdateMinimalContextOption:
    def test_help_shows_minimal_context_flag(self):
        runner = CliRunner()
        result = runner.invoke(update_cmd, ["--help"])
        assert result.exit_code == 0
        assert "--minimal-context" in result.output
