# Task 01 — FIX-1: 啟動精靈 renderPage() 補套 wizard.css className（P0）

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`（`renderPage()` 函式，現行 148-310 行）
- Test: `docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js`（既有檔，新增 14 條斷言；可能更新 1 條既有斷言）

**根因：** `wizard.css` 222 行有完整 `.wizard-card` / `.wizard-option-btn` / `.wizard-btn-primary` / `.wizard-summary` / `.wizard-steps` / `.wizard-step[data-step-status]` / `.wizard-error-box` 等選擇器，但 `ui-wizard.js` `renderPage()` 各 case 吐裸 HTML、零 className → CSS 全死碼，且 `[data-step-status]` 掛在裸 `<li>` 對不上 CSS 選擇器 `.wizard-step[data-step-status]`。

**改動性質：** 純 className + 結構性 markup 細修，不動狀態機、不動 dispatch、不動 `data-*` 屬性、不寫新 CSS。

**Coverage 影響：** 新增的 icon 三元運算式（done/running/pending 三分支）由既有「PROGRESS with multiple steps renders done/running/pending correctly」測試（tests/ui-wizard.test.js:637-673）覆蓋；只需加 className 與 icon 字元斷言即可維持 100%。

---

## Step-by-step

- [ ] **Step 1: 為 PAGE_ACTION 寫失敗測試（新增 `.wizard-card` / `.wizard-option-btn` / `.wizard-subtitle` 斷言）**

打開 `tests/ui-wizard.test.js`，找到 `describe('initWizard', ...)`（line 312）內既有 test `it('renders PAGE_ACTION after status loaded', ...)`（line 339-351），**在它之後**新增下列 test：

```js
  it('PAGE_ACTION has snapshots: option buttons use wizard-option-btn class with strong+span', async () => {
    const api = {
      getStatus: vi.fn().mockResolvedValue({
        state: { has_snapshots: true, has_api_key: true },
        next_actions: [],
      }),
      postAnalyze: vi.fn(),
      getJobStatus: vi.fn(),
      setProject: vi.fn(),
    };
    const { initWizard } = await import('../js/ui-wizard.js');
    initWizard(container, api, vi.fn());
    await vi.waitFor(() => container.querySelector('[data-action="update"]'));
    expect(container.querySelector('.wizard-card')).not.toBeNull();
    expect(container.querySelector('.wizard-subtitle')).not.toBeNull();
    expect(container.querySelector('.wizard-options')).not.toBeNull();
    const updateBtn = container.querySelector('[data-action="update"]');
    expect(updateBtn.classList.contains('wizard-option-btn')).toBe(true);
    expect(updateBtn.querySelector('strong')).not.toBeNull();
    expect(updateBtn.querySelector('span')).not.toBeNull();
  });

  it('PAGE_ACTION no snapshots: analyze + view buttons use wizard-option-btn', async () => {
    const api = {
      getStatus: vi.fn().mockResolvedValue({
        state: { has_snapshots: false, has_api_key: true },
        next_actions: [],
      }),
      postAnalyze: vi.fn(),
      getJobStatus: vi.fn(),
      setProject: vi.fn(),
    };
    const { initWizard } = await import('../js/ui-wizard.js');
    initWizard(container, api, vi.fn());
    await vi.waitFor(() => container.querySelector('[data-action="analyze"]'));
    expect(container.querySelector('[data-action="analyze"]').classList.contains('wizard-option-btn')).toBe(true);
    expect(container.querySelector('[data-action="view"]').classList.contains('wizard-option-btn')).toBe(true);
  });

  it('switch section uses wizard-field + wizard-btn-primary and no <hr>', async () => {
    const api = {
      getStatus: vi.fn().mockResolvedValue({
        state: { has_snapshots: false, has_api_key: true },
        next_actions: [],
      }),
      postAnalyze: vi.fn(),
      getJobStatus: vi.fn(),
      setProject: vi.fn(),
    };
    const { initWizard } = await import('../js/ui-wizard.js');
    initWizard(container, api, vi.fn());
    await vi.waitFor(() => container.querySelector('[data-switch-input]'));
    expect(container.querySelector('hr')).toBeNull();
    expect(container.querySelector('.wizard-field')).not.toBeNull();
    expect(container.querySelector('[data-switch-btn]').classList.contains('wizard-btn-primary')).toBe(true);
  });

  it('switch conflict uses wizard-error-box and wizard-btn-primary', async () => {
    const api = {
      getStatus: vi.fn().mockResolvedValue({
        state: { has_snapshots: false, has_api_key: true },
        next_actions: [],
      }),
      postAnalyze: vi.fn(),
      getJobStatus: vi.fn(),
      setProject: vi.fn().mockResolvedValue({ status: 'conflict', active_job_id: 'j1', message: 'busy' }),
    };
    const { initWizard } = await import('../js/ui-wizard.js');
    initWizard(container, api, vi.fn());
    await vi.waitFor(() => container.querySelector('[data-switch-input]'));
    container.querySelector('[data-switch-input]').value = '/x';
    container.querySelector('[data-switch-btn]').click();
    await vi.waitFor(() => container.querySelector('[data-switch-conflict]'));
    expect(container.querySelector('.wizard-error-box')).not.toBeNull();
    expect(container.querySelector('[data-switch-force-btn]').classList.contains('wizard-btn-primary')).toBe(true);
  });

  it('PAGE_SETUP uses wizard-field + wizard-btn-primary + wizard-subtitle', async () => {
    const api = {
      getStatus: vi.fn().mockResolvedValue({
        state: { has_snapshots: false, has_api_key: true, file_count: 42 },
        next_actions: [],
      }),
      postAnalyze: vi.fn(),
      getJobStatus: vi.fn(),
    };
    const { initWizard } = await import('../js/ui-wizard.js');
    initWizard(container, api, vi.fn());
    await vi.waitFor(() => container.querySelector('[data-action="analyze"]'));
    container.querySelector('[data-action="analyze"]').click();
    await vi.waitFor(() => container.querySelector('[data-page="PAGE_SETUP"]'));
    expect(container.querySelector('.wizard-field')).not.toBeNull();
    expect(container.querySelector('.wizard-subtitle')).not.toBeNull();
    expect(container.querySelector('[data-next="setup"]').classList.contains('wizard-btn-primary')).toBe(true);
  });

  it('PAGE_LABEL uses wizard-field + wizard-btn-primary', async () => {
    const api = {
      getStatus: vi.fn().mockResolvedValue({
        state: { has_snapshots: false, has_api_key: true },
        next_actions: [],
      }),
      postAnalyze: vi.fn(),
      getJobStatus: vi.fn(),
    };
    const { initWizard } = await import('../js/ui-wizard.js');
    initWizard(container, api, vi.fn());
    await vi.waitFor(() => container.querySelector('[data-action="analyze"]'));
    container.querySelector('[data-action="analyze"]').click();
    container.querySelector('[data-next="setup"]').click();
    await vi.waitFor(() => container.querySelector('[data-page="PAGE_LABEL"]'));
    expect(container.querySelector('.wizard-field')).not.toBeNull();
    expect(container.querySelector('[data-next="label"]').classList.contains('wizard-btn-primary')).toBe(true);
  });

  it('PAGE_CONFIRM uses wizard-summary dl/dt/dd + wizard-btn-primary', async () => {
    const api = {
      getStatus: vi.fn().mockResolvedValue({
        state: { has_snapshots: true, has_api_key: true },
        next_actions: [],
      }),
      postAnalyze: vi.fn(),
      getJobStatus: vi.fn(),
      setProject: vi.fn(),
    };
    const { initWizard } = await import('../js/ui-wizard.js');
    initWizard(container, api, vi.fn());
    await vi.waitFor(() => container.querySelector('[data-action="update"]'));
    container.querySelector('[data-action="update"]').click();
    await vi.waitFor(() => container.querySelector('[data-page="PAGE_CONFIRM"]'));
    const dl = container.querySelector('dl.wizard-summary');
    expect(dl).not.toBeNull();
    expect(dl.querySelectorAll('dt').length).toBe(2);
    expect(dl.querySelectorAll('dd').length).toBe(2);
    expect(container.querySelector('[data-submit]').classList.contains('wizard-btn-primary')).toBe(true);
  });

  it('PROGRESS step list uses wizard-steps + wizard-step + wizard-step-icon', async () => {
    vi.useFakeTimers();
    try {
      const steps = [
        { step_name: '探索', status: 'done' },
        { step_name: 'LLM', status: 'running' },
        { step_name: '寫入', status: 'pending' },
      ];
      const api = {
        getStatus: vi.fn().mockResolvedValue({
          state: { has_snapshots: false, has_api_key: true },
          next_actions: [],
        }),
        postAnalyze: vi.fn().mockResolvedValue({ job_id: 'j' }),
        getJobStatus: vi.fn().mockResolvedValue({
          status: 'running', current_step: 'LLM', steps,
        }),
      };
      const { initWizard } = await import('../js/ui-wizard.js');
      initWizard(container, api, vi.fn());
      await Promise.resolve(); await Promise.resolve();
      container.querySelector('[data-action="analyze"]').click();
      container.querySelector('[data-next="setup"]').click();
      container.querySelector('[data-next="label"]').click();
      container.querySelector('[data-submit]').click();
      await Promise.resolve(); await Promise.resolve();
      await vi.advanceTimersByTimeAsync(1500);
      expect(container.querySelector('ul.wizard-steps')).not.toBeNull();
      const items = container.querySelectorAll('li.wizard-step');
      expect(items.length).toBe(3);
      // Icons: ✓ for done, ◐ for running, ○ for pending
      expect(items[0].querySelector('.wizard-step-icon').textContent).toBe('✓');
      expect(items[1].querySelector('.wizard-step-icon').textContent).toBe('◐');
      expect(items[2].querySelector('.wizard-step-icon').textContent).toBe('○');
    } finally {
      vi.useRealTimers();
    }
  });

  it('PROGRESS fallback (no steps) uses wizard-step with pending icon ○', async () => {
    vi.useFakeTimers();
    try {
      const api = {
        getStatus: vi.fn().mockResolvedValue({
          state: { has_snapshots: false, has_api_key: true },
          next_actions: [],
        }),
        postAnalyze: vi.fn().mockResolvedValue({ job_id: 'j' }),
        getJobStatus: vi.fn().mockResolvedValue({
          status: 'running', current_step: null, steps: undefined,
        }),
      };
      const { initWizard } = await import('../js/ui-wizard.js');
      initWizard(container, api, vi.fn());
      await Promise.resolve(); await Promise.resolve();
      container.querySelector('[data-action="analyze"]').click();
      container.querySelector('[data-next="setup"]').click();
      container.querySelector('[data-next="label"]').click();
      container.querySelector('[data-submit]').click();
      await Promise.resolve(); await Promise.resolve();
      await vi.advanceTimersByTimeAsync(1500);
      const fallbackItem = container.querySelector('li.wizard-step[data-step-status="pending"]');
      expect(fallbackItem).not.toBeNull();
      expect(fallbackItem.querySelector('.wizard-step-icon').textContent).toBe('○');
    } finally {
      vi.useRealTimers();
    }
  });

  it('agent mode pre uses wizard-agent-params; copy uses wizard-btn-copy; done uses wizard-btn-primary', async () => {
    const api = {
      getStatus: vi.fn().mockResolvedValue({
        state: { has_snapshots: false, has_api_key: false },
        next_actions: [],
      }),
      postAnalyze: vi.fn(),
      getJobStatus: vi.fn(),
    };
    const { initWizard } = await import('../js/ui-wizard.js');
    initWizard(container, api, vi.fn());
    await vi.waitFor(() => container.querySelector('[data-action="analyze"]'));
    container.querySelector('[data-action="analyze"]').click();
    container.querySelector('[data-next="setup"]').click();
    container.querySelector('[data-next="label"]').click();
    container.querySelector('[data-submit]').click();
    await vi.waitFor(() => container.querySelector('[data-agent-params]'));
    expect(container.querySelector('[data-agent-params]').classList.contains('wizard-agent-params')).toBe(true);
    expect(container.querySelector('[data-copy]').classList.contains('wizard-btn-copy')).toBe(true);
    expect(container.querySelector('[data-done]').classList.contains('wizard-btn-primary')).toBe(true);
  });

  it('PAGE_ERROR uses wizard-error-box and link uses wizard-btn-primary', async () => {
    const api = {
      getStatus: vi.fn().mockRejectedValue(new Error('boom')),
      postAnalyze: vi.fn(),
      getJobStatus: vi.fn(),
    };
    const { initWizard } = await import('../js/ui-wizard.js');
    initWizard(container, api, vi.fn());
    await vi.waitFor(() => container.querySelector('[data-page="PAGE_ERROR"]'));
    expect(container.querySelector('.wizard-error-box')).not.toBeNull();
    expect(container.querySelector('a[href="/index.html"]').classList.contains('wizard-btn-primary')).toBe(true);
  });

  it('every rendered page wraps in .wizard-card', async () => {
    const api = {
      getStatus: vi.fn().mockResolvedValue({
        state: { has_snapshots: false, has_api_key: true },
        next_actions: [],
      }),
      postAnalyze: vi.fn(),
      getJobStatus: vi.fn(),
    };
    const { initWizard } = await import('../js/ui-wizard.js');
    initWizard(container, api, vi.fn());
    await vi.waitFor(() => container.querySelector('[data-page]'));
    expect(container.querySelector('[data-page].wizard-card')).not.toBeNull();
  });
```

接著找到既有 test `it('renders PAGE_ERROR with fallback "未知錯誤" when errorMessage is null', ...)`（line 629-635）— 它對 `<p>` 斷言 textContent，FIX-1 變更 ⑦ 改為 `<div class="wizard-error-box">`，textContent 斷言不變仍會通過；不需動。

- [ ] **Step 2: 跑測試確認新增的 14 條全失敗**

```bash
cd docs/frontend-local-version-viewer/viewer
npx vitest run tests/ui-wizard.test.js --reporter=verbose 2>&1 | grep -E "(✓|✗|FAIL|PASS)" | tail -40
```

Expected：14 條新測試全 FAIL（class not found / null query result）；既有 ~40 條通過。

- [ ] **Step 3: 改 `js/ui-wizard.js` 變更 ① — 為 wrap 加 `wizard-card` className**

開啟 `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`，找到 line 148-151：

```js
export function renderPage(container, state, dispatch, redirectFn, api) {
  container.innerHTML = '';
  const wrap = document.createElement('div');
  wrap.setAttribute('data-page', state.page);
```

改為：

```js
export function renderPage(container, state, dispatch, redirectFn, api) {
  container.innerHTML = '';
  const wrap = document.createElement('div');
  wrap.setAttribute('data-page', state.page);
  wrap.className = 'wizard-card';
```

- [ ] **Step 4: 變更 ② — PAGE_ACTION 兩分支改用 .wizard-option-btn**

找到 line 158-171（PAGE_ACTION case）：

```js
    case 'PAGE_ACTION':
      if (!state.hasSnapshots) {
        wrap.innerHTML = `
          <h2>歡迎使用 The Door</h2>
          <button data-action="analyze">首次分析此專案</button>
          <button data-action="view" disabled>查看快照（尚無資料）</button>
        `;
      } else {
        wrap.innerHTML = `
          <h2>選擇操作</h2>
          <button data-action="update">更新分析（重新跑）</button>
          <button data-action="view">直接查看現有快照</button>
        `;
      }
```

改為：

```js
    case 'PAGE_ACTION':
      if (!state.hasSnapshots) {
        wrap.innerHTML = `
          <h2>歡迎使用 The Door</h2>
          <p class="wizard-subtitle">首次使用，從分析此專案開始。</p>
          <div class="wizard-options">
            <button class="wizard-option-btn" data-action="analyze">
              <strong>首次分析此專案</strong>
              <span>掃描原始碼，建立第一份結構快照。</span>
            </button>
            <button class="wizard-option-btn" data-action="view" disabled>
              <strong>查看快照</strong>
              <span>尚無資料。</span>
            </button>
          </div>
        `;
      } else {
        wrap.innerHTML = `
          <h2>選擇操作</h2>
          <p class="wizard-subtitle">偵測到既有快照，選擇下一步。</p>
          <div class="wizard-options">
            <button class="wizard-option-btn" data-action="update">
              <strong>更新分析</strong>
              <span>重新掃描原始碼，產生新版本快照。</span>
            </button>
            <button class="wizard-option-btn" data-action="view">
              <strong>查看現有快照</strong>
              <span>直接進入 Viewer，不重新分析。</span>
            </button>
          </div>
        `;
      }
```

- [ ] **Step 5: 變更 ③ — switch section 移除 `<hr>`、改用 wizard-field + wizard-btn-primary；conflict 用 wizard-error-box**

找到 line 184-207（switchSection 兩分支）：

```js
      if (state.switchConflict) {
        switchSection.innerHTML = `
          <div data-switch-conflict>
            <p>目前有進行中的分析任務</p>
            <button data-switch-force-btn>立即切換（中斷任務）</button>
            <button data-switch-cancel-btn>取消</button>
          </div>
        `;
        // ... event bindings unchanged
      } else {
        switchSection.innerHTML = `
          <hr>
          <label>切換至其他專案
            <input type="text" data-switch-input placeholder="/absolute/path/to/project">
          </label>
          <button data-switch-btn>切換</button>
        `;
        // ... event bindings unchanged
      }
```

改為（**事件綁定區段保留不動**，只動 `innerHTML`）：

```js
      if (state.switchConflict) {
        switchSection.innerHTML = `
          <div data-switch-conflict class="wizard-error-box">
            <p>目前有進行中的分析任務</p>
            <button class="wizard-btn-primary" data-switch-force-btn>立即切換（中斷任務）</button>
            <button data-switch-cancel-btn>取消</button>
          </div>
        `;
        // ... event bindings unchanged
      } else {
        switchSection.innerHTML = `
          <div class="wizard-field">
            <label>切換至其他專案</label>
            <input type="text" data-switch-input placeholder="/absolute/path/to/project">
          </div>
          <button class="wizard-btn-primary" data-switch-btn>切換</button>
        `;
        // ... event bindings unchanged
      }
```

- [ ] **Step 6: 變更 ④ — PAGE_SETUP / PAGE_LABEL 改 wizard-field + wizard-btn-primary + wizard-subtitle**

找到 line 228-241（PAGE_SETUP case）：

```js
    case 'PAGE_SETUP':
      wrap.innerHTML = `
        <h2>設定分析範圍</h2>
        <p>偵測到 ${state.fileCount} 個源碼檔案。</p>
        <label>排除目錄（逗號分隔，選填）：
          <input type="text" data-excludes placeholder="tests/, docs/" value="${state.excludesRaw}">
        </label>
        <button data-next="setup">下一步</button>
      `;
```

改為：

```js
    case 'PAGE_SETUP':
      wrap.innerHTML = `
        <h2>設定分析範圍</h2>
        <p class="wizard-subtitle">偵測到 ${state.fileCount} 個源碼檔案。</p>
        <div class="wizard-field">
          <label>排除目錄（逗號分隔，選填）</label>
          <input type="text" data-excludes placeholder="tests/, docs/" value="${state.excludesRaw}">
        </div>
        <button class="wizard-btn-primary" data-next="setup">下一步</button>
      `;
```

找到 line 243-255（PAGE_LABEL case）：

```js
    case 'PAGE_LABEL':
      wrap.innerHTML = `
        <h2>快照標籤</h2>
        <label>版本標籤（選填）：
          <input type="text" data-label placeholder="v1.0.0" value="${state.label}">
        </label>
        <button data-next="label">下一步</button>
      `;
```

改為：

```js
    case 'PAGE_LABEL':
      wrap.innerHTML = `
        <h2>快照標籤</h2>
        <div class="wizard-field">
          <label>版本標籤（選填）</label>
          <input type="text" data-label placeholder="v1.0.0" value="${state.label}">
        </div>
        <button class="wizard-btn-primary" data-next="label">下一步</button>
      `;
```

- [ ] **Step 7: 變更 ⑤ — PAGE_CONFIRM 用 wizard-summary dl/dt/dd + wizard-btn-primary**

找到 line 257-268（PAGE_CONFIRM case）：

```js
    case 'PAGE_CONFIRM': {
      const mode = state.hasApiKey ? 'API key 模式' : 'Agent 模式（無 API key）';
      wrap.innerHTML = `
        <h2>確認送出</h2>
        <p>操作：${state.action}</p>
        <p>模式：${mode}</p>
        <button data-submit>確認送出</button>
      `;
      wrap.querySelector('[data-submit]').addEventListener('click', () => {
        dispatch({ type: 'SUBMIT' });
      });
      break;
    }
```

改為（事件綁定不動）：

```js
    case 'PAGE_CONFIRM': {
      const mode = state.hasApiKey ? 'API key 模式' : 'Agent 模式（無 API key）';
      wrap.innerHTML = `
        <h2>確認送出</h2>
        <dl class="wizard-summary">
          <dt>操作</dt><dd>${state.action}</dd>
          <dt>模式</dt><dd>${mode}</dd>
        </dl>
        <button class="wizard-btn-primary" data-submit>確認送出</button>
      `;
      wrap.querySelector('[data-submit]').addEventListener('click', () => {
        dispatch({ type: 'SUBMIT' });
      });
      break;
    }
```

- [ ] **Step 8: 變更 ⑥ — PROGRESS 進度列加 wizard-step + wizard-step-icon；Agent 模式加 wizard-agent-params/btn-copy/btn-primary**

找到 line 275-299（PROGRESS case）：

```js
    case 'PROGRESS':
      if (!state.hasApiKey) {
        wrap.innerHTML = `
          <h2>Agent 模式 — 複製以下指令給 Claude</h2>
          <pre data-agent-params>extract_structure(codebase_path="${state.projectPath}")
snapshot_write(codebase_path="${state.projectPath}", l1_features=[...], label="${state.label || 'v1.0.0'}")</pre>
          <button data-copy>複製</button>
          <button data-done>我已讓 agent 執行完畢，進入 Viewer</button>
        `;
        wrap.querySelector('[data-copy]').addEventListener('click', () => {
          navigator.clipboard.writeText(wrap.querySelector('[data-agent-params]').textContent);
        });
        wrap.querySelector('[data-done]').addEventListener('click', () => redirectFn('/index.html'));
      } else {
        const stepItems = state.steps.map((s, i) => {
          const idx = stepIndexForCurrentStep(state.steps, state.currentStep);
          const cls = i < idx ? 'done' : i === idx ? 'running' : 'pending';
          return `<li data-step-status="${cls}">${s.step_name}</li>`;
        }).join('');
        wrap.innerHTML = `
          <h2>分析進行中</h2>
          <ul>${stepItems || '<li data-step-status="pending">初始化中…</li>'}</ul>
        `;
      }
      break;
```

改為（事件綁定不動）：

```js
    case 'PROGRESS':
      if (!state.hasApiKey) {
        wrap.innerHTML = `
          <h2>Agent 模式 — 複製以下指令給 Claude</h2>
          <pre class="wizard-agent-params" data-agent-params>extract_structure(codebase_path="${state.projectPath}")
snapshot_write(codebase_path="${state.projectPath}", l1_features=[...], label="${state.label || 'v1.0.0'}")</pre>
          <button class="wizard-btn-copy" data-copy>複製</button>
          <button class="wizard-btn-primary" data-done>我已讓 agent 執行完畢，進入 Viewer</button>
        `;
        wrap.querySelector('[data-copy]').addEventListener('click', () => {
          navigator.clipboard.writeText(wrap.querySelector('[data-agent-params]').textContent);
        });
        wrap.querySelector('[data-done]').addEventListener('click', () => redirectFn('/index.html'));
      } else {
        const idx = stepIndexForCurrentStep(state.steps, state.currentStep);
        const stepItems = state.steps.map((s, i) => {
          const cls  = i < idx ? 'done' : i === idx ? 'running' : 'pending';
          const icon = cls === 'done' ? '✓' : cls === 'running' ? '◐' : '○';
          return `<li class="wizard-step" data-step-status="${cls}">`
               + `<span class="wizard-step-icon">${icon}</span>${s.step_name}</li>`;
        }).join('');
        const fallback = '<li class="wizard-step" data-step-status="pending">'
          + '<span class="wizard-step-icon">○</span>初始化中…</li>';
        wrap.innerHTML = `
          <h2>分析進行中</h2>
          <ul class="wizard-steps">${stepItems || fallback}</ul>
        `;
      }
      break;
```

注意：`idx` 計算從 map 內提到外（小重構）— 既有邏輯每次 map iteration 重算 `idx` 是同值，外提是無副作用優化。

- [ ] **Step 9: 變更 ⑦ — PAGE_ERROR 用 wizard-error-box + 連結 wizard-btn-primary**

找到 line 301-307（PAGE_ERROR case）：

```js
    case 'PAGE_ERROR':
      wrap.innerHTML = `
        <h2>發生錯誤</h2>
        <p>${state.errorMessage || '未知錯誤'}</p>
        <a href="/index.html">前往 Viewer</a>
      `;
      break;
```

改為：

```js
    case 'PAGE_ERROR':
      wrap.innerHTML = `
        <h2>發生錯誤</h2>
        <div class="wizard-error-box">${state.errorMessage || '未知錯誤'}</div>
        <a class="wizard-btn-primary" href="/index.html">前往 Viewer</a>
      `;
      break;
```

- [ ] **Step 10: 跑測試確認全綠**

```bash
cd docs/frontend-local-version-viewer/viewer
npx vitest run tests/ui-wizard.test.js --reporter=basic 2>&1 | tail -10
```

Expected：所有 ui-wizard 測試 PASS（既有 ~40 + 新增 14 = ~54 條），0 失敗。

若 fail：對照 step 3-9 的程式碼是否精確替換；常見錯誤是漏掉 `class=` 屬性或事件綁定區段被誤動。

- [ ] **Step 11: 跑全 viewer 測試 + coverage 確認 100%**

```bash
cd docs/frontend-local-version-viewer/viewer
npx vitest run --coverage 2>&1 | tail -25
```

Expected：
- 所有測試 PASS（baseline pre-existing failures 不變）
- Coverage report 顯示 `ui-wizard.js`：Lines 100% / Functions 100% / Branches 100% / Statements 100%
- 整體 4 個 threshold 全綠（不出現 `ERROR: Coverage threshold not met`）

若 ui-wizard.js coverage 未達 100%，看 uncovered line：通常是新加的 icon 三元分支或 `wizard-error-box` 條件 — 補對應 test。

- [ ] **Step 12: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js \
        docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js
git commit -m "$(cat <<'EOF'
fix(frontend): FIX-1 wizard renderer 接上 wizard.css className

renderPage() 各 case 補 .wizard-card / .wizard-option-btn /
.wizard-btn-primary / .wizard-summary / .wizard-steps /
.wizard-step[data-step-status] / .wizard-error-box className，
解掉 wizard.css 222 行死碼與 [data-step-status] 選擇器對不上問題。

- PAGE_ACTION 兩分支改 .wizard-option-btn + strong/span
- switch section 移除 <hr>，改 .wizard-field
- PAGE_SETUP/PAGE_LABEL 拆 label 為 .wizard-field 結構
- PAGE_CONFIRM 改 dl.wizard-summary
- PROGRESS 進度列加 .wizard-step + .wizard-step-icon (✓/◐/○)
- Agent 模式 pre 加 .wizard-agent-params、複製鈕 .wizard-btn-copy
- PAGE_ERROR 改 .wizard-error-box

不動狀態機、dispatch、事件綁定、data-* 屬性。
新增 14 條 className/結構斷言；coverage 100%。
EOF
)"
```

---

## Acceptance criteria

- `wizard.css` 每個 class selector 都有對應 DOM render（手動 grep 驗證）。
- ui-wizard 全測試綠（新增 14 條 + 既有 ~40 條）。
- `npx vitest run --coverage` 4 項 threshold 全綠。
- 未動任何 `data-*` 屬性、未動 `transition()` / `dispatch()` / 事件綁定。
- 手動：`the-door ui <test-target>` 開瀏覽器，wizard.html 各頁無灰按鈕；PROGRESS 完成步驟綠字、進行中粗體。
