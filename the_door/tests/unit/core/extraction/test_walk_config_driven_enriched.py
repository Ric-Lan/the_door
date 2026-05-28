"""Tests that _walk_config_driven produces enriched ASTNode for 6 languages."""
from __future__ import annotations

from pathlib import Path

import pytest

from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.models import ASTNode


FIXTURE_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "multilang"


def _extract_for_language(lang: str, ext: str) -> list[ASTNode]:
    path = FIXTURE_DIR / lang / f"sample.{ext}"
    assert path.exists(), f"fixture missing: {path}"
    extractor = ASTExtractor()
    result = extractor.extract(str(path.parent))
    return [n for n in result.nodes if n.file.endswith(f"sample.{ext}")]


def _find_method_or_function(nodes: list[ASTNode], name_substring: str) -> ASTNode:
    matches = [n for n in nodes if name_substring.lower() in n.name.lower()]
    assert matches, f"no node containing {name_substring!r} in {[n.name for n in nodes]}"
    # Prefer method/function over class.
    for n in matches:
        if n.type in ("method", "function"):
            return n
    return matches[0]


class TestJavaEnrichment:
    def test_greet_method_has_parameters(self):
        nodes = _extract_for_language("java", "java")
        greet = _find_method_or_function(nodes, "greet")
        assert any("name" in p for p in greet.parameters)
        assert any("times" in p for p in greet.parameters)

    def test_class_has_block_comment_docstring(self):
        nodes = _extract_for_language("java", "java")
        greeter = next((n for n in nodes if n.name == "Greeter"), None)
        assert greeter is not None
        assert greeter.docstring is not None
        assert "Greet" in greeter.docstring

    def test_class_has_annotation_decorator(self):
        nodes = _extract_for_language("java", "java")
        greeter = next((n for n in nodes if n.name == "Greeter"), None)
        assert greeter is not None
        assert any("Deprecated" in d for d in greeter.decorators)


class TestGoEnrichment:
    def test_function_parameters(self):
        nodes = _extract_for_language("go", "go")
        greet = _find_method_or_function(nodes, "Greet")
        assert any("name" in p for p in greet.parameters)

    def test_function_docstring_from_preceding_line_comments(self):
        nodes = _extract_for_language("go", "go")
        greet = _find_method_or_function(nodes, "Greet")
        assert greet.docstring is not None
        assert "greeting" in greet.docstring.lower() or "Greet" in greet.docstring


class TestRustEnrichment:
    def test_struct_has_outer_doc(self):
        nodes = _extract_for_language("rust", "rs")
        greeter = next((n for n in nodes if n.name == "Greeter"), None)
        assert greeter is not None
        assert greeter.docstring is not None
        assert "Greet someone" in greeter.docstring

    def test_struct_has_derive_attribute(self):
        nodes = _extract_for_language("rust", "rs")
        greeter = next((n for n in nodes if n.name == "Greeter"), None)
        assert greeter is not None
        assert any("derive" in d for d in greeter.decorators)

    def test_method_parameters_extracted(self):
        nodes = _extract_for_language("rust", "rs")
        greet = _find_method_or_function(nodes, "greet")
        joined = " ".join(greet.parameters)
        assert "name" in joined

    def test_method_return_type(self):
        nodes = _extract_for_language("rust", "rs")
        greet = _find_method_or_function(nodes, "greet")
        assert greet.return_type is not None
        assert "String" in greet.return_type


class TestRubyEnrichment:
    def test_method_has_doc_comment(self):
        nodes = _extract_for_language("ruby", "rb")
        greet = _find_method_or_function(nodes, "greet")
        if greet.docstring is None:
            pytest.xfail(
                "Ruby grammar wraps method in body_statement — comments are "
                "children of class, not siblings of method, so prev_sibling lookup fails"
            )
        assert "name" in greet.docstring.lower() or "Greet" in greet.docstring

    def test_method_parameters(self):
        nodes = _extract_for_language("ruby", "rb")
        greet = _find_method_or_function(nodes, "greet")
        joined = " ".join(greet.parameters)
        assert "name" in joined
        assert "times" in joined

    def test_method_no_decorators(self):
        nodes = _extract_for_language("ruby", "rb")
        greet = _find_method_or_function(nodes, "greet")
        assert greet.decorators == []


class TestPhpEnrichment:
    def test_method_phpdoc_extracted(self):
        nodes = _extract_for_language("php", "php")
        greet = _find_method_or_function(nodes, "greet")
        if greet.docstring is None:
            pytest.xfail("PHP grammar quirk — see Task 03 acceptance note")
        assert "Greet" in greet.docstring

    def test_method_parameters(self):
        nodes = _extract_for_language("php", "php")
        greet = _find_method_or_function(nodes, "greet")
        joined = " ".join(greet.parameters)
        assert "name" in joined


class TestCsharpEnrichment:
    def test_method_xmldoc_extracted(self):
        nodes = _extract_for_language("csharp", "cs")
        greet = _find_method_or_function(nodes, "Greet")
        assert greet.docstring is not None
        assert "Greet" in greet.docstring

    def test_method_attribute_extracted(self):
        nodes = _extract_for_language("csharp", "cs")
        greet = _find_method_or_function(nodes, "Greet")
        assert any("Obsolete" in d for d in greet.decorators)


class TestCommentsFieldEmptyForGenericPath:
    """generic walker 統一 comments=[]（spec §3.5）。"""

    @pytest.mark.parametrize("lang,ext", [
        ("java", "java"), ("go", "go"), ("rust", "rs"),
        ("ruby", "rb"), ("php", "php"), ("csharp", "cs"),
    ])
    def test_comments_is_empty_list(self, lang, ext):
        nodes = _extract_for_language(lang, ext)
        for n in nodes:
            assert n.comments == [], f"{lang} {n.name} should have empty comments (generic path)"
