# Task 02 — JS 邏輯：`ui-wizard.js` 狀態機 + 測試

> **依賴：** 無（可與 Task 01 平行）
> **注意：** vitest.config.js 已設定 100% coverage threshold，此 task 必須達到才能通過 CI。

**Files:**
- Create: `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`
- Create: `docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js`

**測試指令：**
```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run --coverage
```

---

## 模組設計（先讀再寫）

`ui-wizard.js` 導出純函式（易測試）+ 一個 controller factory：

```
export function getInitialState()           → WizardState
export function transition(state, action)   → WizardState  (pure)
export function parseExcludes(str)          → string[]     (pure)
export function buildAnalyzeBody(state)     → object       (pure)
export function stepIndexForCurrentStep(steps, currentStep) → number (pure)
export function createApi(fetchFn)          → { getStatus, postAnalyze, getJobStatus }
export function initWizard(container, api, redirectFn)  → void
```

`WizardState` 形狀：
```js
{
  page: 'LOADING' | 'PAGE_ACTION' | 'PAGE_SETUP' | 'PAGE_LABEL' | 'PAGE_CONFIRM' | 'SUBMITTING' | 'PROGRESS' | 'PAGE_ERROR',
  hasSnapshots: boolean,
  hasApiKey: boolean,
  projectPath: string,
  fileCount: number,
  action: 'analyze' | 'update' | 'view' | null,
  excludesRaw: string,
  label: string,
  jobId: string | null,
  jobStatus: 'running' | 'done' | 'failed' | null,
  currentStep: string | null,
  steps: Array<{step_name: string, status: string}>,
  errorMessage: string | null,
  pollFailCount: number,
}
```

---

## Task 02.1 — `getInitialState` + `transition` 狀態機

- [ ] **Step 1: 建立測試檔**

建立 `docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js`：

```js
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getInitialState,
  transition,
  parseExcludes,
  buildAnalyzeBody,
  stepIndexForCurrentStep,
  createApi,
} from '../js/ui-wizard.js';

describe('getInitialState', () => {
  it('returns LOADING page with all defaults', () => {
    const s = getInitialState();
    expect(s.page).toBe('LOADING');
    expect(s.action).toBeNull();
    expect(s.jobId).toBeNull();
    expect(s.pollFailCount).toBe(0);
  });
});

describe('transition: STATUS_LOADED', () => {
  it('transitions to PAGE_ACTION with has_snapshots=true', () => {
    const s = transition(getInitialState(), {
      type: 'STATUS_LOADED',
      hasSnapshots: true,
      hasApiKey: true,
      projectPath: '/my/proj',
      fileCount: 42,
    });
    expect(s.page).toBe('PAGE_ACTION');
    expect(s.hasSnapshots).toBe(true);
    expect(s.fileCount).toBe(42);
  });

  it('transitions to PAGE_ACTION with has_snapshots=false', () => {
    const s = transition(getInitialState(), {
      type: 'STATUS_LOADED',
      hasSnapshots: false,
      hasApiKey: false,
      projectPath: '/p',
      fileCount: 5,
    });
    expect(s.page).toBe('PAGE_ACTION');
    expect(s.hasSnapshots).toBe(false);
  });
});

describe('transition: SELECT_ACTION', () => {
  function stateWithSnapshots(has) {
    return transition(getInitialState(), {
      type: 'STATUS_LOADED', hasSnapshots: has,
      hasApiKey: true, projectPath: '/p', fileCount: 1,
    });
  }

  it('analyze action (no snapshots) goes to PAGE_SETUP', () => {
    const s = transition(stateWithSnapshots(false), { type: 'SELECT_ACTION', action: 'analyze' });
    expect(s.page).toBe('PAGE_SETUP');
    expect(s.action).toBe('analyze');
  });

  it('update action (has snapshots) goes to PAGE_CONFIRM', () => {
    const s = transition(stateWithSnapshots(true), { type: 'SELECT_ACTION', action: 'update' });
    expect(s.page).toBe('PAGE_CONFIRM');
    expect(s.action).toBe('update');
  });

  it('view action redirects (page stays PAGE_ACTION, action=view)', () => {
    const s = transition(stateWithSnapshots(true), { type: 'SELECT_ACTION', action: 'view' });
    expect(s.action).toBe('view');
    // redirect is handled outside transition; page doesn't change
    expect(s.page).toBe('PAGE_ACTION');
  });
});

describe('transition: PAGE_SETUP → PAGE_LABEL', () => {
  it('NEXT_FROM_SETUP goes to PAGE_LABEL with excludesRaw', () => {
    const base = {
      ...getInitialState(),
      page: 'PAGE_SETUP',
      action: 'analyze',
      hasSnapshots: false,
      hasApiKey: true,
    };
    const s = transition(base, { type: 'NEXT_FROM_SETUP', excludesRaw: 'tests/, docs/' });
    expect(s.page).toBe('PAGE_LABEL');
    expect(s.excludesRaw).toBe('tests/, docs/');
  });
});

describe('transition: PAGE_LABEL → PAGE_CONFIRM', () => {
  it('NEXT_FROM_LABEL goes to PAGE_CONFIRM with label', () => {
    const base = { ...getInitialState(), page: 'PAGE_LABEL', action: 'analyze' };
    const s = transition(base, { type: 'NEXT_FROM_LABEL', label: 'v1.0.0' });
    expect(s.page).toBe('PAGE_CONFIRM');
    expect(s.label).toBe('v1.0.0');
  });
});

describe('transition: SUBMIT → SUBMITTING / PROGRESS / ERROR', () => {
  it('SUBMIT goes to SUBMITTING', () => {
    const base = { ...getInitialState(), page: 'PAGE_CONFIRM', action: 'analyze' };
    const s = transition(base, { type: 'SUBMIT' });
    expect(s.page).toBe('SUBMITTING');
  });

  it('JOB_STARTED goes to PROGRESS with jobId', () => {
    const base = { ...getInitialState(), page: 'SUBMITTING' };
    const s = transition(base, { type: 'JOB_STARTED', jobId: 'abc123' });
    expect(s.page).toBe('PROGRESS');
    expect(s.jobId).toBe('abc123');
  });

  it('POLL_UPDATE with running keeps PROGRESS and updates steps', () => {
    const base = { ...getInitialState(), page: 'PROGRESS', jobId: 'x', pollFailCount: 0 };
    const steps = [{ step_name: '探索', status: 'done' }, { step_name: 'LLM', status: 'running' }];
    const s = transition(base, {
      type: 'POLL_UPDATE',
      status: 'running',
      currentStep: 'LLM',
      steps,
    });
    expect(s.page).toBe('PROGRESS');
    expect(s.currentStep).toBe('LLM');
    expect(s.steps).toEqual(steps);
    expect(s.pollFailCount).toBe(0);
  });

  it('POLL_UPDATE with done sets page to PROGRESS (redirect handled externally)', () => {
    const base = { ...getInitialState(), page: 'PROGRESS', jobId: 'x' };
    const s = transition(base, { type: 'POLL_UPDATE', status: 'done', currentStep: null, steps: [] });
    expect(s.jobStatus).toBe('done');
  });

  it('POLL_UPDATE with failed goes to PAGE_ERROR', () => {
    const base = { ...getInitialState(), page: 'PROGRESS', jobId: 'x' };
    const s = transition(base, {
      type: 'POLL_UPDATE', status: 'failed', currentStep: null, steps: [],
    });
    expect(s.page).toBe('PAGE_ERROR');
  });

  it('POLL_FAIL increments pollFailCount', () => {
    const base = { ...getInitialState(), page: 'PROGRESS', pollFailCount: 1 };
    const s = transition(base, { type: 'POLL_FAIL' });
    expect(s.pollFailCount).toBe(2);
  });

  it('POLL_FAIL at 3 goes to PAGE_ERROR', () => {
    const base = { ...getInitialState(), page: 'PROGRESS', pollFailCount: 2 };
    const s = transition(base, { type: 'POLL_FAIL' });
    expect(s.page).toBe('PAGE_ERROR');
  });
});

describe('transition: STATUS_ERROR', () => {
  it('STATUS_ERROR goes to PAGE_ERROR', () => {
    const s = transition(getInitialState(), {
      type: 'STATUS_ERROR', message: 'network fail',
    });
    expect(s.page).toBe('PAGE_ERROR');
    expect(s.errorMessage).toBe('network fail');
  });
});

describe('transition: SUBMIT_ERROR', () => {
  it('SUBMIT_ERROR goes to PAGE_ERROR', () => {
    const base = { ...getInitialState(), page: 'SUBMITTING' };
    const s = transition(base, { type: 'SUBMIT_ERROR', message: 'server error' });
    expect(s.page).toBe('PAGE_ERROR');
    expect(s.errorMessage).toBe('server error');
  });
});
```

- [ ] **Step 2: 建立 `ui-wizard.js` 骨架讓測試失敗（而非 import error）**

建立 `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`：

```js
export function getInitialState() { return {}; }
export function transition(state, action) { return state; }
export function parseExcludes(str) { return []; }
export function buildAnalyzeBody(state) { return {}; }
export function stepIndexForCurrentStep(steps, currentStep) { return -1; }
export function createApi(fetchFn) { return {}; }
export function initWizard(container, api, redirectFn) {}
```

- [ ] **Step 3: 確認測試失敗（不是 import error）**

```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-wizard.test.js 2>&1 | tail -20
```
期望：多個 FAIL，但無 `Cannot find module`。

- [ ] **Step 4: 實作 `getInitialState` + `transition`**

將 `ui-wizard.js` 完整替換為：

```js
// ─── State shape ────────────────────────────────────────────────────────────
export function getInitialState() {
  return {
    page: 'LOADING',
    hasSnapshots: false,
    hasApiKey: false,
    projectPath: '',
    fileCount: 0,
    action: null,
    excludesRaw: '',
    label: '',
    jobId: null,
    jobStatus: null,
    currentStep: null,
    steps: [],
    errorMessage: null,
    pollFailCount: 0,
  };
}

// ─── Pure state machine ──────────────────────────────────────────────────────
export function transition(state, action) {
  switch (action.type) {
    case 'STATUS_LOADED':
      return {
        ...state,
        page: 'PAGE_ACTION',
        hasSnapshots: action.hasSnapshots,
        hasApiKey: action.hasApiKey,
        projectPath: action.projectPath,
        fileCount: action.fileCount,
      };

    case 'STATUS_ERROR':
      return { ...state, page: 'PAGE_ERROR', errorMessage: action.message };

    case 'SELECT_ACTION': {
      const nextPage =
        action.action === 'analyze' ? 'PAGE_SETUP' :
        action.action === 'update'  ? 'PAGE_CONFIRM' :
        state.page; // 'view' — redirect handled externally
      return { ...state, page: nextPage, action: action.action };
    }

    case 'NEXT_FROM_SETUP':
      return { ...state, page: 'PAGE_LABEL', excludesRaw: action.excludesRaw };

    case 'NEXT_FROM_LABEL':
      return { ...state, page: 'PAGE_CONFIRM', label: action.label };

    case 'SUBMIT':
      return { ...state, page: 'SUBMITTING' };

    case 'SUBMIT_ERROR':
      return { ...state, page: 'PAGE_ERROR', errorMessage: action.message };

    case 'JOB_STARTED':
      return { ...state, page: 'PROGRESS', jobId: action.jobId };

    case 'POLL_UPDATE': {
      if (action.status === 'failed') {
        return { ...state, page: 'PAGE_ERROR', jobStatus: 'failed',
                 errorMessage: action.errorMessage || '分析失敗' };
      }
      return {
        ...state,
        jobStatus: action.status,
        currentStep: action.currentStep,
        steps: action.steps,
      };
    }

    case 'POLL_FAIL': {
      const newCount = state.pollFailCount + 1;
      if (newCount >= 3) {
        return { ...state, page: 'PAGE_ERROR', pollFailCount: newCount,
                 errorMessage: '分析可能仍在進行，請直接前往 Viewer 確認' };
      }
      return { ...state, pollFailCount: newCount };
    }

    default:
      return state;
  }
}
```

- [ ] **Step 5: 確認狀態機測試通過**

```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-wizard.test.js 2>&1 | grep -E "PASS|FAIL|✓|✗" | head -30
```
期望：所有 `describe('transition:...')` 和 `describe('getInitialState')` 通過。

- [ ] **Step 6: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js
git commit -m "feat(wizard): implement getInitialState and transition state machine with tests"
```

---

## Task 02.2 — `parseExcludes` + `buildAnalyzeBody`

- [ ] **Step 1: 在測試檔加測試**

在 `ui-wizard.test.js` 的最末加入：

```js
describe('parseExcludes', () => {
  it('comma-separated strings are trimmed', () => {
    expect(parseExcludes('tests/, docs/ , node_modules/')).toEqual(['tests/', 'docs/', 'node_modules/']);
  });

  it('empty string returns empty array', () => {
    expect(parseExcludes('')).toEqual([]);
  });

  it('whitespace-only string returns empty array', () => {
    expect(parseExcludes('   ')).toEqual([]);
  });

  it('single entry without comma', () => {
    expect(parseExcludes('tests/')).toEqual(['tests/']);
  });
});

describe('buildAnalyzeBody', () => {
  it('includes extra_ignore when excludesRaw is non-empty', () => {
    const state = { ...getInitialState(), excludesRaw: 'tests/', label: 'v1.0.0', action: 'analyze' };
    const body = buildAnalyzeBody(state);
    expect(body.extra_ignore).toEqual(['tests/']);
    expect(body.label).toBe('v1.0.0');
  });

  it('omits extra_ignore when excludesRaw is empty', () => {
    const state = { ...getInitialState(), excludesRaw: '', label: '', action: 'analyze' };
    const body = buildAnalyzeBody(state);
    expect(body.extra_ignore).toBeUndefined();
  });

  it('omits label when label is empty string', () => {
    const state = { ...getInitialState(), excludesRaw: '', label: '', action: 'analyze' };
    const body = buildAnalyzeBody(state);
    expect(body.label).toBeUndefined();
  });
});
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-wizard.test.js -t "parseExcludes|buildAnalyzeBody" 2>&1 | tail -10
```
期望：FAILED。

- [ ] **Step 3: 實作 `parseExcludes` + `buildAnalyzeBody`**

在 `ui-wizard.js` 的 `transition` 之後加入：

```js
// ─── Pure helpers ────────────────────────────────────────────────────────────
export function parseExcludes(str) {
  if (!str || !str.trim()) return [];
  return str.split(',').map(s => s.trim()).filter(Boolean);
}

export function buildAnalyzeBody(state) {
  const body = {};
  const excludes = parseExcludes(state.excludesRaw);
  if (excludes.length > 0) body.extra_ignore = excludes;
  if (state.label && state.label.trim()) body.label = state.label.trim();
  return body;
}
```

- [ ] **Step 4: 確認測試通過**

```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-wizard.test.js -t "parseExcludes|buildAnalyzeBody" 2>&1 | tail -5
```
期望：全部 PASSED。

- [ ] **Step 5: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js
git commit -m "feat(wizard): add parseExcludes and buildAnalyzeBody helpers with tests"
```

---

## Task 02.3 — `stepIndexForCurrentStep` + `createApi`

- [ ] **Step 1: 在測試檔加測試**

```js
describe('stepIndexForCurrentStep', () => {
  const steps = [
    { step_name: '探索檔案', status: 'done' },
    { step_name: 'LLM 分析', status: 'running' },
    { step_name: '寫入快照', status: 'pending' },
  ];

  it('returns index of running step by currentStep name', () => {
    expect(stepIndexForCurrentStep(steps, 'LLM 分析')).toBe(1);
  });

  it('returns -1 when currentStep is null', () => {
    expect(stepIndexForCurrentStep(steps, null)).toBe(-1);
  });

  it('returns -1 when currentStep not in steps', () => {
    expect(stepIndexForCurrentStep(steps, 'nonexistent')).toBe(-1);
  });
});

describe('createApi', () => {
  it('getStatus calls GET /api/status and returns json', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ state: { has_snapshots: true, has_api_key: false }, next_actions: [] }),
    });
    const api = createApi(mockFetch);
    const result = await api.getStatus();
    expect(mockFetch).toHaveBeenCalledWith('/api/status');
    expect(result.state.has_snapshots).toBe(true);
  });

  it('postAnalyze calls POST /api/analyze with body', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ job_id: 'abc' }),
    });
    const api = createApi(mockFetch);
    const result = await api.postAnalyze({ label: 'v1' });
    expect(mockFetch).toHaveBeenCalledWith('/api/analyze', expect.objectContaining({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label: 'v1' }),
    }));
    expect(result.job_id).toBe('abc');
  });

  it('getJobStatus calls GET /api/update/status/<jobId>', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'running', current_step: 'LLM', steps: [] }),
    });
    const api = createApi(mockFetch);
    const result = await api.getJobStatus('job-123');
    expect(mockFetch).toHaveBeenCalledWith('/api/update/status/job-123');
    expect(result.status).toBe('running');
  });

  it('getStatus throws when response not ok', async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const api = createApi(mockFetch);
    await expect(api.getStatus()).rejects.toThrow();
  });

  it('postAnalyze throws when response not ok', async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: false, status: 409 });
    const api = createApi(mockFetch);
    await expect(api.postAnalyze({})).rejects.toThrow();
  });

  it('getJobStatus throws when response not ok', async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: false, status: 404 });
    const api = createApi(mockFetch);
    await expect(api.getJobStatus('x')).rejects.toThrow();
  });
});
```

- [ ] **Step 2: 實作 `stepIndexForCurrentStep` + `createApi`**

在 `ui-wizard.js` 的 `buildAnalyzeBody` 之後加入：

```js
export function stepIndexForCurrentStep(steps, currentStep) {
  if (!currentStep) return -1;
  return steps.findIndex(s => s.step_name === currentStep);
}

export function createApi(fetchFn = window.fetch.bind(window)) {
  async function _check(resp) {
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  }
  return {
    getStatus() {
      return fetchFn('/api/status').then(_check);
    },
    postAnalyze(body) {
      return fetchFn('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }).then(_check);
    },
    getJobStatus(jobId) {
      return fetchFn(`/api/update/status/${jobId}`).then(_check);
    },
  };
}
```

- [ ] **Step 3: 確認全部測試通過**

```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-wizard.test.js 2>&1 | tail -5
```
期望：全部 PASSED，0 failed。

- [ ] **Step 4: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js
git commit -m "feat(wizard): add stepIndexForCurrentStep and createApi with full test coverage"
```

---

## Task 02.4 — `initWizard` controller（含 agent 模式）

> `initWizard` 是副作用 controller，測試用 spy/mock DOM。

- [ ] **Step 1: 在測試檔加測試**

```js
describe('initWizard', () => {
  let container;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  afterEach(() => {
    document.body.removeChild(container);
    vi.restoreAllMocks();
  });

  it('calls getStatus on init', async () => {
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
    await vi.waitFor(() => expect(api.getStatus).toHaveBeenCalled());
  });

  it('renders PAGE_ACTION after status loaded', async () => {
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
    await vi.waitFor(() => expect(container.querySelector('[data-page="PAGE_ACTION"]')).not.toBeNull());
  });

  it('calls redirectFn with /index.html when view is selected', async () => {
    const api = {
      getStatus: vi.fn().mockResolvedValue({
        state: { has_snapshots: true, has_api_key: true },
        next_actions: [],
      }),
      postAnalyze: vi.fn(),
      getJobStatus: vi.fn(),
    };
    const redirectFn = vi.fn();
    const { initWizard } = await import('../js/ui-wizard.js');
    initWizard(container, api, redirectFn);
    await vi.waitFor(() => expect(container.querySelector('[data-action="view"]')).not.toBeNull());
    container.querySelector('[data-action="view"]').click();
    expect(redirectFn).toHaveBeenCalledWith('/index.html');
  });

  it('agent mode: shows params block without calling postAnalyze', async () => {
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
    // Get to confirm page: select analyze, skip setup, skip label, confirm
    await vi.waitFor(() => container.querySelector('[data-action="analyze"]'));
    container.querySelector('[data-action="analyze"]').click();
    await vi.waitFor(() => container.querySelector('[data-page="PAGE_SETUP"]'));
    container.querySelector('[data-next="setup"]').click();
    await vi.waitFor(() => container.querySelector('[data-page="PAGE_LABEL"]'));
    container.querySelector('[data-next="label"]').click();
    await vi.waitFor(() => container.querySelector('[data-page="PAGE_CONFIRM"]'));
    container.querySelector('[data-submit]').click();
    // Should NOT call postAnalyze in agent mode
    await vi.waitFor(() => container.querySelector('[data-page="PROGRESS"]'));
    expect(api.postAnalyze).not.toHaveBeenCalled();
    expect(container.querySelector('[data-agent-params]')).not.toBeNull();
  });

  it('renders PROGRESS step list when hasApiKey=true', async () => {
    // fake timers required: setInterval(1500) must fire to get non-empty steps into DOM
    // vi.waitFor is NOT used here because its internal polling is also frozen by fake timers
    vi.useFakeTimers();
    try {
      const steps = [{ step_name: 'LLM 分析', status: 'running' }];
      const api = {
        getStatus: vi.fn().mockResolvedValue({
          state: { has_snapshots: false, has_api_key: true },
          next_actions: [],
        }),
        postAnalyze: vi.fn().mockResolvedValue({ job_id: 'job-abc' }),
        getJobStatus: vi.fn().mockResolvedValue({
          status: 'running', current_step: 'LLM 分析', steps,
        }),
      };
      const { initWizard } = await import('../js/ui-wizard.js');
      initWizard(container, api, vi.fn());
      await Promise.resolve(); await Promise.resolve(); // flush getStatus microtask chain
      expect(container.querySelector('[data-page="PAGE_ACTION"]')).not.toBeNull();
      container.querySelector('[data-action="analyze"]').click();
      expect(container.querySelector('[data-page="PAGE_SETUP"]')).not.toBeNull();
      container.querySelector('[data-next="setup"]').click();
      expect(container.querySelector('[data-page="PAGE_LABEL"]')).not.toBeNull();
      container.querySelector('[data-next="label"]').click();
      expect(container.querySelector('[data-page="PAGE_CONFIRM"]')).not.toBeNull();
      container.querySelector('[data-submit]').click();
      await Promise.resolve(); await Promise.resolve(); // flush postAnalyze → JOB_STARTED
      expect(container.querySelector('[data-page="PROGRESS"]')).not.toBeNull();
      expect(container.querySelector('[data-agent-params]')).toBeNull();
      // Advance time to fire setInterval(1500) → getJobStatus → POLL_UPDATE → re-render with steps
      await vi.advanceTimersByTimeAsync(1500);
      expect(container.querySelector('[data-step-status="running"]')).not.toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it('renders PAGE_ERROR when getStatus fails', async () => {
    const api = {
      getStatus: vi.fn().mockRejectedValue(new Error('network fail')),
      postAnalyze: vi.fn(),
      getJobStatus: vi.fn(),
    };
    const { initWizard } = await import('../js/ui-wizard.js');
    initWizard(container, api, vi.fn());
    await vi.waitFor(() => expect(container.querySelector('[data-page="PAGE_ERROR"]')).not.toBeNull());
    expect(container.querySelector('[data-page="PAGE_ERROR"]').textContent).toMatch(/network fail/);
  });
});
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-wizard.test.js -t "initWizard" 2>&1 | tail -10
```

- [ ] **Step 3: 實作 `initWizard`**

在 `ui-wizard.js` 最後加入：

```js
// ─── DOM renderer ────────────────────────────────────────────────────────────
function renderPage(container, state, dispatch, redirectFn) {
  container.innerHTML = '';
  const wrap = document.createElement('div');
  wrap.setAttribute('data-page', state.page);

  switch (state.page) {
    case 'LOADING':
      wrap.innerHTML = '<p>載入中…</p>';
      break;

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
      wrap.querySelectorAll('[data-action]').forEach(btn => {
        if (!btn.disabled) {
          btn.addEventListener('click', () => {
            const act = btn.getAttribute('data-action');
            if (act === 'view') { redirectFn('/index.html'); return; }
            dispatch({ type: 'SELECT_ACTION', action: act });
          });
        }
      });
      break;

    case 'PAGE_SETUP':
      wrap.innerHTML = `
        <h2>設定分析範圍</h2>
        <p>偵測到 ${state.fileCount} 個源碼檔案。</p>
        <label>排除目錄（逗號分隔，選填）：
          <input type="text" data-excludes placeholder="tests/, docs/" value="${state.excludesRaw}">
        </label>
        <button data-next="setup">下一步</button>
      `;
      wrap.querySelector('[data-next="setup"]').addEventListener('click', () => {
        const raw = wrap.querySelector('[data-excludes]').value;
        dispatch({ type: 'NEXT_FROM_SETUP', excludesRaw: raw });
      });
      break;

    case 'PAGE_LABEL':
      wrap.innerHTML = `
        <h2>快照標籤</h2>
        <label>版本標籤（選填）：
          <input type="text" data-label placeholder="v1.0.0" value="${state.label}">
        </label>
        <button data-next="label">下一步</button>
      `;
      wrap.querySelector('[data-next="label"]').addEventListener('click', () => {
        const lbl = wrap.querySelector('[data-label]').value;
        dispatch({ type: 'NEXT_FROM_LABEL', label: lbl });
      });
      break;

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

    case 'SUBMITTING':
      wrap.innerHTML = '<p>送出中…</p>';
      break;

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

    case 'PAGE_ERROR':
      wrap.innerHTML = `
        <h2>發生錯誤</h2>
        <p>${state.errorMessage || '未知錯誤'}</p>
        <a href="/index.html">前往 Viewer</a>
      `;
      break;
  }

  container.appendChild(wrap);
}

// ─── Controller ──────────────────────────────────────────────────────────────
export function initWizard(container, api, redirectFn = (url) => { window.location.href = url; }) {
  let state = getInitialState();

  function dispatch(action) {
    state = transition(state, action);
    renderPage(container, state, dispatch, redirectFn);
    handleSideEffects(state, action);
  }

  function handleSideEffects(state, action) {
    if (action.type === 'SUBMIT') {
      if (!state.hasApiKey) {
        // Agent mode: skip API call, go straight to PROGRESS
        dispatch({ type: 'JOB_STARTED', jobId: null });
        return;
      }
      const body = buildAnalyzeBody(state);
      api.postAnalyze(body)
        .then(data => dispatch({ type: 'JOB_STARTED', jobId: data.job_id }))
        .catch(err => dispatch({ type: 'SUBMIT_ERROR', message: String(err) }));
    }

    if (action.type === 'JOB_STARTED' && state.jobId) {
      startPolling(state.jobId);
    }
  }

  function startPolling(jobId) {
    const timer = setInterval(async () => {
      try {
        const data = await api.getJobStatus(jobId);
        dispatch({ type: 'POLL_UPDATE', status: data.status,
                   currentStep: data.current_step, steps: data.steps || [],
                   errorMessage: data.error_message });
        if (data.status === 'done') {
          clearInterval(timer);
          redirectFn('/index.html');
        }
        if (data.status === 'failed') clearInterval(timer);
      } catch {
        dispatch({ type: 'POLL_FAIL' });
        if (state.pollFailCount >= 3) clearInterval(timer);
      }
    }, 1500);
  }

  // Bootstrap
  api.getStatus()
    .then(data => {
      dispatch({
        type: 'STATUS_LOADED',
        hasSnapshots: data.state.has_snapshots,
        hasApiKey: data.state.has_api_key,
        projectPath: data.state.project_path || '',
        fileCount: data.state.file_count || 0,
      });
    })
    .catch(err => dispatch({ type: 'STATUS_ERROR', message: String(err) }));

  renderPage(container, state, dispatch, redirectFn);
}
```

- [ ] **Step 4: 確認全部測試通過 + coverage**

```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run --coverage 2>&1 | tail -15
```
期望：所有 test PASSED，coverage 100%（lines/functions/branches/statements）。

- [ ] **Step 5: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js
git commit -m "feat(wizard): implement initWizard controller with DOM rendering and agent mode"
```
