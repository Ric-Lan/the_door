# Task 08 — MCP `analyze_tool` `context_mode` Input

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `analyze_tool` MCP tool 的 input schema 新增 optional `context_mode` 欄位，enum `["detail", "minimal"]`，預設 `"detail"`。把該值直接傳給 `BatchReader` 建構子。`extract_structure` MCP tool **不受影響**（它不呼叫 LLM）。

**Architecture:** `analyze_tool.py` 在 line 51 直接建構 `BatchReader(llm_provider=..., structure=...)` — 不經 `PipelineOrchestrator`。本任務在該處讀取輸入字典的 `context_mode` 並作為 kwarg 傳入。沒指定 = `"detail"`，向後相容。

**Tech Stack:** Python 3.11+, jsonschema-style input schema, pytest, pytest-asyncio.

**Test Coverage Requirement:** `analyze_tool.py` 中本任務修改的範圍達 100% line coverage（含 schema 驗證、預設值、無效值拒絕、轉發路徑）。

---

## Background（自含）

`analyze_tool` MCP tool 位於 `the_door/src/the_door/mcp/tools/analyze_tool.py`。實際程式碼（前置 grep 驗證）：

```python
# analyze_tool.py:51
reader = BatchReader(llm_provider=llm_provider, structure=structure)
```

**重要事實**：analyze_tool **沒有**透過 `PipelineOrchestrator` 建構 `BatchReader` — 它直接 `import BatchReader` 並 instantiate。因此測試應 patch 的對象是 `BatchReader`（在 analyze_tool 模組命名空間內），不是 `PipelineOrchestrator`。

`BatchReader` 已在前置任務支援 `context_mode: Literal["detail", "minimal"]`，預設 `"detail"`，非法值在 `__init__` raise `ValueError`。

MCP tool 通常有：
- `TOOL_SCHEMA`（或類似命名）：jsonschema 風格 input shape
- handler 函式（例如 `handle(input_dict)`、`run(...)` 或 module-level function）

**spec §5.3 明確規定**：`extract_structure` MCP tool **不受本任務影響** — 它只做結構抽取，不呼叫 LLM。

---

## Files

- Modify: `the_door/src/the_door/mcp/tools/analyze_tool.py`
- Test (new): `the_door/tests/unit/mcp/tools/test_analyze_tool_context_mode.py`

---

## Steps

### Step 1 — Inspect current analyze_tool structure

- [ ] **Step 1: Read current analyze_tool.py**

Run: `grep -n "^def \|^class \|TOOL_SCHEMA\|BatchReader" the_door/src/the_door/mcp/tools/analyze_tool.py`

Record:
1. Module-level constants (e.g. `TOOL_SCHEMA` or alternative name)
2. Handler function name (e.g. `handle`, `run`, `analyze`, `__call__`)
3. BatchReader construction call site (already confirmed at line 51 area)

調整 Step 2 / Step 4 的測試 patch path 與 handler 呼叫名為實際名稱。

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


def _stub_extraction_dependencies(monkeypatch):
    """讓 handler 能跑到 BatchReader 建構點而不需真實 LLM / extraction。"""
    monkeypatch.setattr(
        analyze_tool, "ASTExtractor",
        lambda: MagicMock(extract=MagicMock(return_value=MagicMock(
            files=[], nodes=[], edges=[],
        ))),
        raising=False,
    )
    # 視 analyze_tool 實際 import 名稱微調以下 names
    monkeypatch.setattr(
        analyze_tool, "create_provider",
        lambda *a, **kw: MagicMock(),
        raising=False,
    )


class TestHandlerForwardsToBatchReader:
    def test_handler_passes_minimal_when_input_says_minimal(self, monkeypatch):
        _stub_extraction_dependencies(monkeypatch)
        # Patch BatchReader 在 analyze_tool 命名空間
        with patch.object(analyze_tool, "BatchReader") as MockBR:
            mock_reader = MockBR.return_value
            mock_reader.read = MagicMock(return_value=MagicMock(
                l1_output=MagicMock(features=[], feature_relations=[],
                                    unclassified_nodes=[], infrastructure_nodes=[]),
            ))
            analyze_tool.handle({
                "codebase_path": "./fixture",
                "context_mode": "minimal",
            })
            assert MockBR.call_args.kwargs.get("context_mode") == "minimal"

    def test_handler_defaults_to_detail_when_field_absent(self, monkeypatch):
        _stub_extraction_dependencies(monkeypatch)
        with patch.object(analyze_tool, "BatchReader") as MockBR:
            mock_reader = MockBR.return_value
            mock_reader.read = MagicMock(return_value=MagicMock(
                l1_output=MagicMock(features=[], feature_relations=[],
                                    unclassified_nodes=[], infrastructure_nodes=[]),
            ))
            analyze_tool.handle({"codebase_path": "./fixture"})
            assert MockBR.call_args.kwargs.get("context_mode") == "detail"

    def test_handler_rejects_invalid_context_mode(self, monkeypatch):
        _stub_extraction_dependencies(monkeypatch)
        with pytest.raises((ValueError, Exception)):
            analyze_tool.handle({
                "codebase_path": "./fixture",
                "context_mode": "weird",
            })
```

> **注意**：上述測試假設 handler 名為 `handle(input_dict)`。Step 1 確認實際名後對齊。`_stub_extraction_dependencies` 中的 attribute name（`ASTExtractor`、`create_provider`）也以 analyze_tool 實際 import 命名為準；若該函式 lazy-import，需相應改變 patch path。

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest the_door/tests/unit/mcp/tools/test_analyze_tool_context_mode.py -v`
Expected: FAIL — schema 缺欄位、handler 未轉發。

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
    "required": [  # 既有 required 不變，不加 context_mode
        # ...
    ],
}
```

- [ ] **Step 5: Update handler to read & forward context_mode to BatchReader**

In the handler function（從 Step 1 確認的實際名）找到 BatchReader 建構點 (~line 51)。改為：

```python
def handle(input_dict):
    # ... existing input parsing / setup ...

    context_mode = input_dict.get("context_mode", "detail")
    if context_mode not in ("detail", "minimal"):
        raise ValueError(
            f"context_mode must be 'detail' or 'minimal', got {context_mode!r}"
        )

    # ... existing extraction / structure build ...

    reader = BatchReader(
        llm_provider=llm_provider,
        structure=structure,
        context_mode=context_mode,
    )
    # ... existing reader.read() call ...
```

> **Why explicit validation here**：即使 `BatchReader.__init__` 也驗證 context_mode，在 MCP 邊界做 explicit check 給 caller 更直接的錯誤訊息，並在 schema 驗證失靈時擋住非法值。違反 DRY 但安全性與可診斷性的權衡接受。

- [ ] **Step 6: Run tests**

Run: `pytest the_door/tests/unit/mcp/tools/test_analyze_tool_context_mode.py -v`
Expected: ALL PASS.

如某些 mock patch path 不正確（例如 `create_provider` 在 analyze_tool 內以不同名稱 import），就地修正 patch path（不改實作）。

- [ ] **Step 7: Coverage check**

Run: `pytest the_door/tests/unit/mcp/tools/ --cov=the_door.mcp.tools.analyze_tool --cov-report=term-missing`
Expected: 本任務修改範圍 100% line coverage（含 `context_mode = input_dict.get(...)` 與驗證 raise 路徑）。

- [ ] **Step 8: Verify extract_structure unchanged**

Run: `git diff the_door/src/the_door/mcp/tools/extract_structure_tool.py 2>/dev/null`（如該檔不存在 git diff 會無輸出，跳過此步）
Expected: 無變動。

- [ ] **Step 9: Full regression**

Run: `pytest the_door/tests/ -x -q`
Expected: 無新 failure。

- [ ] **Step 10: Manual MCP smoke test (optional)**

啟動 MCP server（背景）：
```bash
the-door mcp-serve &
```

用 MCP client 或 curl 送一個 `tools/call analyze_tool` 請求，帶 `"context_mode": "minimal"`，確認接受。完成後 `kill %1` 終止 background server。

> 純人工驗證。若環境無法跑 MCP server，可跳過。

- [ ] **Step 11: Commit**

```bash
git add the_door/src/the_door/mcp/tools/analyze_tool.py the_door/tests/unit/mcp/tools/test_analyze_tool_context_mode.py
git commit -m "feat(mcp): analyze_tool accepts optional context_mode input

Default 'detail' for new richer-context behavior; 'minimal' opts out to
node_id-only legacy mode. Forwarded directly to BatchReader (analyze_tool
does not use PipelineOrchestrator). Schema-level enum + explicit handler
validation at MCP boundary. extract_structure tool unaffected."
```

---

## Acceptance Criteria

- [ ] `analyze_tool.TOOL_SCHEMA.properties.context_mode` 存在
- [ ] enum = `["detail", "minimal"]`
- [ ] default = `"detail"`
- [ ] 不在 `required` 清單（向後相容）
- [ ] Handler 在 input dict 缺 `context_mode` 時用 `"detail"`
- [ ] Handler 收到非法 `context_mode` 值時 raise（不靜默通過給 BatchReader）
- [ ] Handler 把 `context_mode` 作為 kwarg 傳給 `BatchReader(...)` 建構子
- [ ] **未引入** `PipelineOrchestrator` mock / patch — 因為 analyze_tool 不經 orchestrator
- [ ] `extract_structure` MCP tool 未變動
- [ ] 本任務修改範圍 100% line coverage
- [ ] `pytest the_door/tests/` 無新增 failure
