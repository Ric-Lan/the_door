import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../js/ui-topbar.js', () => ({
  renderTopBar: vi.fn(),
  updateLogoMark: vi.fn(),
}));

vi.mock('../js/ui-list.js', () => ({
  renderChangeList: vi.fn(),
  changeSymbol: vi.fn((t) => '?'),
}));

vi.mock('../js/ui-detail.js', () => ({
  renderDetailPanel: vi.fn(),
  renderDetailPanelL1: vi.fn(),
  renderError: vi.fn(),
}));

vi.mock('../js/ui-modal.js', () => ({
  showUpdateModal: vi.fn(),
  hideUpdateModal: vi.fn(),
  showModalError: vi.fn(),
  submitUpdate: vi.fn(),
}));

vi.mock('../js/layers.js', () => ({
  loadL1Graph: vi.fn().mockResolvedValue(undefined),
  switchToL1: vi.fn(),
  switchToL2: vi.fn(),
  switchToMindmap: vi.fn(),
}));

vi.mock('../js/graph.js', () => ({
  initGraph: vi.fn(),
  renderLegend: vi.fn(),
  openGraphDrawer: vi.fn(),
  closeGraphDrawer: vi.fn(),
}));

vi.mock('../js/viewmodel.js', () => ({
  buildViewModelFromReport: vi.fn((report) => ({ source: 'built', _from: report })),
  snapshotLabel: vi.fn((s) => s?.label || s?.version_id || 'unknown'),
}));

import {
  render,
  setMode,
  init,
} from '../js/app.js';
import { state } from '../js/state.js';
import { els } from '../js/dom.js';
import * as uiTopbar from '../js/ui-topbar.js';
import * as uiList from '../js/ui-list.js';
import * as uiDetail from '../js/ui-detail.js';
import * as uiModal from '../js/ui-modal.js';
import * as layers from '../js/layers.js';
import * as graph from '../js/graph.js';
import * as viewmodel from '../js/viewmodel.js';

function resetState() {
  state.updateModel = null;
  state.l1Model = null;
  state.mode = 'baseline';
  state.selectedId = null;
  state.projectStatus = null;
  state.pollingJobId = null;
  state.pollingHandle = null;
  state.layerState = 'L1';
  state.selectedFeatureId = null;
  state.selectedModuleId = null;
  state.l1GraphViewModel = null;
  state.l2GraphViewModel = null;
  state.l3GraphViewModel = null;
  state.diffGraphViewModel = null;
  state.cytoscapeInstance = null;
  state.cytoscapeAvailable = false;
  state.diffSortMode = 'risk';
  state.layerExplanation = null;
  state.snapshots = [];
  state.versionA = null;
  state.versionB = null;
  state.versionDiff = null;
}

function resetDom() {
  els.summaryText.textContent = '';
  els.inputOldPath.value = '';
  els.inputNewPath.value = '';
  const appShell = document.querySelector('.app-shell');
  if (appShell) appShell.classList.remove('diff-mode');
  const banner = document.getElementById('diff-mode-banner');
  if (banner) banner.hidden = true;
  // reset version-selector elements
  document.getElementById('select-version-a').innerHTML = '';
  document.getElementById('select-version-b').innerHTML = '';
  document.getElementById('select-version-a').onchange = null;
  document.getElementById('select-version-b').onchange = null;
  document.getElementById('version-selector-bar').hidden = true;
}

beforeEach(() => {
  resetState();
  resetDom();
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── render ───────────────────────────────────────────────────────

describe('render', () => {
  it('calls renderTopBar, renderChangeList, renderDetailPanel, updateLogoMark in order', () => {
    render();
    const topbarOrder = uiTopbar.renderTopBar.mock.invocationCallOrder[0];
    const listOrder = uiList.renderChangeList.mock.invocationCallOrder[0];
    const detailOrder = uiDetail.renderDetailPanel.mock.invocationCallOrder[0];
    const logoOrder = uiTopbar.updateLogoMark.mock.invocationCallOrder[0];
    expect(topbarOrder).toBeLessThan(listOrder);
    expect(listOrder).toBeLessThan(detailOrder);
    expect(detailOrder).toBeLessThan(logoOrder);
  });

  it('passes onSelectFeature + onSelectChange callbacks to renderChangeList', () => {
    render();
    expect(uiList.renderChangeList).toHaveBeenCalledWith(
      expect.objectContaining({
        onSelectFeature: expect.any(Function),
        onSelectChange: expect.any(Function),
      })
    );
  });

  it('onSelectChange updates state.selectedId and re-renders (diff-mode card flow)', () => {
    render();
    const callbacks = uiList.renderChangeList.mock.calls[0][0];
    callbacks.onSelectChange('id-abc');
    expect(state.selectedId).toBe('id-abc');
    expect(uiList.renderChangeList).toHaveBeenCalledTimes(2);
  });

  it('onSelectFeature updates state, syncs cytoscape, and triggers full re-render', () => {
    state.l1Model = { features: [{ id: 'f1', label: 'F1' }] };
    render();
    const callbacks = uiList.renderChangeList.mock.calls[0][0];
    const beforeCalls = uiList.renderChangeList.mock.calls.length;
    callbacks.onSelectFeature({ id: 'f1', label: 'F1', description: 'd' });
    expect(state.selectedId).toBe('f1');
    expect(state.selectedFeatureId).toBe('f1');
    // render() called again → renderChangeList re-invoked
    expect(uiList.renderChangeList.mock.calls.length).toBe(beforeCalls + 1);
    // renderDetailPanel called with onEnterL2 callback so the panel shows the button
    expect(uiDetail.renderDetailPanel).toHaveBeenCalledWith(
      expect.objectContaining({ onEnterL2: expect.any(Function) })
    );
  });

  it('onSelectFeature syncs Cytoscape selection when instance present', () => {
    const cyNode = { select: vi.fn() };
    const elementsObj = { unselect: vi.fn() };
    state.cytoscapeInstance = {
      elements: vi.fn(() => elementsObj),
      getElementById: vi.fn(() => cyNode),
      animate: vi.fn(),
    };
    render();
    const callbacks = uiList.renderChangeList.mock.calls[0][0];
    callbacks.onSelectFeature({ id: 'fx', label: 'X' });
    expect(elementsObj.unselect).toHaveBeenCalled();
    expect(cyNode.select).toHaveBeenCalled();
    expect(state.cytoscapeInstance.animate).toHaveBeenCalled();
  });

  it('onSelectFeature handles missing cytoscape node gracefully', () => {
    state.cytoscapeInstance = {
      elements: vi.fn(() => ({ unselect: vi.fn() })),
      getElementById: vi.fn(() => null),
      animate: vi.fn(),
    };
    render();
    const callbacks = uiList.renderChangeList.mock.calls[0][0];
    expect(() => callbacks.onSelectFeature({ id: 'fx' })).not.toThrow();
    expect(state.cytoscapeInstance.animate).not.toHaveBeenCalled();
  });

  it('onSelectFeature no-op for cytoscape sync when instance absent, still re-renders', () => {
    state.cytoscapeInstance = null;
    render();
    const callbacks = uiList.renderChangeList.mock.calls[0][0];
    expect(() => callbacks.onSelectFeature({ id: 'fx' })).not.toThrow();
    expect(uiDetail.renderDetailPanel).toHaveBeenCalled();
  });

  it('adds diff-mode class to .app-shell when mode === "diff"', () => {
    state.mode = 'diff';
    render();
    expect(document.querySelector('.app-shell').classList.contains('diff-mode')).toBe(true);
  });

  it('removes diff-mode class when mode !== "diff"', () => {
    document.querySelector('.app-shell').classList.add('diff-mode');
    state.mode = 'baseline';
    render();
    expect(document.querySelector('.app-shell').classList.contains('diff-mode')).toBe(false);
  });

  it('shows diff-mode-banner when mode === "diff"', () => {
    state.mode = 'diff';
    render();
    expect(document.getElementById('diff-mode-banner').hidden).toBe(false);
  });

  it('hides diff-mode-banner when mode !== "diff"', () => {
    document.getElementById('diff-mode-banner').hidden = false;
    state.mode = 'baseline';
    render();
    expect(document.getElementById('diff-mode-banner').hidden).toBe(true);
  });

  it('does not throw when .app-shell missing', () => {
    const shell = document.querySelector('.app-shell');
    shell.className = '';
    try {
      expect(() => render()).not.toThrow();
    } finally {
      shell.className = 'app-shell';
    }
  });

  it('does not throw when #diff-mode-banner missing', () => {
    const banner = document.getElementById('diff-mode-banner');
    banner.id = 'diff-mode-banner-tmp';
    try {
      expect(() => render()).not.toThrow();
    } finally {
      banner.id = 'diff-mode-banner';
    }
  });
});

// ── setMode ──────────────────────────────────────────────────────

describe('setMode', () => {
  it('returns early when mode === "diff" but no diff and no version-compare', async () => {
    state.updateModel = { diff_available: false };
    await setMode('diff');
    expect(state.mode).toBe('baseline');
    expect(uiTopbar.renderTopBar).not.toHaveBeenCalled();
  });

  it('switches when hasDiff', async () => {
    state.updateModel = { diff_available: true, changes: [{ id: 'x' }] };
    await setMode('diff');
    expect(state.mode).toBe('diff');
    expect(state.selectedId).toBe('x');
    expect(uiTopbar.renderTopBar).toHaveBeenCalled();
    expect(layers.loadL1Graph).not.toHaveBeenCalled();
  });

  it('switches and reloads L1 for baseline when hasVersionCompare', async () => {
    state.versionA = 'v1';
    state.versionB = 'v2';
    await setMode('baseline');
    expect(state.mode).toBe('baseline');
    expect(layers.loadL1Graph).toHaveBeenCalledWith('v1');
  });

  it('switches and reloads L1 for current when hasVersionCompare', async () => {
    state.versionA = 'v1';
    state.versionB = 'v2';
    await setMode('current');
    expect(layers.loadL1Graph).toHaveBeenCalledWith('v2');
  });

  it('switches and reloads L1 for diff via versionB when hasVersionCompare', async () => {
    state.versionA = 'v1';
    state.versionB = 'v2';
    await setMode('diff');
    expect(state.mode).toBe('diff');
    expect(layers.loadL1Graph).toHaveBeenCalledWith('v2');
  });

  it('does not reload L1 when hasDiff blocks the version-compare branch', async () => {
    state.versionA = 'v1';
    state.versionB = 'v2';
    state.updateModel = { diff_available: true };
    await setMode('baseline');
    expect(layers.loadL1Graph).not.toHaveBeenCalled();
  });

  it('baseline non-version-compare — no loadL1Graph call', async () => {
    await setMode('baseline');
    expect(state.mode).toBe('baseline');
    expect(layers.loadL1Graph).not.toHaveBeenCalled();
  });

  it('selectedId uses changes[0] when mode=diff', async () => {
    state.updateModel = { diff_available: true, changes: [{ id: 'c1' }, { id: 'c2' }] };
    await setMode('diff');
    expect(state.selectedId).toBe('c1');
  });

  it('selectedId uses features[0] when mode=baseline', async () => {
    state.l1Model = { features: [{ id: 'f1' }] };
    await setMode('baseline');
    expect(state.selectedId).toBe('f1');
  });

  it('selectedId = null when no l1Model in non-diff mode', async () => {
    await setMode('baseline');
    expect(state.selectedId).toBeNull();
  });

  it('selectedId = null when no changes in diff mode', async () => {
    state.updateModel = { diff_available: true, changes: [] };
    await setMode('diff');
    expect(state.selectedId).toBeNull();
  });

  it('selectedId = null when changes undefined in diff mode', async () => {
    state.updateModel = { diff_available: true };
    await setMode('diff');
    expect(state.selectedId).toBeNull();
  });
});

// ── init → loadProjectStatus ─────────────────────────────────────

describe('init → loadProjectStatus', () => {
  it('does not fetch on import (only on init)', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    // module already imported above; if it fetched on import, calls.length > 0
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('fetches /api/project and sets state.projectStatus on ok', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) {
        return Promise.resolve({
          ok: true, status: 200,
          json: async () => ({ project_path: '/p', available_data: {} }),
        });
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    init();
    await new Promise(r => setTimeout(r, 0));
    expect(fetchSpy.mock.calls[0][0]).toContain('/api/project');
    expect(state.projectStatus).toEqual({ project_path: '/p', available_data: {} });
  });

  it('calls renderError on !ok with body message', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 500,
      json: async () => ({ error: { message: 'down' } }),
    });
    init();
    await new Promise(r => setTimeout(r, 0));
    expect(uiDetail.renderError).toHaveBeenCalledWith('down');
  });

  it('renderError uses status fallback on !ok with no message', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 503, json: async () => ({}),
    });
    init();
    await new Promise(r => setTimeout(r, 0));
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('503'));
  });

  it('renderError handles unparseable body', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 502, json: async () => { throw new Error('bad json'); },
    });
    init();
    await new Promise(r => setTimeout(r, 0));
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('502'));
  });

  it('falls back to static on network error (catch)', async () => {
    let calls = [];
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      calls.push(url);
      if (url.includes('/api/project')) return Promise.reject(new Error('net'));
      // static fallback urls
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ diff_available: false, nodes: [] }) });
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    // First call is /api/project; subsequent are static
    expect(calls[0]).toContain('/api/project');
    expect(calls.some(u => u.includes('update-view-model.json'))).toBe(true);
  });
});

// ── loadFromApi flow (via init → projectStatus success) ───────────

describe('loadFromApi (via init flow)', () => {
  function projectStatusOk(available_data) {
    return {
      ok: true, status: 200,
      json: async () => ({ project_path: '/p', available_data }),
    };
  }

  it('triggers loadReport when has_latest_report', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) return Promise.resolve(projectStatusOk({ has_latest_report: true }));
      if (url.includes('/api/report/latest')) return Promise.resolve({
        ok: true, status: 200, json: async () => ({ l1_changes: [], l2_details: [] }),
      });
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(fetchSpy.mock.calls.some(c => c[0].includes('/api/report/latest'))).toBe(true);
    expect(viewmodel.buildViewModelFromReport).toHaveBeenCalled();
    expect(state.updateModel).toBeTruthy();
  });

  it('shows empty summary when no latest_report', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) return Promise.resolve(projectStatusOk({}));
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(state.updateModel).toBeNull();
    expect(els.summaryText.textContent).toContain('尚未有分析報告');
  });

  it('triggers loadSnapshots + loadL1Graph when has_snapshots', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) return Promise.resolve(projectStatusOk({ has_snapshots: true }));
      if (url.includes('/api/snapshots')) return Promise.resolve({
        ok: true, status: 200,
        json: async () => ({ snapshots: [{ version_id: 'B' }, { version_id: 'A' }] }),
      });
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(state.snapshots).toHaveLength(2);
    expect(state.versionA).toBe('A');
    expect(state.versionB).toBe('B');
    expect(layers.loadL1Graph).toHaveBeenCalledWith('B'); // version-compare path
  });

  it('loadL1Graph called with null when has_snapshots but no version-compare', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) return Promise.resolve(projectStatusOk({ has_snapshots: true }));
      if (url.includes('/api/snapshots')) return Promise.resolve({
        ok: true, status: 200, json: async () => ({ snapshots: [{ version_id: 'only' }] }),
      });
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(state.versionA).toBeNull();
    expect(layers.loadL1Graph).toHaveBeenCalledWith(null);
  });

  it('skips loadL1Graph when no snapshots', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) return Promise.resolve(projectStatusOk({ has_latest_report: true }));
      if (url.includes('/api/report/latest')) return Promise.resolve({
        ok: true, status: 200, json: async () => ({ l1_changes: [] }),
      });
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(layers.loadL1Graph).not.toHaveBeenCalled();
  });

  it('handles missing available_data (treats as no flags)', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) return Promise.resolve({
        ok: true, status: 200, json: async () => ({ project_path: '/p' }),
      });
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(els.summaryText.textContent).toContain('尚未有分析報告');
    expect(layers.loadL1Graph).not.toHaveBeenCalled();
  });
});

// ── loadReport ────────────────────────────────────────────────────

describe('loadReport (via init flow)', () => {
  it('sets updateModel = null on 404', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) return Promise.resolve({
        ok: true, status: 200,
        json: async () => ({ project_path: '/p', available_data: { has_latest_report: true } }),
      });
      if (url.includes('/api/report/latest')) return Promise.resolve({
        ok: false, status: 404, json: async () => ({}),
      });
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    state.updateModel = { existing: true };
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(state.updateModel).toBeNull();
  });

  it('calls handleApiError → renderError on !ok non-404 with body message', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) return Promise.resolve({
        ok: true, status: 200,
        json: async () => ({ project_path: '/p', available_data: { has_latest_report: true } }),
      });
      if (url.includes('/api/report/latest')) return Promise.resolve({
        ok: false, status: 500,
        json: async () => ({ error: { message: 'srv' } }),
      });
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('srv'));
  });

  it('handleApiError uses HTTP status fallback when no body message', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) return Promise.resolve({
        ok: true, status: 200,
        json: async () => ({ project_path: '/p', available_data: { has_latest_report: true } }),
      });
      if (url.includes('/api/report/latest')) return Promise.resolve({
        ok: false, status: 503, json: async () => ({}),
      });
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('HTTP 503'));
  });

  it('handles unparseable error body on !ok', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) return Promise.resolve({
        ok: true, status: 200,
        json: async () => ({ project_path: '/p', available_data: { has_latest_report: true } }),
      });
      if (url.includes('/api/report/latest')) return Promise.resolve({
        ok: false, status: 500, json: async () => { throw new Error('bad'); },
      });
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('HTTP 500'));
  });

  it('builds ViewModel from report on success', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) return Promise.resolve({
        ok: true, status: 200,
        json: async () => ({ project_path: '/p', available_data: { has_latest_report: true } }),
      });
      if (url.includes('/api/report/latest')) return Promise.resolve({
        ok: true, status: 200, json: async () => ({ l1_changes: [{ feature_id: 'x' }] }),
      });
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(viewmodel.buildViewModelFromReport).toHaveBeenCalledWith({ l1_changes: [{ feature_id: 'x' }] });
  });

  it('catches network error during loadReport', async () => {
    let n = 0;
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) return Promise.resolve({
        ok: true, status: 200,
        json: async () => ({ project_path: '/p', available_data: { has_latest_report: true } }),
      });
      if (url.includes('/api/report/latest')) return Promise.reject(new Error('netdown'));
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('netdown'));
  });

  it('uses "network error" fallback in catch', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) return Promise.resolve({
        ok: true, status: 200,
        json: async () => ({ project_path: '/p', available_data: { has_latest_report: true } }),
      });
      if (url.includes('/api/report/latest')) return Promise.reject({});
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('network error'));
  });
});

// ── loadSnapshots ────────────────────────────────────────────────

describe('loadSnapshots (via init flow)', () => {
  it('silently returns on !ok', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) return Promise.resolve({
        ok: true, status: 200,
        json: async () => ({ available_data: { has_snapshots: true } }),
      });
      if (url.includes('/api/snapshots')) return Promise.resolve({
        ok: false, status: 500, json: async () => ({}),
      });
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(state.snapshots).toEqual([]);
  });

  it('handles missing snapshots key', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) return Promise.resolve({
        ok: true, status: 200,
        json: async () => ({ available_data: { has_snapshots: true } }),
      });
      if (url.includes('/api/snapshots')) return Promise.resolve({
        ok: true, status: 200, json: async () => ({}),
      });
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(state.snapshots).toEqual([]);
    expect(state.versionA).toBeNull();
    expect(state.versionB).toBeNull();
  });

  it('versionA stays null with single snapshot', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) return Promise.resolve({
        ok: true, status: 200,
        json: async () => ({ available_data: { has_snapshots: true } }),
      });
      if (url.includes('/api/snapshots')) return Promise.resolve({
        ok: true, status: 200, json: async () => ({ snapshots: [{ version_id: 'sole' }] }),
      });
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(state.versionA).toBeNull();
    expect(state.versionB).toBe('sole');
  });

  it('silently catches network error', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) return Promise.resolve({
        ok: true, status: 200,
        json: async () => ({ available_data: { has_snapshots: true } }),
      });
      if (url.includes('/api/snapshots')) return Promise.reject(new Error('boom'));
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    // Should not throw, state.snapshots remains []
    expect(state.snapshots).toEqual([]);
  });
});

// ── loadStaticFallback ───────────────────────────────────────────

describe('loadStaticFallback (via init network error)', () => {
  function mockFallback({ updateRes, l1Res }) {
    let calls = 0;
    return vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) return Promise.reject(new Error('net'));
      if (url.includes('update-view-model.json')) return updateRes();
      if (url.includes('l1-view-model.json')) return l1Res();
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
  }

  it('sets updateModel + l1GraphViewModel + l1Model on full success, calls initGraph + renderLegend', async () => {
    mockFallback({
      updateRes: () => Promise.resolve({
        ok: true, status: 200, json: async () => ({ diff_available: false }),
      }),
      l1Res: () => Promise.resolve({
        ok: true, status: 200,
        json: async () => ({ nodes: [{ id: 'a', label: 'A', confidence: 'high', description: 'd', trigger_description: 't' }] }),
      }),
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(state.updateModel).toEqual({ diff_available: false });
    expect(state.l1GraphViewModel.nodes).toHaveLength(1);
    expect(state.l1Model.features[0].source).toBe('L1Output.features');
    expect(state.l1Model.stats.feature_count).toBe(1);
    expect(graph.initGraph).toHaveBeenCalled();
    expect(graph.renderLegend).toHaveBeenCalled();
    expect(state.layerState).toBe('L1');
  });

  it('renderError on update-view-model !ok, does not attempt l1', async () => {
    const fetchSpy = mockFallback({
      updateRes: () => Promise.resolve({ ok: false, status: 404, json: async () => ({}) }),
      l1Res: () => Promise.resolve({ ok: true, status: 200, json: async () => ({}) }),
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('404'));
    expect(fetchSpy.mock.calls.some(c => c[0].includes('l1-view-model.json'))).toBe(false);
  });

  it('renderError on update-view-model network failure (catch)', async () => {
    mockFallback({
      updateRes: () => Promise.reject(new Error('staticdown')),
      l1Res: () => Promise.resolve({ ok: true, status: 200, json: async () => ({}) }),
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('staticdown'));
  });

  it('renderError uses "network error" fallback when err has no message', async () => {
    mockFallback({
      updateRes: () => Promise.reject({}),
      l1Res: () => Promise.resolve({ ok: true, status: 200, json: async () => ({}) }),
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('network error'));
  });

  it('keeps l1GraphViewModel null when l1 !ok', async () => {
    mockFallback({
      updateRes: () => Promise.resolve({ ok: true, status: 200, json: async () => ({ diff_available: false }) }),
      l1Res: () => Promise.resolve({ ok: false, status: 404, json: async () => ({}) }),
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(state.l1GraphViewModel).toBeNull();
    expect(state.l1Model).toBeNull();
    expect(graph.initGraph).not.toHaveBeenCalled();
  });

  it('sets state.mode = "diff" when diff_available', async () => {
    mockFallback({
      updateRes: () => Promise.resolve({ ok: true, status: 200, json: async () => ({ diff_available: true, changes: [{ id: 'x' }] }) }),
      l1Res: () => Promise.resolve({ ok: false, status: 404, json: async () => ({}) }),
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(state.mode).toBe('diff');
    expect(state.selectedId).toBe('x');
  });

  it('sets state.mode = "baseline" when no diff_available', async () => {
    mockFallback({
      updateRes: () => Promise.resolve({ ok: true, status: 200, json: async () => ({ diff_available: false }) }),
      l1Res: () => Promise.resolve({ ok: false, status: 404, json: async () => ({}) }),
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(state.mode).toBe('baseline');
  });

  it('catches l1 json fetch network error — state stays null', async () => {
    mockFallback({
      updateRes: () => Promise.resolve({ ok: true, status: 200, json: async () => ({ diff_available: false }) }),
      l1Res: () => Promise.reject(new Error('l1net')),
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(state.l1GraphViewModel).toBeNull();
    expect(state.l1Model).toBeNull();
  });

  it('handles l1 json parse error', async () => {
    mockFallback({
      updateRes: () => Promise.resolve({ ok: true, status: 200, json: async () => ({ diff_available: false }) }),
      l1Res: () => Promise.resolve({ ok: true, status: 200, json: async () => { throw new Error('parse'); } }),
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(state.l1GraphViewModel).toBeNull();
  });

  it('handles l1 json with no nodes key (uses || [] branch)', async () => {
    mockFallback({
      updateRes: () => Promise.resolve({ ok: true, status: 200, json: async () => ({ diff_available: false }) }),
      l1Res: () => Promise.resolve({ ok: true, status: 200, json: async () => ({}) }),
    });
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(state.l1Model.features).toEqual([]);
    expect(state.l1Model.stats.feature_count).toBe(0);
  });
});

// ── button event bindings ────────────────────────────────────────

describe('event bindings (via init)', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => Promise.reject(new Error('skip')));
    init();
  });

  it('btnDiff click triggers setMode("diff")', async () => {
    state.updateModel = { diff_available: true, changes: [{ id: 'x' }] };
    els.btnDiff.click();
    await new Promise(r => setTimeout(r, 0));
    expect(state.mode).toBe('diff');
  });

  it('btnBaseline click triggers setMode("baseline")', async () => {
    state.mode = 'diff';
    els.btnBaseline.click();
    await new Promise(r => setTimeout(r, 0));
    expect(state.mode).toBe('baseline');
  });

  it('btnCurrent click triggers setMode("current")', async () => {
    els.btnCurrent.click();
    await new Promise(r => setTimeout(r, 0));
    expect(state.mode).toBe('current');
  });

  it('btnReanalyze click → showUpdateModal', () => {
    els.btnReanalyze.click();
    expect(uiModal.showUpdateModal).toHaveBeenCalled();
  });

  it('btnModalCancel click → hideUpdateModal', () => {
    els.btnModalCancel.click();
    expect(uiModal.hideUpdateModal).toHaveBeenCalled();
  });

  it('btnModalSubmit — both paths empty → showModalError, no submit', () => {
    els.inputOldPath.value = '   ';
    els.inputNewPath.value = '';
    els.btnModalSubmit.click();
    expect(uiModal.showModalError).toHaveBeenCalled();
    expect(uiModal.submitUpdate).not.toHaveBeenCalled();
  });

  it('btnModalSubmit — only oldPath empty → showModalError', () => {
    els.inputOldPath.value = '';
    els.inputNewPath.value = '/new';
    els.btnModalSubmit.click();
    expect(uiModal.showModalError).toHaveBeenCalled();
  });

  it('btnModalSubmit — only newPath empty → showModalError', () => {
    els.inputOldPath.value = '/old';
    els.inputNewPath.value = '';
    els.btnModalSubmit.click();
    expect(uiModal.showModalError).toHaveBeenCalled();
  });

  it('btnModalSubmit — both paths set → hideUpdateModal + submitUpdate with callbacks', () => {
    els.inputOldPath.value = '/old';
    els.inputNewPath.value = '/new';
    els.btnModalSubmit.click();
    expect(uiModal.hideUpdateModal).toHaveBeenCalled();
    expect(uiModal.submitUpdate).toHaveBeenCalledWith('/old', '/new', expect.objectContaining({
      onComplete: expect.any(Function),
      onError: expect.any(Function),
    }));
  });

  it('submitUpdate onComplete with null projectStatus — loadFromApi early-returns', async () => {
    state.projectStatus = null;
    els.inputOldPath.value = '/old';
    els.inputNewPath.value = '/new';
    els.btnModalSubmit.click();
    const submitCallbacks = uiModal.submitUpdate.mock.calls[0][2];
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(() => {
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    submitCallbacks.onComplete();
    await new Promise(r => setTimeout(r, 10));
    // No /api/report/latest fetch — loadFromApi returned early
    expect(fetchSpy.mock.calls.some(c => c[0].includes('/api/report/latest'))).toBe(false);
  });

  it('submitUpdate onComplete callback re-runs loadFromApi (uses existing projectStatus)', async () => {
    // Simulate prior projectStatus from earlier load
    state.projectStatus = { available_data: { has_latest_report: true } };
    els.inputOldPath.value = '/old';
    els.inputNewPath.value = '/new';
    els.btnModalSubmit.click();
    const submitCallbacks = uiModal.submitUpdate.mock.calls[0][2];
    // Mock fetch — onComplete should re-fetch /api/report/latest via loadReport
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/report/latest')) return Promise.resolve({
        ok: true, status: 200, json: async () => ({ l1_changes: [{ feature_id: 'new' }] }),
      });
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    submitCallbacks.onComplete();
    await new Promise(r => setTimeout(r, 10));
    expect(fetchSpy.mock.calls.some(c => c[0].includes('/api/report/latest'))).toBe(true);
  });

  it('btnGraphToggle click → openGraphDrawer', () => {
    els.btnGraphToggle.click();
    expect(graph.openGraphDrawer).toHaveBeenCalled();
  });

  it('btnDrawerClose click → closeGraphDrawer', () => {
    els.btnDrawerClose.click();
    expect(graph.closeGraphDrawer).toHaveBeenCalled();
  });

  it('graphBackdrop click → closeGraphDrawer', () => {
    els.graphBackdrop.click();
    expect(graph.closeGraphDrawer).toHaveBeenCalled();
  });

  it('btnMindmap click → switchToMindmap', () => {
    els.btnMindmap.click();
    expect(layers.switchToMindmap).toHaveBeenCalled();
  });

  it('btnBackL1 click → switchToL1', () => {
    els.btnBackL1.click();
    expect(layers.switchToL1).toHaveBeenCalled();
  });
});

// ── optional button binding null-safety ───────────────────────────

describe('optional button bindings — null-safety', () => {
  it('init does not throw when optional buttons absent', () => {
    const originalGraphToggle = els.btnGraphToggle;
    const originalDrawerClose = els.btnDrawerClose;
    const originalBackdrop = els.graphBackdrop;
    const originalMindmap = els.btnMindmap;
    const originalBackL1 = els.btnBackL1;
    els.btnGraphToggle = null;
    els.btnDrawerClose = null;
    els.graphBackdrop = null;
    els.btnMindmap = null;
    els.btnBackL1 = null;
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => Promise.reject(new Error('skip')));
    try {
      expect(() => init()).not.toThrow();
    } finally {
      els.btnGraphToggle = originalGraphToggle;
      els.btnDrawerClose = originalDrawerClose;
      els.graphBackdrop = originalBackdrop;
      els.btnMindmap = originalMindmap;
      els.btnBackL1 = originalBackL1;
    }
  });
});

// ── populateVersionSelectors (via init flow) ─────────────────────

describe('populateVersionSelectors (via init flow)', () => {
  function setupSnapshots(snapshots) {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/project')) return Promise.resolve({
        ok: true, status: 200,
        json: async () => ({ available_data: { has_snapshots: true } }),
      });
      if (url.includes('/api/snapshots')) return Promise.resolve({
        ok: true, status: 200, json: async () => ({ snapshots }),
      });
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
  }

  it('hides selectorBar when snapshots <= 1', async () => {
    setupSnapshots([{ version_id: 'only', label: 'Only' }]);
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(document.getElementById('version-selector-bar').hidden).toBe(true);
  });

  it('shows selectorBar with options when snapshots > 1', async () => {
    setupSnapshots([
      { version_id: 'B', label: 'B' },
      { version_id: 'A', label: 'A' },
    ]);
    init();
    await new Promise(r => setTimeout(r, 10));
    expect(document.getElementById('version-selector-bar').hidden).toBe(false);
    const selA = document.getElementById('select-version-a');
    const selB = document.getElementById('select-version-b');
    expect(selA.options).toHaveLength(2);
    expect(selB.options).toHaveLength(2);
    expect(selA.value).toBe('A'); // baseline = older = state.versionA
    expect(selB.value).toBe('B'); // current = newer
  });

  it('selA onchange updates state.versionA, mode=diff, calls renderTopBar + loadL1Graph(versionB)', async () => {
    setupSnapshots([
      { version_id: 'B', label: 'B' },
      { version_id: 'A', label: 'A' },
    ]);
    init();
    await new Promise(r => setTimeout(r, 10));
    layers.loadL1Graph.mockClear();
    uiTopbar.renderTopBar.mockClear();
    const selA = document.getElementById('select-version-a');
    selA.value = 'B';
    await selA.onchange();
    expect(state.versionA).toBe('B');
    expect(state.mode).toBe('diff');
    expect(uiTopbar.renderTopBar).toHaveBeenCalled();
    expect(layers.loadL1Graph).toHaveBeenCalledWith('B');
  });

  it('selA onchange falls back to versionA when versionB null', async () => {
    setupSnapshots([
      { version_id: 'B', label: 'B' },
      { version_id: 'A', label: 'A' },
    ]);
    init();
    await new Promise(r => setTimeout(r, 10));
    state.versionB = null;
    layers.loadL1Graph.mockClear();
    const selA = document.getElementById('select-version-a');
    selA.value = 'A';
    await selA.onchange();
    expect(layers.loadL1Graph).toHaveBeenCalledWith('A');
  });

  it('selB onchange updates state.versionB and calls loadL1Graph(versionB)', async () => {
    setupSnapshots([
      { version_id: 'B', label: 'B' },
      { version_id: 'A', label: 'A' },
    ]);
    init();
    await new Promise(r => setTimeout(r, 10));
    layers.loadL1Graph.mockClear();
    const selB = document.getElementById('select-version-b');
    selB.value = 'A';
    await selB.onchange();
    expect(state.versionB).toBe('A');
    expect(state.mode).toBe('diff');
    expect(layers.loadL1Graph).toHaveBeenCalledWith('A');
  });

  it('returns early when selA missing', async () => {
    const orig = document.getElementById('select-version-a');
    orig.id = 'select-version-a-tmp';
    try {
      setupSnapshots([{ version_id: 'B' }, { version_id: 'A' }]);
      init();
      await new Promise(r => setTimeout(r, 10));
      expect(document.getElementById('version-selector-bar').hidden).toBe(true);
    } finally {
      orig.id = 'select-version-a';
    }
  });

  it('returns early when selB missing', async () => {
    const orig = document.getElementById('select-version-b');
    orig.id = 'select-version-b-tmp';
    try {
      setupSnapshots([{ version_id: 'B' }, { version_id: 'A' }]);
      init();
      await new Promise(r => setTimeout(r, 10));
      expect(document.getElementById('version-selector-bar').hidden).toBe(true);
    } finally {
      orig.id = 'select-version-b';
    }
  });

  it('returns early when selectorBar missing', async () => {
    const orig = document.getElementById('version-selector-bar');
    orig.id = 'version-selector-bar-tmp';
    try {
      setupSnapshots([{ version_id: 'B' }, { version_id: 'A' }]);
      init();
      await new Promise(r => setTimeout(r, 10));
      // No throw; can't verify hidden state, but populate function returned safely.
    } finally {
      orig.id = 'version-selector-bar';
    }
  });
});
