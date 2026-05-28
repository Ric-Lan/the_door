# Task 04 — Serialize Payload Helper + BatchReader Context Modes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `BatchReader` 引入 `context_mode: Literal["detail", "minimal"]` 參數，預設 `"detail"`。新增單一 `_serialize_payload(nodes, batch_num, context_mode) -> str` helper，由 `_process_batch` 與 `_maybe_split` 共同使用，杜絕雙重序列化。

**Architecture:**
- `BatchReader.__init__` 接受 `context_mode`，預設 `"detail"`
- 新增 instance method `_serialize_payload`：依模式輸出 JSON 字串（minimal: node_ids 列表；detail: 完整 ASTNode dict 列表）
- `_process_batch` 改呼叫 `_serialize_payload` 取得 prompt JSON
- `_maybe_split` 改接 `context_mode` 並透過 `_serialize_payload` 估算實際 payload token 數

**Tech Stack:** Python 3.11+, dataclasses, json, pytest, pytest-asyncio。

**Test Coverage Requirement:** `batch_reader.py` 中 `_serialize_payload`、`_process_batch`、`_maybe_split` 三條路徑（含 detail / minimal 雙分支）達 100% line coverage。pytest 加 `--cov=the_door.core.reading.batch_reader --cov-fail-under=100`。

---

## Background（自含）

`BatchReader` 在 `the_door/src/the_door/core/reading/batch_reader.py` 把 AST 節點透過 LLM 轉成 L1 features。當前 `_process_batch` 只送 node_id 字串清單（[第 256-259 行]）：

```python
prompt = json.dumps({
    "batch": batch_num,
    "nodes": node_ids,
})
```

`ASTNode` (定義於 `the_door/src/the_door/models.py:19-31`) 有完整內容欄位（parameters / return_type / decorators / docstring / comments / file / language / type / name / node_id），但全部被丟掉。

`StructureJSON`（`models.py` 中定義）持有 `nodes: list[ASTNode]`，在 `BatchReader.__init__` 已透過 `self._structure = structure` 持有。

`_maybe_split`（第 226-248 行）目前用 `json.dumps(node_ids)` 估算 payload 大小 — 在 detail 模式下會嚴重低估，導致大批次未被切開、LLM 收到超出 context window 的請求。

**spec §6.2 強制要求**：序列化邏輯收斂為單一共用 helper，避免雙重 json.dumps。本任務實作這個 helper。

**spec §4.1 / §4.2 的 prompt 規則更新**由獨立任務處理，**不在本任務範圍**。本任務只動 BatchReader 的序列化與 mode 切換。

---

## Files

- Modify: `the_door/src/the_door/core/reading/batch_reader.py`
- Modify: `the_door/tests/unit/core/reading/test_batch_reader.py`（既有測試補 `context_mode="minimal"`）
- Test (new section in existing or new file): `the_door/tests/unit/core/reading/test_batch_reader_context_modes.py`

---

## Steps

### Step 1 — Audit existing test surface

- [ ] **Step 1: List existing prompt-shape assertions**

Run: `grep -n "json.dumps\|\"nodes\"\|prompt =" the_door/tests/unit/core/reading/test_batch_reader.py`

Record the list — these test cases will need `context_mode="minimal"` to remain green. Do not change them yet.

### Step 2 — Write failing tests for new behavior

- [ ] **Step 2: Create new test file for context modes**

Create `the_door/tests/unit/core/reading/test_batch_reader_context_modes.py`:

```python
"""Tests for BatchReader context_mode (detail / minimal)."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from the_door.core.reading.batch_reader import BatchReader
from the_door.models import ASTNode, StructureJSON, TopologyEntry


def _build_structure() -> StructureJSON:
    nodes = [
        ASTNode(
            node_id="src/foo.py::greet",
            type="function",
            name="greet",
            file="src/foo.py",
            language="python",
            parameters=["name: str", "times: int = 1"],
            return_type="str",
            decorators=["@app.route('/hello', methods=['GET'])"],
            docstring="Greet someone by name.",
            comments=[],
        ),
        ASTNode(
            node_id="src/foo.py::farewell",
            type="function",
            name="farewell",
            file="src/foo.py",
            language="python",
            parameters=["name: str"],
            return_type="str",
            decorators=[],
            docstring=None,
            comments=[],
        ),
    ]
    topology = [
        TopologyEntry(node_id="src/foo.py::greet", in_degree=0, out_degree=0,
                      topology_rank=0, is_entry_point=True, batch_assignment=1),
        TopologyEntry(node_id="src/foo.py::farewell", in_degree=0, out_degree=0,
                      topology_rank=0, is_entry_point=True, batch_assignment=1),
    ]
    return StructureJSON(files=[], nodes=nodes, edges=[], topology=topology)


def _build_provider(complete_response: str = '{"features":[]}'):
    provider = AsyncMock()
    provider.complete = AsyncMock(return_value=complete_response)
    provider.estimate_tokens = lambda text: len(text) // 4
    return provider


class TestSerializePayloadModeBranching:
    def test_minimal_mode_outputs_node_ids_list(self):
        s = _build_structure()
        br = BatchReader(_build_provider(), s, context_mode="minimal")
        payload = br._serialize_payload(
            ["src/foo.py::greet", "src/foo.py::farewell"],
            batch_num=1,
        )
        data = json.loads(payload)
        assert data["batch"] == 1
        assert data["context_mode"] == "minimal"
        assert data["nodes"] == ["src/foo.py::greet", "src/foo.py::farewell"]

    def test_detail_mode_outputs_full_ast_node_dicts(self):
        s = _build_structure()
        br = BatchReader(_build_provider(), s, context_mode="detail")
        payload = br._serialize_payload(["src/foo.py::greet"], batch_num=2)
        data = json.loads(payload)
        assert data["batch"] == 2
        assert data["context_mode"] == "detail"
        assert len(data["nodes"]) == 1
        node = data["nodes"][0]
        assert node["node_id"] == "src/foo.py::greet"
        assert node["name"] == "greet"
        assert node["parameters"] == ["name: str", "times: int = 1"]
        assert node["return_type"] == "str"
        assert "app.route" in node["decorators"][0]
        assert node["docstring"] == "Greet someone by name."
        assert node["comments"] == []
        assert node["file"] == "src/foo.py"
        assert node["language"] == "python"
        assert node["type"] == "function"

    def test_detail_mode_skips_unknown_node_id(self):
        s = _build_structure()
        br = BatchReader(_build_provider(), s, context_mode="detail")
        # 未知 node_id 應靜默忽略，不 crash
        payload = br._serialize_payload(["src/foo.py::greet", "missing::id"], batch_num=1)
        data = json.loads(payload)
        node_ids = [n["node_id"] for n in data["nodes"]]
        assert node_ids == ["src/foo.py::greet"]


class TestBatchReaderDefaultMode:
    def test_default_context_mode_is_detail(self):
        s = _build_structure()
        br = BatchReader(_build_provider(), s)
        assert br._context_mode == "detail"

    def test_invalid_context_mode_raises(self):
        s = _build_structure()
        with pytest.raises(ValueError):
            BatchReader(_build_provider(), s, context_mode="weird")


class TestProcessBatchUsesSerializeHelper:
    def test_detail_mode_prompt_contains_docstring(self):
        s = _build_structure()
        provider = _build_provider('{"features":[]}')
        br = BatchReader(provider, s, context_mode="detail")
        asyncio.run(br._process_batch(["src/foo.py::greet"], batch_num=1))
        # Assert provider.complete was called with detail-mode payload
        called_prompt = provider.complete.call_args.args[0]
        assert "Greet someone by name." in called_prompt

    def test_minimal_mode_prompt_does_not_contain_docstring(self):
        s = _build_structure()
        provider = _build_provider('{"features":[]}')
        br = BatchReader(provider, s, context_mode="minimal")
        asyncio.run(br._process_batch(["src/foo.py::greet"], batch_num=1))
        called_prompt = provider.complete.call_args.args[0]
        assert "Greet someone by name." not in called_prompt
        # Minimal still includes the node_id
        assert "src/foo.py::greet" in called_prompt


class TestMaybeSplitUsesSerializedPayloadSize:
    def test_minimal_mode_small_payload_no_split(self):
        s = _build_structure()
        br = BatchReader(_build_provider(), s, context_mode="minimal", max_context_tokens=10_000)
        sub_batches = br._maybe_split(["src/foo.py::greet", "src/foo.py::farewell"])
        assert len(sub_batches) == 1

    def test_detail_mode_large_payload_triggers_split(self):
        # 給一個很小的 token budget，detail 模式應該切分
        s = _build_structure()
        br = BatchReader(_build_provider(), s, context_mode="detail", max_context_tokens=5)
        sub_batches = br._maybe_split(["src/foo.py::greet", "src/foo.py::farewell"])
        assert len(sub_batches) >= 2  # 被切開

    def test_maybe_split_respects_serialize_payload_output(self):
        """確保 _maybe_split 估算的是 _serialize_payload 實際輸出的大小，
        不是 node_ids 字串長度。"""
        s = _build_structure()
        br = BatchReader(_build_provider(), s, context_mode="detail", max_context_tokens=1000)
        # 比對 _maybe_split 推估用的字串是 _serialize_payload 結果
        serialized = br._serialize_payload(["src/foo.py::greet"], batch_num=1)
        assert "parameters" in serialized  # detail 模式必含 parameters key


class TestRegenerateNotInScope:
    """regenerate() 的 context_mode 適配在後續任務做，本任務不動。"""
    def test_placeholder(self):
        assert True
```

- [ ] **Step 3: Run new tests to verify they fail**

Run: `pytest the_door/tests/unit/core/reading/test_batch_reader_context_modes.py -v`
Expected: FAIL（`_serialize_payload` / `context_mode` 參數不存在）。

### Step 3 — Implement BatchReader changes

- [ ] **Step 4: Modify BatchReader class**

Open `the_door/src/the_door/core/reading/batch_reader.py`. Apply these changes:

**4a. Add `context_mode` param to `__init__`:**

```python
from typing import Literal

_VALID_CONTEXT_MODES = ("detail", "minimal")


class BatchReader:
    def __init__(
        self,
        llm_provider,
        structure: StructureJSON,
        *,
        max_context_tokens: int | None = None,
        context_mode: Literal["detail", "minimal"] = "detail",
    ) -> None:
        if context_mode not in _VALID_CONTEXT_MODES:
            raise ValueError(
                f"context_mode must be one of {_VALID_CONTEXT_MODES}, got {context_mode!r}"
            )
        self._provider = llm_provider
        self._structure = structure
        self._parser = ResponseParser()
        self._pruning = PruningEngine(structure.edges)
        self._max_context_tokens = max_context_tokens
        self._context_mode = context_mode
        # Build lookup for detail mode (avoid O(n) scan per serialize call)
        self._node_lookup: dict[str, ASTNode] = {n.node_id: n for n in structure.nodes}
```

> Add `from the_door.models import ASTNode` to the imports if not present.

**4b. Add `_build_payload` (dict) + `_serialize_payload` (str):**

```python
    def _build_payload(self, node_ids: list[str], batch_num: int) -> dict:
        """Build the prompt payload as a dict (pre-serialization form).

        Splitting build vs serialize means token accounting + regenerate path
        can reuse the dict without round-tripping through json.loads().
        """
        if self._context_mode == "minimal":
            return {
                "batch": batch_num,
                "context_mode": "minimal",
                "nodes": list(node_ids),
            }
        # "detail"
        node_dicts: list[dict] = []
        for nid in node_ids:
            node = self._node_lookup.get(nid)
            if node is None:
                # 未知 node_id：靜默跳過（與既有 minimal 行為一致 —
                # PruningEngine 與 batch_assignment 可能提供 unknown ID）
                continue
            node_dicts.append({
                "node_id": node.node_id,
                "type": node.type,
                "name": node.name,
                "file": node.file,
                "language": node.language,
                "parameters": list(node.parameters),
                "return_type": node.return_type,
                "decorators": list(node.decorators),
                "docstring": node.docstring,
                "comments": list(node.comments),
            })
        return {
            "batch": batch_num,
            "context_mode": "detail",
            "nodes": node_dicts,
        }

    def _serialize_payload(self, node_ids: list[str], batch_num: int) -> str:
        """Serialize the batch payload for LLM consumption.

        Output is the exact string passed to provider.complete(). Internally
        delegates to `_build_payload` so structure is defined in one place.
        """
        return json.dumps(self._build_payload(node_ids, batch_num), ensure_ascii=False)
```

**4c. Change `_process_batch` to use helper AND keep the serialized string for token reuse:**

Replace the current prompt assembly:

```python
# BEFORE:
prompt = json.dumps({
    "batch": batch_num,
    "nodes": node_ids,
})

# AFTER:
prompt = self._serialize_payload(node_ids, batch_num)
```

And modify `_process_batch` to **return** the prompt string alongside its existing return value so `read()` can do token accounting without re-serializing. Specifically, change the signature:

```python
async def _process_batch(
    self, node_ids: list[str], batch_num: int,
) -> tuple[list[Feature], list[FeatureRelation], list[str], list[str], str]:
    prompt = self._serialize_payload(node_ids, batch_num)
    response = await self._provider.complete(prompt, system_prompt=L1_SYSTEM_PROMPT)
    # ... existing parsing logic unchanged ...
    return features, relations, unclassified, infrastructure, prompt
```

Callers (only `read()`) destructure the extra tuple element.

**4d. Change `_maybe_split` to use helper for size estimation:**

Replace the `payload_text = json.dumps(node_ids)` line:

```python
# BEFORE:
payload_text = json.dumps(node_ids)
estimated_tokens = self._provider.estimate_tokens(payload_text)

# AFTER:
payload_text = self._serialize_payload(node_ids, batch_num=0)
estimated_tokens = self._provider.estimate_tokens(payload_text)
```

`batch_num=0` 是大小估算的 placeholder — `batch_num` 對 JSON 長度影響只有 1-3 bytes（單一整數欄位），可忽略；但仍走 `_serialize_payload` 確保 minimal/detail 兩模式的估算路徑一致。

> 此處接受 `_maybe_split` 中一次序列化（為了估算大小無可避免）。**該批次後續真正執行時 `_process_batch` 會再序列化一次** — 這 1 次重複不可消除，但避免了 spec 警告的「同批序列化多次」反模式：每批最多 2 次（split 估算 + 實送）。

**4e. Update the token accounting line in `read()`:**

Locate `total_tokens += self._provider.estimate_tokens(json.dumps([n for n in sub_nodes]))` and replace with code that uses the prompt string already returned from `_process_batch`:

```python
# BEFORE (in read() loop body):
features, relations, unclassified, infrastructure = await self._process_batch(sub_nodes, batch_num)
# ...
total_tokens += self._provider.estimate_tokens(json.dumps([n for n in sub_nodes]))

# AFTER:
features, relations, unclassified, infrastructure, prompt_str = await self._process_batch(sub_nodes, batch_num)
# ...
total_tokens += self._provider.estimate_tokens(prompt_str)
```

Token accounting now reflects the **exact** payload sent to LLM and **does not re-serialize**.

- [ ] **Step 5: Run new tests to verify they pass**

Run: `pytest the_door/tests/unit/core/reading/test_batch_reader_context_modes.py -v`
Expected: ALL PASS.

### Step 4 — Patch existing tests to keep them green

- [ ] **Step 6: Add context_mode="minimal" to existing prompt-shape tests**

For each existing test in `the_door/tests/unit/core/reading/test_batch_reader.py` that:
- Constructs `BatchReader(...)` AND
- Asserts the prompt JSON shape contains `"nodes": [list of strings]` (i.e., relies on minimal-mode behavior)

Add `context_mode="minimal"` to the `BatchReader(...)` constructor call.

Example diff:

```python
# BEFORE
br = BatchReader(provider, structure)

# AFTER
br = BatchReader(provider, structure, context_mode="minimal")
```

Tests that don't assert prompt shape can be left alone (they'll work fine with default detail mode).

- [ ] **Step 7: Run patched existing tests**

Run: `pytest the_door/tests/unit/core/reading/test_batch_reader.py -v`
Expected: 全綠。若某 test 仍失敗，找出該 test 依賴的具體 prompt shape 並決定：
- 該 test 應該維持 minimal 行為（補 `context_mode="minimal"`）
- 該 test 應該升級到驗證 detail 行為（改 assertion）

- [ ] **Step 8: Coverage check**

Run: `pytest the_door/tests/unit/core/reading/ --cov=the_door.core.reading.batch_reader --cov-report=term-missing`

Expected:
- `_serialize_payload` 兩個分支（minimal / detail）皆有覆蓋
- `_maybe_split` 在 detail 模式觸發切分有覆蓋
- `_process_batch` 兩個模式皆有覆蓋
- 整檔 line coverage = 100%

如未達 100%，補測試。

- [ ] **Step 9: Full regression**

Run: `pytest the_door/tests/ -x -q`
Expected: 無新 failure。

- [ ] **Step 10: Commit**

```bash
git add the_door/src/the_door/core/reading/batch_reader.py the_door/tests/unit/core/reading/
git commit -m "feat(reading): add context_mode + _serialize_payload helper to BatchReader

Detail mode (default) sends full ASTNode dicts to LLM; minimal mode keeps
node_id-only payload as opt-out fallback. Shared _serialize_payload helper
used by _process_batch, _maybe_split, and token accounting — eliminates
duplicate serialization and ensures split decisions match real prompt size.
Existing tests updated with explicit context_mode='minimal'."
```

---

## Acceptance Criteria

- [ ] `BatchReader.__init__` 接受 `context_mode` 參數，預設 `"detail"`
- [ ] 無效 `context_mode` 值在 `__init__` 即 raise `ValueError`
- [ ] `_serialize_payload` method 存在；minimal 模式輸出 node_id 字串列表；detail 模式輸出完整 ASTNode dict 列表
- [ ] `_process_batch` 透過 `_serialize_payload` 產 prompt（不再自行 json.dumps）
- [ ] `_maybe_split` 透過 `_serialize_payload` 估算 payload 大小
- [ ] `read()` 的 token 計數透過 `_serialize_payload` 取得
- [ ] 既有 batch_reader 測試以 `context_mode="minimal"` 標註全綠
- [ ] 新增 context_modes 測試全綠（含 detail / minimal 雙路徑、不明 node_id 處理、預設值、無效值）
- [ ] `batch_reader.py` line coverage = 100%
- [ ] `pytest the_door/tests/` 無新增 failure
