"""Property-based tests for AST extraction.

Tests are written BEFORE implementation (TDD red phase).
Uses Hypothesis to verify universal correctness properties.
"""
import json
import shutil
from pathlib import Path

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.models import ExtractionResult, ASTNode


def _clean_dir(path: Path) -> None:
    """Remove all contents of a directory (for Hypothesis tmp_path reuse)."""
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


# === Strategies ===

VALID_PYTHON_FUNCTION = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
    min_size=1, max_size=20
).filter(lambda s: s[0].isalpha() or s[0] == "_")


def make_python_file(functions: list[str], with_docstring: bool = True) -> str:
    """Generate a valid Python file with given function names."""
    lines = []
    for fn in functions:
        if with_docstring:
            lines.append(f'def {fn}():\n    """Docstring for {fn}."""\n    pass\n\n')
        else:
            lines.append(f'def {fn}():\n    pass\n\n')
    return "".join(lines)


# === Property 1: Extracted nodes contain all required attributes ===

class TestProperty1ExtractedNodesAttributes:
    """Feature: the-door-phase-1-min, Property 1: Extracted nodes contain all required attributes"""

    @settings(max_examples=100)
    @given(fn_names=st.lists(VALID_PYTHON_FUNCTION, min_size=1, max_size=5, unique=True))
    def test_all_nodes_have_required_attributes(self, fn_names, tmp_path):
        """For any parseable source file, every extracted node has all required attributes.

        **Validates: Requirements 1.2, 1.7**
        """
        # Arrange
        _clean_dir(tmp_path)
        source = make_python_file(fn_names)
        (tmp_path / "test_file.py").write_text(source, encoding="utf-8")

        # Act
        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))

        # Assert
        required_attrs = {"node_id", "type", "name", "file", "language",
                         "decorators", "parameters", "return_type", "docstring", "comments"}
        for node in result.nodes:
            node_attrs = set(vars(node).keys())
            assert required_attrs.issubset(node_attrs), (
                f"Node {node.name} missing attributes: {required_attrs - node_attrs}"
            )
            assert node.node_id is not None
            assert node.type in ("function", "class", "method")
            assert node.name is not None
            assert node.language == "python"


# === Property 2: Extraction resilience — unparseable files do not halt processing ===

class TestProperty2ExtractionResilience:
    """Feature: the-door-phase-1-min, Property 2: Extraction resilience — unparseable files do not halt processing"""

    @settings(max_examples=50)
    @given(
        valid_count=st.integers(min_value=1, max_value=3),
        invalid_count=st.integers(min_value=1, max_value=3)
    )
    def test_unparseable_files_recorded_not_halting(self, valid_count, invalid_count, tmp_path):
        """For any mix of valid and invalid files, valid files are extracted and invalid ones are recorded.

        **Validates: Requirements 1.5**
        """
        # Arrange
        _clean_dir(tmp_path)
        for i in range(valid_count):
            (tmp_path / f"valid_{i}.py").write_text(f'def func_{i}():\n    pass\n')
        for i in range(invalid_count):
            (tmp_path / f"invalid_{i}.py").write_bytes(b'\x00\x01\x02\x03\xff\xfe')

        # Act
        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))

        # Assert
        assert len(result.nodes) >= valid_count, "Valid files should produce nodes"
        assert len(result.errors) == invalid_count, (
            f"Expected {invalid_count} errors, got {len(result.errors)}"
        )


# === Property 3: Docstring and comment preservation round-trip ===

class TestProperty3DocstringPreservation:
    """Feature: the-door-phase-1-min, Property 3: Docstring and comment preservation round-trip"""

    @settings(max_examples=100)
    @given(docstring_text=st.text(min_size=1, max_size=200).filter(lambda s: '"""' not in s and "'''" not in s))
    def test_docstrings_preserved_verbatim(self, docstring_text, tmp_path):
        """For any source file with docstrings, extracted docstrings match source exactly.

        **Validates: Requirements 1.6**
        """
        # Arrange
        _clean_dir(tmp_path)
        source = f'def my_func():\n    """{docstring_text}"""\n    pass\n'
        (tmp_path / "test_file.py").write_text(source, encoding="utf-8")

        # Act
        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))

        # Assert
        assert len(result.nodes) >= 1
        func_node = next((n for n in result.nodes if n.name == "my_func"), None)
        assert func_node is not None
        assert func_node.docstring == docstring_text


# === Property 4: Extraction output structural integrity ===

class TestProperty4StructuralIntegrity:
    """Feature: the-door-phase-1-min, Property 4: Extraction output structural integrity"""

    @settings(max_examples=50)
    @given(fn_names=st.lists(VALID_PYTHON_FUNCTION, min_size=2, max_size=5, unique=True))
    def test_node_ids_unique_and_edges_valid(self, fn_names, tmp_path):
        """For any valid codebase, node_ids are unique and edges reference existing nodes.

        **Validates: Requirements 17.1, 17.2, 17.3**
        """
        # Arrange — create file with functions that call each other
        _clean_dir(tmp_path)
        lines = []
        for i, fn in enumerate(fn_names):
            if i > 0:
                lines.append(f'def {fn}():\n    {fn_names[0]}()\n\n')
            else:
                lines.append(f'def {fn}():\n    pass\n\n')
        (tmp_path / "test_file.py").write_text("".join(lines), encoding="utf-8")

        # Act
        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))

        # Assert — unique node_ids
        node_ids = [n.node_id for n in result.nodes]
        assert len(node_ids) == len(set(node_ids)), "node_ids must be unique"

        # Assert — edges reference existing node_ids
        node_id_set = set(node_ids)
        for edge in result.edges:
            assert edge.from_node in node_id_set, f"Edge from {edge.from_node} references non-existent node"
            assert edge.to_node in node_id_set, f"Edge to {edge.to_node} references non-existent node"
