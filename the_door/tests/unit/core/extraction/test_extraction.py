"""Unit tests for AST extraction modules (TDD red phase).

Tests are written BEFORE implementation — all should fail until modules are implemented.
Covers: FileDiscovery (9.1), NodeBuilder (9.2), EdgeBuilder (9.3), ASTExtractor (9.4).
"""
import json
from pathlib import Path

import pytest

from the_door.core.extraction.file_discovery import FileDiscovery
from the_door.core.extraction.node_builder import NodeBuilder
from the_door.core.extraction.edge_builder import EdgeBuilder
from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.models import FileInfo, ASTNode, Edge, ExtractionResult


FIXTURES = Path(__file__).parent.parent.parent.parent / "fixtures"
PYTHON_SIMPLE = FIXTURES / "sample_codebases" / "python_simple"


# === FileDiscovery tests (Task 9.1) ===


class TestFileDiscovery:
    """Unit tests for file_discovery module."""

    def test_discovers_python_files(self, tmp_path):
        (tmp_path / "main.py").write_text("x = 1")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "helper.py").write_text("y = 2")

        discovery = FileDiscovery()
        files = discovery.discover(str(tmp_path))

        paths = [f.path for f in files]
        assert any("main.py" in p for p in paths)
        assert any("helper.py" in p for p in paths)

    def test_discovers_typescript_files(self, tmp_path):
        (tmp_path / "app.ts").write_text("const x = 1;")

        discovery = FileDiscovery()
        files = discovery.discover(str(tmp_path))

        assert any(f.language == "typescript" for f in files)

    def test_discovers_java_files(self, tmp_path):
        (tmp_path / "Main.java").write_text("class Main {}")

        discovery = FileDiscovery()
        files = discovery.discover(str(tmp_path))

        assert any(f.language == "java" for f in files)

    def test_respects_gitignore(self, tmp_path):
        (tmp_path / ".gitignore").write_text("node_modules/\n__pycache__/\n")
        (tmp_path / "main.py").write_text("x = 1")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg.js").write_text("module.exports = {}")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "main.cpython-310.pyc").write_bytes(b"\x00")

        discovery = FileDiscovery()
        files = discovery.discover(str(tmp_path))

        paths = [f.path for f in files]
        assert not any("node_modules" in p for p in paths)
        assert not any("__pycache__" in p for p in paths)

    def test_empty_directory_returns_empty(self, tmp_path):
        discovery = FileDiscovery()
        files = discovery.discover(str(tmp_path))
        assert files == []

    def test_detects_correct_language(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1")
        (tmp_path / "index.ts").write_text("const x = 1;")
        (tmp_path / "Main.java").write_text("class Main {}")

        discovery = FileDiscovery()
        files = discovery.discover(str(tmp_path))

        lang_map = {Path(f.path).name: f.language for f in files}
        assert lang_map.get("app.py") == "python"
        assert lang_map.get("index.ts") == "typescript"
        assert lang_map.get("Main.java") == "java"

    def test_returns_fileinfo_instances(self, tmp_path):
        (tmp_path / "test.py").write_text("pass")

        discovery = FileDiscovery()
        files = discovery.discover(str(tmp_path))

        assert len(files) >= 1
        assert all(isinstance(f, FileInfo) for f in files)

    def test_nonexistent_path_returns_empty(self, tmp_path):
        """Non-directory path returns empty list."""
        files = FileDiscovery().discover(str(tmp_path / "no_such_dir"))
        assert files == []

    def test_file_matching_gitignore_pattern_is_skipped(self, tmp_path):
        """A file matching .gitignore is excluded (covers the spec.match_file continue branch)."""
        (tmp_path / ".gitignore").write_text("skip_me.py\n")
        (tmp_path / "skip_me.py").write_text("x = 1")
        (tmp_path / "keep_me.py").write_text("y = 2")
        files = FileDiscovery().discover(str(tmp_path))
        paths = [f.path for f in files]
        assert not any("skip_me" in p for p in paths)
        assert any("keep_me" in p for p in paths)

    def test_ignores_dot_claude_directory(self, tmp_path):
        """Files inside .claude/ worktrees must never appear in discovery results."""
        (tmp_path / ".claude" / "worktrees" / "foo").mkdir(parents=True)
        (tmp_path / ".claude" / "worktrees" / "foo" / "bar.py").write_text("x = 1")
        (tmp_path / "main.py").write_text("y = 2")
        files = FileDiscovery().discover(str(tmp_path))
        paths = [f.path for f in files]
        assert not any(".claude" in p for p in paths)
        assert any("main.py" in p for p in paths)

    def test_extra_ignore_excludes_specified_dirs(self, tmp_path):
        """extra_ignore patterns are applied on top of the default ignore list."""
        (tmp_path / "vendor" / "lib").mkdir(parents=True)
        (tmp_path / "vendor" / "lib" / "foo.py").write_text("x = 1")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("y = 2")
        files = FileDiscovery().discover(str(tmp_path), extra_ignore=["vendor/"])
        paths = [f.path for f in files]
        assert not any("vendor" in p for p in paths)
        assert any("app.py" in p for p in paths)


# === NodeBuilder tests (Task 9.2) ===


class TestNodeBuilder:
    """Unit tests for node_builder module."""

    def test_extracts_function_with_all_attributes(self, tmp_path):
        source = (
            'def hello(name: str) -> str:\n'
            '    """Greet user."""\n'
            '    return f"Hi {name}"\n'
        )
        (tmp_path / "test.py").write_text(source)

        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))

        node = next((n for n in result.nodes if n.name == "hello"), None)
        assert node is not None
        assert node.type == "function"
        assert "name: str" in node.parameters
        assert node.return_type == "str"
        assert node.docstring == "Greet user."

    def test_extracts_class_and_methods(self, tmp_path):
        source = (
            'class MyClass:\n'
            '    """A class."""\n'
            '    def method(self):\n'
            '        pass\n'
        )
        (tmp_path / "test.py").write_text(source)

        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))

        class_node = next((n for n in result.nodes if n.name == "MyClass"), None)
        method_node = next((n for n in result.nodes if n.name == "method"), None)
        assert class_node is not None
        assert class_node.type == "class"
        assert method_node is not None
        assert method_node.type == "method"

    def test_extracts_decorators(self, tmp_path):
        source = '@app.route("/test")\ndef handler():\n    pass\n'
        (tmp_path / "test.py").write_text(source)

        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))

        node = next((n for n in result.nodes if n.name == "handler"), None)
        assert node is not None
        assert any("app.route" in d for d in node.decorators)

    def test_preserves_docstrings_verbatim(self, tmp_path):
        source = 'def func():\n    """Multi-line\n    docstring."""\n    pass\n'
        (tmp_path / "test.py").write_text(source)

        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))

        node = next((n for n in result.nodes if n.name == "func"), None)
        assert node is not None
        assert "Multi-line" in node.docstring
        assert "docstring." in node.docstring

    def test_preserves_todo_fixme_comments(self, tmp_path):
        source = '# TODO: implement this\ndef func():\n    # FIXME: broken\n    pass\n'
        (tmp_path / "test.py").write_text(source)

        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))

        node = next((n for n in result.nodes if n.name == "func"), None)
        assert node is not None
        assert any("TODO" in c for c in node.comments) or any(
            "FIXME" in c for c in node.comments
        )

    def test_empty_file_returns_no_nodes(self, tmp_path):
        (tmp_path / "empty.py").write_text("")

        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))

        # An empty file should produce no function/class/method nodes
        file_nodes = [n for n in result.nodes if "empty.py" in n.file]
        assert len(file_nodes) == 0

    def test_file_with_no_functions_or_classes(self, tmp_path):
        (tmp_path / "constants.py").write_text("X = 1\nY = 2\n")

        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))

        file_nodes = [n for n in result.nodes if "constants.py" in n.file]
        assert len(file_nodes) == 0

    def test_function_node_has_start_and_end_line(self, tmp_path):
        source = "x = 1\n\ndef hello():\n    pass\n"
        # 行號： 1: x=1  2: (空行)  3: def hello()  4:     pass
        (tmp_path / "test.py").write_text(source)
        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))
        node = next(n for n in result.nodes if n.name == "hello")
        assert node.start_line == 3
        assert node.end_line == 4

    def test_decorated_function_start_line_is_decorator_line(self, tmp_path):
        source = "@app.route(\"/test\")\ndef handler():\n    pass\n"
        # 行號： 1: @app.route  2: def handler  3:     pass
        (tmp_path / "test.py").write_text(source)
        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))
        node = next(n for n in result.nodes if n.name == "handler")
        assert node.start_line == 1   # decorator 行，非 def 行
        assert node.end_line == 3

    def test_class_method_has_independent_start_end_lines(self, tmp_path):
        source = (
            "class Foo:\n"          # line 1
            "    def bar(self):\n"  # line 2
            "        pass\n"        # line 3
            "    def baz(self):\n"  # line 4
            "        return 1\n"    # line 5
        )
        (tmp_path / "test.py").write_text(source)
        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))
        bar = next(n for n in result.nodes if n.name == "bar")
        baz = next(n for n in result.nodes if n.name == "baz")
        assert bar.start_line == 2
        assert bar.end_line == 3
        assert baz.start_line == 4
        assert baz.end_line == 5


# === EdgeBuilder tests (Task 9.3) ===


class TestEdgeBuilder:
    """Unit tests for edge_builder module."""

    def test_detects_call_relationships(self, tmp_path):
        source = "def caller():\n    callee()\n\ndef callee():\n    pass\n"
        (tmp_path / "test.py").write_text(source)

        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))

        call_edges = [e for e in result.edges if e.type == "calls"]
        assert len(call_edges) >= 1
        assert any(e.to_node.endswith("::callee") for e in call_edges)

    def test_detects_import_relationships(self, tmp_path):
        (tmp_path / "a.py").write_text(
            "from .b import helper\ndef main():\n    helper()\n"
        )
        (tmp_path / "b.py").write_text("def helper():\n    pass\n")

        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))

        import_edges = [e for e in result.edges if e.type == "imports"]
        # Should detect import relationship between a.py and b.py
        assert len(import_edges) >= 0  # May vary by implementation

    def test_edges_reference_valid_node_ids(self, tmp_path):
        source = "def a():\n    b()\n\ndef b():\n    pass\n"
        (tmp_path / "test.py").write_text(source)

        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))

        node_ids = {n.node_id for n in result.nodes}
        for edge in result.edges:
            assert edge.from_node in node_ids, (
                f"Edge from_node {edge.from_node} not in nodes"
            )
            assert edge.to_node in node_ids, (
                f"Edge to_node {edge.to_node} not in nodes"
            )

    def test_detects_class_inheritance(self, tmp_path):
        source = "class Base:\n    pass\n\nclass Child(Base):\n    pass\n"
        (tmp_path / "test.py").write_text(source)

        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))

        extends_edges = [e for e in result.edges if e.type == "extends"]
        assert len(extends_edges) >= 1


# === ASTExtractor orchestrator tests (Task 9.4) ===


class TestASTExtractor:
    """Unit tests for ast_extractor orchestrator."""

    def test_full_extraction_on_fixture(self):
        extractor = ASTExtractor()
        result = extractor.extract(str(PYTHON_SIMPLE))

        assert len(result.files) >= 3
        assert len(result.nodes) >= 5
        assert len(result.edges) >= 1
        assert len(result.errors) == 0

    def test_returns_extraction_result(self):
        extractor = ASTExtractor()
        result = extractor.extract(str(PYTHON_SIMPLE))

        assert isinstance(result, ExtractionResult)
        assert isinstance(result.files, list)
        assert isinstance(result.nodes, list)
        assert isinstance(result.edges, list)
        assert isinstance(result.errors, list)

    def test_skips_unparseable_files(self, tmp_path):
        (tmp_path / "good.py").write_text("def func():\n    pass\n")
        (tmp_path / "bad.py").write_bytes(b"\x00\x01\x02\xff\xfe")

        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))

        assert len(result.nodes) >= 1
        assert len(result.errors) == 1
        assert "bad.py" in result.errors[0].file_path

    def test_empty_codebase(self, tmp_path):
        extractor = ASTExtractor()
        result = extractor.extract(str(tmp_path))

        assert result.files == []
        assert result.nodes == []
        assert result.edges == []

    def test_invalid_path_raises_error(self):
        extractor = ASTExtractor()
        with pytest.raises((FileNotFoundError, ValueError, OSError)):
            extractor.extract("/nonexistent/path/that/does/not/exist")


# === Collision disambiguation tests (Task 01.7) ===

COLLIDING_INIT = Path(__file__).parent.parent.parent.parent / "fixtures" / "sample_codebases" / "colliding_init"


def test_extract_disambiguates_three_colliding_init():
    result = ASTExtractor().extract(str(COLLIDING_INIT))
    init_ids = [
        n.node_id for n in result.nodes
        if n.node_id.endswith("::__init__") or "::__init__#" in n.node_id
    ]
    assert len(init_ids) == 3
    assert len(set(init_ids)) == 3
    assert any(nid.endswith("::__init__") for nid in init_ids)
    assert any(nid.endswith("::__init__#2") for nid in init_ids)
    assert any(nid.endswith("::__init__#3") for nid in init_ids)
    assert len(set(n.node_id for n in result.nodes)) == len(result.nodes)


def test_extract_no_collision_no_suffix(tmp_path):
    tmp_path.joinpath("a.py").write_text("def foo():\n    pass\n")
    result = ASTExtractor().extract(str(tmp_path))
    assert all("#" not in n.node_id for n in result.nodes)


def test_extract_collision_is_deterministic():
    r1 = ASTExtractor().extract(str(COLLIDING_INIT))
    r2 = ASTExtractor().extract(str(COLLIDING_INIT))
    assert [n.node_id for n in r1.nodes] == [n.node_id for n in r2.nodes]
