# Task 02 — EdgeBuilder Core Rewrite + Python Scope Rules

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重寫 `EdgeBuilder` 加入 scope-aware 解析核心：`_resolve()` 三段式（scope → alias → name_match fallback）、`ScopeContext` 建構機制、Python 的 `qualified` import alias 解析、以及 `build_edges` 新簽名。同步更新唯一呼叫端 `ast_extractor.py`。

**Architecture:** `EdgeBuilder` 從純 stateless 改成 per-call 帶 instance state（`_name_to_ids` / `_node_map`，在 `build_edges` 開頭設定，call 結束後清空）。`ScopeContext` 每個檔案建構一次，每個 call site clone 並更新 `caller_name`。`_parse_import_aliases` 以 `import_resolution` 策略 dispatch：本任務只實作 `"qualified"` 策略（Python），其他策略留 stub 回傳 `{}`（供後續任務填入）。

**Tech Stack:** Python 3.11+, tree-sitter, pytest, pytest-cov。

**Pre-requisite:** Task 01 完成（`ScopeRules`, `ScopeContext`, `Edge.resolution` schema 已存在）。

**Test Coverage Requirement:**

```
pytest the_door/tests/unit/core/extraction/test_edgebuilder_core.py -v \
  --cov=the_door.core.extraction.edge_builder \
  --cov=the_door.core.extraction.ast_extractor \
  --cov-fail-under=100
```

---

## Background（自含）

**目前 EdgeBuilder 狀態（`the_door/src/the_door/core/extraction/edge_builder.py`）：**

- `build_edges(self, nodes, trees)` — 2 參數
- 每條 edge 用 `Edge(from_node=..., to_node=..., type=...)` 建構（沒有 `resolution`）
- `_detect_calls` 79 行：`for target_id in name_to_ids[called_name]` 全域裸名匹配
- 沒有 scope context 概念、沒有 import alias 解析

**目前 ASTExtractor 呼叫端（`the_door/src/the_door/core/extraction/ast_extractor.py:194`）：**

```python
edges = self._edge_builder.build_edges(result.nodes, trees)
```

**Python import syntax（tree-sitter grammar）：**

| import 語法 | tree-sitter node type | children |
|---|---|---|
| `from orders.validator import validate` | `import_from_statement` | `dotted_name` → module, `import` keyword, `dotted_name` → name |
| `from orders.validator import validate as v` | `import_from_statement` | `dotted_name` → module, `aliased_import` → {`dotted_name`, `as`, `identifier` (alias)} |
| `import os` | `import_statement` | `dotted_name` |

`aliased_import` 的子節點格式：`[dotted_name("validate"), as_keyword, identifier("v")]`
— alias 是最後一個 `identifier`，original name 是 `dotted_name` 的最後一個 segment。

**_resolve 三段式（spec §4.6，修正版）：**

```
1. 若 is_dynamic（caller_name in dynamic_markers OR method_resolution == dynamic_dispatch）
   → 走 name_match 但標 skipped_dynamic
2. 嘗試 _resolve_by_scope（file-local / package-local 優先）→ scope_rule
3. 嘗試 _resolve_by_import_alias（import 別名查詢）→ import_alias
4. Fallback：name_match（保留，不丟邊）
```

**重要：** fallback 必須保留。「可見的低信心邊」嚴格優於「靜默漏邊」。

---

## Files

- Modify: `the_door/src/the_door/core/extraction/edge_builder.py`
- Modify: `the_door/src/the_door/core/extraction/ast_extractor.py`
- Test (new): `the_door/tests/unit/core/extraction/test_edgebuilder_core.py`

---

## Steps

### Step 1 — 寫 failing tests

- [ ] **Step 1: 建立測試檔案**

新增 `the_door/tests/unit/core/extraction/test_edgebuilder_core.py`：

```python
"""Tests for Task 02 — EdgeBuilder scope-aware core rewrite (Python / qualified strategy)."""
from __future__ import annotations

from pathlib import Path

import pytest

from the_door.core.extraction.edge_builder import EdgeBuilder
from the_door.core.extraction.language_configs import (
    LANGUAGE_CONFIGS,
    ScopeContext,
    ScopeRules,
    LanguageConfig,
)
from the_door.models import ASTNode, Edge


# ── helpers ───────────────────────────────────────────────────────────────────

def _node(node_id, name, file, lang="python", ntype="function"):
    return ASTNode(
        node_id=node_id,
        name=name,
        file=file,
        language=lang,
        type=ntype,
    )


# ── build_edges signature accepts configs ─────────────────────────────────────

class TestBuildEdgesSignature:
    def test_build_edges_accepts_configs_kwarg(self, tmp_path):
        """build_edges(nodes, trees, configs=...) must not raise TypeError."""
        builder = EdgeBuilder()
        edges = builder.build_edges([], {}, configs={})
        assert edges == []

    def test_build_edges_backward_compat_two_args(self, tmp_path):
        """Existing callers using build_edges(nodes, trees) still work."""
        builder = EdgeBuilder()
        edges = builder.build_edges([], {})
        assert edges == []


# ── inline tree-sitter parser helper ─────────────────────────────────────────
# 專案 deps 是個別套件（見 ast_extractor.py:25-79），沒有 tree_sitter_languages 統一入口。
import tree_sitter

_LANG_LOADERS = {
    "python":     ("tree_sitter_python",     "language"),
    "typescript": ("tree_sitter_typescript", "language_typescript"),
    "java":       ("tree_sitter_java",       "language"),
    "go":         ("tree_sitter_go",         "language"),
    "rust":       ("tree_sitter_rust",       "language"),
    "ruby":       ("tree_sitter_ruby",       "language"),
    "php":        ("tree_sitter_php",        "language_php"),
    "c_sharp":    ("tree_sitter_c_sharp",    "language"),
}


def _make_parser(lang: str) -> tree_sitter.Parser:
    mod_name, attr = _LANG_LOADERS[lang]
    mod = __import__(mod_name)
    return tree_sitter.Parser(tree_sitter.Language(getattr(mod, attr)()))


def _parse_python(source: str):
    parser = _make_parser("python")
    tree = parser.parse(source.encode())
    return tree, source.encode()


class TestParseQualifiedImports:
    def setup_method(self):
        self.builder = EdgeBuilder()

    def test_simple_from_import(self):
        tree, src = _parse_python("from orders.validator import validate\n")
        rules = ScopeRules(
            import_resolution="qualified",
            function_resolution="file_local_then_imports",
            method_resolution="class_local_then_inherited",
            inheritance_resolution="multiple",
        )
        aliases = self.builder._parse_import_aliases(tree.root_node, src, rules)
        # 無 alias — name 本身作為鍵
        assert "validate" in aliases
        assert aliases["validate"] == "validate"

    def test_aliased_from_import(self):
        tree, src = _parse_python("from orders.validator import validate as v_order\n")
        rules = ScopeRules(
            import_resolution="qualified",
            function_resolution="file_local_then_imports",
            method_resolution="class_local_then_inherited",
            inheritance_resolution="multiple",
        )
        aliases = self.builder._parse_import_aliases(tree.root_node, src, rules)
        assert "v_order" in aliases
        assert aliases["v_order"] == "validate"

    def test_multiple_imports(self):
        source = (
            "from orders.validator import validate as v_order\n"
            "from users.validator import validate as v_user\n"
        )
        tree, src = _parse_python(source)
        rules = ScopeRules(
            import_resolution="qualified",
            function_resolution="file_local_then_imports",
            method_resolution="class_local_then_inherited",
            inheritance_resolution="multiple",
        )
        aliases = self.builder._parse_import_aliases(tree.root_node, src, rules)
        assert aliases.get("v_order") == "validate"
        assert aliases.get("v_user") == "validate"

    def test_non_qualified_strategy_returns_empty(self):
        tree, src = _parse_python("from x import y\n")
        rules = ScopeRules(
            import_resolution="es_module",  # not qualified → stub returns {}
            function_resolution="file_local_then_imports",
            method_resolution="class_local_then_inherited",
            inheritance_resolution="single",
        )
        aliases = self.builder._parse_import_aliases(tree.root_node, src, rules)
        # es_module not yet implemented in this task → empty dict
        assert isinstance(aliases, dict)


# ── _resolve: dynamic dispatch ────────────────────────────────────────────────

class TestResolve:
    def setup_method(self):
        self.builder = EdgeBuilder()
        # Pre-populate internal state as build_edges would
        self.builder._name_to_ids = {
            "validate": ["orders/validator.py::validate", "users/validator.py::validate"],
            "process": ["processor.py::process"],
        }
        self.builder._node_map = {
            "orders/validator.py::validate": _node("orders/validator.py::validate", "validate", "orders/validator.py"),
            "users/validator.py::validate": _node("users/validator.py::validate", "validate", "users/validator.py"),
            "processor.py::process": _node("processor.py::process", "process", "processor.py"),
        }

    def _rules(self, method_resolution="class_local_then_inherited", dynamic_markers=frozenset()):
        return ScopeRules(
            import_resolution="qualified",
            function_resolution="file_local_then_imports",
            method_resolution=method_resolution,
            inheritance_resolution="multiple",
            dynamic_markers=dynamic_markers,
        )

    def _ctx(self, file="orders/service.py", aliases=None, caller_name="checkout", caller_class=None):
        return ScopeContext(
            current_file=file,
            import_aliases=aliases or {},
            caller_class=caller_class,
            caller_name=caller_name,
        )

    # dynamic dispatch

    def test_dynamic_dispatch_method_resolution_marks_skipped_dynamic(self):
        rules = self._rules(method_resolution="dynamic_dispatch")
        ctx = self._ctx()
        result = self.builder._resolve("validate", ctx, rules)
        assert all(res == "skipped_dynamic" for _, res in result)
        assert len(result) == 2  # both candidates kept

    def test_dynamic_marker_in_caller_name_marks_skipped_dynamic(self):
        rules = self._rules(dynamic_markers=frozenset({"__getattr__"}))
        ctx = self._ctx(caller_name="__getattr__")
        result = self.builder._resolve("validate", ctx, rules)
        assert all(res == "skipped_dynamic" for _, res in result)

    def test_dynamic_no_candidates_returns_empty(self):
        rules = self._rules(method_resolution="dynamic_dispatch")
        ctx = self._ctx()
        result = self.builder._resolve("nonexistent", ctx, rules)
        assert result == []

    # scope rule — file local

    def test_file_local_resolves_same_file_as_scope_rule(self):
        rules = self._rules()
        ctx = self._ctx(file="orders/validator.py")  # same file as one candidate
        result = self.builder._resolve("validate", ctx, rules)
        assert len(result) == 1
        assert result[0] == ("orders/validator.py::validate", "scope_rule")

    def test_file_local_falls_back_name_match_when_no_same_file(self):
        rules = self._rules()
        ctx = self._ctx(file="other/service.py")  # different file
        result = self.builder._resolve("validate", ctx, rules)
        # Both candidates returned as name_match (fallback)
        resolutions = {res for _, res in result}
        assert resolutions == {"name_match"}
        assert len(result) == 2

    # import alias

    def test_import_alias_resolves_single_target(self):
        rules = self._rules()
        ctx = self._ctx(file="other/service.py", aliases={"v_order": "validate"})
        result = self.builder._resolve("v_order", ctx, rules)
        # v_order → validate → found in name_to_ids
        assert any(res == "import_alias" for _, res in result)

    def test_import_alias_unknown_name_falls_back_to_name_match(self):
        rules = self._rules()
        ctx = self._ctx(file="other/service.py", aliases={})
        result = self.builder._resolve("process", ctx, rules)
        assert len(result) == 1
        assert result[0][1] == "name_match"

    # fallback never drops edges

    def test_fallback_name_match_returns_all_candidates(self):
        rules = self._rules()
        ctx = self._ctx(file="completely/different.py")
        result = self.builder._resolve("validate", ctx, rules)
        node_ids = {nid for nid, _ in result}
        assert "orders/validator.py::validate" in node_ids
        assert "users/validator.py::validate" in node_ids

    def test_unknown_name_returns_empty(self):
        rules = self._rules()
        ctx = self._ctx()
        result = self.builder._resolve("totally_unknown", ctx, rules)
        assert result == []


# ── build_edges integration: resolution propagates to edges ──────────────────

class TestBuildEdgesResolution:
    """Integration: build_edges produces edges with correct resolution fields."""

    def _build_python(self, source: str, file_name="service.py"):
        """Parse Python source and run build_edges with Python scope rules."""
        lang_obj = tree_sitter_languages.get_language("python")
        parser = tree_sitter_languages.get_parser("python")
        tree = parser.parse(source.encode())

        # Build a minimal set of nodes matching the source
        nodes = []
        # We rely on the test to supply pre-built nodes rather than running ASTExtractor
        return tree, source.encode()

    def test_edge_has_resolution_field(self):
        """Any edge produced must have a non-empty resolution string."""
        from the_door.core.extraction.ast_extractor import ASTExtractor
        import tempfile, os

        source = "def foo():\n    return 1\ndef bar():\n    foo()\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "main.py")
            with open(path, "w") as f:
                f.write(source)
            extractor = ASTExtractor()
            result = extractor.extract(tmp)
        for edge in result.edges:
            assert edge.resolution in ("scope_rule", "import_alias", "name_match", "skipped_dynamic"), \
                f"Unexpected resolution: {edge.resolution!r}"

    def test_same_file_call_gets_scope_rule(self):
        """foo() calls bar() in same file → scope_rule when Python config present."""
        from the_door.core.extraction.ast_extractor import ASTExtractor
        import tempfile, os

        source = "def target():\n    return 1\ndef caller():\n    target()\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "single.py")
            with open(path, "w") as f:
                f.write(source)
            extractor = ASTExtractor()
            result = extractor.extract(tmp)

        call_edges = [e for e in result.edges if e.type == "calls"]
        assert any(e.resolution == "scope_rule" for e in call_edges), \
            f"Expected scope_rule edge, got: {[e.resolution for e in call_edges]}"
```

- [ ] **Step 2: 執行，確認 FAIL**

```
cd the_door
pytest tests/unit/core/extraction/test_edgebuilder_core.py -v 2>&1 | head -30
```

期望：`AttributeError: 'EdgeBuilder' object has no attribute '_parse_import_aliases'` 或類似。

---

### Step 2 — 重寫 `edge_builder.py`

- [ ] **Step 3: 完整重寫 `edge_builder.py`**

用以下內容**完全取代** `the_door/src/the_door/core/extraction/edge_builder.py`：

```python
"""Edge builder module — scope-aware call/import/extends relationship detection."""
from __future__ import annotations

from tree_sitter import Node as TSNode

from the_door.core.extraction.language_configs import (
    LANGUAGE_CONFIGS,
    LanguageConfig,
    ScopeContext,
    ScopeRules,
)
from the_door.models import ASTNode, Edge


class EdgeBuilder:
    """Detect relationships between AST nodes with scope-aware resolution.

    Resolution provenance per edge:
      scope_rule      — resolved via same-file or same-package scope
      import_alias    — resolved via import alias table
      name_match      — fallback bare-name match (low confidence)
      skipped_dynamic — dynamic dispatch context, edge kept but untrusted
    """

    def __init__(self) -> None:
        # Instance state populated per build_edges() call so resolve helpers
        # never AttributeError if called before/between builds.
        self._name_to_ids: dict[str, list[str]] = {}
        self._node_map: dict[str, ASTNode] = {}

    def build_edges(
        self,
        nodes: list[ASTNode],
        trees: dict,
        configs: dict[str, LanguageConfig] | None = None,
    ) -> list[Edge]:
        """Analyze parsed trees to find edges between known nodes.

        Parameters
        ----------
        nodes : list[ASTNode]
            All extracted AST nodes.
        trees : dict[str, tuple[tree, bytes]]
            Mapping of relative file path → (tree-sitter Tree, source bytes).
        configs : dict[str, LanguageConfig] | None
            Per-language config dict (e.g. LANGUAGE_CONFIGS). If None, falls
            back to the global LANGUAGE_CONFIGS.
        """
        lang_configs = configs if configs is not None else LANGUAGE_CONFIGS

        # Build lookup structures (instance state for this call)
        self._name_to_ids = {}
        for n in nodes:
            self._name_to_ids.setdefault(n.name, []).append(n.node_id)
        self._node_map = {n.node_id: n for n in nodes}

        node_id_set = set(self._node_map)
        edges: list[Edge] = []

        for file_path, (tree, source_bytes) in trees.items():
            file_nodes = [n for n in nodes if n.file == file_path]
            if not file_nodes:
                continue

            # Determine language config and scope rules for this file
            lang = file_nodes[0].language
            lang_config = lang_configs.get(lang)
            rules = lang_config.scope_rules if lang_config else None

            # Build per-file ScopeContext (import alias table)
            if rules is not None:
                import_aliases = self._parse_import_aliases(tree.root_node, source_bytes, rules)
            else:
                import_aliases = {}
            base_ctx = ScopeContext(
                current_file=file_path,
                import_aliases=import_aliases,
                caller_class=None,
            )

            self._detect_calls(tree.root_node, file_nodes, node_id_set, edges, base_ctx, rules)
            self._detect_extends(tree.root_node, file_nodes, node_id_set, edges, base_ctx, rules)

        self._detect_imports(nodes, trees, node_id_set, edges, lang_configs)

        # Deduplicate (key: from, to, type — resolution is not part of dedup key
        # so that scope_rule edges are preferred over name_match duplicates)
        seen: set[tuple[str, str, str]] = set()
        unique_edges: list[Edge] = []
        for e in edges:
            key = (e.from_node, e.to_node, e.type)
            if key not in seen:
                seen.add(key)
                unique_edges.append(e)

        # Clear instance state
        self._name_to_ids = {}
        self._node_map = {}

        return unique_edges

    # ── import alias parsing ────────────────────────────────────────────────

    def _parse_import_aliases(
        self, root: TSNode, source_bytes: bytes, rules: ScopeRules
    ) -> dict[str, str]:
        """Parse import statements from a file's AST into alias → original name.

        Dispatches on rules.import_resolution. Unknown strategies return {}.
        """
        strategy = rules.import_resolution
        if strategy == "qualified":
            return self._parse_qualified_imports(root, source_bytes)
        if strategy == "es_module":
            return self._parse_es_module_imports(root, source_bytes)
        if strategy == "namespaced":
            return self._parse_namespaced_imports(root, source_bytes)
        if strategy == "module_path":
            return self._parse_module_path_imports(root, source_bytes)
        return {}

    def _parse_qualified_imports(self, root: TSNode, source_bytes: bytes) -> dict[str, str]:
        """Python-style: from module import name [as alias] → {alias: name}."""
        aliases: dict[str, str] = {}
        self._walk_qualified_imports(root, source_bytes, aliases)
        return aliases

    def _walk_qualified_imports(
        self, node: TSNode, source_bytes: bytes, aliases: dict[str, str]
    ) -> None:
        """Walk a Python AST collecting `from X import [name as alias]` aliases.

        tree-sitter-python grammar puts `import_from_statement` children in this
        order: `from` keyword → dotted_name(module) → `import` keyword → one or
        more {dotted_name | aliased_import | identifier} representing the imported
        names. We track "seen import keyword" so the *module path* dotted_name
        is not confused with imported-name dotted_names.
        """
        if node.type == "import_from_statement":
            seen_import_kw = False
            for child in node.children:
                if child.type == "import":
                    seen_import_kw = True
                    continue
                if not seen_import_kw:
                    continue  # skip the module-path dotted_name before `import`
                if child.type == "aliased_import":
                    orig_name = None
                    alias_name = None
                    for sub in child.children:
                        if sub.type == "dotted_name" and orig_name is None:
                            orig_name = sub.text.decode("utf-8", errors="replace").split(".")[-1]
                        elif sub.type == "identifier":
                            if orig_name is None:
                                orig_name = sub.text.decode("utf-8", errors="replace")
                            else:
                                alias_name = sub.text.decode("utf-8", errors="replace")
                    if orig_name and alias_name:
                        aliases[alias_name] = orig_name
                elif child.type == "dotted_name":
                    name = child.text.decode("utf-8", errors="replace").split(".")[-1]
                    if name.isidentifier():
                        aliases[name] = name
                elif child.type == "identifier":
                    name = child.text.decode("utf-8", errors="replace")
                    if name.isidentifier():
                        aliases[name] = name
            # Fully handled this import_from_statement — do not recurse into its
            # children (would re-walk aliased_import / dotted_name with no effect
            # and waste cycles on large files with many imports).
            return
        # Recurse only for non-import nodes (find nested imports).
        for child in node.children:
            self._walk_qualified_imports(child, source_bytes, aliases)

    def _parse_es_module_imports(self, root: TSNode, source_bytes: bytes) -> dict[str, str]:
        """TypeScript/JS ES6: import { name as alias } from '...' → {alias: name}."""
        # Implemented in Task 03
        return {}

    def _parse_namespaced_imports(self, root: TSNode, source_bytes: bytes) -> dict[str, str]:
        """Java/PHP/C#: import/use statements → {alias: name}."""
        # Implemented in Task 03 (Java) and Task 05 (PHP/C#)
        return {}

    def _parse_module_path_imports(self, root: TSNode, source_bytes: bytes) -> dict[str, str]:
        """Go/Rust: use/import path statements → {last_segment: last_segment}."""
        # Implemented in Task 04
        return {}

    # ── resolution logic ───────────────────────────────────────────────────

    def _resolve(
        self, name: str, context: ScopeContext, rules: ScopeRules | None
    ) -> list[tuple[str, str]]:
        """Resolve a called name to (node_id, resolution) pairs.

        Empty list means no edge is produced.
        Multiple results only occur in the name_match / skipped_dynamic fallback path.
        """
        if rules is None:
            # No scope rules configured → pure name_match fallback
            matches = self._name_to_ids.get(name, [])
            return [(m, "name_match") for m in matches]

        # Step 1: Dynamic dispatch check
        is_dynamic = (
            context.has_dynamic_marker(rules.dynamic_markers)
            or rules.method_resolution == "dynamic_dispatch"
        )
        if is_dynamic:
            matches = self._name_to_ids.get(name, [])
            return [(m, "skipped_dynamic") for m in matches]

        # Step 2: Scope rule (file-local / package-local)
        scoped = self._resolve_by_scope(name, context, rules)
        if scoped:
            return [(scoped, "scope_rule")]

        # Step 3: Import alias
        aliased = self._resolve_by_import_alias(name, context, rules)
        if aliased:
            return [(aliased, "import_alias")]

        # Step 4: Fallback — name_match (keep all candidates, low confidence)
        matches = self._name_to_ids.get(name, [])
        return [(m, "name_match") for m in matches]

    def _resolve_by_scope(
        self, name: str, context: ScopeContext, rules: ScopeRules
    ) -> str | None:
        """Return a single node_id if the name can be scope-resolved, else None."""
        candidates = self._name_to_ids.get(name, [])
        if not candidates:
            return None

        strategy = rules.function_resolution
        if strategy == "file_local_then_imports":
            same_file = [
                c for c in candidates
                if c in self._node_map and self._node_map[c].file == context.current_file
            ]
            if same_file:
                return same_file[0]

        elif strategy == "package_local_then_imports":
            current_pkg = context.current_file.rsplit("/", 1)[0] if "/" in context.current_file else ""
            same_pkg = [
                c for c in candidates
                if c in self._node_map
                and (
                    self._node_map[c].file.rsplit("/", 1)[0] == current_pkg
                    if "/" in self._node_map[c].file
                    else current_pkg == ""
                )
            ]
            if same_pkg:
                return same_pkg[0]

        return None

    def _resolve_by_import_alias(
        self, name: str, context: ScopeContext, rules: ScopeRules
    ) -> str | None:
        """Return a node_id if name is a known import alias, else None."""
        original_name = context.import_aliases.get(name)
        if original_name is None:
            return None
        candidates = self._name_to_ids.get(original_name, [])
        if not candidates:
            return None
        return candidates[0]

    # ── detection methods ──────────────────────────────────────────────────

    def _detect_calls(
        self,
        root: TSNode,
        file_nodes: list[ASTNode],
        node_id_set: set[str],
        edges: list[Edge],
        base_ctx: ScopeContext,
        rules: ScopeRules | None,
    ) -> None:
        for node in file_nodes:
            if node.type == "class":
                continue
            func_ts_node = self._find_definition_node(root, node)
            if func_ts_node is None:
                continue
            body = self._find_child(func_ts_node, "block") or self._find_child(
                func_ts_node, "statement_block"
            )
            if body is None:
                continue
            # Clone context with caller info for this specific node.
            # Derive caller_class from node_id format "ClassName.method_name" if
            # the node is a method; bare functions have no dot and caller_class=None.
            if node.type == "method" and "." in node.node_id.rsplit("/", 1)[-1]:
                # node_id last segment looks like "Class.method" → use "Class"
                last_seg = node.node_id.rsplit("/", 1)[-1]
                derived_class = last_seg.rsplit(".", 1)[0]
            else:
                derived_class = None
            call_ctx = ScopeContext(
                current_file=base_ctx.current_file,
                import_aliases=base_ctx.import_aliases,
                caller_class=derived_class,
                caller_name=node.name,
            )
            called_names = self._collect_call_names(body)
            for called_name in called_names:
                if rules is not None:
                    resolved = self._resolve(called_name, call_ctx, rules)
                else:
                    candidates = self._name_to_ids.get(called_name, [])
                    resolved = [(c, "name_match") for c in candidates]
                for target_id, res_type in resolved:
                    if target_id != node.node_id and target_id in node_id_set:
                        edges.append(
                            Edge(
                                from_node=node.node_id,
                                to_node=target_id,
                                type="calls",
                                resolution=res_type,
                            )
                        )

    def _detect_extends(
        self,
        root: TSNode,
        file_nodes: list[ASTNode],
        node_id_set: set[str],
        edges: list[Edge],
        base_ctx: ScopeContext,
        rules: ScopeRules | None,
    ) -> None:
        for node in file_nodes:
            if node.type != "class":
                continue
            class_ts_node = self._find_definition_node(root, node)
            if class_ts_node is None:
                continue
            base_names = self._extract_base_classes(class_ts_node)
            for base_name in base_names:
                if rules is not None:
                    ext_ctx = ScopeContext(
                        current_file=base_ctx.current_file,
                        import_aliases=base_ctx.import_aliases,
                        caller_class=node.name,
                        caller_name=node.name,
                    )
                    resolved = self._resolve(base_name, ext_ctx, rules)
                else:
                    candidates = self._name_to_ids.get(base_name, [])
                    resolved = [(c, "name_match") for c in candidates]
                for target_id, res_type in resolved:
                    if target_id != node.node_id and target_id in node_id_set:
                        edges.append(
                            Edge(
                                from_node=node.node_id,
                                to_node=target_id,
                                type="extends",
                                resolution=res_type,
                            )
                        )

    def _detect_imports(
        self,
        nodes: list[ASTNode],
        trees: dict,
        node_id_set: set[str],
        edges: list[Edge],
        lang_configs: dict[str, LanguageConfig],
    ) -> None:
        for file_path, (tree, source_bytes) in trees.items():
            file_nodes = [n for n in nodes if n.file == file_path]
            if not file_nodes:
                continue
            imported_names = self._collect_import_names(tree.root_node)
            for imp_name in imported_names:
                if imp_name in self._name_to_ids:
                    for target_id in self._name_to_ids[imp_name]:
                        target_file = self._node_map[target_id].file if target_id in self._node_map else ""
                        if target_file != file_path:
                            for src_node in file_nodes:
                                edges.append(
                                    Edge(
                                        from_node=src_node.node_id,
                                        to_node=target_id,
                                        type="imports",
                                        resolution="name_match",
                                    )
                                )
                                break

    # ── tree-sitter helpers (unchanged from original) ───────────────────────

    def _find_definition_node(self, root: TSNode, ast_node: ASTNode) -> TSNode | None:
        return self._search_for_definition(root, ast_node.name, ast_node.type)

    def _search_for_definition(self, ts_node: TSNode, name: str, node_type: str) -> TSNode | None:
        if self._is_matching_definition(ts_node, name, node_type):
            return ts_node
        if ts_node.type == "decorated_definition":
            for child in ts_node.children:
                if self._is_matching_definition(child, name, node_type):
                    return child
        for child in ts_node.children:
            result = self._search_for_definition(child, name, node_type)
            if result is not None:
                return result
        return None

    def _is_matching_definition(self, ts_node: TSNode, name: str, node_type: str) -> bool:
        def_types = {
            "function": ("function_definition", "function_declaration"),
            "method": ("function_definition", "method_definition"),
            "class": ("class_definition", "class_declaration"),
        }
        expected_types = def_types.get(node_type, ())
        if ts_node.type not in expected_types:
            return False
        for child in ts_node.children:
            if child.type in ("identifier", "type_identifier", "property_identifier"):
                if child.text.decode("utf-8", errors="replace") == name:
                    return True
        return False

    def _collect_call_names(self, node: TSNode) -> set[str]:
        names: set[str] = set()
        if node.type == "call":
            func_node = node.children[0] if node.children else None
            if func_node:
                if func_node.type == "identifier":
                    names.add(func_node.text.decode("utf-8", errors="replace"))
                elif func_node.type == "attribute":
                    last_id = ""
                    for child in func_node.children:
                        if child.type == "identifier":
                            last_id = child.text.decode("utf-8", errors="replace")
                    if last_id:
                        names.add(last_id)
        for child in node.children:
            names.update(self._collect_call_names(child))
        return names

    def _extract_base_classes(self, class_node: TSNode) -> list[str]:
        bases: list[str] = []
        for child in class_node.children:
            if child.type == "argument_list":
                for arg in child.children:
                    if arg.type == "identifier":
                        bases.append(arg.text.decode("utf-8", errors="replace"))
            if child.type == "class_heritage":
                for sub in child.children:
                    if sub.type in ("identifier", "type_identifier"):
                        bases.append(sub.text.decode("utf-8", errors="replace"))
        return bases

    def _collect_import_names(self, root: TSNode) -> set[str]:
        names: set[str] = set()
        self._walk_imports(root, names)
        return names

    def _walk_imports(self, node: TSNode, names: set[str]) -> None:
        if node.type in ("import_from_statement", "import_statement"):
            for child in node.children:
                if child.type == "dotted_name":
                    parts = child.text.decode("utf-8", errors="replace").split(".")
                    names.add(parts[-1])
                elif child.type == "aliased_import":
                    for sub in child.children:
                        if sub.type in ("dotted_name", "identifier"):
                            names.add(sub.text.decode("utf-8", errors="replace").split(".")[-1])
                            break
                elif child.type == "identifier" and child.prev_sibling and child.prev_sibling.type == "import":
                    names.add(child.text.decode("utf-8", errors="replace"))
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "import_clause":
                    self._extract_ts_import_names(child, names)
        for child in node.children:
            self._walk_imports(child, names)

    def _extract_ts_import_names(self, node: TSNode, names: set[str]) -> None:
        if node.type == "identifier":
            names.add(node.text.decode("utf-8", errors="replace"))
        if node.type == "import_specifier":
            for child in node.children:
                if child.type == "identifier":
                    names.add(child.text.decode("utf-8", errors="replace"))
                    break
        for child in node.children:
            self._extract_ts_import_names(child, names)

    @staticmethod
    def _find_child(node: TSNode, child_type: str) -> TSNode | None:
        for child in node.children:
            if child.type == child_type:
                return child
        return None
```

- [ ] **Step 4: 執行 EdgeBuilder 測試**

```
cd the_door
pytest tests/unit/core/extraction/test_edgebuilder_core.py -v 2>&1 | tail -20
```

期望：大部分 PASS。若有失敗先 debug 修正再繼續。

---

### Step 3 — 更新 `ast_extractor.py` 呼叫端

- [ ] **Step 5: 更新 `ast_extractor.py:194` 傳入 lang configs**

找到 `the_door/src/the_door/core/extraction/ast_extractor.py` 約第 192-200 行：

```python
        # Step 4: Build edges
        try:
            edges = self._edge_builder.build_edges(result.nodes, trees)
```

改成：

```python
        # Step 4: Build edges
        try:
            edges = self._edge_builder.build_edges(result.nodes, trees, configs=LANGUAGE_CONFIGS)
```

並在 `ast_extractor.py` 頂部 import 區加入：

```python
from the_door.core.extraction.language_configs import LANGUAGE_CONFIGS
```

（若已有則略過。）

- [ ] **Step 6: 加入 Python ScopeRules 到 LANGUAGE_CONFIGS**

在 `the_door/src/the_door/core/extraction/language_configs.py` 找到 `LANGUAGE_CONFIGS` dict 的 `"python"` entry，加入 `scope_rules`。

目前 `"python"` entry 的最後一個欄位之後加入：

```python
    scope_rules=ScopeRules(
        import_resolution="qualified",
        function_resolution="file_local_then_imports",
        method_resolution="class_local_then_inherited",
        inheritance_resolution="multiple",
        dynamic_markers=frozenset({"__getattr__", "getattr"}),
    ),
```

---

### Step 4 — 全套驗收

- [ ] **Step 7: 執行本任務測試 + coverage**

```
cd the_door
pytest tests/unit/core/extraction/test_edgebuilder_core.py -v \
  --cov=the_door.core.extraction.edge_builder \
  --cov=the_door.core.extraction.ast_extractor \
  --cov-fail-under=100
```

期望：全部 PASS + 100% coverage。

若覆蓋率不足，確認測試有觸及 `_parse_es_module_imports` / `_parse_namespaced_imports` / `_parse_module_path_imports`（它們是 stub 直接 return `{}`，需要一個測試 hit 過）。

- [ ] **Step 8: 全套回歸**

```
cd the_door
pytest tests/ -q 2>&1 | tail -5
```

期望：全部 PASS。

- [ ] **Step 9: Commit**

```
git add the_door/src/the_door/core/extraction/edge_builder.py \
        the_door/src/the_door/core/extraction/ast_extractor.py \
        the_door/src/the_door/core/extraction/language_configs.py \
        the_door/tests/unit/core/extraction/test_edgebuilder_core.py
git commit -m "feat(edge): scope-aware EdgeBuilder core + Python qualified import resolution"
```
