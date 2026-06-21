"""BlockHandlers — GET /api/blocks（讀當前快照的 L1.5 區塊樹，零 agent）。"""
from __future__ import annotations

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.guidance.remediation import Remediation, make_error_envelope
from the_door.core.ui.api.context import APIContext


class BlockHandlers:
    def __init__(self, ctx: APIContext) -> None:
        self._ctx = ctx

    def get_blocks(self, ctx=None, *, version_id=None, **_) -> tuple[int, dict]:
        """GET /api/blocks?version_id=<id> — 兩層區塊樹 + 每葉區塊成員。"""
        store = SnapshotStore(self._ctx.project_root)
        snapshot = store.get_snapshot(version_id) if version_id else store.get_latest()
        if snapshot is None:
            msg = (f"Snapshot '{version_id}' not found." if version_id
                   else "尚未為這個專案產出 L1 分析")
            return 404, make_error_envelope(
                code="no_block_data", message=msg,
                remediation=Remediation(code="no_block_data", message=msg),
                source="get_blocks",
            )
        feat = snapshot.l1_snapshot
        blocks = []
        for bid, b in snapshot.l1_5_snapshot.items():
            blocks.append({
                "block_id": b.block_id,
                "label": b.label,
                "responsibility": b.responsibility,
                "parent_block_id": b.parent_block_id,
                "is_new_this_version": b.is_new_this_version,
                "features": [
                    {
                        "feature_id": fid,
                        "label": feat[fid].label if fid in feat else fid,
                        "confidence": feat[fid].confidence if fid in feat else None,
                        "description": feat[fid].description if fid in feat else "",
                    }
                    for fid in b.related_features
                ],
            })
        return 200, {"blocks": blocks}
