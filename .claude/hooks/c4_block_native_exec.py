#!/usr/bin/env python3
"""C4 gate (丙案): block ad-hoc native python code-exec via the Bash tool.

PreToolUse hook on Bash. Denies commands that run inline python (`python -c`) or a
standalone `.py` script — the structural escape hatch for bypassing The Door's MCP
tools (種子 §9.2: agent wrote `_noise_inspect.py` and ran it). Co-require with C3:
gating MCP order alone leaves this hole open.

Allows legitimate dev / CLI invocations: `python -m ...` (pytest, the_door, pip),
`pytest`, `pip`, `git`, `npx`, `the-door`, and anything not invoking python on a
script / inline. jq-free. Fail-open on unparseable / missing command.

Known leak (pilot-acceptable, 種子 認 Bash-parse 必有縫): flags before the script/-c
(e.g. `python -u foo.py`) are not caught. Tighten later if needed.
"""
import json
import re
import sys

# python / python3 / pythonX.Y, then (after whitespace) either `-c`  OR  a non-flag
# token ending in `.py`.  `-m` (module run) is intentionally NOT matched → allowed.
_BLOCK = re.compile(r"\bpython[0-9.]*\s+(-c\b|[^-\s][^\s]*\.py\b)")


def _deny(msg: str) -> int:
    """Write the deny message as UTF-8 bytes (locale-independent) and return 2."""
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
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if _BLOCK.search(cmd):
        return _deny(
            "⛔ 原生 python code-exec 被擋（丙案 C4）：請勿用 `python -c` 或臨時 .py "
            "腳本繞過 The Door 的 MCP 工具。\n"
            "結構性動作請走 mcp__the-door__* 工具；測試請用 `python -m pytest`。\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
