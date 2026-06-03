import re
from pathlib import Path

import pytest

import the_door.core.ui.api as api_pkg
from the_door.core.ui.api.error_codes import ERROR_CODES, ErrCode, build_error


def _codes_emitted_by_handlers() -> set[str]:
    """Scan the API layer source for every error code string it actually
    emits (via ``code="..."`` kwargs and positional ``build_error("...")``),
    so the registry can be checked for completeness against real usage."""
    api_dir = Path(api_pkg.__file__).parent
    sources = list((api_dir / "handlers").glob("*.py")) + [api_dir / "router.py"]
    emitted: set[str] = set()
    for py in sources:
        src = py.read_text(encoding="utf-8")
        emitted |= set(re.findall(r'code\s*=\s*"([^"]+)"', src))
        emitted |= set(re.findall(r'build_error\(\s*"([^"]+)"', src))
    return emitted


def test_build_error_unregistered_code_raises():
    with pytest.raises(ValueError, match="unregistered error code"):
        build_error("does.not.exist", source="test")


def test_every_code_has_http_file_desc():
    for code, ec in ERROR_CODES.items():
        assert isinstance(ec.http, int) and ec.file and ec.desc


def test_descs_are_english_ascii():
    for ec in ERROR_CODES.values():
        assert ec.desc.isascii(), f"error desc must be English: {ec.desc!r}"


def test_build_error_fills_source_file_from_registry():
    status, body = build_error("router.no_route", source="router.dispatch")
    assert status == 404
    assert body["error"]["code"] == "router.no_route"
    assert body["error"]["source_file"] == "core/ui/api/router.py"
    assert body["error"]["message"].isascii()


def test_router_codes_registered():
    for c in ("router.no_route", "router.method_not_allowed", "router.invalid_json", "router.handler_error"):
        assert c in ERROR_CODES


def test_every_emitted_code_is_registered():
    """Drift guard: every error code the handlers actually emit must be in the
    central registry, so docs/api/error-codes.md stays a complete catalog."""
    emitted = _codes_emitted_by_handlers()
    missing = sorted(emitted - set(ERROR_CODES))
    assert not missing, (
        f"error codes emitted by handlers but not registered in ERROR_CODES: "
        f"{missing} — add them to error_codes.py and regenerate the docs "
        f"(python -m the_door.core.ui.api._gen_docs)"
    )
