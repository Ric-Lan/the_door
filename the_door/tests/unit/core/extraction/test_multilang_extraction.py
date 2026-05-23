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


class TestJavaExtraction:
    """Java: method_declaration, constructor_declaration, class_declaration (spec R3)."""

    def test_java_class_extracted(self, tmp_path):
        (tmp_path / "A.java").write_text("public class Animal { public void speak() {} public Animal() {} }\n")
        result = ASTExtractor().extract(str(tmp_path))
        class_nodes = [n for n in result.nodes if n.name == "Animal" and n.type == "class"]
        assert len(class_nodes) >= 1

    def test_java_method_extracted_as_method(self, tmp_path):
        (tmp_path / "A.java").write_text("public class Animal { public void speak() {} }\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "speak" in nodes
        assert nodes["speak"].type == "method"

    def test_java_constructor_extracted_as_method(self, tmp_path):
        (tmp_path / "A.java").write_text("public class Animal { public Animal() {} }\n")
        result = ASTExtractor().extract(str(tmp_path))
        method_nodes = [n for n in result.nodes if n.name == "Animal" and n.type == "method"]
        assert len(method_nodes) >= 1


class TestRubyExtraction:
    """Ruby: method, class (spec R3)."""

    def test_ruby_class_extracted(self, tmp_path):
        (tmp_path / "a.rb").write_text("class Animal\n  def speak\n  end\nend\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Animal" in nodes
        assert nodes["Animal"].type == "class"

    def test_ruby_method_inside_class_is_method(self, tmp_path):
        (tmp_path / "a.rb").write_text("class Animal\n  def speak\n  end\nend\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "speak" in nodes
        assert nodes["speak"].type == "method"

    def test_ruby_standalone_method_is_function(self, tmp_path):
        (tmp_path / "a.rb").write_text("def standalone_func\nend\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "standalone_func" in nodes
        assert nodes["standalone_func"].type == "function"


class TestPhpExtraction:
    """PHP: function_definition, method_declaration, class_declaration (spec R3)."""

    def test_php_standalone_function_extracted(self, tmp_path):
        (tmp_path / "a.php").write_text("<?php\nfunction standalone_func() {}\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "standalone_func" in nodes
        assert nodes["standalone_func"].type == "function"

    def test_php_class_extracted(self, tmp_path):
        (tmp_path / "a.php").write_text("<?php\nclass Animal { function speak() {} }\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Animal" in nodes
        assert nodes["Animal"].type == "class"

    def test_php_method_inside_class_is_method(self, tmp_path):
        (tmp_path / "a.php").write_text("<?php\nclass Animal { function speak() {} }\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "speak" in nodes
        assert nodes["speak"].type == "method"


class TestCSharpExtraction:
    """C#: method_declaration, constructor_declaration, class_declaration (spec R3)."""

    def test_csharp_class_extracted(self, tmp_path):
        (tmp_path / "a.cs").write_text("class Animal { void Speak() {} }\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Animal" in nodes
        assert nodes["Animal"].type == "class"

    def test_csharp_method_extracted_as_method(self, tmp_path):
        (tmp_path / "a.cs").write_text("class Animal { void Speak() {} }\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Speak" in nodes
        assert nodes["Speak"].type == "method"

    def test_csharp_constructor_extracted_as_method(self, tmp_path):
        (tmp_path / "a.cs").write_text("class Animal { public Animal() {} }\n")
        result = ASTExtractor().extract(str(tmp_path))
        method_nodes = [n for n in result.nodes if n.name == "Animal" and n.type == "method"]
        assert len(method_nodes) >= 1


class TestCExtraction:
    """C: function_definition, struct_specifier (spec R3)."""

    def test_c_function_extracted(self, tmp_path):
        (tmp_path / "a.c").write_text("void move_point(int x) {}\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "move_point" in nodes
        assert nodes["move_point"].type == "function"

    def test_c_struct_extracted_as_class(self, tmp_path):
        (tmp_path / "a.c").write_text("struct Point { int x; };\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Point" in nodes
        assert nodes["Point"].type == "class"


class TestCppExtraction:
    """C++: function_definition, class_specifier (spec R3)."""

    def test_cpp_class_extracted(self, tmp_path):
        (tmp_path / "a.cpp").write_text("class Shape { void draw() {} };\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Shape" in nodes
        assert nodes["Shape"].type == "class"

    def test_cpp_method_inside_class_is_method(self, tmp_path):
        (tmp_path / "a.cpp").write_text("class Shape { void draw() {} };\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "draw" in nodes
        assert nodes["draw"].type == "method"

    def test_cpp_top_level_function_is_function(self, tmp_path):
        (tmp_path / "a.cpp").write_text("void render() {}\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "render" in nodes
        assert nodes["render"].type == "function"


class TestGoExtraction:
    """Go: function_declaration, method_declaration, type_spec struct/interface (spec R4)."""

    def test_go_standalone_function_extracted(self, tmp_path):
        src = "package main\nfunc Standalone() {}\n"
        (tmp_path / "a.go").write_text(src)
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Standalone" in nodes
        assert nodes["Standalone"].type == "function"

    def test_go_method_extracted_as_method(self, tmp_path):
        src = "package main\ntype Shape struct{}\nfunc (s Shape) Draw() {}\n"
        (tmp_path / "a.go").write_text(src)
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Draw" in nodes
        assert nodes["Draw"].type == "method"

    def test_go_struct_extracted_as_class(self, tmp_path):
        src = "package main\ntype Shape struct { X int }\n"
        (tmp_path / "a.go").write_text(src)
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Shape" in nodes
        assert nodes["Shape"].type == "class"

    def test_go_interface_extracted_as_class(self, tmp_path):
        src = "package main\ntype Drawable interface { Draw() }\n"
        (tmp_path / "a.go").write_text(src)
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Drawable" in nodes
        assert nodes["Drawable"].type == "class"


class TestConfigFallback:
    """Unknown language uses old substring fallback (spec R2)."""

    def test_unknown_language_fallback_extracts_function_definition(self, tmp_path):
        import tree_sitter_python
        from tree_sitter import Language, Parser

        from the_door.core.extraction.node_builder import NodeBuilder
        from the_door.models import FileInfo

        lang = Language(tree_sitter_python.language())
        parser = Parser(lang)
        tree = parser.parse(b"def foo(): pass")
        file_info = FileInfo(path="x.unknown", language="unknown_lang")
        nb = NodeBuilder()
        results = []
        nb._walk_config_driven(tree.root_node, file_info, results, None)
        names = {n.name for n in results}
        assert "foo" in names

    def test_unknown_language_fallback_extracts_class_declaration(self, tmp_path):
        import tree_sitter_python
        from tree_sitter import Language, Parser

        from the_door.core.extraction.node_builder import NodeBuilder
        from the_door.models import FileInfo

        lang = Language(tree_sitter_python.language())
        parser = Parser(lang)
        tree = parser.parse(b"class Bar: pass")
        file_info = FileInfo(path="x.unknown", language="unknown_lang")
        nb = NodeBuilder()
        results = []
        nb._walk_config_driven(tree.root_node, file_info, results, None)
        names = {n.name for n in results}
        assert "Bar" in names
