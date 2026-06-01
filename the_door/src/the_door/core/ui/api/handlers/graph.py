"""GraphHandlers — L1, L2, structure, and layer-explanation endpoints."""
from __future__ import annotations

import asyncio
import datetime
import json
import threading
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.guidance.actions import NextAction
from the_door.core.guidance.remediation import Remediation, make_error_envelope
from the_door.core.llm.config_manager import ConfigManager, ConfigError
from the_door.core.llm.provider import create_provider
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.graph_view_model import (
    build_l1_graph_view_model_from_snapshot,
    build_l2_graph_view_model,
)
from the_door.core.ui.job_store import JobStore, UpdateJob
from the_door.core.ui.l2_generator import L2Generator, L2GenerationError

_VALID_LAYERS = {"l1", "l2", "l3"}


class GraphHandlers:
    def __init__(self, ctx: APIContext) -> None:
        self._ctx = ctx

    # ------------------------------------------------------------------
    # GET /api/l1
    # ------------------------------------------------------------------

    def get_l1(self, ctx=None, *, version_id=None, **_) -> tuple[int, dict]:
        """GET /api/l1 — return L1_Graph_ViewModel from a VersionSnapshot."""
        try:
            store = SnapshotStore(self._ctx.project_root)
            snapshot = store.get_snapshot(version_id) if version_id else store.get_latest()
            if snapshot is None:
                msg = (
                    f"Snapshot '{version_id}' not found."
                    if version_id
                    else "尚未為這個專案產出 L1 分析"
                )
                return 404, make_error_envelope(
                    code="no_l1_data",
                    message=msg,
                    remediation=Remediation(
                        code="no_l1_data",
                        message=msg,
                        next_action=NextAction(
                            id="analyze.first_time",
                            title="首次分析",
                            rationale="尚未在此專案產出任何 L1 快照，先跑一次 analyze。",
                            priority=1,
                            cli_command=(
                                f"the-door analyze {self._ctx.project_root.as_posix()}"
                            ),
                        ),
                    ),
                    source="handle_get_l1",
                )
            l1_snapshot_dict = {
                fid: {
                    "label": fs.label,
                    "confidence": fs.confidence,
                    "description": fs.description,
                    "trigger_description": fs.trigger_description,
                    "confidence_reason": fs.confidence_reason,
                    "source_nodes": list(fs.source_nodes) if fs.source_nodes else [],
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
    # GET /api/l2/<feature_id>
    # ------------------------------------------------------------------

    def get_l2(self, ctx=None, *, feature_id=None, **_) -> tuple[int, dict]:
        """GET /api/l2/<feature_id> — return L2_Graph_ViewModel if cached."""
        try:
            l2_output = L2Generator.load(self._ctx.project_root, feature_id)
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
    # POST /api/l2/<feature_id>/generate
    # ------------------------------------------------------------------

    def generate_l2(self, ctx=None, *, feature_id=None, **_) -> tuple[int, dict]:
        """POST /api/l2/<feature_id>/generate — start async L2 generation job."""
        # 1. Check structure.json exists
        structure_path = self._ctx.project_root / ".the-door" / "structure.json"
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
        job = self._ctx.job_store.try_create_job()
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
    # GET /api/structure
    # ------------------------------------------------------------------

    def get_structure(self, ctx=None, **_) -> tuple[int, dict]:
        """GET /api/structure — return structure.json content."""
        structure_path = self._ctx.project_root / ".the-door" / "structure.json"
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
    # GET /api/layer-explanation/<feature_id>/<layer>
    # ------------------------------------------------------------------

    def get_layer_explanation(self, ctx=None, *, feature_id=None, layer=None, **_) -> tuple[int, dict]:
        """GET /api/layer-explanation/<feature_id>/<layer> — return cached explanation."""
        if layer not in _VALID_LAYERS:
            return 400, self._make_error(
                code="invalid_layer",
                message=f"Invalid layer '{layer}'. Must be one of: l1, l2, l3.",
                source="handle_get_layer_explanation",
            )

        cache_path = (
            self._ctx.project_root
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
    # POST /api/layer-explanation/<feature_id>/<layer>/generate
    # ------------------------------------------------------------------

    def generate_layer_explanation(self, ctx=None, *, feature_id=None, layer=None, **_) -> tuple[int, dict]:
        """POST /api/layer-explanation/<feature_id>/<layer>/generate — start explanation job."""
        if layer not in _VALID_LAYERS:
            return 400, self._make_error(
                code="invalid_layer",
                message=f"Invalid layer '{layer}'. Must be one of: l1, l2, l3.",
                source="handle_post_layer_explanation_generate",
            )

        job = self._ctx.job_store.try_create_job()
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
    # Background thread methods
    # ------------------------------------------------------------------

    def _run_l2_generate_job(
        self, job: UpdateJob, feature_id: str, structure_json: dict
    ) -> None:
        try:
            config = ConfigManager.load()
            llm_provider = create_provider(config)
        except ConfigError as exc:
            self._ctx.job_store.fail_job(job.job_id, f"Config error: {exc}")
            return

        try:
            from the_door.models import StructureJSON, ASTNode, Edge as StructureEdge

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

            generator = L2Generator(self._ctx.project_root, llm_provider)
            asyncio.run(generator.generate(feature_id, structure))
            self._ctx.job_store.complete_job(job.job_id)
        except L2GenerationError as exc:
            self._ctx.job_store.fail_job(job.job_id, str(exc))
        except Exception as exc:
            self._ctx.job_store.fail_job(job.job_id, str(exc))

    def _run_layer_explanation_job(
        self, job: UpdateJob, feature_id: str, layer: str
    ) -> None:
        try:
            config = ConfigManager.load()
            llm_provider = create_provider(config)
        except ConfigError as exc:
            self._ctx.job_store.fail_job(job.job_id, f"Config error: {exc}")
            return

        try:
            prompt = (
                f"Generate a concise explanation for the '{layer}' layer "
                f"of feature '{feature_id}'. "
                "Describe the purpose, key components, and interactions at this layer. "
                "Keep the explanation under 300 words."
            )

            explanation_text = asyncio.run(llm_provider.complete(prompt))

            cache_dir = (
                self._ctx.project_root
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
            self._ctx.job_store.complete_job(job.job_id)
        except Exception as exc:
            self._ctx.job_store.fail_job(job.job_id, str(exc))

    @staticmethod
    def _make_error(code: str, message: str, source: str) -> dict:
        return {"error": {"code": code, "message": message, "source": source}}
