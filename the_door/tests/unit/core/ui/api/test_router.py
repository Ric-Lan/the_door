from the_door.core.ui.api.router import Router, Route, _handler_file


def _ok(ctx, **kw):
    return 200, {"got": kw}


def _boom(ctx, **kw):
    raise ValueError("kaboom")


def _routes():
    return [
        Route("GET",  "/api/ping",            _ok,   summary="測試用 ping"),
        Route("GET",  "/api/item/{item_id}",  _ok,   summary="測試用取 item"),
        Route("POST", "/api/item/{item_id}",  _ok,   summary="測試用建 item"),
        Route("GET",  "/api/boom",            _boom, summary="測試用爆炸"),
    ]


def test_exact_match_dispatch():
    r = Router(ctx=None, routes=_routes())
    status, body = r.dispatch("GET", "/api/ping", raw_body=b"")
    assert status == 200


def test_template_param_extracted():
    r = Router(ctx=None, routes=_routes())
    status, body = r.dispatch("GET", "/api/item/42", raw_body=b"")
    assert body["got"]["item_id"] == "42"


def test_no_route_404():
    r = Router(ctx=None, routes=_routes())
    status, body = r.dispatch("GET", "/api/nope", raw_body=b"")
    assert status == 404 and body["error"]["code"] == "router.no_route"


def test_method_not_allowed_405():
    r = Router(ctx=None, routes=_routes())
    status, body = r.dispatch("DELETE", "/api/ping", raw_body=b"")
    assert status == 405 and body["error"]["code"] == "router.method_not_allowed"


def test_post_bad_json_400():
    r = Router(ctx=None, routes=_routes())
    status, body = r.dispatch("POST", "/api/item/1", raw_body=b"{bad")
    assert status == 400 and body["error"]["code"] == "router.invalid_json"


def test_handler_exception_500_with_source_file():
    r = Router(ctx=None, routes=_routes())
    status, body = r.dispatch("GET", "/api/boom", raw_body=b"")
    assert status == 500
    assert body["error"]["code"] == "router.handler_error"
    assert body["error"]["source"].startswith("router:")
    assert body["error"]["source_file"].endswith(".py")


def test_every_route_has_nonempty_summary():
    for rt in _routes():
        assert rt.summary.strip()


def test_handler_file_origin_without_marker(monkeypatch):
    """When the module's origin lacks the 'the_door/' marker, return origin verbatim."""
    import importlib

    class _Spec:
        origin = "/some/other/place/mymod.py"

    class _Mod:
        __spec__ = _Spec()

    monkeypatch.setattr(importlib, "import_module", lambda name: _Mod())

    def fake_handler():
        pass
    fake_handler.__module__ = "mymod"
    assert _handler_file(fake_handler) == "/some/other/place/mymod.py"


def test_handler_file_import_failure_fallback(monkeypatch):
    """When import_module raises, fall back to the dotted-module path form."""
    import importlib

    def boom(name):
        raise ImportError("nope")
    monkeypatch.setattr(importlib, "import_module", boom)

    def fake_handler():
        pass
    fake_handler.__module__ = "pkg.sub.mod"
    assert _handler_file(fake_handler) == "pkg/sub/mod.py"
