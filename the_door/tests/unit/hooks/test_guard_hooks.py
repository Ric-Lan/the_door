"""Guard hook tests (F1): the prototype-edit and `the-door serve` guards.

These two PreToolUse guards were jq-based but jq is systematically absent on this
host (which silently disabled them), so they are now plain python. Black-box: feed
stdin JSON to `.claude/hooks/*.py`, assert exit code + stderr.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
PROTO = "block_prototype_edits.py"
SERVE = "block_the_door_serve.py"


def run_hook(script: str, payload: dict | None = None, *, raw: str | None = None):
    data = raw if raw is not None else json.dumps(payload or {})
    r = subprocess.run(
        [sys.executable, str(HOOKS_DIR / script)],
        input=data, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return r.returncode, r.stderr


# ── block_prototype_edits ─────────────────────────────────────────────

def test_proto_edit_in_prototype_denies():
    rc, err = run_hook(PROTO, {"tool_input": {
        "file_path": "docs/frontend-local-version-viewer/prototype/app.js"}})
    assert rc == 2
    assert "prototype/" in err


def test_proto_edit_windows_backslash_denies():
    rc, _ = run_hook(PROTO, {"tool_input": {
        "file_path": r"C:\repo\docs\frontend-local-version-viewer\prototype\app.js"}})
    assert rc == 2


def test_proto_edit_in_viewer_allows():
    rc, _ = run_hook(PROTO, {"tool_input": {
        "file_path": "docs/frontend-local-version-viewer/viewer/app.js"}})
    assert rc == 0


def test_proto_no_path_allows():
    rc, _ = run_hook(PROTO, {"tool_input": {}})
    assert rc == 0


def test_proto_non_json_allows():
    rc, _ = run_hook(PROTO, raw="not json")
    assert rc == 0


# ── block_the_door_serve ──────────────────────────────────────────────

@pytest.mark.parametrize("cmd", ["the-door serve", "the-door serve --port 8765"])
def test_serve_denies(cmd):
    rc, err = run_hook(SERVE, {"tool_input": {"command": cmd}})
    assert rc == 2
    assert "ui" in err


@pytest.mark.parametrize("cmd", [
    "the-door ui ./project",
    "the-door status .",
    "git commit -m serve",
])
def test_serve_allows_legit(cmd):
    rc, _ = run_hook(SERVE, {"tool_input": {"command": cmd}})
    assert rc == 0


def test_serve_non_json_allows():
    rc, _ = run_hook(SERVE, raw="not json")
    assert rc == 0


def test_serve_no_command_allows():
    rc, _ = run_hook(SERVE, {"tool_input": {}})
    assert rc == 0


# ── settings.json: guards registered as python, no jq残留 ─────────────

def test_settings_registers_python_guards_no_jq():
    data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    cmds = [
        hk["command"]
        for h in data["hooks"]["PreToolUse"]
        for hk in h.get("hooks", [])
    ]
    assert any(PROTO in c for c in cmds)
    assert any(SERVE in c for c in cmds)
    # jq was systematically absent → no hook may depend on it.
    assert not any("jq " in c for c in cmds), "jq-based hook still present"
    for name in (PROTO, SERVE):
        assert (HOOKS_DIR / name).is_file()
