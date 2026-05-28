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

    def test_scoped_use_list(self):
        """use std::{io, fmt} — scoped_use_list branch."""
        tree, src = _parse("rust", "use std::{io, fmt};\n")
        aliases = self.builder._parse_import_aliases(tree.root_node, src, _module_path_rules())
        assert "io" in aliases
        assert "fmt" in aliases

    def test_scoped_use_list_with_alias(self):
        """use std::{Validator as V, fmt} — use_as_clause inside scoped_use_list (line 352).

        The aliased item must be a scoped_identifier (e.g. crate::Validator) for the
        alias mapping to be recorded; the plain identifier case is not handled by
        _extract_rust_use_item for use_as_clause.  This test exercises the
        `elif item.type == "use_as_clause"` branch via a scoped form.
        """
        tree, src = _parse("rust", "use crate::{orders::Validator as V, fmt};\n")
        aliases = self.builder._parse_import_aliases(tree.root_node, src, _module_path_rules())
        # fmt — plain identifier branch
        assert "fmt" in aliases
        # Validator as V — scoped_identifier orig mapped to alias
        assert aliases.get("V") == "Validator"

    def test_bare_use_identifier(self):
        """use validator; — bare identifier under use_declaration (lines 355-357)."""
        tree, src = _parse("rust", "use validator;\n")
        aliases = self.builder._parse_import_aliases(tree.root_node, src, _module_path_rules())
        assert aliases.get("validator") == "validator"


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
