"""Unit tests for source_reviewer module.

Tests are written BEFORE implementation (TDD red phase).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from the_door.core.reading.source_reviewer import SourceReviewer, SourceSnippet


class TestSourceReviewerExtractSnippet:
    """Unit tests for SourceReviewer.extract_snippet()."""

    def test_extract_known_function(self, tmp_path: Path):
        """extract_snippet for known function → correct SourceSnippet."""
        source_file = tmp_path / "module.py"
        source_file.write_text(
            "import os\n"
            "\n"
            "def hello_world():\n"
            "    print('hello')\n"
            "    return True\n"
            "\n"
            "def other_func():\n"
            "    pass\n"
        )

        reviewer = SourceReviewer(codebase_path=tmp_path)
        snippet = reviewer.extract_snippet(
            node_id="module.py::hello_world",
            file_path="module.py",
        )

        assert snippet is not None
        assert isinstance(snippet, SourceSnippet)
        assert snippet.file_path == "module.py"
        assert "def hello_world():" in snippet.source_text
        assert "print('hello')" in snippet.source_text
        assert "return True" in snippet.source_text
        assert snippet.start_line == 3
        assert snippet.end_line == 5

    def test_source_file_not_found_returns_none(self, tmp_path: Path):
        """Source file not found → returns None."""
        reviewer = SourceReviewer(codebase_path=tmp_path)
        snippet = reviewer.extract_snippet(
            node_id="nonexistent.py::func",
            file_path="nonexistent.py",
        )

        assert snippet is None

    def test_node_not_locatable_returns_none(self, tmp_path: Path):
        """Node cannot be located in file → returns None."""
        source_file = tmp_path / "module.py"
        source_file.write_text(
            "def existing_func():\n"
            "    pass\n"
        )

        reviewer = SourceReviewer(codebase_path=tmp_path)
        snippet = reviewer.extract_snippet(
            node_id="module.py::nonexistent_func",
            file_path="module.py",
        )

        assert snippet is None

    def test_snippet_exceeding_10kb_truncated(self, tmp_path: Path):
        """Snippet exceeding 10KB → truncated with '[truncated]' marker."""
        # Create a function with a very large body
        large_body = "\n".join(f"    x_{i} = {i}" for i in range(3000))
        source_file = tmp_path / "large_module.py"
        source_file.write_text(f"def large_func():\n{large_body}\n")

        reviewer = SourceReviewer(codebase_path=tmp_path)
        snippet = reviewer.extract_snippet(
            node_id="large_module.py::large_func",
            file_path="large_module.py",
        )

        assert snippet is not None
        assert len(snippet.source_text) <= 10 * 1024 + 100  # Allow small overhead
        assert "[truncated]" in snippet.source_text

    def test_extracts_only_specific_node(self, tmp_path: Path):
        """Extracts only the specific node, not entire file."""
        source_file = tmp_path / "module.py"
        source_file.write_text(
            "def func_a():\n"
            "    return 'a'\n"
            "\n"
            "def func_b():\n"
            "    return 'b'\n"
            "\n"
            "def func_c():\n"
            "    return 'c'\n"
        )

        reviewer = SourceReviewer(codebase_path=tmp_path)
        snippet = reviewer.extract_snippet(
            node_id="module.py::func_b",
            file_path="module.py",
        )

        assert snippet is not None
        assert "func_b" in snippet.source_text
        assert "func_a" not in snippet.source_text
        assert "func_c" not in snippet.source_text
