# 設計：`api_handlers.py` 拆分為 `api/` package（重構第一刀）

> **日期**：2026-05-31
> **類型**：純重構（結構先行、行為不變）
> **範圍**：將 `core/ui/api_handlers.py`（1234 行 / 21 端點）拆成 `core/ui/api/` package，
> 引入集中式路由樞紐、共用依賴 context、集中錯誤碼登記表、兩份同源生成文件。
> **背景**：The Door 自我重構待辦的第一刀（見
> `docs/refactoring/2026-05-31-refactoring-backlog.md`）。本檔僅涵蓋這一刀。

---

## 1. 動機與證據

- `api_handlers.py` 全 repo 行數第一（1234 行），單一 `APIHandlers` 類別承載 21 個
  互不相干的端點（snapshots / L1-L2 / diff / doubts / timeline / jobs / notes …）。
- 多職責、只因「都叫 API」被綁一檔 → 符合拆分準則 A（多職責、邊界清楚、按域拆不增耦合）。
- 額外發現的冗餘：`server.py` 的 POST 分派中，body 解析（Content-Length → read →
  `json.loads` → 400）**被複製 4+ 次**；GET/POST 各一長串 if/elif。

## 2. 決策準則（北極星）

1. 可讀性／可維護性優先於「乾淨度」。
2. 結構先行、行為不變（純重構、測試零回歸、覆蓋不降）。
3. 證據驅動。
4. 能簡潔就簡潔——抽象要償還成本。

**拆分與簡潔不衝突、各司其職**：拆分服務維護性（功能獨立、明確），簡潔服務效率
（不繞路、不重工）。好的動刀讓兩者同時成立。

**護欄（越線即否決）**：不改抽取層 / ASTNode / L1–L3 / snapshot schema；
不寫框架/廠商解析器；測試 100% 覆蓋。

## 3. 不可變契約

> **HTTP 表面（URL + method + 回應 body）完全不變、行為完全不變。**

`APIHandlers` 為純內部類別，唯一生產端消費者是 `server.py`（已驗證），可乾淨移除、
不留 facade。前端打 HTTP URL，URL 不動 → 前端零影響。

## 4. 目標結構與分類原則

### 分類原則（package by domain，不為填資料夾而拆碎）

1. 分類資料夾是**避免重構後「一坨平鋪」**的手段，不是把檔案拆更細的理由。
2. 資料夾**收同類的多個檔**；不為單一檔開資料夾。
3. 拆分只沿**真實職責接縫**，數量由職責決定。
4. 跨領域共用放 package 根，分類深度上限一層。

> 註：拆檔對**執行期效率幾乎零影響**（Python import 有 cache）；過度拆的代價是
> 維護性，故只沿 6 條領域接縫拆，不再細分。

### 結構

```
core/ui/api/
  __init__.py          # 對外入口：暴露 router + APIContext
  context.py           # APIContext：共用依賴資料袋（跨領域，放根）
  router.py            # 中轉樞紐 + 集中 body 解析 + 路由表（跨領域，放根）
  error_codes.py       # 集中式錯誤碼登記表（跨領域，放根）
  _shared.py           # 共用 helper：錯誤封套等（如有共用才建）
  handlers/            # 分類資料夾：6 個領域 handler，根目錄不堆雜
    project.py         #   project / set-project / status
    analysis.py        #   analyze / update / update-status（async job）
    catalog.py         #   snapshots / timeline / report-latest（唯讀）
    graph.py           #   l1 / l2(+gen) / structure / layer-explanation(+gen)
    diff.py            #   diff / diff-explanations(+gen)
    annotation.py      #   notes / doubts
```

### 領域劃分（6 域，職責內聚）

| 領域 | 端點 | 內聚理由 |
|---|---|---|
| project | project / set-project / status | 當前專案是誰、切換、狀態 |
| analysis | analyze / update / update-status | async job 驅動的重運算 |
| catalog | snapshots / timeline / report-latest | 唯讀版本目錄查詢 |
| graph | l1 / l2(+gen) / structure / layer-explanation(+gen) | 圖層內容讀取與生成 |
| diff | diff / diff-explanations(+gen) | 版本比對與差異說明 |
| annotation | notes / doubts | 使用者疊加的標註資料 |

每個 handler 都能單獨回答「做什麼／怎麼用／依賴什麼」，彼此不互 import，只共用 `APIContext`。

## 5. 中轉樞紐 router

### 職責

收 `(method, path, raw_body)` → 比對路由表 → 給對應 handler 需要的參數 → 回
`(status, body)`。**只做調度，不含業務邏輯。** 收掉 server.py 散落的：GET/POST
if/elif、重複 body 解析、動態路徑手動 split、405 散判。

### 中央路由表（決策：集中式，API 全貌單一擁有者）

router.py 內一張宣告式表，**每條路由帶繁中 `summary`**（用途註解就住在路由旁，
定位 = 讀表；並作為 API 文件單一來源）：

```
ROUTES = [
  Route("GET",  "/api/l1",                       graph.get_l1,
        summary="讀取指定版本的 L1 功能圖（節點 + 功能間關聯）"),
  Route("POST", "/api/l2/{feature_id}/generate", graph.generate_l2,
        summary="為指定功能啟動 L2 模組分解的非同步生成任務（需 LLM）"),
  Route("GET",  "/api/diff",                      diff.versions,
        summary="比對 baseline 與 current 兩版本，回傳功能層差異圖"),
  ...
]
```

- `{job_id}`/`{feature_id}` 為路徑參數模板，比對時抽出、以關鍵字傳給 handler。
- query string 由 router 解析後一併傳入。
- 比對順序：精確路徑 → 模板路徑；命中後檢查 method；POST 才解析 body。

### dispatch 流程

```
server.py：收 HTTP → 取 method/path/raw_body → router.dispatch(...) → 送 JSON
router.dispatch：
  1. 比對 ROUTES（精確 → 模板），無命中 → 404
  2. method 不符 → 405
  3. POST → 集中解析 body（壞 JSON → 400）
  4. try: handler(ctx, **path_params, **query, body=...)
     except Exception → 500 + handler_error 封套（帶 source + source_file）
  5. 回傳 (status, body)
```

`server.py` 縮成「收 HTTP → 交 router → 送 JSON」純 HTTP 殼。

### 守簡潔

router = 一張表 + 一個小模板比對器（約 20 行），**不是框架**：無中介層鏈、
無攔截器、無裝飾器魔法、無正則路由 DSL。

## 6. 共用依賴 `APIContext`

各 store 現況皆**每次呼叫從 `project_root` 現建、無快取**（因專案動態切換），故 context
只需持有 3 樣 lazy 存取器：

```
@dataclass(frozen=True)
class APIContext:
    _project_root_fn: Callable[[], Path]
    _job_store_fn: Callable[[], JobStore]
    _switch_project_fn: Callable[[str, bool], dict]

    @property
    def project_root(self) -> Path:    return self._project_root_fn()
    @property
    def job_store(self) -> JobStore:   return self._job_store_fn()
    def switch_project(self, path, force): return self._switch_project_fn(path, force)
```

- **明細可見**：handler 拿 `ctx` 即知可用 `ctx.project_root` / `ctx.job_store` /
  `ctx.switch_project`——依賴不被藏（故否決「依賴樞紐 / service locator」）。
- **動態切換不破**：每次經 fn 取當前值，與現況 `self._project_root` 行為一致。
- handler 內 store 照舊現建：`SnapshotStore(self._ctx.project_root)`。
- **組裝點單一**：server bootstrap 建一個 `APIContext` 交給 router，router 用它
  實例化 6 個領域 handler。
- **紀律**：context 只裝跨領域共用的這 3 樣；單一領域用的不准塞入（防 god-object）；
  純資料 + property，不含業務邏輯、不做 store 快取。

## 7. 錯誤機制與集中式錯誤碼登記表

### 錯誤回應形狀（加入檔案標記）

```
{
  "error": {
    "code": "router.handler_error",
    "message": "...",
    "source": "router:diff.versions",               # 邏輯來源（誰）
    "source_file": "core/ui/api/handlers/diff.py"    # 檔案標記（哪個檔），src 相對路徑
  }
}
```

### 集中式錯誤碼登記表 `error_codes.py`

所有 API 區錯誤碼的唯一登記處（沿用既有封套欄位 code/message/source，不另造）：

```
ERROR_CODES = {
  "router.no_route":           ErrCode(http=404, file="core/ui/api/router.py",
                                       desc="請求路徑未命中任何路由"),
  "router.method_not_allowed": ErrCode(http=405, file="core/ui/api/router.py",
                                       desc="路徑存在但 HTTP method 不符"),
  "router.invalid_json":       ErrCode(http=400, file="core/ui/api/router.py",
                                       desc="POST body 非合法 JSON"),
  "router.handler_error":      ErrCode(http=500, file="<動態：失敗 handler 之檔>",
                                       desc="handler 拋出未預期例外"),
  "l2_not_generated":          ErrCode(http=404, file="core/ui/api/handlers/graph.py",
                                       desc="該功能尚未生成 L2"),
  ...（API 區既有業務碼一併登記）
}
```

一次解三事：
- **檔案標記**：建封套時用 code 查表自動帶出 `source_file`。
- **可查找**：找/加碼只看這張表。
- **防衝突**：新增碼須登記，重複 key 由測試擋下。

**紀律**：`ErrCode` 為扁平資料（http/file/desc），非例外繼承樹；本刀只登記
**API 區**（router + 6 handler）的碼，repo 其他散碼全面收編**另立 backlog**（YAGNI）；
原則入 spec：新增 API 錯誤碼一律先登記此表。

`router.handler_error` 只兜 handler 未預期例外，**不**攔截/改寫 handler 自身的正常
業務錯誤回應（如 `l2_not_generated`）。

## 8. 兩份「程式生成、契約釘住」的文件

### 8a. AI agent 索引版 API 文件 → `docs/api/ai-agent-api-index.md`

**從路由表 `summary` 生成**：

| 區塊 | 內容 |
|---|---|
| 快速索引表 | method · path · 繁中 summary · 對應 handler（一頁掃完全 API） |
| 每端點細項 | 路徑/query 參數、回應 body 形狀、可能錯誤碼 |
| 錯誤碼附錄 | 從 `ERROR_CODES` 生成（同源） |

導向：給 AI agent 用、精簡可掃描、範例可直接打。

### 8b. 錯誤碼目錄 → `docs/api/error-codes.md`

從 `ERROR_CODES` 登記表生成（code · http · file · desc）。

### 防 stale

兩份文件皆由 `summary` / `ERROR_CODES` 生成，程式改文件跟著改，不漂移。

## 9. 測試策略（TDD）

### 行為不變安全網

`tests/integration/test_e2e_ui_server.py` 對全 13 端點發**真 HTTP**=行為凍結基準，
重構全程必須 GREEN（URL/method/回應 body 一字不差）；任一步變紅 = 改壞行為，回退。

### 兩層單元測試（鏡像分類）

```
tests/unit/core/ui/api/
  handlers/test_project.py     # 建 ctx + ProjectHandlers，呼新方法、沿用舊斷言
  handlers/test_analysis.py
  handlers/test_catalog.py
  handlers/test_graph.py
  handlers/test_diff.py
  handlers/test_annotation.py
  test_router.py     # 路徑比對 / 405 / 404 / body 解析 / 壞 JSON 400 /
                     #   handler 拋例外 → 500 + router.handler_error + source_file 正確
  test_context.py    # 動態切換：project_root_fn 變更後 ctx.project_root 跟著變
  test_error_codes.py# 每碼有 http/file/desc；重複 key 偵測
```

### Contract 測試（釘不變量）

- 每條 route 的 `summary` 非空（漏寫繁中註解 → 紅）。
- `ERROR_CODES` 每碼齊備且唯一。
- 生成的兩份文件涵蓋所有 route / 所有碼。

### 覆蓋率

新 `api/` package 每檔 100% 覆蓋；移除 `api_handlers.py` 後無指向死類別的殘骸。

## 10. 方法改名對照（舊 → 新）

```
handle_get_project              → project.get
handle_post_set_project         → project.set_project
handle_get_status               → project.status
handle_post_analyze             → analysis.analyze
handle_post_update              → analysis.update
handle_get_update_status        → analysis.update_status
handle_get_snapshots            → catalog.snapshots
handle_get_timeline             → catalog.timeline
handle_get_l1                   → graph.get_l1
handle_get_l2                   → graph.get_l2
handle_post_l2_generate         → graph.generate_l2
handle_get_structure            → graph.get_structure
handle_get_layer_explanation    → graph.get_layer_explanation
handle_post_layer_explanation_generate → graph.generate_layer_explanation
handle_diff_versions            → diff.versions
handle_get_diff_explanation     → diff.get_explanation
handle_post_diff_explanation_generate  → diff.generate_explanation
handle_get_report_latest        → catalog.report_latest   # 歸 catalog（唯讀查詢）
handle_get_doubts               → annotation.doubts
handle_get_notes                → annotation.get_notes
handle_post_notes               → annotation.post_notes
```

## 11. 範圍邊界（YAGNI / 非目標）

- **本刀只拆 `api_handlers.py`**；其他刀（guidance dead-code、models.py 套件化、
  report_renderer 等）見 refactoring backlog，不在此。
- repo 全域錯誤碼收編 = 另立 backlog。
- 不改任何端點的 URL / 回應語意 / 業務邏輯。
- 不引入 web framework、不改 HTTP server 實作（仍用既有 `BaseHTTPRequestHandler`）。

## 12. 驗收

- e2e 真 HTTP 測試全綠（行為不變）。
- 全套測試零回歸、`api/` package 100% 覆蓋。
- `server.py` 僅剩 HTTP 殼 + 呼叫 router；`api_handlers.py` 移除。
- 兩份文件生成且 contract 測試通過。
- 以 The Door 對重構前後做結構 diff，確認拓樸語意一致（只搬位置）。
