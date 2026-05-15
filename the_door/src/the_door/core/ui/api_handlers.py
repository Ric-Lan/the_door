"""APIHandlers — business logic for all API endpoints.

Each method returns (status_code: int, body: dict) with no HTTP side effects.
All core modules are injected/mocked in tests.

Phase UI-2: 7 original endpoints.
Phase UI-3: 6 new endpoints + 2 private background thread methods.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.llm.config_manager import ConfigManager, ConfigError
from the_door.core.llm.provider import create_provider
from the_door.core.pipeline.pipeline_orchestrator import PipelineOrchestrator
from the_door.core.pipeline.report_renderer import ReportRenderer
from the_door.core.scope.doubt_store import DoubtStore
from the_door.core.timeline.timeline_engine import TimelineEngine
from the_door.core.ui.graph_view_model import (
    build_l1_graph_view_model_from_snapshot,
    build_l2_graph_view_model,
)
from the_door.core.ui.job_store import JobStore, UpdateJob
from the_door.core.ui.l2_generator import L2Generator, L2GenerationError
from the_door.core.ui.serializers import (
    empty_timeline_result,
    serialize_doubt,
    serialize_snapshot,
    serialize_timeline_result,
)
from the_door.models import PipelineConfig

_VALID_LAYERS = {"l1", "l2", "l3"}


class APIHandlers:
    """Business logic layer for all 7 API endpoints.

    All methods return (status_code: int, body: dict).
    No HTTP side effects — the HTTP layer (server.py) handles sending.
    """

    def __init__(self, project_root: Path, job_store: JobStore) -> None:
        self._project_root = project_root
        self._job_store = job_store

    # ------------------------------------------------------------------
    # GET /api/project
    # ------------------------------------------------------------------

    def handle_get_project(self) -> tuple[int, dict]:
        """Return project path and available data status."""
        dot_dir = self._project_root / ".the-door"
        dot_exists = dot_dir.exists()

        if not dot_exists:
            return 200, {
                "project_path": str(self._project_root.resolve()),
                "dot_the_door_exists": False,
                "available_data": {
                    "has_snapshots": False,
                    "has_latest_report": False,
                    "has_doubts": False,
                    "has_scope_config": False,
                },
            }

        try:
            snapshots = SnapshotStore(self._project_root).list_snapshots()
            doubts = DoubtStore(self._project_root).list_doubts()
            has_scope_config = (dot_dir / "scope-config.json").exists()
            has_latest_report = self._find_latest_report_path() is not None

            return 200, {
                "project_path": str(self._project_root.resolve()),
                "dot_the_door_exists": True,
                "available_data": {
                    "has_snapshots": len(snapshots) > 0,
                    "has_latest_report": has_latest_report,
                    "has_doubts": len(doubts) > 0,
                    "has_scope_config": has_scope_config,
                },
            }
        except Exception as exc:
            return 500, self._make_error(
                code="project_read_error",
                message=str(exc),
                source="handle_get_project",
            )

    # ------------------------------------------------------------------
    # GET /api/snapshots
    # ------------------------------------------------------------------

    def handle_get_snapshots(self) -> tuple[int, dict]:
        """Return all snapshots sorted by timestamp descending."""
        try:
            snapshots = SnapshotStore(self._project_root).list_snapshots()
            sorted_snapshots = sorted(snapshots, key=lambda s: s.timestamp, reverse=True)
            return 200, {"snapshots": [serialize_snapshot(s) for s in sorted_snapshots]}
        except Exception as exc:
            return 500, self._make_error(
                code="snapshot_read_error",
                message=str(exc),
                source="handle_get_snapshots",
            )

    # ------------------------------------------------------------------
    # GET /api/report/latest
    # ------------------------------------------------------------------

    def handle_get_report_latest(self) -> tuple[int, dict]:
        """Return the latest UpdateReport JSON."""
        latest_path = self._find_latest_report_path()
        if latest_path is None:
            return 404, self._make_error(
                code="no_report_found",
                message="No update report found in .the-door/",
                source="handle_get_report_latest",
            )
        try:
            content = latest_path.read_text(encoding="utf-8")
            return 200, json.loads(content)
        except json.JSONDecodeError as exc:
            return 500, self._make_error(
                code="report_parse_error",
                message=str(exc),
                source="handle_get_report_latest",
            )
        except Exception as exc:
            return 500, self._make_error(
                code="report_read_error",
                message=str(exc),
                source="handle_get_report_latest",
            )

    # ------------------------------------------------------------------
    # POST /api/update
    # ------------------------------------------------------------------

    def handle_post_update(self, body: dict) -> tuple[int, dict]:
        """Validate request, create job, start background pipeline thread."""
        # 1. Validate required fields
        old_path_str = body.get("old_path")
        new_path_str = body.get("new_path")
        if old_path_str is None or new_path_str is None:
            return 400, self._make_error(
                code="missing_required_field",
                message="Both 'old_path' and 'new_path' are required.",
                source="handle_post_update",
            )

        old_path = Path(old_path_str)
        new_path = Path(new_path_str)

        # 2. Validate paths exist and are directories
        if not old_path.exists() or not old_path.is_dir():
            return 400, self._make_error(
                code="invalid_path",
                message=f"old_path does not exist or is not a directory: {old_path_str}",
                source="handle_post_update",
            )
        if not new_path.exists() or not new_path.is_dir():
            return 400, self._make_error(
                code="invalid_path",
                message=f"new_path does not exist or is not a directory: {new_path_str}",
                source="handle_post_update",
            )

        # 3. Validate paths are not the same
        if old_path.resolve() == new_path.resolve():
            return 400, self._make_error(
                code="same_path",
                message="old_path and new_path must be different directories.",
                source="handle_post_update",
            )

        # 4. Security: validate paths are under project_root
        project_root_resolved = self._project_root.resolve()
        try:
            old_path.resolve().relative_to(project_root_resolved)
        except ValueError:
            return 400, self._make_error(
                code="invalid_path",
                message=f"old_path is outside project root: {old_path_str}",
                source="handle_post_update",
            )
        try:
            new_path.resolve().relative_to(project_root_resolved)
        except ValueError:
            return 400, self._make_error(
                code="invalid_path",
                message=f"new_path is outside project root: {new_path_str}",
                source="handle_post_update",
            )

        # 5. Check for running job
        job = self._job_store.try_create_job()
        if job is None:
            return 409, self._make_error(
                code="job_already_running",
                message="A pipeline job is already running. Please wait for it to complete.",
                source="handle_post_update",
            )

        output_language = body.get("output_language") or "zh-Hant"

        # 6. Start background thread
        thread = threading.Thread(
            target=self._run_pipeline_job,
            args=(job, old_path, new_path, output_language),
            daemon=True,
        )
        thread.start()

        return 202, {"job_id": job.job_id}

    # ------------------------------------------------------------------
    # GET /api/update/status/<job_id>
    # ------------------------------------------------------------------

    def handle_get_update_status(self, job_id: str) -> tuple[int, dict]:
        """Return the current status of a pipeline job."""
        job = self._job_store.get_job(job_id)
        if job is None:
            return 404, self._make_error(
                code="job_not_found",
                message=f"No job found with id: {job_id}",
                source="handle_get_update_status",
            )

        response: dict = {
            "job_id": job.job_id,
            "status": job.status,
            "current_step": job.current_step,
            "steps": list(job.steps),
        }
        if job.status == "failed":
            response["error_message"] = job.error_message

        return 200, response

    # ------------------------------------------------------------------
    # GET /api/doubts
    # ------------------------------------------------------------------

    def handle_get_doubts(self) -> tuple[int, dict]:
        """Return all doubts with summary."""
        try:
            doubts = DoubtStore(self._project_root).list_doubts()
            return 200, {
                "doubts": [serialize_doubt(d) for d in doubts],
                "summary": {"total": len(doubts)},
            }
        except Exception as exc:
            return 500, self._make_error(
                code="doubt_read_error",
                message=str(exc),
                source="handle_get_doubts",
            )

    # ------------------------------------------------------------------
    # GET /api/timeline
    # ------------------------------------------------------------------

    def handle_get_timeline(self) -> tuple[int, dict]:
        """Return timeline analysis result."""
        try:
            snapshots = SnapshotStore(self._project_root).list_snapshots()
            if not snapshots:
                return 200, empty_timeline_result()
            result = TimelineEngine().analyze(snapshots)
            return 200, serialize_timeline_result(result)
        except Exception as exc:
            return 500, self._make_error(
                code="timeline_error",
                message=str(exc),
                source="handle_get_timeline",
            )

    # ------------------------------------------------------------------
    # GET /api/l1  (Phase UI-3)
    # ------------------------------------------------------------------

    def handle_get_l1(self, version_id: str | None = None) -> tuple[int, dict]:
        """GET /api/l1 — return L1_Graph_ViewModel from a VersionSnapshot.

        If version_id is provided, loads that specific snapshot.
        Otherwise falls back to the latest snapshot.
        """
        try:
            store = SnapshotStore(self._project_root)
            snapshot = store.get_snapshot(version_id) if version_id else store.get_latest()
            if snapshot is None:
                msg = (
                    f"Snapshot '{version_id}' not found."
                    if version_id
                    else "No snapshot found. Run analysis first."
                )
                return 404, self._make_error(
                    code="no_l1_data",
                    message=msg,
                    source="handle_get_l1",
                )
            l1_snapshot_dict = {
                fid: {
                    "label": fs.label,
                    "confidence": fs.confidence,
                    "description": fs.description,
                    "trigger_description": fs.trigger_description,
                }
                for fid, fs in snapshot.l1_snapshot.items()
            }
            feature_relations_list = [
                {
                    "from_feature": rel.from_feature,
                    "to_feature": rel.to_feature,
                    "relation": rel.relation,
                }
                for rel in snapshot.feature_relations_snapshot
            ]
            view_model = build_l1_graph_view_model_from_snapshot(
                l1_snapshot_dict, feature_relations_list
            )
            return 200, view_model
        except Exception as exc:
            return 500, self._make_error(
                code="l1_read_error",
                message=str(exc),
                source="handle_get_l1",
            )

    # ------------------------------------------------------------------
    # GET /api/diff?baseline=<version_id>&current=<version_id>
    # ------------------------------------------------------------------

    def handle_diff_versions(self, baseline_id: str, current_id: str) -> tuple[int, dict]:
        """GET /api/diff — compute L1 diff between two snapshots by version_id."""
        from the_door.core.diff.diff_engine import DiffEngine
        try:
            store = SnapshotStore(self._project_root)
            baseline = store.get_snapshot(baseline_id)
            current = store.get_snapshot(current_id)
            if baseline is None:
                return 404, self._make_error(
                    code="snapshot_not_found",
                    message=f"Baseline snapshot '{baseline_id}' not found.",
                    source="handle_diff_versions",
                )
            if current is None:
                return 404, self._make_error(
                    code="snapshot_not_found",
                    message=f"Current snapshot '{current_id}' not found.",
                    source="handle_diff_versions",
                )
            engine = DiffEngine()
            diff_result = engine.compute_l1_diff(baseline, current)
            node_states = {
                nd.node_id: nd.diff_state
                for nd in diff_result.node_diffs
            }
            return 200, {
                "baseline_id": baseline_id,
                "current_id": current_id,
                "summary": {
                    "added": diff_result.summary.added_count,
                    "removed": diff_result.summary.removed_count,
                    "attribute_changed": diff_result.summary.attribute_changed_count,
                    "dependency_changed": diff_result.summary.dependency_changed_count,
                    "total_changed": diff_result.summary.total_changed_count,
                },
                "node_states": node_states,
            }
        except Exception as exc:
            return 500, self._make_error(
                code="diff_error",
                message=str(exc),
                source="handle_diff_versions",
            )

    # ------------------------------------------------------------------
    # GET /api/l2/<feature_id>  (Phase UI-3)
    # ------------------------------------------------------------------

    def handle_get_l2(self, feature_id: str) -> tuple[int, dict]:
        """GET /api/l2/<feature_id> — return L2_Graph_ViewModel if cached."""
        try:
            l2_output = L2Generator.load(self._project_root, feature_id)
            if l2_output is None:
                return 404, self._make_error(
                    code="l2_not_generated",
                    message=f"L2 data not yet generated for feature '{feature_id}'.",
                    source="handle_get_l2",
                )
            view_model = build_l2_graph_view_model(l2_output)
            return 200, view_model
        except Exception as exc:
            return 500, self._make_error(
                code="l2_read_error",
                message=str(exc),
                source="handle_get_l2",
            )

    # ------------------------------------------------------------------
    # POST /api/l2/<feature_id>/generate  (Phase UI-3)
    # ------------------------------------------------------------------

    def handle_post_l2_generate(self, feature_id: str) -> tuple[int, dict]:
        """POST /api/l2/<feature_id>/generate — start async L2 generation job."""
        # 1. Check structure.json exists
        structure_path = self._project_root / ".the-door" / "structure.json"
        if not structure_path.exists():
            return 404, self._make_error(
                code="no_structure_data",
                message="structure.json not found. Run 'the-door extract' first.",
                source="handle_post_l2_generate",
            )

        # 2. Read structure.json
        try:
            structure_json = json.loads(structure_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return 500, self._make_error(
                code="structure_read_error",
                message=str(exc),
                source="handle_post_l2_generate",
            )

        # 3. Try to create job
        job = self._job_store.try_create_job()
        if job is None:
            return 409, self._make_error(
                code="job_already_running",
                message="A job is already running. Please wait for it to complete.",
                source="handle_post_l2_generate",
            )

        # 4. Start background thread
        thread = threading.Thread(
            target=self._run_l2_generate_job,
            args=(job, feature_id, structure_json),
            daemon=True,
        )
        thread.start()

        return 202, {"job_id": job.job_id}

    # ------------------------------------------------------------------
    # GET /api/layer-explanation/<feature_id>/<layer>  (Phase UI-3)
    # ------------------------------------------------------------------

    def handle_get_layer_explanation(
        self, feature_id: str, layer: str
    ) -> tuple[int, dict]:
        """GET /api/layer-explanation/<feature_id>/<layer> — return cached explanation."""
        if layer not in _VALID_LAYERS:
            return 400, self._make_error(
                code="invalid_layer",
                message=f"Invalid layer '{layer}'. Must be one of: l1, l2, l3.",
                source="handle_get_layer_explanation",
            )

        cache_path = (
            self._project_root
            / ".the-door"
            / "layer-explanations"
            / feature_id
            / f"{layer}.json"
        )
        if not cache_path.exists():
            return 404, self._make_error(
                code="explanation_not_cached",
                message=f"No cached explanation for feature '{feature_id}' layer '{layer}'.",
                source="handle_get_layer_explanation",
            )

        try:
            content = json.loads(cache_path.read_text(encoding="utf-8"))
            return 200, content
        except Exception as exc:
            return 500, self._make_error(
                code="explanation_read_error",
                message=str(exc),
                source="handle_get_layer_explanation",
            )

    # ------------------------------------------------------------------
    # POST /api/layer-explanation/<feature_id>/<layer>/generate  (Phase UI-3)
    # ------------------------------------------------------------------

    def handle_post_layer_explanation_generate(
        self, feature_id: str, layer: str
    ) -> tuple[int, dict]:
        """POST /api/layer-explanation/<feature_id>/<layer>/generate — start explanation job."""
        if layer not in _VALID_LAYERS:
            return 400, self._make_error(
                code="invalid_layer",
                message=f"Invalid layer '{layer}'. Must be one of: l1, l2, l3.",
                source="handle_post_layer_explanation_generate",
            )

        job = self._job_store.try_create_job()
        if job is None:
            return 409, self._make_error(
                code="job_already_running",
                message="A job is already running. Please wait for it to complete.",
                source="handle_post_layer_explanation_generate",
            )

        thread = threading.Thread(
            target=self._run_layer_explanation_job,
            args=(job, feature_id, layer),
            daemon=True,
        )
        thread.start()

        return 202, {"job_id": job.job_id}

    # ------------------------------------------------------------------
    # GET /api/structure  (Phase UI-3)
    # ------------------------------------------------------------------

    def handle_get_structure(self) -> tuple[int, dict]:
        """GET /api/structure — return structure.json content."""
        structure_path = self._project_root / ".the-door" / "structure.json"
        if not structure_path.exists():
            return 404, self._make_error(
                code="no_structure_data",
                message="structure.json not found. Run 'the-door extract' first.",
                source="handle_get_structure",
            )

        try:
            content = json.loads(structure_path.read_text(encoding="utf-8"))
            return 200, content
        except Exception as exc:
            return 500, self._make_error(
                code="structure_read_error",
                message=str(exc),
                source="handle_get_structure",
            )

    # ------------------------------------------------------------------
    # Private background thread methods (Phase UI-3)
    # ------------------------------------------------------------------

    def _run_l2_generate_job(
        self, job: UpdateJob, feature_id: str, structure_json: dict
    ) -> None:
        """Background thread: generate L2Output via LLM and persist.

        Uses asyncio.run() to call async L2Generator.generate().
        Catches ConfigError / L2GenerationError and calls fail_job().
        """
        try:
            config = ConfigManager.load()
            llm_provider = create_provider(config)
        except ConfigError as exc:
            self._job_store.fail_job(job.job_id, f"Config error: {exc}")
            return

        try:
            from the_door.models import StructureJSON, ASTNode, Edge as StructureEdge

            # Reconstruct StructureJSON from the dict
            nodes = [
                ASTNode(
                    node_id=n["node_id"],
                    name=n["name"],
                    type=n["type"],
                    file=n["file"],
                )
                for n in structure_json.get("nodes", [])
            ]
            edges = [
                StructureEdge(
                    from_node=e["from_node"],
                    to_node=e["to_node"],
                    type=e["type"],
                )
                for e in structure_json.get("edges", [])
            ]
            structure = StructureJSON(nodes=nodes, edges=edges)

            generator = L2Generator(self._project_root, llm_provider)
            asyncio.run(generator.generate(feature_id, structure))
            self._job_store.complete_job(job.job_id)
        except L2GenerationError as exc:
            self._job_store.fail_job(job.job_id, str(exc))
        except Exception as exc:
            self._job_store.fail_job(job.job_id, str(exc))

    def _run_layer_explanation_job(
        self, job: UpdateJob, feature_id: str, layer: str
    ) -> None:
        """Background thread: generate layer explanation via LLM and persist.

        Uses asyncio.run() to call async llm_provider.complete().
        Catches all exceptions and calls fail_job().
        """
        try:
            config = ConfigManager.load()
            llm_provider = create_provider(config)
        except ConfigError as exc:
            self._job_store.fail_job(job.job_id, f"Config error: {exc}")
            return

        try:
            # Build a simple prompt for the layer explanation
            prompt = (
                f"Generate a concise explanation for the '{layer}' layer "
                f"of feature '{feature_id}'. "
                "Describe the purpose, key components, and interactions at this layer. "
                "Keep the explanation under 300 words."
            )

            explanation_text = asyncio.run(llm_provider.complete(prompt))

            # Persist to .the-door/layer-explanations/<feature_id>/<layer>.json
            cache_dir = (
                self._project_root
                / ".the-door"
                / "layer-explanations"
                / feature_id
            )
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = cache_dir / f"{layer}.json"
            cache_data = {
                "feature_id": feature_id,
                "layer": layer,
                "explanation": explanation_text,
                "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            cache_path.write_text(
                json.dumps(cache_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._job_store.complete_job(job.job_id)
        except Exception as exc:
            self._job_store.fail_job(job.job_id, str(exc))

    # ------------------------------------------------------------------
    # GET /api/diff-explanations/<feature_id>
    # ------------------------------------------------------------------

    def handle_get_diff_explanation(
        self,
        feature_id: str,
        baseline_version_id: str | None,
        current_version_id: str | None,
        output_language: str | None,
    ) -> tuple[int, dict]:
        """Return cached diff explanation or empty state. Never triggers LLM."""
        if not baseline_version_id or not current_version_id or not output_language:
            return 400, self._make_error(
                "missing_params",
                "baseline_version_id, current_version_id, and output_language are required",
                "handle_get_diff_explanation",
            )
        from the_door.core.ui.diff_explanation_store import DiffExplanationStore
        entry = DiffExplanationStore(self._project_root).get(
            feature_id, baseline_version_id, current_version_id, output_language
        )
        return 200, {"explanation": entry}

    # ------------------------------------------------------------------
    # POST /api/diff-explanations/<feature_id>/generate
    # ------------------------------------------------------------------

    def handle_post_diff_explanation_generate(
        self, feature_id: str, body: dict
    ) -> tuple[int, dict]:
        """Generate a diff explanation for one feature via LLM and cache it."""
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

        # Resolve LLM provider (same pattern as _run_layer_explanation_job)
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
            # LLM returned non-JSON — wrap as low-confidence plain text
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
        DiffExplanationStore(self._project_root).save(entry)
        return 200, {"explanation": entry}

    def _collect_diff_context(
        self, feature_id: str, baseline_version_id: str, current_version_id: str
    ) -> dict:
        """Return available diff data for the feature from UpdateReport."""
        latest_path = self._find_latest_report_path()
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
        """Build a structured prompt for diff explanation generation."""
        ctx_text = json.dumps(context, ensure_ascii=False, indent=2) if context else "（無差異資料）"
        return f"""你是版本差異分析助理。根據以下差異資料，以 {output_language} 回答四個問題。

差異資料（feature_id: {feature_id}）：
{ctx_text}

請以 JSON 格式回答，不要包含其他文字：
{{
  "impact_summary": "此差異輸出影響什麼（一句話，面向非工程師）",
  "possible_purpose": "此變更可以達成什麼目的（一句話，用「可能」語氣）",
  "linked_resources": ["相關功能或模組名稱列表，最多 5 個"],
  "caution": "需要注意的地方；資料不足時說明推論依據有限",
  "confidence": "high 或 medium 或 low"
}}

規則：
- 只根據提供的資料推論，不要編造需求、commit message 或不存在的資源。
- 若資料不足，confidence 填 low，caution 說明推論依據有限。
- 文字面向非工程師，避免不必要的技術術語。
- 必須使用 {output_language} 語言回答。"""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_pipeline_job(
        self, job: UpdateJob, old_path: Path, new_path: Path, output_language: str = "zh-Hant"
    ) -> None:
        """Background thread: run pipeline, persist report, update job status."""
        try:
            config = PipelineConfig(old_path=old_path, new_path=new_path, output_language=output_language)
            result = PipelineOrchestrator().run(config, progress_callback=job.update_step)
            report = ReportRenderer().render_json(result)
            self._persist_report(report)
            self._job_store.complete_job(job.job_id)
        except Exception as exc:
            self._job_store.fail_job(job.job_id, str(exc))

    def _persist_report(self, report: dict) -> None:
        """Persist report to .the-door/update-report-<generated_at>.json."""
        generated_at = report.get("generated_at", "unknown")
        safe_ts = generated_at.replace(":", "-")
        filename = f"update-report-{safe_ts}.json"
        dot_dir = self._project_root / ".the-door"
        dot_dir.mkdir(parents=True, exist_ok=True)
        (dot_dir / filename).write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _find_latest_report_path(self) -> Path | None:
        """Find the newest update-report-*.json by generated_at (fallback: mtime)."""
        dot_dir = self._project_root / ".the-door"
        if not dot_dir.exists():
            return None
        candidates = list(dot_dir.glob("update-report-*.json"))
        if not candidates:
            return None

        def sort_key(p: Path):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                val = data.get("generated_at", "")
                if val:
                    return (1, val)
                return (0, p.stat().st_mtime_ns)
            except Exception:
                return (0, p.stat().st_mtime_ns)

        return max(candidates, key=sort_key)

    # ------------------------------------------------------------------
    # GET /api/notes
    # ------------------------------------------------------------------

    def handle_get_notes(
        self,
        mode: str | None,
        feature_id: str | None,
        version_a: str | None,
        version_b: str | None,
    ) -> tuple[int, dict]:
        """Return notes for the given mode + version + feature key."""
        if not mode or not feature_id:
            return 400, self._make_error(
                "missing_params", "mode and feature_id are required", "handle_get_notes"
            )
        if mode not in ("baseline", "current", "diff"):
            return 400, self._make_error(
                "invalid_mode",
                f"mode must be baseline, current, or diff; got: {mode}",
                "handle_get_notes",
            )
        if mode == "baseline" and not version_a:
            return 400, self._make_error(
                "missing_params", "version_a is required for baseline mode", "handle_get_notes"
            )
        if mode == "current" and not version_b:
            return 400, self._make_error(
                "missing_params", "version_b is required for current mode", "handle_get_notes"
            )
        if mode == "diff" and (not version_a or not version_b):
            return 400, self._make_error(
                "missing_params",
                "version_a and version_b are required for diff mode",
                "handle_get_notes",
            )
        from the_door.core.ui.note_store import NoteStore
        notes = NoteStore(self._project_root).list_notes(
            mode, feature_id, version_a, version_b
        )
        return 200, {"notes": notes}

    # ------------------------------------------------------------------
    # POST /api/notes
    # ------------------------------------------------------------------

    def handle_post_notes(self, body: dict) -> tuple[int, dict]:
        """Validate and persist a new user note."""
        mode = body.get("mode")
        feature_id = body.get("feature_id")
        name_input = (body.get("name_input") or "").strip()
        comment = (body.get("comment") or "").strip()
        version_a = body.get("version_a") or None
        version_b = body.get("version_b") or None

        if not mode or not feature_id:
            return 400, self._make_error(
                "missing_params", "mode and feature_id are required", "handle_post_notes"
            )
        if mode not in ("baseline", "current", "diff"):
            return 400, self._make_error(
                "invalid_mode",
                f"mode must be baseline, current, or diff; got: {mode}",
                "handle_post_notes",
            )
        if not name_input:
            return 400, self._make_error(
                "empty_name", "name_input must not be empty", "handle_post_notes"
            )
        if not comment:
            return 400, self._make_error(
                "empty_comment", "comment must not be empty", "handle_post_notes"
            )
        if len(name_input) > 40:
            return 400, self._make_error(
                "name_too_long",
                "name_input must be 40 characters or less",
                "handle_post_notes",
            )
        if len(comment) > 2000:
            return 400, self._make_error(
                "comment_too_long",
                "comment must be 2000 characters or less",
                "handle_post_notes",
            )
        if mode == "baseline" and not version_a:
            return 400, self._make_error(
                "missing_params", "version_a is required for baseline mode", "handle_post_notes"
            )
        if mode == "current" and not version_b:
            return 400, self._make_error(
                "missing_params", "version_b is required for current mode", "handle_post_notes"
            )
        if mode == "diff" and (not version_a or not version_b):
            return 400, self._make_error(
                "missing_params",
                "version_a and version_b are required for diff mode",
                "handle_post_notes",
            )
        from the_door.core.ui.note_store import NoteStore
        note = NoteStore(self._project_root).add_note(
            mode, feature_id, version_a, version_b, name_input, comment
        )
        return 201, {"note": note}

    @staticmethod
    def _make_error(code: str, message: str, source: str) -> dict:
        """Build a standard API_Error_Response dict."""
        return {"error": {"code": code, "message": message, "source": source}}
