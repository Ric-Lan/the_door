"""Doubt record persistence and state machine management.

All file I/O uses encoding="utf-8" for Windows compatibility.
Doubt records stored as individual JSON files in .the-door/doubts/.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path

import jsonschema

from the_door.models import (
    DoubtNotFoundError,
    DoubtRecord,
    DoubtSummary,
    DoubtTerminalError,
    InvalidTransitionError,
    Resolution,
    StateTransition,
)
from the_door.core.scope.doubt_lifecycle import DoubtLifecycle

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema loading — same pattern as core/scope/scope_verifier.py
# ---------------------------------------------------------------------------
_SCHEMAS_DIR = files("the_door") / "schemas"
_DOUBT_RECORD_SCHEMA_PATH = _SCHEMAS_DIR / "doubt-record.schema.json"

_doubt_schema: dict | None = None


def _load_doubt_schema() -> dict:
    """Load the doubt-record JSON schema."""
    with _DOUBT_RECORD_SCHEMA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _get_doubt_schema() -> dict:
    """Return the cached doubt-record schema, loading on first access."""
    global _doubt_schema  # noqa: PLW0603
    if _doubt_schema is None:
        _doubt_schema = _load_doubt_schema()
    return _doubt_schema



class DoubtStore:
    """疑義記錄的持久化存儲與狀態機管理。

    所有檔案 I/O 使用 encoding="utf-8"（Windows 相容）。
    疑義記錄存為 .the-door/doubts/<doubt_id>.json。
    """

    def __init__(self, project_root: Path) -> None:
        self._doubts_dir = project_root / ".the-door" / "doubts"
        self._lifecycle = DoubtLifecycle()

    # =================================================================
    # CRUD methods
    # =================================================================

    def create_doubt(
        self,
        *,
        source_node: str,
        doubt_type: str,
        created_by: str,
    ) -> DoubtRecord:
        """建立新的疑義記錄。

        - 產生 UUID v4 作為 doubt_id
        - 初始狀態：discovered
        - 持久化到 .the-door/doubts/<doubt_id>.json
        """
        doubt_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        doubt = DoubtRecord(
            doubt_id=doubt_id,
            source_node=source_node,
            doubt_type=doubt_type,
            current_state="discovered",
            created_by=created_by,
            created_at=now,
            updated_at=now,
            assigned_to=None,
            state_history=[],
            resolution=None,
        )

        self._doubts_dir.mkdir(parents=True, exist_ok=True)
        self._persist(doubt)
        return doubt

    def get_doubt(self, doubt_id: str) -> DoubtRecord:
        """依 doubt_id 載入疑義記錄。

        Raises:
            DoubtNotFoundError: 找不到指定的疑義記錄
        """
        file_path = self._doubts_dir / f"{doubt_id}.json"
        if not file_path.exists():
            raise DoubtNotFoundError(doubt_id)

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            schema = _get_doubt_schema()
            jsonschema.validate(data, schema, cls=jsonschema.Draft202012Validator)
            return self._deserialize_doubt(data)
        except (json.JSONDecodeError, jsonschema.ValidationError) as exc:
            logger.warning("Corrupted or invalid doubt file: %s — %s", file_path, exc)
            raise DoubtNotFoundError(doubt_id) from exc

    def list_doubts(
        self,
        *,
        states: list[str] | None = None,
        types: list[str] | None = None,
        source_node: str | None = None,
        active_only: bool = False,
    ) -> list[DoubtRecord]:
        """列出疑義記錄，支援篩選。

        1. 載入所有 doubt JSON 檔案
        2. 對所有 discovered/investigating 疑義執行 timeout 檢查（lazy evaluation）
        3. 套用篩選條件
        4. 依 created_at 降序排列（最新優先）
        5. 回傳篩選後的結果
        """
        doubts = self._load_all_doubts()

        # Lazy timeout evaluation: check timeouts before applying filters
        for i, doubt in enumerate(doubts):
            if doubt.current_state in ("discovered", "investigating"):
                updated = self.check_timeouts(doubt)
                if updated is not None:
                    doubts[i] = updated

        # Apply filters
        if states is not None:
            doubts = [d for d in doubts if d.current_state in states]
        if types is not None:
            doubts = [d for d in doubts if d.doubt_type in types]
        if source_node is not None:
            doubts = [d for d in doubts if d.source_node == source_node]
        if active_only:
            doubts = [d for d in doubts if not self._lifecycle.is_terminal(d.current_state)]

        # Sort by created_at descending (newest first)
        doubts.sort(key=lambda d: d.created_at, reverse=True)
        return doubts

    def get_summary(self) -> DoubtSummary:
        """回傳疑義聚合統計：總活躍數、各狀態計數、各類型計數。"""
        doubts = self._load_all_doubts()

        by_state: dict[str, int] = {}
        by_type: dict[str, int] = {}
        total_active = 0

        for d in doubts:
            by_state[d.current_state] = by_state.get(d.current_state, 0) + 1
            by_type[d.doubt_type] = by_type.get(d.doubt_type, 0) + 1
            if not self._lifecycle.is_terminal(d.current_state):
                total_active += 1

        return DoubtSummary(
            total_active=total_active,
            by_state=by_state,
            by_type=by_type,
        )

    def has_active_doubt(self, source_node: str, doubt_type: str) -> bool:
        """檢查是否已有同 source_node + doubt_type 的活躍（非終態）疑義。"""
        doubts = self._load_all_doubts()
        return any(
            d.source_node == source_node
            and d.doubt_type == doubt_type
            and not self._lifecycle.is_terminal(d.current_state)
            for d in doubts
        )

    # =================================================================
    # State transition operations
    # =================================================================

    def assign(
        self,
        doubt_id: str,
        assignee: str,
        actor: str,
    ) -> DoubtRecord:
        """discovered → investigating：指派調查者。"""
        return self.transition(doubt_id, "investigating", actor=actor, assignee=assignee)

    def explain(
        self,
        doubt_id: str,
        description: str,
        resolved_by: str,
    ) -> DoubtRecord:
        """investigating → explained：確認為誤報。"""
        return self.transition(doubt_id, "explained", actor=resolved_by, description=description)

    def fix(
        self,
        doubt_id: str,
        description: str,
        resolved_by: str,
    ) -> DoubtRecord:
        """investigating → fixed：問題已修正。"""
        return self.transition(doubt_id, "fixed", actor=resolved_by, description=description)

    def escalate(
        self,
        doubt_id: str,
        reason: str,
        actor: str,
    ) -> DoubtRecord:
        """discovered/investigating → escalated：升級至管理層。"""
        return self.transition(doubt_id, "escalated", actor=actor, reason=reason)

    def resolve_escalation(
        self,
        doubt_id: str,
        resolution_type: str,
        description: str,
        resolved_by: str,
    ) -> DoubtRecord:
        """escalated → explained/fixed/accepted_risk：管理層決策。"""
        return self.transition(doubt_id, resolution_type, actor=resolved_by, description=description)

    # =================================================================
    # Timeout mechanism
    # =================================================================

    def check_timeouts(self, doubt: DoubtRecord) -> DoubtRecord | None:
        """檢查單一疑義是否超時，若超時則自動升級。

        基準時間規則：
        - discovered 狀態：從 created_at 算起，超過 discovery_timeout_days → escalated
        - investigating 狀態：從 state_history 最後一筆 entry 的 timestamp 算起
          （即進入 investigating 的轉換時間），超過 investigation_timeout_days → escalated
        - 其他狀態：回傳 None（不適用 timeout）
        - 使用 UTC 時間戳比較

        Returns:
            更新後的 DoubtRecord（若已升級），或 None（未超時或不適用）
        """
        if doubt.current_state not in ("discovered", "investigating"):
            return None

        discovery_timeout_days, investigation_timeout_days = self._load_timeout_config()
        now = datetime.now(timezone.utc)

        if doubt.current_state == "discovered":
            # Parse created_at — handle both 'Z' suffix and '+00:00'
            created_at_str = doubt.created_at
            if created_at_str.endswith("Z"):
                created_at_str = created_at_str[:-1] + "+00:00"
            created_at = datetime.fromisoformat(created_at_str)
            elapsed = now - created_at
            if elapsed.total_seconds() >= discovery_timeout_days * 86400:
                return self._apply_transition(
                    doubt, "escalated", "system_timeout",
                    reason=f"Auto-escalated: no investigator assigned within {discovery_timeout_days} days",
                )
            return None

        if doubt.current_state == "investigating":
            # Use the timestamp of the LAST entry in state_history
            if not doubt.state_history:
                return None
            last_transition = doubt.state_history[-1]
            last_ts_str = last_transition.timestamp
            if last_ts_str.endswith("Z"):
                last_ts_str = last_ts_str[:-1] + "+00:00"
            last_ts = datetime.fromisoformat(last_ts_str)
            elapsed = now - last_ts
            if elapsed.total_seconds() >= investigation_timeout_days * 86400:
                return self._apply_transition(
                    doubt, "escalated", "system_timeout",
                    reason=f"Auto-escalated: no progress in {investigation_timeout_days} days",
                )
            return None

        return None  # pragma: no cover

    def _load_timeout_config(self) -> tuple[int, int]:
        """從 .the-door/scope-config.json 載入 timeout 設定。

        scope-config.json 為 project-level 配置，格式：
        {"discovery_timeout_days": 3, "investigation_timeout_days": 7}

        若檔案不存在或欄位缺失，使用預設值：
        discovery_timeout_days=3, investigation_timeout_days=7
        """
        default_discovery = 3
        default_investigation = 7
        config_path = self._doubts_dir.parent / "scope-config.json"

        if not config_path.exists():
            return (default_discovery, default_investigation)

        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to parse scope-config.json: %s — using defaults", exc
            )
            return (default_discovery, default_investigation)

        discovery = data.get("discovery_timeout_days", default_discovery)
        investigation = data.get("investigation_timeout_days", default_investigation)

        return (int(discovery), int(investigation))

    # =================================================================
    # Internal methods
    # =================================================================

    def transition(self, doubt_id, target_state, *, actor,
                   reason=None, assignee=None, description=None):
        """Single public entry: load, plan & apply any transition by target state."""
        doubt = self.get_doubt(doubt_id)
        return self._apply_transition(doubt, target_state, actor,
                                      reason=reason, assignee=assignee,
                                      description=description)

    def _apply_transition(self, doubt, to_state, actor, *, reason=None,
                          assignee=None, description=None):
        plan = self._lifecycle.plan(
            doubt_id=doubt.doubt_id, from_state=doubt.current_state,
            to_state=to_state, actor=actor, reason=reason,
            assignee=assignee, description=description,
        )
        doubt.current_state = to_state
        doubt.updated_at = plan.transition.timestamp
        doubt.state_history.append(plan.transition)
        if plan.resolution is not None:
            doubt.resolution = plan.resolution
        if plan.set_assigned_to:
            doubt.assigned_to = plan.assigned_to
        self._persist(doubt)
        return doubt

    def _serialize_doubt(self, doubt: DoubtRecord) -> dict:
        """將 DoubtRecord 序列化為 JSON-compatible dict。"""
        data: dict = {
            "doubt_id": doubt.doubt_id,
            "source_node": doubt.source_node,
            "doubt_type": doubt.doubt_type,
            "current_state": doubt.current_state,
            "created_by": doubt.created_by,
            "created_at": doubt.created_at,
            "updated_at": doubt.updated_at,
            "assigned_to": doubt.assigned_to,
            "state_history": [
                {
                    "from_state": t.from_state,
                    "to_state": t.to_state,
                    "timestamp": t.timestamp,
                    "actor": t.actor,
                    "reason": t.reason,
                }
                for t in doubt.state_history
            ],
            "resolution": (
                {
                    "type": doubt.resolution.type,
                    "description": doubt.resolution.description,
                    "resolved_by": doubt.resolution.resolved_by,
                    "resolved_at": doubt.resolution.resolved_at,
                }
                if doubt.resolution is not None
                else None
            ),
        }
        return data

    def _deserialize_doubt(self, data: dict) -> DoubtRecord:
        """從 JSON dict 反序列化為 DoubtRecord。"""
        state_history = [
            StateTransition(
                from_state=t["from_state"],
                to_state=t["to_state"],
                timestamp=t["timestamp"],
                actor=t["actor"],
                reason=t.get("reason"),
            )
            for t in data.get("state_history", [])
        ]

        resolution_data = data.get("resolution")
        resolution = None
        if resolution_data is not None:
            resolution = Resolution(
                type=resolution_data["type"],
                description=resolution_data["description"],
                resolved_by=resolution_data["resolved_by"],
                resolved_at=resolution_data["resolved_at"],
            )

        return DoubtRecord(
            doubt_id=data["doubt_id"],
            source_node=data["source_node"],
            doubt_type=data["doubt_type"],
            current_state=data["current_state"],
            created_by=data["created_by"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            assigned_to=data.get("assigned_to"),
            state_history=state_history,
            resolution=resolution,
        )

    def _persist(self, doubt: DoubtRecord) -> None:
        """將 DoubtRecord 寫入 JSON 檔案（encoding="utf-8"）。

        Validates against schema before writing.
        """
        self._doubts_dir.mkdir(parents=True, exist_ok=True)
        data = self._serialize_doubt(doubt)

        # Validate against schema before writing
        schema = _get_doubt_schema()
        jsonschema.validate(data, schema, cls=jsonschema.Draft202012Validator)

        file_path = self._doubts_dir / f"{doubt.doubt_id}.json"
        file_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _load_doubt(self, path: Path) -> DoubtRecord | None:
        """Load and validate a single doubt file. Return None on corruption."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            schema = _get_doubt_schema()
            jsonschema.validate(data, schema, cls=jsonschema.Draft202012Validator)
            return self._deserialize_doubt(data)
        except (json.JSONDecodeError, jsonschema.ValidationError) as exc:
            logger.warning("Skipping corrupted doubt file: %s — %s", path, exc)
            return None

    def _load_all_doubts(self) -> list[DoubtRecord]:
        """Load all doubt files from disk. Skip corrupted files with warning."""
        if not self._doubts_dir.exists():
            return []

        doubts: list[DoubtRecord] = []
        for file_path in self._doubts_dir.glob("*.json"):
            doubt = self._load_doubt(file_path)
            if doubt is not None:
                doubts.append(doubt)
        return doubts
