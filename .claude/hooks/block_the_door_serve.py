#!/usr/bin/env python3
"""Guard hook: block the non-existent `the-door serve` command.

PreToolUse hook on Bash. The local server command is `the-door ui <test-target>`,
not `serve`. Was a jq-based hook, but jq is systematically absent on this host
(which silently disabled it), so it is now plain python. jq-free. Fail-open on
unparseable / missing command.
"""
import json
import re
import sys

_BLOCK = re.compile(r"\bthe-door\s+serve\b")


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
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if _BLOCK.search(cmd):
        return _deny(
            "⛔ 指令是 the-door ui <test-target>，不是 serve。請改用 ui 子命令。\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
