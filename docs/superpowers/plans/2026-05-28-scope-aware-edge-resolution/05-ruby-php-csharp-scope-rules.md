# Task 05 — Ruby + PHP + C# Scope Rules

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為 Ruby（簡化版 — `method_resolution=dynamic_dispatch`，所有 method 邊強制 skipped_dynamic）、PHP（`namespaced` + alias）和 C#（`namespaced` + alias）填入 `ScopeRules`，並擴充 `_parse_namespaced_imports` 支援 PHP `use Foo\Bar [as B];` 與 C# `using System.Linq;`。

**Architecture:** Ruby 不需要 import alias parser（即使解析了也無效，因為 step 1 `is_dynamic` 會把所有 method 邊標 skipped_dynamic）。PHP 與 C# 共用 namespaced 策略：擴充 Task 03 已建立的 `_walk_namespaced_imports`，增加 PHP `use_declaration` 與 C# `using_directive` 兩種 node type 處理。

**Pre-requisite:** Task 01 + Task 02 + Task 03（共用 `_parse_namespaced_imports` 入口）。Task 04 不必先做。

**Tech Stack:** Python 3.11+, tree-sitter-languages, pytest, pytest-cov。

**Test Coverage Requirement:**

```
pytest the_door/tests/unit/core/extraction/test_ruby_php_csharp_scope_rules.py -v \
  --cov=the_door.core.extraction.edge_builder \
  --cov=the_door.core.extraction.language_configs \
  --cov-fail-under=100
```

---

## Background（自含）

**為何 Ruby 簡化？**

Ruby 因為 monkey patching、`method_missing`、`define_method`、`send` 等動態 dispatch 太常見，spec §4.3 表格直接設 `method_resolution=dynamic_dispatch`。對應 `EdgeBuilder._resolve()` 修正版 step 1（Task 02 已實作）：

```python
is_dynamic = (
    context.has_dynamic_marker(rules.dynamic_markers)
    or rules.method_resolution == "dynamic_dispatch"
)
if is_dynamic:
    matches = self._name_to_ids.get(name, [])
    return [(m, "skipped_dynamic") for m in matches]
```

→ Ruby 所有 method 邊都會落在 step 1，標 `skipped_dynamic`，承認結構上解不了。本任務 Ruby 部分只需填 `LANGUAGE_CONFIGS["ruby"].scope_rules`，**不需要**寫 Ruby import parser（即使寫了也走不到 step 3）。

**PHP `use` 語法 → tree-sitter node types：**

| 語法 | node type | 結構 |
|---|---|---|
| `use App\Models\User;` | `namespace_use_declaration` → `namespace_use_clause` → `qualified_name` | path |
| `use App\Models\User as U;` | `namespace_use_declaration` → `namespace_use_clause` → `qualified_name`, `name`(U) | alias |
| `use App\Models\{User, Post};` | `namespace_use_declaration` → `namespace_use_group_clause` | group |

**C# `using` 語法 → tree-sitter node types：**

| 語法 | node type | 結構 |
|---|---|---|
| `using System.Linq;` | `using_directive` → `qualified_name` | namespace |
| `using L = System.Linq;` | `using_directive` → `name_equals`(L), `qualified_name` | alias |

**目前狀態：**
- Task 03 已實作 Java 部分的 `_walk_namespaced_imports`，本任務擴充支援 PHP / C#
- `LANGUAGE_CONFIGS["ruby"]`、`["php"]`、`["csharp"]` 都無 `scope_rules`

---

## Files

- Modify: `the_door/src/the_door/core/extraction/edge_builder.py`
- Modify: `the_door/src/the_door/core/extraction/language_configs.py`
- Test (new): `the_door/tests/unit/core/extraction/test_ruby_php_csharp_scope_rules.py`

---

## Steps

### Step 1 — 寫 failing tests

- [ ] **Step 1: 建立測試檔案**

新增 `the_door/tests/unit/core/extraction/test_ruby_php_csharp_scope_rules.py`：

```python
"""Tests for Task 05 — Ruby (dynamic), PHP + C# (namespaced) scope rules."""
from __future__ import annotations

import pytest
import tree_sitter

from the_door.core.extraction.edge_builder import EdgeBuilder
from the_door.core.extraction.language_configs import LANGUAGE_CONFIGS, ScopeContext, ScopeRules


# Inline parser helper — 專案用個別 tree_sitter_<lang> 套件，不是 tree_sitter_languages
_LANG_LOADERS = {
    "ruby":    ("tree_sitter_ruby",    "language"),
    "php":     ("tree_sitter_php",     "language_php"),
    "c_sharp": ("tree_sitter_c_sharp", "language"),
}


def _parse(lang: str, source: str):
    mod_name, attr = _LANG_LOADERS[lang]
    mod = __import__(mod_name)
    parser = tree_sitter.Parser(tree_sitter.Language(getattr(mod, attr)()))
    tree = parser.parse(source.encode())
    return tree, source.encode()


def _ns_rules():
    return ScopeRules(
        import_resolution="namespaced",
        function_resolution="package_local_then_imports",
        method_resolution="class_local_then_inherited",
        inheritance_resolution="single",
    )


# ── PHP namespaced imports ────────────────────────────────────────────────────

class TestPhpNamespacedImports:
    def setup_method(self):
        self.builder = EdgeBuilder()

    def test_simple_use(self):
        source = "<?php\nuse App\\Models\\User;\n"
        tree, src = _parse("php", source)
        aliases = self.builder._parse_import_aliases(tree.root_node, src, _ns_rules())
        assert aliases.get("User") == "User"

    def test_use_with_alias(self):
        source = "<?php\nuse App\\Models\\User as U;\n"
        tree, src = _parse("php", source)
        aliases = self.builder._parse_import_aliases(tree.root_node, src, _ns_rules())
        assert aliases.get("U") == "User"

    def test_no_use_returns_empty(self):
        tree, src = _parse("php", "<?php\nclass Foo {}\n")
        aliases = self.builder._parse_import_aliases(tree.root_node, src, _ns_rules())
        assert aliases == {}


# ── C# using directives ─────────────────────────────────────────────────────

class TestCsharpUsingDirectives:
    def setup_method(self):
        self.builder = EdgeBuilder()

    def test_simple_using(self):
        tree, src = _parse("c_sharp", "using System.Linq;\n")
        aliases = self.builder._parse_import_aliases(tree.root_node, src, _ns_rules())
        assert "Linq" in aliases

    def test_using_with_alias(self):
        tree, src = _parse("c_sharp", "using L = System.Linq;\n")
        aliases = self.builder._parse_import_aliases(tree.root_node, src, _ns_rules())
        assert aliases.get("L") == "Linq"

    def test_no_using_returns_empty(self):
        tree, src = _parse("c_sharp", "class Foo {}\n")
        aliases = self.builder._parse_import_aliases(tree.root_node, src, _ns_rules())
        assert aliases == {}


# ── Ruby: dynamic_dispatch enforces skipped_dynamic ──────────────────────────

class TestRubyDynamicDispatch:
    def test_ruby_scope_rules_method_resolution_is_dynamic_dispatch(self):
        cfg = LANGUAGE_CONFIGS.get("ruby")
        assert cfg is not None
        assert cfg.scope_rules is not None
        assert cfg.scope_rules.method_resolution == "dynamic_dispatch"

    def test_resolve_under_ruby_rules_marks_skipped_dynamic(self):
        """All Ruby method calls go through _resolve() step 1 → skipped_dynamic."""
        builder = EdgeBuilder()
        builder._name_to_ids = {"process": ["a.rb::process", "b.rb::process"]}
        builder._node_map = {}  # not needed for dynamic path
        rules = LANGUAGE_CONFIGS["ruby"].scope_rules
        ctx = ScopeContext(
            current_file="x.rb",
            import_aliases={},
            caller_class=None,
            caller_name="run",
        )
        result = builder._resolve("process", ctx, rules)
        assert all(res == "skipped_dynamic" for _, res in result)
        assert len(result) == 2


# ── LANGUAGE_CONFIGS for ruby / php / csharp ─────────────────────────────────

class TestRubyPhpCsharpConfigs:
    def test_ruby_scope_rules(self):
        cfg = LANGUAGE_CONFIGS["ruby"]
        assert cfg.scope_rules is not None
        assert cfg.scope_rules.import_resolution == "qualified"
        assert cfg.scope_rules.function_resolution == "global"
        assert cfg.scope_rules.method_resolution == "dynamic_dispatch"
        assert cfg.scope_rules.inheritance_resolution == "mixin"
        for marker in ("method_missing", "define_method", "send"):
            assert marker in cfg.scope_rules.dynamic_markers

    def test_php_scope_rules(self):
        cfg = LANGUAGE_CONFIGS["php"]
        assert cfg.scope_rules is not None
        assert cfg.scope_rules.import_resolution == "namespaced"
        assert cfg.scope_rules.function_resolution == "package_local_then_imports"
        assert cfg.scope_rules.method_resolution == "class_local_then_inherited"
        assert cfg.scope_rules.inheritance_resolution == "single"
        for marker in ("__call", "call_user_func"):
            assert marker in cfg.scope_rules.dynamic_markers

    def test_csharp_scope_rules(self):
        cfg = LANGUAGE_CONFIGS["csharp"]
        assert cfg.scope_rules is not None
        assert cfg.scope_rules.import_resolution == "namespaced"
        assert cfg.scope_rules.function_resolution == "package_local_then_imports"
        assert cfg.scope_rules.method_resolution == "class_local_then_inherited"
        assert cfg.scope_rules.inheritance_resolution == "single"
        assert "dynamic" in cfg.scope_rules.dynamic_markers
```

- [ ] **Step 2: 執行，確認 FAIL**

```
cd the_door
pytest tests/unit/core/extraction/test_ruby_php_csharp_scope_rules.py -v 2>&1 | head -20
```

---

### Step 2 — 擴充 `_walk_namespaced_imports` 支援 PHP + C#

- [ ] **Step 3: 修改 `_walk_namespaced_imports`**

在 `edge_builder.py` 找到 Task 03 已建立的 `_walk_namespaced_imports`：

```python
    def _walk_namespaced_imports(
        self, node: TSNode, source_bytes: bytes, aliases: dict[str, str]
    ) -> None:
        # Java: import_declaration
        if node.type == "import_declaration":
            last_name = self._extract_last_qualified_name(node)
            if last_name:
                aliases[last_name] = last_name
        # PHP: use_declaration (handled in Task 05 by extending this method)
        # C#: using_directive (handled in Task 05)
        for child in node.children:
            self._walk_namespaced_imports(child, source_bytes, aliases)
```

改成：

```python
    def _walk_namespaced_imports(
        self, node: TSNode, source_bytes: bytes, aliases: dict[str, str]
    ) -> None:
        # Java: import_declaration → last segment
        if node.type == "import_declaration":
            last_name = self._extract_last_qualified_name(node)
            if last_name:
                aliases[last_name] = last_name

        # PHP: namespace_use_declaration → namespace_use_clause (per clause)
        if node.type == "namespace_use_clause":
            self._extract_php_use_clause(node, aliases)

        # C#: using_directive
        if node.type == "using_directive":
            self._extract_csharp_using(node, aliases)

        for child in node.children:
            self._walk_namespaced_imports(child, source_bytes, aliases)

    def _extract_php_use_clause(self, clause: TSNode, aliases: dict[str, str]) -> None:
        """Extract PHP `use Foo\Bar [as B];` → {B (or Bar): Bar}."""
        orig = None
        alias = None
        for child in clause.children:
            if child.type in ("qualified_name", "name"):
                text = child.text.decode("utf-8", errors="replace")
                last_seg = text.replace("\\", ".").rstrip(".").split(".")[-1].strip()
                if orig is None:
                    orig = last_seg
                else:
                    alias = last_seg
        if orig:
            aliases[alias if alias else orig] = orig

    def _extract_csharp_using(self, node: TSNode, aliases: dict[str, str]) -> None:
        """Extract C# `using [Alias =] System.Linq;` → {Alias (or Linq): Linq}."""
        alias = None
        orig = None
        for child in node.children:
            if child.type == "name_equals":
                # name_equals → identifier "="
                for sub in child.children:
                    if sub.type == "identifier":
                        alias = sub.text.decode("utf-8", errors="replace")
                        break
            elif child.type in ("qualified_name", "identifier"):
                text = child.text.decode("utf-8", errors="replace")
                orig = text.split(".")[-1].strip()
        if orig:
            aliases[alias if alias else orig] = orig
```

- [ ] **Step 4: PHP + C# 解析測試 PASS**

```
cd the_door
pytest tests/unit/core/extraction/test_ruby_php_csharp_scope_rules.py::TestPhpNamespacedImports tests/unit/core/extraction/test_ruby_php_csharp_scope_rules.py::TestCsharpUsingDirectives -v
```

若失敗，加 `print(tree.root_node.sexp())` 並對齊實際 node types。

---

### Step 3 — 填入 LANGUAGE_CONFIGS

- [ ] **Step 5: Ruby scope_rules（簡化版）**

在 `language_configs.py` 找到 `"ruby"` entry，加入：

```python
    scope_rules=ScopeRules(
        import_resolution="qualified",
        function_resolution="global",
        method_resolution="dynamic_dispatch",
        inheritance_resolution="mixin",
        dynamic_markers=frozenset({"method_missing", "define_method", "send"}),
    ),
```

- [ ] **Step 6: PHP scope_rules**

找到 `"php"` entry，加入：

```python
    scope_rules=ScopeRules(
        import_resolution="namespaced",
        function_resolution="package_local_then_imports",
        method_resolution="class_local_then_inherited",
        inheritance_resolution="single",
        dynamic_markers=frozenset({"__call", "call_user_func"}),
    ),
```

- [ ] **Step 7: C# scope_rules**

找到 `"csharp"` entry，加入：

```python
    scope_rules=ScopeRules(
        import_resolution="namespaced",
        function_resolution="package_local_then_imports",
        method_resolution="class_local_then_inherited",
        inheritance_resolution="single",
        dynamic_markers=frozenset({"dynamic"}),
    ),
```

- [ ] **Step 8: Ruby dispatch 與 config 測試 PASS**

```
cd the_door
pytest tests/unit/core/extraction/test_ruby_php_csharp_scope_rules.py::TestRubyDynamicDispatch tests/unit/core/extraction/test_ruby_php_csharp_scope_rules.py::TestRubyPhpCsharpConfigs -v
```

---

### Step 4 — 全套驗收

- [ ] **Step 9: Coverage**

```
cd the_door
pytest tests/unit/core/extraction/test_ruby_php_csharp_scope_rules.py -v \
  --cov=the_door.core.extraction.edge_builder \
  --cov=the_door.core.extraction.language_configs \
  --cov-fail-under=100
```

- [ ] **Step 10: 全套回歸**

```
cd the_door
pytest tests/ -q 2>&1 | tail -5
```

- [ ] **Step 11: Commit**

```
git add the_door/src/the_door/core/extraction/edge_builder.py \
        the_door/src/the_door/core/extraction/language_configs.py \
        the_door/tests/unit/core/extraction/test_ruby_php_csharp_scope_rules.py
git commit -m "feat(edge): Ruby (dynamic_dispatch), PHP and C# (namespaced) scope rules"
```
