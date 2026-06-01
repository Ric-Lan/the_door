from pathlib import Path
from the_door.core.ui.api.docgen import render_api_index, render_error_codes
from the_door.core.ui.api.router import build_routes
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.error_codes import ERROR_CODES
from the_door.core.ui.api.handlers.project import ProjectHandlers
from the_door.core.ui.api.handlers.analysis import AnalysisHandlers
from the_door.core.ui.api.handlers.catalog import CatalogHandlers
from the_door.core.ui.api.handlers.graph import GraphHandlers
from the_door.core.ui.api.handlers.diff import DiffHandlers
from the_door.core.ui.api.handlers.annotation import AnnotationHandlers

def _routes():
    ctx = APIContext(lambda: Path("."), lambda: None, lambda p, f: {})
    return build_routes(ProjectHandlers(ctx), AnalysisHandlers(ctx), CatalogHandlers(ctx),
                        GraphHandlers(ctx), DiffHandlers(ctx), AnnotationHandlers(ctx))

def test_api_index_covers_every_route():
    routes = _routes()
    md = render_api_index(routes)
    for rt in routes:
        assert rt.path in md and rt.summary in md

def test_error_doc_covers_every_code():
    md = render_error_codes(ERROR_CODES)
    for code, ec in ERROR_CODES.items():
        assert code in md and ec.desc in md

def test_every_route_summary_nonempty():
    for rt in _routes():
        assert rt.summary.strip()


def test_gen_docs_main_writes_two_files(tmp_path, monkeypatch, capsys):
    # main() writes to Path("../docs/api") relative to cwd; run it in an isolated
    # working dir so it never touches the real repo docs.
    work = tmp_path / "the_door"
    work.mkdir()
    monkeypatch.chdir(work)
    from the_door.core.ui.api import _gen_docs
    _gen_docs.main()
    out = capsys.readouterr().out
    assert "generated 2 docs" in out
    assert (tmp_path / "docs" / "api" / "ai-agent-api-index.md").exists()
    assert (tmp_path / "docs" / "api" / "error-codes.md").exists()
