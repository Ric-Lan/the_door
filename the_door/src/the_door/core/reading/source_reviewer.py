"""Source reviewer — extract function body from source for LLM review."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


MAX_SNIPPET_BYTES = 10 * 1024  # 10KB


@dataclass
class SourceSnippet:
    """Extracted source code snippet for LLM review."""

    file_path: str
    source_text: str
    start_line: int
    end_line: int


class SourceReviewer:
    """Extract original source code snippets for nodes needing review."""

    def __init__(self, codebase_path: Path) -> None:
        self._codebase_path = codebase_path

    def extract_snippet(
        self,
        node_id: str,
        file_path: str,
    ) -> SourceSnippet | None:
        """Extract function body or class definition from source file.

        Returns None if file not found or node cannot be located.
        Only extracts the specific node, not the entire file.
        """
        # Resolve file path
        full_path = self._codebase_path / file_path
        if not full_path.exists():
            return None

        try:
            content = full_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

        lines = content.splitlines(keepends=True)

        # Extract function/class name from node_id (format: "file.py::func_name")
        parts = node_id.split("::")
        if len(parts) < 2:
            return None
        func_name = parts[-1]

        # Find the function/class definition
        start_line, end_line = self._find_definition(lines, func_name)
        if start_line is None:
            return None

        # Extract the snippet
        snippet_lines = lines[start_line - 1 : end_line]
        source_text = "".join(snippet_lines)

        # Truncate if exceeding 10KB
        if len(source_text.encode("utf-8")) > MAX_SNIPPET_BYTES:
            # Truncate to fit within limit
            truncated = source_text[:MAX_SNIPPET_BYTES].rsplit("\n", 1)[0]
            source_text = truncated + "\n[truncated]\n"

        return SourceSnippet(
            file_path=file_path,
            source_text=source_text,
            start_line=start_line,
            end_line=end_line,
        )

    def _find_definition(
        self, lines: list[str], func_name: str
    ) -> tuple[int | None, int | None]:
        """Find the start and end line of a function/class definition.

        Returns (start_line, end_line) as 1-indexed inclusive, or (None, None).
        """
        # Pattern to match def/class with the given name
        pattern = re.compile(
            rf"^(\s*)(def|class)\s+{re.escape(func_name)}\s*[\(:]"
        )

        for i, line in enumerate(lines):
            match = pattern.match(line)
            if match:
                start_line = i + 1  # 1-indexed
                indent = len(match.group(1))
                # Find end of definition (next line at same or lower indent, or EOF)
                end_line = self._find_end_of_block(lines, i, indent)
                return start_line, end_line

        return None, None

    def _find_end_of_block(
        self, lines: list[str], start_idx: int, base_indent: int
    ) -> int:
        """Find the last line of a block starting at start_idx.

        A block ends when we encounter a non-empty line at the same or lower
        indentation level (excluding the start line itself).
        """
        last_content_line = start_idx

        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            stripped = line.rstrip()

            # Skip empty lines
            if not stripped:
                continue

            # Calculate indentation
            line_indent = len(line) - len(line.lstrip())

            # If indentation is <= base, block has ended
            if line_indent <= base_indent:
                break

            last_content_line = i

        return last_content_line + 1  # 1-indexed
