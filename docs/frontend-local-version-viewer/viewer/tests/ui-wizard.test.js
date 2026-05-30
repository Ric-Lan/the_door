import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getInitialState,
  transition,
  parseExcludes,
  buildAnalyzeBody,
  stepIndexForCurrentStep,
  createApi,
  renderPage,
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
});

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
    expect(dl.querySelectorAll('dt').length).toBeGreaterThanOrEqual(2);
    expect(dl.querySelectorAll('dd').length).toBeGreaterThanOrEqual(2);
    expect(container.querySelector('[data-submit]').classList.contains('wizard-btn-primary')).toBe(true);
  });

  it('PROGRESS step list uses wizard-steplist + wizard-sl-row (phasebar)', async () => {
    vi.useFakeTimers();
    try {
      const steps = [
        { step_name: 'analyze_old', status: 'completed' },
        { step_name: 'analyze_new', status: 'running' },
      ];
      const api = {
        getStatus: vi.fn().mockResolvedValue({
          state: { has_snapshots: false, has_api_key: true },
          next_actions: [],
        }),
        postAnalyze: vi.fn().mockResolvedValue({ job_id: 'j' }),
        getJobStatus: vi.fn().mockResolvedValue({
          status: 'running', current_step: 'analyze_new', steps,
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
      // New phasebar structure
      expect(container.querySelector('.wizard-phasebar')).not.toBeNull();
      expect(container.querySelector('.wizard-steplist')).not.toBeNull();
      // 6 canonical step rows
      expect(container.querySelectorAll('.wizard-sl-row').length).toBe(6);
      // completed + running steps have correct data-step-status
      expect(container.querySelector('[data-step-status="completed"]')).not.toBeNull();
      expect(container.querySelector('[data-step-status="running"]')).not.toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it('PROGRESS fallback (no steps) renders 6 canonical pending rows via phasebar', async () => {
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
      // All 6 canonical steps should be rendered as pending rows
      const pendingRows = container.querySelectorAll('.wizard-sl-row[data-step-status="pending"]');
      expect(pendingRows.length).toBe(6);
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
    await vi.waitFor(() => expect(container.querySelector('[data-page="PAGE_ERROR"]')).not.toBeNull());
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

  it('calls redirectFn with /index.html when view is selected', async () => {
    vi.useFakeTimers();
    try {
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
      await vi.advanceTimersByTimeAsync(700);
      expect(redirectFn).toHaveBeenCalledWith('/index.html');
    } finally {
      vi.useRealTimers();
    }
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
    await vi.waitFor(() => container.querySelector('[data-action="analyze"]'));
    container.querySelector('[data-action="analyze"]').click();
    await vi.waitFor(() => container.querySelector('[data-page="PAGE_SETUP"]'));
    container.querySelector('[data-next="setup"]').click();
    await vi.waitFor(() => container.querySelector('[data-page="PAGE_LABEL"]'));
    container.querySelector('[data-next="label"]').click();
    await vi.waitFor(() => container.querySelector('[data-page="PAGE_CONFIRM"]'));
    container.querySelector('[data-submit]').click();
    await vi.waitFor(() => container.querySelector('[data-page="PROGRESS"]'));
    expect(api.postAnalyze).not.toHaveBeenCalled();
    expect(container.querySelector('[data-agent-params]')).not.toBeNull();
  });

  it('agent mode: copy button copies text', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    });
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
    await vi.waitFor(() => container.querySelector('[data-page="PAGE_SETUP"]'));
    container.querySelector('[data-next="setup"]').click();
    await vi.waitFor(() => container.querySelector('[data-page="PAGE_LABEL"]'));
    container.querySelector('[data-next="label"]').click();
    await vi.waitFor(() => container.querySelector('[data-page="PAGE_CONFIRM"]'));
    container.querySelector('[data-submit]').click();
    await vi.waitFor(() => container.querySelector('[data-copy]'));
    container.querySelector('[data-copy]').click();
    expect(writeText).toHaveBeenCalled();
  });

  it('agent mode: done button redirects to /index.html', async () => {
    vi.useFakeTimers();
    try {
      const redirectFn = vi.fn();
      const api = {
        getStatus: vi.fn().mockResolvedValue({
          state: { has_snapshots: false, has_api_key: false },
          next_actions: [],
        }),
        postAnalyze: vi.fn(),
        getJobStatus: vi.fn(),
      };
      const { initWizard } = await import('../js/ui-wizard.js');
      initWizard(container, api, redirectFn);
      await vi.waitFor(() => container.querySelector('[data-action="analyze"]'));
      container.querySelector('[data-action="analyze"]').click();
      await vi.waitFor(() => container.querySelector('[data-page="PAGE_SETUP"]'));
      container.querySelector('[data-next="setup"]').click();
      await vi.waitFor(() => container.querySelector('[data-page="PAGE_LABEL"]'));
      container.querySelector('[data-next="label"]').click();
      await vi.waitFor(() => container.querySelector('[data-page="PAGE_CONFIRM"]'));
      container.querySelector('[data-submit]').click();
      await vi.waitFor(() => container.querySelector('[data-done]'));
      container.querySelector('[data-done]').click();
      await vi.advanceTimersByTimeAsync(700);
      expect(redirectFn).toHaveBeenCalledWith('/index.html');
    } finally {
      vi.useRealTimers();
    }
  });

  it('renders PROGRESS step list when hasApiKey=true', async () => {
    vi.useFakeTimers();
    try {
      const steps = [{ step_name: 'analyze_new', status: 'running' }];
      const api = {
        getStatus: vi.fn().mockResolvedValue({
          state: { has_snapshots: false, has_api_key: true },
          next_actions: [],
        }),
        postAnalyze: vi.fn().mockResolvedValue({ job_id: 'job-abc' }),
        getJobStatus: vi.fn().mockResolvedValue({
          status: 'running', current_step: 'analyze_new', steps,
        }),
      };
      const { initWizard } = await import('../js/ui-wizard.js');
      initWizard(container, api, vi.fn());
      await Promise.resolve(); await Promise.resolve();
      expect(container.querySelector('[data-page="PAGE_ACTION"]')).not.toBeNull();
      container.querySelector('[data-action="analyze"]').click();
      expect(container.querySelector('[data-page="PAGE_SETUP"]')).not.toBeNull();
      container.querySelector('[data-next="setup"]').click();
      expect(container.querySelector('[data-page="PAGE_LABEL"]')).not.toBeNull();
      container.querySelector('[data-next="label"]').click();
      expect(container.querySelector('[data-page="PAGE_CONFIRM"]')).not.toBeNull();
      container.querySelector('[data-submit]').click();
      await Promise.resolve(); await Promise.resolve();
      expect(container.querySelector('[data-page="PROGRESS"]')).not.toBeNull();
      expect(container.querySelector('[data-agent-params]')).toBeNull();
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

  it('POLL_UPDATE done redirects to viewer', async () => {
    vi.useFakeTimers();
    try {
      const api = {
        getStatus: vi.fn().mockResolvedValue({
          state: { has_snapshots: false, has_api_key: true },
          next_actions: [],
        }),
        postAnalyze: vi.fn().mockResolvedValue({ job_id: 'job-done' }),
        getJobStatus: vi.fn().mockResolvedValue({
          status: 'done', current_step: null, steps: [],
        }),
      };
      const redirectFn = vi.fn();
      const { initWizard } = await import('../js/ui-wizard.js');
      initWizard(container, api, redirectFn);
      await Promise.resolve(); await Promise.resolve();
      container.querySelector('[data-action="analyze"]').click();
      container.querySelector('[data-next="setup"]').click();
      container.querySelector('[data-next="label"]').click();
      container.querySelector('[data-submit]').click();
      await Promise.resolve(); await Promise.resolve();
      // Interval fires at 1500ms; after getJobStatus resolves, redirectWithTransition
      // schedules a 620ms setTimeout. Total: 1500 + 620 = 2120ms.
      await vi.advanceTimersByTimeAsync(2200);
      expect(redirectFn).toHaveBeenCalledWith('/index.html');
    } finally {
      vi.useRealTimers();
    }
  });

  it('POLL_UPDATE failed goes to PAGE_ERROR via polling', async () => {
    vi.useFakeTimers();
    try {
      const api = {
        getStatus: vi.fn().mockResolvedValue({
          state: { has_snapshots: false, has_api_key: true },
          next_actions: [],
        }),
        postAnalyze: vi.fn().mockResolvedValue({ job_id: 'job-fail' }),
        getJobStatus: vi.fn().mockResolvedValue({
          status: 'failed', current_step: null, steps: [], error_message: '分析失敗',
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
      expect(container.querySelector('[data-page="PAGE_ERROR"]')).not.toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it('POLL_FAIL 3 times goes to PAGE_ERROR', async () => {
    vi.useFakeTimers();
    try {
      const api = {
        getStatus: vi.fn().mockResolvedValue({
          state: { has_snapshots: false, has_api_key: true },
          next_actions: [],
        }),
        postAnalyze: vi.fn().mockResolvedValue({ job_id: 'job-netfail' }),
        getJobStatus: vi.fn().mockRejectedValue(new Error('network error')),
      };
      const { initWizard } = await import('../js/ui-wizard.js');
      initWizard(container, api, vi.fn());
      await Promise.resolve(); await Promise.resolve();
      container.querySelector('[data-action="analyze"]').click();
      container.querySelector('[data-next="setup"]').click();
      container.querySelector('[data-next="label"]').click();
      container.querySelector('[data-submit]').click();
      await Promise.resolve(); await Promise.resolve();
      // 3 poll failures
      await vi.advanceTimersByTimeAsync(1500);
      await vi.advanceTimersByTimeAsync(1500);
      await vi.advanceTimersByTimeAsync(1500);
      expect(container.querySelector('[data-page="PAGE_ERROR"]')).not.toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it('postAnalyze failure goes to PAGE_ERROR', async () => {
    const api = {
      getStatus: vi.fn().mockResolvedValue({
        state: { has_snapshots: false, has_api_key: true },
        next_actions: [],
      }),
      postAnalyze: vi.fn().mockRejectedValue(new Error('submit failed')),
      getJobStatus: vi.fn(),
    };
    const { initWizard } = await import('../js/ui-wizard.js');
    initWizard(container, api, vi.fn());
    await vi.waitFor(() => container.querySelector('[data-action="analyze"]'));
    container.querySelector('[data-action="analyze"]').click();
    container.querySelector('[data-next="setup"]').click();
    container.querySelector('[data-next="label"]').click();
    container.querySelector('[data-submit]').click();
    await vi.waitFor(() => expect(container.querySelector('[data-page="PAGE_ERROR"]')).not.toBeNull());
  });

  it('transition default case returns same state', () => {
    const s = getInitialState();
    const result = transition(s, { type: 'UNKNOWN_ACTION' });
    expect(result).toBe(s);
  });

  it('uses default redirectFn (window.location.href) when not provided', async () => {
    // Cover the default parameter arrow function in initWizard
    vi.useFakeTimers();
    try {
      const api = {
        getStatus: vi.fn().mockResolvedValue({
          state: { has_snapshots: true, has_api_key: true },
          next_actions: [],
        }),
        postAnalyze: vi.fn(),
        getJobStatus: vi.fn(),
      };
      // Mock window.location
      const locationDescriptor = Object.getOwnPropertyDescriptor(window, 'location');
      delete window.location;
      window.location = { href: '' };
      const { initWizard: initWizard3 } = await import('../js/ui-wizard.js');
      initWizard3(container, api); // no redirectFn — uses default
      await vi.waitFor(() => container.querySelector('[data-action="view"]'));
      container.querySelector('[data-action="view"]').click();
      await vi.advanceTimersByTimeAsync(700);
      expect(window.location.href).toBe('/index.html');
      // restore
      if (locationDescriptor) Object.defineProperty(window, 'location', locationDescriptor);
    } finally {
      vi.useRealTimers();
    }
  });

  it('renders PAGE_ERROR with fallback "未知錯誤" when errorMessage is null', () => {
    // Cover the `state.errorMessage || '未知錯誤'` falsy branch in renderPage directly
    const state = { ...getInitialState(), page: 'PAGE_ERROR', errorMessage: null };
    const el = document.createElement('div');
    renderPage(el, state, () => {}, () => {}, { setProject: vi.fn() });
    expect(el.textContent).toMatch(/未知錯誤/);
  });

  it('PROGRESS with multiple steps renders completed/running/pending correctly', async () => {
    vi.useFakeTimers();
    try {
      const steps = [
        { step_name: 'analyze_old', status: 'completed' },
        { step_name: 'analyze_new', status: 'running' },
      ];
      const api = {
        getStatus: vi.fn().mockResolvedValue({
          state: { has_snapshots: false, has_api_key: true },
          next_actions: [],
        }),
        postAnalyze: vi.fn().mockResolvedValue({ job_id: 'job-multi' }),
        getJobStatus: vi.fn().mockResolvedValue({
          status: 'running', current_step: 'analyze_new', steps,
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
      // The completed step should have data-step-status="completed"
      expect(container.querySelector('[data-step-status="completed"]')).not.toBeNull();
      // The current step should be 'running'
      expect(container.querySelector('[data-step-status="running"]')).not.toBeNull();
      // Steps not yet started should be 'pending'
      expect(container.querySelector('[data-step-status="pending"]')).not.toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it('POLL_UPDATE with no steps from api uses empty array', async () => {

    vi.useFakeTimers();
    try {
      const api = {
        getStatus: vi.fn().mockResolvedValue({
          state: { has_snapshots: false, has_api_key: true },
          next_actions: [],
        }),
        postAnalyze: vi.fn().mockResolvedValue({ job_id: 'job-nosteps' }),
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
      // Should render PROGRESS with fallback pending li
      expect(container.querySelector('[data-page="PROGRESS"]')).not.toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

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

  it('switch input event dispatches SWITCH_PATH_CHANGE', async () => {
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
    const input = container.querySelector('[data-switch-input]');
    input.value = '/typed/path';
    input.dispatchEvent(new Event('input'));
    await vi.waitFor(() => {
      const i = container.querySelector('[data-switch-input]');
      return i && i.value === '/typed/path';
    });
  });
});

describe('PAGE_ACTION mode-note (spec §4.2 ⓐ)', () => {
  function mount(hasApiKey, hasSnapshots) {
    const c = document.createElement('div');
    renderPage(c, { ...getInitialState(), page: 'PAGE_ACTION', hasApiKey, hasSnapshots },
      () => {}, () => {}, { setProject: () => Promise.resolve({}) });
    return c;
  }

  it('renders .wizard-eyebrow with step 1 label', () => {
    const c = mount(true, false);
    const eb = c.querySelector('.wizard-eyebrow');
    expect(eb).not.toBeNull();
    expect(eb.textContent).toMatch(/步驟 1/);
  });

  it('renders .wizard-mode-note.api when hasApiKey=true', () => {
    const c = mount(true, false);
    const n = c.querySelector('.wizard-mode-note');
    expect(n).not.toBeNull();
    expect(n.classList.contains('api')).toBe(true);
    expect(n.classList.contains('agent')).toBe(false);
    expect(n.querySelector('.mn-badge').textContent).toMatch(/API/);
  });

  it('renders .wizard-mode-note.agent when hasApiKey=false', () => {
    const c = mount(false, false);
    const n = c.querySelector('.wizard-mode-note');
    expect(n.classList.contains('agent')).toBe(true);
    expect(n.classList.contains('api')).toBe(false);
    expect(n.querySelector('.mn-badge').textContent).toMatch(/Agent/);
  });

  it('mode-note appears in both has_snapshots=true and =false branches', () => {
    expect(mount(true, true).querySelector('.wizard-mode-note')).not.toBeNull();
    expect(mount(true, false).querySelector('.wizard-mode-note')).not.toBeNull();
  });
});

describe('PAGE_CONFIRM mode badge (spec §4.2 ⓓ)', () => {
  function mount(hasApiKey) {
    const c = document.createElement('div');
    renderPage(c, { ...getInitialState(), page: 'PAGE_CONFIRM', hasApiKey, action: 'analyze' },
      () => {}, () => {}, {});
    return c;
  }
  it('badge has .wizard-mode-badge.api when hasApiKey=true', () => {
    const c = mount(true);
    const b = c.querySelector('.wizard-mode-badge');
    expect(b).not.toBeNull();
    expect(b.classList.contains('api')).toBe(true);
    expect(b.textContent).toMatch(/API/);
  });
  it('badge has .wizard-mode-badge.agent when hasApiKey=false', () => {
    const c = mount(false);
    const b = c.querySelector('.wizard-mode-badge');
    expect(b.classList.contains('agent')).toBe(true);
    expect(b.textContent).toMatch(/Agent/);
  });
});

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
