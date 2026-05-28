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


