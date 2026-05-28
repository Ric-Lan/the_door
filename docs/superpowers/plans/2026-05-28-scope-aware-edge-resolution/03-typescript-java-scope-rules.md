# Task 03 — TypeScript + Java Scope Rules

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為 TypeScript（`es_module` 策略）和 Java（`namespaced` 策略）填入 `ScopeRules`，並實作對應的 import alias 解析方法，使兩種語言的 edge resolution 從 `name_match` 升級到 `scope_rule` / `import_alias`。

**Architecture:** 在 `EdgeBuilder` 的 `_parse_es_module_imports` 和 `_parse_namespaced_imports` 中實作實際解析邏輯（目前為 stub）。在 `LANGUAGE_CONFIGS` 填入 TypeScript 和 Java 的 `scope_rules`。

**Pre-requisite:** Task 01（schema）和 Task 02（EdgeBuilder core）完成。

**Tech Stack:** Python 3.11+, tree-sitter-languages, pytest, pytest-cov。

**Test Coverage Requirement:**

```
pytest the_door/tests/unit/core/extraction/test_ts_java_scope_rules.py -v \
  --cov=the_door.core.extraction.edge_builder \
  --cov=the_door.core.extraction.language_configs \
  --cov-fail-under=100
```

---

## Background（自含）

**TypeScript import 語法 → tree-sitter node types：**

| 語法 | node type | 子節點 |
|---|---|---|
| `import { validate } from './validator'` | `import_statement` | `import_clause` → `named_imports` → `import_specifier` → `identifier` |
| `import { validate as v } from './validator'` | `import_statement` | `import_clause` → `named_imports` → `import_specifier` → `identifier`(validate), `identifier`(v) |
| `import DefaultClass from './file'` | `import_statement` | `import_clause` → `identifier`(DefaultClass) |

`import_specifier` children: `[identifier("validate"), "as" keyword, identifier("v")]`
— 若有兩個 identifier，第一個是 original name，第二個是 alias。
— 若只有一個 identifier，name 和 alias 相同。

**Java import 語法 → tree-sitter node types：**

| 語法 | node type | 子節點 |
|---|---|---|
| `import com.example.orders.Validator;` | `import_declaration` | `scoped_identifier` 或 `identifier` |
| `import static com.example.Validator.validate;` | `import_declaration` | `static` keyword + `scoped_identifier` |

Java 沒有 alias 語法。`import com.example.Validator` → alias 和 name 都是 `"Validator"`（最後一段）。

**目前狀態：**
- `EdgeBuilder._parse_es_module_imports` 是 stub，回傳 `{}`
- `EdgeBuilder._parse_namespaced_imports` 是 stub，回傳 `{}`
- `LANGUAGE_CONFIGS["typescript"]` 沒有 `scope_rules`
- `LANGUAGE_CONFIGS["java"]` 沒有 `scope_rules`

---

## Files

- Modify: `the_door/src/the_door/core/extraction/edge_builder.py`
- Modify: `the_door/src/the_door/core/extraction/language_configs.py`
- Test (new): `the_door/tests/unit/core/extraction/test_ts_java_scope_rules.py`

---

## Steps

### Step 1 — 寫 failing tests

- [ ] **Step 1: 建立測試檔案**

新增 `the_door/tests/unit/core/extraction/test_ts_java_scope_rules.py`：

```python
"""Tests for Task 03 — TypeScript (es_module) and Java (namespaced) scope rules."""
from __future__ import annotations

import pytest
import tree_sitter

from the_door.core.extraction.edge_builder import EdgeBuilder
from the_door.core.extraction.language_configs import LANGUAGE_CONFIGS, ScopeRules


# Inline parser helper — 專案用個別 tree_sitter_<lang> 套件，不是 tree_sitter_languages
_LANG_LOADERS = {
    "typescript": ("tree_sitter_typescript", "language_typescript"),
    "java":       ("tree_sitter_java",       "language"),
}


def _parse(lang: str, source: str):
    mod_name, attr = _LANG_LOADERS[lang]
    mod = __import__(mod_name)
    parser = tree_sitter.Parser(tree_sitter.Language(getattr(mod, attr)()))
    tree = parser.parse(source.encode())
    return tree, source.encode()


# ── TypeScript: es_module import parsing ──────────────────────────────────────

class TestParseEsModuleImports:
    def setup_method(self):
        self.builder = EdgeBuilder()

    def _rules(self):
        return ScopeRules(
            import_resolution="es_module",
            function_resolution="file_local_then_imports",
            method_resolution="class_local_then_inherited",
            inheritance_resolution="single",
        )

    def test_named_import_no_alias(self):
        tree, src = _parse("typescript", "import { validate } from './validator';\n")
        aliases = self.builder._parse_import_aliases(tree.root_node, src, self._rules())
        assert aliases.get("validate") == "validate"

    def test_named_import_with_alias(self):
        tree, src = _parse("typescript", "import { validate as v } from './validator';\n")
        aliases = self.builder._parse_import_aliases(tree.root_node, src, self._rules())
        assert aliases.get("v") == "validate"
        assert "validate" not in aliases  # original name not added separately

    def test_default_import(self):
        tree, src = _parse("typescript", "import Validator from './validator';\n")
        aliases = self.builder._parse_import_aliases(tree.root_node, src, self._rules())
        assert aliases.get("Validator") == "Validator"

    def test_multiple_named_imports(self):
        source = "import { validate as v, process as p } from './service';\n"
        tree, src = _parse("typescript", source)
        aliases = self.builder._parse_import_aliases(tree.root_node, src, self._rules())
        assert aliases.get("v") == "validate"
        assert aliases.get("p") == "process"

    def test_non_import_file_returns_empty(self):
        tree, src = _parse("typescript", "const x = 1;\n")
        aliases = self.builder._parse_import_aliases(tree.root_node, src, self._rules())
        assert aliases == {}


# ── Java: namespaced import parsing ──────────────────────────────────────────

class TestParseNamespacedImports:
    def setup_method(self):
        self.builder = EdgeBuilder()

    def _rules(self):
        return ScopeRules(
            import_resolution="namespaced",
            function_resolution="package_local_then_imports",
            method_resolution="class_local_then_inherited",
            inheritance_resolution="single",
        )

    def test_simple_import(self):
        source = "import com.example.orders.Validator;\n"
        tree, src = _parse("java", source)
        aliases = self.builder._parse_import_aliases(tree.root_node, src, self._rules())
        assert aliases.get("Validator") == "Validator"

    def test_multiple_imports(self):
        source = "import com.example.Validator;\nimport com.example.Processor;\n"
        tree, src = _parse("java", source)
        aliases = self.builder._parse_import_aliases(tree.root_node, src, self._rules())
        assert "Validator" in aliases
        assert "Processor" in aliases

    def test_static_import(self):
        source = "import static com.example.Validator.validate;\n"
        tree, src = _parse("java", source)
        aliases = self.builder._parse_import_aliases(tree.root_node, src, self._rules())
        # validate should be present (last segment of static import)
        assert "validate" in aliases

    def test_no_imports_returns_empty(self):
        source = "class Foo {}\n"
        tree, src = _parse("java", source)
        aliases = self.builder._parse_import_aliases(tree.root_node, src, self._rules())
        assert aliases == {}


# ── LANGUAGE_CONFIGS has scope_rules for typescript and java ─────────────────

class TestLanguageConfigsScopeRules:
    def test_typescript_has_scope_rules(self):
        cfg = LANGUAGE_CONFIGS.get("typescript")
        assert cfg is not None
        assert cfg.scope_rules is not None
        assert cfg.scope_rules.import_resolution == "es_module"
        assert cfg.scope_rules.function_resolution == "file_local_then_imports"
        assert cfg.scope_rules.method_resolution == "class_local_then_inherited"
        assert cfg.scope_rules.inheritance_resolution == "single"

    def test_java_has_scope_rules(self):
        cfg = LANGUAGE_CONFIGS.get("java")
        assert cfg is not None
        assert cfg.scope_rules is not None
        assert cfg.scope_rules.import_resolution == "namespaced"
        assert cfg.scope_rules.function_resolution == "package_local_then_imports"
        assert cfg.scope_rules.method_resolution == "class_local_then_inherited"
        assert cfg.scope_rules.inheritance_resolution == "single"
        assert "reflection_invoke" in cfg.scope_rules.dynamic_markers

    def test_typescript_dynamic_markers(self):
        cfg = LANGUAGE_CONFIGS["typescript"]
        assert "any_typed_call" in cfg.scope_rules.dynamic_markers


# ── Smoke tests: same-file resolution for TS ─────────────────────────────────

class TestTypescriptScopeResolution:
    """Verifies that same-file TS function calls resolve as scope_rule."""

    def setup_method(self):
        self.builder = EdgeBuilder()

    def test_same_file_ts_call_resolves_scope_rule(self):
        import tempfile, os
        from the_door.core.extraction.ast_extractor import ASTExtractor

        source = (
            "function target(): void {}\n"
            "function caller(): void { target(); }\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "single.ts")
            with open(path, "w") as f:
                f.write(source)
            extractor = ASTExtractor()
            result = extractor.extract(tmp)

        call_edges = [e for e in result.edges if e.type == "calls"]
        assert any(e.resolution == "scope_rule" for e in call_edges), \
            f"Expected scope_rule, got: {[e.resolution for e in call_edges]}"

    def test_ts_import_alias_call_resolves_import_alias(self):
        import tempfile, os
        from the_door.core.extraction.ast_extractor import ASTExtractor

        validator_src = "export function validate(): boolean { return true; }\n"
        service_src = (
            "import { validate as v } from './validator';\n"
            "function checkout(): void { v(); }\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "validator.ts"), "w") as f:
                f.write(validator_src)
            with open(os.path.join(tmp, "service.ts"), "w") as f:
                f.write(service_src)
            extractor = ASTExtractor()
            result = extractor.extract(tmp)

        alias_edges = [
            e for e in result.edges
            if e.type == "calls" and e.resolution == "import_alias"
        ]
        assert len(alias_edges) >= 1, \
            f"Expected import_alias edge, got: {[(e.from_node, e.to_node, e.resolution) for e in result.edges if e.type == 'calls']}"
```

- [ ] **Step 2: 執行，確認 FAIL**

```
cd the_door
pytest tests/unit/core/extraction/test_ts_java_scope_rules.py -v 2>&1 | head -20
```

期望：`AssertionError`（aliases 為空，因為 stub 回傳 `{}`）

---

### Step 2 — 實作 TypeScript ES Module import 解析

- [ ] **Step 3: 實作 `_parse_es_module_imports`**

在 `edge_builder.py` 找到：

```python
    def _parse_es_module_imports(self, root: TSNode, source_bytes: bytes) -> dict[str, str]:
        """TypeScript/JS ES6: import { name as alias } from '...' → {alias: name}."""
        # Implemented in Task 03
        return {}
```

改成：

```python
    def _parse_es_module_imports(self, root: TSNode, source_bytes: bytes) -> dict[str, str]:
        """TypeScript/JS ES6: import { name as alias } from '...' → {alias: name}."""
        aliases: dict[str, str] = {}
        self._walk_es_module_imports(root, source_bytes, aliases)
        return aliases

    def _walk_es_module_imports(
        self, node: TSNode, source_bytes: bytes, aliases: dict[str, str]
    ) -> None:
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "import_clause":
                    self._extract_es_import_clause(child, aliases)
        for child in node.children:
            self._walk_es_module_imports(child, source_bytes, aliases)

    def _extract_es_import_clause(self, clause: TSNode, aliases: dict[str, str]) -> None:
        for child in clause.children:
            if child.type == "identifier":
                # Default import: import Foo from '...'
                name = child.text.decode("utf-8", errors="replace")
                aliases[name] = name
            elif child.type == "named_imports":
                for spec in child.children:
                    if spec.type == "import_specifier":
                        self._extract_es_import_specifier(spec, aliases)

    def _extract_es_import_specifier(self, spec: TSNode, aliases: dict[str, str]) -> None:
        identifiers = [
            c.text.decode("utf-8", errors="replace")
            for c in spec.children
            if c.type == "identifier"
        ]
        if len(identifiers) == 1:
            # import { name } — no alias
            aliases[identifiers[0]] = identifiers[0]
        elif len(identifiers) >= 2:
            # import { name as alias } — first is original, last is alias
            aliases[identifiers[-1]] = identifiers[0]
```

- [ ] **Step 4: TypeScript tests PASS**

```
cd the_door
pytest tests/unit/core/extraction/test_ts_java_scope_rules.py::TestParseEsModuleImports -v
```

期望：全部 PASS。

---

### Step 3 — 實作 Java namespaced import 解析

- [ ] **Step 5: 實作 `_parse_namespaced_imports`**

找到：

```python
    def _parse_namespaced_imports(self, root: TSNode, source_bytes: bytes) -> dict[str, str]:
        """Java/PHP/C#: import/use statements → {alias: name}."""
        # Implemented in Task 03 (Java) and Task 05 (PHP/C#)
        return {}
```

改成：

```python
    def _parse_namespaced_imports(self, root: TSNode, source_bytes: bytes) -> dict[str, str]:
        """Java/PHP/C# namespaced imports → {alias: simple_name}.

        Java: import com.example.Foo → {"Foo": "Foo"}
        PHP/C#: filled in Task 05
        """
        aliases: dict[str, str] = {}
        self._walk_namespaced_imports(root, source_bytes, aliases)
        return aliases

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

    def _extract_last_qualified_name(self, node: TSNode) -> str | None:
        """Return the last identifier from a dotted/scoped name (e.g. com.example.Foo → Foo)."""
        text = node.text.decode("utf-8", errors="replace") if node.text else ""
        # Strip 'import' / 'static' keywords and semicolons
        parts = text.replace(";", "").strip().split()
        for part in reversed(parts):
            if part not in ("import", "static", "use", "using"):
                segments = part.replace("::", ".").split(".")
                last = segments[-1].strip()
                if last and last.isidentifier():
                    return last
        return None
```

- [ ] **Step 6: Java tests PASS**

```
cd the_door
pytest tests/unit/core/extraction/test_ts_java_scope_rules.py::TestParseNamespacedImports -v
```

期望：全部 PASS。

---

### Step 4 — 填入 LANGUAGE_CONFIGS

- [ ] **Step 7: 為 TypeScript 加入 scope_rules**

在 `language_configs.py` 找到 `"typescript"` entry，在最後一個欄位後加入：

```python
    scope_rules=ScopeRules(
        import_resolution="es_module",
        function_resolution="file_local_then_imports",
        method_resolution="class_local_then_inherited",
        inheritance_resolution="single",
        dynamic_markers=frozenset({"any_typed_call"}),
    ),
```

- [ ] **Step 8: 為 Java 加入 scope_rules**

找到 `"java"` entry，在最後一個欄位後加入：

```python
    scope_rules=ScopeRules(
        import_resolution="namespaced",
        function_resolution="package_local_then_imports",
        method_resolution="class_local_then_inherited",
        inheritance_resolution="single",
        dynamic_markers=frozenset({"reflection_invoke"}),
    ),
```

- [ ] **Step 9: Config 測試 PASS**

```
cd the_door
pytest tests/unit/core/extraction/test_ts_java_scope_rules.py::TestLanguageConfigsScopeRules -v
```

期望：全部 PASS。

---

### Step 5 — Smoke tests + 全套驗收

- [ ] **Step 10: 執行 smoke tests**

```
cd the_door
pytest tests/unit/core/extraction/test_ts_java_scope_rules.py::TestTypescriptScopeResolution -v
```

若失敗，檢查 tree-sitter TS grammar 的實際 node types（可在測試中加 `print(tree.root_node.sexp())` 查看）並修正 `_walk_es_module_imports` 的 node type 名稱。

- [ ] **Step 11: Coverage 驗收**

```
cd the_door
pytest tests/unit/core/extraction/test_ts_java_scope_rules.py -v \
  --cov=the_door.core.extraction.edge_builder \
  --cov=the_door.core.extraction.language_configs \
  --cov-fail-under=100
```

期望：全部 PASS + 100% coverage。

- [ ] **Step 12: 全套回歸**

```
cd the_door
pytest tests/ -q 2>&1 | tail -5
```

- [ ] **Step 13: Commit**

```
git add the_door/src/the_door/core/extraction/edge_builder.py \
        the_door/src/the_door/core/extraction/language_configs.py \
        the_door/tests/unit/core/extraction/test_ts_java_scope_rules.py
git commit -m "feat(edge): TypeScript (es_module) and Java (namespaced) scope rules"
```
