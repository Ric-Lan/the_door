# Task 04 — Go + Rust Scope Rules

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為 Go（`module_path` 策略 + `structural` method dispatch）和 Rust（`module_path` + `trait_dispatch`）填入 `ScopeRules`，並實作 `_parse_module_path_imports` 處理 Go 的 `import "pkg/foo"` 和 Rust 的 `use crate::module::name`。

**Architecture:** 在 `EdgeBuilder._parse_module_path_imports`（目前 stub）中以 tree-sitter node type 雙語言通用解析：擷取最後一個 path segment 作為 alias 與 name。Go 與 Rust 雖然 grammar 不同，但「path 最後一段即本地名稱」的語意一致，可以共用同一個解析器並各自 walk。

**Pre-requisite:** Task 01 + Task 02 完成（Task 03 不必先做）。

**Tech Stack:** Python 3.11+, tree-sitter-languages, pytest, pytest-cov。

**Test Coverage Requirement:**

```
pytest the_door/tests/unit/core/extraction/test_go_rust_scope_rules.py -v \
  --cov=the_door.core.extraction.edge_builder \
  --cov=the_door.core.extraction.language_configs \
  --cov-fail-under=100
```

---

## Background（自含）

**Go import 語法 → tree-sitter node types：**

| 語法 | node type | 結構 |
|---|---|---|
| `import "fmt"` | `import_declaration` → `import_spec` → `interpreted_string_literal` | path string |
| `import f "fmt"` | `import_declaration` → `import_spec` → `package_identifier`(f), `interpreted_string_literal` | alias 在前 |
| `import ( "fmt"; "os" )` | `import_declaration` → `import_spec_list` → 多個 `import_spec` | group import |

Go 「import path」是字串字面值，最後一段（`"orders/validator"` → `validator`）是套件名，可被當作 local name 使用。

**Rust use 語法 → tree-sitter node types：**

| 語法 | node type | 結構 |
|---|---|---|
| `use crate::orders::Validator;` | `use_declaration` → `scoped_identifier` | path segments |
| `use crate::orders::Validator as V;` | `use_declaration` → `use_as_clause` → {`scoped_identifier`, `identifier`} | alias |
| `use crate::orders::{Validator, Processor};` | `use_declaration` → `scoped_use_list` → 多個 `identifier` | group use |

**目前狀態：**
- `EdgeBuilder._parse_module_path_imports` 是 stub，回傳 `{}`
- `LANGUAGE_CONFIGS["go"]` 和 `LANGUAGE_CONFIGS["rust"]` 無 `scope_rules`

---

## Files

- Modify: `the_door/src/the_door/core/extraction/edge_builder.py`
- Modify: `the_door/src/the_door/core/extraction/language_configs.py`
- Test (new): `the_door/tests/unit/core/extraction/test_go_rust_scope_rules.py`

---

## Steps

### Step 1 — 寫 failing tests

- [ ] **Step 1: 建立測試檔案**

新增 `the_door/tests/unit/core/extraction/test_go_rust_scope_rules.py`：

```python
"""Tests for Task 04 — Go + Rust (module_path) scope rules."""
from __future__ import annotations

import pytest
import tree_sitter

from the_door.core.extraction.edge_builder import EdgeBuilder
from the_door.core.extraction.language_configs import LANGUAGE_CONFIGS, ScopeRules


# Inline parser helper — 專案用個別 tree_sitter_<lang> 套件，不是 tree_sitter_languages
_LANG_LOADERS = {
    "go":   ("tree_sitter_go",   "language"),
    "rust": ("tree_sitter_rust", "language"),
}


def _parse(lang: str, source: str):
    mod_name, attr = _LANG_LOADERS[lang]
    mod = __import__(mod_name)
    parser = tree_sitter.Parser(tree_sitter.Language(getattr(mod, attr)()))
    tree = parser.parse(source.encode())
    return tree, source.encode()


def _module_path_rules():
    return ScopeRules(
        import_resolution="module_path",
        function_resolution="package_local_then_imports",
        method_resolution="structural",
        inheritance_resolution="interface_only",
    )


# ── Go: module_path import parsing ────────────────────────────────────────────

class TestGoModulePathImports:
    def setup_method(self):
        self.builder = EdgeBuilder()

    def test_simple_import(self):
        tree, src = _parse("go", 'package main\nimport "fmt"\n')
        aliases = self.builder._parse_import_aliases(tree.root_node, src, _module_path_rules())
        assert aliases.get("fmt") == "fmt"

    def test_import_with_subpath(self):
        tree, src = _parse("go", 'package main\nimport "example.com/orders/validator"\n')
        aliases = self.builder._parse_import_aliases(tree.root_node, src, _module_path_rules())
        assert aliases.get("validator") == "validator"

    def test_aliased_import(self):
        tree, src = _parse("go", 'package main\nimport v "example.com/orders/validator"\n')
        aliases = self.builder._parse_import_aliases(tree.root_node, src, _module_path_rules())
        assert aliases.get("v") == "validator"

    def test_grouped_imports(self):
        source = 'package main\nimport (\n  "fmt"\n  "os"\n)\n'
        tree, src = _parse("go", source)
        aliases = self.builder._parse_import_aliases(tree.root_node, src, _module_path_rules())
        assert "fmt" in aliases
        assert "os" in aliases

    def test_no_imports_returns_empty(self):
        tree, src = _parse("go", "package main\nfunc main() {}\n")
        aliases = self.builder._parse_import_aliases(tree.root_node, src, _module_path_rules())
        assert aliases == {}


# ── Rust: module_path use parsing ────────────────────────────────────────────

class TestRustModulePathImports:
    def setup_method(self):
        self.builder = EdgeBuilder()

    def test_simple_use(self):
        tree, src = _parse("rust", "use crate::orders::Validator;\n")
        aliases = self.builder._parse_import_aliases(tree.root_node, src, _module_path_rules())
        assert aliases.get("Validator") == "Validator"

    def test_use_with_alias(self):
        tree, src = _parse("rust", "use crate::orders::Validator as V;\n")
        aliases = self.builder._parse_import_aliases(tree.root_node, src, _module_path_rules())
        assert aliases.get("V") == "Validator"

    def test_use_list(self):
        tree, src = _parse("rust", "use crate::orders::{Validator, Processor};\n")
        aliases = self.builder._parse_import_aliases(tree.root_node, src, _module_path_rules())
        assert "Validator" in aliases
        assert "Processor" in aliases

    def test_no_use_returns_empty(self):
        tree, src = _parse("rust", "fn main() {}\n")
        aliases = self.builder._parse_import_aliases(tree.root_node, src, _module_path_rules())
        assert aliases == {}


# ── LANGUAGE_CONFIGS for go and rust ─────────────────────────────────────────

class TestGoRustLanguageConfigs:
    def test_go_scope_rules(self):
        cfg = LANGUAGE_CONFIGS.get("go")
        assert cfg is not None
        assert cfg.scope_rules is not None
        assert cfg.scope_rules.import_resolution == "module_path"
        assert cfg.scope_rules.function_resolution == "package_local_then_imports"
        assert cfg.scope_rules.method_resolution == "structural"
        assert cfg.scope_rules.inheritance_resolution == "interface_only"
        assert "reflect_value_call" in cfg.scope_rules.dynamic_markers

    def test_rust_scope_rules(self):
        cfg = LANGUAGE_CONFIGS.get("rust")
        assert cfg is not None
        assert cfg.scope_rules is not None
        assert cfg.scope_rules.import_resolution == "module_path"
        assert cfg.scope_rules.function_resolution == "package_local_then_imports"
        assert cfg.scope_rules.method_resolution == "trait_dispatch"
        assert cfg.scope_rules.inheritance_resolution == "single"
        assert "dyn_trait_call" in cfg.scope_rules.dynamic_markers
```

- [ ] **Step 2: 執行，確認 FAIL**

```
cd the_door
pytest tests/unit/core/extraction/test_go_rust_scope_rules.py -v 2>&1 | head -20
```

---

### Step 2 — 實作 `_parse_module_path_imports`

- [ ] **Step 3: 替換 stub**

在 `edge_builder.py` 找到：

```python
    def _parse_module_path_imports(self, root: TSNode, source_bytes: bytes) -> dict[str, str]:
        """Go/Rust: use/import path statements → {last_segment: last_segment}."""
        # Implemented in Task 04
        return {}
```

改成：

```python
    def _parse_module_path_imports(self, root: TSNode, source_bytes: bytes) -> dict[str, str]:
        """Go (import "path") and Rust (use path::name [as alias]) → {alias: name}."""
        aliases: dict[str, str] = {}
        self._walk_module_path_imports(root, source_bytes, aliases)
        return aliases

    def _walk_module_path_imports(
        self, node: TSNode, source_bytes: bytes, aliases: dict[str, str]
    ) -> None:
        # Go: import_spec (under import_declaration / import_spec_list)
        if node.type == "import_spec":
            self._extract_go_import_spec(node, aliases)
        # Rust: use_declaration → may contain scoped_identifier / use_as_clause / scoped_use_list
        if node.type == "use_declaration":
            for child in node.children:
                self._extract_rust_use_item(child, aliases)
        for child in node.children:
            self._walk_module_path_imports(child, source_bytes, aliases)

    def _extract_go_import_spec(self, spec: TSNode, aliases: dict[str, str]) -> None:
        alias = None
        path = None
        for child in spec.children:
            if child.type == "package_identifier":
                alias = child.text.decode("utf-8", errors="replace")
            elif child.type in ("interpreted_string_literal", "raw_string_literal"):
                raw = child.text.decode("utf-8", errors="replace").strip().strip('"').strip("`")
                path = raw
        if path:
            last_segment = path.rstrip("/").split("/")[-1]
            if alias:
                aliases[alias] = last_segment
            elif last_segment.isidentifier():
                aliases[last_segment] = last_segment

    def _extract_rust_use_item(self, node: TSNode, aliases: dict[str, str]) -> None:
        if node.type == "scoped_identifier":
            text = node.text.decode("utf-8", errors="replace")
            last = text.split("::")[-1].strip()
            if last.isidentifier():
                aliases[last] = last
        elif node.type == "use_as_clause":
            orig = None
            alias = None
            for child in node.children:
                if child.type == "scoped_identifier":
                    orig = child.text.decode("utf-8", errors="replace").split("::")[-1].strip()
                elif child.type == "identifier" and orig is not None:
                    alias = child.text.decode("utf-8", errors="replace")
            if orig and alias:
                aliases[alias] = orig
        elif node.type == "scoped_use_list":
            for child in node.children:
                if child.type == "use_list":
                    for item in child.children:
                        if item.type == "identifier":
                            name = item.text.decode("utf-8", errors="replace")
                            aliases[name] = name
                        elif item.type == "use_as_clause":
                            self._extract_rust_use_item(item, aliases)
        elif node.type == "identifier":
            # bare `use foo;` (rare)
            name = node.text.decode("utf-8", errors="replace")
            if name.isidentifier():
                aliases[name] = name
```

- [ ] **Step 4: Go + Rust import 解析測試 PASS**

```
cd the_door
pytest tests/unit/core/extraction/test_go_rust_scope_rules.py::TestGoModulePathImports tests/unit/core/extraction/test_go_rust_scope_rules.py::TestRustModulePathImports -v
```

若失敗，加 `print(tree.root_node.sexp())` 在測試裡查看 tree-sitter 實際 node types 並修正 case。

---

### Step 3 — 填入 LANGUAGE_CONFIGS

- [ ] **Step 5: Go scope_rules**

在 `language_configs.py` 找到 `"go"` entry，在最後一欄位後加入：

```python
    scope_rules=ScopeRules(
        import_resolution="module_path",
        function_resolution="package_local_then_imports",
        method_resolution="structural",
        inheritance_resolution="interface_only",
        dynamic_markers=frozenset({"reflect_value_call"}),
    ),
```

- [ ] **Step 6: Rust scope_rules**

找到 `"rust"` entry，加入：

```python
    scope_rules=ScopeRules(
        import_resolution="module_path",
        function_resolution="package_local_then_imports",
        method_resolution="trait_dispatch",
        inheritance_resolution="single",
        dynamic_markers=frozenset({"dyn_trait_call"}),
    ),
```

- [ ] **Step 7: Config 測試 PASS**

```
cd the_door
pytest tests/unit/core/extraction/test_go_rust_scope_rules.py::TestGoRustLanguageConfigs -v
```

---

### Step 4 — 全套驗收

- [ ] **Step 8: Coverage**

```
cd the_door
pytest tests/unit/core/extraction/test_go_rust_scope_rules.py -v \
  --cov=the_door.core.extraction.edge_builder \
  --cov=the_door.core.extraction.language_configs \
  --cov-fail-under=100
```

- [ ] **Step 9: 全套回歸**

```
cd the_door
pytest tests/ -q 2>&1 | tail -5
```

- [ ] **Step 10: Commit**

```
git add the_door/src/the_door/core/extraction/edge_builder.py \
        the_door/src/the_door/core/extraction/language_configs.py \
        the_door/tests/unit/core/extraction/test_go_rust_scope_rules.py
git commit -m "feat(edge): Go and Rust (module_path) scope rules"
```
