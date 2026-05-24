"""File discovery module — enumerates source files, detects language, respects .gitignore."""
from __future__ import annotations

import os
from pathlib import Path

import pathspec

from the_door.models import FileInfo

# Extension → language mapping
_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".h": "c",
}

# Directories always ignored regardless of .gitignore
_DEFAULT_IGNORE_PATTERNS = [
    ".git/",
    ".claude/",
    "node_modules/",
    "__pycache__/",
    "dist/",
    "build/",
    ".tox/",
    ".mypy_cache/",
    ".pytest_cache/",
    "*.pyc",
    "*.pyo",
]


class FileDiscovery:
    """Enumerate source files in a codebase, detect language, respect .gitignore."""

    def discover(
        self,
        codebase_path: str,
        extra_ignore: list[str] | None = None,
    ) -> list[FileInfo]:
        """Walk the directory tree and return FileInfo for each recognised source file.

        Respects .gitignore patterns found at the codebase root.
        Skips files whose extension is not in the known language map.
        Returns an empty list for empty directories.
        """
        root = Path(codebase_path).resolve()
        if not root.is_dir():
            return []

        spec = self._load_gitignore(root, extra_ignore=extra_ignore or [])
        results: list[FileInfo] = []

        for dirpath, dirnames, filenames in os.walk(root):
            # Compute relative directory path for pattern matching
            rel_dir = Path(dirpath).relative_to(root)

            # Filter out ignored directories in-place so os.walk skips them
            dirnames[:] = [
                d
                for d in dirnames
                if not spec.match_file(str(rel_dir / d) + "/")
            ]

            for fname in sorted(filenames):
                rel_path = str(rel_dir / fname) if str(rel_dir) != "." else fname
                # Normalise to forward slashes for consistent matching
                rel_path = rel_path.replace("\\", "/")

                if spec.match_file(rel_path):
                    continue

                ext = os.path.splitext(fname)[1].lower()
                language = _EXTENSION_MAP.get(ext)
                if language is None:
                    continue

                results.append(FileInfo(path=rel_path, language=language))

        return results

    @staticmethod
    def _load_gitignore(
        root: Path,
        extra_ignore: list[str] | None = None,
    ) -> pathspec.PathSpec:
        """Load .gitignore from root and combine with default ignore patterns."""
        patterns = list(_DEFAULT_IGNORE_PATTERNS)
        if extra_ignore:
            patterns.extend(extra_ignore)
        gitignore = root / ".gitignore"
        if gitignore.is_file():
            patterns.extend(
                line.strip()
                for line in gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
                if line.strip() and not line.strip().startswith("#")
            )
        return pathspec.PathSpec.from_lines("gitignore", patterns)
