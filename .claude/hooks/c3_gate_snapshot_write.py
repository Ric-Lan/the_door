#!/usr/bin/env python3
"""C3 gate (丙案): deny mcp__the-door__snapshot_write until the edge-residue artifact exists.

PreToolUse hook. Reads the hook event JSON on stdin. If the target codebase has no
`.the-door/edge-residue.json`, exit 2 (deny) with a stderr message teaching the next
step (call the `edge_residue` MCP tool). Otherwise exit 0 (allow).

jq-free (jq is absent on this machine; see C3+C4 spec §2.4). Fail-open on unexpected
input (no codebase_path / unparseable stdin) → exit 0, so the gate never bricks calls
it cannot reason about. Pilot does an EXISTENCE check only — node-coverage / currency
(stale detection) are deferred to C2 (spec §7, 與種子 §3 偏差已登記).
"""
import json
import os
import sys


def _deny(msg: str) -> int:
    """Write the deny message as UTF-8 bytes (locale-independent) and return 2.

    Avoids UnicodeEncodeError on Windows cp950 stderr by going through the binary
    buffer rather than the text layer.
    """
    try:
        sys.stderr.buffer.write(msg.encode("utf-8"))
        sys.stderr.buffer.flush()
    except Exception:
        try:
            sys.stderr.write(msg)
        except Exception:
            pass
    return 2


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # cannot parse → don't block
    tool_input = data.get("tool_input") or {}
    codebase_path = tool_input.get("codebase_path") or ""
    if not codebase_path:
        return 0  # nothing to gate on
    artifact = os.path.join(codebase_path, ".the-door", "edge-residue.json")
    if os.path.isfile(artifact):
        return 0
    return _deny(
        "⛔ snapshot_write 被擋（丙案 C3）：尚未產生 edge-residue artifact。\n"
        "請先呼叫 MCP 工具 `edge_residue`（codebase_path=" + codebase_path + "）\n"
        "產生 " + artifact + " 後再 snapshot_write。\n"
    )


if __name__ == "__main__":
    sys.exit(main())
