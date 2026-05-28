"""Tests for Task 03 — TypeScript (es_module) and Java (namespaced) scope rules."""
from __future__ import annotations

import pytest
import tree_sitter

from the_door.core.extraction.edge_builder import EdgeBuilder
from the_door.core.extraction.language_configs import LANGUAGE_CONFIGS, ScopeRules


# Inline parser helper — project uses individual tree_sitter_<lang> packages, not tree_sitter_languages
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
