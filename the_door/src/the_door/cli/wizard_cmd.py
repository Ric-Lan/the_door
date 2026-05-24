"""`the-door wizard` — interactive single-command analysis flow."""
from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

import click

from the_door.cli.next_action_renderer import render_next_block
from the_door.core.extraction.file_discovery import FileDiscovery
from the_door.core.flow_guard import CheckpointOption, FlowGuard
from the_door.cli.checkpoint_renderer import CheckpointRenderer


def _top_level_summary(files: list) -> dict[str, int]:
    """Count files per top-level directory (or '.' for root-level files)."""
    counts: Counter = Counter()
    for f in files:
        parts = f.path.split("/")
        top = parts[0] if len(parts) > 1 else "."
        counts[top] += 1
    return dict(counts)


@click.command("wizard")
@click.argument(
    "path",
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
    default=".",
)
def wizard_cmd(path: str) -> None:
    """互動式一鍵分析流程：探索目錄 → 排除確認 → 執行分析。"""
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    codebase_path = Path(path).resolve()

    # Step 1: Discover files
    discovery = FileDiscovery()
    files = discovery.discover(str(codebase_path))
    summary = _top_level_summary(files)

    click.echo(f"\n專案路徑：{codebase_path}")
    click.echo(f"偵測到 {len(files)} 個源碼檔案：")
    for dirname, count in sorted(summary.items()):
        click.echo(f"  {dirname}/  ({count} 個檔案)")

    # Step 2: Ask for exclusions
    exclude_input = click.prompt(
        "\n要排除哪些目錄？（逗號分隔，直接 Enter 跳過）",
        default="",
        show_default=False,
    ).strip()

    extra_ignore: list[str] = []
    if exclude_input:
        extra_ignore = [d.strip().rstrip("/") + "/" for d in exclude_input.split(",") if d.strip()]
        files = discovery.discover(str(codebase_path), extra_ignore=extra_ignore)
        summary = _top_level_summary(files)
        click.echo(f"排除後剩餘 {len(files)} 個檔案。")

    # Detect API key
    from the_door.core.llm.config_manager import ConfigManager
    config = ConfigManager.load()
    has_api_key = bool(getattr(config, "api_key", None))
    mode_label = "LLM 分析（API key）" if has_api_key else "MCP 路徑（agent-as-LLM）"

    # Step 3: Checkpoint 1 — 總覽確認
    guard = FlowGuard()
    renderer = CheckpointRenderer(guard)
    decision = guard.check(
        "wizard-start-confirmed",
        f"準備分析 {len(files)} 個檔案，模式：{mode_label}",
        options=[
            CheckpointOption("A", "確認，開始分析"),
            CheckpointOption("B", "中止"),
        ],
    )
    click.echo(f"\n分析計畫：{len(files)} 個檔案 | {mode_label}")
    try:
        chosen = renderer.prompt(decision)
    except EOFError:
        chosen = "B"

    if chosen == "B":
        click.echo("中止。")
        return

    # Step 4: Execute analysis
    if has_api_key:
        _run_with_api(codebase_path, guard, renderer)
    else:
        _print_mcp_hint(codebase_path)


def _run_with_api(
    codebase_path: Path,
    guard: FlowGuard,
    renderer: CheckpointRenderer,
) -> None:
    from the_door.core.pipeline.analyze_pipeline import run_analyze_pipeline
    from the_door.models import AnalyzeConfig
    from the_door.core.diff.snapshot_store import SnapshotStore
    from the_door.core.guidance.state import StateInspector
    from the_door.core.guidance.suggester import NextActionSuggester

    label = click.prompt("快照標籤（例如 v1.0.0）", default="", show_default=False).strip() or None

    # Checkpoint 2 — 覆寫確認
    if label:
        store = SnapshotStore(codebase_path)
        existing_labels = {s.label for s in store.list_snapshots() if s.label}
        if label in existing_labels:
            decision2 = guard.check(
                "wizard-overwrite-confirmed",
                f"已存在標籤 '{label}' 的快照",
                options=[
                    CheckpointOption("A", f"覆寫 '{label}'"),
                    CheckpointOption("B", "另存新標籤"),
                    CheckpointOption("C", "中止"),
                ],
            )
            click.echo(f"\n已有標籤 '{label}' 的快照，請選擇：")
            try:
                chosen2 = renderer.prompt(decision2)
            except EOFError:
                chosen2 = "C"
            if chosen2 == "C":
                click.echo("中止。")
                return
            if chosen2 == "B":
                label = click.prompt("新標籤名稱").strip() or None

    click.echo("\n分析中…")
    try:
        run_analyze_pipeline(codebase_path, AnalyzeConfig())
    except Exception as exc:
        click.echo(f"分析失敗：{exc}", err=True)
        return
    click.echo("✓ 分析完成。")
    state = StateInspector(codebase_path).inspect()
    actions = NextActionSuggester().suggest(state, context="cli")
    render_next_block(actions)


def _print_mcp_hint(codebase_path: Path) -> None:
    click.echo("\n沒有 API key，請使用 MCP 路徑（agent-as-LLM）：")
    path_str = codebase_path.as_posix()
    click.echo(f'  1. extract_structure(codebase_path="{path_str}")')
    click.echo("  2. （你作為 LLM）分析 nodes/edges，產出 l1_features JSON")
    click.echo(f'  3. snapshot_write(codebase_path="{path_str}", l1_features=[...], label="v1.0.0")')
