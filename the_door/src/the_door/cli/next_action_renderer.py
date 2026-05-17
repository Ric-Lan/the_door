import json
import os
import sys

from the_door.core.guidance.actions import NextAction, to_json_dict as action_to_json


_LIMIT = 3


def render_next_block(actions: list[NextAction], *, json_mode: bool | None = None, limit: int = _LIMIT) -> None:
    if json_mode is None:
        json_mode = os.environ.get("THE_DOOR_NEXT_FORMAT", "").lower() == "json"
    sliced = actions[:limit]
    if json_mode:
        sys.stderr.write(json.dumps({"next_actions": [action_to_json(a) for a in sliced]}, ensure_ascii=False) + "\n")
        return
    sys.stderr.write("Next:\n")
    for i, action in enumerate(sliced, start=1):
        form = action.cli_command or action.mcp_tool or action.viewer_route or ""
        sys.stderr.write(f"  {i}. {form}                ({action.title})\n")


def render_remediation(remediation, *, json_mode: bool | None = None) -> None:
    if json_mode is None:
        json_mode = os.environ.get("THE_DOOR_NEXT_FORMAT", "").lower() == "json"
    if json_mode:
        sys.stderr.write(json.dumps({"error": {"code": remediation.code, "message": remediation.message,
                                               "next_action": action_to_json(remediation.next_action) if remediation.next_action else None}}, ensure_ascii=False) + "\n")
        return
    sys.stderr.write(f"Error: {remediation.message}\n")
    if remediation.next_action and remediation.next_action.cli_command:
        sys.stderr.write(f"Try: {remediation.next_action.cli_command}\n")
