"""Edge builder module — scope-aware call/import/extends relationship detection."""
from __future__ import annotations

from tree_sitter import Node as TSNode

from the_door.core.extraction.language_configs import (
    LANGUAGE_CONFIGS,
    LanguageConfig,
    ScopeContext,
    ScopeRules,
)
from the_door.models import ASTNode, Edge


class EdgeBuilder:
    """Detect relationships between AST nodes with scope-aware resolution.

    Resolution provenance per edge:
      scope_rule      — resolved via same-file or same-package scope
      import_alias    — resolved via import alias table
      name_match      — fallback bare-name match (low confidence)
      skipped_dynamic — dynamic dispatch context, edge kept but untrusted
    """

    def __init__(self) -> None:
        # Instance state populated per build_edges() call so resolve helpers
        # never AttributeError if called before/between builds.
        self._name_to_ids: dict[str, list[str]] = {}
        self._node_map: dict[str, ASTNode] = {}

    def build_edges(
        self,
        nodes: list[ASTNode],
        trees: dict,
        configs: dict[str, LanguageConfig] | None = None,
    ) -> list[Edge]:
        """Analyze parsed trees to find edges between known nodes.

        Parameters
        ----------
        nodes : list[ASTNode]
            All extracted AST nodes.
        trees : dict[str, tuple[tree, bytes]]
            Mapping of relative file path → (tree-sitter Tree, source bytes).
        configs : dict[str, LanguageConfig] | None
            Per-language config dict (e.g. LANGUAGE_CONFIGS). If None, falls
            back to the global LANGUAGE_CONFIGS.
        """
        lang_configs = configs if configs is not None else LANGUAGE_CONFIGS

        # Build lookup structures (instance state for this call)
        self._name_to_ids = {}
        for n in nodes:
            self._name_to_ids.setdefault(n.name, []).append(n.node_id)
        self._node_map = {n.node_id: n for n in nodes}

        node_id_set = set(self._node_map)
        edges: list[Edge] = []

        for file_path, (tree, source_bytes) in trees.items():
            file_nodes = [n for n in nodes if n.file == file_path]
            if not file_nodes:
                continue

            # Determine language config and scope rules for this file
            lang = file_nodes[0].language
            lang_config = lang_configs.get(lang)
            rules = lang_config.scope_rules if lang_config else None

            # Build per-file ScopeContext (import alias table)
            if rules is not None:
                import_aliases = self._parse_import_aliases(tree.root_node, source_bytes, rules)
            else:
                import_aliases = {}
            base_ctx = ScopeContext(
                current_file=file_path,
                import_aliases=import_aliases,
                caller_class=None,
            )

            self._detect_calls(tree.root_node, file_nodes, node_id_set, edges, base_ctx, rules)
            self._detect_extends(tree.root_node, file_nodes, node_id_set, edges, base_ctx, rules)

        self._detect_imports(nodes, trees, node_id_set, edges, lang_configs)

        # Deduplicate (key: from, to, type — resolution is not part of dedup key
        # so that scope_rule edges are preferred over name_match duplicates)
        seen: set[tuple[str, str, str]] = set()
        unique_edges: list[Edge] = []
        for e in edges:
            key = (e.from_node, e.to_node, e.type)
            if key not in seen:
                seen.add(key)
                unique_edges.append(e)

        # Clear instance state
        self._name_to_ids = {}
        self._node_map = {}

        return unique_edges

    # ── import alias parsing ────────────────────────────────────────────────

    def _parse_import_aliases(
        self, root: TSNode, source_bytes: bytes, rules: ScopeRules
    ) -> dict[str, str]:
        """Parse import statements from a file's AST into alias → original name.

        Dispatches on rules.import_resolution. Unknown strategies return {}.
        """
        strategy = rules.import_resolution
        if strategy == "qualified":
            return self._parse_qualified_imports(root, source_bytes)
        if strategy == "es_module":
            return self._parse_es_module_imports(root, source_bytes)
        if strategy == "namespaced":
            return self._parse_namespaced_imports(root, source_bytes)
        if strategy == "module_path":
            return self._parse_module_path_imports(root, source_bytes)
        return {}

    def _parse_qualified_imports(self, root: TSNode, source_bytes: bytes) -> dict[str, str]:
        """Python-style: from module import name [as alias] → {alias: name}."""
        aliases: dict[str, str] = {}
        self._walk_qualified_imports(root, source_bytes, aliases)
        return aliases

    def _walk_qualified_imports(
        self, node: TSNode, source_bytes: bytes, aliases: dict[str, str]
    ) -> None:
        """Walk a Python AST collecting `from X import [name as alias]` aliases.

        tree-sitter-python grammar puts `import_from_statement` children in this
        order: `from` keyword → dotted_name(module) → `import` keyword → one or
        more {dotted_name | aliased_import | identifier} representing the imported
        names. We track "seen import keyword" so the *module path* dotted_name
        is not confused with imported-name dotted_names.
        """
        if node.type == "import_from_statement":
            seen_import_kw = False
            for child in node.children:
                if child.type == "import":
                    seen_import_kw = True
                    continue
                if not seen_import_kw:
                    continue  # skip the module-path dotted_name before `import`
                if child.type == "aliased_import":
                    orig_name = None
                    alias_name = None
                    for sub in child.children:
                        if sub.type == "dotted_name" and orig_name is None:
                            orig_name = sub.text.decode("utf-8", errors="replace").split(".")[-1]
                        elif sub.type == "identifier":
                            if orig_name is None:
                                orig_name = sub.text.decode("utf-8", errors="replace")
                            else:
                                alias_name = sub.text.decode("utf-8", errors="replace")
                    if orig_name and alias_name:
                        aliases[alias_name] = orig_name
                elif child.type == "dotted_name":
                    name = child.text.decode("utf-8", errors="replace").split(".")[-1]
                    if name.isidentifier():
                        aliases[name] = name
                elif child.type == "identifier":
                    name = child.text.decode("utf-8", errors="replace")
                    if name.isidentifier():
                        aliases[name] = name
            # Fully handled this import_from_statement — do not recurse into its
            # children (would re-walk aliased_import / dotted_name with no effect
            # and waste cycles on large files with many imports).
            return
        # Recurse only for non-import nodes (find nested imports).
        for child in node.children:
            self._walk_qualified_imports(child, source_bytes, aliases)

    def _parse_es_module_imports(self, root: TSNode, source_bytes: bytes) -> dict[str, str]:
        """TypeScript/JS ES6: import { name as alias } from '...' → {alias: name}."""
        aliases: dict[str, str] = {}
        self._walk_es_module_imports(root, source_bytes, aliases)
        return aliases

    def _walk_es_module_imports(
        self, node: TSNode, source_bytes: bytes, aliases: dict[str, str]
    ) -> None:
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "import_clause":
                    self._extract_es_import_clause(child, aliases)
        for child in node.children:
            self._walk_es_module_imports(child, source_bytes, aliases)

    def _extract_es_import_clause(self, clause: TSNode, aliases: dict[str, str]) -> None:
        for child in clause.children:
            if child.type == "identifier":
                # Default import: import Foo from '...'
                name = child.text.decode("utf-8", errors="replace")
                aliases[name] = name
            elif child.type == "named_imports":
                for spec in child.children:
                    if spec.type == "import_specifier":
                        self._extract_es_import_specifier(spec, aliases)

    def _extract_es_import_specifier(self, spec: TSNode, aliases: dict[str, str]) -> None:
        identifiers = [
            c.text.decode("utf-8", errors="replace")
            for c in spec.children
            if c.type == "identifier"
        ]
        if len(identifiers) == 1:
            # import { name } — no alias
            aliases[identifiers[0]] = identifiers[0]
        elif len(identifiers) >= 2:
            # import { name as alias } — first is original, last is alias
            aliases[identifiers[-1]] = identifiers[0]

    def _parse_namespaced_imports(self, root: TSNode, source_bytes: bytes) -> dict[str, str]:
        """Java/PHP/C# namespaced imports → {alias: simple_name}.

        Java: import com.example.Foo → {"Foo": "Foo"}
        PHP/C#: filled in Task 05
        """
        aliases: dict[str, str] = {}
        self._walk_namespaced_imports(root, source_bytes, aliases)
        return aliases

    def _walk_namespaced_imports(
        self, node: TSNode, source_bytes: bytes, aliases: dict[str, str]
    ) -> None:
        # Java: import_declaration → last segment
        if node.type == "import_declaration":
            last_name = self._extract_last_qualified_name(node)
            if last_name:
                aliases[last_name] = last_name

        # PHP: namespace_use_declaration → namespace_use_clause (per clause)
        if node.type == "namespace_use_clause":
            self._extract_php_use_clause(node, aliases)

        # C#: using_directive
        if node.type == "using_directive":
            self._extract_csharp_using(node, aliases)

        for child in node.children:
            self._walk_namespaced_imports(child, source_bytes, aliases)

    def _extract_php_use_clause(self, clause: TSNode, aliases: dict[str, str]) -> None:
        r"""Extract PHP `use Foo\Bar [as B];` → {B (or Bar): Bar}."""
        orig = None
        alias = None
        for child in clause.children:
            if child.type in ("qualified_name", "name"):
                text = child.text.decode("utf-8", errors="replace")
                last_seg = text.replace("\\", ".").rstrip(".").split(".")[-1].strip()
                if orig is None:
                    orig = last_seg
                else:
                    alias = last_seg
        if orig:
            aliases[alias if alias else orig] = orig

    def _extract_csharp_using(self, node: TSNode, aliases: dict[str, str]) -> None:
        """Extract C# `using [Alias =] System.Linq;` → {Alias (or Linq): Linq}."""
        # Collect named children (skip punctuation/keywords)
        named = [c for c in node.children if c.type not in ("using", ";", "=")]
        # Check for alias pattern: identifier "=" qualified_name
        # In tree: 'using' identifier '=' qualified_name ';'
        # named will be [identifier, qualified_name] when alias present
        alias = None
        orig = None
        if len(named) == 2 and named[0].type == "identifier" and named[1].type in ("qualified_name", "identifier"):
            alias = named[0].text.decode("utf-8", errors="replace")
            text = named[1].text.decode("utf-8", errors="replace")
            orig = text.split(".")[-1].strip()
        elif len(named) == 1 and named[0].type in ("qualified_name", "identifier"):
            text = named[0].text.decode("utf-8", errors="replace")
            orig = text.split(".")[-1].strip()
        if orig:
            aliases[alias if alias else orig] = orig

    def _extract_last_qualified_name(self, node: TSNode) -> str | None:
        """Return the last identifier from a dotted/scoped name (e.g. com.example.Foo → Foo)."""
        text = node.text.decode("utf-8", errors="replace") if node.text else ""
        # Strip 'import' / 'static' keywords and semicolons
        parts = text.replace(";", "").strip().split()
        for part in reversed(parts):
            if part not in ("import", "static", "use", "using"):
                segments = part.replace("::", ".").split(".")
                last = segments[-1].strip()
                if last and last.isidentifier():
                    return last
        return None

    def _parse_module_path_imports(self, root: TSNode, source_bytes: bytes) -> dict[str, str]:
        """Go (import "path") and Rust (use path::name [as alias]) → {alias: name}."""
        aliases: dict[str, str] = {}
        self._walk_module_path_imports(root, source_bytes, aliases)
        return aliases

    def _walk_module_path_imports(
        self, node: TSNode, source_bytes: bytes, aliases: dict[str, str]
    ) -> None:
        # Go: import_spec (under import_declaration / import_spec_list)
        if node.type == "import_spec":
            self._extract_go_import_spec(node, aliases)
        # Rust: use_declaration → may contain scoped_identifier / use_as_clause / scoped_use_list
        if node.type == "use_declaration":
            for child in node.children:
                self._extract_rust_use_item(child, aliases)
        for child in node.children:
            self._walk_module_path_imports(child, source_bytes, aliases)

    def _extract_go_import_spec(self, spec: TSNode, aliases: dict[str, str]) -> None:
        alias = None
        path = None
        for child in spec.children:
            if child.type == "package_identifier":
                alias = child.text.decode("utf-8", errors="replace")
            elif child.type in ("interpreted_string_literal", "raw_string_literal"):
                raw = child.text.decode("utf-8", errors="replace").strip().strip('"').strip("`")
                path = raw
        if path:
            last_segment = path.rstrip("/").split("/")[-1]
            if alias:
                aliases[alias] = last_segment
            elif last_segment.isidentifier():
                aliases[last_segment] = last_segment

    def _extract_rust_use_item(self, node: TSNode, aliases: dict[str, str]) -> None:
        if node.type == "scoped_identifier":
            text = node.text.decode("utf-8", errors="replace")
            last = text.split("::")[-1].strip()
            if last.isidentifier():
                aliases[last] = last
        elif node.type == "use_as_clause":
            orig = None
            alias = None
            for child in node.children:
                if child.type == "scoped_identifier":
                    orig = child.text.decode("utf-8", errors="replace").split("::")[-1].strip()
                elif child.type == "identifier" and orig is not None:
                    alias = child.text.decode("utf-8", errors="replace")
            if orig and alias:
                aliases[alias] = orig
        elif node.type == "scoped_use_list":
            for child in node.children:
                if child.type == "use_list":
                    for item in child.children:
                        if item.type == "identifier":
                            name = item.text.decode("utf-8", errors="replace")
                            aliases[name] = name
                        elif item.type == "use_as_clause":
                            self._extract_rust_use_item(item, aliases)
        elif node.type == "identifier":
            # bare `use foo;` (rare)
            name = node.text.decode("utf-8", errors="replace")
            if name.isidentifier():
                aliases[name] = name

    # ── resolution logic ───────────────────────────────────────────────────

    def _resolve(
        self, name: str, context: ScopeContext, rules: ScopeRules | None
    ) -> list[tuple[str, str]]:
        """Resolve a called name to (node_id, resolution) pairs.

        Empty list means no edge is produced.
        Multiple results only occur in the name_match / skipped_dynamic fallback path.
        """
        if rules is None:
            # No scope rules configured → pure name_match fallback
            matches = self._name_to_ids.get(name, [])
            return [(m, "name_match") for m in matches]

        # Step 1: Dynamic dispatch check
        is_dynamic = (
            context.has_dynamic_marker(rules.dynamic_markers)
            or rules.method_resolution == "dynamic_dispatch"
        )
        if is_dynamic:
            matches = self._name_to_ids.get(name, [])
            return [(m, "skipped_dynamic") for m in matches]

        # Step 2: Scope rule (file-local / package-local)
        scoped = self._resolve_by_scope(name, context, rules)
        if scoped:
            return [(scoped, "scope_rule")]

        # Step 3: Import alias
        aliased = self._resolve_by_import_alias(name, context, rules)
        if aliased:
            return [(aliased, "import_alias")]

        # Step 4: Fallback — name_match (keep all candidates, low confidence)
        matches = self._name_to_ids.get(name, [])
        return [(m, "name_match") for m in matches]

    def _resolve_by_scope(
        self, name: str, context: ScopeContext, rules: ScopeRules
    ) -> str | None:
        """Return a single node_id if the name can be scope-resolved, else None."""
        candidates = self._name_to_ids.get(name, [])
        if not candidates:
            return None

        strategy = rules.function_resolution
        if strategy == "file_local_then_imports":
            same_file = [
                c for c in candidates
                if c in self._node_map and self._node_map[c].file == context.current_file
            ]
            if same_file:
                return same_file[0]

        elif strategy == "package_local_then_imports":
            current_pkg = context.current_file.rsplit("/", 1)[0] if "/" in context.current_file else ""
            same_pkg = [
                c for c in candidates
                if c in self._node_map
                and (
                    self._node_map[c].file.rsplit("/", 1)[0] == current_pkg
                    if "/" in self._node_map[c].file
                    else current_pkg == ""
                )
            ]
            if same_pkg:
                return same_pkg[0]

        return None

    def _resolve_by_import_alias(
        self, name: str, context: ScopeContext, rules: ScopeRules
    ) -> str | None:
        """Return a node_id if name is a known import alias, else None."""
        original_name = context.import_aliases.get(name)
        if original_name is None:
            return None
        candidates = self._name_to_ids.get(original_name, [])
        if not candidates:
            return None
        return candidates[0]

    # ── detection methods ──────────────────────────────────────────────────

    def _detect_calls(
        self,
        root: TSNode,
        file_nodes: list[ASTNode],
        node_id_set: set[str],
        edges: list[Edge],
        base_ctx: ScopeContext,
        rules: ScopeRules | None,
    ) -> None:
        for node in file_nodes:
            if node.type == "class":
                continue
            func_ts_node = self._find_definition_node(root, node)
            if func_ts_node is None:
                continue
            body = self._find_child(func_ts_node, "block") or self._find_child(
                func_ts_node, "statement_block"
            )
            if body is None:
                continue
            # Clone context with caller info for this specific node.
            # Derive caller_class from node_id format "ClassName.method_name" if
            # the node is a method; bare functions have no dot and caller_class=None.
            if node.type == "method" and "." in node.node_id.rsplit("/", 1)[-1]:
                # node_id last segment looks like "Class.method" → use "Class"
                last_seg = node.node_id.rsplit("/", 1)[-1]
                derived_class = last_seg.rsplit(".", 1)[0]
            else:
                derived_class = None
            call_ctx = ScopeContext(
                current_file=base_ctx.current_file,
                import_aliases=base_ctx.import_aliases,
                caller_class=derived_class,
                caller_name=node.name,
            )
            called_names = self._collect_call_names(body)
            for called_name in called_names:
                if rules is not None:
                    resolved = self._resolve(called_name, call_ctx, rules)
                else:
                    candidates = self._name_to_ids.get(called_name, [])
                    resolved = [(c, "name_match") for c in candidates]
                for target_id, res_type in resolved:
                    if target_id != node.node_id and target_id in node_id_set:
                        edges.append(
                            Edge(
                                from_node=node.node_id,
                                to_node=target_id,
                                type="calls",
                                resolution=res_type,
                            )
                        )

    def _detect_extends(
        self,
        root: TSNode,
        file_nodes: list[ASTNode],
        node_id_set: set[str],
        edges: list[Edge],
        base_ctx: ScopeContext,
        rules: ScopeRules | None,
    ) -> None:
        for node in file_nodes:
            if node.type != "class":
                continue
            class_ts_node = self._find_definition_node(root, node)
            if class_ts_node is None:
                continue
            base_names = self._extract_base_classes(class_ts_node)
            for base_name in base_names:
                if rules is not None:
                    ext_ctx = ScopeContext(
                        current_file=base_ctx.current_file,
                        import_aliases=base_ctx.import_aliases,
                        caller_class=node.name,
                        caller_name=node.name,
                    )
                    resolved = self._resolve(base_name, ext_ctx, rules)
                else:
                    candidates = self._name_to_ids.get(base_name, [])
                    resolved = [(c, "name_match") for c in candidates]
                for target_id, res_type in resolved:
                    if target_id != node.node_id and target_id in node_id_set:
                        edges.append(
                            Edge(
                                from_node=node.node_id,
                                to_node=target_id,
                                type="extends",
                                resolution=res_type,
                            )
                        )

    def _detect_imports(
        self,
        nodes: list[ASTNode],
        trees: dict,
        node_id_set: set[str],
        edges: list[Edge],
        lang_configs: dict[str, LanguageConfig],
    ) -> None:
        for file_path, (tree, source_bytes) in trees.items():
            file_nodes = [n for n in nodes if n.file == file_path]
            if not file_nodes:
                continue
            imported_names = self._collect_import_names(tree.root_node)
            for imp_name in imported_names:
                if imp_name in self._name_to_ids:
                    for target_id in self._name_to_ids[imp_name]:
                        target_file = self._node_map[target_id].file if target_id in self._node_map else ""
                        if target_file != file_path:
                            for src_node in file_nodes:
                                edges.append(
                                    Edge(
                                        from_node=src_node.node_id,
                                        to_node=target_id,
                                        type="imports",
                                        resolution="name_match",
                                    )
                                )
                                break

    # ── tree-sitter helpers (unchanged from original) ───────────────────────

    def _find_definition_node(self, root: TSNode, ast_node: ASTNode) -> TSNode | None:
        return self._search_for_definition(root, ast_node.name, ast_node.type)

    def _search_for_definition(self, ts_node: TSNode, name: str, node_type: str) -> TSNode | None:
        if self._is_matching_definition(ts_node, name, node_type):
            return ts_node
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
        def_types = {
            "function": ("function_definition", "function_declaration"),
            "method": ("function_definition", "method_definition"),
            "class": ("class_definition", "class_declaration"),
        }
        expected_types = def_types.get(node_type, ())
        if ts_node.type not in expected_types:
            return False
        for child in ts_node.children:
            if child.type in ("identifier", "type_identifier", "property_identifier"):
                if child.text.decode("utf-8", errors="replace") == name:
                    return True
        return False

    def _collect_call_names(self, node: TSNode) -> set[str]:
        names: set[str] = set()
        # Python: call node; TypeScript/JS: call_expression node
        if node.type in ("call", "call_expression"):
            func_node = node.children[0] if node.children else None
            if func_node:
                if func_node.type == "identifier":
                    names.add(func_node.text.decode("utf-8", errors="replace"))
                elif func_node.type in ("attribute", "member_expression"):
                    last_id = ""
                    for child in func_node.children:
                        if child.type in ("identifier", "property_identifier"):
                            last_id = child.text.decode("utf-8", errors="replace")
                    if last_id:
                        names.add(last_id)
        for child in node.children:
            names.update(self._collect_call_names(child))
        return names

    def _extract_base_classes(self, class_node: TSNode) -> list[str]:
        bases: list[str] = []
        for child in class_node.children:
            if child.type == "argument_list":
                for arg in child.children:
                    if arg.type == "identifier":
                        bases.append(arg.text.decode("utf-8", errors="replace"))
            if child.type == "class_heritage":
                for sub in child.children:
                    if sub.type in ("identifier", "type_identifier"):
                        bases.append(sub.text.decode("utf-8", errors="replace"))
        return bases

    def _collect_import_names(self, root: TSNode) -> set[str]:
        names: set[str] = set()
        self._walk_imports(root, names)
        return names

    def _walk_imports(self, node: TSNode, names: set[str]) -> None:
        if node.type in ("import_from_statement", "import_statement"):
            for child in node.children:
                if child.type == "dotted_name":
                    parts = child.text.decode("utf-8", errors="replace").split(".")
                    names.add(parts[-1])
                elif child.type == "aliased_import":
                    for sub in child.children:
                        if sub.type in ("dotted_name", "identifier"):
                            names.add(sub.text.decode("utf-8", errors="replace").split(".")[-1])
                            break
                elif child.type == "identifier" and child.prev_sibling and child.prev_sibling.type == "import":
                    names.add(child.text.decode("utf-8", errors="replace"))
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "import_clause":
                    self._extract_ts_import_names(child, names)
        for child in node.children:
            self._walk_imports(child, names)

    def _extract_ts_import_names(self, node: TSNode, names: set[str]) -> None:
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
        for child in node.children:
            if child.type == child_type:
                return child
        return None
