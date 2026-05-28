# Task 01 — Schema Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改動任何現有行為的前提下，釘定本 spec 所需的全部 schema：`ScopeRules` / `ScopeContext` dataclass、`LanguageConfig.scope_rules` 欄位、`Edge.resolution` 欄位、structure_serializer 的序列化/反序列化向後相容。

**Architecture:** 純 schema 變動，無邏輯改動。`Edge` 加 `resolution="name_match"` 預設值，確保所有現有程式碼與舊 snapshot 不需修改即可繼續運作。`ScopeRules` 與 `ScopeContext` 放進 `language_configs.py`，作為後續任務的共用型別。

**Tech Stack:** Python 3.11+ dataclasses, `typing.Literal`, pytest, pytest-cov。

**Test Coverage Requirement:** 本任務所改動的每個檔案需 100% line coverage。以下指令驗收：

```
pytest the_door/tests/unit/core/extraction/test_schema_foundation.py -v --cov=the_door.core.extraction.language_configs --cov=the_door.models --cov=the_door.core.extraction.structure_serializer --cov-fail-under=100
```

---

## Background（自含）

本任務是 Scope-Aware Edge Resolution spec（`docs/superpowers/specs/2026-05-28-scope-aware-edge-resolution-design.md`）的 Phase 0。

**目前狀態（執行前必讀）：**

- `the_door/src/the_door/models.py:35` — `Edge` dataclass 有 3 個欄位：`from_node`, `to_node`, `type`（值為 `"calls"` / `"extends"` / `"imports"`）。**沒有** `resolution` 欄位。
- `the_door/src/the_door/core/extraction/language_configs.py:14` — `LanguageConfig` dataclass **沒有** `scope_rules` 欄位。`ScopeRules` / `ScopeContext` 均不存在。
- `the_door/src/the_door/core/extraction/structure_serializer.py:43` — `build_structure_dict(structure: StructureJSON, scan_result: ScanResult | None)` 序列化 edge 只寫 `{"from": ..., "to": ..., "type": ...}`，**沒有** `resolution`。
- `the_door/src/the_door/core/extraction/structure_serializer.py:96` — `parse_structure_dict(data: dict) → StructureJSON` 反序列化 edge：`Edge(from_node=e["from"], to_node=e["to"], type=e["type"])`，**沒有** `resolution`。
- **重要**：API 名稱是 `build_structure_dict` / `parse_structure_dict`，**不是** `serialize` / `deserialize`。處理的型別是 `StructureJSON`（含 `topology` 欄位），**不是** `ExtractionResult`（無 `topology`）。

**本任務完成後的狀態：**

- `Edge` 增加 `resolution: str = "name_match"`（frozen dataclass 加欄位+預設值沒有問題）
- `LanguageConfig` 增加 `scope_rules: ScopeRules | None = None`
- `ScopeRules` 與 `ScopeContext` 定義於 `language_configs.py`
- serializer 寫出 `resolution`；反序列化用 `e.get("resolution", "name_match")`（舊 snapshot 不受影響）
- 所有既有測試繼續全部 PASS（`Edge(from_node=..., to_node=..., type=...)` 呼叫無需改動，因為 `resolution` 有預設值）

---

## Files

- Modify: `the_door/src/the_door/models.py`
- Modify: `the_door/src/the_door/core/extraction/language_configs.py`
- Modify: `the_door/src/the_door/core/extraction/structure_serializer.py`
- Test (new): `the_door/tests/unit/core/extraction/test_schema_foundation.py`

---

## Steps

### Step 1 — 寫 failing tests

- [ ] **Step 1: 建立測試檔案**

新增 `the_door/tests/unit/core/extraction/test_schema_foundation.py`：

```python
"""Tests for Task 01 — ScopeRules / ScopeContext / Edge.resolution / serializer backward compat."""
from __future__ import annotations

import pytest

from the_door.core.extraction.language_configs import (
    LANGUAGE_CONFIGS,
    LanguageConfig,
    ScopeContext,
    ScopeRules,
)
from the_door.core.extraction.structure_serializer import build_structure_dict, parse_structure_dict
from the_door.models import ASTNode, Edge, StructureJSON


# ── ScopeRules schema ──────────────────────────────────────────────────────────

class TestScopeRulesSchema:
    def test_can_construct_with_all_fields(self):
        rules = ScopeRules(
            import_resolution="qualified",
            function_resolution="file_local_then_imports",
            method_resolution="class_local_then_inherited",
            inheritance_resolution="multiple",
            dynamic_markers=frozenset({"__getattr__"}),
        )
        assert rules.import_resolution == "qualified"
        assert rules.function_resolution == "file_local_then_imports"
        assert rules.method_resolution == "class_local_then_inherited"
        assert rules.inheritance_resolution == "multiple"
        assert "__getattr__" in rules.dynamic_markers

    def test_dynamic_markers_defaults_to_empty_frozenset(self):
        rules = ScopeRules(
            import_resolution="es_module",
            function_resolution="file_local_then_imports",
            method_resolution="class_local_then_inherited",
            inheritance_resolution="single",
        )
        assert rules.dynamic_markers == frozenset()

    def test_is_frozen(self):
        rules = ScopeRules(
            import_resolution="qualified",
            function_resolution="file_local_then_imports",
            method_resolution="class_local_then_inherited",
            inheritance_resolution="multiple",
        )
        with pytest.raises(Exception):  # frozen dataclass raises FrozenInstanceError
            rules.import_resolution = "namespaced"  # type: ignore

    def test_import_resolution_valid_literals(self):
        for val in ("qualified", "namespaced", "module_path", "es_module"):
            rules = ScopeRules(
                import_resolution=val,  # type: ignore
                function_resolution="file_local_then_imports",
                method_resolution="class_local_then_inherited",
                inheritance_resolution="single",
            )
            assert rules.import_resolution == val

    def test_function_resolution_valid_literals(self):
        for val in ("file_local_then_imports", "package_local_then_imports", "global"):
            rules = ScopeRules(
                import_resolution="qualified",
                function_resolution=val,  # type: ignore
                method_resolution="class_local_then_inherited",
                inheritance_resolution="single",
            )
            assert rules.function_resolution == val

    def test_method_resolution_valid_literals(self):
        for val in ("class_local_then_inherited", "structural", "trait_dispatch", "dynamic_dispatch"):
            rules = ScopeRules(
                import_resolution="qualified",
                function_resolution="file_local_then_imports",
                method_resolution=val,  # type: ignore
                inheritance_resolution="single",
            )
            assert rules.method_resolution == val

    def test_inheritance_resolution_valid_literals(self):
        for val in ("single", "multiple", "mixin", "interface_only"):
            rules = ScopeRules(
                import_resolution="qualified",
                function_resolution="file_local_then_imports",
                method_resolution="class_local_then_inherited",
                inheritance_resolution=val,  # type: ignore
            )
            assert rules.inheritance_resolution == val


# ── ScopeContext schema ────────────────────────────────────────────────────────

class TestScopeContextSchema:
    def test_can_construct(self):
        ctx = ScopeContext(
            current_file="orders/service.py",
            import_aliases={"v": "validate"},
            caller_class="OrderService",
            caller_name="checkout",
        )
        assert ctx.current_file == "orders/service.py"
        assert ctx.import_aliases == {"v": "validate"}
        assert ctx.caller_class == "OrderService"
        assert ctx.caller_name == "checkout"

    def test_caller_name_defaults_to_empty_string(self):
        ctx = ScopeContext(
            current_file="main.py",
            import_aliases={},
            caller_class=None,
        )
        assert ctx.caller_name == ""

    def test_caller_class_can_be_none(self):
        ctx = ScopeContext(current_file="main.py", import_aliases={}, caller_class=None)
        assert ctx.caller_class is None

    def test_has_dynamic_marker_true_when_caller_name_matches(self):
        ctx = ScopeContext(
            current_file="x.py",
            import_aliases={},
            caller_class=None,
            caller_name="__getattr__",
        )
        assert ctx.has_dynamic_marker(frozenset({"__getattr__", "method_missing"})) is True

    def test_has_dynamic_marker_false_when_no_match(self):
        ctx = ScopeContext(
            current_file="x.py",
            import_aliases={},
            caller_class=None,
            caller_name="checkout",
        )
        assert ctx.has_dynamic_marker(frozenset({"__getattr__", "method_missing"})) is False

    def test_has_dynamic_marker_false_on_empty_markers(self):
        ctx = ScopeContext(
            current_file="x.py",
            import_aliases={},
            caller_class=None,
            caller_name="__getattr__",
        )
        assert ctx.has_dynamic_marker(frozenset()) is False


# ── LanguageConfig.scope_rules ─────────────────────────────────────────────────

class TestLanguageConfigScopeRules:
    def test_scope_rules_field_defaults_to_none(self):
        cfg = LanguageConfig()
        assert cfg.scope_rules is None

    def test_scope_rules_can_be_set(self):
        rules = ScopeRules(
            import_resolution="qualified",
            function_resolution="file_local_then_imports",
            method_resolution="class_local_then_inherited",
            inheritance_resolution="multiple",
        )
        cfg = LanguageConfig(scope_rules=rules)
        assert cfg.scope_rules is rules

    def test_existing_language_configs_still_constructable(self):
        # Ensures no regression to existing LANGUAGE_CONFIGS dict
        assert "python" in LANGUAGE_CONFIGS
        assert LANGUAGE_CONFIGS["python"].function_types  # frozenset still there


# ── Edge.resolution ────────────────────────────────────────────────────────────

class TestEdgeResolution:
    def test_edge_default_resolution_is_name_match(self):
        e = Edge(from_node="A.foo", to_node="B.bar", type="calls")
        assert e.resolution == "name_match"

    def test_edge_resolution_can_be_set_explicitly(self):
        e = Edge(from_node="A.foo", to_node="B.bar", type="calls", resolution="scope_rule")
        assert e.resolution == "scope_rule"

    def test_edge_resolution_accepts_all_valid_values(self):
        for val in ("scope_rule", "import_alias", "name_match", "skipped_dynamic"):
            e = Edge(from_node="A.foo", to_node="B.bar", type="calls", resolution=val)
            assert e.resolution == val

    def test_edge_still_frozen(self):
        e = Edge(from_node="A.foo", to_node="B.bar", type="calls")
        with pytest.raises(Exception):
            e.resolution = "scope_rule"  # type: ignore

    def test_edge_type_field_still_named_type_not_edge_type(self):
        e = Edge(from_node="A.foo", to_node="B.bar", type="calls")
        assert hasattr(e, "type")
        assert not hasattr(e, "edge_type")

    def test_edge_type_value_is_calls_not_call(self):
        e = Edge(from_node="A.foo", to_node="B.bar", type="calls")
        assert e.type == "calls"


# ── structure_serializer backward compat ──────────────────────────────────────

def _make_structure(edges):
    return StructureJSON(
        files=[],
        nodes=[],
        edges=edges,
        topology=[],
    )


class TestSerializerResolution:
    def test_build_structure_dict_writes_resolution_field(self):
        e = Edge(from_node="A.foo", to_node="B.bar", type="calls", resolution="scope_rule")
        structure = _make_structure([e])
        data = build_structure_dict(structure, None)
        assert data["edges"][0]["resolution"] == "scope_rule"

    def test_build_structure_dict_writes_name_match_for_default(self):
        e = Edge(from_node="A.foo", to_node="B.bar", type="calls")
        structure = _make_structure([e])
        data = build_structure_dict(structure, None)
        assert data["edges"][0]["resolution"] == "name_match"

    def test_parse_structure_dict_reads_resolution_when_present(self):
        data = {
            "files": [],
            "nodes": [],
            "edges": [{"from": "A.foo", "to": "B.bar", "type": "calls", "resolution": "import_alias"}],
            "topology": [],
        }
        result = parse_structure_dict(data)
        assert result.edges[0].resolution == "import_alias"

    def test_parse_structure_dict_defaults_resolution_to_name_match_for_old_snapshots(self):
        """Old snapshots without 'resolution' key must load without error."""
        data = {
            "files": [],
            "nodes": [],
            "edges": [{"from": "A.foo", "to": "B.bar", "type": "calls"}],  # no resolution key
            "topology": [],
        }
        result = parse_structure_dict(data)
        assert result.edges[0].resolution == "name_match"

    def test_roundtrip_preserves_resolution(self):
        e = Edge(from_node="X.m", to_node="Y.n", type="extends", resolution="skipped_dynamic")
        structure = _make_structure([e])
        data = build_structure_dict(structure, None)
        restored = parse_structure_dict(data)
        assert restored.edges[0].resolution == "skipped_dynamic"
```

- [ ] **Step 2: 執行測試，確認全部 FAIL**

```
cd the_door
pytest tests/unit/core/extraction/test_schema_foundation.py -v 2>&1 | head -40
```

期望：`ImportError: cannot import name 'ScopeRules' from 'the_door.core.extraction.language_configs'`（或類似 import 錯誤）

---

### Step 2 — 修改 `language_configs.py`

- [ ] **Step 3: 在 `language_configs.py` 加入 ScopeRules / ScopeContext / scope_rules 欄位**

在 `the_door/src/the_door/core/extraction/language_configs.py` 的 `from __future__ import annotations` 之後加入：

```python
from typing import Literal
```

（若已有則略過。）

在 `@dataclass(frozen=True) class LanguageConfig:` **之前**插入：

```python
ImportStrategy = Literal["qualified", "namespaced", "module_path", "es_module"]
FunctionStrategy = Literal["file_local_then_imports", "package_local_then_imports", "global"]
MethodStrategy = Literal[
    "class_local_then_inherited", "structural", "trait_dispatch", "dynamic_dispatch"
]
InheritanceStrategy = Literal["single", "multiple", "mixin", "interface_only"]


@dataclass(frozen=True)
class ScopeRules:
    """Per-language scope resolution strategy — how EdgeBuilder resolves call targets."""

    import_resolution: ImportStrategy
    function_resolution: FunctionStrategy
    method_resolution: MethodStrategy
    inheritance_resolution: InheritanceStrategy
    dynamic_markers: frozenset[str] = field(default_factory=frozenset)


@dataclass
class ScopeContext:
    """Per-file, per-call-site scope snapshot used by EdgeBuilder._resolve().

    Constructed once per file at the start of edge detection, then cloned
    per call site with caller_name updated.
    """

    current_file: str
    """Relative file path of the file currently being analyzed."""

    import_aliases: dict[str, str]
    """alias → original_name mapping parsed from import statements.

    Example (Python):  from orders.validator import validate as v
                       → {"v": "validate"}
    Example (TS):      import { validate as v } from './validator'
                       → {"v": "validate"}
    """

    caller_class: str | None
    """Class name containing the current function, or None for module-level."""

    caller_name: str = ""
    """Name of the function/method currently being analyzed."""

    def has_dynamic_marker(self, markers: frozenset[str]) -> bool:
        """Return True if caller_name is in the dynamic markers set."""
        return bool(self.caller_name and self.caller_name in markers)
```

在 `LanguageConfig` dataclass 的**最後一個欄位後**加入：

```python
    scope_rules: "ScopeRules | None" = None
    """Scope resolution rules for EdgeBuilder. None until Task 03-05 fill them in."""
```

完整欄位順序（最終狀態，確認不破壞既有欄位）：
```
function_types / method_types / class_types / container_types
parameters_field / return_type_field
doc_comment_strategy / doc_comment_types / doc_comment_markers / decorator_types
scope_rules   ← 新增（最後）
```

- [ ] **Step 4: 執行測試，確認 ScopeRules / ScopeContext / LanguageConfig 相關 test 全部 PASS**

```
cd the_door
pytest tests/unit/core/extraction/test_schema_foundation.py::TestScopeRulesSchema tests/unit/core/extraction/test_schema_foundation.py::TestScopeContextSchema tests/unit/core/extraction/test_schema_foundation.py::TestLanguageConfigScopeRules -v
```

期望：全部 PASS。

---

### Step 3 — 修改 `models.py`

- [ ] **Step 5: 在 `Edge` dataclass 加入 `resolution` 欄位**

找到 `the_door/src/the_door/models.py` 的 `Edge` dataclass（目前在約第 34 行）：

```python
@dataclass(frozen=True)
class Edge:
    """A relationship between two AST nodes."""

    from_node: str  # node_id
    to_node: str  # node_id
    type: str  # "calls" | "imports" | "extends" | "implements"
```

改成：

```python
@dataclass(frozen=True)
class Edge:
    """A relationship between two AST nodes."""

    from_node: str  # node_id
    to_node: str  # node_id
    type: str  # "calls" | "imports" | "extends" | "implements"
    resolution: str = "name_match"
    # "scope_rule" | "import_alias" | "name_match" | "skipped_dynamic"
```

**注意：** `resolution` 有預設值，所有現有 `Edge(from_node=..., to_node=..., type=...)` 呼叫不需修改。

- [ ] **Step 6: 執行 Edge 相關測試，確認 PASS**

```
cd the_door
pytest tests/unit/core/extraction/test_schema_foundation.py::TestEdgeResolution -v
```

期望：全部 PASS。

- [ ] **Step 7: 確認既有全套測試不迴歸**

```
cd the_door
pytest tests/ -x -q 2>&1 | tail -5
```

期望：`passed` 數量與修改前相同（所有 edge 建構點有預設值，無需改動）。若出現 FAIL 請先修復再繼續。

---

### Step 4 — 修改 `structure_serializer.py`

- [ ] **Step 8: 更新 `build_structure_dict` — 寫出 resolution**

找到 `the_door/src/the_door/core/extraction/structure_serializer.py` 第 42-44 行：

```python
        "edges": [
            {"from": e.from_node, "to": e.to_node, "type": e.type}
            for e in structure.edges
        ],
```

改成：

```python
        "edges": [
            {"from": e.from_node, "to": e.to_node, "type": e.type, "resolution": e.resolution}
            for e in structure.edges
        ],
```

- [ ] **Step 9: 更新 `parse_structure_dict` — 讀 resolution，舊 snapshot 給預設值**

找到第 95-97 行：

```python
    edges = [
        Edge(from_node=e["from"], to_node=e["to"], type=e["type"])
        for e in data["edges"]
    ]
```

改成：

```python
    edges = [
        Edge(
            from_node=e["from"],
            to_node=e["to"],
            type=e["type"],
            resolution=e.get("resolution", "name_match"),
        )
        for e in data["edges"]
    ]
```

- [ ] **Step 10: 執行 serializer 測試，確認 PASS**

```
cd the_door
pytest tests/unit/core/extraction/test_schema_foundation.py::TestSerializerResolution -v
```

期望：全部 PASS。

---

### Step 5 — 全套驗收

- [ ] **Step 11: 執行本任務全部測試 + coverage**

```
cd the_door
pytest tests/unit/core/extraction/test_schema_foundation.py -v \
  --cov=the_door.core.extraction.language_configs \
  --cov=the_door.models \
  --cov=the_door.core.extraction.structure_serializer \
  --cov-fail-under=100
```

期望：所有 test PASS + coverage 100%。

- [ ] **Step 12: 確認全套回歸測試通過**

```
cd the_door
pytest tests/ -q 2>&1 | tail -5
```

期望：全部 PASS，0 失敗。

- [ ] **Step 13: Commit**

```
git add the_door/src/the_door/models.py \
        the_door/src/the_door/core/extraction/language_configs.py \
        the_door/src/the_door/core/extraction/structure_serializer.py \
        the_door/tests/unit/core/extraction/test_schema_foundation.py
git commit -m "feat(schema): add ScopeRules/ScopeContext/Edge.resolution for scope-aware edge resolution"
```
