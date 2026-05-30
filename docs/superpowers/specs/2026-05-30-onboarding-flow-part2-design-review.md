# Onboarding Flow Part 2 Design Spec — 審查清單

> 對象：`docs/superpowers/specs/2026-05-30-onboarding-flow-part2-design.md`（commit `a38f91d`）
> 審查日期：2026-05-30
> 審查依據：TDD / CLEAN CODE / 邏輯 bug / 幻覺 / 資源浪費 / 過度設計
> 用法：勾選 `[x]` 表示同意採納 → 一輪 spec patch 把所有採納項一次改完。
>
> **2026-05-30 更新：13 條全部 grep 驗證為真且已 inline patch 進 spec（未 commit）。** 另發現一條更嚴重的衍生 bug A0（精靈 `run_analyze_pipeline` 不發 `[步驟 N/M]` 訊息、`job_store` 正則完全抓不到、精靈 PROGRESS 頁當前根本沒 step 資料），併入 A3 修法以 adapter 解。下方 `[x]` 標示已套用。

---

## A. Critical（不修會壞落地或產生 plan 模糊）

- [x] **A1 · §2「落地改為」code block 缺 stylesheet link**
  - 證據：spec §2 line 162-170 寫了 `<body>` 結構含 mount + script，沒列 `<link rel="stylesheet" href="styles.css">` / `wizard.css`
  - 現況 `viewer/wizard.html:7-8` 兩個 link 都在
  - 影響：plan task agent 照 spec §2 改 wizard.html 會把樣式 link 一併刪、wizard 頁裸樣 render
  - 修法：§2 code block 增加 `<head>` 段（含兩個 stylesheet link），或在描述加註「僅改 `<body>` 結構、`<head>` 不動」

- [x] **A2 · `--font-sans` / `--font-mono` 補入 styles.css :root 會改變既有 Viewer 字體**
  - 證據：spec §1.3 將兩 token 加進 styles.css :root（值含 `"Segoe UI",Arial,"Noto Sans TC","PingFang TC"...`）
  - 現況 `viewer/styles.css` 第 1420/1429/1556/1575/1624/1633/1643 行已有 7 處 `var(--font-sans, sans-serif)` / `var(--font-mono, monospace)` 用 fallback
  - 影響：補入 token 後 mindmap/legend/cards 等 7 處從系統字 sans-serif/monospace 切到 token 值，視覺 silent regression
  - 修法（建議走第 2 種，符合「不污染主 Viewer」原則）：
    1. 補入 token 並標為「故意視覺收斂」驗收項
    2. 把兩 token 限定 wizard.css 內、不放 styles.css :root；wizard 內 `.wizard-content { font-family: var(--font-sans); }` 局部 scope

- [x] **A3 · `run_analyze_pipeline` vs `PipelineOrchestrator.run` entry point 混用**
  - 證據：§5.1「`run_analyze_pipeline` 的 `progress_callback`」 vs §5.2 引用 `pipeline_orchestrator.py:60-66 _STEP_DEFS`（後者）
  - 兩者實際是不同函式：`analyze_pipeline.py:46 run_analyze_pipeline`（單版本分析）vs `pipeline_orchestrator.py:101 PipelineOrchestrator.run`（6 步 update）
  - 影響：plan task #1 不知道改哪個 callback；精靈 POST /api/analyze 與 modal POST /api/update 可能走不同管線
  - 修法：§5.1 加 entry-point 對照表，明確「精靈 analyze → `run_analyze_pipeline`；Viewer modal update → `PipelineOrchestrator.run`；兩條 callback 都要加 progress」（實際對應請 task #1 開工時 grep api_handlers 確認）

- [x] **A4 · §4.1 `STAGE.PAGE_ERROR = 4` 與設計原則 1「不可造假進度」矛盾**
  - 證據：§4.1 STAGE map 把 PAGE_ERROR 寫死 4；但 PAGE_ERROR 觸發來源含 STATUS_ERROR（`ui-wizard.js:37`，發生在 LOADING 階段）
  - 影響：初始載入失敗時 rail 顯示「分析中」+ 門開 80%，與真實情境嚴重不符
  - 修法（二選一）：
    1. transition 加 `errorOriginPage` 欄位，stage 從 origin 推回
    2. PAGE_ERROR 一律顯示 stage 0（不動門隱喻），spec 加註此為 known trade-off

- [x] **A5 · §5.3 `activePhaseIndex` 程式碼與接續敘述邏輯不一致**
  - 證據：§5.3 範例 function 只看 `currentStep`，但接續敘述要求「`bucket.steps` 全 `completed` → `.done`；含 `currentStep` 或某 step `status==='running'` → `.active`」
  - 影響：`currentStep === null`（step 之間）時 function 回 -1 無法分辨 done/pending；plan task #6 落地會卡
  - 修法：把 `activePhaseIndex` 拆成 `phaseStatus(bucket, steps, currentStep)`，回傳 `'done' | 'active' | 'pending'`；§5.3 範例與敘述對齊

- [x] **A6 · BACK transition 缺第 3 條 + update 路徑 PAGE_CONFIRM 未處理**
  - 證據：§4.3 只定義 `BACK_TO_ACTION` + `BACK_TO_SETUP`
    - analyze 路徑 PAGE_CONFIRM「上一步」應回 PAGE_LABEL，缺 `BACK_TO_LABEL`
    - update 路徑（`SELECT_ACTION update` 直跳 PAGE_CONFIRM）的 PAGE_CONFIRM「上一步」原型 `flow.js:190` 回 action，spec §4.2 ⓓ 未指明
  - 影響：plan task #7 落地會自行決策、行為不可預測
  - 修法（建議）：採通用化單一 action `{ type: 'BACK', target: 'PAGE_ACTION'|'PAGE_SETUP'|'PAGE_LABEL' }`；renderPage 依當前 page + state.action 決定 target

---

## B. Warning（會留下不確定性、但不立刻壞）

- [x] **B1 · `progress.current_file` 在 update 雙根模式下基準不明**
  - 證據：§5.1「`current_file` 是專案根的相對路徑（與 `Edge.from_node` 同一基準）」；但 `PipelineOrchestrator.run` 同時跑 `config.old_path` 和 `config.new_path` 兩個 root
  - 影響：前端 feed 顯示混雜 old/new 路徑、同名檔分不清
  - 修法：`progress` 加 `current_root: 'old'|'new'` 欄位；或前端 feed 顯示 `[old] xxx.py` / `[new] xxx.py` 前綴

- [x] **B2 · file-level progress 鏈未說明、task #1 估算可能嚴重低估**
  - 證據：§5.1 / §5.4 只說「callback 加結構化資料」；但 file-level work 在 NodeBuilder/AnalysisPipeline 內部，要把 `current_file` 打通需貫穿多層
  - 影響：plan task #1 可能只改 JobStore + handler、忽略 walker 端的鏈接線
  - 修法：§5.1 補實作鏈圖「NodeBuilder.scan → AnalysisPipeline → run_analyze_pipeline callback → JobStore.update_progress」；plan #1 拆 1a (ProgressReporter 抽象 + 鏈接線) + 1b (handler payload)

- [x] **B3 · §3.1 grep 規則僅覆蓋 `from`-起始、漏 `0%`-起始**
  - 證據：§3.1 驗收「`@keyframes ... { from {...} ... }`」；但 `flow.css:127 @keyframes plpulse{0%,100%{opacity:1;}50%{opacity:.35;}}` 用 `0%/100%`
  - 影響：當下不違反精神（從 1 起始）、規則未來抓不到 `0%` 起始的 regress
  - 修法：規則改為「任何 keyframes block 內 `opacity:\s*0` 命中為 0」

- [x] **B4 · door-light transition 違反「不可 opacity:0 起始」精神、未列例外**
  - 證據：`flow.css:69 .door-light{...opacity:0;transition:opacity .55s ease;}` 是門隱喻核心，門裡光從 0 淡入 .92
  - §3.1 只規範 @keyframes、沒提 transition；plan task #3 agent 可能誤刪
  - 影響：門光被弄壞、隱喻失效
  - 修法：§3.1 末段加「`.wizard-door-light` opacity:0 是門隱喻例外，由 `.lit` class 觸發切換；transition 不受此紀律」

---

## C. Suggestion（不影響正確性、只影響精準度）

- [x] **C1 · §1.3「14 個 token」實際 13 個**
  - 證據：terminal 3 + font 2 + radius 2 + rail 6 = 13
  - 修法：改 13

- [x] **C2 · 多處行號 off-by-N**
  - 證據對照：
    | spec 寫 | 實際 |
    |---|---|
    | `flow.css:8-21 :root` | line 7-22 |
    | `flow.css` 290 行 | 291 行 |
    | `flow.css:175-194 steplist` | phasebar 191-200、steplist 202-210 |
    | `flow.css:254-258 viewerIn` | line 253-260 |
    | `flow.css:55-104 rail` | line 55-100（rail-foot 99-100） |
    | `flow.js` 447 行 | 448 行 |
    | `wizard-flow.html` 26 行 | 27 行 |
    | `styles.css:846-867` 6 條 chips | 6 條規則範圍 846-870 |
  - 影響：plan task agent grep 找不到（off-by-1/2/3 級），落地慢但不壞
  - 修法（二選一）：行號全部修齊；或一次寫「行號為審查當下快照，實作以實際檔為準」

- [x] **C3 · §5.4「`pollJobStatus` callback」用詞不準**
  - 證據：`pollJobStatus` 是 `ui-modal.js:82`；精靈頁 `ui-wizard.js:368-393` 是 `startPolling` 內部匿名 setInterval async function
  - 影響：plan task agent 在精靈頁找 `pollJobStatus` 找不到
  - 修法：§5.4 改為「精靈頁 polling 回呼裡直接 append」

---

## D. 已驗證為對的（確認無誤、無須動）

- [x] PipelineOrchestrator progress 訊息格式 `[步驟 N/M] 正在執行：<英文短碼>...` 與 spec §5.2 假設一致（grep 確認 `pipeline_orchestrator.py:172/200/231/...`）
- [x] `job_store.py` `_RE_RUNNING` 抓 `<step_name>` 確為英文短碼（lazy + `\.{0,3}$` lookahead）
- [x] `handle_get_update_status` 函式名正確存在於 `api_handlers.py:333`
- [x] `ui-modal.js:33 renderPipelineProgress` 行號正確
- [x] `index.html:79-84 #pipeline-progress / #current-step / #steps-list` 結構正確
- [x] `wizard.html:7-8` 既有載入 styles.css + wizard.css（§7.2 共用區策略可行）
- [x] `wizard-css-units.test.js` 已存在於 FIX-2 階段（spec §9「擴充」前提成立）
- [x] `.onboarding-card`（FIX-4，`styles.css:1825`）/ `.not-analyzed-cmd`（FIX-3，`styles.css:1146`）/ `.empty-state`（FIX-5，`styles.css:704`）已 ship、可被 §6.1 / §6.2 直接引用
- [x] flow.css `screenIn`（106）/ `viewerIn`（255）/ `thresholdOut`（51）均不違反「不可 opacity:0 起始」紀律
- [x] flow.css `plIn`（133）違反規則 → §3.1 已處理改寫
- [x] spec §1.3 `--shadow-modal` 衝突描述正確（styles.css 0.15 vs flow.css 0.12）
- [x] spec §0.3 wizard-* 前綴策略：grep 確認 `.opt/.btn/.eyebrow/.field/.summary/.phasebar/.phase/.steplist/.sl-row/.prog-*/.pl-*/.transient/.bigspin/.agent-*/.astep/.mode-note/.rail/.content/.screen` 在 styles.css 全 0 命中
- [x] 新增 `BACK_*` transition 不破壞既有 reducer pure 性質
- [x] §11 與 Edge Noise / 疑義面板 / scope-aware edge 等其他工作確認零交集
- [x] `ui-wizard.js:118 createApi` export 存在、§2 落地版 import 可行

---

## E. 採納流程建議

1. 先就 A-C 各條打 `[x]`（採納）或留白（不採納 / 待議）
2. 若有「不採納」項，請補一句 reason 讓 spec patch agent 知道
3. 採納清單回拋後 → 跑一次 spec patch（建議 inline 改原 spec、不再產第三份檔；維持「收斂成單一 spec」原則）
4. patch 完再短 review 一次（針對改動本身），通過後即可進 writing-plans

> 預估 spec patch 工作量：A 段 6 條 ~20-30 分鐘改動 + 驗證；B 段 4 條 ~10 分鐘；C 段純文字 ~5 分鐘。
