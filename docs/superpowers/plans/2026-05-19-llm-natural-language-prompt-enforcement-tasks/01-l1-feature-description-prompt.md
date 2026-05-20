# L1 Feature Description Prompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the L1 feature-description system prompt that does not exist today, and wire it through `batch_reader`'s two LLM provider calls so L1 snapshot quality stops depending on transient agent-as-LLM context.

**Architecture:** Add a new central `core/llm/prompts.py` module holding an `L1_SYSTEM_PROMPT` constant that enforces the non-technical-reader audience contract. Pass `system_prompt=L1_SYSTEM_PROMPT` to the two `provider.complete` call sites in `batch_reader.py`.

**Tech Stack:** Python 3.12, pytest (existing test infrastructure under `the_door/tests/`), existing LLM provider abstraction (`core/llm/provider.py`).

---

## Background

Source investigation (2026-05-19 session):

**L1 prompt does not exist.** [`batch_reader.py:255`](the_door/src/the_door/core/reading/batch_reader.py:255) builds `prompt = json.dumps({"batch": batch_num, "nodes": node_ids})` and [`batch_reader.py:260`](the_door/src/the_door/core/reading/batch_reader.py:260) calls `await self._provider.complete(prompt)` positionally — no `system_prompt`. Provider classes accept `system_prompt: str | None = None` but it defaults to `None`. The LLM has no stylistic instruction. Snapshot quality currently depends on whichever agent-as-LLM context happened to be present when the snapshot was written; nothing survives across sessions.

**Design principle:** L1 = non-technical reader critical-need; natural language is thickest at this layer. See [README.md](README.md) for the full layer principle and shared out-of-scope list.

## File Structure

| Action | Path | Responsibility |
|---|---|---|
| Create | `the_door/src/the_door/core/llm/prompts.py` | Central prompt strings — `L1_SYSTEM_PROMPT` constant |
| Create | `the_door/tests/unit/core/llm/test_prompts.py` | Prompt content assertions |
| Modify | [`the_door/src/the_door/core/reading/batch_reader.py`](the_door/src/the_door/core/reading/batch_reader.py:151) (lines 151, 260) | Pass `system_prompt=L1_SYSTEM_PROMPT` to `provider.complete` |
| Modify | `the_door/tests/unit/core/reading/test_batch_reader.py` | Assert system_prompt is wired through |

---

## Task 1: Add `L1_SYSTEM_PROMPT` constant and prompt-content tests

**Files:**
- Create: `the_door/src/the_door/core/llm/prompts.py`
- Test:   `the_door/tests/unit/core/llm/test_prompts.py`

- [ ] **Step 1: Write the failing test**

```python
# the_door/tests/unit/core/llm/test_prompts.py
"""Tests assert L1_SYSTEM_PROMPT content satisfies the project's
non-technical-reader contract. The tests are inline string assertions —
no separate validator module — see README's "Why no validator module" note.
"""
from the_door.core.llm.prompts import L1_SYSTEM_PROMPT


def test_l1_system_prompt_targets_non_technical_reader():
    """Prompt must explicitly name the audience."""
    assert "非技術讀者" in L1_SYSTEM_PROMPT


def test_l1_system_prompt_lists_forbidden_jargon_categories():
    """Prompt must enumerate the forbidden categories by name so the LLM
    knows what to avoid."""
    for token in ("函式名", "API endpoint", "檔名", "縮寫", "camelCase"):
        assert token in L1_SYSTEM_PROMPT, f"L1 prompt missing forbidden token: {token}"


def test_l1_system_prompt_requires_feature_schema_fields():
    """Prompt must request all required Feature dataclass fields."""
    for field in ("feature_id", "label", "description", "trigger_description",
                  "confidence", "confidence_reason", "source_nodes"):
        assert field in L1_SYSTEM_PROMPT, f"L1 prompt missing schema field: {field}"


def test_l1_system_prompt_requires_feature_relations_top_level_key():
    """Existing parser (_process_batch line 287) reads data['feature_relations'];
    prompt must produce that exact key at top level."""
    assert "feature_relations" in L1_SYSTEM_PROMPT


def test_l1_system_prompt_good_example_avoids_forbidden_tokens():
    """The prompt's own ✅ example must not violate its own rules.
    Inline jargon spot-check on the example description text."""
    # Find the good example block — everything between ✅ and ❌
    assert "✅" in L1_SYSTEM_PROMPT, "missing good example"
    good_block = L1_SYSTEM_PROMPT.split("✅", 1)[1].split("❌", 1)[0]
    # Spot-check: example description must not contain obvious jargon
    forbidden_substrings = ("/api/", ".py", ".js", "JSON-RPC", "AST")
    for forbidden in forbidden_substrings:
        assert forbidden not in good_block, (
            f"L1 prompt good example contains forbidden substring: {forbidden}"
        )


def test_l1_system_prompt_bad_example_present():
    """Negative example must be present to anchor the contrast."""
    assert "❌" in L1_SYSTEM_PROMPT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest the_door/tests/unit/core/llm/test_prompts.py -v`
Expected: `ModuleNotFoundError: No module named 'the_door.core.llm.prompts'`

- [ ] **Step 3: Write minimal implementation**

```python
# the_door/src/the_door/core/llm/prompts.py
"""Central LLM prompt strings for The Door.

Each prompt is paired with prompt-content tests in
``the_door/tests/unit/core/llm/test_prompts.py`` that assert audience,
schema, and forbidden-jargon contracts. No regex validator —
inline tests check what matters at the lowest cost (see README's
"Why no validator module" note).
"""
from __future__ import annotations


L1_SYSTEM_PROMPT = """\
你是 The Door 的 L1 功能分析助理，目標讀者是**非技術讀者**（產品經理、客服、
營運、非工程背景的決策者）。

## 任務

收到一組 AST 節點清單後，將它們分群成數個 L1 功能（feature），每個 feature
回傳以下欄位：

- feature_id：以 `feat-` 開頭的 kebab-case 識別字串
- label：4–10 字中文短名
- description：一段 1–3 句的功能敘述
- trigger_description：一句話描述使用者怎麼觸發此功能
- confidence：`high` / `medium` / `low`
- confidence_reason：一句話說明信心等級依據
- source_nodes：此 feature 對應的節點 id 清單

## 風格規則（硬性）

description 與 trigger_description 必須符合以下全部規則：

1. **目標讀者是非技術讀者** — 用日常語彙，不假設讀者懂程式
2. **禁止實作細節**：
   - 不得出現函式名（任何含 `(` 的識別字、camelCase 或 snake_case 函式名）
   - 不得出現 API endpoint（例如以 `/api/` 開頭的字串）
   - 不得出現檔名（`.py`、`.js`、`.ts` 等副檔名）
   - 不得出現縮寫（AST、JSON-RPC、API、DOM、HTTP、URL、CVSS、CVE 等）
   - 不得出現 camelCase 識別字
3. **用「做什麼／為了什麼」描述，不用「怎麼做」** — 講功能對使用者的意義，
   不講內部實作流程
4. 若必須提及技術名詞才能說清楚，改用中文白話表達（例如「圖譜」而非「graph」）

## 範例

✅ 好範例：
- description：讓你用瀏覽器看分析結果，畫面以可互動的功能圖譜為核心，
  搭配右側的詳情面板與版本選擇器。
- trigger_description：執行啟動 UI 指令；瀏覽器開啟頁面後會自動載入分析資料。

❌ 壞範例：
- description：啟動 HTTP server 對外暴露 /api/* 端點，由 renderGraphCanvas
  繪製圖譜，並透過 app.js 的 switchToMindmap 切換思維導圖。
- trigger_description：呼叫 the_door.cli.ui_cmd.main() 後 server.py::start 被觸發。

## 輸出格式

回傳 JSON 物件，包含兩個 top-level key：`features` 與 `feature_relations`。

```json
{
  "features": [
    {
      "feature_id": "feat-xxx",
      "label": "...",
      "description": "...",
      "trigger_description": "...",
      "confidence": "high",
      "confidence_reason": "...",
      "source_nodes": ["node-id-1", "node-id-2"]
    }
  ],
  "feature_relations": [
    {"from": "feat-a", "to": "feat-b", "relation": "depends_on"}
  ]
}
```

不要回傳 markdown 程式碼框、不要加額外文字，只回 JSON 物件。
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest the_door/tests/unit/core/llm/test_prompts.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/llm/prompts.py the_door/tests/unit/core/llm/test_prompts.py
git commit -m "feat(llm): add L1_SYSTEM_PROMPT with non-technical-reader rules"
```

---

## Task 2: Wire `L1_SYSTEM_PROMPT` through `batch_reader`

**Files:**
- Modify: [`the_door/src/the_door/core/reading/batch_reader.py:151`](the_door/src/the_door/core/reading/batch_reader.py:151) and [line 260](the_door/src/the_door/core/reading/batch_reader.py:260)
- Test:   `the_door/tests/unit/core/reading/test_batch_reader.py`

- [ ] **Step 1: Inspect existing test fixtures**

Before writing the new test, locate fixture patterns in the existing file:

Run: `grep -nE "^(def|async def|@pytest|class).+test_|BatchReader\(|AsyncMock|MagicMock" the_door/tests/unit/core/reading/test_batch_reader.py | head -30`

Note: existing tests construct `BatchReader(provider, structure)` with positional args. `BatchReader.__init__` signature is `(self, llm_provider, structure, *, max_context_tokens=None)` — first positional is the provider, second is the structure, parser is created internally. Match this style.

- [ ] **Step 2: Write the failing test**

Append to `the_door/tests/unit/core/reading/test_batch_reader.py`. Reuse helpers already defined in the file for building a minimal `StructureJSON` and stub `Feature`; if no shared helpers exist, copy the minimal construction style used by the closest existing test.

```python
# Append to the_door/tests/unit/core/reading/test_batch_reader.py

import json
from unittest.mock import AsyncMock

import pytest

from the_door.core.llm.prompts import L1_SYSTEM_PROMPT
from the_door.core.reading.batch_reader import BatchReader
from the_door.models import StructureJSON, Feature


def _minimal_structure() -> StructureJSON:
    # No topology entries → BatchReader.read() returns empty, but
    # _process_batch and regenerate can still be invoked directly.
    return StructureJSON()


def _stub_feature() -> Feature:
    return Feature(
        feature_id="feat-x",
        label="x",
        description="",
        trigger="user_action",
        trigger_description="",
        confidence="medium",
        confidence_reason="",
        source_nodes=[],
    )


@pytest.mark.asyncio
async def test_process_batch_passes_l1_system_prompt():
    """_process_batch must pass L1_SYSTEM_PROMPT as the system_prompt argument."""
    provider = AsyncMock()
    provider.complete = AsyncMock(
        return_value=json.dumps({"features": [], "feature_relations": []})
    )

    reader = BatchReader(provider, _minimal_structure())
    await reader._process_batch(node_ids=["n1"], batch_num=0)

    assert provider.complete.await_count == 1
    call = provider.complete.await_args
    system_prompt = call.kwargs.get("system_prompt")
    if system_prompt is None and len(call.args) >= 2:
        system_prompt = call.args[1]
    assert system_prompt == L1_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_regenerate_passes_l1_system_prompt():
    """regenerate() must pass L1_SYSTEM_PROMPT as system_prompt."""
    provider = AsyncMock()
    provider.complete = AsyncMock(
        return_value=json.dumps({"features": [{"feature_id": "feat-x", "label": "x"}]})
    )

    reader = BatchReader(provider, _minimal_structure())
    await reader.regenerate("feat-x", _stub_feature())

    call = provider.complete.await_args
    system_prompt = call.kwargs.get("system_prompt")
    if system_prompt is None and len(call.args) >= 2:
        system_prompt = call.args[1]
    assert system_prompt == L1_SYSTEM_PROMPT
```

If the existing test file does not yet use `pytest-asyncio` markers, check whether `pytest.ini` / `pyproject.toml` configures asyncio mode (likely `asyncio_mode = "auto"`). If not, the `@pytest.mark.asyncio` decorator is required as written.

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest the_door/tests/unit/core/reading/test_batch_reader.py -v -k "system_prompt"`
Expected: AssertionError — `system_prompt is None` because current `complete(prompt)` call has no second argument.

- [ ] **Step 4: Modify `batch_reader.py` to pass `system_prompt`**

```python
# the_door/src/the_door/core/reading/batch_reader.py

# Top of file: add to existing imports
from the_door.core.llm.prompts import L1_SYSTEM_PROMPT

# Line 151 (inside regenerate, replace existing line):
response = await self._provider.complete(prompt, system_prompt=L1_SYSTEM_PROMPT)

# Line 260 (inside _process_batch, replace existing line):
response = await self._provider.complete(prompt, system_prompt=L1_SYSTEM_PROMPT)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest the_door/tests/unit/core/reading/test_batch_reader.py -v`
Expected: all existing tests still pass; the 2 new tests pass.

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/core/reading/batch_reader.py the_door/tests/unit/core/reading/test_batch_reader.py
git commit -m "feat(reading): wire L1_SYSTEM_PROMPT through batch_reader provider calls"
```

---

## Done Criteria

This task document is complete when:

1. `pytest the_door/tests/unit/core/llm/test_prompts.py -v` → 6 passed.
2. `pytest the_door/tests/unit/core/reading/test_batch_reader.py -v` → all existing tests still pass, 2 new tests pass.
3. `pytest the_door/tests/ -x -q` → green (full Python suite still passes).
4. Both commits landed.
