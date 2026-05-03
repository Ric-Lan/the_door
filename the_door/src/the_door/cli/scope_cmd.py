"""CLI command group: scope — scope verification and management."""
from __future__ import annotations

import json
import sys

import click


@click.group("scope")
def scope_group():
    """範圍驗核命令群組。"""
    pass


@scope_group.command("verify")
@click.argument("codebase_path", type=click.Path(exists=True))
@click.option("--scope", "scope_ref", required=True, help="Scope definition 檔案路徑或 scope name")
@click.option("--json", "output_json", is_flag=True, help="輸出 JSON 格式")
@click.option("--render", is_flag=True, help="輸出帶 scope badges 的 Mermaid 圖")
@click.option("-o", "--output", "output_file", type=click.Path(), default=None, help="Write output to file")
def scope_verify(codebase_path: str, scope_ref: str, output_json: bool, render: bool, output_file: str | None):
    """執行範圍驗核：比對 scope definition 與最新 L1 分析產出。"""
    from pathlib import Path
    from the_door.core.scope.scope_verifier import (
        ScopeVerifier,
        parse_scope_definition,
        resolve_scope_path,
    )
    from the_door.core.scope.scope_renderer import ScopeRenderer
    from the_door.core.scope.doubt_store import DoubtStore
    from the_door.core.diff.snapshot_store import SnapshotStore
    from the_door.models import ScopeDefinitionError

    project_root = Path(codebase_path)

    # Resolve scope definition
    try:
        scope_path = resolve_scope_path(scope_ref, project_root)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    try:
        scope_def = parse_scope_definition(scope_path)
    except ScopeDefinitionError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Load latest L1 analysis output via SnapshotStore
    store = SnapshotStore(project_root)
    snapshot = store.get_latest()
    if snapshot is None:
        click.echo(
            "No L1 analysis output found. Run `the-door analyze` first.",
            err=True,
        )
        sys.exit(1)

    # Convert VersionSnapshot.l1_snapshot to L1Output for the verifier
    l1_output = _snapshot_to_l1_output(snapshot)

    # Execute scope verification with auto doubt creation
    verifier = ScopeVerifier()
    doubt_store = DoubtStore(project_root)
    scope_result, new_doubts = verifier.verify_and_create_doubts(
        scope_def, l1_output, doubt_store
    )

    # Format output
    if output_json:
        text = _serialize_scope_result_json(scope_result)
    elif render:
        renderer = ScopeRenderer()
        text = renderer.render_l1_with_scope(l1_output, scope_result)
    else:
        text = _format_scope_summary(scope_result, new_doubts)

    if output_file:
        Path(output_file).write_text(text, encoding="utf-8")
        click.echo(f"Output written to {output_file}")
    else:
        click.echo(text)


@scope_group.command("create")
@click.argument("scope_name")
@click.option("--codebase-path", type=click.Path(exists=True), default=".", help="Codebase 根目錄路徑")
def scope_create(scope_name: str, codebase_path: str):
    """建立新的 scope definition 檔案。列出可用 feature_ids 供參考。"""
    from pathlib import Path
    from the_door.core.scope.scope_verifier import (
        scope_name_to_filename,
        serialize_scope_definition,
    )
    from the_door.core.diff.snapshot_store import SnapshotStore
    from the_door.models import ScopeDefinition

    project_root = Path(codebase_path)
    scopes_dir = project_root / ".the-door" / "scopes"
    scopes_dir.mkdir(parents=True, exist_ok=True)

    kebab_name = scope_name_to_filename(scope_name)
    scope_file = scopes_dir / f"{kebab_name}.json"

    # Create empty scope definition
    scope_def = ScopeDefinition(scope_name=scope_name, features=[], description=None)
    data = serialize_scope_definition(scope_def)
    # Ensure features is an empty list in the output
    data["features"] = []
    scope_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    click.echo(f"Created scope definition: {scope_file}")

    # List available feature_ids from latest L1 output for reference
    store = SnapshotStore(project_root)
    snapshot = store.get_latest()
    if snapshot and snapshot.l1_snapshot:
        click.echo("")
        click.echo("Available feature_ids from latest analysis:")
        for fid, summary in sorted(snapshot.l1_snapshot.items()):
            click.echo(f"  {fid}: {summary.label}")
        click.echo("")
        click.echo("Add desired feature_ids to the scope file's features array.")
    else:
        click.echo("No L1 analysis output available for feature reference.")


@scope_group.command("list")
@click.option("--codebase-path", type=click.Path(exists=True), default=".", help="Codebase 根目錄路徑")
def scope_list(codebase_path: str):
    """列出所有 scope definition 檔案。"""
    from pathlib import Path

    project_root = Path(codebase_path)
    scopes_dir = project_root / ".the-door" / "scopes"

    if not scopes_dir.exists():
        click.echo("No scope definitions found.")
        return

    scope_files = sorted(scopes_dir.glob("*.json"))
    if not scope_files:
        click.echo("No scope definitions found.")
        return

    click.echo("Scope definitions:")
    for sf in scope_files:
        try:
            data = json.loads(sf.read_text(encoding="utf-8"))
            name = data.get("scope_name", sf.stem)
            feature_count = len(data.get("features", []))
            click.echo(f"  {sf.name}: {name} ({feature_count} features)")
        except (json.JSONDecodeError, OSError):
            click.echo(f"  {sf.name}: (error reading file)")


@scope_group.command("show")
@click.argument("scope_name")
@click.option("--codebase-path", type=click.Path(exists=True), default=".", help="Codebase 根目錄路徑")
def scope_show(scope_name: str, codebase_path: str):
    """顯示指定 scope definition 的內容。"""
    from pathlib import Path
    from the_door.core.scope.scope_verifier import resolve_scope_path

    project_root = Path(codebase_path)

    try:
        scope_path = resolve_scope_path(scope_name, project_root)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Read raw JSON for display (don't validate schema — show even empty scopes)
    try:
        data = json.loads(scope_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        click.echo(f"Error reading scope file: {e}", err=True)
        sys.exit(1)

    scope_name_val = data.get("scope_name", scope_path.stem)
    description = data.get("description")
    features = data.get("features", [])

    click.echo(f"Scope: {scope_name_val}")
    if description:
        click.echo(f"Description: {description}")
    click.echo(f"Features ({len(features)}):")
    if not features:
        click.echo("  (none — add feature_ids to the scope file)")
    else:
        for f in features:
            fid = f.get("feature_id", "?")
            label = f.get("expected_label")
            if label:
                click.echo(f"  {fid}: {label}")
            else:
                click.echo(f"  {fid}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _snapshot_to_l1_output(snapshot):
    """Convert a VersionSnapshot's l1_snapshot to an L1Output for the verifier."""
    from the_door.models import L1Output, Feature, FeatureRelation

    features = []
    for fid, summary in snapshot.l1_snapshot.items():
        features.append(
            Feature(
                feature_id=summary.feature_id,
                label=summary.label,
                description=summary.description,
                trigger="auto_triggered",
                trigger_description="",
                confidence=summary.confidence,
                confidence_reason="",
                source_nodes=[],
            )
        )

    relations = []
    for rel in snapshot.feature_relations_snapshot:
        relations.append(
            FeatureRelation(
                from_feature=rel.from_feature,
                to_feature=rel.to_feature,
                relation=rel.relation,
                relation_type="static",
            )
        )

    return L1Output(
        summary="",
        features=features,
        feature_relations=relations,
    )


def _serialize_scope_result_json(scope_result) -> str:
    """Serialize ScopeResult to JSON string."""
    data = {
        "scope_name": scope_result.scope_name,
        "entries": [
            {
                "feature_id": e.feature_id,
                "scope_state": e.scope_state,
                "feature_label": e.feature_label,
                "expected_label": e.expected_label,
            }
            for e in scope_result.entries
        ],
        "counts": {
            "in_scope_complete": scope_result.counts.in_scope_complete,
            "out_of_scope": scope_result.counts.out_of_scope,
            "in_scope_incomplete": scope_result.counts.in_scope_incomplete,
        },
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def _format_scope_summary(scope_result, new_doubts) -> str:
    """Format a human-readable scope verification summary."""
    lines = []
    lines.append(f"📋 {scope_result.scope_name} 範圍驗核")
    lines.append("")

    counts = scope_result.counts
    lines.append(f"  ✓ 範圍內已完成：{counts.in_scope_complete} 個功能")
    if counts.out_of_scope > 0:
        lines.append(f"  ⚠ 超出範圍：{counts.out_of_scope} 個功能（需調查）")
    if counts.in_scope_incomplete > 0:
        lines.append(f"  ○ 範圍內未完成：{counts.in_scope_incomplete} 個功能")

    # List out-of-scope features
    oos = [e for e in scope_result.entries if e.scope_state == "out_of_scope"]
    if oos:
        lines.append("")
        lines.append("超出範圍的功能：")
        for e in oos:
            label = e.feature_label or e.feature_id
            lines.append(f"  ⚠ {e.feature_id}: {label}")

    # List incomplete features
    inc = [e for e in scope_result.entries if e.scope_state == "in_scope_incomplete"]
    if inc:
        lines.append("")
        lines.append("範圍內未完成的功能：")
        for e in inc:
            label = e.expected_label or e.feature_id
            lines.append(f"  ○ {e.feature_id}: {label}")

    # Report new doubts
    if new_doubts:
        lines.append("")
        lines.append(f"已自動建立 {len(new_doubts)} 個疑義記錄：")
        for d in new_doubts:
            lines.append(f"  {d.doubt_id[:8]} ({d.doubt_type}): {d.source_node}")

    return "\n".join(lines)
