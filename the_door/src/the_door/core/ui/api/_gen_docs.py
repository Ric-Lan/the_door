"""Regenerate the published API docs from the live route table / registry.

Run from the inner project dir (``the_door/``)::

    python -m the_door.core.ui.api._gen_docs

Writes ``../docs/api/ai-agent-api-index.md`` and ``../docs/api/error-codes.md``
at the outer repo root.
"""
from __future__ import annotations

from pathlib import Path

from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.docgen import render_api_index, render_error_codes
from the_door.core.ui.api.error_codes import ERROR_CODES
from the_door.core.ui.api.handlers.annotation import AnnotationHandlers
from the_door.core.ui.api.handlers.blocks import BlockHandlers
from the_door.core.ui.api.handlers.catalog import CatalogHandlers
from the_door.core.ui.api.handlers.diff import DiffHandlers
from the_door.core.ui.api.handlers.graph import GraphHandlers
from the_door.core.ui.api.handlers.group import GroupHandlers
from the_door.core.ui.api.handlers.integration import IntegrationHandlers
from the_door.core.ui.api.handlers.project import ProjectHandlers
from the_door.core.ui.api.router import build_routes


def main() -> None:
    ctx = APIContext(lambda: Path("."), lambda p, f: {})
    routes = build_routes(
        ProjectHandlers(ctx),
        CatalogHandlers(ctx),
        GraphHandlers(ctx),
        DiffHandlers(ctx),
        AnnotationHandlers(ctx),
        GroupHandlers(ctx),
        IntegrationHandlers(ctx),
        BlockHandlers(ctx),
    )
    out_dir = Path("../docs/api")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ai-agent-api-index.md").write_text(
        render_api_index(routes), encoding="utf-8"
    )
    (out_dir / "error-codes.md").write_text(
        render_error_codes(ERROR_CODES), encoding="utf-8"
    )
    print("generated 2 docs")


if __name__ == "__main__":  # pragma: no cover - module entry-point guard
    main()
