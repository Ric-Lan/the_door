"""Edge builder module — analyzes call sites, imports, extends, and implements relationships."""
from __future__ import annotations

from tree_sitter import Node as TSNode

from the_door.models import ASTNode, Edge


class EdgeBuilder:
    """Detect relationships between AST nodes: calls, imports, extends."""

    def build_edges(self, nodes: list[ASTNode], trees: dict) -> list[Edge]:
        """Analyze parsed trees to find edges between known nodes.

        Parameters
        ----------
        nodes : list[ASTNode]
            All extracted AST nodes.
        trees : dict[str, tuple[tree, bytes]]
            Mapping of relative file path → (tree-sitter Tree, source bytes).

        Returns
        -------
        list[Edge]
            Edges referencing valid node_ids only.
        """
        # Build lookup structures
        node_id_set = {n.node_id for n in nodes}
        name_to_ids: dict[str, list[str]] = {}
        for n in nodes:
            name_to_ids.setdefault(n.name, []).append(n.node_id)

        # Map node_id → ASTNode for quick access
        node_map = {n.node_id: n for n in nodes}

        edges: list[Edge] = []

        # Detect call edges and extends edges from each file's tree
        for file_path, (tree, source_bytes) in trees.items():
            file_nodes = [n for n in nodes if n.file == file_path]
            self._detect_calls(tree.root_node, file_nodes, name_to_ids, node_id_set, edges)
            self._detect_extends(tree.root_node, file_nodes, name_to_ids, node_id_set, edges)

        # Detect import edges across files
        self._detect_imports(nodes, trees, name_to_ids, node_id_set, edges)

        # Deduplicate
        seen: set[tuple[str, str, str]] = set()
        unique_edges: list[Edge] = []
        for e in edges:
            key = (e.from_node, e.to_node, e.type)
            if key not in seen:
                seen.add(key)
                unique_edges.append(e)

        return unique_edges

    def _detect_calls(
        self,
        root: TSNode,
        file_nodes: list[ASTNode],
        name_to_ids: dict[str, list[str]],
        node_id_set: set[str],
        edges: list[Edge],
    ) -> None:
        """Detect function call relationships within a file."""
        for node in file_nodes:
            if node.type == "class":
                continue
            # Find the function body in the tree and scan for call expressions
            func_ts_node = self._find_definition_node(root, node)
            if func_ts_node is None:
                continue
            body = self._find_child(func_ts_node, "block") or self._find_child(func_ts_node, "statement_block")
            if body is None:
                continue
            called_names = self._collect_call_names(body)
            for called_name in called_names:
                if called_name in name_to_ids:
                    for target_id in name_to_ids[called_name]:
                        if target_id != node.node_id and target_id in node_id_set:
                            edges.append(Edge(from_node=node.node_id, to_node=target_id, type="calls"))

    def _detect_extends(
        self,
        root: TSNode,
        file_nodes: list[ASTNode],
        name_to_ids: dict[str, list[str]],
        node_id_set: set[str],
        edges: list[Edge],
    ) -> None:
        """Detect class inheritance (extends) relationships."""
        for node in file_nodes:
            if node.type != "class":
                continue
            class_ts_node = self._find_definition_node(root, node)
            if class_ts_node is None:
                continue
            base_names = self._extract_base_classes(class_ts_node)
            for base_name in base_names:
                if base_name in name_to_ids:
                    for target_id in name_to_ids[base_name]:
                        if target_id != node.node_id and target_id in node_id_set:
                            edges.append(Edge(from_node=node.node_id, to_node=target_id, type="extends"))

    def _detect_imports(
        self,
        nodes: list[ASTNode],
        trees: dict,
        name_to_ids: dict[str, list[str]],
        node_id_set: set[str],
        edges: list[Edge],
    ) -> None:
        """Detect import relationships between files."""
        for file_path, (tree, source_bytes) in trees.items():
            file_nodes = [n for n in nodes if n.file == file_path]
            if not file_nodes:
                continue

            imported_names = self._collect_import_names(tree.root_node)
            for imp_name in imported_names:
                if imp_name in name_to_ids:
                    for target_id in name_to_ids[imp_name]:
                        # Only create import edge if target is in a different file
                        target_file = target_id.rsplit("::", 1)[0]
                        if target_file != file_path:
                            for src_node in file_nodes:
                                edges.append(Edge(from_node=src_node.node_id, to_node=target_id, type="imports"))
                                break  # One import edge per file is enough

    def _find_definition_node(self, root: TSNode, ast_node: ASTNode) -> TSNode | None:
        """Find the tree-sitter node corresponding to an ASTNode by name matching."""
        return self._search_for_definition(root, ast_node.name, ast_node.type)

    def _search_for_definition(self, ts_node: TSNode, name: str, node_type: str) -> TSNode | None:
        """Recursively search for a function/class/method definition by name."""
        # Check if this node is a definition matching our target
        if self._is_matching_definition(ts_node, name, node_type):
            return ts_node

        # Check decorated definitions
        if ts_node.type == "decorated_definition":
            for child in ts_node.children:
                if self._is_matching_definition(child, name, node_type):
                    return child

        for child in ts_node.children:
            result = self._search_for_definition(child, name, node_type)
            if result is not None:
                return result
        return None

    def _is_matching_definition(self, ts_node: TSNode, name: str, node_type: str) -> bool:
        """Check if a tree-sitter node matches the expected definition."""
        def_types = {
            "function": ("function_definition", "function_declaration"),
            "method": ("function_definition", "method_definition"),
            "class": ("class_definition", "class_declaration"),
        }
        expected_types = def_types.get(node_type, ())
        if ts_node.type not in expected_types:
            return False

        # Check the name child
        for child in ts_node.children:
            if child.type in ("identifier", "type_identifier", "property_identifier"):
                if child.text.decode("utf-8", errors="replace") == name:
                    return True
        return False

    def _collect_call_names(self, node: TSNode) -> set[str]:
        """Recursively collect all function/method call names in a subtree."""
        names: set[str] = set()
        if node.type == "call":
            func_node = node.children[0] if node.children else None
            if func_node:
                if func_node.type == "identifier":
                    names.add(func_node.text.decode("utf-8", errors="replace"))
                elif func_node.type == "attribute":
                    # e.g., obj.method() — extract the method name
                    for child in func_node.children:
                        if child.type == "identifier":
                            last_id = child.text.decode("utf-8", errors="replace")
                    if last_id:
                        names.add(last_id)

        for child in node.children:
            names.update(self._collect_call_names(child))
        return names

    def _extract_base_classes(self, class_node: TSNode) -> list[str]:
        """Extract base class names from a class definition."""
        bases: list[str] = []
        # Python: argument_list after class name
        for child in class_node.children:
            if child.type == "argument_list":
                for arg in child.children:
                    if arg.type == "identifier":
                        bases.append(arg.text.decode("utf-8", errors="replace"))
            # TypeScript: class_heritage
            if child.type == "class_heritage":
                for sub in child.children:
                    if sub.type == "identifier" or sub.type == "type_identifier":
                        bases.append(sub.text.decode("utf-8", errors="replace"))
        return bases

    def _collect_import_names(self, root: TSNode) -> set[str]:
        """Collect imported names from import statements."""
        names: set[str] = set()
        self._walk_imports(root, names)
        return names

    def _walk_imports(self, node: TSNode, names: set[str]) -> None:
        """Recursively find import statements and extract imported names."""
        if node.type in ("import_from_statement", "import_statement"):
            for child in node.children:
                if child.type == "dotted_name":
                    # import foo.bar → extract "bar"
                    parts = child.text.decode("utf-8", errors="replace").split(".")
                    names.add(parts[-1])
                elif child.type == "aliased_import":
                    # from x import y as z → extract "y"
                    for sub in child.children:
                        if sub.type == "dotted_name" or sub.type == "identifier":
                            names.add(sub.text.decode("utf-8", errors="replace"))
                            break
                elif child.type == "identifier" and child.prev_sibling and child.prev_sibling.type == "import":
                    names.add(child.text.decode("utf-8", errors="replace"))

        # TypeScript import
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "import_clause":
                    self._extract_ts_import_names(child, names)

        for child in node.children:
            self._walk_imports(child, names)

    def _extract_ts_import_names(self, node: TSNode, names: set[str]) -> None:
        """Extract imported names from TypeScript import clauses."""
        if node.type == "identifier":
            names.add(node.text.decode("utf-8", errors="replace"))
        if node.type == "import_specifier":
            for child in node.children:
                if child.type == "identifier":
                    names.add(child.text.decode("utf-8", errors="replace"))
                    break
        for child in node.children:
            self._extract_ts_import_names(child, names)

    @staticmethod
    def _find_child(node: TSNode, child_type: str) -> TSNode | None:
        """Find the first child node with the given type."""
        for child in node.children:
            if child.type == child_type:
                return child
        return None
