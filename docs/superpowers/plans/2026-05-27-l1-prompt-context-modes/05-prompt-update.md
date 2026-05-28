# Task 05 — L1_SYSTEM_PROMPT Update for Context Modes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修改 `L1_SYSTEM_PROMPT`：(a) 告知 LLM 輸入可能是 node_id 字串或完整 ASTNode 物件，依 `context_mode` 欄位區分；(b) 新增硬性規則第 5 條，禁止 LLM 直接複製 docstring / comments / decorators / signature 到 description。

**Architecture:** 純 prompt 文字編輯。L1_SYSTEM_PROMPT 是 `the_door/src/the_door/core/llm/prompts.py` 的 module-level constant。對應 prompt-content 測試在 `tests/unit/core/llm/test_prompts.py`。

**Tech Stack:** Python 3.11+, pytest.

**Test Coverage Requirement:** `prompts.py` 維持 100% line coverage（該檔案邏輯極簡，本質是 constant + module docstring；coverage 主要透過 prompt-content 測試達成）。新增測試覆蓋 prompt 出現的兩條關鍵語句。

---

## Background（自含）

`L1_SYSTEM_PROMPT` 位於 `the_door/src/the_door/core/llm/prompts.py`，是 L1 LLM 翻譯使用的 system prompt。當前內容（節錄第 16-84 行）：

```
你是 The Door 的 L1 功能分析助理...

## 任務
你會收到一組 AST 節點清單——可能來自一次批次分析...

## 風格規則（硬性）
description 與 trigger_description 必須符合以下全部規則：
1. 目標讀者是非技術讀者...
2. 禁止實作細節...
3. 用「做什麼／為了什麼」描述...
4. 若必須提及技術名詞才能說清楚...

## 範例
...

## 輸出格式
...
```

兩個必要修改：

1. **「任務」section 第一句**：目前說「AST 節點清單」，需更新為說明可能是字串清單或完整物件，由 `context_mode` 區分。
2. **「風格規則」加第 5 條**：明確禁止 LLM 看到 docstring/comments/decorators/signature 就直接複製進 description（避免 detail 模式反而比 minimal 更糟）。

對應 prompt-content 測試已存在於 `the_door/tests/unit/core/llm/test_prompts.py`，用斷言 prompt 文字片段的方式驗證內容契約（spec 中提到：「prompt-content 測試在 inline 模式檢查 prompt 內容」）。本任務新增 2 個測試案例。

---

## Files

- Modify: `the_door/src/the_door/core/llm/prompts.py`
- Modify (or create section in): `the_door/tests/unit/core/llm/test_prompts.py`

---

## Steps

### Step 1 — Write failing prompt-content tests

- [ ] **Step 1: Add 2 failing tests for new prompt content**

Open `the_door/tests/unit/core/llm/test_prompts.py`. Add the following test class (or append cases to an existing class if the file already groups by prompt section):

```python
"""Tests for context_mode + docstring-passthrough rule (Task 05)."""
from the_door.core.llm.prompts import L1_SYSTEM_PROMPT


class TestContextModeAwareness:
    def test_prompt_mentions_both_context_modes(self):
        """Prompt must inform LLM about minimal vs detail mode formats."""
        assert "context_mode" in L1_SYSTEM_PROMPT
        assert "minimal" in L1_SYSTEM_PROMPT
        assert "detail" in L1_SYSTEM_PROMPT

    def test_prompt_describes_minimal_format(self):
        """Prompt must say minimal mode is node_id-only."""
        # Looser check: prompt should describe the string-id format somewhere
        # near the context_mode mention.
        assert "節點 ID" in L1_SYSTEM_PROMPT or "node id" in L1_SYSTEM_PROMPT.lower()

    def test_prompt_describes_detail_format(self):
        """Prompt must describe detail mode includes signature/docstring/decorators."""
        # Detail mode 出現的關鍵字
        assert "docstring" in L1_SYSTEM_PROMPT
        assert "signature" in L1_SYSTEM_PROMPT or "簽名" in L1_SYSTEM_PROMPT


class TestDocstringPassthroughRule:
    def test_prompt_has_rule_5_forbidding_docstring_passthrough(self):
        """硬性規則第 5 條：禁止直接複製 docstring 進 description。"""
        # 找到「第 5 條」或「5.」開頭的規則
        assert ("5." in L1_SYSTEM_PROMPT and "docstring" in L1_SYSTEM_PROMPT)

    def test_rule_explicitly_says_dont_copy(self):
        """規則必須明確禁止「直接複製」「引用」這類動作。"""
        text = L1_SYSTEM_PROMPT
        forbidden_action_phrases = ["不可", "禁止", "不得"]
        copy_phrases = ["複製", "引用", "抄錄"]
        # 至少一組「禁止 + 複製」組合出現於 prompt
        has_forbid = any(p in text for p in forbidden_action_phrases)
        has_copy = any(p in text for p in copy_phrases)
        assert has_forbid and has_copy

    def test_rule_covers_all_implementation_hints(self):
        """Rule 5 應點名 docstring / comments / decorators / signature 等實作層資訊。"""
        text = L1_SYSTEM_PROMPT
        # 至少 3/4 出現（容許實作上小幅措辭調整）
        markers = ["docstring", "comments", "decorators", "signature"]
        hits = sum(1 for m in markers if m in text or m.lower() in text.lower())
        assert hits >= 3, f"Rule 5 should mention at least 3 of {markers}, got {hits}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest the_door/tests/unit/core/llm/test_prompts.py -v`
Expected: 上述新增測試 FAIL；既有測試 PASS。

### Step 2 — Update L1_SYSTEM_PROMPT

- [ ] **Step 3: Update the prompt text**

Open `the_door/src/the_door/core/llm/prompts.py`. Locate `L1_SYSTEM_PROMPT`. Apply two surgical edits:

**3a. Replace the「任務」section opening paragraph:**

Find:
```
## 任務

你會收到一組 AST 節點清單——可能來自一次批次分析，也可能是單一功能的重新分析。
將它們整理成一或多個 L1 功能（feature），每個 feature 回傳以下欄位：
```

Replace with:
```
## 任務

你會收到一組 AST 節點。每個輸入物件中的 `context_mode` 欄位會告知格式：

- **minimal 模式**（`context_mode: "minimal"`）：`nodes` 是節點 ID 字串清單（如 `"OrderController.checkout"`）。只有名稱可參考。
- **detail 模式**（`context_mode: "detail"`）：`nodes` 是物件清單，每個物件包含 node_id、name、file、language、parameters（函數簽名）、return_type、decorators / annotations、docstring、comments 等完整資訊。

輸入可能來自一次批次分析，也可能是單一功能的重新分析。將節點整理成一或多個 L1 功能（feature），每個 feature 回傳以下欄位：
```

**3b. Add Rule 5 to the「風格規則（硬性）」section:**

Find the existing rule 4:
```
4. 若必須提及技術名詞才能說清楚，改用中文白話表達（例如「圖譜」而非「graph」）
```

Insert Rule 5 directly after rule 4:

```
5. **看到 docstring / comments / decorators / annotations / signature 等實作層資訊時**：用它們**理解**功能在做什麼，但**不可**把這些內容直接複製或引用到 description / trigger_description 裡。輸出仍然是給非技術讀者看的白話敘述，不是把英文 docstring 翻譯成中文。
```

- [ ] **Step 4: Run prompt tests**

Run: `pytest the_door/tests/unit/core/llm/test_prompts.py -v`
Expected: 全綠（新增與既有測試皆 PASS）。

若某既有測試因 prompt 內容變更而失敗（例如測試 prompt 字長 / 段落數），就地評估：
- 若 assertion 是內容契約（不允許某些字串出現），保留並修 prompt 不要違反
- 若 assertion 是與被刪除/取代字句的 strict equality，更新 assertion 反映新內容
- **不要**為了通過測試弱化新規則的措辭

- [ ] **Step 5: Coverage check**

Run: `pytest the_door/tests/unit/core/llm/test_prompts.py --cov=the_door.core.llm.prompts --cov-report=term-missing`
Expected: 100%（檔案邏輯極簡）。

- [ ] **Step 6: Smoke test — end-to-end prompt usage**

Run: `pytest the_door/tests/unit/core/reading/ -v -k "test_detail_mode_prompt_contains"`
Expected: 既有「detail 模式 prompt 含 docstring」測試仍 PASS（驗證 prompt 被正確送進 LLM）。

- [ ] **Step 7: Full regression**

Run: `pytest the_door/tests/ -x -q`
Expected: 無新 failure。

- [ ] **Step 8: Commit**

```bash
git add the_door/src/the_door/core/llm/prompts.py the_door/tests/unit/core/llm/test_prompts.py
git commit -m "feat(prompts): teach L1 prompt about context_mode + add anti-passthrough rule

任務 section 告知 LLM 輸入可能是 minimal (node_id 字串) 或 detail
(完整 ASTNode 物件)，由 context_mode 欄位區分。新增硬性規則 5：禁止
直接複製 docstring / comments / decorators / signature 進 description。
配合 prompt-content 測試覆蓋兩條內容契約。"
```

---

## Acceptance Criteria

- [ ] `L1_SYSTEM_PROMPT` 含字串 `"context_mode"`、`"minimal"`、`"detail"`
- [ ] 「任務」section 明確說明 minimal 模式收到 node_id 字串、detail 模式收到完整物件
- [ ] 風格規則新增第 5 條，明確禁止直接複製 docstring/comments/decorators/signature
- [ ] 規則 5 至少點名 3 個（docstring/comments/decorators/signature）
- [ ] 既有 prompt-content 測試（既有 forbidden-jargon / audience / schema 契約）仍 PASS
- [ ] 新增測試（context_mode awareness、docstring passthrough rule）全綠
- [ ] `prompts.py` 100% line coverage
- [ ] `pytest the_door/tests/` 無新增 failure
