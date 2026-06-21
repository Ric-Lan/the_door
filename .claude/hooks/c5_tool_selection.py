#!/usr/bin/env python3
"""C5 gate: block shell commands that have dedicated Claude Code project tools.

PreToolUse hook on Bash. Denies: grep/rg (→ Grep), cat/head/tail (→ Read),
find (→ Glob). Fail-open on unparseable input. Allows everything else.
"""
import json
import sys
import re

_BLOCKED = {
    "grep": "Grep 工具（pattern, path, output_mode）",
    "rg":   "Grep 工具（pattern, path, output_mode）",
    "cat":  "Read 工具（file_path, offset, limit）",
    "head": "Read 工具（file_path, offset, limit）",
    "tail": "Read 工具（file_path, offset, limit）",
    "find": "Glob 工具（pattern, path）",
}

# matches optional leading KEY=VALUE env-var assignments, captures first real token
_FIRST_TOKEN = re.compile(r"^(?:[A-Z_][A-Z0-9_]*=\S*\s+)*(\S+)", re.IGNORECASE)


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
    m = _FIRST_TOKEN.match(cmd.strip())
    if not m:
        return 0
    tok = m.group(1).lower()
    # Strip path prefix (e.g. /usr/bin/grep → grep)
    tok = tok.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if tok not in _BLOCKED:
        return 0
    redirect = _BLOCKED[tok]
    return _deny(
        f"⛔ C5 工具選擇攔截：偵測到 `{tok}`。\n"
        f"→ 請改用 {redirect}。\n"
        f"Bash 只用於：git、curl、npm/npx、pip、the-door、pytest、rm、mkdir "
        f"等無對應專案工具的操作。\n"
    )


if __name__ == "__main__":
    sys.exit(main())
