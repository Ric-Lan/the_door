"""IntegrationHandlers — GET /api/integration（純結構整合健檢、零 agent）。"""
from __future__ import annotations

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.guidance.remediation import Remediation, make_error_envelope
from the_door.core.integration.checker import run_integration_check
from the_door.core.ui.api.context import APIContext


class IntegrationHandlers:
    def __init__(self, ctx: APIContext) -> None:
        self._ctx = ctx

    def get_integration(self, ctx=None, *, version_id=None, **_) -> tuple[int, dict]:
        """GET /api/integration?version_id=<id> — per-relation 判定 + 徽章聚合 + rollup。"""
        store = SnapshotStore(self._ctx.project_root)
        snapshot = store.get_snapshot(version_id) if version_id else store.get_latest()
        if snapshot is None:
            msg = (f"Snapshot '{version_id}' not found." if version_id
                   else "尚未為這個專案產出 L1 分析")
            return 404, make_error_envelope(
                code="no_integration_data", message=msg,
                remediation=Remediation(code="no_integration_data", message=msg),
                source="get_integration",
            )
        payload = run_integration_check(snapshot, self._ctx.project_root, max_hops=2)
        return 200, payload
