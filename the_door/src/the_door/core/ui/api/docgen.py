"""Markdown documentation generators for the core/ui/api package.

These render two same-source docs from the live route table and error-code
registry, so the published docs can never drift from the code:

* ``render_api_index``  -> AI-agent API index (quick-reference route table).
* ``render_error_codes`` -> error-code catalog.

Every route ``path``/``summary`` and every error ``code``/``desc`` appears
verbatim in the output (a contract test depends on this), so values are NOT
HTML-escaped or otherwise altered.  Ordering is deterministic: routes follow
the route-list order; error codes are sorted by code.
"""
from __future__ import annotations

from typing import Iterable

from the_door.core.ui.api.error_codes import ErrCode
from the_door.core.ui.api.router import Route


def _handler_name(handler) -> str:
    """A readable handler identifier (``ClassName.method`` when available)."""
    return getattr(handler, "__qualname__", None) or getattr(handler, "__name__", repr(handler))


def render_api_index(routes: Iterable[Route]) -> str:
    """Render the AI-agent API index markdown from the live route table."""
    routes = list(routes)
    lines = [
        "# AI-Agent API Index",
        "",
        "Auto-generated from the live route table "
        "(`the_door.core.ui.api.router.build_routes`). Do not edit by hand — "
        "run `python -m the_door.core.ui.api._gen_docs` to regenerate.",
        "",
        f"Total routes: {len(routes)}",
        "",
        "| Method | Path | Summary | Handler |",
        "| --- | --- | --- | --- |",
    ]
    for rt in routes:
        lines.append(
            f"| {rt.method} | `{rt.path}` | {rt.summary} | `{_handler_name(rt.handler)}` |"
        )
    lines += [
        "",
        "## Error codes",
        "",
        "Every handler returns errors via the central registry. See "
        "[error-codes.md](./error-codes.md) for the full catalog of codes, "
        "HTTP statuses, owning source files, and descriptions.",
        "",
    ]
    return "\n".join(lines)


def render_error_codes(codes: dict[str, ErrCode]) -> str:
    """Render the error-code catalog markdown from the registry."""
    lines = [
        "# Error Codes",
        "",
        "Auto-generated from `the_door.core.ui.api.error_codes.ERROR_CODES`. "
        "Do not edit by hand — run `python -m the_door.core.ui.api._gen_docs` "
        "to regenerate.",
        "",
        f"Total codes: {len(codes)}",
        "",
        "| Code | HTTP | Source File | Description |",
        "| --- | --- | --- | --- |",
    ]
    for code in sorted(codes):
        ec = codes[code]
        lines.append(f"| `{code}` | {ec.http} | `{ec.file}` | {ec.desc} |")
    lines.append("")
    return "\n".join(lines)
