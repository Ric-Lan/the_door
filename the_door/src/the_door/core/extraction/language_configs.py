"""Per-language tree-sitter node-type maps for config-driven extraction.

Data ported from codegraph commit 5aae9c4bbff4fe02f8284ef5f91dd9d5391027f6
(MIT License, Copyright (c) 2026 Colby Mchenry),
files src/extraction/languages/*.ts.
See .kiro/specs/multilang-node-extraction/spec.md section 4.1 for the
full citation table.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LanguageConfig:
    function_types: frozenset[str] = field(default_factory=frozenset)
    method_types: frozenset[str] = field(default_factory=frozenset)
    class_types: frozenset[str] = field(default_factory=frozenset)
    # Container nodes: establish a parent scope (so inner functions become
    # methods) but do not themselves produce an ASTNode. Only Rust uses this
    # (impl_item). See spec § 5.2 step 2b.
    container_types: frozenset[str] = field(default_factory=frozenset)


LANGUAGE_CONFIGS: dict[str, LanguageConfig] = {
    "java": LanguageConfig(
        function_types=frozenset(),
        method_types=frozenset({"method_declaration", "constructor_declaration"}),
        class_types=frozenset({"class_declaration", "interface_declaration", "enum_declaration"}),
    ),
    "go": LanguageConfig(
        function_types=frozenset({"function_declaration"}),
        method_types=frozenset({"method_declaration"}),
        class_types=frozenset(),  # handled via type_spec special case in _walk_config_driven
    ),
    "rust": LanguageConfig(
        function_types=frozenset({"function_item"}),
        method_types=frozenset({"function_item"}),
        class_types=frozenset({"struct_item", "enum_item", "trait_item"}),
        container_types=frozenset({"impl_item"}),
    ),
    "ruby": LanguageConfig(
        function_types=frozenset({"method"}),
        method_types=frozenset({"method", "singleton_method"}),
        class_types=frozenset({"class"}),
    ),
    "php": LanguageConfig(
        function_types=frozenset({"function_definition"}),
        method_types=frozenset({"method_declaration"}),
        class_types=frozenset({
            "class_declaration", "trait_declaration",
            "interface_declaration", "enum_declaration",
        }),
    ),
    "csharp": LanguageConfig(
        function_types=frozenset(),
        method_types=frozenset({"method_declaration", "constructor_declaration"}),
        class_types=frozenset({
            "class_declaration", "interface_declaration",
            "struct_declaration", "enum_declaration",
        }),
    ),
    "c": LanguageConfig(
        function_types=frozenset({"function_definition"}),
        method_types=frozenset(),
        class_types=frozenset({"struct_specifier", "enum_specifier"}),
    ),
    "cpp": LanguageConfig(
        function_types=frozenset({"function_definition"}),
        method_types=frozenset({"function_definition"}),
        class_types=frozenset({"class_specifier", "struct_specifier", "enum_specifier"}),
    ),
}
