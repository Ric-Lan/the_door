# api_handlers.py 拆分為 api/ package — Implementation Plan（索引）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans。**每個 phase 檔自含其 task 的完整步驟**；執行某 phase 時讀「本 README + 該 phase 檔」即可，不需讀其他 phase 檔。Steps 用 checkbox（`- [ ]`）。

**Goal:** 把 `core/ui/api_handlers.py`（1234 行 / 單一 `APIHandlers` 類 / 21 端點）拆成 `core/ui/api/` package（中轉樞紐 router + 共用依賴 `APIContext` + 集中錯誤碼登記表 + 6 領域 handler），HTTP 行為完全不變。

**Architecture:** 新結構與舊 `api_handlers.py` **先共存**，逐一建好新模組（context → error_codes → router → 6 handler）並各自 TDD，最後一次性把 `server.py` 切到 `router.dispatch` 並刪除舊類。兩道安全網（既有 e2e 13 端點 + 新增 router 綁定測試補 8 端點）全程保持 GREEN，任一步變紅即回退。

**Tech Stack:** Python 3.12、pytest、stdlib `http.server`（`BaseHTTPRequestHandler`）。無新依賴。

**參考 spec:** `docs/superpowers/specs/2026-05-31-api-handlers-split-design.md`

**全域指令注意:** 內層專案在 `the_door/` 跑（`testpaths=["tests"]`）。所有 `pytest` / `git` 指令的 cwd = `the_door/`。Windows console 有 cp950 問題，跑會輸出 emoji 的指令時加 `PYTHONUTF8=1`。

---

## Phase 檔索引（執行順序）

| Phase 檔 | 含 Task | 內容 |
|---|---|---|
| [01-safety-net.md](01-safety-net.md) | Task 1 | router 綁定整合測試（補 e2e 未覆蓋的 8 端點），先 GREEN |
| [02-foundations.md](02-foundations.md) | Task 2–4 | `error_codes.py` / `context.py` / `router.py` 三個根模組 |
| [03-handlers.md](03-handlers.md) | Task 5–10 | 6 領域 handler 提取（**搬移做法與簽名表見本 README 下方**） |
| [04-switchover.md](04-switchover.md) | Task 11 | 組裝 ROUTES + server.py 切到 router |
| [05-cleanup.md](05-cleanup.md) | Task 12 | 移除舊 `api_handlers.py` 與舊測試 |
| [06-docs-and-verify.md](06-docs-and-verify.md) | Task 13–14 | 兩份同源生成文件 + 最終驗收 |

**依賴順序**：01 →（02 內部 error_codes→context→router 有序）→ 03 →04 →05 →06。03 的 6 個 handler 彼此獨立，可任意序或並行。

---

## 檔案結構（拆分後）

```
the_door/src/the_door/core/ui/
  api/
    __init__.py          # 暴露 Router + APIContext + build_routes
    context.py           # APIContext：3 個 lazy 依賴存取器
    error_codes.py       # ERROR_CODES 登記表 + build_error() helper
    router.py            # Route dataclass + build_routes + Router.dispatch
    docgen.py            # 從 ROUTES + ERROR_CODES 生成兩份文件
    _gen_docs.py         # 一次性生成腳本
    handlers/
      __init__.py
      project.py         # ProjectHandlers: get / set_project / status
      analysis.py        # AnalysisHandlers: analyze / update / update_status
      catalog.py         # CatalogHandlers: snapshots / timeline / report_latest
      graph.py           # GraphHandlers: get_l1 / get_l2 / generate_l2 / get_structure / get_layer_explanation / generate_layer_explanation
      diff.py            # DiffHandlers: versions / get_explanation / generate_explanation
      annotation.py      # AnnotationHandlers: get_notes / post_notes / doubts
  server.py              # 改：建 APIContext + Router，dispatch 改呼 router
  api_handlers.py        # 最後刪除
```

```
the_door/tests/
  integration/test_router_binding.py   # 新增安全網（補 8 端點）
  unit/core/ui/api/
    test_context.py  test_error_codes.py  test_router.py  test_docgen.py
    handlers/test_project.py  test_analysis.py  test_catalog.py
             test_graph.py    test_diff.py      test_annotation.py
```

舊 `tests/unit/core/ui/test_api_handlers*.py`（6 檔）在 Task 12 移除，斷言內容已遷入上列新測試。

---

## 共用：領域 handler 搬移做法 + 精確簽名表（Phase 03 引用本節）

> **每個領域 handler（Task 5–10）的共通形態：**
> 1. 新建 `handlers/<domain>.py`，類別 `__init__(self, ctx: APIContext)` 存 `self._ctx`。
> 2. 把舊 `api_handlers.py` 對應 `handle_*` 方法的**函式體逐字搬入**，只做兩種機械轉換：
>    - `self._project_root` → `self._ctx.project_root`；`self._job_store` → `self._ctx.job_store`；
>      `self._switch_project_fn(...)` → `self._ctx.switch_project(...)`。
>    - 方法簽名：**每個方法宣告與原方法相同的具名 path/query 參數**，前面加 `self, ctx=None, *, body=None`，
>      後面加 `**_` 吸收其餘。**不可只用通用 `**params`**——否則搬移後 body 引用的具名變數會綁不到、runtime NameError。
> 3. 業務邏輯、回應 body、錯誤碼**一字不改**（行為不變）。
> 4. 測試：把舊 `test_api_handlers*.py` 相對應斷言搬入新測試檔，建構改為
>    `H = <Domain>Handlers(APIContext(lambda: tmp_path, lambda: job_store, lambda p,f: {...}))`，呼叫改新方法名。
> 5. 舊 `api_handlers.py` 此時**仍保留**（尚未刪），新舊並存。
>
> **精確簽名表**（router 以 `handler(self._ctx, body=body, **path_params, **query)` 呼叫；下列為各方法須宣告的具名參數，均接 `**_`）：
>
> | 新方法 | 具名參數（path/query） | 備註 |
> |---|---|---|
> | `project.get` / `project.status` | 無 | — |
> | `project.set_project` | `body`（POST body） | — |
> | `analysis.analyze` / `analysis.update` | `body`（POST body） | — |
> | `analysis.update_status` | `job_id`（path） | `/api/update/status/{job_id}` |
> | `catalog.snapshots` / `catalog.timeline` / `catalog.report_latest` | 無 | — |
> | `graph.get_l1` | `version_id`（query） | `?version_id=` |
> | `graph.get_l2` / `graph.generate_l2` | `feature_id`（path） | — |
> | `graph.get_structure` | 無 | — |
> | `graph.get_layer_explanation` / `graph.generate_layer_explanation` | `feature_id`, `layer`（path） | — |
> | `diff.versions` | `baseline`, `current`（query） | **搬入後於 body 開頭加 `baseline_id, current_id = baseline, current`（query 名≠原變數名）** |
> | `diff.get_explanation` | `feature_id`（path）, `baseline_version_id`, `current_version_id`, `output_language`（query） | — |
> | `diff.generate_explanation` | `feature_id`（path）, `body`（POST body） | 原簽名 `(feature_id, body)`，body 由 router 以 `body=` 傳入 |
> | `annotation.get_notes` | `mode`, `feature_id`, `version_a`, `version_b`（query） | — |
> | `annotation.post_notes` | `body`（POST body） | — |
> | `annotation.doubts` | 無 | — |
>
> 範例（diff.versions）：`def versions(self, ctx=None, *, body=None, baseline=None, current=None, **_): baseline_id, current_id = baseline, current; <搬入的原 body>`

---

## 驗收清單（對齊 spec §12）

- [ ] 兩道安全網全綠：e2e（13）+ router_binding（8）= 全 21 端點路由正確性受覆蓋
- [ ] 全套測試零回歸、`api/` package 100% 覆蓋
- [ ] `server.py` 僅剩 HTTP 殼 + 呼叫 router；`api_handlers.py` 已移除
- [ ] 兩份文件生成且 contract 測試通過
- [ ] 錯誤碼回應值英文、route summary 繁中
- [ ] body 解析僅存在於 router 一處（server.py 不再重複）

## 執行交接

計畫拆為以上 phase 檔。建議 **subagent-driven**：每個 Task 派新 subagent（讀 README + 對應 phase 檔），task 間 review。或 **inline**（executing-plans 批次 + checkpoint）。逐刀獨立 merge（本刀完成且兩道安全網綠即可 merge，不必等其他刀）。
