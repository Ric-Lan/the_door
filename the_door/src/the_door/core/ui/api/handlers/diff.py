"""DiffHandlers — GET /api/diff, GET/POST /api/diff-explanations."""
from __future__ import annotations

import asyncio
import datetime
import json

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.guidance.actions import NextAction, to_json_dict as action_to_json
from the_door.core.guidance.remediation import Remediation, make_error_envelope
from the_door.core.guidance.state import StateInspector
from the_door.core.guidance.suggester import NextActionSuggester
from the_door.core.llm.config_manager import ConfigManager, ConfigError
from the_door.core.diff.diff_engine import DiffEngine
from the_door.core.llm.provider import create_provider
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.report_paths import find_latest_report_path
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
            result = store.resolve_baseline(ref)
            if result is not None:
                return result
        except SnapshotNotFoundError:
            pass
        return store.get_snapshot(ref)

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

    # ------------------------------------------------------------------
    # POST /api/diff-explanations/<feature_id>/generate
    # ------------------------------------------------------------------

    def generate_explanation(
        self,
        ctx=None,
        *,
        feature_id=None,
        body=None,
        **_,
    ) -> tuple[int, dict]:
        """Generate a diff explanation for one feature via LLM and cache it."""
        if body is None:
            body = {}
        baseline_version_id = body.get("baseline_version_id")
        current_version_id = body.get("current_version_id")
        output_language = body.get("output_language") or "zh-Hant"

        if not baseline_version_id or not current_version_id:
            return 400, self._make_error(
                "missing_params",
                "baseline_version_id and current_version_id are required",
                "handle_post_diff_explanation_generate",
            )

        # Gather diff context from UpdateReport if available
        diff_context = self._collect_diff_context(
            feature_id, baseline_version_id, current_version_id
        )

        # Resolve LLM provider
        try:
            config = ConfigManager.load()
            llm_provider = create_provider(config)
        except ConfigError as exc:
            return 503, self._make_error(
                "provider_not_configured",
                f"LLM provider is not configured or unavailable: {exc}",
                "handle_post_diff_explanation_generate",
            )

        prompt = self._build_diff_explanation_prompt(
            feature_id, diff_context, output_language
        )
        try:
            raw = asyncio.run(llm_provider.complete(prompt))
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {
                "impact_summary": raw[:500] if raw else "推論格式錯誤。",
                "possible_purpose": "無法解析推論結果。",
                "linked_resources": [],
                "caution": "LLM 回傳非 JSON 格式，請謹慎參考。",
                "confidence": "low",
            }
        except Exception as exc:
            return 500, self._make_error(
                "llm_error",
                f"LLM call failed: {exc}",
                "handle_post_diff_explanation_generate",
            )

        entry = {
            "feature_id": feature_id,
            "change_type": diff_context.get("change_type", ""),
            "impact_summary": parsed.get("impact_summary", ""),
            "possible_purpose": parsed.get("possible_purpose", ""),
            "linked_resources": parsed.get("linked_resources", []),
            "caution": parsed.get("caution", ""),
            "confidence": parsed.get("confidence", "low"),
            "language": output_language,
            "generated_at": (
                datetime.datetime.now(datetime.timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            ),
            "baseline_version_id": baseline_version_id,
            "current_version_id": current_version_id,
        }

        from the_door.core.ui.diff_explanation_store import DiffExplanationStore
        DiffExplanationStore(self._ctx.project_root).save(entry)
        return 200, {"explanation": entry}

    def _collect_diff_context(
        self, feature_id: str, baseline_version_id: str, current_version_id: str
    ) -> dict:
        """Return available diff data for the feature from UpdateReport."""
        latest_path = find_latest_report_path(self._ctx.project_root)
        if latest_path is None:
            return {}
        try:
            report = json.loads(latest_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        context: dict = {}
        for entry in report.get("l2_details", []):
            if entry.get("feature_id") == feature_id:
                context = {
                    "change_type": entry.get("change_type", ""),
                    "current_label": entry.get("current_label", ""),
                    "current_description": entry.get("current_description", ""),
                    "baseline_label": entry.get("baseline_label", ""),
                    "baseline_description": entry.get("baseline_description", ""),
                    "affected_relations": entry.get("affected_relations", []),
                }
                break
        if not context:
            for entry in report.get("l1_changes", []):
                if entry.get("feature_id") == feature_id:
                    context = {
                        "change_type": entry.get("change_type", ""),
                        "current_label": entry.get("current_label", ""),
                    }
                    break
        return context

    @staticmethod
    def _build_diff_explanation_prompt(
        feature_id: str, context: dict, output_language: str
    ) -> str:
        ctx_text = (
            json.dumps(context, ensure_ascii=False, indent=2)
            if context else "（無差異資料）"
        )
        return f"""你是版本差異分析助理。根據以下差異資料，以 {output_language} 回答四個問題。
目標讀者是**非技術讀者**（產品經理、客服、營運），不是工程師。

差異資料（feature_id: {feature_id}）：
{ctx_text}

## 風格規則（硬性）

四個欄位的文字內容必須符合：

- **禁止實作細節**：函式名、API endpoint（如以 `/api/` 開頭的字串）、檔名
  （`.py` / `.js` / `.ts` 等副檔名）、縮寫（AST / JSON-RPC / API / DOM 等）、
  camelCase 識別字
- 用「影響什麼／為了什麼」描述，不用「怎麼改的程式」
- 必須使用 {output_language} 語言回答
- 只根據提供的資料推論，不要編造需求、commit message 或不存在的資源
- 若資料不足，confidence 填 low，caution 說明推論依據有限

## 範例

✅ 好範例：
- impact_summary：使用者打開頁面時看到的不再是滿屏的圖譜，而是一份可閱讀的功能清單。

❌ 壞範例：
- impact_summary：移除 renderGraphCanvas，改用 featureCard 組件，並透過 /api/l1 載入。

## 輸出格式

請以 JSON 格式回答，不要包含其他文字：

{{
  "impact_summary": "此差異對使用者體驗影響什麼（一句話，面向非技術讀者）",
  "possible_purpose": "此變更可以達成什麼目的（一句話，用「可能」語氣）",
  "linked_resources": ["相關功能名稱列表，最多 5 個；不要列函式名或檔名"],
  "caution": "需要注意的地方；資料不足時說明推論依據有限",
  "confidence": "high 或 medium 或 low"
}}"""

    @staticmethod
    def _make_error(code: str, message: str, source: str) -> dict:
        return {"error": {"code": code, "message": message, "source": source}}
