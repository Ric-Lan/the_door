# Task 08 — MCP `analyze_tool` `context_mode` Input

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `analyze_tool` MCP tool 的 input schema 新增 optional `context_mode` 欄位，enum 為 `["detail", "minimal"]`，預設 `"detail"`。把該值轉發給 `PipelineOrchestrator`。`extract_structure` MCP tool **不受影響**（它不呼叫 LLM）。

**Architecture:** MCP tool 接受新欄位，做 enum 驗證後傳給 orchestrator。沒指定欄位的舊 caller 自動拿到 `"detail"`，向後相容。

**Tech Stack:** Python 3.11+, jsonschema-style input schema, pytest, pytest-asyncio.

**Test Coverage Requirement:** `analyze_tool.py` 中本任務修改的範圍達 100% line coverage（含 schema 驗證、預設值、無效值拒絕、轉發路徑）。

---

## Background（自含）

`analyze_tool` MCP tool 位於 `the_door/src/the_door/mcp/tools/analyze_tool.py`。它將 MCP 請求轉成 `PipelineOrchestrator` 呼叫並回傳結果。`PipelineOrchestrator` 在前置任務已接受 `context_mode: Literal["detail", "minimal"]` kwarg。

MCP tool 通常有一個 `TOOL_SCHEMA` 或類似 dict 宣告 input 形狀（jsonschema-flavored）。本任務在其中加入：

```json
{
  "type": "string",
  "enum": ["detail", "minimal"],
  "default": "detail",
  "description": "..."
}
```

並在 handler 函式（例如 `handle(...)`、`run(...)` 或 `__call__`）內讀取此值傳給 orchestrator。

**spec §5.3 明確規定**：`extract_structure` MCP tool **不受本任務影響** — 它只做結構抽取，不呼叫 LLM。

---

## Files

- Modify: `the_door/src/the_door/mcp/tools/analyze_tool.py`
- Test (new): `the_door/tests/unit/mcp/tools/test_analyze_tool_context_mode.py`

---

## Steps

### Step 1 — Inspect current analyze_tool structure

- [ ] **Step 1: Read current analyze_tool.py**

Open `the_door/src/the_door/mcp/tools/analyze_tool.py` and locate:
- `TOOL_SCHEMA` (or equivalent input schema dict)
- Handler function（接收解析後的 input，建立 orchestrator 並執行）

Record handler function signature and the orchestrator-construction call site. This informs Step 4.

### Step 2 — Write failing tests

- [ ] **Step 2: Create test file**

Create `the_door/tests/unit/mcp/tools/test_analyze_tool_context_mode.py`:

```python
"""Tests for context_mode parameter in analyze_tool MCP surface."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from the_door.mcp.tools import analyze_tool


class TestToolSchema:
    def test_schema_declares_context_mode_property(self):
        schema = analyze_tool.TOOL_SCHEMA
        props = schema.get("properties", {})
        assert "context_mode" in props

    def test_context_mode_enum_is_detail_or_minimal(self):
        props = analyze_tool.TOOL_SCHEMA["properties"]
        ctx = props["context_mode"]
        assert ctx.get("type") == "string"
        assert sorted(ctx.get("enum", [])) == ["detail", "minimal"]

    def test_context_mode_default_is_detail(self):
        props = analyze_tool.TOOL_SCHEMA["properties"]
        assert props["context_mode"].get("default") == "detail"

    def test_context_mode_not_in_required(self):
        """Optional — old callers without the field should still work."""
        schema = analyze_tool.TOOL_SCHEMA
        required = schema.get("required", [])
        assert "context_mode" not in required


class TestHandlerForwarding:
    def test_handler_passes_context_mode_to_orchestrator(self):
        with patch("the_door.mcp.tools.analyze_tool.PipelineOrchestrator") as MockOrch:
            instance = MockOrch.return_value
            instance.run = MagicMock(return_value={"ok": True})
            analyze_tool.handle({
                "codebase_path": "./fixture",
                "context_mode": "minimal",
            })
            kwargs = MockOrch.call_args.kwargs
            assert kwargs.get("context_mode") == "minimal"

    def test_handler_defaults_to_detail_when_absent(self):
        with patch("the_door.mcp.tools.analyze_tool.PipelineOrchestrator") as MockOrch:
            instance = MockOrch.return_value
            instance.run = MagicMock(return_value={"ok": True})
            analyze_tool.handle({
                "codebase_path": "./fixture",
            })
            kwargs = MockOrch.call_args.kwargs
            assert kwargs.get("context_mode") == "detail"

    def test_handler_rejects_invalid_context_mode(self):
        with pytest.raises((ValueError, Exception)):
            analyze_tool.handle({
                "codebase_path": "./fixture",
                "context_mode": "weird",
            })
```

> **Note**: 上述測試假設 handler 名為 `handle(input_dict)`。實際 codebase 可能用 `run(...)` 或 `__call__(...)`；以實際介面對齊測試。

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest the_door/tests/unit/mcp/tools/test_analyze_tool_context_mode.py -v`
Expected: FAIL — schema 欠 context_mode 欄位、handler 未轉發。

### Step 3 — Implement schema + handler changes

- [ ] **Step 4: Add context_mode to TOOL_SCHEMA**

Open `the_door/src/the_door/mcp/tools/analyze_tool.py`. Locate `TOOL_SCHEMA` dict and add to `"properties"`:

```python
TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        # ... existing properties ...
        "context_mode": {
            "type": "string",
            "enum": ["detail", "minimal"],
            "default": "detail",
            "description": (
                "LLM 接收節點資訊的詳細度。"
                "'detail'（預設）：送節點完整 signature/docstring/decorators，"
                "翻譯品質較高。"
                "'minimal'：只送 node_id 字串，token 用量低但翻譯品質會回到 v1.3.6 前的水準。"
            ),
        },
    },
    # context_mode 不加進 required；舊 caller 自動 default detail
    "required": [  # 既有 required 不變
        # ...
    ],
}
```

- [ ] **Step 5: Update handler to read & forward context_mode**

In the handler function (e.g. `handle(input_dict)`):

```python
def handle(input_dict):
    # ... existing validation / param extraction ...

    context_mode = input_dict.get("context_mode", "detail")
    if context_mode not in ("detail", "minimal"):
        raise ValueError(
            f"context_mode must be 'detail' or 'minimal', got {context_mode!r}"
        )

    orchestrator = PipelineOrchestrator(
        # ... existing kwargs ...
        context_mode=context_mode,
    )
    return orchestrator.run(...)
```

> **Important**: 即使 orchestrator 自己也驗證 context_mode，handler 在 MCP 邊界做 explicit 驗證有兩個價值：(1) 錯誤訊息對 MCP caller 更直接；(2) schema 驗證失靈時仍能擋住非法值。**不要把驗證委派給 orchestrator 而省略此處**。

- [ ] **Step 6: Run tests**

Run: `pytest the_door/tests/unit/mcp/tools/test_analyze_tool_context_mode.py -v`
Expected: ALL PASS.

如某 mock patch 路徑不正確（`PipelineOrchestrator` 在 analyze_tool.py 內可能是 `from ... import as` 不同 path），就地修正 patch target。

- [ ] **Step 7: Coverage check**

Run: `pytest the_door/tests/unit/mcp/tools/ --cov=the_door.mcp.tools.analyze_tool --cov-report=term-missing`
Expected: 本任務修改範圍 100% line coverage（含 `context_mode = input_dict.get(...)` 與驗證 raise 路徑）。

- [ ] **Step 8: Verify extract_structure unchanged**

Run: `git diff the_door/src/the_door/mcp/tools/extract_structure_tool.py`
Expected: 無變動（spec §5.3 規定）。

如該檔不存在或叫不同名字，跳過此步。

- [ ] **Step 9: Full regression**

Run: `pytest the_door/tests/ -x -q`
Expected: 無新 failure。

- [ ] **Step 10: Manual MCP smoke test (optional but recommended)**

啟動 MCP server（背景）：
```
the-door mcp-serve &
```

用 MCP client 或 curl 送一個 `tools/call analyze_tool` 請求，帶 `"context_mode": "minimal"`，確認被接受。完成後 `kill %1` 終止 background server。

> 此步無 CI 替代，純人工驗證。若環境無法跑 MCP server，可跳過。

- [ ] **Step 11: Commit**

```bash
git add the_door/src/the_door/mcp/tools/analyze_tool.py the_door/tests/unit/mcp/tools/test_analyze_tool_context_mode.py
git commit -m "feat(mcp): analyze_tool accepts optional context_mode input

Default 'detail' for new richer-context behavior; 'minimal' opts out to
node_id-only legacy mode. Schema-level enum validation + explicit handler
validation at the MCP boundary. extract_structure tool unaffected
(it does not invoke LLM)."
```

---

## Acceptance Criteria

- [ ] `analyze_tool.TOOL_SCHEMA.properties.context_mode` 存在
- [ ] enum 為 `["detail", "minimal"]`
- [ ] default 為 `"detail"`
- [ ] 不在 `required` 清單（向後相容）
- [ ] Handler 在 input dict 缺 `context_mode` 時用 `"detail"`
- [ ] Handler 收到非法 `context_mode` 值時 raise（不靜默通過給 orchestrator）
- [ ] Handler 把 `context_mode` 傳給 `PipelineOrchestrator` 建構式
- [ ] `extract_structure` MCP tool 未變動
- [ ] 本任務修改範圍 100% line coverage
- [ ] `pytest the_door/tests/` 無新增 failure
