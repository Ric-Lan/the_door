"""system_status MCP tool — report current project state + next-action suggestions."""
from __future__ import annotations

from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.flow_guard import CheckpointOption, FlowGuard
from the_door.core.guidance.state import StateInspector, to_json_dict as state_to_json
from the_door.core.guidance.suggester import NextActionSuggester
from the_door.core.guidance.actions import to_json_dict as action_to_json
from the_door.mcp.tools._response_envelope import wrap

_flow_guard = FlowGuard()


TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "project_path": {"type": "string", "description": "Defaults to CWD if omitted."},
        "choice": {
            "type": "string",
            "description": (
                "CHECKPOINT 選項的 key（'A'、'B'）。"
                "首次呼叫省略；收到 result=null 後帶入選擇重新呼叫。"
            ),
        },
    },
    "required": [],
}


def _get_unanalyzed_git_tags(project_path: Path) -> list[str]:
    """Return git tags that have no corresponding snapshot."""
    import subprocess
    try:
        out = subprocess.run(
            ["git", "-C", str(project_path), "tag"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode != 0:
            return []
        all_tags = [t.strip() for t in out.stdout.splitlines() if t.strip()]
    except Exception:
        return []

    if not all_tags:
        return []

    store = SnapshotStore(project_path)
    try:
        snapshots = store.list_snapshots()
    except Exception:
        return []
    tagged_versions = set()
    for s in snapshots:
        for tag in (s.git_tags or []):
            tagged_versions.add(tag)
    return [t for t in all_tags if t not in tagged_versions]


async def execute(arguments: dict) -> dict:
    project_path = Path(arguments.get("project_path", "."))
    choice = arguments.get("choice")

    state = StateInspector(project_path).inspect()
    actions = NextActionSuggester().suggest(state, context="mcp")

    unanalyzed_tags = _get_unanalyzed_git_tags(project_path)
    if unanalyzed_tags:
        decision = _flow_guard.check(
            "unanalyzed-versions-detected",
            f"偵測到 {len(unanalyzed_tags)} 個未分析版本：{', '.join(unanalyzed_tags)}",
            options=[
                CheckpointOption(
                    "A",
                    f"為 {unanalyzed_tags[0]} 建立 snapshot",
                    f"extract_structure(codebase_path='<path>')",
                ),
                CheckpointOption("B", "略過，繼續"),
            ],
            choice=choice,
        )
        if not decision.is_resolved:
            payload: dict = {"_decision": decision}
            return wrap(payload, project_path=project_path, context="mcp")

    return {
        "state": state_to_json(state),
        "next_actions": [action_to_json(a) for a in actions],
    }
