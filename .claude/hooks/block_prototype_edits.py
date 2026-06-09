#!/usr/bin/env python3
"""Guard hook: block edits to the deprecated viewer prototype/ tree.

PreToolUse hook on Edit|Write|NotebookEdit. The only正式版 frontend lives in
docs/frontend-local-version-viewer/viewer/; prototype/ is废弃. Was a jq-based
hook, but jq is systematically absent on this host (which silently disabled it),
so it is now plain python. jq-free. Fail-open on unparseable / missing path.
"""
import json
import sys

_MARKER = "frontend-local-version-viewer/prototype/"


def _deny(msg: str) -> int:
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
        return 0
    path = (data.get("tool_input") or {}).get("file_path") or ""
    # Normalise backslashes so Windows paths match the forward-slash marker.
    if _MARKER in path.replace("\\", "/"):
        return _deny(
            "⛔ prototype/ 已廢棄，請改寫 docs/frontend-local-version-viewer/viewer/\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
