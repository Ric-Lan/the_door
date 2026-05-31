# Phase 04 — 組裝 ROUTES + 切換 server.py（Task 11）

> 讀本檔 + README 即可執行。前置：Phase 02（router）+ Phase 03（6 handler）全完成。
> 驗收靠**兩道安全網**（e2e + router_binding），全程不改其斷言。

## Task 11: 組裝 ROUTES 表 + 切換 server.py 到 router

**Files:**
- Modify: `the_door/src/the_door/core/ui/api/router.py`（加入 `build_routes(...)`）
- Modify: `the_door/src/the_door/core/ui/api/__init__.py`（暴露 Router、APIContext、build_routes）
- Modify: `the_door/src/the_door/core/ui/server.py`（建 APIContext + Router，dispatch 改呼 router；移除舊 GET/POST if-elif 與重複 body 解析）
- Test: 既有 `tests/integration/test_e2e_ui_server.py` + `tests/integration/test_router_binding.py`（皆不改，當切換驗收）

- [ ] **Step 1: 在 router.py 加 `build_routes`（全 21 端點，每條帶繁中 summary）**

```python
def build_routes(p, a, c, g, d, n) -> list[Route]:
    """p/a/c/g/d/n = Project/Analysis/Catalog/Graph/Diff/Annotation handler 實例。"""
    return [
        Route("GET",  "/api/project",                              p.get,        summary="讀取當前專案狀態與基本資訊"),
        Route("POST", "/api/set-project",                          p.set_project,summary="切換當前分析的目標專案"),
        Route("GET",  "/api/status",                               p.status,     summary="回報當前專案狀態與建議下一步"),
        Route("POST", "/api/analyze",                              a.analyze,    summary="啟動完整分析的非同步任務（需 API key）"),
        Route("POST", "/api/update",                               a.update,     summary="啟動增量更新分析的非同步任務"),
        Route("GET",  "/api/update/status/{job_id}",               a.update_status, summary="查詢指定分析任務的進度"),
        Route("GET",  "/api/snapshots",                            c.snapshots,  summary="列出所有版本快照"),
        Route("GET",  "/api/timeline",                             c.timeline,   summary="回傳跨版本時間軸"),
        Route("GET",  "/api/report/latest",                        c.report_latest, summary="讀取最近一次分析報告"),
        Route("GET",  "/api/l1",                                   g.get_l1,     summary="讀取指定版本的 L1 功能圖（節點+關聯）"),
        Route("GET",  "/api/l2/{feature_id}",                      g.get_l2,     summary="讀取指定功能的 L2 模組分解（若已生成）"),
        Route("POST", "/api/l2/{feature_id}/generate",            g.generate_l2,summary="為指定功能啟動 L2 生成任務（需 LLM）"),
        Route("GET",  "/api/structure",                            g.get_structure, summary="讀取原始抽取結構 structure.json"),
        Route("GET",  "/api/layer-explanation/{feature_id}/{layer}", g.get_layer_explanation, summary="讀取指定功能在指定層的說明"),
        Route("POST", "/api/layer-explanation/{feature_id}/{layer}/generate", g.generate_layer_explanation, summary="為指定功能層啟動說明生成（需 LLM）"),
        Route("GET",  "/api/diff",                                 d.versions,   summary="比對 baseline 與 current 兩版本的功能層差異"),
        Route("GET",  "/api/diff-explanations/{feature_id}",       d.get_explanation, summary="讀取指定功能的差異說明（若已生成）"),
        Route("POST", "/api/diff-explanations/{feature_id}/generate", d.generate_explanation, summary="為指定功能啟動差異說明生成（需 LLM）"),
        Route("GET",  "/api/doubts",                               n.doubts,     summary="列出作用域分析產生的疑慮項"),
        Route("GET",  "/api/notes",                                n.get_notes,  summary="讀取使用者註記"),
        Route("POST", "/api/notes",                                n.post_notes, summary="新增使用者註記"),
    ]
```

- [ ] **Step 2: 改 server.py — 建 context+router、dispatch 改呼 router**

把 `server.py` 中 `self._api_handlers = APIHandlers(...)`（約 46 行）改為建 `APIContext` + 6 handler + `Router`：

```python
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.router import Router, build_routes
from the_door.core.ui.api.handlers.project import ProjectHandlers
# … 其餘 5 個 handler import（analysis/catalog/graph/diff/annotation）

ctx = APIContext(
    lambda: self._project_root,   # 沿用現有 fn 來源（與舊 APIHandlers 相同）
    lambda: self._job_store,
    self._switch_project,
)
routes = build_routes(ProjectHandlers(ctx), AnalysisHandlers(ctx), CatalogHandlers(ctx),
                      GraphHandlers(ctx), DiffHandlers(ctx), AnnotationHandlers(ctx))
self._router = Router(ctx, routes)
```

把 `_handle_get` 的 **`if path.startswith("/api/")` 分支**（約 144–219 行的整段 API if-elif）換成單一 router.dispatch；**`else` 靜態服務分支（`status, content_type, body_bytes = static_handler.serve(path)` 那段）原樣保留不動**。把 `_handle_post`（約 229–300 行）整段 API if-elif + 重複 body 解析換成單一 dispatch：

```python
def _handle_get(handler, router, static_handler):
    parsed = urlparse(handler.path)
    path = parsed.path
    if path.startswith("/api/"):
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        status, body = router.dispatch("GET", path, raw_body=b"", query=query)
        _send_json(handler, status, body)
        return
    # —— 以下靜態服務分支：保留現行實作（serve(path) 回 3-tuple），勿改 ——
    ...（現行 else 分支原樣）

def _handle_post(handler, router):
    parsed = urlparse(handler.path)
    path = parsed.path
    length = int(handler.headers.get("Content-Length", 0))
    raw = handler.rfile.read(length) if length > 0 else b""
    query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    status, body = router.dispatch("POST", path, raw_body=raw, query=query)
    _send_json(handler, status, body)
```

> `urlparse`/`parse_qs` 已在 server.py import（line 18），直接用。body 解析（json.loads / 壞 JSON→400）現在**只在 router 一處**；server.py 不再重複。`_RequestHandler.do_GET/do_POST`（約 62–66 行）的呼叫改傳 `self._router`（取代 `api_handlers`）。

- [ ] **Step 3: 跑兩道安全網 + 全 ui 測試**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/integration/test_e2e_ui_server.py tests/integration/test_router_binding.py tests/unit/core/ui/ -v`
Expected: 全 PASS（行為不變）。若任一紅 → router 綁定或 server 切換有誤，修到綠；**不得修改 e2e / router_binding 斷言**。

- [ ] **Step 4: Commit**

```bash
cd the_door && git add src/the_door/core/ui/api/router.py src/the_door/core/ui/api/__init__.py src/the_door/core/ui/server.py
git commit -m "feat(api): assemble ROUTES + switch server.py to router dispatch"
```
