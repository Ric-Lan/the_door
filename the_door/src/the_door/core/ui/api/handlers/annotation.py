"""AnnotationHandlers — GET/POST /api/notes, GET /api/doubts."""
from __future__ import annotations

from the_door.core.scope.doubt_store import DoubtStore
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.note_store import NoteStore
from the_door.core.ui.serializers import serialize_doubt


class AnnotationHandlers:
    def __init__(self, ctx: APIContext) -> None:
        self._ctx = ctx

    # ------------------------------------------------------------------
    # GET /api/notes
    # ------------------------------------------------------------------

    def get_notes(
        self,
        ctx=None,
        *,
        mode=None,
        feature_id=None,
        version_a=None,
        version_b=None,
        **_,
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
        notes = NoteStore(self._ctx.project_root).list_notes(
            mode, feature_id, version_a, version_b
        )
        return 200, {"notes": notes}

    # ------------------------------------------------------------------
    # POST /api/notes
    # ------------------------------------------------------------------

    def post_notes(self, ctx=None, *, body=None, **_) -> tuple[int, dict]:
        """Validate and persist a new user note."""
        if body is None:
            body = {}
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
        note = NoteStore(self._ctx.project_root).add_note(
            mode, feature_id, version_a, version_b, name_input, comment
        )
        return 201, {"note": note}

    # ------------------------------------------------------------------
    # GET /api/doubts
    # ------------------------------------------------------------------

    def doubts(self, ctx=None, **_) -> tuple[int, dict]:
        """Return all doubts with summary."""
        try:
            doubts = DoubtStore(self._ctx.project_root).list_doubts()
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

    @staticmethod
    def _make_error(code: str, message: str, source: str) -> dict:
        return {"error": {"code": code, "message": message, "source": source}}
