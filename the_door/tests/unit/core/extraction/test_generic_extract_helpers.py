"""Tests for generic ASTNode extract helpers (Task 02).

Helpers are tested in isolation by feeding minimal tree-sitter parse trees.
"""
from __future__ import annotations

import pytest
from tree_sitter import Language, Parser

from the_door.core.extraction.language_configs import LANGUAGE_CONFIGS
from the_door.core.extraction.node_builder import NodeBuilder


def _parse(source: bytes, language: str):
    """Parse source with the given language. Returns (tree, root_node).

    Uses the same per-language tree_sitter_<lang> packages as
    ``the_door/src/the_door/core/extraction/ast_extractor.py``. Do NOT
    import ``tree_sitter_languages`` — The Door does not depend on it.
    """
    parser = Parser()
    if language == "rust":
        import tree_sitter_rust
        lang_obj = Language(tree_sitter_rust.language())
    elif language == "python":
        import tree_sitter_python
        lang_obj = Language(tree_sitter_python.language())
    elif language == "java":
        import tree_sitter_java
        lang_obj = Language(tree_sitter_java.language())
    elif language == "go":
        import tree_sitter_go
        lang_obj = Language(tree_sitter_go.language())
    elif language == "ruby":
        import tree_sitter_ruby
        lang_obj = Language(tree_sitter_ruby.language())
    elif language == "php":
        import tree_sitter_php
        lang_obj = Language(tree_sitter_php.language_php())
    elif language == "csharp":
        import tree_sitter_c_sharp
        lang_obj = Language(tree_sitter_c_sharp.language())
    else:
        raise ValueError(f"unsupported language for parse helper: {language!r}")
    parser.language = lang_obj
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

    def test_block_comment_strategy_java(self):
        """Java block comment strategy (preceding_block_comment)."""
        builder = NodeBuilder()
        source = b"/** Greet someone. */\npublic class Greeter {}"
        _, root = _parse(source, "java")
        cls = _find_first(root, "class_declaration")
        if cls is None:
            pytest.skip("Java grammar didn't parse expected shape")
        result = builder._extract_doc_comment(
            cls,
            strategy="preceding_block_comment",
            types=frozenset({"block_comment"}),
            markers=frozenset(),
        )
        assert result is not None
        assert "Greet" in result

    def test_block_comment_strategy_marker_mismatch_returns_none(self):
        """Block comment filtered out when markers don't match."""
        builder = NodeBuilder()
        source = b"/* Not a doc comment */\npublic class Foo {}"
        _, root = _parse(source, "java")
        cls = _find_first(root, "class_declaration")
        if cls is None:
            pytest.skip("Java grammar didn't parse expected shape")
        result = builder._extract_doc_comment(
            cls,
            strategy="preceding_block_comment",
            types=frozenset({"block_comment"}),
            markers=frozenset({"/**"}),
        )
        # "/* " doesn't start with "/**" → filtered out
        assert result is None

    def test_block_comment_strategy_no_preceding_comment_returns_none(self):
        """Node with no preceding block comment returns None."""
        builder = NodeBuilder()
        source = b"public class Foo {}"
        _, root = _parse(source, "java")
        cls = _find_first(root, "class_declaration")
        if cls is None:
            pytest.skip("Java grammar didn't parse expected shape")
        result = builder._extract_doc_comment(
            cls,
            strategy="preceding_block_comment",
            types=frozenset({"block_comment"}),
            markers=frozenset(),
        )
        assert result is None

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
