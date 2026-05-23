"""Tests for config-driven multilang node extraction (spec: multilang-node-extraction/spec.md)."""
from pathlib import Path

import pytest

from the_door.core.extraction.ast_extractor import ASTExtractor

FIXTURES = Path(__file__).parent.parent.parent.parent / "fixtures" / "sample_codebases" / "multilang_nodes"


class TestRustExtraction:
    """Rust: function_item, struct_item, impl_item container (spec R3 + R6)."""

    def test_rust_free_function_extracted(self, tmp_path):
        (tmp_path / "s.rs").write_text("fn free_function() {}\n")
        result = ASTExtractor().extract(str(tmp_path))
        names = {n.name for n in result.nodes}
        assert "free_function" in names

    def test_rust_struct_extracted_as_class(self, tmp_path):
        (tmp_path / "s.rs").write_text("struct MyStruct { x: i32 }\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "MyStruct" in nodes
        assert nodes["MyStruct"].type == "class"

    def test_rust_impl_method_extracted_as_method(self, tmp_path):
        src = "struct MyStruct {}\nimpl MyStruct { fn impl_method(&self) {} }\n"
        (tmp_path / "s.rs").write_text(src)
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "impl_method" in nodes, f"impl_method not found; got {set(nodes)}"
        assert nodes["impl_method"].type == "method", f"expected method, got {nodes['impl_method'].type}"

    def test_rust_free_fn_is_function_not_method(self, tmp_path):
        (tmp_path / "s.rs").write_text("fn free_function() {}\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert nodes["free_function"].type == "function"
