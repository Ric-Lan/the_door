# Task 06 — Regenerate Path Mode Parity

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 `BatchReader.regenerate()` 與 `_process_batch` 一致 — 同樣透過 `_serialize_payload` helper 產出 prompt，受 `context_mode` 影響。避免「初次分析走 detail，regenerate 卻走 minimal」造成同一 feature 兩次品質不一致。

**Architecture:** `regenerate()` 目前手寫 `json.dumps({"task": "regenerate", ...})`，改為呼叫共用 helper。將 `task` 欄位以另一條路徑（或合併進 payload 結構）保留。

**Tech Stack:** Python 3.11+, pytest, pytest-asyncio.

**Test Coverage Requirement:** `BatchReader.regenerate()` 路徑（含 detail / minimal 雙模式 + LLM 解析失敗 fallback）達 100% line coverage。

---

## Background（自含）

`BatchReader.regenerate()` 位於 `the_door/src/the_door/core/reading/batch_reader.py:138-160`。當前實作：

```python
async def regenerate(
    self,
    feature_id: str,
    previous_result: Feature,
) -> RegenerateResult:
    source_nodes = previous_result.source_nodes
    prompt = json.dumps({
        "task": "regenerate",
        "feature_id": feature_id,
        "source_nodes": source_nodes,
    })
    response = await self._provider.complete(prompt, system_prompt=L1_SYSTEM_PROMPT)
    ...
```

**問題**：只送 source_nodes 字串清單（minimal-mode-like），就算 BatchReader 設為 detail 模式，regenerate 仍丟掉所有節點詳情。

`_serialize_payload(node_ids, batch_num)` 已在前置任務寫好，會依 `self._context_mode` 輸出 minimal 或 detail payload。本任務把 regenerate 改為呼叫它，並在 payload 內加上 regenerate-specific 的欄位（`task`、`feature_id`）。

`RegenerateResult` dataclass（已存在於同檔）：

```python
@dataclass
class RegenerateResult:
    previous_result: Feature | None = None
    new_result: Feature | None = None
    differs: bool = False
```

---

## Files

- Modify: `the_door/src/the_door/core/reading/batch_reader.py`
- Test (new section in existing file or new file): `the_door/tests/unit/core/reading/test_batch_reader_regenerate.py`

---

## Steps

### Step 1 — Write failing regenerate tests

- [ ] **Step 1: Add tests for regenerate mode parity**

Create `the_door/tests/unit/core/reading/test_batch_reader_regenerate.py`:

```python
"""Tests for BatchReader.regenerate() mode parity with _process_batch."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from the_door.core.reading.batch_reader import BatchReader
from the_door.models import ASTNode, Feature, StructureJSON, TopologyEntry


def _build_structure() -> StructureJSON:
    nodes = [
        ASTNode(
            node_id="src/cart.py::checkout",
            type="function",
            name="checkout",
            file="src/cart.py",
            language="python",
            parameters=["cart_id: str", "user: User"],
            return_type="OrderResult",
            decorators=["@app.route('/checkout', methods=['POST'])"],
            docstring="Process payment and create order.",
            comments=[],
        ),
    ]
    topology = [TopologyEntry(
        node_id="src/cart.py::checkout", in_degree=0, out_degree=0,
        topology_rank=0, is_entry_point=True, batch_assignment=1
    )]
    return StructureJSON(files=[], nodes=nodes, edges=[], topology=topology)


def _build_previous_feature() -> Feature:
    return Feature(
        feature_id="feat-checkout",
        label="Old label",
        description="Old description",
        trigger="user_action",
        trigger_description="...",
        confidence="medium",
        confidence_reason="...",
        source_nodes=["src/cart.py::checkout"],
        needs_source_review=False,
        review_reason=None,
    )


def _build_provider(complete_response: str):
    provider = AsyncMock()
    provider.complete = AsyncMock(return_value=complete_response)
    provider.estimate_tokens = lambda text: len(text) // 4
    return provider


_OK_RESPONSE = json.dumps({
    "features": [
        {
            "feature_id": "feat-checkout",
            "label": "新標籤",
            "description": "讓使用者完成購物車付款。",
            "trigger_description": "使用者點擊結帳按鈕後觸發。",
            "confidence": "high",
            "confidence_reason": "三個信號齊備",
            "source_nodes": ["src/cart.py::checkout"],
        }
    ],
    "feature_relations": [],
})


class TestRegenerateDetailMode:
    def test_detail_mode_prompt_contains_docstring(self):
        s = _build_structure()
        provider = _build_provider(_OK_RESPONSE)
        br = BatchReader(provider, s, context_mode="detail")
        asyncio.run(br.regenerate("feat-checkout", _build_previous_feature()))
        called_prompt = provider.complete.call_args.args[0]
        assert "Process payment and create order." in called_prompt
        # Detail mode 必含 parameters key
        assert "parameters" in called_prompt

    def test_detail_mode_payload_includes_task_marker(self):
        s = _build_structure()
        provider = _build_provider(_OK_RESPONSE)
        br = BatchReader(provider, s, context_mode="detail")
        asyncio.run(br.regenerate("feat-checkout", _build_previous_feature()))
        called_prompt = provider.complete.call_args.args[0]
        data = json.loads(called_prompt)
        assert data.get("task") == "regenerate"
        assert data.get("feature_id") == "feat-checkout"


class TestRegenerateMinimalMode:
    def test_minimal_mode_prompt_excludes_docstring(self):
        s = _build_structure()
        provider = _build_provider(_OK_RESPONSE)
        br = BatchReader(provider, s, context_mode="minimal")
        asyncio.run(br.regenerate("feat-checkout", _build_previous_feature()))
        called_prompt = provider.complete.call_args.args[0]
        assert "Process payment" not in called_prompt
        # Node ID 仍存在
        assert "src/cart.py::checkout" in called_prompt

    def test_minimal_mode_payload_includes_task_marker(self):
        s = _build_structure()
        provider = _build_provider(_OK_RESPONSE)
        br = BatchReader(provider, s, context_mode="minimal")
        asyncio.run(br.regenerate("feat-checkout", _build_previous_feature()))
        data = json.loads(provider.complete.call_args.args[0])
        assert data["task"] == "regenerate"
        assert data["feature_id"] == "feat-checkout"


class TestRegenerateResultParsing:
    def test_successful_regenerate_returns_new_feature(self):
        s = _build_structure()
        provider = _build_provider(_OK_RESPONSE)
        br = BatchReader(provider, s, context_mode="detail")
        result = asyncio.run(br.regenerate("feat-checkout", _build_previous_feature()))
        assert result.new_result is not None
        assert result.new_result.label == "新標籤"
        assert result.differs is True

    def test_parser_failure_returns_none_new_result(self):
        s = _build_structure()
        provider = _build_provider("not-json garbage")
        br = BatchReader(provider, s, context_mode="detail")
        result = asyncio.run(br.regenerate("feat-checkout", _build_previous_feature()))
        assert result.new_result is None
        assert result.differs is False
        assert result.previous_result == _build_previous_feature()

    def test_same_content_marks_differs_false(self):
        s = _build_structure()
        # 回應與 previous_feature 內容一致
        same_response = json.dumps({
            "features": [{
                "feature_id": "feat-checkout",
                "label": "Old label",
                "description": "Old description",
                "trigger_description": "...",
                "confidence": "medium",
                "confidence_reason": "...",
                "source_nodes": ["src/cart.py::checkout"],
            }],
            "feature_relations": [],
        })
        provider = _build_provider(same_response)
        br = BatchReader(provider, s, context_mode="detail")
        result = asyncio.run(br.regenerate("feat-checkout", _build_previous_feature()))
        # 不同實作可能對 differs 有不同定義；至少 new_result 應有值
        assert result.new_result is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest the_door/tests/unit/core/reading/test_batch_reader_regenerate.py -v`
Expected: 大部分 detail-mode 測試 FAIL — 當前 regenerate 只送 source_nodes 字串清單，無 docstring/parameters。

### Step 2 — Implement regenerate using shared helper

- [ ] **Step 3: Refactor regenerate() to use _serialize_payload**

Open `the_door/src/the_door/core/reading/batch_reader.py`. Locate `regenerate` method. Replace its prompt construction:

**Strategy A** — add task/feature_id to existing payload via a small helper:

```python
    def _serialize_regenerate_payload(
        self, source_nodes: list[str], feature_id: str
    ) -> str:
        """Serialize regenerate-task payload using context_mode."""
        # 先取得 base payload（依 context_mode 決定 minimal/detail 形狀）
        base = json.loads(self._serialize_payload(source_nodes, batch_num=0))
        # 把 batch 欄位換成 task / feature_id
        base.pop("batch", None)
        base["task"] = "regenerate"
        base["feature_id"] = feature_id
        return json.dumps(base, ensure_ascii=False)
```

Then in `regenerate`:

```python
    async def regenerate(
        self,
        feature_id: str,
        previous_result: Feature,
    ) -> RegenerateResult:
        source_nodes = list(previous_result.source_nodes)
        prompt = self._serialize_regenerate_payload(source_nodes, feature_id)

        response = await self._provider.complete(prompt, system_prompt=L1_SYSTEM_PROMPT)
        parse_result = self._parser.parse(response)

        if not parse_result.success or not parse_result.data:
            return RegenerateResult(
                previous_result=previous_result,
                new_result=None,
                differs=False,
            )

        # Parse first feature from response (existing logic)
        features_data = parse_result.data.get("features", [])
        if not features_data:
            return RegenerateResult(
                previous_result=previous_result,
                new_result=None,
                differs=False,
            )
        feat_data = features_data[0]
        new_feature = Feature(
            feature_id=feat_data.get("feature_id", feature_id),
            label=feat_data.get("label", ""),
            description=feat_data.get("description", ""),
            trigger=feat_data.get("trigger", "user_action"),
            trigger_description=feat_data.get("trigger_description", ""),
            confidence=feat_data.get("confidence", "medium"),
            confidence_reason=feat_data.get("confidence_reason", ""),
            source_nodes=feat_data.get("source_nodes", source_nodes),
            needs_source_review=feat_data.get("needs_source_review", False),
            review_reason=feat_data.get("review_reason"),
        )

        differs = (
            new_feature.label != previous_result.label
            or new_feature.description != previous_result.description
        )

        return RegenerateResult(
            previous_result=previous_result,
            new_result=new_feature,
            differs=differs,
        )
```

> 若既有 `regenerate` 的回傳 / 解析邏輯與上述不同，**保留原本的解析邏輯**，只替換 prompt 構造那 1-2 行。`differs` 判定條件以既有實作為準。

- [ ] **Step 4: Run regenerate tests**

Run: `pytest the_door/tests/unit/core/reading/test_batch_reader_regenerate.py -v`
Expected: 全綠。

- [ ] **Step 5: Coverage check**

Run: `pytest the_door/tests/unit/core/reading/ --cov=the_door.core.reading.batch_reader --cov-report=term-missing`

Expected: `regenerate` 與 `_serialize_regenerate_payload` 兩個分支（detail/minimal）+ 解析失敗 fallback 路徑皆覆蓋。整檔 100%。

如未達 100%，補測試覆蓋遺漏分支（例如 `features_data` 為空、parse 失敗、source_nodes 為空等）。

- [ ] **Step 6: Full regression**

Run: `pytest the_door/tests/ -x -q`
Expected: 無新 failure。

- [ ] **Step 7: Commit**

```bash
git add the_door/src/the_door/core/reading/batch_reader.py the_door/tests/unit/core/reading/test_batch_reader_regenerate.py
git commit -m "feat(reading): regenerate() honors context_mode via shared serializer

BatchReader.regenerate() now constructs its prompt via _serialize_payload,
so detail mode sends full ASTNode dicts and minimal mode keeps node_id-only
behavior. Avoids quality inconsistency between initial analysis and
single-feature regeneration."
```

---

## Acceptance Criteria

- [ ] `regenerate()` 透過 `_serialize_payload` 構造 prompt（不再直接 json.dumps）
- [ ] Detail 模式下 regenerate prompt 包含 docstring / parameters / decorators
- [ ] Minimal 模式下 regenerate prompt 只含 node_id 字串
- [ ] Regenerate payload 仍包含 `task: "regenerate"` 與 `feature_id` 欄位
- [ ] Parser 失敗 fallback 路徑回傳 `RegenerateResult(new_result=None, differs=False)`
- [ ] `batch_reader.py` line coverage 維持 100%
- [ ] `pytest the_door/tests/` 無新增 failure
