"""CLI command group: doubt — doubt management and lifecycle tracking."""
from __future__ import annotations

import json
import sys

import click


@click.group("doubt")
def doubt_group():
    """疑義管理命令群組。"""
    pass


@doubt_group.command("list")
@click.option("--state", default=None, help="依狀態篩選")
@click.option("--type", "doubt_type", default=None, help="依類型篩選")
@click.option("--json", "output_json", is_flag=True, help="輸出 JSON 格式")
@click.option("--codebase-path", type=click.Path(exists=True), default=".", help="Codebase 根目錄路徑")
def doubt_list(state: str | None, doubt_type: str | None, output_json: bool, codebase_path: str):
    """列出所有活躍疑義。doubt_id 縮寫為前 8 字元。"""
    from pathlib import Path
    from the_door.core.scope.doubt_store import DoubtStore

    project_root = Path(codebase_path)
    store = DoubtStore(project_root)

    states = [state] if state else None
    types = [doubt_type] if doubt_type else None

    doubts = store.list_doubts(states=states, types=types)

    from the_door.cli.post_run_hook import cli_post_run_hook

    if output_json:
        data = [_serialize_doubt_brief(d) for d in doubts]
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))
        cli_post_run_hook(codebase_path, json_mode_active=output_json)
        return

    if not doubts:
        click.echo("No doubts found.")
        cli_post_run_hook(codebase_path, json_mode_active=output_json)
        return

    click.echo(f"{'ID':10s} {'State':15s} {'Type':22s} {'Source Node':20s} {'Assigned To':15s} {'Created At':20s}")
    click.echo("-" * 102)
    for d in doubts:
        assigned = d.assigned_to or "-"
        created = d.created_at[:19]
        click.echo(
            f"{d.doubt_id[:8]:10s} {d.current_state:15s} {d.doubt_type:22s} "
            f"{d.source_node:20s} {assigned:15s} {created:20s}"
        )

    cli_post_run_hook(codebase_path, json_mode_active=output_json)


@doubt_group.command("show")
@click.argument("doubt_id")
@click.option("--codebase-path", type=click.Path(exists=True), default=".", help="Codebase 根目錄路徑")
def doubt_show(doubt_id: str, codebase_path: str):
    """顯示疑義完整記錄（含 state_history 和 resolution）。"""
    from pathlib import Path
    from the_door.core.scope.doubt_store import DoubtStore
    from the_door.models import DoubtNotFoundError

    project_root = Path(codebase_path)
    store = DoubtStore(project_root)

    # Support abbreviated doubt_id (prefix match)
    resolved_id = _resolve_doubt_id(store, doubt_id)
    if resolved_id is None:
        click.echo(f"Error: Doubt not found: '{doubt_id}'", err=True)
        sys.exit(1)

    try:
        doubt = store.get_doubt(resolved_id)
    except DoubtNotFoundError:
        click.echo(f"Error: Doubt not found: '{doubt_id}'", err=True)
        sys.exit(1)

    click.echo(f"Doubt ID:      {doubt.doubt_id}")
    click.echo(f"Source Node:   {doubt.source_node}")
    click.echo(f"Type:          {doubt.doubt_type}")
    click.echo(f"State:         {doubt.current_state}")
    click.echo(f"Created By:    {doubt.created_by}")
    click.echo(f"Created At:    {doubt.created_at}")
    click.echo(f"Updated At:    {doubt.updated_at}")
    click.echo(f"Assigned To:   {doubt.assigned_to or '-'}")

    if doubt.state_history:
        click.echo("")
        click.echo("State History:")
        for t in doubt.state_history:
            reason_str = f" — {t.reason}" if t.reason else ""
            click.echo(f"  {t.timestamp[:19]}  {t.from_state} → {t.to_state}  by {t.actor}{reason_str}")

    if doubt.resolution:
        click.echo("")
        click.echo("Resolution:")
        click.echo(f"  Type:        {doubt.resolution.type}")
        click.echo(f"  Description: {doubt.resolution.description}")
        click.echo(f"  Resolved By: {doubt.resolution.resolved_by}")
        click.echo(f"  Resolved At: {doubt.resolution.resolved_at}")

    from the_door.cli.post_run_hook import cli_post_run_hook
    cli_post_run_hook(codebase_path, json_mode_active=False)


@doubt_group.command("assign")
@click.argument("doubt_id")
@click.argument("assignee")
@click.option("--codebase-path", type=click.Path(exists=True), default=".", help="Codebase 根目錄路徑")
def doubt_assign(doubt_id: str, assignee: str, codebase_path: str):
    """指派調查者（discovered → investigating）。"""
    from pathlib import Path
    from the_door.core.scope.doubt_store import DoubtStore
    from the_door.models import DoubtNotFoundError, InvalidTransitionError, DoubtTerminalError

    project_root = Path(codebase_path)
    store = DoubtStore(project_root)

    resolved_id = _resolve_doubt_id(store, doubt_id)
    if resolved_id is None:
        click.echo(f"Error: Doubt not found: '{doubt_id}'", err=True)
        sys.exit(1)

    try:
        doubt = store.assign(resolved_id, assignee, actor=assignee)
        click.echo(f"Doubt {doubt.doubt_id[:8]} assigned to {assignee} (state: {doubt.current_state})")
        from the_door.cli.post_run_hook import cli_post_run_hook
        cli_post_run_hook(codebase_path, json_mode_active=False)
    except DoubtNotFoundError:
        click.echo(f"Error: Doubt not found: '{doubt_id}'", err=True)
        sys.exit(1)
    except DoubtTerminalError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except InvalidTransitionError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@doubt_group.command("resolve")
@click.argument("doubt_id")
@click.option("--as", "resolution_type", required=True,
              type=click.Choice(["explained", "fixed", "accepted_risk"]),
              help="解決類型")
@click.option("--reason", required=True, help="解決原因說明")
@click.option("--codebase-path", type=click.Path(exists=True), default=".", help="Codebase 根目錄路徑")
def doubt_resolve(doubt_id: str, resolution_type: str, reason: str, codebase_path: str):
    """解決疑義。狀態分派邏輯依 current_state 決定。"""
    from pathlib import Path
    from the_door.core.scope.doubt_store import DoubtStore
    from the_door.models import DoubtNotFoundError, InvalidTransitionError, DoubtTerminalError

    project_root = Path(codebase_path)
    store = DoubtStore(project_root)

    resolved_id = _resolve_doubt_id(store, doubt_id)
    if resolved_id is None:
        click.echo(f"Error: Doubt not found: '{doubt_id}'", err=True)
        sys.exit(1)

    try:
        doubt = store.get_doubt(resolved_id)
    except DoubtNotFoundError:
        click.echo(f"Error: Doubt not found: '{doubt_id}'", err=True)
        sys.exit(1)

    try:
        # State-based dispatch
        if doubt.current_state == "investigating" and resolution_type == "explained":
            updated = store.explain(resolved_id, reason, resolved_by="cli_user")
        elif doubt.current_state == "investigating" and resolution_type == "fixed":
            updated = store.fix(resolved_id, reason, resolved_by="cli_user")
        elif doubt.current_state == "escalated":
            updated = store.resolve_escalation(resolved_id, resolution_type, reason, resolved_by="cli_user")
        else:
            click.echo(
                f"Error: Cannot resolve as '{resolution_type}' from state '{doubt.current_state}'. "
                f"Expected: investigating + explained/fixed, or escalated + any resolution type.",
                err=True,
            )
            sys.exit(1)

        click.echo(f"Doubt {updated.doubt_id[:8]} resolved as {resolution_type} (state: {updated.current_state})")
        from the_door.cli.post_run_hook import cli_post_run_hook
        cli_post_run_hook(codebase_path, json_mode_active=False)
    except DoubtTerminalError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except InvalidTransitionError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@doubt_group.command("escalate")
@click.argument("doubt_id")
@click.option("--reason", required=True, help="升級原因")
@click.option("--codebase-path", type=click.Path(exists=True), default=".", help="Codebase 根目錄路徑")
def doubt_escalate(doubt_id: str, reason: str, codebase_path: str):
    """手動升級疑義至管理層。"""
    from pathlib import Path
    from the_door.core.scope.doubt_store import DoubtStore
    from the_door.models import DoubtNotFoundError, InvalidTransitionError, DoubtTerminalError

    project_root = Path(codebase_path)
    store = DoubtStore(project_root)

    resolved_id = _resolve_doubt_id(store, doubt_id)
    if resolved_id is None:
        click.echo(f"Error: Doubt not found: '{doubt_id}'", err=True)
        sys.exit(1)

    try:
        doubt = store.escalate(resolved_id, reason, actor="cli_user")
        click.echo(f"Doubt {doubt.doubt_id[:8]} escalated (state: {doubt.current_state})")
        from the_door.cli.post_run_hook import cli_post_run_hook
        cli_post_run_hook(codebase_path, json_mode_active=False)
    except DoubtNotFoundError:
        click.echo(f"Error: Doubt not found: '{doubt_id}'", err=True)
        sys.exit(1)
    except DoubtTerminalError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except InvalidTransitionError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_doubt_id(store, doubt_id: str) -> str | None:
    """Resolve a possibly abbreviated doubt_id to a full UUID.

    If doubt_id is a full UUID, return it directly.
    Otherwise, search all doubts for a prefix match.
    Returns None if no match or ambiguous.
    """
    from the_door.models import DoubtNotFoundError

    # Try direct lookup first
    try:
        store.get_doubt(doubt_id)
        return doubt_id
    except DoubtNotFoundError:
        pass

    # Try prefix match
    all_doubts = store.list_doubts()
    matches = [d for d in all_doubts if d.doubt_id.startswith(doubt_id)]
    if len(matches) == 1:
        return matches[0].doubt_id
    return None


def _serialize_doubt_brief(doubt) -> dict:
    """Serialize a DoubtRecord to a brief JSON-compatible dict."""
    data: dict = {
        "doubt_id": doubt.doubt_id,
        "source_node": doubt.source_node,
        "doubt_type": doubt.doubt_type,
        "current_state": doubt.current_state,
        "created_by": doubt.created_by,
        "created_at": doubt.created_at,
        "updated_at": doubt.updated_at,
        "assigned_to": doubt.assigned_to,
    }
    if doubt.state_history:
        data["state_history"] = [
            {
                "from_state": t.from_state,
                "to_state": t.to_state,
                "timestamp": t.timestamp,
                "actor": t.actor,
                "reason": t.reason,
            }
            for t in doubt.state_history
        ]
    if doubt.resolution:
        data["resolution"] = {
            "type": doubt.resolution.type,
            "description": doubt.resolution.description,
            "resolved_by": doubt.resolution.resolved_by,
            "resolved_at": doubt.resolution.resolved_at,
        }
    return data
