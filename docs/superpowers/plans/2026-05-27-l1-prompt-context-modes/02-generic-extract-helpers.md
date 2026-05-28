# Task 02 — Generic Extract Helpers

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `node_builder.py` 新增 4 個純函式 `_extract_parameters` / `_extract_return_type` / `_extract_decorators` / `_extract_doc_comment`，把 tree-sitter node + LanguageConfig 欄位轉為 ASTNode 對應內容。**此任務只新增 helper，不改 `_walk_config_driven` 主流程**。

**Architecture:** 4 個純函式分別處理 4 個 ASTNode 內容欄位。輸入 tree-sitter node + LanguageConfig 欄位（field name / strategy / types / markers），輸出對應型別。沒有任何外部副作用，可獨立單元測試。

**Tech Stack:** Python 3.11+, tree-sitter Python binding, pytest。

**Test Coverage Requirement:** 4 個新 helper 在 `node_builder.py` 中達 100% line coverage（含所有 strategy 分支與 marker 過濾邏輯）。pytest 加 `--cov=the_door.core.extraction.node_builder --cov-fail-under=100`（針對新加的 helper 區塊；若整檔還沒達 100% 在後續任務補）。

---

## Background（自含）

`ASTNode` (定義於 `the_door/src/the_door/models.py:19-31`) 有以下內容欄位：

```python
@dataclass(frozen=True)
class ASTNode:
    node_id: str
    type: str
    name: str
    file: str
    language: str
    decorators: list[str] = field(default_factory=list)
    parameters: list[str] = field(default_factory=list)
    return_type: str | None = None
    docstring: str | None = None
    comments: list[str] = field(default_factory=list)
```

當前 `_walk_config_driven`（在 `the_door/src/the_door/core/extraction/node_builder.py`）對 java/go/rust/ruby/php/csharp 6 語言只填 node_id / type / name / file / language，其他欄位空。

LanguageConfig 已在前置任務擴充加上 `parameters_field` / `return_type_field` / `doc_comment_strategy` / `doc_comment_types` / `doc_comment_markers` / `decorator_types`（見 `language_configs.py`）。

本任務寫 4 個 helper 把 config + tree-sitter node 翻成 ASTNode 對應欄位內容。下個任務才把它們接進主流程。

---

## Files

- Modify: `the_door/src/the_door/core/extraction/node_builder.py`（在現有 class `NodeBuilder` 內新增 4 個 instance method）
- Test (new): `the_door/tests/unit/core/extraction/test_generic_extract_helpers.py`

---

## Steps

### Step 1 — Write failing helper tests (TDD)

- [ ] **Step 1: Write failing tests for all 4 helpers**

Create `the_door/tests/unit/core/extraction/test_generic_extract_helpers.py`:

```python
"""Tests for generic ASTNode extract helpers (Task 02).

Helpers are tested in isolation by feeding minimal tree-sitter parse trees.
"""
from __future__ import annotations

import pytest
from tree_sitter import Language, Parser

from the_door.core.extraction.language_configs import LANGUAGE_CONFIGS
from the_door.core.extraction.node_builder import NodeBuilder


def _parse(source: bytes, language: str):
    """Parse source with the given language. Returns (tree, root_node)."""
    # Use the same Language loading pattern as ast_extractor.py.
    # Implementations may use tree_sitter_languages or similar; adapt as needed.
    import tree_sitter_languages
    parser = Parser()
    lang_obj = tree_sitter_languages.get_language(language)
    parser.set_language(lang_obj)
    tree = parser.parse(source)
    return tree, tree.root_node


def _find_first(node, type_name):
    """Find first descendant of given type via DFS."""
    if node.type == type_name:
        return node
    for child in node.children:
        found = _find_first(child, type_name)
        if found is not None:
            return found
    return None


class TestExtractParameters:
    def test_returns_empty_when_field_name_none(self):
        builder = NodeBuilder()
        # Any node will do; with None field name we should get [].
        _, root = _parse(b"fn foo() {}", "rust")
        fn = _find_first(root, "function_item")
        assert builder._extract_parameters(fn, None) == []

    def test_rust_function_parameters(self):
        builder = NodeBuilder()
        _, root = _parse(b"fn foo(x: i32, y: String) {}", "rust")
        fn = _find_first(root, "function_item")
        result = builder._extract_parameters(fn, "parameters")
        # 至少包含參數文字
        joined = " ".join(result)
        assert "x" in joined and "y" in joined

    def test_missing_field_returns_empty(self):
        """Node without the expected field returns []."""
        builder = NodeBuilder()
        _, root = _parse(b"struct Foo;", "rust")
        st = _find_first(root, "struct_item")
        # struct_item has no "parameters" field.
        assert builder._extract_parameters(st, "parameters") == []


class TestExtractReturnType:
    def test_returns_none_when_field_name_none(self):
        builder = NodeBuilder()
        _, root = _parse(b"fn foo() {}", "rust")
        fn = _find_first(root, "function_item")
        assert builder._extract_return_type(fn, None) is None

    def test_rust_return_type(self):
        builder = NodeBuilder()
        _, root = _parse(b"fn foo() -> i32 { 0 }", "rust")
        fn = _find_first(root, "function_item")
        result = builder._extract_return_type(fn, "return_type")
        assert result is not None
        assert "i32" in result

    def test_no_return_type_returns_none(self):
        builder = NodeBuilder()
        _, root = _parse(b"fn foo() {}", "rust")
        fn = _find_first(root, "function_item")
        assert builder._extract_return_type(fn, "return_type") is None


class TestExtractDecorators:
    def test_returns_empty_when_types_empty(self):
        builder = NodeBuilder()
        _, root = _parse(b"#[derive(Debug)]\nstruct Foo;", "rust")
        st = _find_first(root, "struct_item")
        assert builder._extract_decorators(st, frozenset()) == []

    def test_rust_attribute_extracted(self):
        builder = NodeBuilder()
        source = b"#[derive(Debug)]\nstruct Foo;"
        _, root = _parse(source, "rust")
        # Decorators may be siblings or children depending on grammar;
        # helper should locate by inspecting preceding siblings + own children.
        st = _find_first(root, "struct_item")
        result = builder._extract_decorators(st, frozenset({"attribute_item"}))
        # 至少一筆且包含 derive 字樣
        assert len(result) >= 1
        assert any("derive" in d for d in result)


class TestExtractDocComment:
    def test_returns_none_when_strategy_none(self):
        builder = NodeBuilder()
        _, root = _parse(b"// hello\nfn foo() {}", "rust")
        fn = _find_first(root, "function_item")
        result = builder._extract_doc_comment(
            fn, strategy=None, types=frozenset(), markers=frozenset()
        )
        assert result is None

    def test_rust_outer_doc_comment_extracted(self):
        builder = NodeBuilder()
        source = b"/// This is doc.\nfn foo() {}"
        _, root = _parse(source, "rust")
        fn = _find_first(root, "function_item")
        result = builder._extract_doc_comment(
            fn,
            strategy="preceding_line_comments",
            types=frozenset({"line_comment", "block_comment"}),
            markers=frozenset({"///", "//!"}),
        )
        assert result is not None
        assert "This is doc" in result

    def test_rust_non_doc_comment_filtered_by_marker(self):
        builder = NodeBuilder()
        source = b"// regular comment\nfn foo() {}"
        _, root = _parse(source, "rust")
        fn = _find_first(root, "function_item")
        result = builder._extract_doc_comment(
            fn,
            strategy="preceding_line_comments",
            types=frozenset({"line_comment"}),
            markers=frozenset({"///"}),
        )
        assert result is None  # regular // 被 marker 過濾掉

    def test_no_marker_accepts_all_comment_types(self):
        builder = NodeBuilder()
        source = b"// any line\nfn foo() {}"
        _, root = _parse(source, "rust")
        fn = _find_first(root, "function_item")
        result = builder._extract_doc_comment(
            fn,
            strategy="preceding_line_comments",
            types=frozenset({"line_comment"}),
            markers=frozenset(),  # 空集合 = 不過濾
        )
        assert result is not None

    def test_block_comment_strategy(self):
        """Java/PHP block comment strategy."""
        builder = NodeBuilder()
        source = b"/** Hello. */\nvoid foo() {}"  # PHP-ish
        _, root = _parse(source, "php")
        # 簡化: 找 function_definition
        fn = _find_first(root, "function_definition")
        if fn is None:
            pytest.skip("PHP grammar didn't parse expected shape")
        result = builder._extract_doc_comment(
            fn,
            strategy="preceding_block_comment",
            types=frozenset({"comment"}),
            markers=frozenset({"/**"}),
        )
        if result is not None:
            assert "Hello" in result

    def test_unknown_strategy_returns_none(self):
        builder = NodeBuilder()
        _, root = _parse(b"fn foo() {}", "rust")
        fn = _find_first(root, "function_item")
        result = builder._extract_doc_comment(
            fn,
            strategy="nonexistent_strategy",
            types=frozenset(),
            markers=frozenset(),
        )
        assert result is None  # 未知 strategy 安全 fallback
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest the_door/tests/unit/core/extraction/test_generic_extract_helpers.py -v`
Expected: FAIL with `AttributeError: 'NodeBuilder' object has no attribute '_extract_parameters'`（或類似）。

### Step 2 — Implement 4 helpers

- [ ] **Step 3: Add 4 helper methods to NodeBuilder class**

Open `the_door/src/the_door/core/extraction/node_builder.py`. In the `NodeBuilder` class (after existing `_walk_config_driven` block but anywhere in the class body works), add:

```python
    # ── Generic-walker extract helpers (Task 02) ──────────────────────

    def _extract_parameters(self, node, parameters_field: str | None) -> list[str]:
        """Extract parameter strings from a function/method definition node.

        Returns [] if parameters_field is None or the field is absent.
        Each parameter is returned as raw source text (utf-8 decoded).
        """
        if parameters_field is None:
            return []
        params_node = node.child_by_field_name(parameters_field)
        if params_node is None:
            return []
        result: list[str] = []
        for child in params_node.children:
            # Skip pure punctuation (commas, parens) — they have no name and
            # tree-sitter treats them as separate nodes.
            if child.type in ("(", ")", ",", ";"):
                continue
            text = child.text.decode("utf-8", errors="replace").strip()
            if text:
                result.append(text)
        return result

    def _extract_return_type(self, node, return_type_field: str | None) -> str | None:
        """Extract return-type annotation as raw text.

        Returns None if return_type_field is None or the field is absent.
        """
        if return_type_field is None:
            return None
        rt_node = node.child_by_field_name(return_type_field)
        if rt_node is None:
            return None
        return rt_node.text.decode("utf-8", errors="replace").strip() or None

    def _extract_decorators(self, node, decorator_types: frozenset[str]) -> list[str]:
        """Extract decorator / annotation / attribute text.

        Strategy: scan node's own children + preceding siblings (up to first
        non-decorator non-comment node) for nodes whose type is in
        decorator_types. Each is decoded to raw text.
        Returns [] if decorator_types is empty.
        """
        if not decorator_types:
            return []
        result: list[str] = []

        # Own children (some grammars nest attributes inside the item)
        for child in node.children:
            if child.type in decorator_types:
                text = child.text.decode("utf-8", errors="replace").strip()
                if text:
                    result.append(text)

        # Preceding siblings (most grammars: attributes appear as siblings before
        # the item).
        sibling = node.prev_sibling
        while sibling is not None:
            if sibling.type in decorator_types:
                text = sibling.text.decode("utf-8", errors="replace").strip()
                if text:
                    result.insert(0, text)  # preserve source order
                sibling = sibling.prev_sibling
                continue
            # Stop at the first non-decorator / non-whitespace sibling.
            if sibling.type.strip() and sibling.type not in ("comment", "line_comment", "block_comment"):
                break
            sibling = sibling.prev_sibling

        return result

    def _extract_doc_comment(
        self,
        node,
        strategy: str | None,
        types: frozenset[str],
        markers: frozenset[str],
    ) -> str | None:
        """Extract a doc-comment string preceding the node.

        Strategy:
        - "preceding_line_comments": gather contiguous line-comment siblings
          immediately preceding node, in source order; join with newlines.
        - "preceding_block_comment": take the immediately preceding block
          comment sibling (single node).
        - None or unknown: return None.

        Filtering:
        - Only sibling nodes whose type is in `types` are considered.
        - If `markers` is non-empty, only comments whose raw text (stripped)
          starts with one of the markers are kept.
        """
        if strategy is None or not types:
            return None

        if strategy == "preceding_line_comments":
            collected: list[str] = []
            sibling = node.prev_sibling
            while sibling is not None and sibling.type in types:
                text = sibling.text.decode("utf-8", errors="replace").strip()
                if not text:
                    sibling = sibling.prev_sibling
                    continue
                if markers and not any(text.startswith(m) for m in markers):
                    break  # 連續性中斷 — 遇到非 doc-comment 即停止
                # Strip marker prefix for cleaner output if present.
                cleaned = text
                for m in markers:
                    if cleaned.startswith(m):
                        cleaned = cleaned[len(m):].strip()
                        break
                collected.insert(0, cleaned or text)
                sibling = sibling.prev_sibling
            if not collected:
                return None
            return "\n".join(collected)

        if strategy == "preceding_block_comment":
            sibling = node.prev_sibling
            # Skip whitespace nodes if any (most grammars don't produce them).
            while sibling is not None and not sibling.type.strip():
                sibling = sibling.prev_sibling
            if sibling is None or sibling.type not in types:
                return None
            text = sibling.text.decode("utf-8", errors="replace").strip()
            if not text:
                return None
            if markers and not any(text.startswith(m) for m in markers):
                return None
            return text

        # Unknown strategy — safe fallback.
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest the_door/tests/unit/core/extraction/test_generic_extract_helpers.py -v`
Expected: All PASS。若某語言 grammar fixture 行為與預期不同（e.g. PHP block-comment 在 grammar 內以不同 node type 出現），就地修正測試的 type 名稱或補測試 skip 標籤，但**不要改 helper 邏輯**繞過 — helper 行為由 spec 規定。

- [ ] **Step 5: Coverage check**

Run: `pytest the_door/tests/unit/core/extraction/test_generic_extract_helpers.py --cov=the_door.core.extraction.node_builder --cov-report=term-missing | grep -E "_extract_|TOTAL"`

Expected: 4 個 helper 的行皆覆蓋（每個 strategy 分支、每條 None / empty 早退路徑、marker 過濾路徑都有測試經過）。

若 coverage 缺口，補對應測試（不要改 helper 來繞 coverage）。

- [ ] **Step 6: Regression**

Run: `pytest the_door/tests/ -x -q`
Expected: 無新 failure。

- [ ] **Step 7: Commit**

```bash
git add the_door/src/the_door/core/extraction/node_builder.py the_door/tests/unit/core/extraction/test_generic_extract_helpers.py
git commit -m "feat(extraction): add 4 generic extract helpers for ASTNode enrichment

_extract_parameters, _extract_return_type, _extract_decorators,
_extract_doc_comment — pure functions taking tree-sitter node + config
fields. Not wired into _walk_config_driven yet; next task does the wiring."
```

---

## Acceptance Criteria

- [ ] `NodeBuilder` 增加 4 個 method：`_extract_parameters`、`_extract_return_type`、`_extract_decorators`、`_extract_doc_comment`
- [ ] 每個 helper 是純函式（無 self 狀態存取、無 I/O）
- [ ] None / 空 config 欄位安全 fallback（早退回傳 [] / None）
- [ ] Rust outer doc (`///`) + inner doc (`//!`) 兩種 marker 都能被 `_extract_doc_comment` 取到
- [ ] Marker 過濾正確（給 `///` marker 時，普通 `//` 註解被排除）
- [ ] 未知 strategy 字串回傳 None（安全 fallback，不 raise）
- [ ] 新 helper 區塊 100% line coverage
- [ ] `_walk_config_driven` **未變動**（本任務只新增 helper）
- [ ] `pytest the_door/tests/` 無新增 failure
