"""CLI command: diff — compare current analysis against a baseline version."""
from __future__ import annotations

import json
import sys

import click


@click.command("diff")
@click.argument("codebase_path", type=click.Path(exists=True))
@click.option("--baseline", required=True, help="Baseline reference: git tag, commit SHA, date (YYYY-MM-DD), or snapshot label")
@click.option("--json", "output_json", is_flag=True, help="Output raw DiffResult JSON instead of Mermaid")
@click.option("--layer", type=click.Choice(["l1", "l1.5"]), default="l1", help="Layer to diff (default: l1)")
@click.option("-o", "--output", "output_file", type=click.Path(), default=None, help="Write output to file")
def diff_cmd(codebase_path, baseline, output_json, layer, output_file):
    """Compare current analysis against a baseline version."""
    from pathlib import Path
    from the_door.core.diff.snapshot_store import SnapshotStore
    from the_door.core.diff.diff_engine import DiffEngine
    from the_door.core.diff.diff_renderer import DiffRenderer
    from the_door.models import SnapshotNotFoundError, DiffError

    from the_door.cli.main import CliRemediableError
    from the_door.core.guidance.remediation import Remediation, REMEDIATION_CATALOGUE
    from the_door.core.guidance.state import StateInspector
    from the_door.core.guidance.suggester import NextActionSuggester

    def _suggest_next_action(failure_code: str):
        state = StateInspector(Path(codebase_path)).inspect()
        actions = NextActionSuggester().suggest(state, context="after_error", failure_code=failure_code)
        return actions[0] if actions else None

    store = SnapshotStore(Path(codebase_path))

    # Get current (latest) snapshot
    current = store.get_latest()
    if current is None:
        raise CliRemediableError(Remediation(
            code="no_snapshot_for_baseline",
            message=(
                f"{REMEDIATION_CATALOGUE['no_snapshot_for_baseline']} "
                f"({codebase_path}/.the-door/snapshots/ 為空,先跑 `the-door analyze`。)"
            ),
            next_action=_suggest_next_action("no_snapshot_for_baseline"),
        ))

    # Resolve baseline
    try:
        baseline_snap = store.resolve_baseline(baseline)
    except SnapshotNotFoundError as e:
        # Preserve the available-snapshots UX inside the message — render_remediation
        # writes message verbatim so users still see what they could have referenced.
        lines = [f"snapshot_not_found: 找不到 baseline '{baseline}'."]
        if e.available:
            lines.append("Available snapshots:")
            for snap_info in e.available:
                row = f"  {snap_info['version_id'][:8]}  {snap_info['timestamp']}  {snap_info['trigger']}"
                if snap_info.get("git_tags"):
                    row += f"  tags: {', '.join(snap_info['git_tags'])}"
                if snap_info.get("label"):
                    row += f"  label: {snap_info['label']}"
                lines.append(row)
        raise CliRemediableError(Remediation(
            code="snapshot_not_found",
            message="\n".join(lines),
            next_action=_suggest_next_action("snapshot_not_found"),
        ))

    # Compute diff
    engine = DiffEngine()
    try:
        if layer == "l1":
            diff_result = engine.compute_l1_diff(baseline_snap, current)
        else:
            diff_result = engine.compute_l1_5_diff(baseline_snap, current)
    except DiffError as e:
        raise CliRemediableError(Remediation(
            code="diff_failed",
            message=f"diff_failed: {e}",
            next_action=_suggest_next_action("diff_failed"),
        ))

    # Patch resolved_from into baseline_info for renderer label formatting
    from the_door.models import BaselineInfo, DiffResult as DiffResultModel
    patched_baseline = BaselineInfo(
        version_id=diff_result.baseline_info.version_id,
        timestamp=diff_result.baseline_info.timestamp,
        trigger=diff_result.baseline_info.trigger,
        commit_hash=diff_result.baseline_info.commit_hash,
        git_tags=diff_result.baseline_info.git_tags,
        label=diff_result.baseline_info.label,
        resolved_from=baseline,
    )
    diff_result = DiffResultModel(
        baseline_info=patched_baseline,
        current_info=diff_result.current_info,
        node_diffs=diff_result.node_diffs,
        edge_diffs=diff_result.edge_diffs,
        summary=diff_result.summary,
        layer=diff_result.layer,
    )

    # Output
    if output_json:
        output_data = _serialize_diff_result(diff_result)
        text = json.dumps(output_data, indent=2, ensure_ascii=False)
    else:
        renderer = DiffRenderer()
        if layer == "l1":
            text = renderer.render_l1_diff(diff_result)
        else:
            text = renderer.render_l1_5_diff(diff_result)

    if output_file:
        Path(output_file).write_text(text, encoding="utf-8")
        click.echo(f"Output written to {output_file}")
    else:
        click.echo(text)

    from the_door.cli.post_run_hook import cli_post_run_hook
    cli_post_run_hook(codebase_path, json_mode_active=output_json)


def _serialize_diff_result(diff_result) -> dict:
    """Serialize DiffResult to JSON-compatible dict."""
    def _info_to_dict(info):
        d = {
            "version_id": info.version_id,
            "timestamp": info.timestamp,
            "trigger": info.trigger,
        }
        if info.commit_hash:
            d["commit_hash"] = info.commit_hash
        if info.git_tags:
            d["git_tags"] = info.git_tags
        if info.label:
            d["label"] = info.label
        return d

    return {
        "baseline_info": _info_to_dict(diff_result.baseline_info),
        "current_info": _info_to_dict(diff_result.current_info),
        "node_diffs": [
            {
                "node_id": nd.node_id,
                "diff_state": nd.diff_state,
                "current_label": nd.current_label,
                "current_description": nd.current_description,
                "baseline_label": nd.baseline_label,
                "baseline_description": nd.baseline_description,
                "current_confidence": nd.current_confidence,
                "secondary_changes": nd.secondary_changes,
            }
            for nd in diff_result.node_diffs
        ],
        "edge_diffs": [
            {
                "from_node": ed.from_node,
                "to_node": ed.to_node,
                "diff_state": ed.diff_state,
                "current_relation": ed.current_relation,
                "baseline_relation": ed.baseline_relation,
            }
            for ed in diff_result.edge_diffs
        ],
        "summary": {
            "added_count": diff_result.summary.added_count,
            "removed_count": diff_result.summary.removed_count,
            "dependency_changed_count": diff_result.summary.dependency_changed_count,
            "attribute_changed_count": diff_result.summary.attribute_changed_count,
            "total_changed_count": diff_result.summary.total_changed_count,
        },
    }
