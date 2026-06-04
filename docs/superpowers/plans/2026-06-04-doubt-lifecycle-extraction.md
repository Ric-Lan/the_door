# DoubtLifecycle 抽出 + 轉換規範單一真相（Finding B-2，甲案）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 doubt 轉換政策（合法性＋每個轉換的效果）抽成純 `DoubtLifecycle`（零 I/O），使「四份重複」（`VALID_TRANSITIONS`表／5 動詞／MCP tool if-elif／CLI if-elif）收斂成單一宣告式真相；`DoubtStore` 退為機制（load/persist、落盤一次）；MCP tool 與 CLI 路由改讀同一來源。**公開行為、輸出、tool schema 逐字不變（甲案：零輸出改動）**。

**Architecture:** 新檔 `core/scope/doubt_lifecycle.py` 持純 `plan(...)→TransitionPlan` 與 `check_transition`；`DoubtStore` 加 `self._lifecycle`、統一內部套用點 `_apply_transition`、公開統一入口 `transition()`，5 動詞變薄殼、`check_timeouts` 改走 `_apply_transition`、刪舊 `_transition`、3 處 `TERMINAL_STATES` 引用改指 lifecycle、雙重落盤消除；MCP tool / CLI 移除 if-elif 路由改呼 `store.transition`，錯誤呈現逐字保留。

**Tech Stack:** Python 3.12、pytest、click.testing.CliRunner、`asyncio.run`（tool 為 async）。無新依賴。

**設計依據（並讀）：** `docs/superpowers/specs/2026-06-04-doubt-lifecycle-extraction-design.md`（命題 §1、驗證事實 §2、理論剔除 §3、設計 §4、契約 §5、測試 §6、陷阱 §7）。

---

## 關鍵事實（執行前必讀）

- **測試 cwd**：所有 pytest/git 在**內層** `the_door/` 執行（`testpaths=["tests"]`）。Windows console cp950，跑測試前置 `PYTHONUTF8=1`。docs 在**外層** repo root 的 `docs/`（涉及 `docs/` 的 git 從 worktree 根目錄＝`git rev-parse --show-toplevel` 執行）。
- **⚠️ 順序鐵則**：**Task 1（characterization 測試）必須先寫、且在「未改動的程式碼」上全綠**，作為零回歸安全網（doubt 子系統今天零直接測試）。之後 Task 2/3 任何結構改動後，這批測試必須**仍全綠**＝行為保留的硬證據。Task 2（lifecycle/store）必須先於 Task 3（消費端路由），因 tool/CLI 改呼 `store.transition`，該方法在 Task 2 才存在。
- **⚠️ 護欄（零輸出改動）**：**不得**改 `mcp/tools/doubt_transition_tool.py` 的 `TOOL_SCHEMA`（4–33）、任何回傳 dict 欄位、CLI echo 文字、`schemas/doubt-record.schema.json`、模型欄位。錯誤訊息逐字保留（Task 3 對位）。不抽 interface/ABC、不建 engine、不套 GoF State。不碰 `list_doubts`/`get_summary`/`create_doubt`/序列化/`_persist`/schema-loader 的邏輯（僅 `TERMINAL_STATES` 引用改指 lifecycle）。
- **已驗證事實（spec §2 + 本 plan 審查，無須重驗）**：5 動詞只被 `doubt_transition_tool.py` ＋ `doubt_cmd.py` 呼叫（grep 確認，無其他消費者/測試）。`TERMINAL_STATES` 活碼引用三處：`doubt_store.py` 165/182/**197**（漏 197 會 AttributeError）。tool 必填訊息逐字：59/64/74/83/88/92。CLI `doubt_resolve` 舊 192/195 `except` 在該函式是死碼（else 先攔所有非法）。模型建構子：`StateTransition(from_state,to_state,timestamp,actor,reason)`、`Resolution(type,description,resolved_by,resolved_at)`、`DoubtTerminalError(doubt_id,from_state)`、`InvalidTransitionError(from_state,to_state)`、`DoubtNotFoundError(doubt_id)`（皆由真實碼 serialize/raise 點佐證）。`doubt_type` enum：`out_of_scope`/`in_scope_incomplete`/`anomaly`/`low_confidence`。`scope-config.json` 在 `project_root/.the-door/scope-config.json`（`discovery_timeout_days`/`investigation_timeout_days`，預設 3/7）。

---

## File Structure

| 檔案 | 職責 | 本計畫動作 |
|---|---|---|
| `tests/unit/core/scope/test_doubt_store_characterization.py` | 釘 store 轉換/timeout 現況 | 新建（Task 1） |
| `tests/unit/mcp/test_doubt_transition_tool.py` | 釘 MCP tool 路由/錯誤現況 | 新建（Task 1） |
| `tests/unit/cli/test_doubt_cmd.py` | 釘 CLI 命令現況 | 新建（Task 1） |
| `tests/unit/core/scope/__init__.py` | 套件標記 | 新建（Task 1） |
| `core/scope/doubt_lifecycle.py` | 轉換政策唯一真相（純、零 I/O） | 新建（Task 2） |
| `core/scope/doubt_store.py` | doubt CRUD/持久化/機制 | 委派 lifecycle、統一套用、薄殼動詞、消雙重落盤、刪 `_transition`、改 3 引用（Task 2） |
| `tests/unit/core/scope/test_doubt_lifecycle.py` | lifecycle 純單元 | 新建（Task 2） |
| `mcp/tools/doubt_transition_tool.py` | doubt_transition MCP | `execute` 路由收斂為 `store.transition`（Task 3） |
| `cli/doubt_cmd.py` | doubt CLI 命令群 | `doubt_resolve` 路由收斂 + 例外映射（Task 3） |
| spec 檔 | 設計 | 標已實作（Task 4） |

---

## Task 1: Characterization 測試（先釘現況，未改碼即全綠）

**Files:**
- Create: `the_door/tests/unit/core/scope/__init__.py`（空檔）
- Create: `the_door/tests/unit/core/scope/test_doubt_store_characterization.py`
- Create: `the_door/tests/unit/mcp/test_doubt_transition_tool.py`
- Create: `the_door/tests/unit/cli/test_doubt_cmd.py`

- [ ] **Step 1: 建空 `__init__.py`**

建立 `the_door/tests/unit/core/scope/__init__.py`（空內容）。

- [ ] **Step 2: 寫 store characterization（完整內容）**

建立 `the_door/tests/unit/core/scope/test_doubt_store_characterization.py`：

```python
"""Characterization tests: pin DoubtStore transition + timeout behaviour BEFORE
the DoubtLifecycle extraction. These must stay green across the refactor."""
from __future__ import annotations

import json

import pytest

from the_door.core.scope.doubt_store import DoubtStore
from the_door.models import DoubtTerminalError, InvalidTransitionError


def _store(tmp_path) -> DoubtStore:
    return DoubtStore(tmp_path)


def _new(store, *, source_node="feat-x", doubt_type="anomaly", created_by="tester"):
    return store.create_doubt(source_node=source_node, doubt_type=doubt_type, created_by=created_by)


def test_create_starts_discovered(tmp_path):
    d = _new(_store(tmp_path))
    assert d.current_state == "discovered"
    assert d.resolution is None
    assert d.assigned_to is None


def test_assign_sets_investigating_and_assignee(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    out = store.assign(d.doubt_id, "alice", actor="bob")
    assert out.current_state == "investigating"
    assert out.assigned_to == "alice"
    reloaded = store.get_doubt(d.doubt_id)
    assert reloaded.current_state == "investigating"
    assert reloaded.assigned_to == "alice"
    assert reloaded.state_history[-1].from_state == "discovered"
    assert reloaded.state_history[-1].to_state == "investigating"
    assert reloaded.state_history[-1].actor == "bob"


def test_explain_from_investigating_sets_resolution(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    store.assign(d.doubt_id, "alice", actor="alice")
    out = store.explain(d.doubt_id, "false positive", resolved_by="alice")
    assert out.current_state == "explained"
    assert out.resolution.type == "explained"
    assert out.resolution.description == "false positive"
    assert out.resolution.resolved_by == "alice"
    assert store.get_doubt(d.doubt_id).resolution.type == "explained"


def test_fix_from_investigating_sets_resolution(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    store.assign(d.doubt_id, "alice", actor="alice")
    out = store.fix(d.doubt_id, "patched", resolved_by="alice")
    assert out.current_state == "fixed"
    assert out.resolution.type == "fixed"
    assert out.resolution.description == "patched"


def test_escalate_records_reason_no_resolution(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    out = store.escalate(d.doubt_id, "needs manager", actor="alice")
    assert out.current_state == "escalated"
    assert out.resolution is None
    assert out.state_history[-1].reason == "needs manager"


def test_resolve_escalation_sets_resolution(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    store.escalate(d.doubt_id, "r", actor="alice")
    out = store.resolve_escalation(d.doubt_id, "accepted_risk", "tolerated", resolved_by="mgr")
    assert out.current_state == "accepted_risk"
    assert out.resolution.type == "accepted_risk"
    assert out.resolution.description == "tolerated"
    assert out.resolution.resolved_by == "mgr"


def test_explain_from_escalated_equals_investigating_resolution(tmp_path):
    """§2.2: explained via escalated produces the same Resolution shape."""
    store = _store(tmp_path)
    d = _new(store)
    store.escalate(d.doubt_id, "r", actor="a")
    out = store.resolve_escalation(d.doubt_id, "explained", "fp", resolved_by="mgr")
    assert out.current_state == "explained"
    assert out.resolution.type == "explained"
    assert out.resolution.description == "fp"


def test_illegal_transition_raises(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    # discovered -> explained is illegal (valid: investigating/escalated)
    with pytest.raises(InvalidTransitionError):
        store.explain(d.doubt_id, "x", resolved_by="a")


def test_terminal_state_raises(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    store.assign(d.doubt_id, "a", actor="a")
    store.explain(d.doubt_id, "x", resolved_by="a")  # now terminal
    with pytest.raises(DoubtTerminalError):
        store.fix(d.doubt_id, "y", resolved_by="a")


def _write_timeout_config(tmp_path, discovery, investigation):
    cfg = tmp_path / ".the-door" / "scope-config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps(
        {"discovery_timeout_days": discovery, "investigation_timeout_days": investigation}
    ), encoding="utf-8")


def test_check_timeouts_escalates_discovered_when_due(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    _write_timeout_config(tmp_path, 0, 7)  # discovery timeout 0 days -> always due
    out = store.check_timeouts(store.get_doubt(d.doubt_id))
    assert out is not None
    assert out.current_state == "escalated"
    assert out.state_history[-1].actor == "system_timeout"


def test_check_timeouts_escalates_investigating_when_due(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    store.assign(d.doubt_id, "a", actor="a")
    _write_timeout_config(tmp_path, 3, 0)  # investigation timeout 0 -> always due
    out = store.check_timeouts(store.get_doubt(d.doubt_id))
    assert out is not None
    assert out.current_state == "escalated"


def test_check_timeouts_none_when_not_due(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    _write_timeout_config(tmp_path, 999, 999)
    assert store.check_timeouts(store.get_doubt(d.doubt_id)) is None


def test_check_timeouts_none_when_terminal(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    store.assign(d.doubt_id, "a", actor="a")
    store.explain(d.doubt_id, "x", resolved_by="a")
    assert store.check_timeouts(store.get_doubt(d.doubt_id)) is None


def test_has_active_doubt_and_summary(tmp_path):
    store = _store(tmp_path)
    d = _new(store)
    assert store.has_active_doubt("feat-x", "anomaly") is True
    store.assign(d.doubt_id, "a", actor="a")
    store.explain(d.doubt_id, "x", resolved_by="a")  # terminal
    assert store.has_active_doubt("feat-x", "anomaly") is False
    summary = store.get_summary()
    assert summary.by_state.get("explained") == 1
    assert summary.total_active == 0
```

- [ ] **Step 3: 寫 MCP tool characterization（完整內容）**

建立 `the_door/tests/unit/mcp/test_doubt_transition_tool.py`：

```python
"""Characterization tests: pin doubt_transition MCP tool routing + error
messages BEFORE the refactor. Success paths are verified by reloading the doubt
via DoubtStore (avoids coupling to the response envelope shape)."""
from __future__ import annotations

import asyncio

from the_door.core.scope.doubt_store import DoubtStore
from the_door.mcp.tools.doubt_transition_tool import execute


def _run(args):
    return asyncio.run(execute(args))


def _new(tmp_path):
    store = DoubtStore(tmp_path)
    d = store.create_doubt(source_node="feat-x", doubt_type="anomaly", created_by="t")
    return store, d


def _args(tmp_path, doubt_id, target, **kw):
    base = {"doubt_id": doubt_id, "target_state": target, "actor": "agent",
            "codebase_path": str(tmp_path)}
    base.update(kw)
    return base


def test_assign_path(tmp_path):
    store, d = _new(tmp_path)
    _run(_args(tmp_path, d.doubt_id, "investigating", assignee="alice"))
    r = store.get_doubt(d.doubt_id)
    assert r.current_state == "investigating"
    assert r.assigned_to == "alice"


def test_explained_from_investigating(tmp_path):
    store, d = _new(tmp_path)
    store.assign(d.doubt_id, "a", actor="a")
    _run(_args(tmp_path, d.doubt_id, "explained", reason="fp"))
    r = store.get_doubt(d.doubt_id)
    assert r.current_state == "explained"
    assert r.resolution.type == "explained"
    assert r.resolution.description == "fp"


def test_explained_from_escalated_branch(tmp_path):
    store, d = _new(tmp_path)
    store.escalate(d.doubt_id, "r", actor="a")
    _run(_args(tmp_path, d.doubt_id, "explained", reason="fp"))
    r = store.get_doubt(d.doubt_id)
    assert r.current_state == "explained"
    assert r.resolution.type == "explained"


def test_fixed_from_escalated_branch(tmp_path):
    store, d = _new(tmp_path)
    store.escalate(d.doubt_id, "r", actor="a")
    _run(_args(tmp_path, d.doubt_id, "fixed", reason="done"))
    assert store.get_doubt(d.doubt_id).current_state == "fixed"


def test_escalated_path(tmp_path):
    store, d = _new(tmp_path)
    _run(_args(tmp_path, d.doubt_id, "escalated", reason="up"))
    assert store.get_doubt(d.doubt_id).current_state == "escalated"


def test_accepted_risk_path(tmp_path):
    store, d = _new(tmp_path)
    store.escalate(d.doubt_id, "r", actor="a")
    _run(_args(tmp_path, d.doubt_id, "accepted_risk", reason="tolerate"))
    r = store.get_doubt(d.doubt_id)
    assert r.current_state == "accepted_risk"
    assert r.resolution.type == "accepted_risk"


def test_missing_assignee_error(tmp_path):
    store, d = _new(tmp_path)
    out = _run(_args(tmp_path, d.doubt_id, "investigating"))
    assert out == {"error": True, "message": "assignee is required for investigating transition"}


def test_missing_reason_error(tmp_path):
    store, d = _new(tmp_path)
    store.assign(d.doubt_id, "a", actor="a")
    out = _run(_args(tmp_path, d.doubt_id, "explained"))
    assert out == {"error": True, "message": "reason is required for explained transition"}


def test_unknown_target_state_error(tmp_path):
    store, d = _new(tmp_path)
    out = _run(_args(tmp_path, d.doubt_id, "bogus"))
    assert out == {"error": True, "message": "Unknown target_state: bogus"}


def test_invalid_transition_error_message(tmp_path):
    store, d = _new(tmp_path)
    # discovered -> explained is illegal; tool returns str(InvalidTransitionError)
    out = _run(_args(tmp_path, d.doubt_id, "explained", reason="x"))
    assert out["error"] is True
    assert "explained" in out["message"]
```

- [ ] **Step 4: 寫 CLI characterization（完整內容）**

建立 `the_door/tests/unit/cli/test_doubt_cmd.py`：

```python
"""Characterization tests: pin doubt CLI command behaviour BEFORE the refactor."""
from __future__ import annotations

from click.testing import CliRunner

from the_door.cli.doubt_cmd import doubt_group
from the_door.core.scope.doubt_store import DoubtStore


def _new(tmp_path):
    store = DoubtStore(tmp_path)
    d = store.create_doubt(source_node="feat-x", doubt_type="anomaly", created_by="t")
    return store, d


def _invoke(tmp_path, *cli_args):
    return CliRunner().invoke(doubt_group, [*cli_args, "--codebase-path", str(tmp_path)])


def test_assign(tmp_path):
    store, d = _new(tmp_path)
    res = _invoke(tmp_path, "assign", d.doubt_id, "alice")
    assert res.exit_code == 0
    assert "assigned to alice" in res.output
    assert store.get_doubt(d.doubt_id).current_state == "investigating"


def test_escalate(tmp_path):
    store, d = _new(tmp_path)
    res = _invoke(tmp_path, "escalate", d.doubt_id, "--reason", "up")
    assert res.exit_code == 0
    assert "escalated" in res.output
    assert store.get_doubt(d.doubt_id).current_state == "escalated"


def test_resolve_explained_from_investigating(tmp_path):
    store, d = _new(tmp_path)
    store.assign(d.doubt_id, "a", actor="a")
    res = _invoke(tmp_path, "resolve", d.doubt_id, "--as", "explained", "--reason", "fp")
    assert res.exit_code == 0
    assert "resolved as explained" in res.output
    assert store.get_doubt(d.doubt_id).current_state == "explained"


def test_resolve_accepted_risk_from_escalated(tmp_path):
    store, d = _new(tmp_path)
    store.escalate(d.doubt_id, "r", actor="a")
    res = _invoke(tmp_path, "resolve", d.doubt_id, "--as", "accepted_risk", "--reason", "tol")
    assert res.exit_code == 0
    assert "resolved as accepted_risk" in res.output


def test_resolve_illegal_combo_prints_custom_message(tmp_path):
    """investigating + accepted_risk is illegal -> custom else message, exit 1."""
    store, d = _new(tmp_path)
    store.assign(d.doubt_id, "a", actor="a")
    res = _invoke(tmp_path, "resolve", d.doubt_id, "--as", "accepted_risk", "--reason", "x")
    assert res.exit_code == 1
    assert "Cannot resolve as 'accepted_risk' from state 'investigating'" in res.output


def test_resolve_from_terminal_prints_custom_message(tmp_path):
    """terminal doubt -> custom else message, exit 1 (not 'Error: {e}')."""
    store, d = _new(tmp_path)
    store.assign(d.doubt_id, "a", actor="a")
    store.explain(d.doubt_id, "x", resolved_by="a")  # terminal
    res = _invoke(tmp_path, "resolve", d.doubt_id, "--as", "fixed", "--reason", "x")
    assert res.exit_code == 1
    assert "Cannot resolve as 'fixed' from state 'explained'" in res.output
```

- [ ] **Step 5: 跑 characterization，確認全綠（在未改動的程式碼上）**

Run（cwd = `the_door/`）：
```
PYTHONUTF8=1 python -m pytest tests/unit/core/scope/test_doubt_store_characterization.py tests/unit/mcp/test_doubt_transition_tool.py tests/unit/cli/test_doubt_cmd.py -q
```
Expected: **全 PASS**（這是安全網基準；此刻程式未改）。**若任何紅**：停下回報——表示對現況理解有誤，先修測試對齊現況，不可在此改產品碼。

- [ ] **Step 6: 跑全套件 + 記基準 SHA，然後 Commit**

```
PYTHONUTF8=1 python -m pytest -q
```
Expected: 全 PASS（基準＝當下 main + 本批新測試）。
記「動工前」HEAD 供 Task 4 改動面驗收：
```
git rev-parse HEAD
```
記為 `BASELINE_SHA`。然後（worktree 根目錄）：
```
git add the_door/tests/unit/core/scope/__init__.py the_door/tests/unit/core/scope/test_doubt_store_characterization.py the_door/tests/unit/mcp/test_doubt_transition_tool.py the_door/tests/unit/cli/test_doubt_cmd.py
git commit -m "test(doubt): characterization tests pinning transition + timeout behaviour

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: 抽 `DoubtLifecycle` + store 委派 + 消雙重落盤

**Files:**
- Create: `the_door/src/the_door/core/scope/doubt_lifecycle.py`
- Create: `the_door/tests/unit/core/scope/test_doubt_lifecycle.py`
- Modify: `the_door/src/the_door/core/scope/doubt_store.py`

- [ ] **Step 1: 寫 lifecycle 純單元測試（失敗）**

建立 `the_door/tests/unit/core/scope/test_doubt_lifecycle.py`：

```python
"""Unit tests for DoubtLifecycle — pure transition policy, no I/O."""
from __future__ import annotations

import pytest

from the_door.core.scope.doubt_lifecycle import DoubtLifecycle, TransitionPlan
from the_door.models import DoubtTerminalError, InvalidTransitionError


def test_check_transition_legal_pairs_pass():
    lc = DoubtLifecycle()
    for frm, tos in lc.VALID_TRANSITIONS.items():
        for to in tos:
            lc.check_transition(frm, to, "id")  # must not raise


def test_check_transition_terminal_raises():
    lc = DoubtLifecycle()
    with pytest.raises(DoubtTerminalError):
        lc.check_transition("explained", "fixed", "id")


def test_check_transition_illegal_raises():
    lc = DoubtLifecycle()
    with pytest.raises(InvalidTransitionError):
        lc.check_transition("discovered", "explained", "id")


def test_plan_investigating_sets_assignee():
    lc = DoubtLifecycle()
    p = lc.plan(doubt_id="id", from_state="discovered", to_state="investigating",
                actor="bob", assignee="alice")
    assert isinstance(p, TransitionPlan)
    assert p.set_assigned_to is True
    assert p.assigned_to == "alice"
    assert p.resolution is None
    assert p.transition.to_state == "investigating"
    assert p.transition.actor == "bob"


def test_plan_escalated_records_reason_no_resolution():
    lc = DoubtLifecycle()
    p = lc.plan(doubt_id="id", from_state="discovered", to_state="escalated",
                actor="a", reason="up")
    assert p.resolution is None
    assert p.set_assigned_to is False
    assert p.transition.reason == "up"


def test_plan_resolving_states_build_resolution():
    lc = DoubtLifecycle()
    for to in ("explained", "fixed", "accepted_risk"):
        frm = "investigating" if to in ("explained", "fixed") else "escalated"
        p = lc.plan(doubt_id="id", from_state=frm, to_state=to,
                    actor="mgr", description="d")
        assert p.resolution is not None
        assert p.resolution.type == to
        assert p.resolution.description == "d"
        assert p.resolution.resolved_by == "mgr"
        assert p.set_assigned_to is False


def test_plan_explained_same_resolution_via_two_paths():
    """§2.2 equivalence: type/description/resolved_by identical regardless of from_state."""
    lc = DoubtLifecycle()
    a = lc.plan(doubt_id="id", from_state="investigating", to_state="explained",
                actor="m", description="fp")
    b = lc.plan(doubt_id="id", from_state="escalated", to_state="explained",
                actor="m", description="fp")
    assert (a.resolution.type, a.resolution.description, a.resolution.resolved_by) == \
           (b.resolution.type, b.resolution.description, b.resolution.resolved_by)


def test_plan_illegal_raises_before_building():
    lc = DoubtLifecycle()
    with pytest.raises(InvalidTransitionError):
        lc.plan(doubt_id="id", from_state="discovered", to_state="explained",
                actor="a", description="x")
```

- [ ] **Step 2: 跑測試確認失敗**

Run：
```
PYTHONUTF8=1 python -m pytest tests/unit/core/scope/test_doubt_lifecycle.py -q
```
Expected: **ImportError**（`cannot import name 'DoubtLifecycle'`）。

- [ ] **Step 3: 建立 `doubt_lifecycle.py`（完整內容）**

建立 `the_door/src/the_door/core/scope/doubt_lifecycle.py`：

```python
"""The law of how a doubt moves: legal transitions + what each transition produces.

Pure: no file I/O, no persistence. The store loads/saves DoubtRecords and applies
the plan this class returns. Single home of doubt transition policy (Mealy: the
effect is keyed on the *target state* and carries transition inputs).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from the_door.models import (
    DoubtTerminalError,
    InvalidTransitionError,
    Resolution,
    StateTransition,
)


@dataclass(frozen=True)
class TransitionPlan:
    """What a single legal transition mutates. Pure value, applied by the store."""
    transition: StateTransition
    resolution: Resolution | None
    assigned_to: str | None
    set_assigned_to: bool


class DoubtLifecycle:
    """Maps (from_state, target_state, inputs) -> a TransitionPlan, or raises."""

    VALID_TRANSITIONS: dict[str, set[str]] = {
        "discovered": {"investigating", "escalated"},
        "investigating": {"explained", "fixed", "escalated"},
        "escalated": {"explained", "fixed", "accepted_risk"},
        "explained": set(),
        "fixed": set(),
        "accepted_risk": set(),
    }
    TERMINAL_STATES: set[str] = {"explained", "fixed", "accepted_risk"}
    _RESOLVING_STATES: set[str] = {"explained", "fixed", "accepted_risk"}

    def is_terminal(self, state: str) -> bool:
        return state in self.TERMINAL_STATES

    def check_transition(self, from_state: str, to_state: str, doubt_id: str) -> None:
        """Legality only. Raises DoubtTerminalError / InvalidTransitionError."""
        if from_state in self.TERMINAL_STATES:
            raise DoubtTerminalError(doubt_id, from_state)
        if to_state not in self.VALID_TRANSITIONS.get(from_state, set()):
            raise InvalidTransitionError(from_state, to_state)

    def plan(
        self,
        *,
        doubt_id: str,
        from_state: str,
        to_state: str,
        actor: str,
        reason: str | None = None,
        assignee: str | None = None,
        description: str | None = None,
    ) -> TransitionPlan:
        """Validate legality and build the effect for *to_state* (Mealy: by target).

        Effect by target (behaviour-preserving, see spec §2.2):
          - investigating          -> set assigned_to=assignee
          - escalated               -> record reason only (no resolution)
          - explained/fixed/accepted_risk -> Resolution(type=to_state, description)
        Inputs are assumed present (callers keep their own required-input guards).
        """
        self.check_transition(from_state, to_state, doubt_id)
        now = datetime.now(timezone.utc).isoformat()
        transition = StateTransition(
            from_state=from_state, to_state=to_state,
            timestamp=now, actor=actor, reason=reason,
        )
        resolution = None
        assigned_to = None
        set_assigned = False
        if to_state == "investigating":
            assigned_to = assignee
            set_assigned = True
        elif to_state in self._RESOLVING_STATES:
            resolution = Resolution(
                type=to_state, description=description or "",
                resolved_by=actor, resolved_at=now,
            )
        return TransitionPlan(transition, resolution, assigned_to, set_assigned)
```

- [ ] **Step 4: rewire `doubt_store.py`**

4a. 頂部 import 區（現有 `from the_door.models import (...)` 之後）新增：
```python
from the_door.core.scope.doubt_lifecycle import DoubtLifecycle
```

4b. **刪除** class 內 `VALID_TRANSITIONS`（61–69）與 `TERMINAL_STATES`（71）兩個類屬性。

4c. `__init__`（73–74）在 `self._doubts_dir = ...` 之後新增：
```python
        self._lifecycle = DoubtLifecycle()
```

4d. 把 `TERMINAL_STATES` 的**三處**活碼引用改指 lifecycle（grep 驗證：165/182/197）：
- `list_doubts`（165）：`d.current_state not in self.TERMINAL_STATES` → `d.current_state not in self._lifecycle.TERMINAL_STATES`
- `get_summary`（182）：`if d.current_state not in self.TERMINAL_STATES:` → `if d.current_state not in self._lifecycle.TERMINAL_STATES:`
- `has_active_doubt`（197）：`and d.current_state not in self.TERMINAL_STATES` → `and d.current_state not in self._lifecycle.TERMINAL_STATES`

4e. **新增**統一內部套用點與公開入口（建議放在 `_transition` 原位置區、private 區之前；`transition` 為 public、`_apply_transition` 為 private）：
```python
    def transition(self, doubt_id, target_state, *, actor,
                   reason=None, assignee=None, description=None):
        """Single public entry: load, plan & apply any transition by target state."""
        doubt = self.get_doubt(doubt_id)
        return self._apply_transition(doubt, target_state, actor,
                                      reason=reason, assignee=assignee,
                                      description=description)

    def _apply_transition(self, doubt, to_state, actor, *, reason=None,
                          assignee=None, description=None):
        plan = self._lifecycle.plan(
            doubt_id=doubt.doubt_id, from_state=doubt.current_state,
            to_state=to_state, actor=actor, reason=reason,
            assignee=assignee, description=description,
        )
        doubt.current_state = to_state
        doubt.updated_at = plan.transition.timestamp
        doubt.state_history.append(plan.transition)
        if plan.resolution is not None:
            doubt.resolution = plan.resolution
        if plan.set_assigned_to:
            doubt.assigned_to = plan.assigned_to
        self._persist(doubt)
        return doubt
```

4f. 把 5 個動詞**整段 body 改為薄殼**（簽名不變）：
```python
    def assign(self, doubt_id, assignee, actor):
        """discovered -> investigating: 指派調查者。"""
        return self.transition(doubt_id, "investigating", actor=actor, assignee=assignee)

    def explain(self, doubt_id, description, resolved_by):
        """investigating -> explained: 確認為誤報。"""
        return self.transition(doubt_id, "explained", actor=resolved_by, description=description)

    def fix(self, doubt_id, description, resolved_by):
        """investigating -> fixed: 問題已修正。"""
        return self.transition(doubt_id, "fixed", actor=resolved_by, description=description)

    def escalate(self, doubt_id, reason, actor):
        """discovered/investigating -> escalated: 升級至管理層。"""
        return self.transition(doubt_id, "escalated", actor=actor, reason=reason)

    def resolve_escalation(self, doubt_id, resolution_type, description, resolved_by):
        """escalated -> explained/fixed/accepted_risk: 管理層決策。"""
        return self.transition(doubt_id, resolution_type, actor=resolved_by, description=description)
```

4g. `check_timeouts` 內兩處 `self._transition(doubt, "escalated", "system_timeout", reason=...)`（原 315/334）改為：
```python
                return self._apply_transition(
                    doubt, "escalated", "system_timeout", reason=...,
                )
```
（`reason=` 文字維持原樣：discovered 路徑用 `f"Auto-escalated: no investigator assigned within {discovery_timeout_days} days"`；investigating 路徑用 `f"Auto-escalated: no progress in {investigation_timeout_days} days"`。）

4h. **刪除**舊 `_transition` 方法（原 377–423）。確認 grep `_transition` 在 `doubt_store.py` 內**零殘留**（5 動詞與 check_timeouts 已改）。

- [ ] **Step 5: 跑 lifecycle 測試 + characterization（全綠）**

Run：
```
PYTHONUTF8=1 python -m pytest tests/unit/core/scope/ tests/unit/mcp/test_doubt_transition_tool.py tests/unit/cli/test_doubt_cmd.py -q
```
Expected: **全 PASS**（lifecycle 8 測 + Task 1 characterization 仍全綠＝行為保留）。

- [ ] **Step 6: 跑全套件，確認零回歸**

```
PYTHONUTF8=1 python -m pytest -q
```
Expected: 全 PASS。**若紅**：停下回報 BLOCKED，附失敗測試；不得為過關改 lifecycle 行為或加回雙重落盤。

- [ ] **Step 7: Commit**

```
git add the_door/src/the_door/core/scope/doubt_lifecycle.py the_door/src/the_door/core/scope/doubt_store.py the_door/tests/unit/core/scope/test_doubt_lifecycle.py
git commit -m "refactor(doubt): extract pure DoubtLifecycle, single-persist, verbs as thin shims

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: 消費端路由收斂（tool + CLI 共讀 `store.transition`）

**Files:**
- Modify: `the_door/src/the_door/mcp/tools/doubt_transition_tool.py`
- Modify: `the_door/src/the_door/cli/doubt_cmd.py`

- [ ] **Step 1: 收斂 `doubt_transition_tool.py` `execute`（56–92）**

把 `try:` 內整段 if-elif（含 escalated 分支）替換為：必填 guard（逐字保留）→ 單一 `store.transition`。`execute` 內既有的 `DoubtNotFoundError`/`DoubtTerminalError`/`InvalidTransitionError` import 與 `except` 區、結尾 `return wrap({...})` **不動**。把：
```python
    try:
        if target_state == "investigating":
            if not assignee:
                return {"error": True, "message": "assignee is required for investigating transition"}
            doubt = store.assign(doubt_id, assignee, actor)

        elif target_state == "explained":
            if not reason:
                return {"error": True, "message": "reason is required for explained transition"}
            current = store.get_doubt(doubt_id)
            if current.current_state == "escalated":
                doubt = store.resolve_escalation(doubt_id, "explained", reason, actor)
            else:
                doubt = store.explain(doubt_id, reason, actor)

        elif target_state == "fixed":
            if not reason:
                return {"error": True, "message": "reason is required for fixed transition"}
            current = store.get_doubt(doubt_id)
            if current.current_state == "escalated":
                doubt = store.resolve_escalation(doubt_id, "fixed", reason, actor)
            else:
                doubt = store.fix(doubt_id, reason, actor)

        elif target_state == "escalated":
            if not reason:
                return {"error": True, "message": "reason is required for escalated transition"}
            doubt = store.escalate(doubt_id, reason, actor)

        elif target_state == "accepted_risk":
            if not reason:
                return {"error": True, "message": "reason is required for accepted_risk transition"}
            doubt = store.resolve_escalation(doubt_id, "accepted_risk", reason, actor)

        else:
            return {"error": True, "message": f"Unknown target_state: {target_state}"}

    except DoubtNotFoundError:
```
替換為：
```python
    if target_state == "investigating" and not assignee:
        return {"error": True, "message": "assignee is required for investigating transition"}
    if target_state in ("explained", "fixed", "escalated", "accepted_risk") and not reason:
        return {"error": True, "message": f"reason is required for {target_state} transition"}
    if target_state not in ("investigating", "explained", "fixed", "escalated", "accepted_risk"):
        return {"error": True, "message": f"Unknown target_state: {target_state}"}

    try:
        doubt = store.transition(
            doubt_id, target_state, actor=actor,
            reason=reason, assignee=assignee, description=reason,
        )
    except DoubtNotFoundError:
```
（`description=reason` 對位：investigating 用 assignee／escalated 用 reason／3 resolving 用 description=reason → 與舊 `explain`/`fix`/`resolve_escalation` 傳 reason 當 description 一致，見 spec §4.3a。`current = store.get_doubt(...)` 的查詢隨 if-elif 一併移除。）

- [ ] **Step 2: 收斂 `doubt_cmd.py` `doubt_resolve`（174–197）**

把 `try:` 內的 state-based dispatch（if/elif/else）與其後 `except DoubtTerminalError`/`except InvalidTransitionError` 整段替換為：單一 `store.transition` ＋ 把兩種例外映射回**原客製句**。`doubt = store.get_doubt(resolved_id)`（168，供客製句的 `current_state`）**保留**。把：
```python
    try:
        # State-based dispatch
        if doubt.current_state == "investigating" and resolution_type == "explained":
            updated = store.explain(resolved_id, reason, resolved_by="cli_user")
        elif doubt.current_state == "investigating" and resolution_type == "fixed":
            updated = store.fix(resolved_id, reason, resolved_by="cli_user")
        elif doubt.current_state == "escalated":
            updated = store.resolve_escalation(resolved_id, resolution_type, reason, resolved_by="cli_user")
        else:
            click.echo(
                f"Error: Cannot resolve as '{resolution_type}' from state '{doubt.current_state}'. "
                f"Expected: investigating + explained/fixed, or escalated + any resolution type.",
                err=True,
            )
            sys.exit(1)

        click.echo(f"Doubt {updated.doubt_id[:8]} resolved as {resolution_type} (state: {updated.current_state})")
        from the_door.cli.post_run_hook import cli_post_run_hook
        cli_post_run_hook(codebase_path, json_mode_active=False)
    except DoubtTerminalError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except InvalidTransitionError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
```
替換為：
```python
    try:
        updated = store.transition(
            resolved_id, resolution_type, actor="cli_user", description=reason,
        )
        click.echo(f"Doubt {updated.doubt_id[:8]} resolved as {resolution_type} (state: {updated.current_state})")
        from the_door.cli.post_run_hook import cli_post_run_hook
        cli_post_run_hook(codebase_path, json_mode_active=False)
    except (DoubtTerminalError, InvalidTransitionError):
        click.echo(
            f"Error: Cannot resolve as '{resolution_type}' from state '{doubt.current_state}'. "
            f"Expected: investigating + explained/fixed, or escalated + any resolution type.",
            err=True,
        )
        sys.exit(1)
```
（`DoubtTerminalError`/`InvalidTransitionError` 已在該函式 157 import；`doubt_assign`/`doubt_escalate` 不動。）

- [ ] **Step 3: 跑 characterization（tool + CLI）+ 全套件**

Run：
```
PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_doubt_transition_tool.py tests/unit/cli/test_doubt_cmd.py tests/unit/core/scope/ -q
```
Expected: **全 PASS**（行為逐字保留的硬證據）。
再跑全套件：
```
PYTHONUTF8=1 python -m pytest -q
```
Expected: 全 PASS、零回歸。**若紅**：停下回報 BLOCKED；不得改 lifecycle 行為或動 tool schema/輸出。

- [ ] **Step 4: Commit**

```
git add the_door/src/the_door/mcp/tools/doubt_transition_tool.py the_door/src/the_door/cli/doubt_cmd.py
git commit -m "refactor(doubt): converge tool + CLI routing onto DoubtStore.transition

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: 收尾 — 覆蓋/改動面驗收 + 標 spec 已實作

**Files:**
- Modify: `docs/superpowers/specs/2026-06-04-doubt-lifecycle-extraction-design.md`

- [ ] **Step 1: 覆蓋驗收**

Run（cwd = `the_door/`）：
```
PYTHONUTF8=1 python -m pytest --cov=the_door.core.scope.doubt_lifecycle --cov-report=term-missing tests/unit/core/scope/ tests/
```
Expected: 全 PASS；`doubt_lifecycle.py` 由單元測涵蓋（合法性/效果 by target/序保留/失敗）。記下數字。

- [ ] **Step 2: 確認改動面**

Run（cwd = worktree root；`BASELINE_SHA` = Task 1 Step 6 記下的 SHA；若無記錄，此計畫為線性 4 commit、此刻 HEAD=Task 3 commit，則 `BASELINE_SHA` 即 `HEAD~3`）：
```
git diff --stat <BASELINE_SHA>..HEAD
```
Expected：僅 `core/scope/doubt_lifecycle.py`（新）、`core/scope/doubt_store.py`、`mcp/tools/doubt_transition_tool.py`、`cli/doubt_cmd.py`、`tests/unit/core/scope/__init__.py`（新）、`tests/unit/core/scope/test_doubt_lifecycle.py`（新）、`tests/unit/core/scope/test_doubt_store_characterization.py`（新）、`tests/unit/mcp/test_doubt_transition_tool.py`（新）、`tests/unit/cli/test_doubt_cmd.py`（新）。**不得有其他檔被改**（尤其：`doubt_transition_tool.py` 的 `TOOL_SCHEMA`、`schemas/doubt-record.schema.json`、模型、任何輸出格式皆未動）。若有他檔變更 → 回報。

- [ ] **Step 3: 標記 spec 已實作**

編輯 `docs/superpowers/specs/2026-06-04-doubt-lifecycle-extraction-design.md` 標頭，把：
```
> **日期**：2026-06-04　**狀態**：設計中、待審（spike 已對真實碼完成）
```
改為：
```
> **日期**：2026-06-04　**狀態**：已實作（plan: docs/superpowers/plans/2026-06-04-doubt-lifecycle-extraction.md）
```

- [ ] **Step 4: Commit**

`docs/` 在**外層** repo root。從 worktree 根目錄（`git rev-parse --show-toplevel` 輸出）執行：
```
git add docs/superpowers/specs/2026-06-04-doubt-lifecycle-extraction-design.md
git commit -m "docs: mark doubt lifecycle extraction implemented

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 5: 收尾回報**

回報：`DoubtLifecycle` 抽出為純 class（零 I/O、合法性＋效果 by target 單一真相）；`DoubtStore` 委派、統一 `transition`/`_apply_transition`、5 動詞薄殼、雙重落盤消除、舊 `_transition` 與類屬性已刪、3 處 `TERMINAL_STATES` 改指 lifecycle；MCP tool 與 CLI 路由收斂讀單一來源、escalated 分支消失；**tool schema/輸出/錯誤訊息逐字不變**；characterization 測（改前釘、改後綠）＋ lifecycle 單元測全綠；全套件零回歸；改動面僅 spec 列檔。等使用者決定 merge（本地 merge、不主動 push）。

---

## 設計註記（給審查者）

- **保留 5 動詞為薄殼、不移除**：它們具名自我說明（assign/explain/fix/...）、以 positional 參數強制必填輸入（比全選填的 `transition()` 更安全），且被 CLI/MCP 直接呼叫；移除＝API 破壞且無收益。新增 `transition()` 是純加法統一入口（供消費端去重）。
- **通用性**：`DoubtLifecycle` 為純領域邏輯，零廠商/語言/框架耦合；不碰分析層、不碰輸出契約（乙案＝全專案輸出 pass，見 memory `todo_output_direction_assessment`，本刀不做）。

---

## Self-Review（已執行）

- **Spec coverage**：§4.1 lifecycle→Task2 Step3；§4.2 store 委派/薄殼/單次落盤/刪 _transition/改 3 引用→Task2 Step4；§4.3a tool→Task3 Step1；§4.3b CLI 例外映射→Task3 Step2；§4.4 不改清單→Task4 Step2 驗收；§6.1 characterization→Task1；§6.2 lifecycle 單元→Task2 Step1。全覆蓋。
- **Placeholder scan**：無 TBD；所有 step 有完整碼/指令/預期輸出。`BASELINE_SHA` 記錄式（後備 `HEAD~3`）、docs commit「worktree 根目錄執行」——可機械解析。
- **順序鐵則**：Task1 characterization 先綠（安全網）→ Task2 lifecycle/store（`transition` 落地）→ Task3 消費端（依賴 `transition`）→ Task4 收尾。滿足 spec §7.1。
- **Type/簽名一致**：`DoubtLifecycle().plan(*, doubt_id, from_state, to_state, actor, reason, assignee, description)`、`check_transition(from_state, to_state, doubt_id)`、`store.transition(doubt_id, target_state, *, actor, reason, assignee, description)`、`_apply_transition(doubt, to_state, actor, *, reason, assignee, description)`、`TransitionPlan(transition, resolution, assigned_to, set_assigned_to)`——跨 task 與 spec §4 一致，模型建構子與真實碼一致。
- **零輸出改動驗收**：Task4 Step2 明列 tool schema/輸出/schema/模型不得變；characterization（Task1）改前改後皆綠＝行為逐字保留的機械證據。
