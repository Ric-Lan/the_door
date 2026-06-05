# S1 doubt through-line Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 doubt 線的 **LLM-facing 膜** retrofit 落地——三 enum（current_state/doubt_type/resolution.type）每值意義從行註解移進結構，emit 經 S0 `MembraneElement` 投影、input schema 補 enum、schema 半膜→全膜，全部由**單一膜詞彙來源**驅動。乙案首個整膜試點（S1），萃取 S2–S7 照抄的慣例。

**Architecture:** 純加法詞彙模組 `core/scope/doubt_membrane.py`（值→`SignalPosition` 工廠、文法從 `DoubtLifecycle` 導出、gloss 唯一手寫）＋ 兩 MCP 工具的 input enum / output 投影 ＋ schema per-value 補完。**LLM-facing only**：人類面 emit（serialize_doubt/CLI/viewer JS）、落盤 out。

**Tech Stack:** Python、S0 `core/membrane`（MembraneElement/SignalPosition/ReservedPassthrough/to_json）、JSON Schema Draft 2020-12（oneOf/const）、jsonschema、pytest。

**理論錨（spec `docs/superpowers/specs/2026-06-05-S1-doubt-throughline-spec.md`；種子檔 §8.10/§8.13）：**
- 膜不變量（§8.10）：意義靠結構位置 → 三 enum emit 帶 position。
- B 操作位置用內部單一來源 → current_state 文法從 `DoubtLifecycle` 導出（J4）。
- 單一來源（§8.16，零副本）：input schema 由 gloss builder **衍生**（無副本）；record schema 唯一副本經 parity test 守（J3）。
- per-value 切法：doubt 全閉集→全 Signal、reason/description→Reserved、零 Noise/Verdict（J5）。
- fact-finder：無裁決欄（S0 base 已保證）。

**Preconditions（執行前確認，非 task）：**
- 換 worktree 後先 `pip install -e ./the_door`（S0 已裝）。
- pytest cwd＝內層 `the_door/`；Windows cp950 前置 `PYTHONUTF8=1`。
- 基線＝S0 merged 後 1462 passed。本 plan：詞彙/schema 純加法；emit 形狀變更由 characterization 見證。

**已驗事實（寫 plan 前 spike，2026-06-05）：**
- 既有 `tests/unit/mcp/test_doubt_transition_tool.py` 刻意**不**斷言 wrap dict 形狀（success 走 store 重載、error 才斷言 dict）→ output 投影**不破壞既有斷言**。
- `target_state` 合法集＝`{investigating,explained,fixed,escalated,accepted_risk}`（`doubt_transition_tool.py:60` 守衛、`discovered` 非 target）。
- `doubt_store.py:39-48` 用 jsonschema 驗 doubt-record；實測 `oneOf/const` 與 `enum` 驗證等價。
- `:60` 內部守衛保留為深度防禦（input enum 是給 LLM 讀、非執行期強制）。

---

## File Structure

| 檔案 | 職責 | 動作 |
|---|---|---|
| `src/the_door/core/scope/doubt_membrane.py` | 膜詞彙單一來源（3 gloss dict＋3 signal/element 工廠＋free_text＋3 input schema builder） | Create ~95 行 |
| `tests/unit/core/scope/test_doubt_membrane.py` | 工廠 happy-path＋J4 導出連動 | Create |
| `tests/unit/mcp/test_doubt_tools_membrane.py` | 兩工具 output 投影 characterization（先釘 bare→後改 {value,position}）＋input enum 斷言＋J5 | Create |
| `src/the_door/mcp/tools/doubt_transition_tool.py` | input enum（target_state）＋output 投影 | Modify |
| `src/the_door/mcp/tools/doubt_list_tool.py` | input enum（state/type）×2＋output 投影 | Modify |
| `schemas/doubt-record.schema.json` | 三 enum → oneOf/const per-value 意義 | Modify |
| `tests/unit/core/scope/test_doubt_membrane_parity.py` | J3：record schema `oneOf const→desc` == gloss 逐字（唯一副本） | Create |

---

### Task 1: 膜詞彙單一來源 `doubt_membrane.py`（含 J4 導出連動）

**理論錨：** B 操作位置用內部單一來源（§8.10）；current_state 文法從 `DoubtLifecycle` 導出、不重寫死（J4）。**純加法、零既有碼改動。**

**Files:**
- Create: `src/the_door/core/scope/doubt_membrane.py`
- Test: `tests/unit/core/scope/test_doubt_membrane.py`

- [ ] **Step 1: Write the failing test**

建立 `tests/unit/core/scope/test_doubt_membrane.py`：

```python
"""S1 doubt 膜詞彙：工廠正確性 + J4 文法從 DoubtLifecycle 導出。"""
import pytest

from the_door.core.scope import doubt_membrane as dm
from the_door.core.scope.doubt_lifecycle import DoubtLifecycle


def test_current_state_signal_derives_grammar():
    """current_state→Signal；preconditions 反查、co_requires 由 _RESOLVING 導出。"""
    sp = dm.current_state_signal("explained")
    assert set(sp.contrasts) == set(DoubtLifecycle.VALID_TRANSITIONS.keys())
    assert set(sp.preconditions) == {"investigating", "escalated"}   # 哪些 from→explained
    assert sp.consequences == ("terminal",)                          # is_terminal
    assert sp.co_requires == ("reason",)                             # explained ∈ _RESOLVING
    assert "預期行為" in sp.gloss


def test_current_state_non_terminal_consequences_are_targets():
    """非終態的 consequences＝可達 targets（非 'terminal'）。"""
    sp = dm.current_state_signal("discovered")
    assert set(sp.consequences) == {"investigating", "escalated"}
    assert sp.co_requires == ()


def test_doubt_type_signal_minimal():
    sp = dm.doubt_type_signal("anomaly")
    assert set(sp.contrasts) == {"out_of_scope", "in_scope_incomplete", "anomaly", "low_confidence"}
    assert sp.preconditions == ()


def test_resolution_type_signal_contrasts_are_resolving_states():
    sp = dm.resolution_type_signal("fixed")
    assert set(sp.contrasts) == DoubtLifecycle._RESOLVING_STATES


def test_element_factories_project():
    assert dm.current_state_element("explained").to_json()["value"] == "explained"
    assert dm.free_text_element("任意說明").to_json() == {
        "value": "任意說明", "position": {"kind": "reserved"}
    }


def test_j4_grammar_follows_lifecycle(monkeypatch):
    """J4：擴 VALID_TRANSITIONS 加新狀態，contrasts 自動含之（證非寫死）。"""
    patched = dict(DoubtLifecycle.VALID_TRANSITIONS)
    patched["discovered"] = {"investigating", "escalated", "snoozed"}
    patched["snoozed"] = set()
    monkeypatch.setattr(dm._LC, "VALID_TRANSITIONS", patched)
    sp = dm.current_state_signal("discovered")
    assert "snoozed" in sp.contrasts          # 自動跟動、未改 doubt_membrane 碼


def test_input_schema_builders_derive_from_gloss():
    """零副本：input schema 的 enum＝gloss key 集、各 gloss ∈ description（衍生鎖）。"""
    ts = dm.target_state_schema()
    assert ts["enum"] == ["investigating", "explained", "fixed", "escalated", "accepted_risk"]
    assert dm._STATE_GLOSS["explained"] in ts["description"]
    assert dm.state_filter_schema()["enum"] == list(dm._STATE_GLOSS.keys())   # 6
    assert dm.type_filter_schema()["enum"] == list(dm._TYPE_GLOSS.keys())     # 4
    assert dm._TYPE_GLOSS["anomaly"] in dm.type_filter_schema()["description"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/scope/test_doubt_membrane.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'the_door.core.scope.doubt_membrane'`

- [ ] **Step 3: Write minimal implementation**

建立 `src/the_door/core/scope/doubt_membrane.py`＝**spec §3.1 的 exact code 全文**（3 gloss dict＋`current_state_signal`/`doubt_type_signal`/`resolution_type_signal`＋3 `*_element`＋`free_text_element`＋`_TARGET_STATES`/`_enum_schema`/`target_state_schema`/`state_filter_schema`/`type_filter_schema`）。

> 不在此重貼（避免雙源漂移）；spec §3.1 是唯一 code 來源。關鍵不變式：`current_state_signal` 的 preconditions/consequences/co_requires **從 `_LC.VALID_TRANSITIONS`/`is_terminal`/`_RESOLVING_STATES` 每次呼叫即時讀**（J4 連動）；`_enum_schema` 的 `enum`＝key list、`description`＝`lead＋"；".join(f"{k}={gloss[k]}")`（J3 衍生、零副本）。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/scope/test_doubt_membrane.py -q`
Expected: PASS（7 passed）

> 註：`test_j4` monkeypatch `dm._LC.VALID_TRANSITIONS`（instance 屬性覆寫）→ 函式每次讀 `_LC.VALID_TRANSITIONS` 故跟動。`_STATE_GLOSS["discovered"]` 既有、不需為新狀態加 gloss（測試對既有值取 signal）。

- [ ] **Step 5: Commit**

```bash
git add src/the_door/core/scope/doubt_membrane.py tests/unit/core/scope/test_doubt_membrane.py
git commit -m "feat(doubt-membrane): single vocabulary source, grammar derived from DoubtLifecycle (J4)

S1 第一塊：doubt 三 enum 值→SignalPosition 工廠；current_state 文法從
DoubtLifecycle 導出（非重寫死）；gloss 唯一手寫。慣例樣板供 S2-S7 照抄。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 兩工具 output characterization（先釘 bare 現狀）

**理論錨：** characterization 先行（§9.4）——動契約前釘現狀。**本 task 不改生產碼。**

**Files:**
- Test: `tests/unit/mcp/test_doubt_tools_membrane.py`（Create）

- [ ] **Step 1: Write characterization test pinning CURRENT bare shape**

建立 `tests/unit/mcp/test_doubt_tools_membrane.py`：

```python
"""S1 characterization + 膜投影：先釘兩工具 output bare 現狀（本 commit），
Task 4 投影後改為 {value, position}（見證契約變更）。"""
from __future__ import annotations

import asyncio

from the_door.core.scope.doubt_store import DoubtStore
from the_door.mcp.tools.doubt_transition_tool import execute as transition_exec
from the_door.mcp.tools.doubt_list_tool import execute as list_exec


def _seed_explained(tmp_path):
    store = DoubtStore(tmp_path)
    d = store.create_doubt(source_node="feat-x", doubt_type="anomaly", created_by="t")
    store.assign(d.doubt_id, "alice", actor="a")
    return store, d


def test_transition_output_current_state_is_bare(tmp_path):
    """CHARACTERIZATION（Task 2 現狀）：current_state 為 bare str。"""
    store, d = _seed_explained(tmp_path)
    out = asyncio.run(transition_exec({
        "doubt_id": d.doubt_id, "target_state": "explained", "actor": "a",
        "reason": "fp", "codebase_path": str(tmp_path),
    }))
    assert out["current_state"] == "explained"
    assert out["doubt_type"] == "anomaly"
    assert out["resolution"]["type"] == "explained"
```

- [ ] **Step 2: Run test to verify it PASSES (pins current behavior)**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_doubt_tools_membrane.py -q`
Expected: PASS（1 passed）——characterization 釘住現狀。

> 這是 characterization（非 red-green）：通過＝成功捕捉現狀。Task 4 投影後本斷言改為 `{value, position}` 形狀＝見證有意契約變更。

- [ ] **Step 3: Commit**

```bash
git add tests/unit/mcp/test_doubt_tools_membrane.py
git commit -m "test(doubt-tools): characterize bare output shape before membrane projection

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: input schema 寫嚴（B 側 CWA enum）

**理論錨：** B 側 CWA 寫嚴（§8.12 修正②）；input enum 給消費端 LLM 讀。

**Files:**
- Modify: `src/the_door/mcp/tools/doubt_transition_tool.py`（TOOL_SCHEMA.target_state）
- Modify: `src/the_door/mcp/tools/doubt_list_tool.py`（TOOL_SCHEMA.state / type）
- Test: `tests/unit/mcp/test_doubt_tools_membrane.py`（append input enum 斷言）

- [ ] **Step 1: Write the failing test**

append：

```python
from the_door.mcp.tools import doubt_transition_tool, doubt_list_tool
from the_door.core.scope.doubt_lifecycle import DoubtLifecycle


def test_transition_target_state_has_enum():
    sch = doubt_transition_tool.TOOL_SCHEMA["properties"]["target_state"]
    assert set(sch["enum"]) == {"investigating", "explained", "fixed", "escalated", "accepted_risk"}
    assert "investigating" in sch["description"]


def test_list_state_and_type_have_enum():
    props = doubt_list_tool.TOOL_SCHEMA["properties"]
    assert set(props["state"]["enum"]) == set(DoubtLifecycle.VALID_TRANSITIONS.keys())
    assert set(props["type"]["enum"]) == {"out_of_scope", "in_scope_incomplete", "anomaly", "low_confidence"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_doubt_tools_membrane.py -q`
Expected: FAIL — `KeyError: 'enum'`

- [ ] **Step 3: Write minimal implementation**

兩工具 input schema **由 builder 衍生、不手寫**（spec §3.2）：

`doubt_transition_tool.py`：module 頂部加 `from the_door.core.scope import doubt_membrane`，TOOL_SCHEMA 的 `target_state`（取代 line 12-15）改為 `"target_state": doubt_membrane.target_state_schema(),`。

`doubt_list_tool.py`：加同 import，`state`（line 11-14）→ `doubt_membrane.state_filter_schema()`、`type`（line 15-18）→ `doubt_membrane.type_filter_schema()`。

> 零副本：enum＋description 全在 `doubt_membrane` 從 gloss 建構（Task 1 已含 builder）。無手抄字串→無漂移→input 側無需 parity（衍生鎖在 Task 1 `test_input_schema_builders_derive_from_gloss`）。
> import 安全（grep 驗）：`doubt_membrane`→{`core.membrane`, `doubt_lifecycle`→`models`}，無 tool/server 鏈，零循環。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_doubt_tools_membrane.py -q`
Expected: PASS（3 passed）。既有 `test_doubt_transition_tool.py::test_unknown_target_state_error` 仍綠（`:60` 守衛保留）。

- [ ] **Step 5: Commit**

```bash
git add src/the_door/mcp/tools/doubt_transition_tool.py src/the_door/mcp/tools/doubt_list_tool.py tests/unit/mcp/test_doubt_tools_membrane.py
git commit -m "feat(doubt-tools): B-side CWA — input schema enums + per-value meaning (J2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: output 投影（三 enum→{value,position}）＋ 更新 characterization

**理論錨：** 膜不變量（emit 帶 position，J1）；真驗整膜（description→Reserved，J5）。

**Files:**
- Modify: `src/the_door/mcp/tools/doubt_transition_tool.py`（wrap payload）
- Modify: `src/the_door/mcp/tools/doubt_list_tool.py`（wrap payload）
- Test: `tests/unit/mcp/test_doubt_tools_membrane.py`（Task 2 characterization 改新形狀＋J5）

- [ ] **Step 1: Update characterization to NEW shape (now failing)**

把 Task 2 的 `test_transition_output_current_state_is_bare` 改為：

```python
def test_transition_output_projects_membrane(tmp_path):
    """投影後：三 enum 為 {value, position}；description 為 reserved（整膜）。"""
    store, d = _seed_explained(tmp_path)
    out = asyncio.run(transition_exec({
        "doubt_id": d.doubt_id, "target_state": "explained", "actor": "a",
        "reason": "fp", "codebase_path": str(tmp_path),
    }))
    assert out["current_state"]["value"] == "explained"
    assert out["current_state"]["position"]["kind"] == "signal"
    assert "investigating" in out["current_state"]["position"]["preconditions"]
    assert out["doubt_type"]["value"] == "anomaly"
    assert out["resolution"]["type"]["value"] == "explained"
    assert out["resolution"]["description"]["position"]["kind"] == "reserved"  # J5 reserved


def test_list_output_projects_membrane(tmp_path):
    store, d = _seed_explained(tmp_path)
    asyncio.run(transition_exec({
        "doubt_id": d.doubt_id, "target_state": "explained", "actor": "a",
        "reason": "fp", "codebase_path": str(tmp_path),
    }))
    out = asyncio.run(list_exec({"codebase_path": str(tmp_path)}))
    row = out["doubts"][0]
    assert row["current_state"]["position"]["kind"] == "signal"
    assert row["doubt_type"]["position"]["kind"] == "signal"
    assert isinstance(out["total"], int)        # total 維持裸 int（J5：非有損聚合）


def test_j5_emit_only_signal_or_reserved(tmp_path):
    """J5：doubt emit 的 position kind ∈ {signal, reserved}，無 noise/verdict。"""
    store, d = _seed_explained(tmp_path)
    out = asyncio.run(transition_exec({
        "doubt_id": d.doubt_id, "target_state": "explained", "actor": "a",
        "reason": "fp", "codebase_path": str(tmp_path),
    }))
    kinds = {
        out["current_state"]["position"]["kind"],
        out["doubt_type"]["position"]["kind"],
        out["resolution"]["type"]["position"]["kind"],
        out["resolution"]["description"]["position"]["kind"],
    }
    assert kinds <= {"signal", "reserved"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_doubt_tools_membrane.py -q`
Expected: FAIL — `current_state` 仍為 str、`["value"]` 取值失敗（`TypeError: string indices`）。

- [ ] **Step 3: Write minimal implementation**

`doubt_transition_tool.py` wrap payload＝**spec §3.3 的 exact code**（投影 `doubt_type`/`current_state` 經 `*_element(...).to_json()`、`resolution.type` 經 `resolution_type_element`、`resolution.description` 經 `free_text_element`；其餘欄不變）。`execute()` 內加 import `from the_door.core.scope.doubt_membrane import (current_state_element, doubt_type_element, resolution_type_element, free_text_element)`。

`doubt_list_tool.py`：per-doubt dict 同樣投影四欄；`total` 不變（裸 int）。

> 不重貼 code（spec §3.3 唯一來源）。關鍵：四欄 → `{value, position}`；`total` 與非 enum 欄維持原樣。

> **順手收斂（非強求）**：若兩處 per-doubt 投影 dict 完全相同，抽 `core/scope/doubt_membrane.py::project_doubt(d) -> dict` 共用，兩工具改 call 它（消重複）。不強求；先綠再視重複度決定。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_doubt_tools_membrane.py -q`
Expected: PASS（input enum 3＋投影 3＝全綠）。

- [ ] **Step 5: Commit**

```bash
git add src/the_door/mcp/tools/doubt_transition_tool.py src/the_door/mcp/tools/doubt_list_tool.py tests/unit/mcp/test_doubt_tools_membrane.py
git commit -m "feat(doubt-tools): project 3 enums through MembraneElement; description->reserved (J1/J5)

Output contract change (witnessed by characterization): enum fields become
{value, position}; resolution.description carries reserved window. LLM-facing
information gain; zero internal consumer breakage (verified).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: schema 半膜→全膜（oneOf/const）＋ J3 parity

**理論錨：** §8.16「機制已在、未用」；J3 單一來源——input 已於 Task 1/3 衍生（零副本），此 task 守 record schema 這唯一副本（parity vs gloss）。

**Files:**
- Modify: `schemas/doubt-record.schema.json`（三 enum → oneOf/const+description）
- Test: `tests/unit/core/scope/test_doubt_membrane_parity.py`（Create）

- [ ] **Step 1: Write the failing test**

建立 `tests/unit/core/scope/test_doubt_membrane_parity.py`：

```python
"""J3：每值意義單一來源——schema description == doubt_membrane gloss（逐字）。"""
import json
from pathlib import Path

from the_door.core.scope import doubt_membrane as dm

_SCHEMA = json.loads(
    (Path(__file__).parents[4] / "schemas" / "doubt-record.schema.json").read_text(encoding="utf-8")
)


def _oneof_map(node):
    return {b["const"]: b["description"] for b in node["oneOf"]}


def test_current_state_schema_matches_gloss():
    m = _oneof_map(_SCHEMA["properties"]["current_state"])
    assert m == dm._STATE_GLOSS


def test_doubt_type_schema_matches_gloss():
    m = _oneof_map(_SCHEMA["properties"]["doubt_type"])
    assert m == dm._TYPE_GLOSS


def test_resolution_type_schema_matches_gloss():
    node = _SCHEMA["properties"]["resolution"]["oneOf"][1]["properties"]["type"]
    assert _oneof_map(node) == dm._RESOLUTION_GLOSS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/scope/test_doubt_membrane_parity.py -q`
Expected: FAIL — `KeyError: 'oneOf'`（schema 仍 enum 形式）。

- [ ] **Step 3: Write minimal implementation**

`schemas/doubt-record.schema.json`：三處 `enum` 改 `oneOf` of `{const, description}`（形式＝spec §3.4 範例），description **逐字＝** `_STATE_GLOSS`(6)／`_TYPE_GLOSS`(4)／`_RESOLUTION_GLOSS`(3) 對應值。位置：`current_state`(line 37-48)、`doubt_type`(line 27-36)、`resolution.oneOf[1].properties.type`(line 127-134)。

> 這是 J3 的**唯一受測副本**（靜態 JSON 不能 import gloss）；parity test（Step 1）逐字鎖死。改 gloss 時須同步此檔、test 會抓漏。

- [ ] **Step 4: Run test to verify it passes ＋ schema 驗證未破壞**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/scope/test_doubt_membrane_parity.py tests/unit/core/scope/ -q`
Expected: PASS（parity 3 passed）＋既有 doubt_store 驗證測試全綠（oneOf/const 驗證等價、已實測）。

- [ ] **Step 5: Commit**

```bash
git add schemas/doubt-record.schema.json tests/unit/core/scope/test_doubt_membrane_parity.py
git commit -m "feat(doubt-schema): half-membrane -> full — oneOf/const per-value meaning, parity-locked (J3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: 全套件回歸驗收 ＋ 連貫性

**Files:** （無；驗收 gate）

- [ ] **Step 1: doubt 相關全測**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/scope/ tests/unit/mcp/ tests/unit/core/membrane/ -q`
Expected: 全綠（含 S0 `test_s1_coherence.py` 仍綠＝S0 地基未鬆動）。

- [ ] **Step 2: 全測零回歸**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest -q`
Expected: 1462（S0 基線）＋新增測試、零 fail。**唯一「變更」＝Task 4 characterization 從 bare 改 {value,position}（有意契約變更、已見證）**；其餘純加法。若有非預期 fail（例如某 test 斷言 doubt 工具 dict 的 enom 為 str）→ 停下檢查是否真有未盤點的 LLM-facing 消費者。

- [ ] **Step 3:（無新 commit；驗收通過即 S1 完成）**

S1 完成 → 進 S2（NoisePosition／edge）spec。起 S2 前重跑種子檔 §9.2 理論重錨、讀 S1 spec §5（慣例樣板）＋§7（對 S2 連貫性回驗點）＋S0 §3a（NoisePosition 方向）。

---

## Self-Review

**1. Spec coverage：**
- spec §3.1 詞彙來源 → Task 1 ✓
- spec §3.2 input enum → Task 3 ✓
- spec §3.3 output 投影（含 description→reserved）→ Task 4 ✓
- spec §3.4 schema oneOf/const → Task 5 ✓
- spec §4 不變量 J1(T4)/J2(T3)/J3(T1 衍生鎖＋T5 schema parity)/J4(T1)/J5(T4) ✓
- spec §6 characterization 先行 → Task 2（先釘）+ Task 4（改形狀）✓
- spec §9 交付物 8 項 → Task 1-5 全覆蓋（deliverable 8＝Task 4 characterization 更新）✓
- out（serialize_doubt/CLI/viewer/落盤/NoisePosition/provenance）→ 正確不在本 plan ✓

**2. Placeholder scan：** 無 TBD；每 step 含完整 code＋exact 指令＋預期輸出 ✓

**3. Type consistency：** `current_state_signal/doubt_type_signal/resolution_type_signal`＋`*_element`＋`free_text_element`＋`target_state_schema/state_filter_schema/type_filter_schema`／`MembraneElement.to_json()→{value,position:{kind,...}}`（S0 既定）／TOOL_SCHEMA 由 builder 衍生（enum 集對齊 gloss key／模型真實集）／record schema oneOf const 對齊 gloss dict——跨 Task 1-5 一致 ✓。`DoubtLifecycle.VALID_TRANSITIONS/_RESOLVING_STATES/is_terminal` 對齊 `doubt_lifecycle.py:32/41/43` ✓

**5. J3 零副本（審查修正）：** input schema 由 `doubt_membrane` builder 衍生（無手抄、無 parity 需求）；record 靜態 schema 為唯一副本、Task 5 parity 逐字守。消除前版「3 份手抄＋只測 2 份」的假性單一來源。

**4. 依賴順序：** Task 1（詞彙）→ Task 3/4（工具用詞彙）；Task 1（gloss）→ Task 5（schema parity 讀 gloss）；Task 2（釘現狀）→ Task 4（改形狀）。無逆序 ✓
