# Task 01 — LanguageConfig Schema Extension

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 擴充 `LanguageConfig` dataclass 加入 6 個新欄位（parameters_field / return_type_field / doc_comment_strategy / doc_comment_types / doc_comment_markers / decorator_types），並為 java/go/rust/ruby/php/csharp 6 種語言填入抽取規則。**此任務只動 schema 與資料，不改抽取行為**。

**Architecture:** Frozen dataclass 加 6 個 optional 欄位，預設值保持「不抽」語意（None / 空 frozenset）。原有欄位 function_types / method_types / class_types / container_types 完全不動，向後相容。

**Tech Stack:** Python 3.11+ dataclass, pytest, frozenset。

**Test Coverage Requirement:** 修改後的 `core/extraction/language_configs.py` 必須達 100% line coverage。pytest 加 `--cov=the_door.core.extraction.language_configs --cov-fail-under=100`。

---

## Background（自含）

當前 `the_door/src/the_door/core/extraction/language_configs.py` 是 codegraph commit `5aae9c4` 抄錄的 per-language tree-sitter node-type 對照表。`LanguageConfig` dataclass 只有 4 個欄位（function_types / method_types / class_types / container_types），決定「哪些 tree-sitter node 算 function/class」。

`ASTNode` (定義於 `the_door/src/the_door/models.py`) 還有 5 個內容欄位（parameters / return_type / decorators / docstring / comments），但 `_walk_config_driven` 對 java/go/rust/ruby/php/csharp 6 種語言**完全沒填**。Python / TypeScript 走專用 walker 有填。

本任務為後續 `_walk_config_driven` enriched builder（在獨立任務做）鋪 schema 基礎：把「每個語言的 doc-comment / parameter / annotation 抽取規則」用宣告式 config 表達。

---

## Files

- Modify: `the_door/src/the_door/core/extraction/language_configs.py`
- Test (new): `the_door/tests/unit/core/extraction/test_language_configs.py`

---

## Steps

### Step 1 — Write failing schema tests

- [ ] **Step 1: Add failing tests for new LanguageConfig fields**

Create `the_door/tests/unit/core/extraction/test_language_configs.py`:

```python
"""Tests for LanguageConfig schema extension (Task 01)."""
from __future__ import annotations

import pytest

from the_door.core.extraction.language_configs import (
    LANGUAGE_CONFIGS,
    LanguageConfig,
)


class TestLanguageConfigSchema:
    """LanguageConfig must expose 6 new optional extraction-rule fields."""

    def test_has_parameters_field(self):
        cfg = LanguageConfig()
        assert cfg.parameters_field is None  # default

    def test_has_return_type_field(self):
        cfg = LanguageConfig()
        assert cfg.return_type_field is None

    def test_has_doc_comment_strategy(self):
        cfg = LanguageConfig()
        assert cfg.doc_comment_strategy is None

    def test_has_doc_comment_types_default_empty_frozenset(self):
        cfg = LanguageConfig()
        assert cfg.doc_comment_types == frozenset()

    def test_has_doc_comment_markers_default_empty_frozenset(self):
        cfg = LanguageConfig()
        assert cfg.doc_comment_markers == frozenset()

    def test_has_decorator_types_default_empty_frozenset(self):
        cfg = LanguageConfig()
        assert cfg.decorator_types == frozenset()

    def test_legacy_fields_still_present(self):
        cfg = LanguageConfig()
        assert cfg.function_types == frozenset()
        assert cfg.method_types == frozenset()
        assert cfg.class_types == frozenset()
        assert cfg.container_types == frozenset()

    def test_dataclass_is_frozen(self):
        cfg = LanguageConfig()
        with pytest.raises(Exception):  # FrozenInstanceError
            cfg.parameters_field = "foo"  # type: ignore[misc]


class TestLanguageRules:
    """Each registered language gets its extraction-rule fields populated."""

    @pytest.mark.parametrize("lang", ["java", "go", "rust", "ruby", "php", "csharp"])
    def test_language_has_parameters_field(self, lang):
        cfg = LANGUAGE_CONFIGS[lang]
        assert cfg.parameters_field is not None, f"{lang} missing parameters_field"

    def test_rust_doc_comment_markers_have_both_outer_and_inner(self):
        cfg = LANGUAGE_CONFIGS["rust"]
        assert "///" in cfg.doc_comment_markers
        assert "//!" in cfg.doc_comment_markers

    def test_rust_decorator_types_include_attribute_item(self):
        cfg = LANGUAGE_CONFIGS["rust"]
        assert "attribute_item" in cfg.decorator_types

    def test_java_decorator_types_include_annotation(self):
        cfg = LANGUAGE_CONFIGS["java"]
        assert "annotation" in cfg.decorator_types
        assert "marker_annotation" in cfg.decorator_types

    def test_csharp_doc_comment_marker_triple_slash(self):
        cfg = LANGUAGE_CONFIGS["csharp"]
        assert "///" in cfg.doc_comment_markers

    def test_php_doc_comment_marker_phpdoc(self):
        cfg = LANGUAGE_CONFIGS["php"]
        assert "/**" in cfg.doc_comment_markers

    def test_go_no_doc_comment_markers(self):
        cfg = LANGUAGE_CONFIGS["go"]
        assert cfg.doc_comment_markers == frozenset()

    def test_ruby_no_decorator_types(self):
        cfg = LANGUAGE_CONFIGS["ruby"]
        assert cfg.decorator_types == frozenset()

    @pytest.mark.parametrize("lang,strategy", [
        ("java", "preceding_block_comment"),
        ("go", "preceding_line_comments"),
        ("rust", "preceding_line_comments"),
        ("ruby", "preceding_line_comments"),
        ("php", "preceding_block_comment"),
        ("csharp", "preceding_line_comments"),
    ])
    def test_doc_comment_strategy(self, lang, strategy):
        cfg = LANGUAGE_CONFIGS[lang]
        assert cfg.doc_comment_strategy == strategy

    def test_python_typescript_javascript_not_extended(self):
        """專用 walker 處理 — config-driven 欄位保持預設。"""
        for lang in ("python", "typescript", "javascript"):
            if lang not in LANGUAGE_CONFIGS:
                continue
            cfg = LANGUAGE_CONFIGS[lang]
            assert cfg.parameters_field is None
            assert cfg.doc_comment_strategy is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest the_door/tests/unit/core/extraction/test_language_configs.py -v`
Expected: FAIL with `AttributeError` 或 `TypeError`（欄位不存在）。

- [ ] **Step 3: Extend LanguageConfig dataclass**

Edit `the_door/src/the_door/core/extraction/language_configs.py`. Replace the existing `LanguageConfig` dataclass with:

```python
@dataclass(frozen=True)
class LanguageConfig:
    # ── 既有欄位（節點識別，codegraph 引入時就有） ──
    function_types: frozenset[str] = field(default_factory=frozenset)
    method_types: frozenset[str] = field(default_factory=frozenset)
    class_types: frozenset[str] = field(default_factory=frozenset)
    container_types: frozenset[str] = field(default_factory=frozenset)

    # ── 新增欄位（detail 模式 ASTNode 充實用，Task 02/03 會用） ──
    parameters_field: str | None = None
    """tree-sitter field name for parameters node, e.g. "parameters"."""

    return_type_field: str | None = None
    """tree-sitter field name for return type node, e.g. "return_type"."""

    doc_comment_strategy: str | None = None
    """如何尋找 doc comment：
    - "preceding_line_comments"：往前掃連續的 line comment 節點
    - "preceding_block_comment"：往前掃單一 block comment 節點
    - None：不抽 doc comment
    """

    doc_comment_types: frozenset[str] = field(default_factory=frozenset)
    """tree-sitter comment node types 集合（如 {"line_comment", "block_comment"}）。"""

    doc_comment_markers: frozenset[str] = field(default_factory=frozenset)
    """選填的 doc-comment 前綴字串集合。空 = 接受所有匹配 type 的註解；
    非空 = 只保留以集合內某個字串開頭的註解。
    e.g. Rust {"///", "//!"} 區分 outer/inner doc；C# {"///"}。"""

    decorator_types: frozenset[str] = field(default_factory=frozenset)
    """tree-sitter 節點型別中視為 decorator / annotation / attribute 的集合。
    輸出寫入 ASTNode.decorators（與 Python/TS walker 行為對齊）。
    e.g. Rust {"attribute_item"}、Java {"annotation", "marker_annotation"}。"""
```

- [ ] **Step 4: Populate 6 language entries**

Replace the existing `LANGUAGE_CONFIGS` dict entries for java/go/rust/ruby/php/csharp with extraction rules added. Keep node-type fields unchanged; only **add** the new fields. Example for java:

```python
LANGUAGE_CONFIGS: dict[str, LanguageConfig] = {
    "java": LanguageConfig(
        function_types=frozenset(),
        method_types=frozenset({"method_declaration", "constructor_declaration"}),
        class_types=frozenset({"class_declaration", "interface_declaration", "enum_declaration"}),
        parameters_field="parameters",
        return_type_field="type",
        doc_comment_strategy="preceding_block_comment",
        doc_comment_types=frozenset({"block_comment"}),
        doc_comment_markers=frozenset(),
        decorator_types=frozenset({"annotation", "marker_annotation"}),
    ),
    "go": LanguageConfig(
        function_types=frozenset({"function_declaration"}),
        method_types=frozenset({"method_declaration"}),
        class_types=frozenset(),
        parameters_field="parameters",
        return_type_field="result",
        doc_comment_strategy="preceding_line_comments",
        doc_comment_types=frozenset({"comment"}),
        doc_comment_markers=frozenset(),
        decorator_types=frozenset(),
    ),
    "rust": LanguageConfig(
        function_types=frozenset({"function_item"}),
        method_types=frozenset({"function_item"}),
        class_types=frozenset({"struct_item", "enum_item", "trait_item"}),
        container_types=frozenset({"impl_item"}),
        parameters_field="parameters",
        return_type_field="return_type",
        doc_comment_strategy="preceding_line_comments",
        doc_comment_types=frozenset({"line_comment", "block_comment"}),
        doc_comment_markers=frozenset({"///", "//!"}),
        decorator_types=frozenset({"attribute_item"}),
    ),
    "ruby": LanguageConfig(
        function_types=frozenset({"method"}),
        method_types=frozenset({"method", "singleton_method"}),
        class_types=frozenset({"class"}),
        parameters_field="method_parameters",
        return_type_field=None,
        doc_comment_strategy="preceding_line_comments",
        doc_comment_types=frozenset({"comment"}),
        doc_comment_markers=frozenset(),
        decorator_types=frozenset(),
    ),
    "php": LanguageConfig(
        function_types=frozenset({"function_definition"}),
        method_types=frozenset({"method_declaration"}),
        class_types=frozenset({
            "class_declaration", "trait_declaration",
            "interface_declaration", "enum_declaration",
        }),
        parameters_field="formal_parameters",
        return_type_field="return_type",
        doc_comment_strategy="preceding_block_comment",
        doc_comment_types=frozenset({"comment"}),
        doc_comment_markers=frozenset({"/**"}),
        decorator_types=frozenset(),
    ),
    "csharp": LanguageConfig(
        function_types=frozenset(),
        method_types=frozenset({"method_declaration", "constructor_declaration"}),
        class_types=frozenset({
            "class_declaration", "interface_declaration",
            "struct_declaration", "enum_declaration",
        }),
        parameters_field="parameter_list",
        return_type_field="type",  # 暫填 "type"，落地時以實際 grammar 修正
        doc_comment_strategy="preceding_line_comments",
        doc_comment_types=frozenset({"comment"}),
        doc_comment_markers=frozenset({"///"}),
        decorator_types=frozenset({"attribute_list"}),
    ),
    # ── 不在本任務改動：python / typescript / javascript ──
    # 那些走專用 walker，extraction-rule 欄位保留預設。若 LANGUAGE_CONFIGS
    # 既有檔案中存在 python/typescript/javascript 條目，不要修改。
}
```

> **保留現況提醒**：若現有檔案 `LANGUAGE_CONFIGS` dict 中已有 python / typescript / javascript 條目（用於 fallback path），維持原樣，只動 java/go/rust/ruby/php/csharp 6 條。

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest the_door/tests/unit/core/extraction/test_language_configs.py -v --cov=the_door.core.extraction.language_configs --cov-report=term-missing`

Expected:
- 所有 test PASS
- Coverage 100%

如 coverage < 100%，補測試覆蓋未涵蓋的分支或欄位。

- [ ] **Step 6: Run full test suite for regression**

Run: `pytest the_door/tests/ -x -q`
Expected: 無新增 failure（既有測試應不受影響，因為新欄位有預設值）。

- [ ] **Step 7: Commit**

```bash
git add the_door/src/the_door/core/extraction/language_configs.py the_door/tests/unit/core/extraction/test_language_configs.py
git commit -m "feat(extraction): extend LanguageConfig with detail-mode extraction rules

Add 6 optional fields (parameters_field, return_type_field, doc_comment_*,
decorator_types) for upcoming _walk_config_driven enrichment. Populate
java/go/rust/ruby/php/csharp with tree-sitter field name mappings.
Python/TS walkers unaffected. Schema-only change; no behavior delta."
```

---

## Acceptance Criteria

- [ ] LanguageConfig 新增 6 個欄位，預設值為 None / 空 frozenset
- [ ] java/go/rust/ruby/php/csharp 6 種語言皆填上 parameters_field 與 doc_comment_strategy
- [ ] Rust doc_comment_markers 同時包含 `///` 與 `//!`
- [ ] python / typescript / javascript 條目（若存在）保持原樣
- [ ] `pytest the_door/tests/unit/core/extraction/test_language_configs.py` 全綠
- [ ] `language_configs.py` line coverage = 100%
- [ ] 既有 pytest 套件無新增 failure
- [ ] Commit 包含 src + test 兩個檔案
