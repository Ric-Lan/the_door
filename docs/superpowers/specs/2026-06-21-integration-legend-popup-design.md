# Integration Legend Popup — Design Spec

**目的**：在功能卡片列 panel-header 的 `#list-source` 同列右方加一個 `ⓘ 整合標示` 按鈕，
點擊後浮出 popup 說明整合健檢標示（✅/❌/⚠/無標示）的含意，並附 `static`、`AST` 術語解釋。

---

## 改動範圍

| 檔案 | 動作 |
|---|---|
| `index.html` | panel-header 加 flex wrapper + `#btn-integ-legend` 按鈕 |
| `styles.css` | 新增 `.panel-header-sub`、`.integ-legend-btn`、`.integ-legend-popup` 約 35 行 |
| `js/ui-integration.js` | 新增 `initIntegrationLegend()` 函數 |
| `js/app.js` | `init()` 裡呼叫 `initIntegrationLegend()` |

---

## HTML 結構（index.html 修改段）

```html
<!-- cards-panel .panel-header 內 -->
<div class="panel-header">
  <h2 id="list-title">功能總覽</h2>
  <div class="panel-header-sub">
    <p id="list-source"></p>
    <button id="btn-integ-legend" class="integ-legend-btn" type="button"
            title="整合健檢標示說明">ⓘ 整合標示</button>
  </div>
</div>
```

Popup 元素插在 `index.html` body 末尾（全域 fixed，不受 panel overflow 截切）：

```html
<div id="integ-legend-popup" class="integ-legend-popup" hidden role="dialog"
     aria-label="整合健檢標示說明" aria-modal="true">
  <!-- 由 initIntegrationLegend() 填入內容 -->
</div>
```

---

## Popup 內容（精確文字）

```
整合健檢標示說明                                          [✕]

✅ 有接上（backed）
   宣稱的 static 依賴在程式碼結構上有連線支撐。

❌ 沒接上（gap）
   宣稱有 static 依賴，但 AST 找不到對應呼叫路徑，建議確認。

⚠ 無法判定（undetermined）
   依賴目標不是程式碼節點（如 HTTP 或跨語言呼叫），無法從結構驗證。

（無標示）未評估
   此功能沒有宣稱 static 依賴，不在整合健檢範圍內。

━━━━━━━━━━━━━━━━━━━━━━━
術語說明

static
   Agent 在標記功能依賴時使用的類型，表示「期待這條依賴在程式碼裡有
   直接的呼叫路徑」（同語言的直接 import / call）。The Door 會用 AST
   驗證它是否真的接上。

AST（Abstract Syntax Tree，抽象語法樹）
   程式碼的結構化表示，記錄函式、類別與彼此的呼叫關係。The Door 以
   AST 為基礎判斷功能之間是否存在實際連線，而非只看功能描述。
```

---

## CSS 規格（使用現有 CSS 變數，不引入新色）

```css
/* panel-header 子列：p + 按鈕同行 */
.panel-header-sub {
  display: flex;
  align-items: center;
  gap: 8px;
}
.panel-header-sub p { margin: 0; flex: 1; }

/* 按鈕 */
.integ-legend-btn {
  flex-shrink: 0;
  padding: 2px 7px;
  font-size: 11px;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: var(--surface);
  color: var(--muted);
  cursor: pointer;
  white-space: nowrap;
}
.integ-legend-btn:hover { background: var(--line); color: var(--text); }

/* Popup */
.integ-legend-popup {
  position: fixed;
  z-index: 300;
  width: 340px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow-modal);
  padding: 16px;
  font-size: 13px;
  line-height: 1.55;
}
.integ-legend-popup[hidden] { display: none; }

.integ-legend-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-weight: 600;
  font-size: 13px;
}
.integ-legend-close {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  color: var(--muted);
  padding: 0 2px;
}
.integ-legend-close:hover { color: var(--text); }

.integ-legend-rows { margin-bottom: 12px; }
.integ-legend-row  { margin-bottom: 8px; }
.integ-legend-row .sym { font-size: 14px; }
.integ-legend-row .lbl { font-weight: 600; }
.integ-legend-row .desc { color: var(--muted); font-size: 12px; margin-top: 1px; }

.integ-legend-divider {
  border: none;
  border-top: 1px solid var(--line);
  margin: 12px 0;
}
.integ-legend-terms { font-size: 12px; }
.integ-legend-term-title { font-weight: 600; margin-top: 8px; margin-bottom: 2px; }
.integ-legend-term-desc   { color: var(--muted); line-height: 1.5; }
```

---

## JS 規格（`initIntegrationLegend()`）

```js
export function initIntegrationLegend() {
  const btn   = document.getElementById('btn-integ-legend');
  const popup = document.getElementById('integ-legend-popup');
  if (!btn || !popup) return;

  // 填充 popup 內容（一次性）
  popup.innerHTML = `
    <div class="integ-legend-header">
      整合健檢標示說明
      <button class="integ-legend-close" type="button" aria-label="關閉">✕</button>
    </div>
    <div class="integ-legend-rows">
      <div class="integ-legend-row">
        <span class="sym">✅</span> <span class="lbl">有接上（backed）</span>
        <div class="desc">宣稱的 static 依賴在程式碼結構上有連線支撐。</div>
      </div>
      <div class="integ-legend-row">
        <span class="sym">❌</span> <span class="lbl">沒接上（gap）</span>
        <div class="desc">宣稱有 static 依賴，但 AST 找不到對應呼叫路徑，建議確認。</div>
      </div>
      <div class="integ-legend-row">
        <span class="sym">⚠</span> <span class="lbl">無法判定（undetermined）</span>
        <div class="desc">依賴目標不是程式碼節點（如 HTTP 或跨語言呼叫），無法從結構驗證。</div>
      </div>
      <div class="integ-legend-row">
        <span class="lbl">（無標示）未評估</span>
        <div class="desc">此功能沒有宣稱 static 依賴，不在整合健檢範圍內。</div>
      </div>
    </div>
    <hr class="integ-legend-divider">
    <div class="integ-legend-terms">
      <div class="integ-legend-term-title">static</div>
      <div class="integ-legend-term-desc">
        Agent 在標記功能依賴時使用的類型，表示「期待這條依賴在程式碼裡有直接的呼叫路徑」
        （同語言的直接 import / call）。The Door 會用 AST 驗證它是否真的接上。
      </div>
      <div class="integ-legend-term-title">AST（Abstract Syntax Tree，抽象語法樹）</div>
      <div class="integ-legend-term-desc">
        程式碼的結構化表示，記錄函式、類別與彼此的呼叫關係。The Door 以 AST 為基礎判斷
        功能之間是否存在實際連線，而非只看功能描述。
      </div>
    </div>
  `;

  // 定位 popup 在按鈕正下方
  function positionPopup() {
    const r = btn.getBoundingClientRect();
    popup.style.top  = (r.bottom + 6) + 'px';
    popup.style.left = Math.max(8, r.left - 260 + r.width) + 'px'; // 靠右對齊按鈕
  }

  // Toggle
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    if (!popup.hidden) { popup.hidden = true; return; }
    positionPopup();
    popup.hidden = false;
  });

  // 關閉按鈕
  popup.querySelector('.integ-legend-close').addEventListener('click', () => {
    popup.hidden = true;
  });

  // 點外部關閉
  document.addEventListener('click', (e) => {
    if (!popup.hidden && !popup.contains(e.target) && e.target !== btn) {
      popup.hidden = true;
    }
  });

  // ESC 關閉
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') popup.hidden = true;
  });
}
```

---

## app.js 修改

```js
import { renderIntegrationPanel, initIntegrationLegend } from './ui-integration.js';
// ...
export function init() {
  initDetailTabs();
  initIntegrationLegend();   // ← 新增這行
  // ... 其餘不變
}
```

---

## 不做的事

- 不加動畫（keep it simple）
- 不在 diff 模式下隱藏按鈕（整合標示在任何模式下都可能出現在卡片上）
- 不新增獨立 JS 模組（函數加入現有 `ui-integration.js`）
