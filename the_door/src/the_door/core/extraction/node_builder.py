"""Node builder module — walks tree-sitter AST to extract function, class, and method nodes."""
from __future__ import annotations

import hashlib
from pathlib import Path

from tree_sitter import Node as TSNode

from the_door.models import ASTNode, FileInfo
from the_door.core.extraction.language_configs import LANGUAGE_CONFIGS


class NodeBuilder:
    """Walk a tree-sitter AST and extract function, class, and method nodes."""

    def build_nodes(self, tree, file_info: FileInfo, codebase_root: Path) -> list[ASTNode]:
        """Extract function/class/method nodes from a parsed tree-sitter tree."""
        self._codebase_root = codebase_root
        self._body_file_cache: dict[str, list[str]] = {}
        nodes: list[ASTNode] = []
        self._walk(tree.root_node, file_info, nodes, parent_class=None)
        return nodes

    def _abs_path(self, rel_path: str) -> str | None:
        """Return absolute path for rel_path, or None if codebase_root is not set."""
        root = getattr(self, "_codebase_root", None)
        if root is None:
            return None
        return str(root / rel_path)

    def _compute_body_hash(self, file_path: str | None, start_line: int | None, end_line: int | None) -> str | None:
        if file_path is None or start_line is None or end_line is None:
            return None
        cache = getattr(self, "_body_file_cache", {})
        if file_path not in cache:
            try:
                with open(file_path, encoding="utf-8", errors="replace") as f:
                    cache[file_path] = f.readlines()
            except OSError:
                cache[file_path] = []
            self._body_file_cache = cache
        lines = cache[file_path]
        if not lines:
            return None
        body = "".join(lines[start_line - 1 : end_line])
        return hashlib.md5(body.encode("utf-8")).hexdigest()

    def _walk(
        self,
        node: TSNode,
        file_info: FileInfo,
        results: list[ASTNode],
        parent_class: str | None,
    ) -> None:
        """Recursively walk the AST and collect function/class/method definitions."""
        if file_info.language == "python":
            self._walk_python(node, file_info, results, parent_class)
        elif file_info.language in ("typescript", "javascript"):
            self._walk_typescript(node, file_info, results, parent_class)
        else:
            # Basic fallback: look for function_definition and class_definition
            self._walk_config_driven(node, file_info, results, parent_class)

    # ── Python ──────────────────────────────────────────────────────────

    def _walk_python(
        self,
        node: TSNode,
        file_info: FileInfo,
        results: list[ASTNode],
        parent_class: str | None,
    ) -> None:
        if node.type == "decorated_definition":
            self._handle_python_decorated(node, file_info, results, parent_class)
            return

        if node.type == "function_definition":
            results.append(
                self._build_python_function(node, file_info, parent_class, decorators=[])
            )
            return

        if node.type == "class_definition":
            self._handle_python_class(node, file_info, results, decorators=[])
            return

        for child in node.children:
            self._walk_python(child, file_info, results, parent_class)

    def _handle_python_decorated(
        self,
        node: TSNode,
        file_info: FileInfo,
        results: list[ASTNode],
        parent_class: str | None,
    ) -> None:
        """Handle a decorated_definition node (decorator + function/class)."""
        decorators: list[str] = []
        definition = None
        for child in node.children:
            if child.type == "decorator":
                decorators.append(self._extract_decorator_text(child))
            elif child.type == "function_definition":
                definition = child
            elif child.type == "class_definition":
                definition = child

        if definition is None:
            return

        if definition.type == "function_definition":
            results.append(
                self._build_python_function(
                    definition, file_info, parent_class, decorators,
                    outer_start_line=node.start_point[0] + 1,
                )
            )
        elif definition.type == "class_definition":
            self._handle_python_class(
                definition, file_info, results, decorators,
                outer_start_line=node.start_point[0] + 1,
            )

    def _handle_python_class(
        self,
        node: TSNode,
        file_info: FileInfo,
        results: list[ASTNode],
        decorators: list[str],
        outer_start_line: int | None = None,
    ) -> None:
        """Extract a class node and recurse into its body for methods."""
        name = self._child_text(node, "identifier")
        if not name:
            return

        docstring = self._extract_python_docstring(node)
        comments = self._collect_nearby_comments(node)

        _start = outer_start_line if outer_start_line is not None else node.start_point[0] + 1
        _end = node.end_point[0] + 1
        results.append(
            ASTNode(
                node_id=f"{file_info.path}::{name}",
                type="class",
                name=name,
                file=file_info.path,
                language=file_info.language,
                start_line=_start,
                end_line=_end,
                body_hash=self._compute_body_hash(
                    self._abs_path(file_info.path), _start, _end
                ),
                decorators=decorators,
                parameters=[],
                return_type=None,
                docstring=docstring,
                comments=comments,
            )
        )

        # Recurse into class body for methods
        body = self._find_child(node, "block")
        if body:
            for child in body.children:
                self._walk_python(child, file_info, results, parent_class=name)

    def _build_python_function(
        self,
        node: TSNode,
        file_info: FileInfo,
        parent_class: str | None,
        decorators: list[str],
        outer_start_line: int | None = None,
    ) -> ASTNode:
        """Build an ASTNode from a Python function_definition."""
        name = self._child_text(node, "identifier")
        params = self._extract_python_params(node)
        return_type = self._extract_python_return_type(node)
        docstring = self._extract_python_docstring(node)
        comments = self._collect_nearby_comments(node)
        node_type = "method" if parent_class else "function"

        _start = outer_start_line if outer_start_line is not None else node.start_point[0] + 1
        _end = node.end_point[0] + 1
        return ASTNode(
            node_id=f"{file_info.path}::{name}",
            type=node_type,
            name=name,
            file=file_info.path,
            language=file_info.language,
            start_line=_start,
            end_line=_end,
            body_hash=self._compute_body_hash(
                self._abs_path(file_info.path), _start, _end
            ),
            decorators=decorators,
            parameters=params,
            return_type=return_type,
            docstring=docstring,
            comments=comments,
        )

    def _extract_python_params(self, func_node: TSNode) -> list[str]:
        """Extract parameter strings from a function_definition."""
        params_node = self._find_child(func_node, "parameters")
        if not params_node:
            return []
        result: list[str] = []
        for child in params_node.children:
            if child.type in ("identifier", "typed_parameter", "default_parameter",
                              "typed_default_parameter", "list_splat_pattern",
                              "dictionary_splat_pattern"):
                text = child.text.decode("utf-8", errors="replace")
                result.append(text)
        return result

    def _extract_python_return_type(self, func_node: TSNode) -> str | None:
        """Extract return type annotation from a function_definition."""
        ret_type = self._find_child(func_node, "type")
        if ret_type:
            return ret_type.text.decode("utf-8", errors="replace")
        return None

    def _extract_python_docstring(self, def_node: TSNode) -> str | None:
        """Extract docstring from a function or class definition.

        The docstring is the first expression_statement containing a string
        in the body block. Falls back to raw source extraction when tree-sitter
        produces an ERROR node (e.g., for docstrings containing quote characters).
        """
        # First check for ERROR nodes as direct children of the definition
        # (tree-sitter may place the error before the block when docstrings
        # contain quote characters that confuse the parser)
        for child in def_node.children:
            if child.type == "ERROR":
                result = self._extract_docstring_from_error(child)
                if result is not None:
                    return result

        body = self._find_child(def_node, "block")
        if not body:
            return None

        for child in body.children:
            if child.type == "expression_statement":
                for sub in child.children:
                    if sub.type == "string":
                        return self._strip_string_quotes(sub.text.decode("utf-8", errors="replace"))
                break  # Only check the first expression_statement
            elif child.type == "ERROR":
                # tree-sitter couldn't parse the docstring (e.g., contains quotes)
                # Fall back to extracting from raw source text
                result = self._extract_docstring_from_error(child)
                if result is not None:
                    return result

        return None

    def _extract_docstring_from_error(self, error_node: TSNode) -> str | None:
        """Try to extract a docstring from an ERROR node using raw text.

        When tree-sitter can't parse a docstring (e.g., it contains quote
        characters), we fall back to scanning the raw text for triple-quoted
        strings.
        """
        raw = error_node.text.decode("utf-8", errors="replace").strip()
        # Try triple-double-quote extraction with greedy matching
        for quote in ('"""', "'''"):
            if raw.startswith(quote):
                # Find the LAST occurrence of the closing triple quote
                # (handles cases where content contains quotes)
                end_idx = raw.rfind(quote, len(quote))
                if end_idx > len(quote) - 1:
                    return raw[len(quote):end_idx].replace("\r\n", "\n")
                # If rfind only finds the opening, try find
                end_idx = raw.find(quote, len(quote))
                if end_idx != -1:
                    return raw[len(quote):end_idx].replace("\r\n", "\n")
        return None

    @staticmethod
    def _strip_string_quotes(s: str) -> str:
        """Strip triple or single quotes from a string literal and normalise line endings."""
        for quote in ('"""', "'''"):
            if s.startswith(quote) and s.endswith(quote):
                return s[3:-3].replace("\r\n", "\n")
        for quote in ('"', "'"):
            if s.startswith(quote) and s.endswith(quote):
                return s[1:-1].replace("\r\n", "\n")
        return s.replace("\r\n", "\n")

    def _extract_decorator_text(self, decorator_node: TSNode) -> str:
        """Extract the decorator text without the @ symbol."""
        text = decorator_node.text.decode("utf-8", errors="replace")
        # Remove leading @
        if text.startswith("@"):
            text = text[1:]
        return text

    # ── TypeScript / JavaScript ─────────────────────────────────────────

    def _walk_typescript(
        self,
        node: TSNode,
        file_info: FileInfo,
        results: list[ASTNode],
        parent_class: str | None,
    ) -> None:
        """Walk TypeScript/JavaScript AST."""
        if node.type in ("function_declaration", "function"):
            name = self._child_text(node, "identifier")
            if name:
                results.append(self._build_ts_function(node, file_info, name, parent_class))
            return

        if node.type in ("class_declaration", "class"):
            self._handle_ts_class(node, file_info, results)
            return

        if node.type == "method_definition" and parent_class:
            name = self._child_text(node, "property_identifier")
            if name:
                results.append(self._build_ts_method(node, file_info, name, parent_class))
            return

        for child in node.children:
            self._walk_typescript(child, file_info, results, parent_class)

    def _handle_ts_class(
        self,
        node: TSNode,
        file_info: FileInfo,
        results: list[ASTNode],
    ) -> None:
        name = self._child_text(node, "type_identifier")
        if not name:
            return

        docstring = self._extract_ts_jsdoc(node)
        results.append(
            ASTNode(
                node_id=f"{file_info.path}::{name}",
                type="class",
                name=name,
                file=file_info.path,
                language=file_info.language,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                body_hash=self._compute_body_hash(
                    self._abs_path(file_info.path),
                    node.start_point[0] + 1,
                    node.end_point[0] + 1,
                ),
                decorators=[],
                parameters=[],
                return_type=None,
                docstring=docstring,
                comments=[],
            )
        )

        body = self._find_child(node, "class_body")
        if body:
            for child in body.children:
                self._walk_typescript(child, file_info, results, parent_class=name)

    def _build_ts_function(
        self, node: TSNode, file_info: FileInfo, name: str, parent_class: str | None
    ) -> ASTNode:
        docstring = self._extract_ts_jsdoc(node)
        return ASTNode(
            node_id=f"{file_info.path}::{name}",
            type="method" if parent_class else "function",
            name=name,
            file=file_info.path,
            language=file_info.language,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            body_hash=self._compute_body_hash(
                self._abs_path(file_info.path),
                node.start_point[0] + 1,
                node.end_point[0] + 1,
            ),
            decorators=[],
            parameters=[],
            return_type=None,
            docstring=docstring,
            comments=[],
        )

    def _build_ts_method(
        self, node: TSNode, file_info: FileInfo, name: str, parent_class: str
    ) -> ASTNode:
        docstring = self._extract_ts_jsdoc(node)
        return ASTNode(
            node_id=f"{file_info.path}::{name}",
            type="method",
            name=name,
            file=file_info.path,
            language=file_info.language,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            body_hash=self._compute_body_hash(
                self._abs_path(file_info.path),
                node.start_point[0] + 1,
                node.end_point[0] + 1,
            ),
            decorators=[],
            parameters=[],
            return_type=None,
            docstring=docstring,
            comments=[],
        )

    def _extract_ts_jsdoc(self, node: TSNode) -> str | None:
        """Extract JSDoc comment preceding a node."""
        prev = node.prev_named_sibling
        if prev and prev.type == "comment":
            text = prev.text.decode("utf-8", errors="replace").strip()
            if text.startswith("/**") and text.endswith("*/"):
                return text[3:-2].strip()
            if text.startswith("//"):
                return text[2:].strip()
        return None

    # ── Generic fallback ────────────────────────────────────────────────

    def _walk_config_driven(
        self,
        node: TSNode,
        file_info: FileInfo,
        results: list[ASTNode],
        parent_class: str | None,
    ) -> None:
        """Config-driven walker for languages covered by LANGUAGE_CONFIGS."""
        cfg = LANGUAGE_CONFIGS.get(file_info.language)
        if cfg is None:
            # Fallback for languages not yet in the config table.
            # Retained so newly-registered grammars get rough extraction
            # rather than nothing.
            if "function_definition" in node.type or "function_declaration" in node.type:
                name = self._child_text(node, "identifier")
                if name:
                    results.append(ASTNode(
                        node_id=f"{file_info.path}::{name}",
                        type="method" if parent_class else "function",
                        name=name,
                        file=file_info.path,
                        language=file_info.language,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        body_hash=self._compute_body_hash(
                            self._abs_path(file_info.path),
                            node.start_point[0] + 1,
                            node.end_point[0] + 1,
                        ),
                    ))
                return
            if "class_definition" in node.type or "class_declaration" in node.type:
                name = self._child_text(node, "identifier") or self._child_text(node, "type_identifier")
                if name:
                    results.append(ASTNode(
                        node_id=f"{file_info.path}::{name}",
                        type="class",
                        name=name,
                        file=file_info.path,
                        language=file_info.language,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        body_hash=self._compute_body_hash(
                            self._abs_path(file_info.path),
                            node.start_point[0] + 1,
                            node.end_point[0] + 1,
                        ),
                    ))
                return
            for child in node.children:
                self._walk_config_driven(child, file_info, results, parent_class)
            return

        # ── Go type_spec special case (spec § 5.3) ──────────────────────
        if file_info.language == "go" and node.type == "type_spec":
            type_child = node.child_by_field_name("type")
            if type_child is not None and type_child.type in ("struct_type", "interface_type"):
                name = self._get_name_by_field(node)
                if name:
                    results.append(
                        self._build_enriched_node(node, cfg, file_info, "class", name)
                    )
            return

        # ── Container nodes (e.g. Rust impl_item): scope but no own node ──
        if node.type in cfg.container_types:
            type_node = node.child_by_field_name("type")
            container_name = (
                type_node.text.decode("utf-8", errors="replace")
                if type_node is not None
                else "__impl__"
            )
            for child in node.children:
                self._walk_config_driven(child, file_info, results, container_name)
            return

        # ── Class nodes ───────────────────────────────────────────────────
        if node.type in cfg.class_types:
            name = self._extract_name(node, file_info.language)
            if name:
                results.append(
                    self._build_enriched_node(node, cfg, file_info, "class", name)
                )
                for child in node.children:
                    self._walk_config_driven(child, file_info, results, name)
            else:
                for child in node.children:
                    self._walk_config_driven(child, file_info, results, parent_class)
            return

        # ── Method nodes (inside a class/container scope) ─────────────────
        if node.type in cfg.method_types and parent_class is not None:
            name = self._extract_name(node, file_info.language)
            if name:
                results.append(
                    self._build_enriched_node(node, cfg, file_info, "method", name)
                )
            return

        # ── Orphaned method nodes (method_types but no parent class) ──────
        # Go methods appear at AST top-level with no class wrapper; they are
        # still methods. Any other language method_type that lacks a class
        # context is also extracted as method rather than silently dropped.
        if node.type in cfg.method_types and node.type not in cfg.function_types:
            name = self._extract_name(node, file_info.language)
            if name:
                results.append(
                    self._build_enriched_node(node, cfg, file_info, "method", name)
                )
            return

        # ── Function nodes (top-level or method_types with no parent) ─────
        if node.type in cfg.function_types:
            name = self._extract_name(node, file_info.language)
            if name:
                results.append(
                    self._build_enriched_node(node, cfg, file_info, "function", name)
                )
            return

        # ── Recurse ───────────────────────────────────────────────────────
        for child in node.children:
            self._walk_config_driven(child, file_info, results, parent_class)

    # ── Enriched-node builder (Task 03) ──────────────────────────────

    def _build_enriched_node(
        self,
        node,
        cfg,         # LanguageConfig
        file_info,   # FileInfo
        kind: str,   # "function" | "method" | "class"
        name: str,
    ) -> ASTNode:
        """Build an ASTNode with all content fields populated via cfg + helpers."""
        return ASTNode(
            node_id=f"{file_info.path}::{name}",
            type=kind,
            name=name,
            file=file_info.path,
            language=file_info.language,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            body_hash=self._compute_body_hash(
                self._abs_path(file_info.path),
                node.start_point[0] + 1,
                node.end_point[0] + 1,
            ),
            parameters=self._extract_parameters(node, cfg.parameters_field),
            return_type=self._extract_return_type(node, cfg.return_type_field),
            decorators=self._extract_decorators(node, cfg.decorator_types),
            docstring=self._extract_doc_comment(
                node,
                cfg.doc_comment_strategy,
                cfg.doc_comment_types,
                cfg.doc_comment_markers,
                skip_types=cfg.decorator_types,
            ),
            comments=[],  # generic 路徑不收 comments
        )

    # ── Generic-walker extract helpers (Task 02) ──────────────────────

    def _extract_parameters(self, node, parameters_field: str | None) -> list[str]:
        """Extract parameter strings from a function/method definition node.

        Returns [] if parameters_field is None or the field is absent.
        Each parameter is returned as raw source text (utf-8 decoded).
        """
        if parameters_field is None:
            return []
        params_node = node.child_by_field_name(parameters_field)
        if params_node is None:
            return []
        result: list[str] = []
        for child in params_node.children:
            # Skip pure punctuation (commas, parens) — they have no name and
            # tree-sitter treats them as separate nodes.
            if child.type in ("(", ")", ",", ";"):
                continue
            text = child.text.decode("utf-8", errors="replace").strip()
            if text:
                result.append(text)
        return result

    def _extract_return_type(self, node, return_type_field: str | None) -> str | None:
        """Extract return-type annotation as raw text.

        Returns None if return_type_field is None or the field is absent.
        """
        if return_type_field is None:
            return None
        rt_node = node.child_by_field_name(return_type_field)
        if rt_node is None:
            return None
        return rt_node.text.decode("utf-8", errors="replace").strip() or None

    def _extract_decorators(self, node, decorator_types: frozenset[str]) -> list[str]:
        """Extract decorator / annotation / attribute text.

        Strategy: scan node's own children + preceding siblings (up to first
        non-decorator non-comment node) for nodes whose type is in
        decorator_types. Each is decoded to raw text.

        Also searches inside a `modifiers` child when present (Java/C# put
        annotations inside a modifiers wrapper node).

        Returns [] if decorator_types is empty.
        """
        if not decorator_types:
            return []
        result: list[str] = []

        # Own children — direct matches and modifiers children (Java/C#)
        for child in node.children:
            if child.type in decorator_types:
                text = child.text.decode("utf-8", errors="replace").strip()
                if text:
                    result.append(text)
            elif child.type == "modifiers":
                # Java/C#: annotations are nested inside a modifiers node
                for mod_child in child.children:
                    if mod_child.type in decorator_types:
                        text = mod_child.text.decode("utf-8", errors="replace").strip()
                        if text:
                            result.append(text)

        # Preceding siblings (most grammars: attributes appear as siblings before
        # the item).
        sibling = node.prev_sibling
        while sibling is not None:
            if sibling.type in decorator_types:
                text = sibling.text.decode("utf-8", errors="replace").strip()
                if text:
                    result.insert(0, text)  # preserve source order
                sibling = sibling.prev_sibling
                continue
            # Stop at the first non-decorator / non-comment sibling.
            # tree-sitter 節點型別名永遠沒有前後空白。
            if sibling.type not in ("comment", "line_comment", "block_comment"):
                break
            sibling = sibling.prev_sibling

        return result

    def _extract_doc_comment(
        self,
        node,
        strategy: str | None,
        types: frozenset[str],
        markers: frozenset[str],
        skip_types: frozenset[str] | None = None,
    ) -> str | None:
        """Extract a doc-comment string preceding the node.

        Strategy:
        - "preceding_line_comments": gather contiguous line-comment siblings
          immediately preceding node, in source order; join with newlines.
        - "preceding_block_comment": take the immediately preceding block
          comment sibling (single node).
        - None or unknown: return None.

        Filtering:
        - Only sibling nodes whose type is in `types` are considered.
        - If `markers` is non-empty, only comments whose raw text (stripped)
          starts with one of the markers are kept.
        - `skip_types`: node types to silently skip when scanning backward
          (e.g. decorator/attribute nodes that appear between doc-comment
          and declaration — common in Rust/C#).
        """
        if strategy is None or not types:
            return None
        _skip = skip_types or frozenset()

        if strategy == "preceding_line_comments":
            collected: list[str] = []
            sibling = node.prev_sibling
            while sibling is not None and (sibling.type in types or sibling.type in _skip):
                if sibling.type in _skip:
                    # Skip decorator/attribute nodes silently — they sit between
                    # doc-comment and declaration in Rust/C# etc.
                    sibling = sibling.prev_sibling
                    continue
                text = sibling.text.decode("utf-8", errors="replace").strip()
                if not text:
                    sibling = sibling.prev_sibling
                    continue
                if markers and not any(text.startswith(m) for m in markers):
                    break  # 連續性中斷 — 遇到非 doc-comment 即停止
                # Strip marker prefix for cleaner output if present.
                cleaned = text
                for m in markers:
                    if cleaned.startswith(m):
                        cleaned = cleaned[len(m):].strip()
                        break
                collected.insert(0, cleaned or text)
                sibling = sibling.prev_sibling
            if not collected:
                return None
            return "\n".join(collected)

        if strategy == "preceding_block_comment":
            sibling = node.prev_sibling
            # Skip whitespace nodes if any (most grammars don't produce them).
            while sibling is not None and not sibling.type.strip():
                sibling = sibling.prev_sibling
            if sibling is None or sibling.type not in types:
                return None
            text = sibling.text.decode("utf-8", errors="replace").strip()
            if not text:
                return None
            if markers and not any(text.startswith(m) for m in markers):
                return None
            return text

        # Unknown strategy — safe fallback.
        return None

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _child_text(node: TSNode, child_type: str) -> str | None:
        """Get the text of the first child with the given type."""
        for child in node.children:
            if child.type == child_type:
                return child.text.decode("utf-8", errors="replace")
        return None

    @staticmethod
    def _get_name_by_field(node: TSNode) -> str | None:
        """Get node name via child_by_field_name('name'), decode if found."""
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return name_node.text.decode("utf-8", errors="replace")
        return None

    @staticmethod
    def _extract_name(node: TSNode, language: str) -> str | None:
        """Extract node name, handling per-language quirks."""
        # C and C++: function name is nested in declarator field
        if language in ("c", "cpp") and node.type == "function_definition":
            decl = node.child_by_field_name("declarator")
            if decl is not None:
                inner = decl.child_by_field_name("declarator")
                if inner is not None:
                    return inner.text.decode("utf-8", errors="replace")
            return None

        # Standard: try name field first, then type_identifier, then identifier
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return name_node.text.decode("utf-8", errors="replace")

        for child_type in ("type_identifier", "identifier"):
            for child in node.children:
                if child.type == child_type:
                    return child.text.decode("utf-8", errors="replace")
        return None

    @staticmethod
    def _find_child(node: TSNode, child_type: str) -> TSNode | None:
        """Find the first child node with the given type."""
        for child in node.children:
            if child.type == child_type:
                return child
        return None

    @staticmethod
    def _collect_nearby_comments(node: TSNode) -> list[str]:
        """Collect TODO/FIXME comments near a function/class definition.

        Checks the previous sibling and comments inside the body.
        """
        comments: list[str] = []

        # Check previous sibling for comments (e.g., # TODO above function)
        prev = node.prev_named_sibling
        if prev and prev.type == "comment":
            text = prev.text.decode("utf-8", errors="replace")
            if any(marker in text.upper() for marker in ("TODO", "FIXME")):
                comments.append(text)

        # Also check the parent's previous sibling (for decorated definitions)
        parent = node.parent
        if parent and parent.type == "decorated_definition":
            prev_parent = parent.prev_named_sibling
            if prev_parent and prev_parent.type == "comment":
                text = prev_parent.text.decode("utf-8", errors="replace")
                if any(marker in text.upper() for marker in ("TODO", "FIXME")):
                    comments.append(text)

        # Check comments inside the function body
        body = None
        for child in node.children:
            if child.type == "block":
                body = child
                break

        if body:
            for child in body.children:
                if child.type == "comment":
                    text = child.text.decode("utf-8", errors="replace")
                    if any(marker in text.upper() for marker in ("TODO", "FIXME")):
                        comments.append(text)

        return comments
