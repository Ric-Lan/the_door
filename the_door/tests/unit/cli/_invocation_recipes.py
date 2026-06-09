"""Minimal CLI invocation recipes for the post-run-hook meta-test.

Each entry maps a command_name -> a callable that takes a tmp_path and returns
a (args_list, machine_flag_or_None) tuple. ``args_list`` is the list passed to
``CliRunner.invoke(main, [command_name, ...])``.

Grouped subcommands use a dotted key (e.g. ``"snapshot.list"``); the meta-test
splits them into individual click args.

The spec design **expects** many recipes to fail/skip due to the minimal seed
state of an empty tmp_path — that's fine. The meta-test skips when the command
exits non-zero. The point is to have every command listed here so the dict
itself documents the coverage surface.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

Recipe = Callable[[Path], tuple[list[str], str | None]]


def _path_only(tmp_path: Path) -> tuple[list[str], str | None]:
    return [str(tmp_path)], None


def _path_only_with_json_flag(tmp_path: Path) -> tuple[list[str], str | None]:
    return [str(tmp_path)], "--json"


def _no_args(tmp_path: Path) -> tuple[list[str], str | None]:
    return [], None


def _diff_args(tmp_path: Path) -> tuple[list[str], str | None]:
    # diff requires --baseline; will likely fail on empty tmp (no snapshots) → skip path
    return [str(tmp_path), "--baseline", "v0.0.0"], "--json"


def _validate_args(tmp_path: Path) -> tuple[list[str], str | None]:
    # validate takes two file paths; pass missing files → command will exit(1) → skip
    return [str(tmp_path / "missing-output.json"), str(tmp_path / "missing-structure.json")], None


def _scan_args(tmp_path: Path) -> tuple[list[str], str | None]:
    return [str(tmp_path)], "--json"


def _history_args(tmp_path: Path) -> tuple[list[str], str | None]:
    return [str(tmp_path)], None


def _render_args(tmp_path: Path) -> tuple[list[str], str | None]:
    # render needs an input file; pass a missing one → click will exit (no machine flag)
    return [str(tmp_path / "input.json")], None


def _timeline_args(tmp_path: Path) -> tuple[list[str], str | None]:
    return [str(tmp_path)], "--json"


def _config_init_args(tmp_path: Path) -> tuple[list[str], str | None]:
    target = tmp_path / "config.toml"
    return ["--path", str(target)], None


def _snapshot_list_args(tmp_path: Path) -> tuple[list[str], str | None]:
    return [str(tmp_path)], None


def _snapshot_create_args(tmp_path: Path) -> tuple[list[str], str | None]:
    return [str(tmp_path), "--label", "test-label"], None


def _snapshot_prune_args(tmp_path: Path) -> tuple[list[str], str | None]:
    return [str(tmp_path), "--dry-run"], None


def _scope_list_args(tmp_path: Path) -> tuple[list[str], str | None]:
    return ["--codebase-path", str(tmp_path)], None


def _scope_show_args(tmp_path: Path) -> tuple[list[str], str | None]:
    return ["missing-scope", "--codebase-path", str(tmp_path)], None


def _scope_create_args(tmp_path: Path) -> tuple[list[str], str | None]:
    return ["test-scope", "--codebase-path", str(tmp_path)], None


def _scope_verify_args(tmp_path: Path) -> tuple[list[str], str | None]:
    return [str(tmp_path), "--scope", "missing-scope"], "--json"


def _doubt_list_args(tmp_path: Path) -> tuple[list[str], str | None]:
    return ["--codebase-path", str(tmp_path)], "--json"


def _doubt_show_args(tmp_path: Path) -> tuple[list[str], str | None]:
    return ["deadbeef", "--codebase-path", str(tmp_path)], None


def _doubt_assign_args(tmp_path: Path) -> tuple[list[str], str | None]:
    return ["deadbeef", "alice", "--codebase-path", str(tmp_path)], None


def _doubt_resolve_args(tmp_path: Path) -> tuple[list[str], str | None]:
    return [
        "deadbeef", "--as", "explained", "--reason", "test",
        "--codebase-path", str(tmp_path),
    ], None


def _doubt_escalate_args(tmp_path: Path) -> tuple[list[str], str | None]:
    return ["deadbeef", "--reason", "test", "--codebase-path", str(tmp_path)], None


RECIPES: dict[str, Recipe] = {
    # status is the canary — exercises success path on a minimal tmp_path.
    "status": _path_only,
    # projects has no required args; will succeed listing zero projects.
    "projects": _no_args,
    # The rest are spec-design-skips on minimal seed.
    "extract": _path_only,
    "diff": _diff_args,
    "validate": _validate_args,
    "scan": _scan_args,
    "history": _history_args,
    "render": _render_args,
    "timeline": _timeline_args,
    "config.init": _config_init_args,
    "snapshot.list": _snapshot_list_args,
    "snapshot.create": _snapshot_create_args,
    "snapshot.prune": _snapshot_prune_args,
    "scope.list": _scope_list_args,
    "scope.show": _scope_show_args,
    "scope.create": _scope_create_args,
    "scope.verify": _scope_verify_args,
    "doubt.list": _doubt_list_args,
    "doubt.show": _doubt_show_args,
    "doubt.assign": _doubt_assign_args,
    "doubt.resolve": _doubt_resolve_args,
    "doubt.escalate": _doubt_escalate_args,
}
