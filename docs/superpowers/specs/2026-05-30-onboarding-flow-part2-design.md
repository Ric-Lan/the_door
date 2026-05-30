# Onboarding Flow Part 2 — Design Spec

> 把 Claude Design 產的「精靈 → Viewer 進場體驗」原型落地進 vanilla viewer。
> 此檔取代下列分散討論檔（全部已整合進來、可棄用）：
> - `frontend-onboarding-flow-spec-part2.md` / `…part2 (1).md`（前兩版 spec）
> - `frontend-onboarding-flow-spec-part2-audit.md`（第一輪審查）
> - `frontend-onboarding-flow-spec-part2-patch.md`（補丁清單）
>
> **基準：** main `c6f6f02`；Part 1 (FIX-1~5) 已 ship；Edge Noise (v1.4.6) 已 ship；原型已 commit 至 `docs/frontend-local-version-viewer/part2-prototype/`。

---

## 0 · 範圍與基準

### 0.1 與 Part 1 的關係

Part 1 已 ship 的 className，Part 2 **沿用不改**：

```
.wizard-card .wizard-subtitle .wizard-options .wizard-option-btn
.wizard-field .wizard-btn-primary .wizard-summary（dl>dt+dd）
.wizard-steps .wizard-step[data-step-status] .wizard-step-icon
.wizard-agent-params .wizard-btn-copy .wizard-error-box
```

Part 2 新增：
- 雙欄外殼（`.wizard-shell` + `.wizard-rail` + `.wizard-content`）
- 進度 phasebar / steplist / 即時 feed
- 入口模式說明條（`.wizard-mode-note`）
- 穿門轉場 + Viewer 淡入
- modal `ui-modal.js renderPipelineProgress` 改用同一 phasebar/steplist
- 後端 `progress.*` 欄位 + 前端消費
- `transition()` 新增 `BACK` action + `errorOriginPage` 欄位

### 0.2 不在範圍

- 疑義面板重做（spec 已 DEFER 多輪）
- 「有資料」落地版（原型只設計空專案 onboarding；有資料用戶直接走既有 Viewer，不另設計）
- 主 Viewer 內其他視覺改版（樹狀圖 / 心智圖 / 細節面板）

### 0.3 命名空間紀律

原型 `flow.css` 裸 class（`.opt`/`.btn`/`.eyebrow`/`.field`/`.summary`/`.phasebar`/`.phase`/`.steplist`/`.sl-row`/`.prog-*`/`.pl-*`/`.transient`/`.bigspin`/`.agent-*`/`.astep`/`.mode-note`/`.rail`/`.content`/`.screen`）落地時一律加 `wizard-` 前綴。已 grep 驗證 `styles.css` 全 0 命中、無當下衝突。

### 0.4 設計原則

1. **不可造假進度**：UI 任何進度元素（feed / phasebar / steplist / count）只能反映後端真實狀態。`flow.js startTicker()` 亂數資料禁搬。
2. **不污染主 Viewer**：精靈專屬樣式 → `wizard.css`；onboarding 落地樣式 → `styles.css`（與 FIX-4 同處）；shared progress 區（§7.2）→ `styles.css` 但用 `wizard-` 前綴。
3. **狀態機只在必要例外處動**：本 spec 動點為 (a) `BACK` 通用 action（§4.3）；(b) `errorOriginPage` 欄位（§4.1）。其餘 reducer / api / 輪詢全保留。
4. **px + 既有 token，圓角統一 6px**（沿用 FIX-2）。

### 0.5 視覺真實來源

原型已 commit：

```
docs/frontend-local-version-viewer/part2-prototype/
├── flow.css                (291 行，視覺值的權威)
├── flow.js                 (448 行，含 railHTML/screenHTML/viewerHTML 三個純字串模板)
├── wizard-flow.html        (27 行，shell 參考)
├── assets/                 (4 SVG：the-door-glyph/mark, mark-l1, mark-diff)
└── shots/                  (7 PNG：action/fresh/01-05 flow，驗收金標準)
```

落地時 plan task 用相對路徑引用具體行號（例：`flow.css:55-100 .wizard-rail 區段`）。本 spec 內出現的行號為審查當下快照，實作時以實際檔案為準（行號可能因 prototype 微調漂移 1-3 行）。`shots/` 是手動視覺驗收的對照基準，不改。

---

## 1 · 設計系統

### 1.1 版面結構：雙欄

```
.wizard-shell（display:flex，滿版）
├── .wizard-rail        (左 312px・門外暗面・深 teal)
│   ├── .wizard-rail-brand    門標 SVG + 「The Door / 門 · 啟動精靈」
│   ├── .wizard-door-wrap     會隨進度開啟的門 SVG
│   ├── .wizard-stepper       垂直 6 階段步驟（進度填充線）
│   └── .wizard-rail-foot     「CODE → FUNCTIONAL LANGUAGE」
└── .wizard-content     (右・門內明亮・白底)
    └── .wizard-screen       當前 page 內容（包住既有 .wizard-card）
```

### 1.2 階段映射

每個 `state.page` 對應 stage 0–5：

| stage | 名稱 | 對應 page |
|---|---|---|
| 0 | 選擇操作 | `PAGE_ACTION` / `LOADING` |
| 1 | 設定範圍 | `PAGE_SETUP` |
| 2 | 快照標籤 | `PAGE_LABEL` |
| 3 | 確認送出 | `PAGE_CONFIRM` |
| 4 | 分析中 | `SUBMITTING` / `PROGRESS`（`PAGE_ERROR` 不固定為 4，依 `errorOriginPage` 推回；見 §4.1） |
| 5 | 進入 Viewer | redirect 後（落地畫面） |

- 門開啟角度 = `-78deg × (stage/5)`；stage 5 時 `.wizard-door-light.lit` 全亮
- 步驟填充線高度 = `(stage/5) × 100%`
- 已過步驟 `.done`（✓ + 綠）；當前 `.active`（白圓 + 光暈）
- `update` 路徑 stage 直接 0→3（位置式 stepper 自動把 i<stage 標 `.done`，無特例邏輯）

### 1.3 Token 整合策略

`flow.css :root`（line 7-22）定義所有 token。落地分兩處補入（**注意：font tokens 不放 styles.css :root**——styles.css 已有 7 處 `var(--font-sans, sans-serif)` / `var(--font-mono, monospace)` 帶 fallback，補入會 silent regression 主 Viewer 字體）：

**A. 補進 `styles.css :root`，11 個：**

```css
/* 終端塊 */
--term-bg: #1e293b;
--term-fg: #e2e8f0;
--term-toolbar: #263238;
/* 圓角 */
--radius: 3px;        /* 終端塊頂列、小膠囊 */
--radius-card: 6px;   /* 卡片、選項按鈕、輸入框（= FIX-2 6px 字面量） */
/* 門外暗面 */
--rail-bg: #0a3b37;
--rail-bg-2: #072925;
--rail-line: rgba(217, 243, 239, .16);
--rail-text: #eafaf7;
--rail-muted: #7fb8b1;
--rail-dim: #4d827c;
```

**B. 補進 `wizard.css` 內 `.wizard-shell` scope，2 個：**

```css
.wizard-shell, .wizard-shell * {
  --font-sans: "Segoe UI", Arial, "Noto Sans TC", "PingFang TC", sans-serif;
  --font-mono: Consolas, "Courier New", monospace;
}
```

**值衝突裁決：**

| token | styles.css 現值 | flow.css 值 | 處置 |
|---|---|---|---|
| `--shadow-modal` | `0 8px 24px rgba(0,0,0,0.15)` | `0 8px 24px rgba(0,0,0,0.12)` | 保留 styles.css 現值（3% alpha 差人眼難辨；不動避免影響既有 modal） |

FIX-2 已 ship 的 `border-radius: 6px` 字面量不回頭改成 `var(--radius-card)`（等價）。

### 1.4 不沿用原型的決策（reference only）

- `flow.css` 內 `.opt`/`.field`/`.btn`/`.summary` 等已 ship 的 wizard-* 對等版，**忽略**（沿用 FIX-1 已 ship）
- `flow.css` 內 `.viewer`/`.v-top`/`.onboard*`（模擬 Viewer 頂列與 onboarding 卡）**忽略**（生產用真實 `index.html` topbar + Part 1 FIX-4 `.onboarding-card`）
- `flow.css` 內 `#stage`/`#frame`/`.chrome`/`#walk`/`#tweaks*` **忽略**（demo 外殼）
- `wizard-flow.html` 的 faux browser chrome **不保留**（生產已在瀏覽器，再加 chrome 視覺重複）

---

## 2 · wizard.html shell

現況（`docs/frontend-local-version-viewer/viewer/wizard.html`，完整檔）：
```html
<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>The Door — 啟動精靈</title>
  <link rel="stylesheet" href="styles.css">
  <link rel="stylesheet" href="wizard.css">
</head>
<body>
  <div class="wizard-root">
    <div id="wizard-mount"></div>
  </div>
  <script type="module">
    import { initWizard, createApi } from './js/ui-wizard.js';
    const container = document.getElementById('wizard-mount');
    const api = createApi();
    initWizard(container, api);
  </script>
</body>
</html>
```

落地改動範圍：**僅 `<body>` 結構**，`<head>` 完全不動（兩個 stylesheet link 保留）。`<body>` 改為：

```html
<body>
  <div id="wizard-mount"></div>
  <script type="module">
    import { initWizard, createApi } from './js/ui-wizard.js';
    const container = document.getElementById('wizard-mount');
    initWizard(container, createApi());
  </script>
</body>
```

`styles.css` 加上（在「Pipeline progress」段之前或檔尾共用區）：
```css
html, body { height: 100%; margin: 0; }
#wizard-mount { height: 100vh; }
```

不再需要 `.wizard-root` 的置中 flex（雙欄自己滿版）。

---

## 3 · wizard.css 新增區塊

從 `flow.css` 移植下列區塊到 `wizard.css`（全部加 `wizard-` 前綴、token 補齊已套用 §1.3）：

| 來源（`flow.css` 行） | 落地區塊 |
|---|---|
| `.wizard` / `.wizard.leaving` + `@keyframes thresholdOut`（line 49-53） | `.wizard-shell` / `.wizard-shell.leaving` + `@keyframes wizardThresholdOut` |
| `.rail` 及子項（line 55-100） | `.wizard-rail` / `.wizard-rail-brand` / `.wizard-door-*` / `.wizard-stepper` / `.wizard-step-bar` / `.wizard-rail-foot` |
| `.content` / `.screen` / `.screen-enter` + `@keyframes screenIn`（line 102-106） | `.wizard-content` / `.wizard-screen` / `.wizard-screen-enter` + `@keyframes wizardScreenIn` |
| `.eyebrow` / `.mode-note*`（line 108-118） | `.wizard-eyebrow` / `.wizard-mode-note` / `.wizard-mode-note .mn-badge` |
| `.wizard-btn-ghost`（新增，原型 `.btn-ghost` line 175-176） | 次要鈕（給「上一步」/「重試」/「取消」） |
| `.phasebar` / `.phase*` / `@keyframes indet`（line 191-200） + `.spin` + `@keyframes spin` / `.prog-note`（line 211-214） | `.wizard-phasebar` / `.wizard-phase.done\|.active\|.pending\|.failed`（`.failed` 配 `--removed-*`，原型無此狀態） / `@keyframes wizardIndet` / `.wizard-spin` / `@keyframes wizardSpin` / `.wizard-prog-note` |
| `.steplist` / `.sl-row*`（line 202-210） | `.wizard-steplist` / `.wizard-sl-row` / `.wizard-sl-row.done` / `.wizard-sl-row.active` / **`.wizard-sl-row.failed`（新增，配 `--removed-*`）** |
| `.prog-live` / `.pl-*` + `@keyframes plpulse` / **`@keyframes plIn`（須改）**（line 120-133） | `.wizard-prog-live` / `.wizard-pl-*` + `@keyframes wizardPlPulse` / `@keyframes wizardPlIn` |
| `.agent-why` / `.agent-steps` / `.astep*` / `.cmd*`（line 216-236） | `.wizard-agent-why` / `.wizard-agent-steps` / `.wizard-astep*`（終端塊本體沿用已 ship `.wizard-agent-params`） |
| `.transient` / `.bigspin`（line 238-242） | `.wizard-transient` / `.wizard-bigspin`（SUBMITTING / LOADING 用） |

### 3.1 動畫安全紀律

`flow.css` 大多遵守「不可 `opacity: 0` 起始」紀律（`screenIn` 只 translateX、`viewerIn` 只 scale、`thresholdOut` 是 `to opacity: 0` 不算起始；`plpulse` 從 1 起始）。**唯一違反者** `@keyframes plIn`（flow.css:133）即時 feed 行進入動畫：

```css
/* flow.css:133 違反 */
@keyframes plIn{from{opacity:0;transform:translateY(4px);}to{opacity:1;transform:translateY(0);}}
```

落地改寫為（只 translateY、無 opacity）：

```css
@keyframes wizardPlIn { from { transform: translateY(4px); } to { transform: translateY(0); } }
.wizard-prog-live .wizard-pl-line { animation: wizardPlIn .25s ease; }
```

**驗收：** `wizard.css` 與 `styles.css` 共用區內任何 `@keyframes` block（不論用 `from` / `0%` / 中間百分比）都不含 `opacity:\s*0` 起始。grep 規則：「scan 全部 `@keyframes` block 內文，命中 `opacity:\s*0` 必為 0」。

**Door-light 例外（transition，非 keyframe）：** `.wizard-door-light` 沿用原型 `opacity:0` 起始（由 `.lit` class 透過 transition 切到 `.92`），是門隱喻核心、不可拿掉。本紀律僅規範 `@keyframes`，不涵蓋 transition；plan task 落地時不可誤刪 `.wizard-door-light { opacity: 0; transition: opacity .55s ease; }` 這條規則。

---

## 4 · ui-wizard.js — renderPage 重構

### 4.1 雙欄外殼

`renderPage` 改為先建外殼，再把當前 page 內容塞進 `.wizard-screen`：

```js
// 階段映射
const STAGE = {
  LOADING: 0, PAGE_ACTION: 0,
  PAGE_SETUP: 1, PAGE_LABEL: 2, PAGE_CONFIRM: 3,
  SUBMITTING: 4, PROGRESS: 4,
  // PAGE_ERROR 故意不在表內，由 railStage() 用 errorOriginPage 推回
};
function railStage(state) {
  if (state.page === 'PAGE_ERROR') {
    // STATUS_ERROR 發生在 LOADING（stage 0）、SUBMIT_ERROR/POLL_FAIL 發生在 SUBMITTING/PROGRESS（stage 4）。
    // 若無 errorOriginPage 資訊則一律退回 0，避免設計原則 1「不可造假進度」被違反。
    return STAGE[state.errorOriginPage] ?? 0;
  }
  return STAGE[state.page] ?? 0;
}
```

**state 微調：** transition 進入 `PAGE_ERROR` 時補記 `errorOriginPage` 欄位（符合 §0.4 第 3 條「狀態機只在必要例外處動」）：

```js
case 'STATUS_ERROR':
  return { ...state, page: 'PAGE_ERROR', errorMessage: action.message, errorOriginPage: state.page };
case 'SUBMIT_ERROR':
  return { ...state, page: 'PAGE_ERROR', errorMessage: action.message, errorOriginPage: state.page };
case 'POLL_UPDATE':
  if (action.status === 'failed') {
    return { ...state, page: 'PAGE_ERROR', jobStatus: 'failed',
             errorMessage: action.errorMessage || '分析失敗', errorOriginPage: state.page };
  }
  /* 其餘分支不變 */
case 'POLL_FAIL':
  /* newCount >= 3 分支：retval 補 errorOriginPage: state.page */
```

`getInitialState()` 加 `errorOriginPage: null`。

renderPage 重構為先建外殼、再把當前 page 內容塞進 `.wizard-screen`：

```js
export function renderPage(container, state, dispatch, redirectFn, api) {
  container.innerHTML = '';
  const shell = document.createElement('div');
  shell.className = 'wizard-shell';

  // 左欄
  shell.insertAdjacentHTML('beforeend', wizardRailHTML(railStage(state), state.page === 'PROGRESS' && state.status === 'completed'));

  // 右欄
  const content = document.createElement('div');
  content.className = 'wizard-content';
  const screen = document.createElement('div');
  screen.className = 'wizard-screen wizard-screen-enter';
  screen.setAttribute('data-page', state.page);
  content.appendChild(screen);
  shell.appendChild(content);
  container.appendChild(shell);

  switch (state.page) { /* 各 case 內容塞進 screen */ }
}
```

`wizardRailHTML(stage, lit)` 從 `flow.js:107-134 railHTML(stage, lit, doorAnim)` 移植，class 名全部加前綴。

### 4.2 逐 page 內容對照

各 case 把內容塞進 `screen`（取代既有 `wrap`）。除了下列 ⓐ-ⓘ 標出的「新加」與「保留」項，其他**全部沿用 FIX-1 已 ship 的 markup 與事件綁定**。

**ⓐ PAGE_ACTION**
- 加 `.wizard-eyebrow`（"步驟 1 / 開始"）
- 加 `.wizard-mode-note.api` 或 `.wizard-mode-note.agent`（由 `state.hasApiKey` 決定）—— 入口即揭露執行模式
- `.wizard-options` 內按鈕沿用 FIX-1 的 `.wizard-option-btn`（strong + span 雙行），可選加 `<span class="wizard-opt-ico">{svg}</span>`
- 切換區沿用既有 `data-switch-input` / `data-switch-btn` 綁定
- 切換衝突變體沿用既有 `.wizard-error-box` + `data-switch-force-btn` / `data-switch-cancel-btn`

**ⓑ PAGE_SETUP / PAGE_LABEL**
- 沿用 `.wizard-field`（`<div class="wizard-field"><label></label><input></div>`）
- 主動作沿用 `.wizard-btn-primary`
- **新增「上一步」鈕**：`.wizard-btn-ghost`，綁 `dispatch({ type: 'BACK', target: <當前頁的上一頁> })`（PAGE_SETUP→PAGE_ACTION、PAGE_LABEL→PAGE_SETUP，見 §4.3 對照表）

**ⓒ LOADING**
- `.wizard-screen` 內放 `.wizard-transient`（`.wizard-bigspin` + 「載入中…」），與 SUBMITTING 同樣式
- rail stage 0

**ⓓ PAGE_CONFIRM**
- 沿用 `.wizard-summary`（`dl>dt+dd`：操作 / 排除目錄 / 標籤 / 執行模式 badge）
- 執行模式 badge 依 `state.hasApiKey`，與入口 `.wizard-mode-note` 樣式一致

**ⓔ SUBMITTING**
- `.wizard-transient` + `<div class="tl">送出中…</div>`

**ⓕ PROGRESS（API 模式）**
- 上方 `.wizard-phasebar`（見 §5.3 3-bucket 映射）
- 下方 `.wizard-steplist`，每 step 一個 `.wizard-sl-row[data-step-status]`
- 即時 feed `.wizard-prog-live` + `.wizard-pl-feed` + `.wizard-pl-count`（消費後端 `progress.*`，見 §5.1）

**ⓖ PROGRESS（Agent 模式，`!hasApiKey`）**
- 沿用 `.wizard-agent-params` 終端塊 + `.wizard-btn-copy`
- 「進入 Viewer」鈕 `.wizard-btn-primary`，綁 `redirectFn('/index.html')`（穿門轉場見 §6.2）

**ⓗ PAGE_ERROR**
- 沿用 `.wizard-error-box`（+ `state.errorMessage`）
- 重試 `.wizard-btn-ghost`、前往 Viewer `.wizard-btn-primary`

**ⓘ 重繪節奏**
- `POLL_UPDATE` 觸發 `dispatch → renderPage` → 整 `.wizard-shell` 重畫（rail stage 在 PROGRESS 固定 4，重畫無妨）
- 即時 feed `.wizard-pl-line` 追加由 polling 回呼（`ui-wizard.js:368-393 startPolling` 內的 setInterval async function）直接 `appendChild`、**不靠整頁重畫**（避免 stutter）

### 4.3 新增 BACK transition

`transition()` 新增**單一通用化 case**（僅改 `page`，其餘 state 保留）：

```js
case 'BACK':
  return { ...state, page: action.target };
```

`action.target` 由觸發按鈕決定，必為合法後退目標。三條 BACK 邊（連帶覆蓋 analyze 與 update 兩條路徑）：

| 觸發位置 | dispatch | 場景 |
|---|---|---|
| PAGE_SETUP「上一步」 | `{ type: 'BACK', target: 'PAGE_ACTION' }` | analyze 路徑 |
| PAGE_LABEL「上一步」 | `{ type: 'BACK', target: 'PAGE_SETUP' }` | analyze 路徑 |
| PAGE_CONFIRM「上一步」 | analyze 路徑：`{ type: 'BACK', target: 'PAGE_LABEL' }` <br> update 路徑：`{ type: 'BACK', target: 'PAGE_ACTION' }`（依 `state.action === 'update'` 判斷） | 兩條路徑 |

對應現有 `NEXT_FROM_SETUP` / `NEXT_FROM_LABEL` 形成 5 個轉場路徑（三條 BACK + 兩條 NEXT）。狀態機其餘部分（dispatch / api / 輪詢 / POLL_UPDATE / SUBMIT / SUBMIT_ERROR / JOB_STARTED / POLL_FAIL / SWITCH_* / SELECT_ACTION / STATUS_LOADED / STATUS_ERROR）完全不動（STATUS_ERROR / SUBMIT_ERROR / POLL_UPDATE failed / POLL_FAIL 補 `errorOriginPage` 欄位的微調已於 §4.1 列明）。

### 4.4 既有測試 `ui-wizard.test.js` 衝擊

FIX-1 加的 14 條 className 斷言（PAGE_ACTION / switch / PAGE_SETUP / PAGE_LABEL / PAGE_CONFIRM / PROGRESS / agent / PAGE_ERROR / wizard-card 包覆）**全部仍然有效**（同名 className 沿用）。新增雙欄外殼意味著選擇器要從 `container.querySelector('.wizard-card')` 改成 `container.querySelector('.wizard-shell .wizard-card')` —— 但 FIX-1 測試多數用 `container.querySelector('.wizard-card')`（不限定父層），實際上不需動。Plan task 落地時跑全測試確認。

---

## 5 · 進度資料契約（後端補欄位）

### 5.1 Entry point 對照表

精靈與 Viewer modal 走**不同**後端 entry point，task #1 兩條都要改：

| 觸發 | Handler | Entry function | 既有 progress 訊息 | 6-step 對齊 |
|---|---|---|---|---|
| 精靈 `POST /api/analyze`（**僅 API 模式**；agent 模式 `!hasApiKey` 不打此 API，由 `ui-wizard.js:352-360` 直接 `dispatch JOB_STARTED jobId=null`） | `handle_post_analyze`（`api_handlers.py:251`） | `run_analyze_pipeline`（`analyze_pipeline.py:46`） | 5 條 high-level 自由字串（line 112/115/155/171/336），不含 `[步驟 N/M]` 前綴 → `job_store.py` 正則目前抓不到 → 精靈 PROGRESS 頁 `steps[]` 一直為空 | **不對齊，須 adapter** |
| Viewer modal `POST /api/update` | `handle_post_update`（`api_handlers.py:1052`） | `PipelineOrchestrator().run`（`pipeline_orchestrator.py:101`） | 標準 `[步驟 N/6] 正在執行：<英文短碼>...` / `[步驟 N/6] ✓ <英文短碼>（耗時 X.Xs）` | 已對齊 |

**task #1 必做改動：**

1. **`handle_post_analyze` 套 progress adapter**——以 per-request closure 包住 job 引用、把 `run_analyze_pipeline` 5 條 high-level 訊息映射成 `[步驟 N/6]` 格式發給 `job.update_step`。注入形式：

```python
# handle_post_analyze 內，取代既有 progress_callback=job.update_step
def make_adapter(job):
    sent_skipped = False
    def adapter(msg: str) -> None:
        nonlocal sent_skipped
        if not sent_skipped:
            job.update_step("[步驟 1/6] ⊘ analyze_old（已跳過：首次分析無舊版）")
            job.update_step("[步驟 3/6] ⊘ diff（已跳過：首次分析無舊版）")
            job.update_step("[步驟 4/6] ⊘ scope_verify（已跳過：首次分析無 scope）")
            sent_skipped = True
        # 映射規則見下表
        ...
    return adapter

run_analyze_pipeline(self._project_root, config, progress_callback=make_adapter(job))
```

訊息映射表（左 = `run_analyze_pipeline` 真實發出，右 = adapter 轉發給 `job.update_step`）：

| `run_analyze_pipeline` 訊息（前綴匹配） | adapter 發出 | step 2 狀態 |
|---|---|---|
| `"Provider: ..."`（`analyze_pipeline.py:112`） | （吞掉，不轉發） | — |
| `"Extracting structure from ..."`（line 115） | `[步驟 2/6] 正在執行：analyze_new...` | running |
| `"Structure JSON persisted to ..."`（line 155） | （吞掉；step 2 仍 running，由 §5.1 第 4 條 file-level progress 撐住即時 feed） | running |
| `"Running batch analysis..."`（line 171） | （吞掉；同上，LLM 階段是最耗時段，依賴 file-level progress） | running |
| `"Snapshot saved: <sha>"`（line 336） | 連發 3 條：`[步驟 2/6] ✓ analyze_new（耗時 X.Xs）` + `[步驟 5/6] ✓ timeline（耗時 0.0s）` + `[步驟 6/6] ✓ report（耗時 0.0s）` | completed |

`run_analyze_pipeline` 本體不動、`job_store` 正則不動、`PipelineOrchestrator.run` 不動。

2. **`job_store.UpdateJob` 新增 `progress` 欄位**：`Optional[dict]`，預設 None；含 `files_done`/`files_total`/`current_file`/`current_root`。配 `update_progress(progress: dict)` 方法。

3. **`handle_get_update_status` payload 增加 `progress`**：

```json
{
  "job_id": "...",
  "status": "running",
  "current_step": "analyze_new",
  "steps": [
    { "step_name": "analyze_old", "status": "skipped", "duration_ms": null },
    { "step_name": "analyze_new", "status": "running", "duration_ms": null }
  ],
  "progress": {
    "files_done": 142,
    "files_total": 247,
    "current_file": "src/the_door/core/ui/api_handlers.py",
    "current_root": "new"
  }
}
```

4. **file-level progress 鏈接線**：file-level 訊息發生在 `ASTExtractor.extract` / `BatchReader` 內部 file loop，現有 `Callable[[str], None]` 無結構化欄位。新增 `ProgressReporter` 抽象貫穿：

```
ASTExtractor.extract (file walker)  ─┐
                                     ├──→ ProgressReporter ─→ run_analyze_pipeline / PipelineOrchestrator
BatchReader.run                     ─┘                                            ↓
                                                                          job.update_progress(dict)
                                                                                  ↓
                                                                       handle_get_update_status payload
```

plan task #1 拆 **1a**（ProgressReporter 抽象 + `ASTExtractor`/`BatchReader` 鏈接線 + adapter）與 **1b**（job_store 欄位 + handler payload + 整合測試）。

**契約紀律：**
- `progress` 是 optional：步驟之間或當前步驟未進 file-level work 時為 `null`
- `files_done` / `files_total` 是整數，`files_done ≤ files_total`
- `current_file` 是相對路徑，基準由 `current_root` 標示
- `current_root` 取值：`"new"` / `"old"`（精靈永遠 `"new"`；modal update 在 `analyze_new` 階段 `"new"`、`analyze_old` 階段 `"old"`）
- 當 `progress` 為 `null`，前端 `.wizard-prog-live` 整塊不顯示

### 5.2 真實 canonical step_name

`pipeline_orchestrator.py:60-66 _STEP_DEFS` 定義 6 步：

```
analyze_old · analyze_new · diff · scope_verify · timeline · report
```

精靈 analyze 路徑與 modal update 路徑經 §5.1 adapter 對齊後，**皆**以這 6 步呈現：

- **精靈 analyze**（首次分析無舊版）：`analyze_old`/`diff`/`scope_verify` 一律 `skipped`；`analyze_new` 對應 `run_analyze_pipeline` 的 AST 抽取 + LLM 批次分析整段；`timeline`/`report` 對應 snapshot 寫入後的收尾動作。
- **modal update**：6 步原樣（除非 `config.scope_name is None` 則 `scope_verify` 也 `skipped`；`config.skip_timeline` 則 `timeline` `skipped`）。

`POLL_UPDATE` 帶的 `currentStep` 是上述英文短碼，由 `job_store.py` 從 `[步驟 N/M] ✓ <step_name>` / `[步驟 N/M] 正在執行：<step_name>...` 訊息原樣解析（`job_store.py:20-23` 的四條正則）、**不翻譯**。

### 5.3 3-bucket phasebar + 完整 steplist

**phasebar（3 段視覺概念桶，動態映射）：**

```js
const PHASE_BUCKETS = [
  { id: 'explore', label: '探索結構', steps: ['analyze_old', 'analyze_new'] },
  { id: 'analyze', label: '比對與驗核', steps: ['diff', 'scope_verify'] },
  { id: 'report',  label: '產出快照',   steps: ['timeline', 'report'] },
];

// 回傳 'done' | 'active' | 'pending' | 'failed'
function phaseStatus(bucket, steps, currentStep) {
  const ownedSteps = steps.filter(s => bucket.steps.includes(s.step_name));
  if (ownedSteps.length === 0) return 'pending';
  // failed 優先：任一 step failed → 整個 bucket failed（不可顯示「完成」綠色，違反原則 1）
  if (ownedSteps.some(s => s.status === 'failed')) return 'failed';
  // active = 任一 step running，或 currentStep 屬於本 bucket
  const hasRunning = ownedSteps.some(s => s.status === 'running');
  const currentInBucket = currentStep && bucket.steps.includes(currentStep);
  if (hasRunning || currentInBucket) return 'active';
  // done = 所有對應 step 都已結束（completed / skipped）
  const allEnded = bucket.steps.every(name => {
    const s = ownedSteps.find(x => x.step_name === name);
    return s && (s.status === 'completed' || s.status === 'skipped');
  });
  return allEnded ? 'done' : 'pending';
}
```

phase 樣式：`.wizard-phase.done` / `.wizard-phase.active`（含 `@keyframes wizardIndet`）/ `.wizard-phase.pending` / `.wizard-phase.failed`（用 `--removed-*` 配色，新增於 §3 wizard.css 表 phase 區塊）。

**精靈 analyze 情境提示：** 因 `analyze_old`/`diff`/`scope_verify` 全 `skipped`，bucket `explore` 與 `analyze` 多半在 PROGRESS 頁載入時就 `.done`（除非 `analyze_new` 仍在跑），bucket `report` 在 snapshot 寫入後才 `.done`。這是預期視覺、非 bug。

**steplist（完整 6 步顯示，狀態真實）：**

每 step 對應一個 `.wizard-sl-row[data-step-status="<status>"]`，圖示由 `status` 推導：
- `completed` → ✓ 綠
- `failed` → ✗ 紅（用 `--removed-*`）
- `skipped` → ⊘ 灰
- `running` → 旋轉 spinner（`.wizard-spin`）
- 其他 / 未開始 → ○ 灰

顯示 label 透過映射表（render-time 翻譯，**不參與比對**）：

```js
const STEP_LABELS = {
  analyze_old:  '分析舊版',
  analyze_new:  '分析新版',
  diff:         '比對差異',
  scope_verify: '範圍驗核',
  timeline:     '時間軸',
  report:       '產生報告',
};
const labelFor = (step_name) => STEP_LABELS[step_name] ?? step_name;
```

**紀律：** 任何比對都用後端真實 `step_name`（英文短碼）。中文 label 只在 DOM render 那一刻使用。

### 5.4 即時 feed（消費 `progress.*`）

`.wizard-prog-live` 內容：

```
[●] 142 / 247  ▸ src/the_door/core/ui/api_handlers.py
[●] 142 / 247  ▸ src/the_door/core/ui/job_store.py
[●] 142 / 247  ▸ ...
```

由 polling 回呼（精靈頁的 `startPolling` 內部 setInterval async function，`ui-wizard.js:368-393`）直接 append（不靠整頁重畫）：

```js
function appendPlLine(filePath) {
  const feed = document.querySelector('.wizard-pl-feed');
  if (!feed) return;
  const line = document.createElement('div');
  line.className = 'wizard-pl-line';
  line.textContent = filePath;
  feed.appendChild(line);
  // 限制最多 N 行避免無限長
  while (feed.children.length > 20) feed.removeChild(feed.firstChild);
}
```

計數 `.wizard-pl-count` 顯示 `files_done / files_total`，每次 POLL 直接 setText（不 append）。

**嚴禁** 把 `flow.js:324/328 startTicker()` 的隨機資料搬進落地實作。

---

## 6 · 落地畫面 + 穿門轉場

### 6.1 落地 = index.html 的 onboarding（FIX-4）

精靈跑完 `redirectFn('/index.html')`。落地呈現是 Part 1 FIX-4 `.onboarding-card`，已在 main：
- 標號圓點 + 「歡迎使用 The Door」標題
- 從 `/api/status` 取 top 3 `next_actions`，每項用 `.not-analyzed-cmd` 終端塊顯示 cli_command

原型 `flow.css` 的 `.onboard*` 與 `.viewer` / `.v-top` **忽略**（已有真實 `index.html` topbar + FIX-4 卡）。

### 6.2 穿門轉場（跨頁淡出 + 淡入）

精靈頁送出 / 完成觸發 redirect 前：

```js
function redirectWithTransition(url) {
  const shell = document.querySelector('.wizard-shell');
  if (shell) shell.classList.add('leaving');
  // 等動畫結束才跳頁；fallback：超時 700ms 強制跳
  setTimeout(() => { window.location = url; }, 620);
}
```

`@keyframes wizardThresholdOut`（從 flow.css:51 移植，安全寫法）：

```css
.wizard-shell.leaving { animation: wizardThresholdOut .62s cubic-bezier(.7, 0, .3, 1) forwards; }
@keyframes wizardThresholdOut { to { transform: scale(1.06); opacity: 0; filter: brightness(1.25); } }
```

`thresholdOut` 是 `to opacity: 0`、不是 `from opacity: 0`，安全。

`index.html` 載入時對 `.onboarding-card` 套淡入（在 `styles.css` 新增）：

```css
.onboarding-card { animation: viewerIn .6s cubic-bezier(.2, .7, .2, 1) both; }
@keyframes viewerIn { from { transform: scale(.99); } to { transform: scale(1); } }
```

**紀律：** `viewerIn` 只 scale、無 `opacity: 0` 起始。`.onboarding-card` 基底 `opacity: 1`。

---

## 7 · Viewer 內「重新分析」進度 modal 一致化

**現況：** `index.html:79-84` 有 `#pipeline-progress` / `#current-step` / `#steps-list`，由 `ui-modal.js:33 renderPipelineProgress` 渲染，輪詢 `pollJobStatus(1.5s)`（`ui-modal.js:82` / `startPolling` 內 setInterval），樣式在 `viewer/styles.css:822-870`（`.pipeline-progress` / `.progress-header` / `.steps-list` flex-wrap chips、`.step-item` / `.step-completed` / `.step-failed` / `.step-skipped` / `.step-error` 共 6 條 chips 規則）。

**目標：** 套用 Part 2 phasebar + steplist 設計到 modal 進度區，全站「分析進度」長相一致。

### 7.1 改動範圍

1. **`ui-modal.js renderPipelineProgress(job)`** — DOM 結構改成 phasebar + steplist + 即時 feed（同 §5.3 / §5.4），消費同一份 `progress.*` 契約
2. **`viewer/styles.css:846-870`** — 移除 `.steps-list` / `.step-item` / `.step-completed` / `.step-failed` / `.step-skipped` / `.step-error` 6 條 chips 規則（已被 `.wizard-phasebar` / `.wizard-sl-row*` 取代）
3. **`viewer/index.html:79-84`** — `#pipeline-progress` 內 `#current-step` / `#steps-list` 容器保留，內容由 `renderPipelineProgress` 重畫
4. 共用 `wizard.css` 的 phasebar / steplist 規則 → 但 index.html 載入 `wizard.css` 會引入精靈頁專屬規則（rail 等）。**解法：** 把 phasebar + steplist + prog-live 區塊獨立為 `styles.css` 一段 `/* Progress (shared) */`，`wizard.css` 不重複定義；index.html 已載入 `styles.css`、`wizard.html` head 同樣已載 `styles.css`，兩邊都能拿到。

### 7.2 共用 CSS 切割

`styles.css` 新增一段 `/* Progress (shared) */`，含：
- `.wizard-phasebar` / `.wizard-phase.done|.active|.pending|.failed` / `@keyframes wizardIndet`
- `.wizard-steplist` / `.wizard-sl-row.done|.running|.pending|.failed|.skipped`
- `.wizard-prog-live` / `.wizard-pl-head|.pl-feed|.pl-line|.pl-count|.pl-dot` / `@keyframes wizardPlPulse` / `@keyframes wizardPlIn`
- `.wizard-spin` / `@keyframes wizardSpin`

`wizard.css` 不重複定義；`wizard.css` 只留精靈頁專屬（雙欄外殼、rail、`@keyframes wizardScreenIn`、mode-note、agent-* 包裝、transient、btn-ghost、§1.3 B 段 font tokens）。

共用區仍用 `wizard-` 前綴（不改名為 `.progress-*`，避免重寫所有規則）。

---

## 8 · 不引入新 CSS 變數政策

§1.3 新增 13 個 token（11 進 `styles.css :root`，2 進 `wizard.css` scope）已足以表達整個 Part 2。**不新增 `--fs-*`**、**不重定義既有 token**（如 `--shadow` / `--text` / `--accent`）。

---

## 9 · 驗收（手動 + 自動）

**自動（測試）：**
- 既有 `tests/ui-wizard.test.js` 全綠（FIX-1 加的 className 斷言不退步）
- 新增 `tests/wizard-shell.test.js`：雙欄結構、rail stage、stepper、mode-note 依 hasApiKey
- 新增 `tests/wizard-phasebar.test.js`：`phaseStatus(bucket, steps, currentStep)` 純函式對 4 種回傳值（`done`/`active`/`pending`/`failed`）映射、首次分析 skipped → done 處理、單一 step `failed` → 整 bucket failed
- 新增 `tests/wizard-progress-feed.test.js`：`appendPlLine` 限長、`null progress` 隱藏 feed、計數更新
- 新增 `tests/wizard-back-action.test.js`：通用化 `BACK` transition 對三個 target（PAGE_ACTION/PAGE_SETUP/PAGE_LABEL）純改 page、保留其他 state；額外覆蓋 update 路徑 PAGE_CONFIRM→PAGE_ACTION
- 新增 `tests/wizard-error-origin.test.js`：STATUS_ERROR / SUBMIT_ERROR / POLL_UPDATE failed / POLL_FAIL 進入 PAGE_ERROR 時，`errorOriginPage` 正確記錄為前一頁；`railStage()` 對 PAGE_ERROR 依 `errorOriginPage` 推回正確 stage（STATUS_ERROR→0、SUBMIT_ERROR from PAGE_CONFIRM→3、POLL_FAIL from PROGRESS→4）
- 修改 `tests/ui-modal.test.js`：`renderPipelineProgress` 用新 phasebar/steplist 結構
- 新增 `tests/wizard-css-units.test.js` 擴充（已存在於 FIX-2）：增加「無 `opacity: 0` 起始於 @keyframes」靜態檢查
- 100% coverage 維持

**手動（對照 `part2-prototype/shots/`）：**
- 精靈每頁雙欄；rail 門隨 stage 開啟、stepper 填充線高度與當前 step 高亮正確（對照 `01-flow.png` ~ `05-flow.png`）
- PAGE_ACTION 標題下 `.wizard-mode-note` 依 hasApiKey 顯示 API (teal) / Agent (琥珀)（對照 `action.png`）
- PAGE_CONFIRM badge 與入口 mode-note 一致
- PROGRESS：phasebar 3 段、steplist 完整 6 步、即時 feed 顯示真實 `current_file`（後端契約啟用後）
- 後端 `progress` 為 null 時 `.wizard-prog-live` 不出現（不偽造）
- Agent 模式：`.wizard-agent-params` 終端塊 + 可運作複製鈕
- 送出 → 完成 → redirect：`.wizard-shell.leaving` 淡出 + `.onboarding-card` 淡入（對照 `fresh.png`）
- Viewer modal 重新分析：與精靈 PROGRESS 同樣 phasebar + steplist 視覺
- scan `wizard.css` + `styles.css` 共用區所有 `@keyframes` block，內文命中 `opacity:\s*0` 應為 0（含 `from` / `0%` / 中間百分比；door-light transition 例外，不在 @keyframes 內）
- `wizard.css` 內 grep `[0-9]rem` 命中應為 0（沿用 FIX-2）

---

## 10 · Plan 拆分建議（writing-plans 接力時參考）

預期 plan 約 10-11 task，由低風險 / 純資產 / 純樣式 → 高風險 / 觸後端 排序：

1. **後端 `progress` 契約**（拆 1a + 1b 兩個 sub-task，見 §5.1）：
   - **1a**：ProgressReporter 抽象 + `ASTExtractor.extract` / `BatchReader` 內部 file-loop 鏈接線 + `handle_post_analyze` 套 adapter（映射 `run_analyze_pipeline` 訊息為 `[步驟 N/6]` 格式）
   - **1b**：`job_store.UpdateJob.progress` 欄位 + `update_progress()` 方法 + `handle_get_update_status` payload 補 `progress` + 對應整合測試
2. **CSS 共用進度區** — `styles.css` 新增 phasebar/steplist/prog-live + tokens（§1.3 A 段共 11 個進 `:root`；font tokens B 段 2 個進 wizard.css）
3. **CSS 雙欄外殼 + rail** — `wizard.css` 新增 `.wizard-shell` / `.wizard-rail*` / `.wizard-content` / `.wizard-screen` + `wizardScreenIn` 動畫 + B 段 font tokens 注入 `.wizard-shell` scope（`plIn` 已在 task #2 共用區處理）
4. **renderPage 雙欄重構** — `ui-wizard.js` 加外殼 + `wizardRailHTML` 移植 + `errorOriginPage` state 欄位（§4.1）；FIX-1 測試保持綠
5. **PAGE_ACTION mode-note + PAGE_CONFIRM badge** + 切換衝突外觀微調
6. **PROGRESS phasebar + steplist + 即時 feed**（消費 progress.*，phaseStatus 純函式見 §5.3）
7. **通用化 BACK transition + 上一步鈕**（單一 `{ type: 'BACK', target }` action，三個觸發位置見 §4.3）
8. **`ui-modal.js renderPipelineProgress` 改用新設計 + `viewer/styles.css:846-870` 6 條 chips 規則移除**
9. **跨頁穿門轉場**（`.wizard-shell.leaving` + `.onboarding-card` viewerIn）
10. **CHANGELOG v1.4.7 + 雙語 README core capabilities + 手動視覺驗收（對照 shots/）**

依賴：1a 必須最早（產出 `[步驟 N/6]` 訊息流是其餘消費基礎）；1b 與 2 / 3 可並行；4 依 3；5、6 依 4；6 同時依 1b（消費 progress.*）；7 與 4-6 並行；8 依 2、6（與 1b 消費同一 payload）；9 末段；10 最後。

---

## 11 · 來源檔對應（已 commit 至 repo）

| 來源 | 行 / 區段 | 落地處 |
|---|---|---|
| `flow.css:7-22` `:root` | token 定義 | §1.3 整合策略 |
| `flow.css:49-53` thresholdOut | 穿門淡出 | §6.2 |
| `flow.css:55-100` rail | 左欄門外 | §3 / §4.1 |
| `flow.css:102-106` content + screen + screenIn | 右欄門內 + 進場動畫 | §3 / §4.1 |
| `flow.css:120-133` prog-live + plIn | 即時 feed（plIn 須改寫） | §3.1 / §5.4 |
| `flow.css:191-200` phasebar + indet | phasebar | §5.3 |
| `flow.css:202-210` steplist | steplist | §5.3 / §7.2 |
| `flow.css:253-260` viewer + viewerIn | 落地淡入 | §6.2 |
| `flow.js:107-134` railHTML | rail 模板 | §4.1 |
| `flow.js:137-244` screenHTML | 各頁 markup | §4.2 |
| `flow.js:246-260` viewerHTML | 落地版 | 棄用，落地用 FIX-4 |
| `flow.js:328` startTicker（呼叫處 line 324） | demo 假資料 | 棄用（§5.4 嚴禁） |
| `wizard-flow.html`（27 行） | shell | §2（chrome 不保留） |
| `shots/*.png` | 視覺驗收基準 | §9 |
| `assets/*.svg` | 品牌 / 階段 icon | §1.1 rail-brand / §5.3 phase ico |
