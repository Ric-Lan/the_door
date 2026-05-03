"""Entry point detector — identifies framework entry points in AST nodes."""
from __future__ import annotations

from the_door.models import ASTNode


# Known framework entry decorators (matched as substrings)
KNOWN_ENTRY_DECORATORS: frozenset[str] = frozenset({
    # Web frameworks
    "app.route",
    "Controller",
    "Get",
    "Post",
    "Put",
    "Delete",
    "Patch",
    "RequestMapping",
    # Event / scheduling frameworks
    "Cron",
    "EventSubscriber",
    "On",
    "Subscribe",
    "Scheduled",
    # CLI frameworks
    "click.command",
    "click.group",
    "typer.command",
    "app.command",
    "app.callback",
})

# Directory patterns that indicate entry point files
ENTRY_DIRECTORIES: frozenset[str] = frozenset({
    "routes/",
    "handlers/",
    "controllers/",
    "views/",
    "endpoints/",
    "commands/",
    "cli/",
})


class EntryPointDetector:
    """Detect whether an AST node is a framework entry point."""

    def is_entry_point(self, node: ASTNode, in_degree: int, out_degree: int) -> bool:
        """Return True if node is an entry point.

        Entry point rules:
        1. Has a known framework entry decorator, OR
        2. Has in_degree=0 AND out_degree>0 AND file path contains an entry directory, OR
        3. Is a CLI entry function (name is 'main' with out_degree>0, or file is __main__.py)
        """
        # Rule 1: Check decorators
        if self._has_entry_decorator(node):
            return True

        # Rule 2: Zero in-degree, positive out-degree, in entry directory
        if in_degree == 0 and out_degree > 0 and self._is_in_entry_directory(node):
            return True

        # Rule 3: CLI entry patterns
        if self._is_cli_entry(node, out_degree):
            return True

        return False

    def _has_entry_decorator(self, node: ASTNode) -> bool:
        """Check if any decorator matches known entry decorators."""
        for decorator in node.decorators:
            # Strip @ prefix if present
            dec_text = decorator.lstrip("@")
            for known in KNOWN_ENTRY_DECORATORS:
                if known in dec_text:
                    return True
        return False

    def _is_in_entry_directory(self, node: ASTNode) -> bool:
        """Check if the node's file is in a known entry directory."""
        file_path = node.file.replace("\\", "/")
        for entry_dir in ENTRY_DIRECTORIES:
            if entry_dir in file_path:
                return True
        return False

    def _is_cli_entry(self, node: ASTNode, out_degree: int) -> bool:
        """Check if the node is a CLI entry point.

        Matches:
        - Functions named 'main' with out_degree > 0
        - Functions in __main__.py files
        """
        if out_degree == 0:
            return False

        # Function named 'main' (common CLI entry pattern)
        if node.name == "main":
            return True

        # File is __main__.py
        file_path = node.file.replace("\\", "/")
        if file_path.endswith("__main__.py"):
            return True

        return False
