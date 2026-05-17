"""CLI commands: snapshot — manage version snapshots."""
from __future__ import annotations

import json
import logging
import sys

import click

logger = logging.getLogger(__name__)


@click.group("snapshot")
def snapshot_group():
    """Manage version snapshots."""
    pass


@snapshot_group.command("create")
@click.argument("codebase_path", type=click.Path(exists=True), default=".")
@click.option("--label", required=True, help="Human-readable snapshot label")
def snapshot_create(codebase_path, label):
    """Create a manual snapshot from the most recent analysis output."""
    from pathlib import Path
    from the_door.core.diff.snapshot_store import SnapshotStore
    from the_door.models import SnapshotError

    store = SnapshotStore(Path(codebase_path))

    # Get the latest snapshot to use as source for manual snapshot
    latest = store.get_latest()
    if latest is None:
        click.echo("No analysis output found. Run `the-door analyze` first.", err=True)
        sys.exit(1)

    # Create manual snapshot from latest data
    try:
        snapshot = store.create_snapshot(
            l1_snapshot=latest.l1_snapshot,
            feature_relations=latest.feature_relations_snapshot,
            analyzed_files=latest.analyzed_files,
            commit_hash=latest.commit_hash,
            git_tags=latest.git_tags,
            trigger="manual",
            label=label,
            l1_5_snapshot=latest.l1_5_snapshot if latest.l1_5_snapshot else None,
        )
    except SnapshotError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"Snapshot created: {snapshot.version_id}")
    click.echo(f"Label: {label}")

    from the_door.cli.post_run_hook import cli_post_run_hook
    cli_post_run_hook(codebase_path, json_mode_active=False)


@snapshot_group.command("list")
@click.argument("codebase_path", type=click.Path(exists=True), default=".")
def snapshot_list(codebase_path):
    """List all available snapshots."""
    from pathlib import Path
    from the_door.core.diff.snapshot_store import SnapshotStore

    store = SnapshotStore(Path(codebase_path))
    snapshots = store.list_snapshots()

    from the_door.cli.post_run_hook import cli_post_run_hook

    if not snapshots:
        click.echo("No snapshots found.")
        cli_post_run_hook(codebase_path, json_mode_active=False)
        return

    # Table header
    click.echo(f"{'ID':<10} {'Timestamp':<26} {'Trigger':<8} {'Git Tags':<20} {'Label'}")
    click.echo("-" * 90)

    for snap in snapshots:
        short_id = snap.version_id[:8]
        tags = ", ".join(snap.git_tags) if snap.git_tags else ""
        label_str = snap.label or ""
        click.echo(f"{short_id:<10} {snap.timestamp:<26} {snap.trigger:<8} {tags:<20} {label_str}")

    cli_post_run_hook(codebase_path, json_mode_active=False)


@snapshot_group.command("prune")
@click.argument("codebase_path", type=click.Path(exists=True), default=".")
@click.option("--dry-run", is_flag=True, help="僅顯示將被刪除的 snapshot，不實際刪除")
@click.option("--force", is_flag=True, help="跳過確認直接執行刪除")
@click.option("--max", "max_snapshots", type=int, default=None, help="覆蓋 max_snapshots 設定")
def snapshot_prune(codebase_path, dry_run, force, max_snapshots):
    """根據保留策略清理過期的 snapshot。"""
    from pathlib import Path

    from the_door.core.diff.snapshot_store import SnapshotStore
    from the_door.core.timeline.retention_engine import RetentionEngine

    store = SnapshotStore(Path(codebase_path))
    snapshots = store.list_snapshots()

    # Load retention config from .the-door/retention-config.json
    default_max = 50
    default_enabled = True
    config_path = Path(codebase_path) / ".the-door" / "retention-config.json"

    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            config_max = data.get("max_snapshots", default_max)
            config_enabled = data.get("enabled", default_enabled)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to parse retention-config.json: %s — using defaults",
                exc,
            )
            config_max = default_max
            config_enabled = default_enabled
    else:
        config_max = default_max
        config_enabled = default_enabled

    # --max flag overrides config value
    effective_max = max_snapshots if max_snapshots is not None else config_max

    engine = RetentionEngine()
    decision = engine.compute_retention(
        snapshots, max_snapshots=effective_max, enabled=config_enabled
    )

    from the_door.cli.post_run_hook import cli_post_run_hook

    if not decision.to_remove:
        click.echo("所有快照均在保留範圍內")
        cli_post_run_hook(codebase_path, json_mode_active=False)
        return

    # Build a lookup for display
    snap_map = {s.version_id: s for s in snapshots}

    # Display list of snapshots to be removed
    click.echo(f"將刪除 {len(decision.to_remove)} 個快照：")
    click.echo(
        f"{'ID':<10} {'Timestamp':<26} {'Trigger':<8} {'Label'}"
    )
    click.echo("-" * 70)
    for vid in decision.to_remove:
        snap = snap_map.get(vid)
        if snap:
            short_id = snap.version_id[:8]
            label_str = snap.label or ""
            click.echo(
                f"{short_id:<10} {snap.timestamp:<26} {snap.trigger:<8} {label_str}"
            )

    if dry_run:
        cli_post_run_hook(codebase_path, json_mode_active=False)
        return

    if not force:
        if not click.confirm("確認刪除？"):
            click.echo("已取消")
            cli_post_run_hook(codebase_path, json_mode_active=False)
            return

    for vid in decision.to_remove:
        store.delete_snapshot(vid)

    click.echo(f"已刪除 {len(decision.to_remove)} 個快照")

    cli_post_run_hook(codebase_path, json_mode_active=False)
