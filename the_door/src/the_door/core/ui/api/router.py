"""Dispatch hub for core/ui/api.

Routes are declared as ``Route`` dataclass instances.  ``Router.dispatch``
matches the incoming (method, path) pair against the route table, extracts
template parameters, parses POST/PUT/PATCH bodies, calls the handler, and
wraps any exception into a structured ``router.handler_error`` response so
callers always get a (status, dict) pair.
"""
from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Optional

from the_door.core.ui.api.error_codes import build_error


@dataclass(frozen=True)
class Route:
    method: str          # upper-case HTTP verb
    path: str            # template, e.g. "/api/item/{item_id}"
    handler: Callable
    summary: str         # brief Chinese/English label for the route table


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _match(template: str, path: str) -> Optional[dict[str, str]]:
    """Return extracted params if *path* matches *template*, else None.

    Template segments wrapped in ``{name}`` are captured; all other segments
    must match exactly (case-sensitive).
    """
    t_parts = template.split("/")
    p_parts = path.split("/")
    if len(t_parts) != len(p_parts):
        return None
    params: dict[str, str] = {}
    for t, p in zip(t_parts, p_parts):
        if t.startswith("{") and t.endswith("}"):
            params[t[1:-1]] = p
        elif t != p:
            return None
    return params


def _handler_file(handler: Callable) -> str:
    """Return a src-relative ``*.py`` path for *handler*'s defining module."""
    try:
        mod = importlib.import_module(handler.__module__)
        spec = getattr(mod, "__spec__", None)
        if spec and spec.origin:
            origin: str = spec.origin.replace("\\", "/")
            # Trim to src-relative form: keep everything from "the_door/" onward
            marker = "the_door/"
            idx = origin.rfind(marker)
            if idx != -1:
                return origin[idx:]
            return origin
    except Exception:
        pass
    return f"{handler.__module__.replace('.', '/')}.py"


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

_BODY_METHODS = {"POST", "PUT", "PATCH"}


class Router:
    def __init__(self, ctx: Any, routes: list[Route]) -> None:
        self._ctx = ctx
        self._routes = routes

    def dispatch(
        self,
        method: str,
        path: str,
        raw_body: bytes,
        query: Optional[dict[str, str]] = None,
    ) -> tuple[int, dict]:
        """Match (method, path), parse body, call handler, return (status, body)."""
        # Strip query string if present
        path = path.split("?", 1)[0]
        query = query or {}

        path_match = False
        for route in self._routes:
            params = _match(route.path, path)
            if params is None:
                continue
            # Path matched — note it for potential 405
            path_match = True
            if route.method != method.upper():
                continue
            # Method matched — parse body for mutating verbs
            body: dict = {}
            if method.upper() in _BODY_METHODS and raw_body:
                try:
                    body = json.loads(raw_body)
                except (json.JSONDecodeError, ValueError):
                    return build_error(
                        "router.invalid_json",
                        source=f"router:{route.handler.__qualname__}",
                    )
            # Call handler
            try:
                status, resp_body = route.handler(
                    self._ctx, body=body, **params, **query
                )
                return status, resp_body
            except Exception as exc:
                return build_error(
                    "router.handler_error",
                    source=f"router:{route.handler.__qualname__}",
                    message=str(exc),
                    source_file=_handler_file(route.handler),
                )

        if path_match:
            return build_error("router.method_not_allowed", source="router.dispatch")
        return build_error("router.no_route", source="router.dispatch")


# ---------------------------------------------------------------------------
# Route table assembly
# ---------------------------------------------------------------------------

def build_routes(p, a, c, g, d, n) -> list[Route]:
    """p/a/c/g/d/n = Project/Analysis/Catalog/Graph/Diff/Annotation handler instances."""
    return [
        Route("GET",  "/api/project",                              p.get,        summary="讀取當前專案狀態與基本資訊"),
        Route("POST", "/api/set-project",                          p.set_project,summary="切換當前分析的目標專案"),
        Route("GET",  "/api/status",                               p.status,     summary="回報當前專案狀態與建議下一步"),
        Route("POST", "/api/analyze",                              a.analyze,    summary="啟動完整分析的非同步任務（需 API key）"),
        Route("POST", "/api/update",                              a.update,    summary="啟動增量更新分析的非同步任務"),
        Route("GET",  "/api/update/status/{job_id}",               a.update_status, summary="查詢指定分析任務的進度"),
        Route("GET",  "/api/snapshots",                            c.snapshots,  summary="列出所有版本快照"),
        Route("GET",  "/api/timeline",                             c.timeline,   summary="回傳跨版本時間軸"),
        Route("GET",  "/api/report/latest",                        c.report_latest, summary="讀取最近一次分析報告"),
        Route("GET",  "/api/l1",                                   g.get_l1,     summary="讀取指定版本的 L1 功能圖（節點+關聯）"),
        Route("GET",  "/api/l2/{feature_id}",                      g.get_l2,     summary="讀取指定功能的 L2 模組分解（若已生成）"),
        Route("GET",  "/api/structure",                            g.get_structure, summary="讀取原始抽取結構 structure.json"),
        Route("GET",  "/api/layer-explanation/{feature_id}/{layer}", g.get_layer_explanation, summary="讀取指定功能在指定層的說明"),
        Route("GET",  "/api/diff",                                 d.versions,   summary="比對 baseline 與 current 兩版本的功能層差異"),
        Route("GET",  "/api/diff-explanations/{feature_id}",       d.get_explanation, summary="讀取指定功能的差異說明（若已生成）"),
        Route("GET",  "/api/doubts",                               n.doubts,     summary="列出作用域分析產生的疑慮項"),
        Route("GET",  "/api/notes",                                n.get_notes,  summary="讀取使用者註記"),
        Route("POST", "/api/notes",                                n.post_notes, summary="新增使用者註記"),
    ]
