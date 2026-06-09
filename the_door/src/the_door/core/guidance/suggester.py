from typing import Callable

from the_door.core.guidance.state import SystemState
from the_door.core.guidance.actions import NextAction, ActionContext


_Factory = Callable[[SystemState, ActionContext], NextAction]
_Rule = tuple[Callable[[SystemState], bool], tuple[ActionContext, ...], _Factory]


def _rule_first_time(state, context):
    return NextAction(id="extract.first_time",
                      title="首次分析這個專案（agent-as-LLM）",
                      rationale="專案尚未建立 .the-door/ — 用 extract_structure 抽結構，由 agent 產 L1 後 snapshot_write。",
                      priority=1,
                      mcp_tool="extract_structure",
                      mcp_arguments={"codebase_path": state.project_path.as_posix()})


def _rule_snapshot_write_first(state, context):
    return NextAction(id="snapshot.write_first", title="寫入首個 snapshot",
                      rationale="已有 structure.json 但尚未持久化為 snapshot。", priority=2,
                      mcp_tool="snapshot_write",
                      mcp_arguments={"codebase_path": state.project_path.as_posix()})


def _rule_incremental(state, context):
    label = state.latest_snapshot.label or state.latest_snapshot.version_id
    return NextAction(id="analyze_changes.incremental",
                      title="分析新版本（繼承既有 baseline）",
                      rationale="已有 baseline — 用 analyze_changes 取受影響功能，由 agent 重產後 snapshot_write(inherit_from)。",
                      priority=2,
                      mcp_tool="analyze_changes",
                      mcp_arguments={"codebase_path": state.project_path.as_posix(), "baseline": label})


def _rule_viewer_open(state, context):
    path = state.project_path.as_posix()
    if context == "viewer":
        return NextAction(id="viewer.open", title="在 viewer 比對兩個版本",
                          rationale="已有 ≥ 2 個 snapshot。", priority=3,
                          viewer_route="/")
    return NextAction(id="viewer.open", title="在 viewer 比對兩個版本",
                      rationale="已有 ≥ 2 個 snapshot。", priority=3,
                      cli_command=f"the-door ui {path}")


def _rule_diff_cli(state, context):
    prev = state.snapshots[1]
    label = prev.label or prev.version_id
    return NextAction(id="diff.cli", title="在 CLI 看版本差異",
                      rationale="想看純文字 diff 摘要。", priority=4,
                      cli_command=f"the-door diff --baseline {label} {state.project_path.as_posix()}")


def _rule_backfill(state, context):
    target = next(s for s in state.snapshots if not s.has_persisted_structure)
    label = target.label or target.version_id
    return NextAction(id="extract.backfill_structure",
                      title="補既有 snapshot 的 persisted structure（無需 API key）",
                      rationale="baseline 缺少 structures/<vid>.json.gz。", priority=5,
                      cli_command=f"the-door extract --as-version {label} <baseline_source_path>")


def _rule_repair_drift(state, context):
    label = state.latest_snapshot.label or state.latest_snapshot.version_id
    return NextAction(id="extract.repair_drift",
                      title="修復 source_nodes 漂移（重抽結構，無需 API key）",
                      rationale="偵測到 source_nodes_drift — 重跑 extract 後用 snapshot_patch 補 source_nodes。",
                      priority=6,
                      cli_command=f"the-door extract --as-version {label} <baseline_source_path>")


def _rule_system_status(state, context):
    path = state.project_path.as_posix()
    if context == "mcp":
        return NextAction(id="system_status.show", title="查看目前專案狀態與建議",
                          rationale="不確定下一步時的安全選擇。", priority=90,
                          mcp_tool="system_status", mcp_arguments={"project_path": path})
    if context == "viewer":
        return NextAction(id="system_status.show", title="查看目前專案狀態與建議",
                          rationale="不確定下一步時的安全選擇。", priority=90,
                          viewer_route="/?status=1")
    return NextAction(id="system_status.show", title="查看目前專案狀態與建議",
                      rationale="不確定下一步時的安全選擇。", priority=90,
                      cli_command=f"the-door status {path}")


def _rule_onboarding(state, context):
    return NextAction(id="onboarding.read_claude_md", title="閱讀使用指南",
                      rationale="所有 fallback。", priority=99,
                      cli_command="the-door --help")


_RULES: list[_Rule] = [
    (lambda s: not s.has_dot_the_door, ("cli", "mcp"), _rule_first_time),
    (lambda s: s.has_structure_json and not s.snapshots, ("mcp", "after_error"), _rule_snapshot_write_first),
    (lambda s: len(s.snapshots) >= 1, ("cli", "mcp"), _rule_incremental),
    (lambda s: len(s.snapshots) >= 2, ("cli", "viewer"), _rule_viewer_open),
    (lambda s: len(s.snapshots) >= 2, ("cli",), _rule_diff_cli),
    (lambda s: bool(s.snapshots) and not all(e.has_persisted_structure for e in s.snapshots), ("cli", "after_error"), _rule_backfill),
    (lambda s: any(w.code == "source_nodes_drift" for w in s.warnings), ("cli",), _rule_repair_drift),
    (lambda s: True, ("cli", "mcp", "viewer", "after_error"), _rule_system_status),
    (lambda s: True, ("cli", "mcp", "viewer", "after_error"), _rule_onboarding),
]


_AFTER_ERROR_BOOST = {
    "no_persisted_structure_for_baseline": "extract.backfill_structure",
    "baseline_not_found": "system_status.show",
    "snapshot_not_found": "system_status.show",
    "no_snapshot_for_baseline": "snapshot.write_first",
}


class NextActionSuggester:
    def suggest(
        self,
        state: SystemState,
        context: ActionContext,
        failure_code: str | None = None,
    ) -> list[NextAction]:
        actions: dict[str, NextAction] = {}
        for predicate, surfaces, factory in _RULES:
            if context not in surfaces:
                continue
            if not predicate(state):
                continue
            action = factory(state, context)
            if action.id not in actions:
                actions[action.id] = action
        if context == "after_error" and failure_code in _AFTER_ERROR_BOOST:
            boost_id = _AFTER_ERROR_BOOST[failure_code]
            if boost_id in actions:
                old = actions[boost_id]
                actions[boost_id] = NextAction(
                    id=old.id, title=old.title, rationale=old.rationale,
                    priority=1,
                    cli_command=old.cli_command, mcp_tool=old.mcp_tool,
                    mcp_arguments=old.mcp_arguments, viewer_route=old.viewer_route,
                )
        result = list(actions.values())
        result.sort(key=lambda a: (a.priority, a.id))
        return result
