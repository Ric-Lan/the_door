# 步驟 0 — 測試基礎設施

## 目標

建立 Vitest + jsdom 測試環境，使後續所有模組的 TDD 流程可以執行。

## 產出物

| 檔案 | 說明 |
|---|---|
| `viewer/package.json` | type: module，devDeps: vitest / jsdom / @vitest/coverage-v8 |
| `viewer/vitest.config.js` | jsdom 環境、setupFiles、100% 覆蓋率閾值 |
| `viewer/tests/setup.js` | jsdom HTML fixture，完整複製 index.html 所有 element IDs |

## package.json 規格

```json
{
  "name": "the-door-viewer",
  "type": "module",
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage"
  },
  "devDependencies": {
    "@vitest/coverage-v8": "^2.0.0",
    "jsdom": "^25.0.0",
    "vitest": "^2.0.0"
  }
}
```

## vitest.config.js 規格

```js
import { defineConfig } from 'vitest/config';
export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.js'],
    globals: true,
    coverage: {
      provider: 'v8',
      include: ['js/**/*.js'],
      reporter: ['text', 'lcov'],
      all: true,
      thresholds: { lines: 100, functions: 100, branches: 100, statements: 100 },
    },
  },
});
```

## tests/setup.js 規格

- 必須在 `document.body.innerHTML` 設定完整 HTML fixture
- fixture 必須包含 `dom.js` 的 `els` 物件所有 31 個 element IDs
- element IDs 清單：
  `btn-diff`, `btn-baseline`, `btn-current`, `btn-reanalyze`,
  `summary-text`, `count-added`, `count-removed`, `count-modified`, `count-risk`,
  `list-title`, `list-source`, `feature-list`,
  `detail-source`, `detail-content`,
  `pipeline-progress`, `current-step`, `steps-list`,
  `update-modal`, `input-old-path`, `input-new-path`, `modal-error`, `input-language`,
  `btn-modal-cancel`, `btn-modal-submit`,
  `graph-drawer`, `graph-backdrop`, `btn-graph-toggle`, `btn-drawer-close`,
  `zoom-controls`, `btn-back-l1`, `btn-mindmap`
- 額外需要（graph / layers 測試）：
  `graph-container`, `mermaid-fallback`, `legend-panel`,
  `breadcrumb`, `layer-explanation`, `version-selector-bar`,
  `select-version-a`, `select-version-b`, `logo-mark`

## 驗證檢查清單

- [ ] `npm install` 無錯誤
- [ ] `npm test`（無任何 .test.js 時）執行無 crash
- [ ] `npm run test:coverage` 指令存在
