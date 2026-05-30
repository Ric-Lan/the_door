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

Part 1（5 commits b8bbc33 → abf7c55）已把 `wizard.css` 222 行死碼接上線。Part 2 **站在 Part 1 之上做增量**，**不重寫、不取代**它們。

**已在 main 可直接沿用的 className**（FIX-1 / FIX-2 產出，6px 圓角、px 制）：

```
.wizard-card .wizard-subtitle .wizard-options .wizard-option-btn
.wizard-field .wizard-btn-primary .wizard-summary（dl>dt+dd）
.wizard-steps .wizard-step[data-step-status] .wizard-step-icon
.wizard-agent-params .wizard-btn-copy .wizard-error-box
```

**Part 2 新增**：
- 雙欄外殼（`.wizard-shell` + `.wizard-rail` 門隱喻 + `.wizard-content`）
- 進度 phasebar / steplist / 即時 feed
- 入口模式說明條（`.wizard-mode-note`）
- 穿門轉場 + Viewer 淡入
- 全站「分析進度」設計統一（套到既有 `ui-modal.js` 重新分析 modal）
- 後端 `progress.*` 欄位 + 對應前端消費
- `transition()` 新增 BACK action（唯一例外動到狀態機）

### 0.2 不在範圍

- 疑義面板重做（spec 已 DEFER 多輪）
- 「有資料」落地版（原型只設計空專案 onboarding；有資料用戶直接走既有 Viewer，不另設計）
- 主 Viewer 內其他視覺改版（樹狀圖 / 心智圖 / 細節面板）

### 0.3 命名空間紀律

精靈頁專屬規則統一 **`wizard-` 前綴**。原型 `flow.css` 用的裸 class（`.opt`/`.btn`/`.eyebrow`/`.field`/`.summary`/`.phasebar`/`.phase`/`.steplist`/`.sl-row`/`.prog-*`/`.pl-*`/`.transient`/`.bigspin`/`.agent-*`/`.astep`/`.mode-note`/`.rail`/`.content`/`.screen`）落地時一律加 `wizard-` 前綴。已 grep 驗證這些裸 class 在 `styles.css` 全 0 命中，加前綴是預防主 Viewer 未來引入同名造成污染，非當下衝突修補。

### 0.4 設計原則

1. **不可造假進度。** 即時 feed 只能顯示後端真實回傳資料。原型 `flow.js` 的 `startTicker()`（亂數計數 + 輪播假檔名）是 demo 裝飾，**嚴禁原樣搬**。
2. **不污染主 Viewer。** 所有新樣式進 `wizard.css`，用 `wizard-` 前綴；落地畫面的 onboarding 樣式進 `styles.css`（與 FIX-4 同處）。
3. **狀態機只在唯一例外處動：** 新增 `BACK_TO_ACTION` / `BACK_TO_SETUP` 兩個 transition action 支援「上一步」（其餘 dispatch / api / 輪詢全保留）。
4. **px + 既有 token，圓角統一 6px。** 沿用 FIX-2 慣例。

### 0.5 視覺真實來源

原型已 commit：

```
docs/frontend-local-version-viewer/part2-prototype/
├── flow.css                (290 行，視覺值的權威)
├── flow.js                 (447 行，含 railHTML/screenHTML/viewerHTML 三個純字串模板)
├── wizard-flow.html        (26 行，shell 參考)
├── assets/                 (4 SVG：the-door-glyph/mark, mark-l1, mark-diff)
└── shots/                  (7 PNG：action/fresh/01-05 flow，驗收金標準)
```

落地時 plan task 用相對路徑引用具體行號（例：`flow.css:50-105 .wizard-rail 區段`）。`shots/` 是手動視覺驗收的對照基準，不改。

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

隱喻：左欄「門外」暗面、右欄「門內」明亮，使用者由暗走向亮，最後穿門進 Viewer。

### 1.2 門隱喻 + 階段映射

每個 `state.page` 對應 stage 0–5：

| stage | 名稱 | 對應 page |
|---|---|---|
| 0 | 選擇操作 | `PAGE_ACTION` / `LOADING` |
| 1 | 設定範圍 | `PAGE_SETUP` |
| 2 | 快照標籤 | `PAGE_LABEL` |
| 3 | 確認送出 | `PAGE_CONFIRM` |
| 4 | 分析中 | `SUBMITTING` / `PROGRESS` / `PAGE_ERROR` |
| 5 | 進入 Viewer | redirect 後（落地畫面） |

- 門開啟角度 = `-78deg × (stage/5)`；stage 5 時 `.wizard-door-light.lit` 全亮
- 步驟填充線高度 = `(stage/5) × 100%`
- 已過步驟 `.done`（✓ + 綠）；當前 `.active`（白圓 + 光暈）
- `update` 路徑 stage 直接 0→3（位置式 stepper 自動把 i<stage 標 `.done`，無特例邏輯）

### 1.3 Token 整合策略

`flow.css:8-21` 自帶 `:root`，定義了所有需要的 token。`styles.css :root` 大部分已有同值；策略：**把 `flow.css :root` 缺漏的 token 補進 `styles.css :root`，跳過已存在且同值的。**

**需新增到 `styles.css :root` 的 token（共 14 個）：**

```css
/* 終端塊（既有 .not-analyzed-cmd 用 hardcoded，現在收為 token） */
--term-bg: #1e293b;
--term-fg: #e2e8f0;
--term-toolbar: #263238;

/* 字體 */
--font-sans: "Segoe UI", Arial, "Noto Sans TC", "PingFang TC", sans-serif;
--font-mono: Consolas, "Courier New", monospace;

/* 圓角（與 FIX-2 慣例並存，新規則優先用 token 表意） */
--radius: 3px;        /* 小元件如終端塊頂列、小膠囊 */
--radius-card: 6px;   /* 卡片、選項按鈕、輸入框，等於 FIX-2 已 ship 的 6px */

/* 門外暗面 */
--rail-bg: #0a3b37;
--rail-bg-2: #072925;
--rail-line: rgba(217, 243, 239, .16);
--rail-text: #eafaf7;
--rail-muted: #7fb8b1;
--rail-dim: #4d827c;
```

**值衝突（人工裁決）：**

| token | styles.css 現值 | flow.css 值 | 處置 |
|---|---|---|---|
| `--shadow-modal` | `0 8px 24px rgba(0,0,0,0.15)` | `0 8px 24px rgba(0,0,0,0.12)` | **保留 styles.css 現值**（既有元件依此值繪製，改動會微微影響主 Viewer modal 陰影深度；3% alpha 差人眼難辨） |

**FIX-2 圓角紀律共存：** Part 1 FIX-2 已把 `wizard.css` 內 `border-radius` 全部收成 `6px` 字面量。Part 2 新規則可選用 `var(--radius-card)` 或 `6px` 字面量，二者效果等價；既有 FIX-2 字面量**不需回頭改**（避免無價值 churn）。

### 1.4 不沿用原型的決策（reference only）

- `flow.css` 內 `.opt`/`.field`/`.btn`/`.summary` 等已 ship 的 wizard-* 對等版，**忽略**（沿用 FIX-1 已 ship）
- `flow.css` 內 `.viewer`/`.v-top`/`.onboard*`（模擬 Viewer 頂列與 onboarding 卡）**忽略**（生產用真實 `index.html` topbar + Part 1 FIX-4 `.onboarding-card`）
- `flow.css` 內 `#stage`/`#frame`/`.chrome`/`#walk`/`#tweaks*` **忽略**（demo 外殼）
- `wizard-flow.html` 的 faux browser chrome **不保留**（生產已在瀏覽器，再加 chrome 視覺重複）

---

## 2 · wizard.html shell

現況：
```html
<div class="wizard-root">
  <div id="wizard-mount"></div>
</div>
```

落地改為：
```html
<body>
  <div id="wizard-mount"></div>
  <script type="module">
    import { initWizard, createApi } from './js/ui-wizard.js';
    initWizard(document.getElementById('wizard-mount'), createApi());
  </script>
</body>
```

加上：
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
| `.rail` 及子項（line 55-104） | `.wizard-rail` / `.wizard-rail-brand` / `.wizard-door-*` / `.wizard-stepper` / `.wizard-step-bar` / `.wizard-rail-foot` |
| `.content` / `.screen` / `.screen-enter` + `@keyframes screenIn`（line 105-107） | `.wizard-content` / `.wizard-screen` / `.wizard-screen-enter` + `@keyframes wizardScreenIn` |
| `.eyebrow` / `.mode-note*`（line 108-…） | `.wizard-eyebrow` / `.wizard-mode-note` / `.wizard-mode-note .mn-badge` |
| `.wizard-btn-ghost`（新增，原型 `.btn-ghost`） | 次要鈕（給「上一步」/「重試」/「取消」） |
| `.phasebar` / `.phase*` / `@keyframes indet` / `.spin` + `@keyframes spin` / `.prog-note`（line 195-214） | `.wizard-phasebar` / `.wizard-phase*` / `@keyframes wizardIndet` / `.wizard-spin` / `@keyframes wizardSpin` / `.wizard-prog-note` |
| `.steplist` / `.sl-row*`（line ~175-194） | `.wizard-steplist` / `.wizard-sl-row` / `.wizard-sl-row.done` / `.wizard-sl-row.active` / **`.wizard-sl-row.failed`（新增，配 `--removed-*`）** |
| `.prog-live` / `.pl-*` + `@keyframes plpulse` / **`@keyframes plIn`（須改）**（line 120-133） | `.wizard-prog-live` / `.wizard-pl-*` + `@keyframes wizardPlPulse` / `@keyframes wizardPlIn` |
| `.agent-why` / `.agent-steps` / `.astep*`（line 216-…） | `.wizard-agent-why` / `.wizard-agent-steps` / `.wizard-astep*`（終端塊本體沿用已 ship `.wizard-agent-params`） |
| `.transient` / `.bigspin`（line ~) | `.wizard-transient` / `.wizard-bigspin`（SUBMITTING / LOADING 用） |

### 3.1 動畫安全紀律

`flow.css` 大多遵守「不可 `opacity: 0` 起始」紀律（`screenIn` 只 translateX、`viewerIn` 只 scale、`thresholdOut` 是 `to opacity: 0` 不算起始）。**唯一違反者** `@keyframes plIn`（flow.css:133）即時 feed 行進入動畫：

```css
/* flow.css:133 違反 */
@keyframes plIn{from{opacity:0;transform:translateY(4px);}to{opacity:1;transform:translateY(0);}}
```

落地改寫為（只 translateY、無 opacity）：

```css
@keyframes wizardPlIn { from { transform: translateY(4px); } to { transform: translateY(0); } }
.wizard-prog-live .wizard-pl-line { animation: wizardPlIn .25s ease; }
```

**驗收：** `wizard.css` 內任何 `@keyframes ... { from {...} ... }` 都不含 `opacity: 0` 起始。

---

## 4 · ui-wizard.js — renderPage 重構

### 4.1 雙欄外殼

`renderPage` 改為先建外殼，再把當前 page 內容塞進 `.wizard-screen`：

```js
// 階段映射
const STAGE = {
  LOADING: 0, PAGE_ACTION: 0,
  PAGE_SETUP: 1, PAGE_LABEL: 2, PAGE_CONFIRM: 3,
  SUBMITTING: 4, PROGRESS: 4, PAGE_ERROR: 4,
};
const railStage = (state) => STAGE[state.page] ?? 0;

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

`wizardRailHTML(stage, lit)` 從 `flow.js:107-136 railHTML(stage, lit, doorAnim)` 移植，class 名全部加前綴。

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
- **新增「上一步」鈕**：`.wizard-btn-ghost`，綁 `dispatch({ type: 'BACK_TO_ACTION' })` 或 `'BACK_TO_SETUP'`

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
- 即時 feed `.wizard-pl-line` 追加由 `pollJobStatus` callback 直接 `appendChild`、**不靠整頁重畫**（避免 stutter）

### 4.3 新增 BACK transition

`transition()` 新增兩 case（僅改 `page`，其餘 state 保留）：

```js
case 'BACK_TO_ACTION':  return { ...state, page: 'PAGE_ACTION' };
case 'BACK_TO_SETUP':   return { ...state, page: 'PAGE_SETUP' };
```

對應現有 `NEXT_FROM_SETUP` / `NEXT_FROM_LABEL` 形成 4 個轉場 action。狀態機其餘部分（dispatch / api / 輪詢 / POLL_UPDATE / SUBMIT / SUBMIT_ERROR / JOB_STARTED / POLL_FAIL / SWITCH_* / SELECT_ACTION / STATUS_LOADED / STATUS_ERROR）完全不動。

### 4.4 既有測試 `ui-wizard.test.js` 衝擊

FIX-1 加的 14 條 className 斷言（PAGE_ACTION / switch / PAGE_SETUP / PAGE_LABEL / PAGE_CONFIRM / PROGRESS / agent / PAGE_ERROR / wizard-card 包覆）**全部仍然有效**（同名 className 沿用）。新增雙欄外殼意味著選擇器要從 `container.querySelector('.wizard-card')` 改成 `container.querySelector('.wizard-shell .wizard-card')` —— 但 FIX-1 測試多數用 `container.querySelector('.wizard-card')`（不限定父層），實際上不需動。Plan task 落地時跑全測試確認。

---

## 5 · 進度資料契約（後端補欄位）

### 5.1 後端契約（v1.4.7 新增）

`run_analyze_pipeline` 的 `progress_callback` 增加結構化資訊，`job_store.JobEntry` 新增 `progress` 欄位，`handle_get_update_status` payload 增加 `progress`：

```json
{
  "job_id": "...",
  "status": "running",
  "current_step": "analyze_new",
  "steps": [
    { "step_name": "analyze_new", "status": "running", "duration_ms": null },
    ...
  ],
  "progress": {
    "files_done": 142,
    "files_total": 247,
    "current_file": "src/the_door/core/ui/api_handlers.py"
  }
}
```

**契約紀律：**
- `progress` 是 optional：steps 之間或當前 step 未進入 file-level work 時可為 `null`
- `files_done` / `files_total` 是整數，`files_done ≤ files_total`
- `current_file` 是專案根的相對路徑（與 `Edge.from_node` 同一基準）
- 當 `progress` 為 `null` 時前端 `.wizard-prog-live` 整塊不顯示（不偽造）

### 5.2 真實 canonical step_name

`pipeline_orchestrator.py:60-66 _STEP_DEFS` 定義 6 步：

```
analyze_old · analyze_new · diff · scope_verify · timeline · report
```

首次分析（精靈 `analyze` 路徑）只跑 `analyze_new` + 後續產出（`scope_verify`/`timeline`/`report`），`analyze_old`/`diff` 自動標 `skipped`。

`POLL_UPDATE` 帶的 `currentStep` 是上述英文短碼，由 `job_store.py` 從 `[步驟 N/M] ✓ <step_name>` 訊息原樣解析、**不翻譯**。

### 5.3 3-bucket phasebar + 完整 steplist

**phasebar（3 段視覺概念桶，動態映射）：**

```js
const PHASE_BUCKETS = [
  { id: 'explore', label: '探索結構', steps: ['analyze_old', 'analyze_new'] },
  { id: 'analyze', label: '比對與驗核', steps: ['diff', 'scope_verify'] },
  { id: 'report',  label: '產出快照',   steps: ['timeline', 'report'] },
];

function activePhaseIndex(currentStep) {
  return PHASE_BUCKETS.findIndex(b => b.steps.includes(currentStep));
}
```

phase 樣式：`.wizard-phase.done` / `.wizard-phase.active`（含 `@keyframes wizardIndet` 動畫）/ `.wizard-phase.pending`。`bucket.steps` 全 `completed` → `.done`；含 `currentStep` 或某 step `status==='running'` → `.active`；否則 `pending`。

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

由 `pollJobStatus` callback 直接 append（不靠整頁重畫）：

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

**現況：** `index.html:79-84` 有 `#pipeline-progress` / `#current-step` / `#steps-list`，由 `ui-modal.js:33 renderPipelineProgress` 渲染，輪詢 `fetchJobStatus(1.5s)`，樣式在 `styles.css:846-867`（`.steps-list` flex-wrap chips、`.step-item` / `.step-completed` / `.step-failed` / `.step-skipped` / `.step-error`）。

**目標：** 套用 Part 2 phasebar + steplist 設計到 modal 進度區，全站「分析進度」長相一致。

### 7.1 改動範圍

1. **`ui-modal.js renderPipelineProgress(job)`** — DOM 結構改成 phasebar + steplist + 即時 feed（同 §5.3 / §5.4），消費同一份 `progress.*` 契約
2. **`styles.css:846-867`** — 移除 `.steps-list` / `.step-item` / `.step-completed` / `.step-failed` / `.step-skipped` / `.step-error` 6 條 chips 規則（已被 `.wizard-phasebar` / `.wizard-sl-row*` 取代）
3. **`index.html:79-84`** — `#pipeline-progress` 內 `#current-step` / `#steps-list` 容器保留，內容由 `renderPipelineProgress` 重畫
4. 共用 `wizard.css` 的 phasebar / steplist 規則 → 但 index.html 載入 `wizard.css` 會引入精靈頁專屬規則（rail 等）。**解法：** 把 phasebar + steplist + prog-live 區塊獨立為 `progress.css`（或 `styles.css` 一段 `/* Progress (shared) */`），`wizard.css` 與 index.html 都載入。

### 7.2 共用 CSS 切割

新增 `styles.css` 內一段「共用進度樣式」區，含：
- `.wizard-phasebar` / `.wizard-phase*` / `@keyframes wizardIndet`
- `.wizard-steplist` / `.wizard-sl-row*`（含 failed / skipped 樣式）
- `.wizard-prog-live` / `.wizard-pl-*` / `@keyframes wizardPlPulse` / `@keyframes wizardPlIn`
- `.wizard-spin` / `@keyframes wizardSpin`

`wizard.css` 不重複定義這些。`wizard.css` 內留下精靈頁專屬規則（雙欄外殼、rail、screen 動畫、mode-note、agent-* 包裝、transient、btn-ghost）。

**命名上限：** 共用區的 class 仍用 `wizard-` 前綴（雖然會在 index.html 出現）—— 名稱代表「源自精靈設計系統」而非「僅精靈使用」，比改名 `.progress-*` 並重寫所有規則划算。

---

## 8 · 不引入新 CSS 變數政策

§1.3 新增 14 個 token 已足以表達整個 Part 2。**不再新增 `--fs-*`**（字級系統屬未來工作）、**不重定義已存在 token**（如 `--shadow` / `--text` / `--accent`）。

---

## 9 · 驗收（手動 + 自動）

**自動（測試）：**
- 既有 `tests/ui-wizard.test.js` 全綠（FIX-1 加的 className 斷言不退步）
- 新增 `tests/wizard-shell.test.js`：雙欄結構、rail stage、stepper、mode-note 依 hasApiKey
- 新增 `tests/wizard-phasebar.test.js`：3-bucket activePhaseIndex 邏輯、`completed`/`running`/`pending` 狀態映射、首次分析 skipped 處理
- 新增 `tests/wizard-progress-feed.test.js`：`appendPlLine` 限長、`null progress` 隱藏 feed、計數更新
- 新增 `tests/wizard-back-action.test.js`：`BACK_TO_ACTION` / `BACK_TO_SETUP` transition 純改 page、保留其他 state
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
- `wizard.css` 內 grep `opacity:\s*0` 在 `@keyframes ... { from {...} ... }` 命中應為 0
- `wizard.css` 內 grep `[0-9]rem` 命中應為 0（沿用 FIX-2）

---

## 10 · Plan 拆分建議（writing-plans 接力時參考）

預期 plan 約 8-10 task，由低風險 / 純資產 / 純樣式 → 高風險 / 觸後端 排序：

1. **後端 `progress` 契約** — `analyze_pipeline` callback 加結構化資料、`job_store` 新欄位、`handle_get_update_status` payload；新整合測試
2. **CSS 共用進度區** — `styles.css` 新增 phasebar/steplist/prog-live + tokens（§1.3 + §7.2 切割）
3. **CSS 雙欄外殼 + rail** — `wizard.css` 新增 `.wizard-shell` / `.wizard-rail*` / `.wizard-content` / `.wizard-screen` + `wizardScreenIn` 動畫（`plIn` 已在 task #2 共用區處理）
4. **renderPage 雙欄重構** — `ui-wizard.js` 加外殼 + `wizardRailHTML` 移植；FIX-1 測試保持綠
5. **PAGE_ACTION mode-note + PAGE_CONFIRM badge** + 切換衝突外觀微調
6. **PROGRESS phasebar + steplist + 即時 feed**（消費 progress.*）
7. **BACK transition + 上一步鈕**
8. **`ui-modal.js renderPipelineProgress` 改用新設計 + `styles.css:846-867` 6 條 chips 規則移除**
9. **跨頁穿門轉場**（`.wizard-shell.leaving` + `.onboarding-card` viewerIn）
10. **CHANGELOG v1.4.7 + 雙語 README core capabilities + 手動視覺驗收（對照 shots/）**

依賴：1 必須最早（其餘消費）；2、3 可並行；4 依 3；5、6 依 4；7 與 4-6 並行；8 依 2、6；9 末段；10 最後。

---

## 11 · 與其他既有設計的非交集確認

- **Edge Noise Projection (v1.4.6, dff40ff)** — 純後端 + prompt，與本 spec 物理零交集
- **疑義面板（DEFER）** — 與本流程無關，本 spec 不動 ui-doubt.js / `.empty-state`
- **L1 prompt context modes / scope-aware edge resolution / etc.** — 後端結構分析設計，與前端進場流程獨立

---

## 12 · 來源檔對應（reference only，已 commit 至 repo）

| 來源 | 行 / 區段 | 落地處 |
|---|---|---|
| `flow.css:8-21` `:root` | token 定義 | §1.3 整合策略 |
| `flow.css:49-53` thresholdOut | 穿門淡出 | §6.2 |
| `flow.css:55-107` rail + content + screen | 雙欄結構 | §3 / §4.1 |
| `flow.css:120-133` prog-live + plIn | 即時 feed（plIn 須改寫） | §3.1 / §5.4 |
| `flow.css:175-214` steplist + phasebar | 進度 | §5.3 / §7.2 |
| `flow.css:254-258` viewerIn | 落地淡入 | §6.2 |
| `flow.js:107-136` railHTML | rail 模板 | §4.1 |
| `flow.js:137-244` screenHTML | 各頁 markup | §4.2 |
| `flow.js:246-…` viewerHTML | 落地版 | 棄用，落地用 FIX-4 |
| `flow.js:324/328` startTicker | demo 假資料 | 棄用（§5.4 嚴禁） |
| `wizard-flow.html` | shell | §2（chrome 不保留） |
| `shots/*.png` | 視覺驗收基準 | §9 |
| `assets/*.svg` | 品牌 / 階段 icon | §1.1 rail-brand / §5.3 phase ico |
