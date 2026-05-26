# Task 05 — JS: `switchProject()` + PAGE_ACTION 切換 UI

> **依賴：** Task 04 完成（`/api/set-project` 已存在）

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`
- Modify: `docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js`

**測試指令：**
```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-wizard.test.js --coverage 2>&1 | tail -10
```
必須維持 `ui-wizard.js` 100% coverage。

---

## 背景：異動範圍

新增至 `WizardState` 的欄位（加在 `getInitialState` 回傳物件中）：
- `switchPath: ''` — 路徑輸入框的值
- `switchConflict: false` — 是否顯示 conflict 確認區
- `switchActiveJobId: null` — conflict 時的 job ID

新增 actions（加在 `transition` switch 中）：
- `SWITCH_PATH_CHANGE` → 更新 `switchPath`
- `SWITCH_CONFLICT` → `switchConflict: true, switchActiveJobId`
- `SWITCH_CANCEL` → `switchConflict: false`

新增到 `createApi` 回傳物件：
- `setProject(path, force)` → `POST /api/set-project`

新增到 `initWizard`：
- 在 PAGE_ACTION render 新增切換 UI（輸入框 + 按鈕 + conflict 區）
- 按下「切換」→ call `api.setProject(path, false)` → dispatch SWITCH_CONFLICT 或 reload
- 按下「立即切換（中斷任務）」→ call `api.setProject(path, true)` → reload

---

## Task 05.1 — `getInitialState` + `transition` 新 actions

- [ ] **Step 1: 在測試檔加失敗測試**

在 `ui-wizard.test.js` 的最末加入新 describe block：

```js
describe('switchProject state', () => {
  it('getInitialState includes switch fields', () => {
    const s = getInitialState();
    expect(s.switchPath).toBe('');
    expect(s.switchConflict).toBe(false);
    expect(s.switchActiveJobId).toBeNull();
  });

  it('SWITCH_PATH_CHANGE updates switchPath', () => {
    const s = transition(getInitialState(), { type: 'SWITCH_PATH_CHANGE', path: '/my/proj' });
    expect(s.switchPath).toBe('/my/proj');
  });

  it('SWITCH_CONFLICT sets switchConflict and activeJobId', () => {
    const s = transition(getInitialState(), { type: 'SWITCH_CONFLICT', activeJobId: 'job-1' });
    expect(s.switchConflict).toBe(true);
    expect(s.switchActiveJobId).toBe('job-1');
  });

  it('SWITCH_CANCEL clears switchConflict', () => {
    const base = { ...getInitialState(), switchConflict: true, switchActiveJobId: 'job-1' };
    const s = transition(base, { type: 'SWITCH_CANCEL' });
    expect(s.switchConflict).toBe(false);
    expect(s.switchActiveJobId).toBeNull();
  });
});
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-wizard.test.js -t "switchProject state" 2>&1 | tail -10
```
期望：4 FAILED。

- [ ] **Step 3: 修改 `ui-wizard.js`**

**3a.** 在 `getInitialState()` 的回傳物件加入（在 `pollFailCount: 0,` 之後）：
```js
    switchPath: '',
    switchConflict: false,
    switchActiveJobId: null,
```

**3b.** 在 `transition` switch 的 `default:` 之前加入：
```js
    case 'SWITCH_PATH_CHANGE':
      return { ...state, switchPath: action.path };

    case 'SWITCH_CONFLICT':
      return { ...state, switchConflict: true, switchActiveJobId: action.activeJobId };

    case 'SWITCH_CANCEL':
      return { ...state, switchConflict: false, switchActiveJobId: null };
```

- [ ] **Step 4: 確認測試通過**

```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-wizard.test.js -t "switchProject state" 2>&1 | tail -5
```
期望：4 PASSED。

- [ ] **Step 5: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js
git commit -m "feat(switch): add switch-project state fields and transitions to ui-wizard.js"
```

---

## Task 05.2 — `createApi.setProject()`

- [ ] **Step 1: 在測試檔加失敗測試**

在 `describe('createApi')` 的最末加入：

```js
  it('setProject calls POST /api/set-project with path and force', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'switched', path: '/my/proj' }),
    });
    const api = createApi(mockFetch);
    const result = await api.setProject('/my/proj', false);
    expect(mockFetch).toHaveBeenCalledWith('/api/set-project', expect.objectContaining({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: '/my/proj', force: false }),
    }));
    expect(result.status).toBe('switched');
  });

  it('setProject throws when response not ok', async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: false, status: 409 });
    const api = createApi(mockFetch);
    await expect(api.setProject('/x', false)).rejects.toThrow();
  });
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-wizard.test.js -t "setProject" 2>&1 | tail -10
```

- [ ] **Step 3: 在 `createApi` 的回傳物件加入 `setProject`**

在 `createApi` 的 return 物件（`getStatus`, `postAnalyze`, `getJobStatus` 之後）加：

```js
    setProject(path, force) {
      return fetchFn('/api/set-project', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, force }),
      }).then(_check);
    },
```

- [ ] **Step 4: 確認測試通過**

```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-wizard.test.js -t "setProject" 2>&1 | tail -5
```
期望：2 PASSED。

- [ ] **Step 5: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js
git commit -m "feat(switch): add setProject() to createApi"
```

---

## Task 05.3 — PAGE_ACTION 切換 UI + `initWizard` 側效應

- [ ] **Step 1: 在測試檔加失敗測試**

在 `describe('initWizard')` 的最末（`afterEach` 之前）加入：

```js
  it('shows switch section in PAGE_ACTION', async () => {
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
    await vi.waitFor(() => container.querySelector('[data-page="PAGE_ACTION"]'));
    expect(container.querySelector('[data-switch-input]')).not.toBeNull();
    expect(container.querySelector('[data-switch-btn]')).not.toBeNull();
  });

  it('switch success reloads to wizard.html', async () => {
    const redirectFn = vi.fn();
    const api = {
      getStatus: vi.fn().mockResolvedValue({
        state: { has_snapshots: false, has_api_key: true },
        next_actions: [],
      }),
      postAnalyze: vi.fn(),
      getJobStatus: vi.fn(),
      setProject: vi.fn().mockResolvedValue({ status: 'switched', path: '/new' }),
    };
    const { initWizard } = await import('../js/ui-wizard.js');
    initWizard(container, api, redirectFn);
    await vi.waitFor(() => container.querySelector('[data-switch-input]'));
    container.querySelector('[data-switch-input]').value = '/new/path';
    container.querySelector('[data-switch-btn]').click();
    await vi.waitFor(() => expect(redirectFn).toHaveBeenCalledWith('/wizard.html'));
  });

  it('switch conflict shows conflict UI', async () => {
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
    container.querySelector('[data-switch-input]').value = '/new/path';
    container.querySelector('[data-switch-btn]').click();
    await vi.waitFor(() => container.querySelector('[data-switch-conflict]'));
  });

  it('switch conflict force button calls setProject with force=true', async () => {
    const redirectFn = vi.fn();
    const api = {
      getStatus: vi.fn().mockResolvedValue({
        state: { has_snapshots: false, has_api_key: true },
        next_actions: [],
      }),
      postAnalyze: vi.fn(),
      getJobStatus: vi.fn(),
      setProject: vi.fn()
        .mockResolvedValueOnce({ status: 'conflict', active_job_id: 'j1', message: 'busy' })
        .mockResolvedValueOnce({ status: 'switched', path: '/new' }),
    };
    const { initWizard } = await import('../js/ui-wizard.js');
    initWizard(container, api, redirectFn);
    await vi.waitFor(() => container.querySelector('[data-switch-input]'));
    container.querySelector('[data-switch-input]').value = '/new/path';
    container.querySelector('[data-switch-btn]').click();
    await vi.waitFor(() => container.querySelector('[data-switch-force-btn]'));
    container.querySelector('[data-switch-force-btn]').click();
    await vi.waitFor(() => expect(redirectFn).toHaveBeenCalledWith('/wizard.html'));
    expect(api.setProject).toHaveBeenCalledWith(expect.any(String), true);
  });

  it('switch cancel hides conflict UI', async () => {
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
    container.querySelector('[data-switch-input]').value = '/new/path';
    container.querySelector('[data-switch-btn]').click();
    await vi.waitFor(() => container.querySelector('[data-switch-conflict]'));
    container.querySelector('[data-switch-cancel-btn]').click();
    await vi.waitFor(() => expect(container.querySelector('[data-switch-conflict]')).toBeNull());
  });
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-wizard.test.js -t "switch" 2>&1 | tail -10
```

- [ ] **Step 3: 修改 `renderPage` 的 `PAGE_ACTION` case**

在 `renderPage` 的 `case 'PAGE_ACTION':` 末尾（`break;` 之前），在 `wrap.querySelectorAll('[data-action]')...` 之後加入切換 UI：

```js
      // Switch project section
      const switchSection = document.createElement('div');
      if (state.switchConflict) {
        switchSection.innerHTML = `
          <div data-switch-conflict>
            <p>目前有進行中的分析任務</p>
            <button data-switch-force-btn>立即切換（中斷任務）</button>
            <button data-switch-cancel-btn>取消</button>
          </div>
        `;
        switchSection.querySelector('[data-switch-force-btn]').addEventListener('click', () => {
          api.setProject(state.switchPath, true)
            .then(() => redirectFn('/wizard.html'))
            .catch(err => dispatch({ type: 'STATUS_ERROR', message: String(err) }));
        });
        switchSection.querySelector('[data-switch-cancel-btn]').addEventListener('click', () => {
          dispatch({ type: 'SWITCH_CANCEL' });
        });
      } else {
        switchSection.innerHTML = `
          <hr>
          <label>切換至其他專案
            <input type="text" data-switch-input placeholder="/absolute/path/to/project" value="${state.switchPath}">
          </label>
          <button data-switch-btn>切換</button>
        `;
        switchSection.querySelector('[data-switch-input]').addEventListener('input', e => {
          dispatch({ type: 'SWITCH_PATH_CHANGE', path: e.target.value });
        });
        switchSection.querySelector('[data-switch-btn]').addEventListener('click', () => {
          const path = switchSection.querySelector('[data-switch-input]').value;
          api.setProject(path, false)
            .then(result => {
              if (result.status === 'conflict') {
                dispatch({ type: 'SWITCH_CONFLICT', activeJobId: result.active_job_id });
              } else {
                redirectFn('/wizard.html');
              }
            })
            .catch(err => dispatch({ type: 'STATUS_ERROR', message: String(err) }));
        });
      }
      wrap.appendChild(switchSection);
```

**注意：** `api` 和 `redirectFn` 在 `renderPage` 的呼叫端已經傳入，但目前 `renderPage` signature 是 `renderPage(container, state, dispatch, redirectFn)`，沒有 `api`。需要在呼叫端加入，或用 closure。

最簡方式：將 `renderPage` 的 signature 改為接受 `api`：

```js
function renderPage(container, state, dispatch, redirectFn, api) {
```

並在 `initWizard` 裡所有 `renderPage(container, state, dispatch, redirectFn)` 呼叫改為 `renderPage(container, state, dispatch, redirectFn, api)`（共 2 處：`dispatch` 函式內和 bootstrap 末尾）。

- [ ] **Step 4: 確認所有 switch 測試通過 + 100% coverage**

```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-wizard.test.js --coverage 2>&1 | tail -15
```
期望：所有 PASSED，`ui-wizard.js` 100% coverage。

若 coverage 不足（常見於 `[data-switch-force-btn]` error path），加補充測試：

```js
  it('switch force error dispatches STATUS_ERROR', async () => {
    const api = {
      getStatus: vi.fn().mockResolvedValue({
        state: { has_snapshots: false, has_api_key: true },
        next_actions: [],
      }),
      postAnalyze: vi.fn(),
      getJobStatus: vi.fn(),
      setProject: vi.fn()
        .mockResolvedValueOnce({ status: 'conflict', active_job_id: 'j1', message: 'busy' })
        .mockRejectedValueOnce(new Error('network')),
    };
    const { initWizard } = await import('../js/ui-wizard.js');
    initWizard(container, api, vi.fn());
    await vi.waitFor(() => container.querySelector('[data-switch-input]'));
    container.querySelector('[data-switch-input]').value = '/new';
    container.querySelector('[data-switch-btn]').click();
    await vi.waitFor(() => container.querySelector('[data-switch-force-btn]'));
    container.querySelector('[data-switch-force-btn]').click();
    await vi.waitFor(() => container.querySelector('[data-page="PAGE_ERROR"]'));
  });

  it('switch btn error dispatches STATUS_ERROR', async () => {
    const api = {
      getStatus: vi.fn().mockResolvedValue({
        state: { has_snapshots: false, has_api_key: true },
        next_actions: [],
      }),
      postAnalyze: vi.fn(),
      getJobStatus: vi.fn(),
      setProject: vi.fn().mockRejectedValue(new Error('fail')),
    };
    const { initWizard } = await import('../js/ui-wizard.js');
    initWizard(container, api, vi.fn());
    await vi.waitFor(() => container.querySelector('[data-switch-input]'));
    container.querySelector('[data-switch-input]').value = '/new';
    container.querySelector('[data-switch-btn]').click();
    await vi.waitFor(() => container.querySelector('[data-page="PAGE_ERROR"]'));
  });
```

- [ ] **Step 5: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js
git commit -m "feat(switch): add switchProject UI to PAGE_ACTION with conflict handling"
```

- [ ] **Step 6: 確認全套測試（Python + JS）**

```bash
cd the_door && pytest tests/ -q 2>&1 | tail -5
cd docs/frontend-local-version-viewer/viewer && npx vitest run --coverage 2>&1 | tail -5
```
期望：Python 0 failed；JS wizard 100% coverage。
