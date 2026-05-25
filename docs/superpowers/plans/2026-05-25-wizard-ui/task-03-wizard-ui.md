# Task 03 — HTML / CSS：`wizard.html` + `wizard.css`

> **依賴：** Task 02 完成（`ui-wizard.js` 存在且導出 `initWizard`）

**Files:**
- Create: `docs/frontend-local-version-viewer/viewer/wizard.html`
- Create: `docs/frontend-local-version-viewer/viewer/wizard.css`

---

## Task 03.1 — `wizard.css`

- [ ] **Step 1: 建立 `wizard.css`**

建立 `docs/frontend-local-version-viewer/viewer/wizard.css`：

```css
/* wizard.css — Wizard UI 專用樣式
   使用 styles.css 的 CSS 變數，不污染主 Viewer 樣式。
*/

.wizard-root {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
  padding: 24px;
}

.wizard-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 32px 36px;
  width: 100%;
  max-width: 560px;
  box-shadow: var(--shadow);
}

.wizard-card h2 {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text);
  margin: 0 0 8px;
}

.wizard-subtitle {
  color: var(--muted);
  font-size: 0.875rem;
  margin: 0 0 24px;
}

/* Option buttons */
.wizard-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 20px;
}

.wizard-option-btn {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border: 1.5px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s, background 0.15s;
  font-family: inherit;
}

.wizard-option-btn:hover {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.wizard-option-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.wizard-option-btn strong {
  display: block;
  font-size: 0.9rem;
  color: var(--text);
  margin-bottom: 2px;
}

.wizard-option-btn span {
  font-size: 0.8rem;
  color: var(--muted);
}

/* Form fields */
.wizard-field {
  margin-bottom: 18px;
}

.wizard-field label {
  display: block;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-body);
  margin-bottom: 6px;
}

.wizard-field input[type="text"] {
  width: 100%;
  padding: 8px 12px;
  border: 1.5px solid var(--line);
  border-radius: 6px;
  font-size: 0.875rem;
  color: var(--text);
  background: var(--surface);
  font-family: inherit;
  outline: none;
  transition: border-color 0.15s;
}

.wizard-field input[type="text"]:focus {
  border-color: var(--accent);
}

/* Primary action button */
.wizard-btn-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10px 24px;
  background: var(--accent);
  color: var(--on-accent);
  border: none;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.15s;
}

.wizard-btn-primary:hover {
  background: var(--accent-press);
}

/* Summary table in confirm page */
.wizard-summary {
  background: var(--surface-muted);
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 20px;
  font-size: 0.82rem;
  color: var(--text-body);
}

.wizard-summary dt {
  font-weight: 600;
  color: var(--muted);
  margin-top: 8px;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.wizard-summary dt:first-child { margin-top: 0; }

.wizard-summary dd {
  margin: 2px 0 0;
  color: var(--text);
  font-family: monospace;
  font-size: 0.8rem;
}

/* Progress steps */
.wizard-steps {
  list-style: none;
  padding: 0;
  margin: 0 0 20px;
}

.wizard-step {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--line);
  font-size: 0.875rem;
  color: var(--muted);
}

.wizard-step:last-child { border-bottom: none; }

.wizard-step[data-step-status="done"] {
  color: var(--added-fg);
}

.wizard-step[data-step-status="running"] {
  color: var(--accent);
  font-weight: 600;
}

.wizard-step-icon {
  width: 20px;
  text-align: center;
  flex-shrink: 0;
}

/* Agent params block */
.wizard-agent-params {
  background: var(--surface-muted);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 12px 14px;
  font-family: monospace;
  font-size: 0.78rem;
  color: var(--text-body);
  white-space: pre-wrap;
  margin-bottom: 16px;
  overflow-x: auto;
}

.wizard-btn-copy {
  font-size: 0.8rem;
  padding: 6px 14px;
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: 5px;
  cursor: pointer;
  font-family: inherit;
  margin-bottom: 10px;
}

/* Error page */
.wizard-error-box {
  background: var(--danger-bg);
  border: 1px solid var(--danger);
  border-radius: 8px;
  padding: 14px 16px;
  color: var(--danger);
  font-size: 0.875rem;
  margin-bottom: 16px;
}
```

- [ ] **Step 2: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/wizard.css
git commit -m "feat(wizard): add wizard.css with shared CSS variable usage"
```

---

## Task 03.2 — `wizard.html`

- [ ] **Step 1: 建立 `wizard.html`**

建立 `docs/frontend-local-version-viewer/viewer/wizard.html`：

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

- [ ] **Step 2: 手動驗證 HTML 可載入**

```bash
cd docs/frontend-local-version-viewer/viewer && python -m http.server 9999 &
```

在瀏覽器開啟 `http://localhost:9999/wizard.html`。
期望：頁面無 JS 錯誤，顯示「載入中…」。（因為沒有真實 server，`/api/status` 會失敗 → 顯示錯誤頁，這是預期行為）

終止 python server：`kill %1`

- [ ] **Step 3: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/wizard.html
git commit -m "feat(wizard): add wizard.html entry page"
```
