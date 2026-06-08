"""C3+C4 執行序 gate hook 測試（丙案）。

黑箱：以 subprocess 餵 stdin JSON 給 `.claude/hooks/*.py`，斷言 exit code＋stderr。
對應 spec §6（G-1..G-10）／plan Task 1-2。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
C3 = "c3_gate_snapshot_write.py"
C4 = "c4_block_native_exec.py"


def run_hook(script: str, payload: dict | None = None, *, raw: str | None = None):
    data = raw if raw is not None else json.dumps(payload or {})
    r = subprocess.run(
        [sys.executable, str(HOOKS_DIR / script)],
        input=data, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return r.returncode, r.stderr


# ── C3: gate snapshot_write on edge-residue artifact ──────────────────

def test_c3_artifact_missing_denies(tmp_path):
    rc, err = run_hook(C3, {"tool_input": {"codebase_path": str(tmp_path)}})
    assert rc == 2
    assert "edge_residue" in err  # 教學訊息指回工具（誠實紅：缺腳本時 stderr 不含此）


def test_c3_artifact_present_allows(tmp_path):
    art = tmp_path / ".the-door"
    art.mkdir()
    (art / "edge-residue.json").write_text("{}", encoding="utf-8")
    rc, _ = run_hook(C3, {"tool_input": {"codebase_path": str(tmp_path)}})
    assert rc == 0


def test_c3_no_codebase_path_allows():
    rc, _ = run_hook(C3, {"tool_input": {}})
    assert rc == 0  # fail-open


def test_c3_non_json_allows():
    rc, _ = run_hook(C3, raw="not json at all")
    assert rc == 0  # fail-open


# ── C4: block native python code-exec ────────────────────────────────

def test_c4_python_inline_denies():
    rc, err = run_hook(C4, {"tool_input": {"command": 'python -c "import the_door"'}})
    assert rc == 2
    assert "C4" in err  # 教學訊息（誠實紅）


@pytest.mark.parametrize("cmd", ["python foo.py", "python ./a/b.py", "python3 script.py"])
def test_c4_python_script_denies(cmd):
    rc, _ = run_hook(C4, {"tool_input": {"command": cmd}})
    assert rc == 2


@pytest.mark.parametrize("cmd", [
    "PYTHONUTF8=1 python -m pytest -q",
    "pytest tests/",
    "pip install -e ./the_door",
    "git commit -m x",
    "npx vitest run",
    "the-door ui .",
    "python -m the_door mcp-serve",
])
def test_c4_allows_legit(cmd):
    rc, _ = run_hook(C4, {"tool_input": {"command": cmd}})
    assert rc == 0


def test_c4_non_json_allows():
    rc, _ = run_hook(C4, raw="not json")
    assert rc == 0


def test_c4_no_command_allows():
    rc, _ = run_hook(C4, {"tool_input": {}})
    assert rc == 0


# ── G-9: settings.json 完整性 ────────────────────────────────────────

def test_settings_registers_c3_c4():
    data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    pre = data["hooks"]["PreToolUse"]
    matchers = [h.get("matcher") for h in pre]
    assert "mcp__the-door__snapshot_write" in matchers
    cmds = [hk["command"] for h in pre for hk in h.get("hooks", [])]
    assert any(C3 in c for c in cmds)
    assert any(C4 in c for c in cmds)
    for name in (C3, C4):
        assert (HOOKS_DIR / name).is_file()


# ── G-10: 真實 command 字串守衛邏輯（bash） ──────────────────────────

def _working_bash() -> str | None:
    """Return a bash that actually runs POSIX commands, else None.

    On Windows `bash` may resolve to the WSL launcher (`C:\\Windows\\System32\\bash.exe`),
    which is broken if no WSL distro/VM-platform is installed (exit 1). The real Claude
    Code hook shell is git-bash, which works. Probe before relying on it.
    """
    if shutil.which("bash") is None:
        return None
    try:
        r = subprocess.run(
            ["bash", "-c", "echo ok"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10,
        )
    except Exception:
        return None
    return "bash" if r.returncode == 0 and r.stdout.strip() == "ok" else None


@pytest.mark.skipif(_working_bash() is None, reason="no working POSIX bash (WSL stub?)")
def test_c4_command_string_guard_via_bash():
    data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    pre = data["hooks"]["PreToolUse"]
    c4_cmd = next(
        hk["command"]
        for h in pre for hk in h.get("hooks", [])
        if C4 in hk["command"]
    )

    def run(payload: dict, project_dir: str):
        env = dict(os.environ)
        env["CLAUDE_PROJECT_DIR"] = project_dir
        r = subprocess.run(
            ["bash", "-c", c4_cmd],
            input=json.dumps(payload), capture_output=True, text=True,
            encoding="utf-8", errors="replace", env=env,
        )
        return r.returncode, (r.stderr or "") + (r.stdout or "")

    root = REPO_ROOT.as_posix()  # 正斜線：bash [ -f ] 與 Windows-python open 兩端皆接受
    rc, out = run({"tool_input": {"command": 'python -c "x"'}}, root)
    assert rc == 2, "deny case rc=%s out=%r" % (rc, out)
    rc, _ = run({"tool_input": {"command": "git status"}}, root)
    assert rc == 0
    rc, _ = run({"tool_input": {"command": 'python -c "x"'}}, "/no/such/dir")
    assert rc == 0  # fail-open（腳本缺）
