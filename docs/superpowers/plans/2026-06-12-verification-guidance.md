# 非-high 信心交叉驗證引導 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在每個 MCP 工具回應上，附一條靜態、建議式的「交叉驗證引導」，指向已註冊證據工具，讓消費端 LLM 在自評為非-high 信心（觸發處境）時自由取用。

**Architecture:** 純加法、infra 只 surface 不 judge（膜模型）。新增一個無狀態 projection 模組 `verification_guidance()` 產生固定 dict（觸發處境兩成因＋證據工具清單＋建議語氣）；`_response_envelope.wrap` 在正常回應路徑附上該欄位（checkpoint envelope 不附）。基礎設施**不掃 payload、不偵測 confidence**——觸發判斷留給 LLM。零新工具、零跨產出硬連線、不依賴 edge-residue。

**Tech Stack:** Python 3.11+、pytest（cwd＝內層 `the_door/`、`PYTHONUTF8=1`、`python -m pytest`）。

**對應 spec：** `docs/superpowers/specs/2026-06-11-low-confidence-verification-guidance-design.md`（讀者＝LLM；範圍術語以該檔 §3.3「🔑 觸發處境 canonical」為準＝非-high 信心＝{未評估(None) ∪ 中信心(medium) ∪ 低信心(low)}）。

**不可飄移的定位（本輪討論定案，逐 task 守）：**
- infra **surface 不 judge**：`wrap` 不掃 payload、不偵測 confidence；引導是**靜態**的。
- 觸發處境兩成因**分清、不混**：未評估＝LLM 尚未執行評估（≠不可評估）→補做評估；中/低信心＝已評估證據不足→補強證據。
- 措辭**建議/可選**，非強制（無「你必須」）。指向的工具名**必須是已註冊工具**。
- 與既有 `next_actions` **並存、不改其形狀**；引導是獨立 top-level 欄位。
- 不碰 `NextActionSuggester` global 流程；不做可達性/死碼/惡意；不為單一功能極端化。

**✅ 設計張力已雙審裁定＝KEEP（抽 `_build_tools()`）：**
Task 1 把 server.py 的工具清單抽成 `_build_tools()` 以衍生可列舉的 `REGISTERED_TOOL_NAMES`，讓 §6.1「引導工具名 ∈ 已註冊集」這條 invariant **真**可驗。雙審理由：替代案（test-local allowlist `{"extract_structure"}`）是循環論證——「斷言 guidance ⊆ 我自己宣告允許的集合」驗不到「真有註冊」，留飄移縫；`_build_tools()` 是 async closure 無法直接列舉下**最便宜的『誠實』列舉手段**，且屬通用基礎建設（工具名單一來源）、非單一功能極端化。代價＝機械搬移 ~150 行、獨立 commit、低風險（Task 1 Step 3 已加閉包依賴前置檢查）。

---

## File Structure

- **Create** `the_door/src/the_door/core/guidance/verification_guidance.py`
  — 無狀態 projection：`verification_guidance() -> dict`，回傳固定引導內容。SRP＝只產生引導投影、不碰 payload、不判斷。
- **Modify** `the_door/src/the_door/mcp/server.py`
  — 抽 `_build_tools() -> list[Tool]`（既有清單原封不動搬入）＋衍生 `REGISTERED_TOOL_NAMES: frozenset[str]`。單一來源、可列舉。
- **Modify** `the_door/src/the_door/mcp/tools/_response_envelope.py`
  — `wrap` 正常路徑附 `payload["verification_guidance"]`；checkpoint 早回路徑**不附**。
- **Test** `the_door/tests/unit/mcp/test_server_tool_registry.py`（新）— `_build_tools()`/`REGISTERED_TOOL_NAMES` drift guard。
- **Test** `the_door/tests/unit/core/guidance/test_verification_guidance.py`（新）— 引導內容/語氣/工具名 invariant。
- **Test** `the_door/tests/unit/mcp/test_response_envelope.py`（既有，追加）— 附帶/並存/checkpoint 不附。

---

## Task 1: server.py 工具名單一來源（`_build_tools` + `REGISTERED_TOOL_NAMES`）

**Files:**
- Modify: `the_door/src/the_door/mcp/server.py`（`_setup_tools` 內 `list_tools` closure、約 35–185 行）
- Test: `the_door/tests/unit/mcp/test_server_tool_registry.py`

- [ ] **Step 1: 寫失敗測試**

```python
# the_door/tests/unit/mcp/test_server_tool_registry.py
def test_registered_tool_names_match_build_tools():
    from the_door.mcp.server import _build_tools, REGISTERED_TOOL_NAMES
    names = {t.name for t in _build_tools()}
    assert names == REGISTERED_TOOL_NAMES
    # 釘樁：第一刀引導要指向的工具確實註冊
    assert "extract_structure" in REGISTERED_TOOL_NAMES
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/unit/mcp/test_server_tool_registry.py -v`
Expected: FAIL — `ImportError: cannot import name '_build_tools'`

- [ ] **Step 3: 搬移前先驗無閉包依賴**

Run: `git grep -n "self" the_door/src/the_door/mcp/server.py`
Expected: `list_tools` closure 的 `return [Tool(...), ...]` body **不出現** `self` 或其他 enclosing-scope 變數——`Tool(...)` 只引用 module-level import（`Tool` 與 schema 常數）。若 body 內有 `self`/閉包引用，先解依賴再搬（否則 module-level `_build_tools()` 會在 import 時炸）。

- [ ] **Step 4: 最小實作**

在 `server.py` 模組層級（class 外）新增 `_build_tools()`，把 `list_tools` closure 內**既有的** `return [Tool(...), ...]` 清單**原封不動**搬進來，並衍生常數：

```python
# server.py — module level, after imports, before class TheDoorMCPServer
def _build_tools() -> list[Tool]:
    return [
        # ← 把原 list_tools closure 內現有的 Tool(...) 清單整段搬到此處，內容一字不改
    ]


REGISTERED_TOOL_NAMES: frozenset[str] = frozenset(t.name for t in _build_tools())
```

把 closure 改為委派：

```python
    def _setup_tools(self):
        @self._server.list_tools()
        async def list_tools():
            return _build_tools()
```

> 純機械搬移：Tool 定義內容（name/description/inputSchema）全不變，只改「定義位置」與「closure 改呼叫 `_build_tools()`」。

- [ ] **Step 5: 跑測試確認通過**

Run: `python -m pytest tests/unit/mcp/test_server_tool_registry.py -v`
Expected: PASS

- [ ] **Step 6: 局部回歸（確認搬移沒破壞既有 server 行為）**

Run: `python -m pytest tests/unit/mcp/ tests/integration/test_router_binding.py -q`
Expected: PASS（全綠）

- [ ] **Step 7: Commit**

```bash
git add the_door/src/the_door/mcp/server.py the_door/tests/unit/mcp/test_server_tool_registry.py
git commit -F - <<'EOF'
refactor(mcp): 抽 _build_tools()+REGISTERED_TOOL_NAMES 為工具名單一來源

供 verification_guidance invariant（引導工具名 ∈ 已註冊集）可列舉驗證。
Tool 定義內容不變、僅搬移位置。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

## Task 2: `verification_guidance()` projection 模組

**Files:**
- Create: `the_door/src/the_door/core/guidance/verification_guidance.py`
- Test: `the_door/tests/unit/core/guidance/test_verification_guidance.py`

- [ ] **Step 1: 寫失敗測試**

```python
# the_door/tests/unit/core/guidance/test_verification_guidance.py
import json
from the_door.core.guidance.verification_guidance import verification_guidance
from the_door.mcp.server import REGISTERED_TOOL_NAMES


def test_guidance_is_json_serializable_and_stable():
    g = verification_guidance()
    json.dumps(g)                      # JSON-safe
    assert g == verification_guidance()  # 決定性、無狀態


def test_guidance_covers_both_causes_of_trigger_state():
    # 觸發處境兩成因須分清且各帶「相異」動作（未評估→補做評估；中/低→補強證據）
    causes = {c["cause"]: c for c in verification_guidance()["causes"]}
    assert set(causes) == {"unassessed", "low_or_medium"}
    assert "補做" in causes["unassessed"]["action"]         # 補做評估（鑑別 token）
    assert "補強" in causes["low_or_medium"]["action"]       # 補強證據（鑑別 token）
    assert causes["unassessed"]["action"] != causes["low_or_medium"]["action"]  # 兩成因不混


def test_guidance_evidence_tools_are_registered():
    # invariant：指向的工具名必為已註冊工具（不指向不存在工具）
    tools = {t["tool"] for t in verification_guidance()["evidence_tools"]}
    assert tools                                   # 非空
    assert tools <= REGISTERED_TOOL_NAMES
    assert "extract_structure" in tools            # 第一版證據源


def test_guidance_tone_is_suggestive_not_imperative():
    blob = json.dumps(verification_guidance(), ensure_ascii=False)
    assert "可選" in blob and "非強制" in blob     # 建議語氣的有鑑別力 token（非 "可" 這種近恆真字）
    assert "必須" not in blob and "務必" not in blob
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/unit/core/guidance/test_verification_guidance.py -v`
Expected: FAIL — `ModuleNotFoundError: ... verification_guidance`

- [ ] **Step 3: 最小實作**

```python
# the_door/src/the_door/core/guidance/verification_guidance.py
"""非-high 信心交叉驗證引導（projection；infra surface 不 judge）。

固定、無狀態、與工具無關的引導：宣告「自評為非-high 信心（觸發處境）的判斷，
可選用哪些已註冊證據工具交叉驗證」。**不掃 payload、不偵測 confidence、不下結論**——
觸發與否、調哪個、結論為何，全由消費端 LLM 自決。

觸發處境 canonical（spec §3.3）＝非-high 信心 ＝ {未評估(None) ∪ 中信心 ∪ 低信心}。
"""
from __future__ import annotations


def verification_guidance() -> dict:
    """回傳固定引導 dict（JSON-safe、決定性）。"""
    return {
        "applies_when": (
            "當你自評當前判斷為非-high 信心（未評估／中信心／低信心）時，"
            "可選用下列已註冊工具交叉驗證；high 信心無需。"
        ),
        "causes": [
            {
                "cause": "unassessed",
                "meaning": "未評估＝你尚未執行評估這個動作（≠ 產出不可評估）。",
                "action": "去調證據工具把評估補做（可填補的流程缺口）。",
            },
            {
                "cause": "low_or_medium",
                "meaning": "中/低信心＝你已評估、但證據不足所顯示的中低水準。",
                "action": "去調證據工具補強證據。",
            },
        ],
        "evidence_tools": [
            {
                "tool": "extract_structure",
                "usage": "查節點 callers/callees/resolution/topology，"
                         "判斷『孤立／低信心邊』是真是假。",
            },
        ],
        "note": "可選、非強制：是否調用、調哪個、結論為何，由你決定。",
    }
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/unit/core/guidance/test_verification_guidance.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/guidance/verification_guidance.py the_door/tests/unit/core/guidance/test_verification_guidance.py
git commit -F - <<'EOF'
feat(guidance): verification_guidance() 非-high 信心交叉驗證引導 projection

靜態、無狀態、infra surface 不 judge；兩成因（未評估／中低信心）各帶動作；
指向已註冊 extract_structure；建議語氣。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

## Task 3: 接入 `wrap`（正常路徑附、checkpoint 不附）

**Files:**
- Modify: `the_door/src/the_door/mcp/tools/_response_envelope.py:14-38`
- Test: `the_door/tests/unit/mcp/test_response_envelope.py`（追加）

- [ ] **Step 1: 寫失敗測試（追加到既有檔尾）**

```python
def test_wrap_injects_verification_guidance(tmp_path):
    from the_door.mcp.tools._response_envelope import wrap
    from the_door.core.guidance.verification_guidance import verification_guidance
    wrapped = wrap({"result": "ok"}, project_path=tmp_path, context="mcp")
    assert wrapped["verification_guidance"] == verification_guidance()


def test_wrap_guidance_coexists_with_next_actions(tmp_path):
    from the_door.mcp.tools._response_envelope import wrap
    wrapped = wrap({"result": "ok"}, project_path=tmp_path, context="mcp")
    # 並存、不破壞 next_actions 形狀
    assert "next_actions" in wrapped and isinstance(wrapped["next_actions"], list)
    assert "verification_guidance" in wrapped
    assert wrapped["result"] == "ok"


def test_wrap_checkpoint_envelope_has_no_guidance(tmp_path):
    from the_door.mcp.tools._response_envelope import wrap
    from the_door.core.flow_guard import Decision, CheckpointOption
    # chosen 預設 None → is_resolved=False → 走 checkpoint 早回路徑
    decision = Decision(
        checkpoint_name="cp", status="unresolved",
        options=[CheckpointOption(key="k", label="l", next_call="c")],
    )
    env = wrap({"_decision": decision}, project_path=tmp_path, context="mcp")
    # checkpoint 是控制流回應、非判斷輸出：不附引導
    assert env["result"] is None
    assert "verification_guidance" not in env
```

> ✓ 已確認簽名（flow_guard.py:12-21）：`Decision(checkpoint_name:str, status:str,
> options:list[CheckpointOption], chosen:str|None=None)`、`CheckpointOption(key,label,next_call="")`；
> `is_resolved == (chosen is not None)`，故 `chosen` 留預設 None 即走 checkpoint 早回路徑。

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/unit/mcp/test_response_envelope.py -v`
Expected: FAIL — `KeyError: 'verification_guidance'`（前兩個）

- [ ] **Step 3: 最小實作**

`_response_envelope.py` 加 import 並在**正常路徑**附欄位（checkpoint 早回不動）：

```python
from the_door.core.guidance.verification_guidance import verification_guidance
# ... 既有 imports ...

def wrap(payload: dict, project_path: Path, context: ActionContext = "mcp") -> dict:
    decision: Decision | None = payload.pop("_decision", None)
    if decision is not None and not decision.is_resolved:
        return {                      # checkpoint envelope：不附引導
            "checkpoint": decision.checkpoint_name,
            "status": decision.status,
            "options": [
                {"key": o.key, "label": o.label, "next_call": o.next_call}
                for o in decision.options
            ],
            "result": None,
        }

    state = StateInspector(Path(project_path)).inspect()
    actions = NextActionSuggester().suggest(state, context=context)
    payload["next_actions"] = [action_to_json(a) for a in actions]
    payload["verification_guidance"] = verification_guidance()   # ← 新增
    return payload
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/unit/mcp/test_response_envelope.py -v`
Expected: PASS（既有 2 + 新 3 全綠）

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/mcp/tools/_response_envelope.py the_door/tests/unit/mcp/test_response_envelope.py
git commit -F - <<'EOF'
feat(mcp): wrap 正常回應附 verification_guidance（checkpoint 不附）

純加法、與 next_actions 並存不改其形狀。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

## Task 4: 全套回歸 + 通用性釘樁

**Files:** 無新檔；驗證整體。

- [ ] **Step 1: 全套 pytest 零回歸**

Run: `python -m pytest -q`（cwd＝內層 `the_door/`、`PYTHONUTF8=1`）
Expected: PASS；基線 1452 passed + 本 plan 新增（約 +8）、0 failed。

- [ ] **Step 2: 通用性釘樁（人工 grep 確認，spec §6.1 末條）**

Run: `git grep -nE "死碼|dead.?code|惡意|malicious|可達性|reachab" the_door/src/the_door/core/guidance/verification_guidance.py`
Expected: 無 match（引導與死碼/惡意/可達性零耦合）。

- [ ] **Step 3: 確認 efficacy 層維持誠實（spec §6.2，非程式 gate）**

人工確認：本 plan **未**在程式內宣稱「已驗證 LLM 行為改變」；efficacy 仍為 spec §6.2 的 LLM@分級信心（「實質改變行為」＝low），未被洗成 high。無程式碼動作，僅核對 commit 訊息/註解未越界。

- [ ] **Step 4: Final commit（若 Step 1–3 有任何收尾）**

```bash
git status   # 預期 clean；若 Task 1–3 已各自 commit 則本步無動作
```

---

## Self-Review（writing-plans 要求，已自查）

1. **Spec coverage**：§3.1 骨架→Task 3；§3.2 工具清單(extract_structure)→Task 2；§3.3 觸發處境兩成因＋infra 不偵測→Task 2/3；§4 In(wrap 附/清單/測試)→Task 2/3、Out(不碰 global、不掃 payload、無新工具)→守於 Task 3 實作與「不可飄移定位」；§5 並存→Task 3 test、A 覆蓋成本→已知接受；§6.1 artifact 六條→Task 1(工具名∈註冊)/Task 2(兩成因、語氣、清單)/Task 3(並存、checkpoint)/Task 4(零回歸、通用性釘樁)；§6.2 efficacy→Task 4 Step 3 守不越界。**無未覆蓋條目。**
2. **Placeholder scan**：無 TBD/「適當處理」；Task 1 搬移以「既有清單原封不動」精確指涉既有碼（非佔位）；Task 3 對 Decision 建構子標「以實際欄位為準」＝誠實標註、非佔位。
3. **Type consistency**：`verification_guidance()`、`REGISTERED_TOOL_NAMES`、`_build_tools()` 命名跨 Task 一致；引導 dict 鍵（applies_when/causes[cause,meaning,action]/evidence_tools[tool,usage]/note）跨 Task 2 與 Task 3 測試一致。
