"""Orchestrator for AST extraction — coordinates file discovery, node building, and edge building."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import tree_sitter

from the_door.core.extraction.file_discovery import FileDiscovery
from the_door.core.extraction.node_builder import NodeBuilder
from the_door.core.extraction.edge_builder import EdgeBuilder
from the_door.core.extraction.language_configs import LANGUAGE_CONFIGS
from the_door.models import ExtractionError, ExtractionResult

# Language name → tree-sitter language loader
_LANGUAGE_LOADERS: dict[str, callable] = {}


def _init_language_loaders() -> None:
    """Lazily populate the language loader map."""
    if _LANGUAGE_LOADERS:
        return

    try:
        import tree_sitter_python
        _LANGUAGE_LOADERS["python"] = tree_sitter_python.language
    except ImportError:
        pass

    try:
        import tree_sitter_typescript
        _LANGUAGE_LOADERS["typescript"] = tree_sitter_typescript.language_typescript
    except ImportError:
        pass

    try:
        import tree_sitter_javascript
        _LANGUAGE_LOADERS["javascript"] = tree_sitter_javascript.language
    except ImportError:
        pass

    try:
        import tree_sitter_java
        _LANGUAGE_LOADERS["java"] = tree_sitter_java.language
    except ImportError:
        pass

    try:
        import tree_sitter_go
        _LANGUAGE_LOADERS["go"] = tree_sitter_go.language
    except ImportError:
        pass

    try:
        import tree_sitter_rust
        _LANGUAGE_LOADERS["rust"] = tree_sitter_rust.language
    except ImportError:
        pass

    try:
        import tree_sitter_ruby
        _LANGUAGE_LOADERS["ruby"] = tree_sitter_ruby.language
    except ImportError:
        pass

    try:
        import tree_sitter_php
        _LANGUAGE_LOADERS["php"] = tree_sitter_php.language_php
    except ImportError:
        pass

    try:
        import tree_sitter_c_sharp
        _LANGUAGE_LOADERS["csharp"] = tree_sitter_c_sharp.language
    except ImportError:
        pass

    try:
        import tree_sitter_cpp
        _LANGUAGE_LOADERS["cpp"] = tree_sitter_cpp.language
    except ImportError:
        pass

    try:
        import tree_sitter_c
        _LANGUAGE_LOADERS["c"] = tree_sitter_c.language
    except ImportError:
        pass


def _get_parser(language: str) -> tree_sitter.Parser | None:
    """Get a tree-sitter parser for the given language, or None if unavailable."""
    _init_language_loaders()
    loader = _LANGUAGE_LOADERS.get(language)
    if loader is None:
        return None
    lang = tree_sitter.Language(loader())
    return tree_sitter.Parser(lang)


class ASTExtractor:
    """Orchestrate AST extraction: file discovery → node building → edge building."""

    def __init__(self) -> None:
        self._file_discovery = FileDiscovery()
        self._node_builder = NodeBuilder()
        self._edge_builder = EdgeBuilder()
        self._warnings: list[tuple[str, str, str]] = []

    def extract(self, codebase_path: str, extra_ignore: list[str] | None = None) -> ExtractionResult:
        """Extract AST structure from a codebase.

        Parameters
        ----------
        codebase_path : str
            Path to the root of the codebase to analyse.

        Returns
        -------
        ExtractionResult
            Files, nodes, edges, and any extraction errors.

        Raises
        ------
        FileNotFoundError
            If the codebase path does not exist.
        ValueError
            If the codebase path is not a directory.
        """
        root = Path(codebase_path)
        if not root.exists():
            raise FileNotFoundError(f"Codebase path does not exist: {codebase_path}")
        if not root.is_dir():
            raise ValueError(f"Codebase path is not a directory: {codebase_path}")

        result = ExtractionResult()

        # Step 1: Discover files
        files = self._file_discovery.discover(codebase_path, extra_ignore=extra_ignore or [])
        result.files = files

        # Step 2: Parse each file and build nodes
        trees: dict[str, tuple] = {}  # file_path → (tree, source_bytes)

        for file_info in files:
            file_path = root / file_info.path
            parser = _get_parser(file_info.language)
            if parser is None:
                result.errors.append(
                    ExtractionError(
                        file_path=file_info.path,
                        reason=f"Unsupported language: {file_info.language}",
                    )
                )
                continue

            try:
                source_bytes = file_path.read_bytes()
                # Try decoding to verify it's valid text
                source_bytes.decode("utf-8")
                # Normalise line endings for consistent cross-platform parsing
                source_bytes = source_bytes.replace(b"\r\n", b"\n")
            except (OSError, UnicodeDecodeError) as exc:
                result.errors.append(
                    ExtractionError(file_path=file_info.path, reason=str(exc))
                )
                continue

            try:
                tree = parser.parse(source_bytes)
            except Exception as exc:
                result.errors.append(
                    ExtractionError(file_path=file_info.path, reason=str(exc))
                )
                continue

            trees[file_info.path] = (tree, source_bytes)

            try:
                nodes = self._node_builder.build_nodes(tree, file_info)
                result.nodes.extend(nodes)
            except Exception as exc:
                result.errors.append(
                    ExtractionError(file_path=file_info.path, reason=f"Node extraction failed: {exc}")
                )

        # Step 3: Disambiguate colliding node_ids before edge building
        self._warnings = []
        result.nodes = self._disambiguate_node_ids(result.nodes)
        result.warnings = list(self._warnings)

        # Step 4: Build edges
        try:
            edges = self._edge_builder.build_edges(result.nodes, trees, configs=LANGUAGE_CONFIGS)
            result.edges = edges
        except Exception as exc:
            # Edge building failure is non-fatal — record but continue
            result.errors.append(
                ExtractionError(file_path="<edge_builder>", reason=str(exc))
            )

        return result

    def _disambiguate_node_ids(self, nodes: list) -> list:
        groups: dict[str, list] = defaultdict(list)
        for n in nodes:
            groups[n.node_id].append(n)
        result: list = []
        for tentative_id, group in groups.items():
            if len(group) == 1:
                result.append(group[0])
                continue
            group_sorted = sorted(group, key=lambda n: n.file)
            self._warnings.append(
                ("node_id_collision", group_sorted[0].file, f"{len(group)} nodes share node_id={tentative_id!r}; suffix-disambiguated")
            )
            result.append(group_sorted[0])
            for i, n in enumerate(group_sorted[1:], start=2):
                result.append(replace(n, node_id=f"{tentative_id}#{i}"))
        result.sort(key=lambda n: n.file)
        return result
