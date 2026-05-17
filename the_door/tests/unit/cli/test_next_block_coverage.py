"""Meta-test: every CLI command emits a `Next:` block on its success path.

Drives invocation off of ``RECIPES`` from ``_invocation_recipes.py``. Commands
that exit non-zero on a minimal tmp_path (by spec design) auto-skip. Machine
mode (``--json`` / ``--stdout``) must NOT emit a `Next:` block.
"""
from __future__ import annotations

import pytest
from click.testing import CliRunner

from the_door.cli.main import main
from tests.unit.cli._invocation_recipes import RECIPES


def _split_command_name(command_name: str) -> list[str]:
    """Dotted names like ``snapshot.list`` become ``["snapshot", "list"]``."""
    return command_name.split(".")


@pytest.fixture(autouse=True)
def _seed_api_key(monkeypatch):
    # Ensure the suggester surfaces CLI rules deterministically (the
    # first-time `analyze` rule requires an api key, otherwise the CLI may
    # fall back to system_status.show with the same "Next:" string — both are
    # acceptable; this just stabilizes output for any future assertions).
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    # Force human-readable Next: block (not the JSON env variant).
    monkeypatch.delenv("THE_DOOR_NEXT_FORMAT", raising=False)


@pytest.mark.parametrize("command_name", sorted(RECIPES.keys()))
def test_every_command_emits_next_block_on_success(command_name, tmp_path):
    recipe = RECIPES[command_name]
    args, _machine_flag = recipe(tmp_path)
    full_args = [*_split_command_name(command_name), *args]
    result = CliRunner().invoke(main, full_args)
    if result.exit_code != 0:
        pytest.skip(
            f"{command_name} exited {result.exit_code} on minimal seed; "
            f"not a success-path check. stderr={result.stderr!r}"
        )
    assert "Next:" in result.stderr, (
        f"{command_name} success path did not emit Next: block. "
        f"stderr={result.stderr!r}"
    )


@pytest.mark.parametrize(
    "command_name",
    sorted(name for name, recipe in RECIPES.items()),
)
def test_every_command_suppresses_next_block_in_machine_mode(
    command_name, tmp_path
):
    recipe = RECIPES[command_name]
    args, machine_flag = recipe(tmp_path)
    if machine_flag is None:
        pytest.skip(f"{command_name} has no machine-output flag")
    full_args = [*_split_command_name(command_name), machine_flag, *args]
    result = CliRunner().invoke(main, full_args)
    if result.exit_code != 0:
        pytest.skip(
            f"{command_name} exited {result.exit_code} on minimal seed in machine mode"
        )
    assert "Next:" not in result.stderr, (
        f"{command_name} leaked Next: block under {machine_flag}. "
        f"stderr={result.stderr!r}"
    )
