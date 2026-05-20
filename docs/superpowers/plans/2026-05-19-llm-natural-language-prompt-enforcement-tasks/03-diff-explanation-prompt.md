# Diff Explanation Prompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen the diff-explanation prompt so it enforces the non-technical-reader audience contract with an explicit forbidden-jargon list and worked good/bad examples, instead of the current soft directive.

**Architecture:** Rewrite `APIHandlers._build_diff_explanation_prompt` to add a named forbidden-jargon list, a ✅/❌ worked-example pair, and explicit anti-fabrication wording, while preserving the existing 5-field output schema and `output_language` carry-through.

**Tech Stack:** Python 3.12, pytest (existing test infrastructure under `the_door/tests/`).

---

## Background

Source investigation (2026-05-19 session):

**diff_explanation prompt** ([`api_handlers.py:880-904`](the_door/src/the_door/core/ui/api_handlers.py:880)) already says "文字面向非工程師，避免不必要的技術術語" but has no forbidden-pattern list, no worked examples, no enforcement.

**Design principle:** the change/diff explanation is critical-need cross-cutting information that must bubble up to a non-technical reader in natural language. See [README.md](README.md) for the full layer principle and shared out-of-scope list.

## File Structure

| Action | Path | Responsibility |
|---|---|---|
| Modify | [`the_door/src/the_door/core/ui/api_handlers.py`](the_door/src/the_door/core/ui/api_handlers.py:880) (lines 880-904, `_build_diff_explanation_prompt`) | Strengthen with forbidden list + examples |
| Modify | `the_door/tests/unit/core/ui/test_api_handlers.py` | Assert prompt content |

---

## Task 1: Strengthen `_build_diff_explanation_prompt`

**Files:**
- Modify: [`the_door/src/the_door/core/ui/api_handlers.py:880-904`](the_door/src/the_door/core/ui/api_handlers.py:880)
- Modify: `the_door/tests/unit/core/ui/test_api_handlers.py` (or `test_api_handlers_ui3.py` if that file already tests this method)

- [ ] **Step 1: Locate which existing test file tests this method**

Run: `grep -nE "_build_diff_explanation_prompt|diff_explanation_prompt" the_door/tests/unit/core/ui/test_api_handlers*.py`

If a file already has tests for this method, append the new tests there. If neither file mentions it, add to `test_api_handlers.py`.

- [ ] **Step 2: Write the failing tests**

```python
# Append to the_door/tests/unit/core/ui/test_api_handlers.py
# (or test_api_handlers_ui3.py per Step 1 finding)

from the_door.core.ui.api_handlers import APIHandlers


def test_diff_explanation_prompt_lists_forbidden_jargon_categories():
    """Prompt must enumerate forbidden categories by name."""
    prompt = APIHandlers._build_diff_explanation_prompt("feat-x", {}, "zh-Hant")
    for token in ("函式名", "API endpoint", "檔名", "縮寫"):
        assert token in prompt, f"diff_explanation prompt missing forbidden token: {token}"


def test_diff_explanation_prompt_has_good_and_bad_examples():
    prompt = APIHandlers._build_diff_explanation_prompt("feat-x", {}, "zh-Hant")
    assert "✅" in prompt, "missing good example marker"
    assert "❌" in prompt, "missing bad example marker"


def test_diff_explanation_prompt_carries_through_output_language():
    """Existing contract — language parameter must reach the prompt."""
    prompt = APIHandlers._build_diff_explanation_prompt("feat-x", {}, "en")
    assert "en" in prompt


def test_diff_explanation_prompt_preserves_existing_schema():
    """Regression: don't break existing 5-field output schema."""
    prompt = APIHandlers._build_diff_explanation_prompt("feat-x", {}, "zh-Hant")
    for field in ("impact_summary", "possible_purpose", "linked_resources",
                  "caution", "confidence"):
        assert field in prompt


def test_diff_explanation_prompt_good_example_avoids_forbidden_tokens():
    """The prompt's own ✅ example must not violate its own rules."""
    prompt = APIHandlers._build_diff_explanation_prompt("feat-x", {}, "zh-Hant")
    good_block = prompt.split("✅", 1)[1].split("❌", 1)[0]
    for forbidden in ("/api/", ".py", ".js", "JSON-RPC", "AST"):
        assert forbidden not in good_block, (
            f"diff_explanation good example contains forbidden substring: {forbidden}"
        )
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest the_door/tests/unit/core/ui/test_api_handlers.py -v -k "diff_explanation_prompt"`
Expected: 2-3 failures (schema fields and language carry-through pass with current prompt; forbidden-list, good/bad examples, and example-cleanliness fail).

- [ ] **Step 4: Strengthen `_build_diff_explanation_prompt`**

Replace the method body ([`api_handlers.py:880-904`](the_door/src/the_door/core/ui/api_handlers.py:880)):

```python
@staticmethod
def _build_diff_explanation_prompt(
    feature_id: str, context: dict, output_language: str
) -> str:
    """Build a structured prompt for diff explanation generation.

    Enforces non-technical-reader-friendly output via an explicit
    forbidden-jargon list and worked good/bad examples. Tests in
    test_api_handlers.py assert these elements remain present.
    """
    ctx_text = (
        json.dumps(context, ensure_ascii=False, indent=2)
        if context else "（無差異資料）"
    )
    return f"""你是版本差異分析助理。根據以下差異資料，以 {output_language} 回答四個問題。
目標讀者是**非技術讀者**（產品經理、客服、營運），不是工程師。

差異資料（feature_id: {feature_id}）：
{ctx_text}

## 風格規則（硬性）

四個欄位的文字內容必須符合：

- **禁止實作細節**：函式名、API endpoint（如以 `/api/` 開頭的字串）、檔名
  （`.py` / `.js` / `.ts` 等副檔名）、縮寫（AST / JSON-RPC / API / DOM 等）、
  camelCase 識別字
- 用「影響什麼／為了什麼」描述，不用「怎麼改的程式」
- 必須使用 {output_language} 語言回答
- 只根據提供的資料推論，不要編造需求、commit message 或不存在的資源
- 若資料不足，confidence 填 low，caution 說明推論依據有限

## 範例

✅ 好範例：
- impact_summary：使用者打開頁面時看到的不再是滿屏的圖譜，而是一份可閱讀的功能清單。

❌ 壞範例：
- impact_summary：移除 renderGraphCanvas，改用 featureCard 組件，並透過 /api/l1 載入。

## 輸出格式

請以 JSON 格式回答，不要包含其他文字：

{{
  "impact_summary": "此差異對使用者體驗影響什麼（一句話，面向非技術讀者）",
  "possible_purpose": "此變更可以達成什麼目的（一句話，用「可能」語氣）",
  "linked_resources": ["相關功能名稱列表，最多 5 個；不要列函式名或檔名"],
  "caution": "需要注意的地方；資料不足時說明推論依據有限",
  "confidence": "high 或 medium 或 low"
}}"""
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest the_door/tests/unit/core/ui/test_api_handlers.py -v -k "diff_explanation_prompt"`
Expected: all 5 new tests pass; existing tests still green.

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/core/ui/api_handlers.py the_door/tests/unit/core/ui/test_api_handlers.py
git commit -m "feat(api): strengthen diff_explanation prompt with forbidden list + examples"
```

---

## Done Criteria

This task document is complete when:

1. `pytest the_door/tests/unit/core/ui/test_api_handlers.py -v -k "diff_explanation_prompt"` → 5 new tests pass.
2. `pytest the_door/tests/ -x -q` → green (full Python suite still passes).
3. The commit landed.

## Manual smoke check (optional, requires API key or agent-as-LLM run)

Regenerate one diff explanation via the viewer and check the output uses
non-technical wording — no `/api/...`, no file extensions, no camelCase
identifiers in the four text fields.
