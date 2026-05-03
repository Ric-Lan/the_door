"""CLI command: timeline — display feature evolution timeline."""
from __future__ import annotations

import json
import sys
from datetime import datetime

import click


@click.command("timeline")
@click.argument("codebase_path", type=click.Path(exists=True))
@click.option("--render", is_flag=True, help="輸出 Mermaid 時間軸圖形")
@click.option("--json", "output_json", is_flag=True, help="輸出完整 Timeline_Result JSON")
@click.option("--feature", "feature_id", default=None, help="僅顯示指定功能的演進歷史")
@click.option("--since", default=None, help="僅分析指定日期之後的 snapshot（ISO 8601: YYYY-MM-DD）")
@click.option("-o", "--output", "output_file", type=click.Path(), default=None, help="輸出到檔案（UTF-8 編碼）")
def timeline_cmd(codebase_path, render, output_json, feature_id, since, output_file):
    """顯示功能演進時間軸。"""
    from pathlib import Path
    from the_door.core.diff.snapshot_store import SnapshotStore
    from the_door.core.timeline.timeline_engine import TimelineEngine
    from the_door.core.timeline.timeline_renderer import TimelineRenderer

    store = SnapshotStore(Path(codebase_path))
    snapshots = store.list_snapshots()

    if not snapshots:
        click.echo(
            "尚無版本快照。請先執行 `the-door analyze` 或 `the-door snapshot create`",
            err=True,
        )
        sys.exit(1)

    # Filter by --since if provided
    if since is not None:
        try:
            since_date = datetime.fromisoformat(since)
        except ValueError:
            click.echo(
                f"日期格式錯誤：'{since}'。請使用 ISO 8601 格式（YYYY-MM-DD），例如：2024-01-15",
                err=True,
            )
            sys.exit(1)

        since_str = since_date.isoformat()
        snapshots = [s for s in snapshots if s.timestamp >= since_str]

        if not snapshots:
            click.echo("指定日期之後無版本快照", err=True)
            sys.exit(1)

    engine = TimelineEngine()
    renderer = TimelineRenderer()

    # --feature: single feature detail
    if feature_id is not None:
        ft = engine.analyze_feature(snapshots, feature_id)
        if ft is None:
            # Collect all available feature_ids
            all_ids: set[str] = set()
            for snap in snapshots:
                all_ids.update(snap.l1_snapshot.keys())
            sorted_ids = sorted(all_ids)
            click.echo(
                f"找不到功能 '{feature_id}'。可用的 feature_id：",
                err=True,
            )
            for fid in sorted_ids:
                click.echo(f"  {fid}", err=True)
            sys.exit(1)

        text = renderer.render_feature_detail(ft, snapshots)
        _output(text, output_file)
        return

    # Full timeline analysis
    result = engine.analyze(snapshots)

    if output_json:
        output_data = _serialize_timeline_result(result)
        text = json.dumps(output_data, indent=2, ensure_ascii=False)
    elif render:
        text = renderer.render_mermaid(result)
    else:
        text = renderer.render_text(result)

    _output(text, output_file)


def _output(text: str, output_file: str | None) -> None:
    """Write text to file or stdout."""
    if output_file:
        from pathlib import Path
        Path(output_file).write_text(text, encoding="utf-8")
        click.echo(f"Output written to {output_file}")
    else:
        click.echo(text)


def _serialize_timeline_result(result) -> dict:
    """Serialize TimelineResult to JSON-compatible dict."""
    return {
        "snapshot_count": result.snapshot_count,
        "time_range_start": result.time_range_start,
        "time_range_end": result.time_range_end,
        "feature_timelines": [
            {
                "feature_id": ft.feature_id,
                "first_seen_timestamp": ft.first_seen_timestamp,
                "last_seen_timestamp": ft.last_seen_timestamp,
                "change_count": ft.change_count,
                "current_state": ft.current_state,
                "current_label": ft.current_label,
                "drift_events": [
                    {
                        "snapshot_version_id": ev.snapshot_version_id,
                        "previous_description": ev.previous_description,
                        "new_description": ev.new_description,
                        "timestamp": ev.timestamp,
                    }
                    for ev in ft.drift_events
                ],
            }
            for ft in result.feature_timelines
        ],
        "summary": {
            "active_count": result.summary.active_count,
            "removed_count": result.summary.removed_count,
            "total_drift_events": result.summary.total_drift_events,
        },
    }
