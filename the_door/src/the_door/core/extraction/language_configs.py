"""Per-language tree-sitter node-type maps for config-driven extraction.

Data ported from codegraph commit 5aae9c4bbff4fe02f8284ef5f91dd9d5391027f6
(MIT License, Copyright (c) 2026 Colby Mchenry),
files src/extraction/languages/*.ts.
See .kiro/specs/multilang-node-extraction/spec.md section 4.1 for the
full citation table.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ImportStrategy = Literal["qualified", "namespaced", "module_path", "es_module"]
FunctionStrategy = Literal["file_local_then_imports", "package_local_then_imports", "global"]
MethodStrategy = Literal["class_local_then_inherited", "structural", "trait_dispatch", "dynamic_dispatch"]
InheritanceStrategy = Literal["single", "multiple", "mixin", "interface_only"]


@dataclass(frozen=True)
class ScopeRules:
    """Language-specific scope resolution rules for edge building."""

    import_resolution: ImportStrategy
    function_resolution: FunctionStrategy
    method_resolution: MethodStrategy
    inheritance_resolution: InheritanceStrategy
    dynamic_markers: frozenset[str] = field(default_factory=frozenset)


@dataclass
class ScopeContext:
    """Runtime context passed to edge resolution logic."""

    current_file: str
    import_aliases: dict[str, str]
    caller_class: str | None
    caller_name: str = ""

    def has_dynamic_marker(self, markers: frozenset[str]) -> bool:
        """Return True if caller_name is in the given dynamic markers set."""
        return bool(markers) and self.caller_name in markers


@dataclass(frozen=True)
class LanguageConfig:
    # ── 既有欄位（節點識別，codegraph 引入時就有） ──
    function_types: frozenset[str] = field(default_factory=frozenset)
    method_types: frozenset[str] = field(default_factory=frozenset)
    class_types: frozenset[str] = field(default_factory=frozenset)
    # Container nodes: establish a parent scope (so inner functions become
    # methods) but do not themselves produce an ASTNode. Only Rust uses this
    # (impl_item). See spec § 5.2 step 2b.
    container_types: frozenset[str] = field(default_factory=frozenset)

    # ── 新增欄位（detail 模式 ASTNode 充實用，Task 02/03 會用） ──
    parameters_field: str | None = None
    """tree-sitter field name for parameters node, e.g. "parameters"."""

    return_type_field: str | None = None
    """tree-sitter field name for return type node, e.g. "return_type"."""

    doc_comment_strategy: str | None = None
    """如何尋找 doc comment：
    - "preceding_line_comments"：往前掃連續的 line comment 節點
    - "preceding_block_comment"：往前掃單一 block comment 節點
    - None：不抽 doc comment
    """

    doc_comment_types: frozenset[str] = field(default_factory=frozenset)
    """tree-sitter comment node types 集合（如 {"line_comment", "block_comment"}）。"""

    doc_comment_markers: frozenset[str] = field(default_factory=frozenset)
    """選填的 doc-comment 前綴字串集合。空 = 接受所有匹配 type 的註解；
    非空 = 只保留以集合內某個字串開頭的註解。
    e.g. Rust {"///", "//!"} 區分 outer/inner doc；C# {"///"}。"""

    decorator_types: frozenset[str] = field(default_factory=frozenset)
    """tree-sitter 節點型別中視為 decorator / annotation / attribute 的集合。
    輸出寫入 ASTNode.decorators（與 Python/TS walker 行為對齊）。
    e.g. Rust {"attribute_item"}、Java {"annotation", "marker_annotation"}。"""

    scope_rules: "ScopeRules | None" = None
    """Language-specific scope resolution rules. None = not yet configured."""


LANGUAGE_CONFIGS: dict[str, LanguageConfig] = {
    "python": LanguageConfig(
        function_types=frozenset({"function_definition"}),
        method_types=frozenset({"function_definition"}),
        class_types=frozenset({"class_definition"}),
        decorator_types=frozenset({"decorator"}),
        scope_rules=ScopeRules(
            import_resolution="qualified",
            function_resolution="file_local_then_imports",
            method_resolution="class_local_then_inherited",
            inheritance_resolution="multiple",
            dynamic_markers=frozenset({"__getattr__", "getattr"}),
        ),
    ),
    "typescript": LanguageConfig(
        function_types=frozenset({"function_declaration"}),
        method_types=frozenset({"method_definition"}),
        class_types=frozenset({"class_declaration"}),
        decorator_types=frozenset({"decorator"}),
        scope_rules=ScopeRules(
            import_resolution="es_module",
            function_resolution="file_local_then_imports",
            method_resolution="class_local_then_inherited",
            inheritance_resolution="single",
            dynamic_markers=frozenset({"any_typed_call"}),
        ),
    ),
    "javascript": LanguageConfig(
        function_types=frozenset({"function_declaration"}),
        method_types=frozenset({"method_definition"}),
        class_types=frozenset({"class_declaration"}),
        decorator_types=frozenset({"decorator"}),
        scope_rules=ScopeRules(
            import_resolution="es_module",
            function_resolution="file_local_then_imports",
            method_resolution="class_local_then_inherited",
            inheritance_resolution="single",
            dynamic_markers=frozenset(),
        ),
    ),
    "java": LanguageConfig(
        function_types=frozenset(),
        method_types=frozenset({"method_declaration", "constructor_declaration"}),
        class_types=frozenset({"class_declaration", "interface_declaration", "enum_declaration"}),
        parameters_field="parameters",
        return_type_field="type",
        doc_comment_strategy="preceding_block_comment",
        doc_comment_types=frozenset({"block_comment"}),
        doc_comment_markers=frozenset(),
        decorator_types=frozenset({"annotation", "marker_annotation"}),
        scope_rules=ScopeRules(
            import_resolution="namespaced",
            function_resolution="package_local_then_imports",
            method_resolution="class_local_then_inherited",
            inheritance_resolution="single",
            dynamic_markers=frozenset({"reflection_invoke"}),
        ),
    ),
    "go": LanguageConfig(
        function_types=frozenset({"function_declaration"}),
        method_types=frozenset({"method_declaration"}),
        class_types=frozenset(),  # handled via type_spec special case in _walk_config_driven
        parameters_field="parameters",
        return_type_field="result",
        doc_comment_strategy="preceding_line_comments",
        doc_comment_types=frozenset({"comment"}),
        doc_comment_markers=frozenset(),
        decorator_types=frozenset(),
        scope_rules=ScopeRules(
            import_resolution="module_path",
            function_resolution="package_local_then_imports",
            method_resolution="structural",
            inheritance_resolution="interface_only",
            dynamic_markers=frozenset({"reflect_value_call"}),
        ),
    ),
    "rust": LanguageConfig(
        function_types=frozenset({"function_item"}),
        method_types=frozenset({"function_item"}),
        class_types=frozenset({"struct_item", "enum_item", "trait_item"}),
        container_types=frozenset({"impl_item"}),
        parameters_field="parameters",
        return_type_field="return_type",
        doc_comment_strategy="preceding_line_comments",
        doc_comment_types=frozenset({"line_comment", "block_comment"}),
        doc_comment_markers=frozenset({"///", "//!"}),
        decorator_types=frozenset({"attribute_item"}),
        scope_rules=ScopeRules(
            import_resolution="module_path",
            function_resolution="package_local_then_imports",
            method_resolution="trait_dispatch",
            inheritance_resolution="single",
            dynamic_markers=frozenset({"dyn_trait_call"}),
        ),
    ),
    "ruby": LanguageConfig(
        function_types=frozenset({"method"}),
        method_types=frozenset({"method", "singleton_method"}),
        class_types=frozenset({"class"}),
        parameters_field="parameters",
        return_type_field=None,
        doc_comment_strategy="preceding_line_comments",
        doc_comment_types=frozenset({"comment"}),
        doc_comment_markers=frozenset(),
        decorator_types=frozenset(),
    ),
    "php": LanguageConfig(
        function_types=frozenset({"function_definition"}),
        method_types=frozenset({"method_declaration"}),
        class_types=frozenset({
            "class_declaration", "trait_declaration",
            "interface_declaration", "enum_declaration",
        }),
        parameters_field="parameters",
        return_type_field="return_type",
        doc_comment_strategy="preceding_block_comment",
        doc_comment_types=frozenset({"comment"}),
        doc_comment_markers=frozenset({"/**"}),
        decorator_types=frozenset(),
    ),
    "csharp": LanguageConfig(
        function_types=frozenset(),
        method_types=frozenset({"method_declaration", "constructor_declaration"}),
        class_types=frozenset({
            "class_declaration", "interface_declaration",
            "struct_declaration", "enum_declaration",
        }),
        parameters_field="parameter_list",
        return_type_field="type",
        doc_comment_strategy="preceding_line_comments",
        doc_comment_types=frozenset({"comment"}),
        doc_comment_markers=frozenset({"///"}),
        decorator_types=frozenset({"attribute_list"}),
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
