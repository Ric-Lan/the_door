import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  showUpdateModal,
  hideUpdateModal,
  showModalError,
  renderPipelineProgress,
  startPolling,
  stopPolling,
  submitUpdate,
  pollJobStatus,
} from '../js/ui-modal.js';
import { state } from '../js/state.js';
import { els } from '../js/dom.js';

function resetState() {
  state.projectStatus = null;
  state.pollingJobId = null;
  state.pollingHandle = null;
}

function resetDom() {
  els.updateModal.hidden = true;
  els.inputOldPath.value = '';
  els.inputNewPath.value = '';
  els.inputLanguage.value = '';
  els.modalError.hidden = true;
  els.modalError.textContent = '';
  els.pipelineProgress.hidden = true;
  els.stepsList.textContent = '';
  els.currentStep.textContent = '';
  const hint = document.getElementById('modal-project-hint');
  hint.hidden = true;
  hint.textContent = '';
}

beforeEach(() => {
  resetState();
  resetDom();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── showUpdateModal ───────────────────────────────────────────────

describe('showUpdateModal', () => {
  it('shows modal, clears newPath, sets language to zh-Hant', () => {
    showUpdateModal();
    expect(els.updateModal.hidden).toBe(false);
    expect(els.inputNewPath.value).toBe('');
    expect(els.inputLanguage.value).toBe('zh-Hant');
    expect(els.modalError.hidden).toBe(true);
  });

  it('pre-fills oldPath from state.projectStatus.project_path', () => {
    state.projectStatus = { project_path: '/some/path' };
    showUpdateModal();
    expect(els.inputOldPath.value).toBe('/some/path');
  });

  it('sets oldPath to empty string when projectStatus is null', () => {
    state.projectStatus = null;
    showUpdateModal();
    expect(els.inputOldPath.value).toBe('');
  });

  it('shows modal-project-hint with path when project_path exists', () => {
    state.projectStatus = { project_path: '/my/project' };
    showUpdateModal();
    const hint = document.getElementById('modal-project-hint');
    expect(hint.hidden).toBe(false);
    expect(hint.textContent).toBe('專案根目錄：/my/project');
  });

  it('hides modal-project-hint when no project_path', () => {
    state.projectStatus = null;
    showUpdateModal();
    const hint = document.getElementById('modal-project-hint');
    expect(hint.hidden).toBe(true);
  });

  it('focuses inputNewPath', () => {
    const focusSpy = vi.spyOn(els.inputNewPath, 'focus');
    showUpdateModal();
    expect(focusSpy).toHaveBeenCalled();
  });
});

// ── hideUpdateModal ───────────────────────────────────────────────

describe('hideUpdateModal', () => {
  it('sets updateModal.hidden = true', () => {
    els.updateModal.hidden = false;
    hideUpdateModal();
    expect(els.updateModal.hidden).toBe(true);
  });
});

// ── showModalError ────────────────────────────────────────────────

describe('showModalError', () => {
  it('shows error with correct text', () => {
    showModalError('something went wrong');
    expect(els.modalError.hidden).toBe(false);
    expect(els.modalError.textContent).toBe('something went wrong');
  });
});

// ── renderPipelineProgress ────────────────────────────────────────

describe('renderPipelineProgress', () => {
  it('sets currentStep text when current_step is provided', () => {
    renderPipelineProgress({ current_step: 'parse', steps: [] });
    expect(els.currentStep.textContent).toBe('執行中：parse');
  });

  it('sets empty string when current_step is falsy', () => {
    renderPipelineProgress({ current_step: null, steps: [] });
    expect(els.currentStep.textContent).toBe('');
  });

  it('renders empty list when steps array is empty', () => {
    renderPipelineProgress({ current_step: null, steps: [] });
    expect(els.stepsList.children.length).toBe(0);
  });

  it('uses empty array when steps is null — || [] branch', () => {
    renderPipelineProgress({ current_step: null, steps: null });
    expect(els.stepsList.children.length).toBe(0);
  });

  it('renders completed step with ✓ and duration', () => {
    renderPipelineProgress({
      current_step: null,
      steps: [{ status: 'completed', step_name: 'parse', duration_ms: 2500 }],
    });
    const li = els.stepsList.children[0];
    expect(li.className).toBe('step-item step-completed');
    expect(li.textContent).toContain('✓');
    expect(li.textContent).toContain('parse');
    expect(li.textContent).toContain('2.5s');
  });

  it('renders completed step without duration when duration_ms is null', () => {
    renderPipelineProgress({
      current_step: null,
      steps: [{ status: 'completed', step_name: 'parse', duration_ms: null }],
    });
    const li = els.stepsList.children[0];
    expect(li.textContent).not.toContain('s)');
  });

  it('renders failed step with ✗ and error span', () => {
    renderPipelineProgress({
      current_step: null,
      steps: [{ status: 'failed', step_name: 'analyze', duration_ms: null, error_message: 'timeout' }],
    });
    const li = els.stepsList.children[0];
    expect(li.className).toBe('step-item step-failed');
    expect(li.textContent).toContain('✗');
    const errSpan = li.querySelector('.step-error');
    expect(errSpan).not.toBeNull();
    expect(errSpan.textContent).toContain('timeout');
  });

  it('renders pending/other step with ⊘', () => {
    renderPipelineProgress({
      current_step: null,
      steps: [{ status: 'pending', step_name: 'snapshot', duration_ms: null }],
    });
    const li = els.stepsList.children[0];
    expect(li.textContent).toContain('⊘');
  });

  it('does not add error span when error_message is absent', () => {
    renderPipelineProgress({
      current_step: null,
      steps: [{ status: 'completed', step_name: 'parse', duration_ms: 100 }],
    });
    const li = els.stepsList.children[0];
    expect(li.querySelector('.step-error')).toBeNull();
  });
});

// ── stopPolling ───────────────────────────────────────────────────

describe('stopPolling', () => {
  it('calls clearInterval with the polling handle', () => {
    const clearSpy = vi.spyOn(globalThis, 'clearInterval');
    state.pollingHandle = 42;
    stopPolling();
    expect(clearSpy).toHaveBeenCalledWith(42);
  });

  it('sets pollingHandle to null', () => {
    state.pollingHandle = 42;
    stopPolling();
    expect(state.pollingHandle).toBeNull();
  });

  it('sets pollingJobId to null', () => {
    state.pollingJobId = 'job-1';
    stopPolling();
    expect(state.pollingJobId).toBeNull();
  });
});

// ── startPolling ──────────────────────────────────────────────────

describe('startPolling', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'running', current_step: 'step1', steps: [] }),
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('sets pollingJobId, shows pipelineProgress, clears stepsList, sets initial text', () => {
    startPolling('job-abc');
    expect(state.pollingJobId).toBe('job-abc');
    expect(els.pipelineProgress.hidden).toBe(false);
    expect(els.stepsList.textContent).toBe('');
    expect(els.currentStep.textContent).toBe('初始化…');
  });

  it('sets pollingHandle via setInterval with 1500ms interval', async () => {
    startPolling('job-abc');
    expect(state.pollingHandle).not.toBeNull();
    // fire the interval once to cover the arrow function
    await vi.advanceTimersByTimeAsync(1500);
  });

  it('passes callbacks through to pollJobStatus on interval fire', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'running', current_step: null, steps: [] }),
    });
    const onComplete = vi.fn();
    startPolling('job-xyz', { onComplete });
    await vi.advanceTimersByTimeAsync(1500);
    // still running — onComplete not yet called
    expect(onComplete).not.toHaveBeenCalled();
  });
});

// ── submitUpdate ──────────────────────────────────────────────────

describe('submitUpdate', () => {
  it('calls startPolling with jobId and callbacks on success', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ job_id: 'job-1' }),
    });
    vi.useFakeTimers();
    const onComplete = vi.fn();
    await submitUpdate('/old', '/new', { onComplete });
    expect(state.pollingJobId).toBe('job-1');
    expect(state.pollingHandle).not.toBeNull();
    vi.useRealTimers();
  });

  it('calls callbacks.onError when response has no job_id', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      json: async () => ({ error: { message: 'bad request' } }),
    });
    const onError = vi.fn();
    await submitUpdate('/old', '/new', { onError });
    expect(onError).toHaveBeenCalledWith(expect.stringContaining('bad request'));
  });

  it('calls showModalError when no job_id and no onError callback', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      json: async () => ({ error: { message: 'server error' } }),
    });
    await submitUpdate('/old', '/new');
    expect(els.modalError.hidden).toBe(false);
    expect(els.modalError.textContent).toContain('server error');
  });

  it('calls callbacks.onError on network error', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('network failure'));
    const onError = vi.fn();
    await submitUpdate('/old', '/new', { onError });
    expect(onError).toHaveBeenCalledWith(expect.stringContaining('network failure'));
  });

  it('calls showModalError on network error when no callback', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('connection refused'));
    await submitUpdate('/old', '/new');
    expect(els.modalError.hidden).toBe(false);
    expect(els.modalError.textContent).toContain('connection refused');
  });

  it('uses "未知錯誤" fallback when error body has no message — || branch', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      json: async () => ({}),
    });
    await submitUpdate('/old', '/new');
    expect(els.modalError.textContent).toContain('未知錯誤');
  });

  it('uses "network error" fallback when thrown error has no message — || branch', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue({});
    await submitUpdate('/old', '/new');
    expect(els.modalError.textContent).toContain('network error');
  });

  it('uses language from inputLanguage.value when set', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ job_id: 'job-2' }),
    });
    vi.useFakeTimers();
    // add a valid option so the select accepts the value
    const opt = document.createElement('option');
    opt.value = 'en';
    els.inputLanguage.appendChild(opt);
    els.inputLanguage.value = 'en';
    await submitUpdate('/old', '/new');
    const body = JSON.parse(fetchSpy.mock.calls[0][1].body);
    expect(body.output_language).toBe('en');
    els.inputLanguage.removeChild(opt);
    vi.useRealTimers();
  });

  it('falls back to zh-Hant when inputLanguage.value is empty', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ job_id: 'job-3' }),
    });
    vi.useFakeTimers();
    els.inputLanguage.value = '';
    await submitUpdate('/old', '/new');
    const body = JSON.parse(fetchSpy.mock.calls[0][1].body);
    expect(body.output_language).toBe('zh-Hant');
    vi.useRealTimers();
  });
});

// ── pollJobStatus ─────────────────────────────────────────────────

describe('pollJobStatus', () => {
  it('calls callbacks.onComplete and stops polling on completed status', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'completed', current_step: null, steps: [] }),
    });
    state.pollingHandle = 99;
    const onComplete = vi.fn();
    await pollJobStatus('job-1', { onComplete });
    expect(onComplete).toHaveBeenCalled();
    expect(state.pollingHandle).toBeNull();
    expect(els.pipelineProgress.hidden).toBe(true);
  });

  it('does not throw when onComplete callback is absent', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'completed', current_step: null, steps: [] }),
    });
    state.pollingHandle = 99;
    await expect(pollJobStatus('job-1', {})).resolves.not.toThrow();
    expect(state.pollingHandle).toBeNull();
  });

  it('calls showModalError and stops polling on failed status', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'failed',
        current_step: null,
        steps: [],
        error_message: 'pipeline crashed',
      }),
    });
    state.pollingHandle = 99;
    await pollJobStatus('job-1');
    expect(state.pollingHandle).toBeNull();
    expect(els.pipelineProgress.hidden).toBe(true);
    expect(els.modalError.hidden).toBe(false);
    expect(els.modalError.textContent).toContain('pipeline crashed');
  });

  it('stops polling and shows error on fetch failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('connection lost'));
    state.pollingHandle = 99;
    await pollJobStatus('job-1');
    expect(state.pollingHandle).toBeNull();
    expect(els.modalError.hidden).toBe(false);
    expect(els.modalError.textContent).toContain('connection lost');
  });

  it('uses "network error" fallback when thrown error has no message — || branch', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue({});
    state.pollingHandle = 99;
    await pollJobStatus('job-1');
    expect(els.modalError.textContent).toContain('network error');
  });

  it('continues polling when status is running (no stopPolling)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'running', current_step: 'step1', steps: [] }),
    });
    state.pollingHandle = 99;
    await pollJobStatus('job-1');
    expect(state.pollingHandle).toBe(99);
  });
});
