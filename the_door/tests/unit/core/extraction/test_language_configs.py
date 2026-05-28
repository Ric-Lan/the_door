"""Tests for LanguageConfig schema extension (Task 01)."""
from __future__ import annotations

import pytest

from the_door.core.extraction.language_configs import (
    LANGUAGE_CONFIGS,
    LanguageConfig,
)


class TestLanguageConfigSchema:
    """LanguageConfig must expose 6 new optional extraction-rule fields."""

    def test_has_parameters_field(self):
        cfg = LanguageConfig()
        assert cfg.parameters_field is None  # default

    def test_has_return_type_field(self):
        cfg = LanguageConfig()
        assert cfg.return_type_field is None

    def test_has_doc_comment_strategy(self):
        cfg = LanguageConfig()
        assert cfg.doc_comment_strategy is None

    def test_has_doc_comment_types_default_empty_frozenset(self):
        cfg = LanguageConfig()
        assert cfg.doc_comment_types == frozenset()

    def test_has_doc_comment_markers_default_empty_frozenset(self):
        cfg = LanguageConfig()
        assert cfg.doc_comment_markers == frozenset()

    def test_has_decorator_types_default_empty_frozenset(self):
        cfg = LanguageConfig()
        assert cfg.decorator_types == frozenset()

    def test_legacy_fields_still_present(self):
        cfg = LanguageConfig()
        assert cfg.function_types == frozenset()
        assert cfg.method_types == frozenset()
        assert cfg.class_types == frozenset()
        assert cfg.container_types == frozenset()

    def test_dataclass_is_frozen(self):
        cfg = LanguageConfig()
        with pytest.raises(Exception):  # FrozenInstanceError
            cfg.parameters_field = "foo"  # type: ignore[misc]


class TestLanguageRules:
    """Each registered language gets its extraction-rule fields populated."""

    @pytest.mark.parametrize("lang", ["java", "go", "rust", "ruby", "php", "csharp"])
    def test_language_has_parameters_field(self, lang):
        cfg = LANGUAGE_CONFIGS[lang]
        assert cfg.parameters_field is not None, f"{lang} missing parameters_field"

    def test_rust_doc_comment_markers_have_both_outer_and_inner(self):
        cfg = LANGUAGE_CONFIGS["rust"]
        assert "///" in cfg.doc_comment_markers
        assert "//!" in cfg.doc_comment_markers

    def test_rust_decorator_types_include_attribute_item(self):
        cfg = LANGUAGE_CONFIGS["rust"]
        assert "attribute_item" in cfg.decorator_types

    def test_java_decorator_types_include_annotation(self):
        cfg = LANGUAGE_CONFIGS["java"]
        assert "annotation" in cfg.decorator_types
        assert "marker_annotation" in cfg.decorator_types

    def test_csharp_doc_comment_marker_triple_slash(self):
        cfg = LANGUAGE_CONFIGS["csharp"]
        assert "///" in cfg.doc_comment_markers

    def test_php_doc_comment_marker_phpdoc(self):
        cfg = LANGUAGE_CONFIGS["php"]
        assert "/**" in cfg.doc_comment_markers

    def test_go_no_doc_comment_markers(self):
        cfg = LANGUAGE_CONFIGS["go"]
        assert cfg.doc_comment_markers == frozenset()

    def test_ruby_no_decorator_types(self):
        cfg = LANGUAGE_CONFIGS["ruby"]
        assert cfg.decorator_types == frozenset()

    @pytest.mark.parametrize("lang,strategy", [
        ("java", "preceding_block_comment"),
        ("go", "preceding_line_comments"),
        ("rust", "preceding_line_comments"),
        ("ruby", "preceding_line_comments"),
        ("php", "preceding_block_comment"),
        ("csharp", "preceding_line_comments"),
    ])
    def test_doc_comment_strategy(self, lang, strategy):
        cfg = LANGUAGE_CONFIGS[lang]
        assert cfg.doc_comment_strategy == strategy

    def test_python_typescript_javascript_not_extended(self):
        """專用 walker 處理 — config-driven 欄位保持預設。"""
        for lang in ("python", "typescript", "javascript"):
            if lang not in LANGUAGE_CONFIGS:
                continue
            cfg = LANGUAGE_CONFIGS[lang]
            assert cfg.parameters_field is None
            assert cfg.doc_comment_strategy is None
