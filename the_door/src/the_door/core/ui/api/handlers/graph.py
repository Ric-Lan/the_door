"""GraphHandlers — L1, L2, structure, and layer-explanation read endpoints.

Note (T5-V): L2 / layer-explanation **generation** (POST .../generate) was retired
(丙案 D1, headless viewer cannot host an agent-as-LLM at click time). Only the GET
read/display handlers remain; L2Generator is now a display-only loader.
"""
from __future__ import annotations

import json
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.guidance.actions import NextAction
from the_door.core.guidance.remediation import Remediation, make_error_envelope
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.graph_view_model import (
    build_l1_graph_view_model_from_snapshot,
    build_l2_graph_view_model,
)
from the_door.core.ui.l2_generator import L2Generator

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

    @staticmethod
    def _make_error(code: str, message: str, source: str) -> dict:
        return {"error": {"code": code, "message": message, "source": source}}
