"""Node builder module — walks tree-sitter AST to extract function, class, and method nodes."""
from __future__ import annotations

from tree_sitter import Node as TSNode

from the_door.models import ASTNode, FileInfo


class NodeBuilder:
    """Walk a tree-sitter AST and extract function, class, and method nodes."""

    def build_nodes(self, tree, file_info: FileInfo) -> list[ASTNode]:
        """Extract function/class/method nodes from a parsed tree-sitter tree.

        Parameters
        ----------
        tree : tree_sitter.Tree
            The parsed tree-sitter tree.
        file_info : FileInfo
            Metadata about the source file (path, language).

        Returns
        -------
        list[ASTNode]
            Extracted nodes with all required attributes.
        """
        nodes: list[ASTNode] = []
        self._walk(tree.root_node, file_info, nodes, parent_class=None)
        return nodes

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
            self._walk_generic(node, file_info, results, parent_class)

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
                self._build_python_function(definition, file_info, parent_class, decorators)
            )
        elif definition.type == "class_definition":
            self._handle_python_class(definition, file_info, results, decorators)

    def _handle_python_class(
        self,
        node: TSNode,
        file_info: FileInfo,
        results: list[ASTNode],
        decorators: list[str],
    ) -> None:
        """Extract a class node and recurse into its body for methods."""
        name = self._child_text(node, "identifier")
        if not name:
            return

        docstring = self._extract_python_docstring(node)
        comments = self._collect_nearby_comments(node)

        results.append(
            ASTNode(
                node_id=f"{file_info.path}::{name}",
                type="class",
                name=name,
                file=file_info.path,
                language=file_info.language,
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
    ) -> ASTNode:
        """Build an ASTNode from a Python function_definition."""
        name = self._child_text(node, "identifier")
        params = self._extract_python_params(node)
        return_type = self._extract_python_return_type(node)
        docstring = self._extract_python_docstring(node)
        comments = self._collect_nearby_comments(node)
        node_type = "method" if parent_class else "function"

        return ASTNode(
            node_id=f"{file_info.path}::{name}",
            type=node_type,
            name=name,
            file=file_info.path,
            language=file_info.language,
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

    def _walk_generic(
        self,
        node: TSNode,
        file_info: FileInfo,
        results: list[ASTNode],
        parent_class: str | None,
    ) -> None:
        """Generic fallback for unsupported languages — look for common patterns."""
        if "function_definition" in node.type or "function_declaration" in node.type:
            name = self._child_text(node, "identifier")
            if name:
                results.append(
                    ASTNode(
                        node_id=f"{file_info.path}::{name}",
                        type="method" if parent_class else "function",
                        name=name,
                        file=file_info.path,
                        language=file_info.language,
                    )
                )
            return

        if "class_definition" in node.type or "class_declaration" in node.type:
            name = self._child_text(node, "identifier") or self._child_text(node, "type_identifier")
            if name:
                results.append(
                    ASTNode(
                        node_id=f"{file_info.path}::{name}",
                        type="class",
                        name=name,
                        file=file_info.path,
                        language=file_info.language,
                    )
                )
            return

        for child in node.children:
            self._walk_generic(child, file_info, results, parent_class)

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _child_text(node: TSNode, child_type: str) -> str | None:
        """Get the text of the first child with the given type."""
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
