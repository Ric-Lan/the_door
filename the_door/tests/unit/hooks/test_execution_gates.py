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


# ── C3 gate (C2-upgraded): gate snapshot_write on the checklist ───────
# C2 replaced the bare edge-residue.json existence check with a checklist that
# carries node-coverage + contract currency.

from the_door.core.checklist import STAGE_EDGE_RESIDUE, stamp_stage  # noqa: E402
from the_door.models.snapshot import SNAPSHOT_CONTRACT_VERSION  # noqa: E402


def _write(payload, codebase_path, source_nodes=None, updated_nodes=None):
    ti = {"codebase_path": str(codebase_path)}
    if source_nodes is not None:
        ti["l1_features"] = [{"feature_id": "feat-x", "source_nodes": source_nodes}]
    if updated_nodes is not None:
        ti["updated_features"] = [{"feature_id": "feat-y", "source_nodes": updated_nodes}]
    return run_hook(C3, {"tool_input": ti})


def test_c2_6_no_checklist_denies(tmp_path):
    rc, err = run_hook(C3, {"tool_input": {"codebase_path": str(tmp_path)}})
    assert rc == 2
    assert "edge_residue" in err


def test_c5_6_deny_points_to_single_authority(tmp_path):
    """C5-6：deny 指回單一權威（MCP-actionable system_status）＋仍含 edge_residue teach。"""
    rc, err = run_hook(C3, {"tool_input": {"codebase_path": str(tmp_path)}})
    assert rc == 2
    assert "system_status" in err  # MCP-actionable 指回單一權威
    assert "edge_residue" in err   # actionable teach 保留


def test_c2_7_stamped_and_covered_allows(tmp_path):
    # producer↔reader honesty: build the checklist via the real stamp_stage.
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["a", "b"],
                contract_version=SNAPSHOT_CONTRACT_VERSION)
    rc, _ = _write({}, tmp_path, source_nodes=["a"])
    assert rc == 0


def test_c2_8_uncovered_node_denies(tmp_path):
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["a"],
                contract_version=SNAPSHOT_CONTRACT_VERSION)
    rc, err = _write({}, tmp_path, source_nodes=["a", "zzz"])
    assert rc == 2
    assert "coverage" in err or "涵蓋" in err


def test_c2_9_stale_contract_version_denies(tmp_path):
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["a"], contract_version="0")
    rc, _ = _write({}, tmp_path, source_nodes=["a"])
    assert rc == 2


def test_c2_10_updated_features_covered(tmp_path):
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["a"],
                contract_version=SNAPSHOT_CONTRACT_VERSION)
    rc, _ = _write({}, tmp_path, updated_nodes=["nope"])
    assert rc == 2


def test_c2_11_empty_source_nodes_allows(tmp_path):
    # checklist stamped (isolate existence) + no source_nodes (inherit-only) → allow.
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["a"],
                contract_version=SNAPSHOT_CONTRACT_VERSION)
    rc, _ = run_hook(C3, {"tool_input": {"codebase_path": str(tmp_path)}})
    assert rc == 0


def test_c2_12_corrupt_checklist_denies(tmp_path):
    art = tmp_path / ".the-door"
    art.mkdir()
    (art / "checklist.json").write_text("{not json", encoding="utf-8")
    rc, _ = run_hook(C3, {"tool_input": {"codebase_path": str(tmp_path)}})
    assert rc == 2


def test_c2_13_failopen_non_json_and_no_path(tmp_path):
    rc, _ = run_hook(C3, raw="not json at all")
    assert rc == 0
    rc, _ = run_hook(C3, {"tool_input": {}})
    assert rc == 0


# ── C2 drift-pin: hook literals match the_door constants ──────────────

def _c3_source() -> str:
    return (HOOKS_DIR / C3).read_text(encoding="utf-8")


def test_c2_14_hook_contract_version_pins_constant():
    src = _c3_source()
    assert f'"{SNAPSHOT_CONTRACT_VERSION}"' in src
    # the hook's hardcoded current version must equal the authoritative constant
    import the_door.core.checklist as ck  # noqa: F401 (ensure importable)
    assert SNAPSHOT_CONTRACT_VERSION == "1"


def test_c2_15_hook_field_names_pin_checklist_module():
    import the_door.core.checklist as ck
    src = _c3_source()
    for const in (ck.CHECKLIST_FILENAME, ck.FIELD_STAGES, ck.STAGE_EDGE_RESIDUE,
                  ck.FIELD_COVERED_NODES, ck.FIELD_CONTRACT_VERSION):
        assert const in src, f"hook missing checklist field literal {const!r}"
    # negative control: a field that does not exist must NOT be found (pin is real)
    assert "__nonexistent_field__" not in src


# ── 水平推廣: gate snapshot_patch (same c3 hook, source_nodes_by_feature) ──


def _patch(codebase_path, by_feature=None, metadata=None, with_tool_name=True):
    ti = {"codebase_path": str(codebase_path)}
    if by_feature is not None:
        ti["source_nodes_by_feature"] = by_feature
    if metadata is not None:
        ti["feature_metadata_by_feature"] = metadata
    event = {"tool_input": ti}
    if with_tool_name:
        event["tool_name"] = "mcp__the-door__snapshot_patch"
    return run_hook(C3, event)


def test_h1_patch_no_checklist_denies(tmp_path):
    rc, err = _patch(tmp_path, by_feature={"feat-x": ["a"]})
    assert rc == 2
    assert "edge_residue" in err


def test_h2_patch_stamped_and_covered_allows(tmp_path):
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["a", "b"],
                contract_version=SNAPSHOT_CONTRACT_VERSION)
    rc, _ = _patch(tmp_path, by_feature={"feat-x": ["a"]})
    assert rc == 0


def test_h3_patch_uncovered_denies_with_tool_label(tmp_path):
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["a"],
                contract_version=SNAPSHOT_CONTRACT_VERSION)
    rc, err = _patch(tmp_path, by_feature={"feat-x": ["a", "zzz"]})
    assert rc == 2
    assert "coverage" in err or "涵蓋" in err
    assert "snapshot_patch" in err  # coverage-deny 也用 tool-aware 標籤


def test_h4_patch_stale_contract_denies(tmp_path):
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["a"], contract_version="0")
    rc, _ = _patch(tmp_path, by_feature={"feat-x": ["a"]})
    assert rc == 2


def test_h5_patch_metadata_only_no_checklist_allows(tmp_path):
    # metadata-only (no source_nodes_by_feature) → not a node-write → not engaged → allow.
    rc, _ = _patch(tmp_path, metadata={"feat-x": {"trigger_description": "t"}})
    assert rc == 0


def test_h5b_patch_empty_by_feature_allows(tmp_path):
    rc, _ = _patch(tmp_path, by_feature={})
    assert rc == 0
    rc, _ = _patch(tmp_path, by_feature={"feat-x": []})
    assert rc == 0


def test_h5c_patch_metadata_only_without_tool_name_safe_degrades_to_deny(tmp_path):
    # No tool_name → cannot apply the snapshot_patch exemption → engage existence
    # (safe over-gate, never under-gate).
    rc, _ = _patch(tmp_path, metadata={"feat-x": {"trigger_description": "t"}},
                   with_tool_name=False)
    assert rc == 2


def test_h6_patch_deny_uses_tool_aware_label(tmp_path):
    rc, err = _patch(tmp_path, by_feature={"feat-x": ["a"]})
    assert rc == 2
    assert "snapshot_patch" in err


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


def test_h8_settings_registers_snapshot_patch_matcher():
    """水平推廣 H-8：snapshot_patch matcher 指向同一 c3 hook；snapshot_write 仍在。"""
    data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    pre = data["hooks"]["PreToolUse"]
    matchers = [h.get("matcher") for h in pre]
    assert "mcp__the-door__snapshot_patch" in matchers
    assert "mcp__the-door__snapshot_write" in matchers  # 不回歸
    # snapshot_patch matcher 的 command 指向 c3 hook
    patch_entry = next(h for h in pre if h.get("matcher") == "mcp__the-door__snapshot_patch")
    assert any(C3 in hk["command"] for hk in patch_entry.get("hooks", []))


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
