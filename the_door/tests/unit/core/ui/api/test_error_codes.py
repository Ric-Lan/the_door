import pytest

from the_door.core.ui.api.error_codes import ERROR_CODES, ErrCode, build_error


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
