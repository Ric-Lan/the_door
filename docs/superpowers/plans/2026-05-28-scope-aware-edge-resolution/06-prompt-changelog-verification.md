# Task 06 — LLM Prompt Update, CHANGELOG, Dogfood Verification

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `L1_SYSTEM_PROMPT` 教 LLM 看 `resolution` 欄位以提升 description 品質、更新 CHANGELOG.md / README.md，並用 the_door 自身與 v105 test target 跑 dogfood 比對驗收 spec §7 各項指標。

**Architecture:** prompt 是純字串擴增、不破壞既有 schema。BatchReader 在送 LLM payload 時序列化 edge 必須包含 `resolution` 欄位（detail 模式下）。dogfood 比對是離線 script，不影響執行時行為。

**Pre-requisite:** Task 01–05 全部完成（schema、EdgeBuilder、7 語言 ScopeRules 全到位）。

**Tech Stack:** Python 3.11+, pytest, pytest-cov。

**Test Coverage Requirement:**

```
pytest the_door/tests/unit/core/llm/test_prompts_resolution.py the_door/tests/unit/core/reading/test_batch_reader_resolution.py -v \
  --cov=the_door.core.llm.prompts \
  --cov=the_door.core.reading.batch_reader \
  --cov-fail-under=100
```

**重要路徑修正：** BatchReader 實際位於 `the_door.core.reading.batch_reader`（**不是** `core/llm/`）。本任務測試與修改點全部對齊此路徑。

---

## Background（自含）

**目前 L1_SYSTEM_PROMPT 狀態（`the_door/src/the_door/core/llm/prompts.py:16`）：**

prompt 內容包含「任務 / 風格規則 / 範例 / 輸出格式」四段，**沒有**任何提及 edges 的 `resolution` 標籤。LLM 看到 edges 時無法區分高信心邊與裸名邊。

**目前 BatchReader payload 行為（grep 驗證後的事實）：**

- 模組路徑：`the_door.core.reading.batch_reader`（**不是** `core/llm/batch_reader.py`）
- `BatchReader._build_payload(node_ids, batch_num) → dict`（line 254-284）
- **detail mode payload 目前只含 `batch / context_mode / nodes`，完全沒有 `edges`**（見原始碼 line 280-284）
- minimal mode 同樣只有 nodes

**這代表 spec §4.5 的 prompt 教學若沒有「先把 edges 加進 detail payload」就完全失效**——LLM 根本看不到任何邊，談不上分辨 resolution。本任務必須：

1. 擴充 detail mode `_build_payload` → 加 `edges` 欄位（含 resolution，僅選取 from/to 都在當前 batch 的 node_ids 內的邊，避免 payload 爆掉）
2. 更新 prompt 教學 LLM 怎麼看這些 edges
3. minimal mode 保持原狀（minimal 連 nodes 細節都省，更不會放 edges）

**CHANGELOG / README 修改點：**

- `CHANGELOG.md` — 新增 v1.5.0 entry 描述 Scope-Aware Edge Resolution 功能
- `README.md` — 若有提及 edge resolution 或抽取行為的章節，補一行說明

**dogfood 驗收（spec §7.2 / §7.3）：**

| 指標 | 目標 |
|---|---|
| `scope_rule` + `import_alias` 邊佔比 | ≥ 50% |
| `name_match` 殘留邊佔比 | ≤ 40% |
| 總邊數 | 下降 10-30% |
| L1 description 違反風格規則條目數 | ≤ v1.4.0 |

---

## Files

- Modify: `the_door/src/the_door/core/llm/prompts.py`
- Modify: `the_door/src/the_door/core/reading/batch_reader.py`（**必改**：加 edges 入 detail payload）
- Modify: `CHANGELOG.md`
- Modify: `README.md`（若相關）
- Test (new): `the_door/tests/unit/core/llm/test_prompts_resolution.py`
- Test (new): `the_door/tests/unit/core/reading/test_batch_reader_resolution.py`
- Script (new): `scripts/dogfood_scope_resolution_report.py`

---

## Steps

### Step 1 — 確認 BatchReader 現況

- [ ] **Step 1: 檢查 BatchReader `_build_payload` 是否含 edges**

```
grep -n "edges\|edge\|resolution" the_door/src/the_door/core/reading/batch_reader.py | head -30
```

**預期結果（依目前 main 分支）：** detail 模式 `_build_payload` 只輸出 `batch / context_mode / nodes`，不含 edges。Step 7-9 必須執行加 edges。

---

### Step 2 — 寫 prompt + batch_reader failing tests

- [ ] **Step 2: 建立 prompt 測試**

新增 `the_door/tests/unit/core/llm/test_prompts_resolution.py`：

```python
"""Tests for Task 06 — L1_SYSTEM_PROMPT teaches LLM how to read edge.resolution."""
from __future__ import annotations

from the_door.core.llm.prompts import L1_SYSTEM_PROMPT


class TestPromptMentionsResolution:
    def test_prompt_mentions_resolution_field(self):
        assert "resolution" in L1_SYSTEM_PROMPT

    def test_prompt_mentions_scope_rule_label(self):
        assert "scope_rule" in L1_SYSTEM_PROMPT

    def test_prompt_mentions_import_alias_label(self):
        assert "import_alias" in L1_SYSTEM_PROMPT

    def test_prompt_mentions_name_match_label(self):
        assert "name_match" in L1_SYSTEM_PROMPT

    def test_prompt_mentions_skipped_dynamic_label(self):
        assert "skipped_dynamic" in L1_SYSTEM_PROMPT

    def test_prompt_distinguishes_high_low_confidence(self):
        """Prompt must teach LLM that scope_rule/import_alias are high confidence
        and name_match is low confidence."""
        # 高信心 / 低信心 必須在 prompt 內成對出現
        assert "高信心" in L1_SYSTEM_PROMPT
        assert "低信心" in L1_SYSTEM_PROMPT

    def test_prompt_tells_llm_to_skip_uncertain_name_match(self):
        """Prompt must instruct LLM to be conservative with name_match edges."""
        # "寧可不提" 或類似的保守指引必須在
        assert "寧可不提" in L1_SYSTEM_PROMPT or "不要" in L1_SYSTEM_PROMPT
```

- [ ] **Step 3: 建立 batch_reader 測試**

新增 `the_door/tests/unit/core/reading/test_batch_reader_resolution.py`：

```python
"""Tests for Task 06 — BatchReader detail mode payload includes edge.resolution.

BatchReader API (verified against src batch_reader.py:50-57):
- Constructor: BatchReader(llm_provider, structure: StructureJSON, *,
                          max_context_tokens=None, context_mode="detail")
- Method:      _build_payload(node_ids: list[str], batch_num: int) → dict

Note: first positional arg is `llm_provider` (not `provider`); `structure` is the
second positional. We test _build_payload directly because it's the smallest seam
containing the edge serialization logic. The llm_provider is mocked because
BatchReader's constructor wires up PruningEngine + provider but neither is
exercised by _build_payload.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from the_door.core.reading.batch_reader import BatchReader
from the_door.models import ASTNode, Edge, StructureJSON


def _node(node_id, name="x", file="f.py"):
    return ASTNode(
        node_id=node_id,
        name=name,
        file=file,
        language="python",
        type="function",
    )


def _make_reader(nodes, edges, context_mode="detail"):
    structure = StructureJSON(files=[], nodes=nodes, edges=edges, topology=[])
    provider = MagicMock()
    provider.estimate_tokens.return_value = 100
    # Real signature: BatchReader(llm_provider, structure, *, max_context_tokens=None, context_mode="detail")
    return BatchReader(llm_provider=provider, structure=structure, context_mode=context_mode)


class TestBatchReaderResolution:
    """Detail mode payload must include edges with resolution so LLM can read it."""

    def test_detail_payload_includes_edges_key(self):
        nodes = [_node("a.py::foo", "foo"), _node("a.py::bar", "bar")]
        edges = [Edge(from_node="a.py::foo", to_node="a.py::bar", type="calls", resolution="scope_rule")]
        reader = _make_reader(nodes, edges)
        payload = reader._build_payload(["a.py::foo", "a.py::bar"], batch_num=1)
        assert "edges" in payload, f"detail payload must contain 'edges' key, got: {list(payload.keys())}"

    def test_detail_payload_edge_has_resolution_field(self):
        nodes = [_node("a.py::foo"), _node("a.py::bar")]
        edges = [Edge(from_node="a.py::foo", to_node="a.py::bar", type="calls", resolution="scope_rule")]
        reader = _make_reader(nodes, edges)
        payload = reader._build_payload(["a.py::foo", "a.py::bar"], batch_num=1)
        payload_str = json.dumps(payload, ensure_ascii=False)
        assert "scope_rule" in payload_str

    def test_detail_payload_filters_edges_to_batch_node_ids(self):
        """Edges referencing nodes outside the current batch must be excluded
        to keep payload size bounded (per spec §3 non-goal: don't blow up payloads)."""
        nodes = [_node("a.py::foo"), _node("a.py::bar"), _node("c.py::out")]
        edges = [
            Edge(from_node="a.py::foo", to_node="a.py::bar", type="calls", resolution="scope_rule"),
            Edge(from_node="a.py::foo", to_node="c.py::out", type="calls", resolution="name_match"),
        ]
        reader = _make_reader(nodes, edges)
        payload = reader._build_payload(["a.py::foo", "a.py::bar"], batch_num=1)
        # Only the within-batch edge should be present
        edge_dicts = payload.get("edges", [])
        targets = {e["to"] for e in edge_dicts}
        assert "a.py::bar" in targets
        assert "c.py::out" not in targets, "out-of-batch edge must be filtered"

    def test_detail_payload_serializes_all_resolution_types(self):
        nodes = [_node("a.py::foo"), _node("a.py::bar")]
        edges = [
            Edge(from_node="a.py::foo", to_node="a.py::bar", type="calls", resolution="scope_rule"),
            Edge(from_node="a.py::foo", to_node="a.py::bar", type="calls", resolution="import_alias"),
        ]
        # Use distinct edges to confirm both serialize correctly
        edges_full = [
            Edge(from_node="a.py::foo", to_node="a.py::bar", type="calls", resolution="scope_rule"),
            Edge(from_node="a.py::bar", to_node="a.py::foo", type="calls", resolution="name_match"),
        ]
        reader = _make_reader(nodes, edges_full)
        payload = reader._build_payload(["a.py::foo", "a.py::bar"], batch_num=1)
        payload_str = json.dumps(payload, ensure_ascii=False)
        assert "scope_rule" in payload_str
        assert "name_match" in payload_str

    def test_minimal_mode_payload_unchanged_no_edges(self):
        """minimal mode is intentionally edge-less; spec §4.5 教學只對 detail mode."""
        nodes = [_node("a.py::foo")]
        edges = [Edge(from_node="a.py::foo", to_node="a.py::foo", type="calls", resolution="scope_rule")]
        reader = _make_reader(nodes, edges, context_mode="minimal")
        payload = reader._build_payload(["a.py::foo"], batch_num=1)
        assert "edges" not in payload
        assert payload["context_mode"] == "minimal"
```

> **若 BatchReader 建構式所需的 provider 介面與 MagicMock 預設不符**：先看
> `the_door/src/the_door/core/reading/batch_reader.py` 的 `__init__` 參數，補上必要的 mock
> 屬性（不要 monkey-patch 真實 provider 行為）。

- [ ] **Step 4: 執行，確認 FAIL**

```
cd the_door
pytest tests/unit/core/llm/test_prompts_resolution.py tests/unit/core/llm/test_batch_reader_resolution.py -v 2>&1 | head -30
```

---

### Step 3 — 更新 L1_SYSTEM_PROMPT

- [ ] **Step 5: 在 prompt 加入 resolution 教學段落**

在 `the_door/src/the_door/core/llm/prompts.py` 的 `L1_SYSTEM_PROMPT` 內，在「## 風格規則（硬性）」段落之**前**或「## 任務」段落之**後**，插入：

```
## 關聯邊 (edges) 的 resolution 標籤

你會收到的節點之間有 `edges`，每條邊都帶 `resolution` 標籤，用來告訴你這條邊的信心等級：

- `scope_rule`：透過 scope 規則明確解到（同檔 / 同套件）。**高信心**，可以放心採用為事實依據撰寫 description。
- `import_alias`：透過 import 別名解到目標。**高信心**，同上可採用。
- `name_match`：純粹靠裸名匹配找到，可能是程式內多個同名節點之一。**低信心，僅供參考**。若描述會因為這條邊的不確定性而產生分歧，**寧可不提**這條關聯。
- `skipped_dynamic`：偵測到動態 dispatch context（例如 Ruby method_missing、Python __getattr__、reflection）。目的端候選來自裸名匹配，**不可作為事實依據**。**不要對這條邊的目標做任何斷言**。

撰寫 description 時，優先以 `scope_rule` / `import_alias` 高信心邊為依據；對 `name_match` 持保守態度；對 `skipped_dynamic` 不提即可。
```

- [ ] **Step 6: prompt 測試 PASS**

```
cd the_door
pytest tests/unit/core/llm/test_prompts_resolution.py -v
```

期望：全部 PASS。

---

### Step 4 — 擴充 BatchReader `_build_payload` 加入 edges

- [ ] **Step 7: 定位修改點**

```
grep -n "_build_payload\|context_mode\|nodes" the_door/src/the_door/core/reading/batch_reader.py | head -10
```

確認 `_build_payload(self, node_ids, batch_num)` 約在 line 254-284，detail mode 分支當前只 return `{batch, context_mode, nodes}`。

- [ ] **Step 8: 在 detail 分支加入 `edges` 欄位**

找到（約 line 280-284）：

```python
        return {
            "batch": batch_num,
            "context_mode": "detail",
            "nodes": node_dicts,
        }
```

改成：

```python
        # Filter edges to those fully within this batch to bound payload size.
        batch_node_set = set(node_ids)
        edge_dicts = [
            {
                "from": e.from_node,
                "to": e.to_node,
                "type": e.type,
                "resolution": e.resolution,
            }
            for e in self._structure.edges
            if e.from_node in batch_node_set and e.to_node in batch_node_set
        ]
        return {
            "batch": batch_num,
            "context_mode": "detail",
            "nodes": node_dicts,
            "edges": edge_dicts,
        }
```

**設計理由：**
- 只放「from 與 to 都在當前 batch」的邊 → 避免 LLM 看到無法 reference 的目標、避免 payload 爆炸
- minimal mode 不動 → 保持原有 token 節省語意
- 既有 BatchReader 其他方法（`_maybe_split` 用 `_serialize_payload` 估 token）會自動把 edges 計入 size budget

- [ ] **Step 9: BatchReader 測試 PASS**

```
cd the_door
pytest tests/unit/core/reading/test_batch_reader_resolution.py -v
```

若 mock provider 介面不足，補上 `provider.estimate_tokens.return_value = N` 等屬性。**不要**改成 monkey-patch 真實程式。

---

### Step 5 — 更新 CHANGELOG 與 README

- [ ] **Step 10: CHANGELOG 加 v1.5.0 entry**

在 `CHANGELOG.md` 頂部（最新 entry 之前）加入：

```markdown
## [1.5.0] - 2026-05-28

### Added
- **Scope-aware edge resolution** for all 7 supported languages (Python / TypeScript / Java / Go / Rust / Ruby / PHP / C#).
  - New `ScopeRules` declarative config per language defining import / function / method / inheritance resolution strategies.
  - New `Edge.resolution` field with four values: `scope_rule` (high confidence), `import_alias` (high confidence), `name_match` (low confidence fallback), `skipped_dynamic` (dynamic dispatch context — not trusted).
  - LLM prompt teaches the model how to weight edges by resolution provenance.
- New `ScopeContext` dataclass carrying per-file scope state (import aliases, caller class).

### Changed
- `EdgeBuilder.build_edges()` now takes an optional `configs` parameter (backward compatible).
- `ASTExtractor` passes `LANGUAGE_CONFIGS` to `EdgeBuilder`.
- Edge dedup key remains `(from, to, type)` — `resolution` is not part of the key (intentional, allows scope_rule edges to win over name_match duplicates).

### Backward compatibility
- Old snapshots without `resolution` deserialize with `resolution="name_match"` (no migration needed).
- `Edge(from_node=..., to_node=..., type=...)` constructor calls without `resolution` continue to work (defaults to `"name_match"`).
- No public API signature broken; `build_edges(nodes, trees)` still works.
```

- [ ] **Step 11: README 補述（可選）**

執行：

```
grep -n "edge\|relation\|關聯" README.md | head -10
```

若有提及邊質量或精準度的段落，附加一句說明 v1.5.0 後 edge 帶 provenance 標籤。若 README 沒有相關段落，略過此步驟。

---

### Step 6 — Dogfood 驗收 script

- [ ] **Step 12: 建立 dogfood 報告 script**

新增 `scripts/dogfood_scope_resolution_report.py`：

```python
"""Run scope-aware EdgeBuilder against the_door itself and report resolution distribution.

Usage:
  python scripts/dogfood_scope_resolution_report.py [target_path]

Acceptance (spec §7.2):
  - scope_rule + import_alias ≥ 50%
  - name_match ≤ 40%
  - skipped_dynamic: language-dependent (Ruby/Python may be higher)
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from the_door.core.extraction.ast_extractor import ASTExtractor


def main(target: str = ".") -> int:
    target_path = Path(target).resolve()
    print(f"Analyzing: {target_path}")
    extractor = ASTExtractor()
    result = extractor.extract(str(target_path))

    if not result.edges:
        print("ERROR: no edges produced.")
        return 1

    counts = Counter(e.resolution for e in result.edges)
    total = sum(counts.values())
    high = counts.get("scope_rule", 0) + counts.get("import_alias", 0)
    name_match = counts.get("name_match", 0)
    dynamic = counts.get("skipped_dynamic", 0)

    print(f"\nTotal edges: {total}")
    print(f"  scope_rule:      {counts.get('scope_rule', 0):>6} ({counts.get('scope_rule', 0)/total*100:5.1f}%)")
    print(f"  import_alias:    {counts.get('import_alias', 0):>6} ({counts.get('import_alias', 0)/total*100:5.1f}%)")
    print(f"  name_match:      {name_match:>6} ({name_match/total*100:5.1f}%)")
    print(f"  skipped_dynamic: {dynamic:>6} ({dynamic/total*100:5.1f}%)")
    print(f"\nHigh confidence (scope_rule + import_alias): {high/total*100:5.1f}%  (target: ≥ 50%)")
    print(f"Low confidence  (name_match):                 {name_match/total*100:5.1f}%  (target: ≤ 40%)")

    ok = (high / total) >= 0.50 and (name_match / total) <= 0.40
    print(f"\nResult: {'PASS' if ok else 'FAIL (does not meet §7.2 acceptance thresholds)'}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
```

- [ ] **Step 13: 跑 dogfood**

```
cd C:/Users/Ric/Desktop/the_door
python scripts/dogfood_scope_resolution_report.py the_door/src/the_door
```

期望：scope_rule + import_alias ≥ 50%，name_match ≤ 40%。

若未達標：
1. 檢查 Python 是否有走 file_local_then_imports（同檔呼叫應該標 scope_rule）
2. 檢查 import alias 是否解析到（grep 看 import 數量）
3. 若多數仍是 name_match，回頭檢查 Task 02/03 的 scope 解析邏輯，**不要**直接降低驗收標準

- [ ] **Step 14: 對 v105 test target 跑 dogfood**

```
python scripts/dogfood_scope_resolution_report.py C:/Users/Ric/Desktop/test-targets/the-door-v105
```

期望同上。

---

### Step 7 — 最終驗收 + 出版

- [ ] **Step 15: 全套 coverage**

```
cd the_door
pytest tests/unit/core/llm/test_prompts_resolution.py tests/unit/core/llm/test_batch_reader_resolution.py -v \
  --cov=the_door.core.llm.prompts \
  --cov=the_door.core.llm.batch_reader \
  --cov-fail-under=100
```

- [ ] **Step 16: 全套回歸**

```
cd the_door
pytest tests/ -q 2>&1 | tail -5
```

期望：全部 PASS。

- [ ] **Step 17: Spec §7.1 結構性驗收 checklist**

逐項手動確認（grep + 程式碼查驗）：

- [ ] `LanguageConfig.scope_rules` 存在，7 種語言皆有非 None 值
  ```
  python -c "from the_door.core.extraction.language_configs import LANGUAGE_CONFIGS; print({k: v.scope_rules is not None for k, v in LANGUAGE_CONFIGS.items()})"
  ```
- [ ] `ScopeRules` dataclass 含 5 欄位（import/function/method/inheritance + dynamic_markers）
- [ ] `Edge.resolution` 存在，新產生的 edge 必填（grep 證明）
  ```
  grep -n "Edge(" the_door/src/the_door/core/extraction/edge_builder.py
  ```
  每個 `Edge(...)` 建構處必有 `resolution=...`
- [ ] `_resolve()` 三段式存在於 edge_builder.py
- [ ] 舊 snapshot 載入時 `resolution` 預設為 `"name_match"`（Task 01 已測試）
- [ ] `L1_SYSTEM_PROMPT` 含四種 resolution 說明（Task 06 Step 6 已測試）

- [ ] **Step 18: Commit + tag**

```
git add the_door/src/the_door/core/llm/prompts.py \
        the_door/src/the_door/core/reading/batch_reader.py \
        the_door/tests/unit/core/llm/test_prompts_resolution.py \
        the_door/tests/unit/core/reading/test_batch_reader_resolution.py \
        scripts/dogfood_scope_resolution_report.py \
        CHANGELOG.md \
        README.md
git commit -m "feat(llm): teach L1 prompt to read edge.resolution; v1.5.0 dogfood verification"
```

- [ ] **Step 19: 報告 dogfood 數據**

把 Step 13 / 14 的輸出貼回 PR / handoff，作為 spec §7.2 驗收證據。
