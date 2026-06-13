"""DiffHandlers — GET /api/diff, GET /api/diff-explanations.

Note (T5-V): diff-explanation generation (POST .../generate) was retired (丙案 D1).
Only GET read/display handlers remain.
"""
from __future__ import annotations

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.guidance.actions import NextAction, to_json_dict as action_to_json
from the_door.core.guidance.remediation import Remediation, make_error_envelope
from the_door.core.guidance.state import StateInspector
from the_door.core.guidance.suggester import NextActionSuggester
from the_door.core.diff.diff_engine import DiffEngine
from the_door.core.ui.api.context import APIContext
from the_door.models import SnapshotNotFoundError


class DiffHandlers:
    def __init__(self, ctx: APIContext) -> None:
        self._ctx = ctx

    # ------------------------------------------------------------------
    # GET /api/diff?baseline=<ref>&current=<ref>
    # ------------------------------------------------------------------

    def versions(self, ctx=None, *, baseline=None, current=None, **_) -> tuple[int, dict]:
        """GET /api/diff — compute L1 diff between two snapshots."""
        baseline_id, current_id = baseline, current
        if not baseline_id or not current_id:
            return 400, self._make_error(
                "missing_params",
                "baseline and current query params required",
                "/api/diff",
            )
        try:
            store = SnapshotStore(self._ctx.project_root)
            baseline_snap = self._resolve_snapshot(store, baseline_id)
            if baseline_snap is None:
                rem = Remediation(
                    code="snapshot_not_found",
                    message=f"baseline {baseline_id!r} 無法解析",
                    next_action=NextAction(
                        id="system_status.show",
                        title="查看可用 snapshots",
                        rationale="列出目前已分析的版本，協助挑出有效的 baseline。",
                        priority=1,
                        cli_command=f"the-door status {self._ctx.project_root.as_posix()}",
                    ),
                )
                return 404, make_error_envelope(
                    code="snapshot_not_found",
                    message=rem.message,
                    remediation=rem,
                    source="handle_diff_versions",
                )
            current_snap = self._resolve_snapshot(store, current_id)
            if current_snap is None:
                rem = Remediation(
                    code="snapshot_not_found",
                    message=f"current {current_id!r} 無法解析",
                    next_action=NextAction(
                        id="system_status.show",
                        title="查看可用 snapshots",
                        rationale="列出目前已分析的版本，協助挑出有效的 current。",
                        priority=1,
                        cli_command=f"the-door status {self._ctx.project_root.as_posix()}",
                    ),
                )
                return 404, make_error_envelope(
                    code="snapshot_not_found",
                    message=rem.message,
                    remediation=rem,
                    source="handle_diff_versions",
                )

            engine = DiffEngine()
            diff_result = engine.compute_l1_diff(baseline_snap, current_snap)
            node_states = {
                nd.node_id: nd.diff_state
                for nd in diff_result.node_diffs
            }
            node_details = {
                nd.node_id: {
                    "baseline_label": nd.baseline_label,
                    "baseline_description": nd.baseline_description,
                    "current_label": nd.current_label,
                    "current_description": nd.current_description,
                }
                for nd in diff_result.node_diffs
            }
            body = {
                "baseline_id": baseline_snap.version_id,
                "baseline_label": baseline_snap.label,
                "current_id": current_snap.version_id,
                "current_label": current_snap.label,
                "summary": {
                    "added": diff_result.summary.added_count,
                    "removed": diff_result.summary.removed_count,
                    "attribute_changed": diff_result.summary.attribute_changed_count,
                    "dependency_changed": diff_result.summary.dependency_changed_count,
                    "total_changed": diff_result.summary.total_changed_count,
                },
                "node_states": node_states,
                "node_details": node_details,
            }
            state = StateInspector(self._ctx.project_root).inspect()
            actions = NextActionSuggester().suggest(state, context="viewer")
            body["next_actions"] = [action_to_json(a) for a in actions]
            body["version_narrative"] = current_snap.version_narratives.get(baseline_snap.version_id)
            return 200, body
        except Exception as exc:
            return 500, make_error_envelope(
                code="diff_error",
                message=f"diff 計算失敗: {exc}",
                remediation=Remediation(
                    code="diff_error",
                    message=str(exc),
                    next_action=NextAction(
                        id="system_status.show",
                        title="查看狀態",
                        rationale="diff 計算過程拋出例外，先看一下系統狀態與已分析版本。",
                        priority=1,
                        cli_command=(
                            f"the-door status {self._ctx.project_root.as_posix()}"
                        ),
                    ),
                ),
                source="handle_diff_versions",
            )

    def _resolve_snapshot(self, store: SnapshotStore, ref: str):
        try:
            return store.resolve_baseline(ref)
        except SnapshotNotFoundError:
            return None

    # ------------------------------------------------------------------
    # GET /api/diff-explanations/<feature_id>
    # ------------------------------------------------------------------

    def get_explanation(
        self,
        ctx=None,
        *,
        feature_id=None,
        baseline_version_id=None,
        current_version_id=None,
        output_language=None,
        **_,
    ) -> tuple[int, dict]:
        """Return cached diff explanation or empty state. Never triggers LLM."""
        if not baseline_version_id or not current_version_id or not output_language:
            return 400, self._make_error(
                "missing_params",
                "baseline_version_id, current_version_id, and output_language are required",
                "handle_get_diff_explanation",
            )
        from the_door.core.ui.diff_explanation_store import DiffExplanationStore
        entry = DiffExplanationStore(self._ctx.project_root).get(
            feature_id, baseline_version_id, current_version_id, output_language
        )
        return 200, {"explanation": entry}

    # POST /api/diff-explanations/<feature_id>/generate was retired in T5-V (丙案 D1):
    # diff-explanation generation is key-bound and cannot run in the headless viewer.
    # Only the GET read/display path (get_explanation) remains.

    @staticmethod
    def _make_error(code: str, message: str, source: str) -> dict:
        return {"error": {"code": code, "message": message, "source": source}}
