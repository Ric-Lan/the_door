import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../js/ui-detail.js', () => ({
  renderError: vi.fn(),
  renderDetailPanel: vi.fn(),
  renderDetailPanelL1: vi.fn(),
  renderDetailPanelL2: vi.fn(),
  renderDetailPanelL3: vi.fn(),
  renderDetailPanelDiff: vi.fn(),
}));

vi.mock('../js/ui-topbar.js', () => ({
  renderTopBar: vi.fn(),
  updateLogoMark: vi.fn(),
}));

vi.mock('../js/ui-list.js', () => ({
  renderChangeList: vi.fn(),
  changeSymbol: vi.fn((t) => ({
    added: '+',
    removed: '-',
    attribute_changed: '~',
    dependency_changed: '≠',
  }[t] || '?')),
}));

vi.mock('../js/graph.js', () => ({
  initGraph: vi.fn(),
  renderLegend: vi.fn(),
}));

import {
  loadL1Graph,
  loadDiffOverlay,
  switchToL2,
  switchToL3,
  switchToL1,
  switchToL2FromL3,
  loadLayerExplanation,
  generateL2,
  generateLayerExplanation,
  renderBreadcrumb,
  pollUntilComplete,
  renderFeatureList,
  renderL2NotAnalyzed,
  switchToMindmap,
} from '../js/layers.js';
import { state } from '../js/state.js';
import { els } from '../js/dom.js';
import * as uiDetail from '../js/ui-detail.js';
import * as uiTopbar from '../js/ui-topbar.js';
import * as uiList from '../js/ui-list.js';
import * as graph from '../js/graph.js';

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
  const breadcrumb = document.getElementById('breadcrumb');
  if (breadcrumb) breadcrumb.textContent = '';
  const list = document.getElementById('feature-list');
  if (list) list.textContent = '';
  const container = document.getElementById('graph-container');
  if (container) container.textContent = '';
  const explanation = document.getElementById('layer-explanation');
  if (explanation) explanation.textContent = '';
  if (els.btnBackL1) els.btnBackL1.hidden = false;
}

function makeCy(nodesMap = {}) {
  // Simulates a Cytoscape instance with node id lookup. nodesMap: { id -> nodeStub }
  // Each nodeStub: { id, select, data, removeData, hasNode }
  // If id not in map, return falsy via "isEmpty"-style check.
  const elementsObj = { unselect: vi.fn() };
  const nodes = Object.entries(nodesMap).map(([id, stub]) => ({
    id: () => id,
    data: stub.data,
    removeData: stub.removeData,
  }));
  return {
    nodes: vi.fn(() => nodes),
    elements: vi.fn(() => elementsObj),
    getElementById: vi.fn((id) => nodesMap[id] || null),
    animate: vi.fn(),
    _elementsObj: elementsObj,
    _nodes: nodes,
  };
}

beforeEach(() => {
  resetState();
  resetDom();
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── loadL1Graph ───────────────────────────────────────────────────

describe('loadL1Graph', () => {
  it('sets l1GraphViewModel, l1Model, layerState on success', async () => {
    const vm = {
      nodes: [
        { id: 'f1', label: 'F1', confidence: 'high', description: 'd1', trigger_description: 't1' },
        { id: 'f2', label: 'F2', confidence: 'low', description: 'd2', trigger_description: 't2' },
      ],
    };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => vm,
    });
    await loadL1Graph();
    expect(state.l1GraphViewModel).toEqual(vm);
    expect(state.layerState).toBe('L1');
    expect(state.l1Model.features).toHaveLength(2);
    expect(state.l1Model.features[0]).toEqual({
      id: 'f1', label: 'F1', confidence: 'high', description: 'd1', trigger_description: 't1', source: 'L1Output.features',
    });
    expect(state.l1Model.stats.feature_count).toBe(2);
    expect(graph.initGraph).toHaveBeenCalledWith('graph-container', vm);
    expect(graph.renderLegend).toHaveBeenCalled();
    expect(uiTopbar.renderTopBar).toHaveBeenCalled();
    expect(uiList.renderChangeList).toHaveBeenCalled();
    expect(uiDetail.renderDetailPanel).toHaveBeenCalled();
  });

  it('appends version_id to URL when versionId given', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200, json: async () => ({ nodes: [] }),
    });
    await loadL1Graph('v1');
    expect(fetchSpy.mock.calls[0][0]).toBe('/api/l1?version_id=v1');
  });

  it('uses bare /api/l1 when versionId is null', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200, json: async () => ({ nodes: [] }),
    });
    await loadL1Graph();
    expect(fetchSpy.mock.calls[0][0]).toBe('/api/l1');
  });

  it('calls renderError on !res.ok with error message', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 500,
      json: async () => ({ error: { message: 'server boom' } }),
    });
    await loadL1Graph();
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('server boom'));
    expect(state.l1GraphViewModel).toBeNull();
  });

  it('uses status fallback when error body has no message', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 503,
      json: async () => ({}),
    });
    await loadL1Graph();
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('503'));
  });

  it('uses status fallback when error body is unparseable', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 502,
      json: async () => { throw new Error('bad json'); },
    });
    await loadL1Graph();
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('502'));
  });

  it('calls renderError on network error (catch)', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('network failure'));
    await loadL1Graph();
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('network failure'));
  });

  it('uses "network error" fallback in catch when err has no message', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue({});
    await loadL1Graph();
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('network error'));
  });

  it('sets selectedId to first feature when no diff_available', async () => {
    state.updateModel = { diff_available: false };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({ nodes: [{ id: 'first', label: 'F' }, { id: 'second' }] }),
    });
    await loadL1Graph();
    expect(state.selectedId).toBe('first');
  });

  it('selectedId stays unchanged when diff_available', async () => {
    state.updateModel = { diff_available: true };
    state.selectedId = 'preserved';
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({ nodes: [{ id: 'first' }] }),
    });
    await loadL1Graph();
    expect(state.selectedId).toBe('preserved');
  });

  it('handles empty nodes — selectedId becomes null', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({ nodes: [] }),
    });
    await loadL1Graph();
    expect(state.selectedId).toBeNull();
    expect(state.l1Model.stats.feature_count).toBe(0);
  });

  it('handles undefined nodes array — l1Model.features is empty', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({}),
    });
    await loadL1Graph();
    expect(state.l1Model.features).toEqual([]);
    expect(state.l1Model.stats.feature_count).toBe(0);
  });

  it('triggers loadDiffOverlay when versionA && versionB && distinct', async () => {
    state.versionA = 'v1';
    state.versionB = 'v2';
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    fetchSpy.mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ nodes: [] }) });
    fetchSpy.mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ summary: {} }) });
    await loadL1Graph();
    expect(fetchSpy.mock.calls.length).toBe(2);
    expect(fetchSpy.mock.calls[1][0]).toContain('/api/diff?baseline=v1&current=v2');
  });

  it('does not trigger loadDiffOverlay when versionA === versionB', async () => {
    state.versionA = 'v1';
    state.versionB = 'v1';
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200, json: async () => ({ nodes: [] }),
    });
    await loadL1Graph();
    expect(fetchSpy.mock.calls.length).toBe(1);
  });

  it('does not trigger loadDiffOverlay when versionA missing', async () => {
    state.versionA = null;
    state.versionB = 'v2';
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200, json: async () => ({ nodes: [] }),
    });
    await loadL1Graph();
    expect(fetchSpy.mock.calls.length).toBe(1);
  });
});

// ── loadDiffOverlay ───────────────────────────────────────────────

describe('loadDiffOverlay', () => {
  it('returns early when baseline === current', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    await loadDiffOverlay('v1', 'v1');
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('returns early when baseline is null', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    await loadDiffOverlay(null, 'v2');
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('returns early when current is null', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    await loadDiffOverlay('v1', null);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('sets state.versionDiff and updates summaryText with totals > 0', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({
        node_states: {},
        summary: { total_changed: 5, added: 2, removed: 1, attribute_changed: 1, dependency_changed: 1 },
      }),
    });
    await loadDiffOverlay('v1', 'v2');
    expect(state.versionDiff.summary.total_changed).toBe(5);
    expect(els.summaryText.textContent).toContain('2 新增');
    expect(els.summaryText.textContent).toContain('1 移除');
    expect(els.summaryText.textContent).toContain('2 修改');
    expect(uiTopbar.renderTopBar).toHaveBeenCalled();
    expect(uiList.renderChangeList).toHaveBeenCalled();
  });

  it('shows "兩版本功能完全相同" when total_changed === 0', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({ summary: { total_changed: 0 } }),
    });
    await loadDiffOverlay('v1', 'v2');
    expect(els.summaryText.textContent).toBe('版本比較：兩版本功能完全相同。');
  });

  it('shows "兩版本功能完全相同" when summary is missing', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({}),
    });
    await loadDiffOverlay('v1', 'v2');
    expect(els.summaryText.textContent).toContain('兩版本功能完全相同');
  });

  it('uses ?? 0 fallback for summary fields', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({ summary: { total_changed: 1 } }),
    });
    await loadDiffOverlay('v1', 'v2');
    expect(els.summaryText.textContent).toContain('0 新增');
    expect(els.summaryText.textContent).toContain('0 移除');
    expect(els.summaryText.textContent).toContain('0 修改');
  });

  it('applies change_type to cytoscape nodes when state.cytoscapeInstance set', async () => {
    const node1 = { data: vi.fn(), removeData: vi.fn() };
    const node2 = { data: vi.fn(), removeData: vi.fn() };
    state.cytoscapeInstance = makeCy({ 'a': node1, 'b': node2 });
    // makeCy returns ._nodes by-id form; rebuild a cy with both nodes() iterable
    state.cytoscapeInstance = {
      nodes: () => [
        { id: () => 'a', data: node1.data, removeData: node1.removeData },
        { id: () => 'b', data: node2.data, removeData: node2.removeData },
      ],
    };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({
        node_states: { a: 'added', b: 'unchanged' },
        summary: { total_changed: 1, added: 1, removed: 0, attribute_changed: 0, dependency_changed: 0 },
      }),
    });
    await loadDiffOverlay('v1', 'v2');
    expect(node1.data).toHaveBeenCalledWith('change_type', 'added');
    expect(node2.removeData).toHaveBeenCalledWith('change_type');
  });

  it('handles missing node_states (uses || {})', async () => {
    state.cytoscapeInstance = { nodes: () => [{ id: () => 'a', data: vi.fn(), removeData: vi.fn() }] };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({ summary: { total_changed: 0 } }),
    });
    await loadDiffOverlay('v1', 'v2');
    // No throw — node has no state mapped, so removeData branch runs
  });

  it('silently returns on !res.ok', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 500, json: async () => ({}),
    });
    await loadDiffOverlay('v1', 'v2');
    expect(state.versionDiff).toBeNull();
    expect(uiDetail.renderError).not.toHaveBeenCalled();
  });

  it('silently catches network error', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('boom'));
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    await loadDiffOverlay('v1', 'v2');
    expect(warnSpy).toHaveBeenCalled();
    expect(uiDetail.renderError).not.toHaveBeenCalled();
  });
});

// ── switchToL2 ────────────────────────────────────────────────────

describe('switchToL2', () => {
  it('sets state and calls updateLogoMark + renderBreadcrumb', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200, json: async () => ({ nodes: [] }),
    });
    await switchToL2('feat-1');
    expect(state.selectedFeatureId).toBe('feat-1');
    expect(state.layerState).toBe('L2');
    expect(uiTopbar.updateLogoMark).toHaveBeenCalled();
  });

  it('fires loadLayerExplanation (fire-and-forget) — second fetch call exists', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200, json: async () => ({ nodes: [] }),
    });
    await switchToL2('feat-1');
    // calls: 1 for L2 fetch, 1 for layer-explanation (fire-and-forget)
    expect(fetchSpy.mock.calls.some(c => c[0].includes('/api/layer-explanation/feat-1/l2'))).toBe(true);
  });

  it('renders renderL2NotAnalyzed on 404', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/l2/feat-x') && !url.includes('explanation')) {
        return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
      }
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
    });
    state.l1GraphViewModel = { nodes: [{ id: 'feat-x', label: 'X' }] };
    await switchToL2('feat-x');
    const list = document.getElementById('feature-list');
    expect(list.querySelector('.not-analyzed-state')).not.toBeNull();
  });

  it('sets state.l2GraphViewModel and calls initGraph + renderFeatureList on success', async () => {
    const vm = { nodes: [{ id: 'm1', label: 'M1' }] };
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('explanation')) return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
      return Promise.resolve({ ok: true, status: 200, json: async () => vm });
    });
    await switchToL2('feat-1');
    expect(state.l2GraphViewModel).toEqual(vm);
    expect(graph.initGraph).toHaveBeenCalledWith('graph-container', vm);
  });

  it('calls renderError on !ok non-404', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('explanation')) return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
      return Promise.resolve({ ok: false, status: 500, json: async () => ({ error: { message: 'boom' } }) });
    });
    await switchToL2('feat-1');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('boom'));
  });

  it('uses res.status fallback on !ok with no body message', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('explanation')) return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
      return Promise.resolve({ ok: false, status: 503, json: async () => ({}) });
    });
    await switchToL2('feat-1');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('503'));
  });

  it('handles unparseable error body', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('explanation')) return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
      return Promise.resolve({ ok: false, status: 502, json: async () => { throw new Error('x'); } });
    });
    await switchToL2('feat-1');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('502'));
  });

  it('calls renderError on network error (catch)', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('explanation')) return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
      return Promise.reject(new Error('net'));
    });
    await switchToL2('feat-1');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('net'));
  });

  it('uses "network error" fallback when err has no message', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('explanation')) return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
      return Promise.reject({});
    });
    await switchToL2('feat-1');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('network error'));
  });
});

// ── switchToL3 ────────────────────────────────────────────────────

describe('switchToL3', () => {
  it('sets state and calls updateLogoMark + renderBreadcrumb', async () => {
    state.l2GraphViewModel = { nodes: [{ id: 'm1', source_nodes: [] }] };
    await switchToL3('m1');
    expect(state.selectedModuleId).toBe('m1');
    expect(state.layerState).toBe('L3');
    expect(uiTopbar.updateLogoMark).toHaveBeenCalled();
  });

  it('uses empty viewModel when source_nodes is empty', async () => {
    state.l2GraphViewModel = { nodes: [{ id: 'm1', source_nodes: [] }] };
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    await switchToL3('m1');
    expect(graph.initGraph).toHaveBeenCalledWith('graph-container', { nodes: [], edges: [] });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('treats missing module as empty source_nodes', async () => {
    state.l2GraphViewModel = { nodes: [] };
    await switchToL3('not-here');
    expect(graph.initGraph).toHaveBeenCalledWith('graph-container', { nodes: [], edges: [] });
  });

  it('treats null l2GraphViewModel as empty source_nodes', async () => {
    state.l2GraphViewModel = null;
    await switchToL3('m1');
    expect(graph.initGraph).toHaveBeenCalledWith('graph-container', { nodes: [], edges: [] });
  });

  it('filters structure nodes and edges by source_nodes', async () => {
    state.l2GraphViewModel = { nodes: [{ id: 'm1', source_nodes: ['A', 'B'] }] };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({
        nodes: [
          { node_id: 'A', name: 'NameA', type: 'class', file: 'a.py' },
          { node_id: 'B', name: 'NameB', type: 'fn', file: 'b.py' },
          { node_id: 'C', name: 'NameC', type: 'fn', file: 'c.py' },
        ],
        edges: [
          { from_node: 'A', to_node: 'B' },
          { from_node: 'A', to_node: 'C' },
          { from_node: 'B', to_node: 'C' },
        ],
      }),
    });
    await switchToL3('m1');
    expect(state.l3GraphViewModel.nodes).toEqual([
      { id: 'A', label: 'NameA', type: 'class', file: 'a.py' },
      { id: 'B', label: 'NameB', type: 'fn', file: 'b.py' },
    ]);
    expect(state.l3GraphViewModel.edges).toEqual([{ source: 'A', target: 'B' }]);
  });

  it('handles structure with missing nodes/edges arrays', async () => {
    state.l2GraphViewModel = { nodes: [{ id: 'm1', source_nodes: ['A'] }] };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200, json: async () => ({}),
    });
    await switchToL3('m1');
    expect(state.l3GraphViewModel).toEqual({ nodes: [], edges: [] });
  });

  it('shows empty-state in graph-container on structure 404', async () => {
    state.l2GraphViewModel = { nodes: [{ id: 'm1', source_nodes: ['A'] }] };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 404, json: async () => ({}),
    });
    await switchToL3('m1');
    const container = document.getElementById('graph-container');
    expect(container.querySelector('.empty-state').textContent).toContain('結構資料不存在');
  });

  it('skips graph-container update if element absent on 404', async () => {
    state.l2GraphViewModel = { nodes: [{ id: 'm1', source_nodes: ['A'] }] };
    const container = document.getElementById('graph-container');
    container.id = 'graph-container-tmp';
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 404, json: async () => ({}),
    });
    try {
      await expect(switchToL3('m1')).resolves.toBeUndefined();
    } finally {
      container.id = 'graph-container';
    }
  });

  it('calls renderError on structure !ok non-404', async () => {
    state.l2GraphViewModel = { nodes: [{ id: 'm1', source_nodes: ['A'] }] };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 500,
      json: async () => ({ error: { message: 'down' } }),
    });
    await switchToL3('m1');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('down'));
  });

  it('uses status fallback on structure !ok with no body message', async () => {
    state.l2GraphViewModel = { nodes: [{ id: 'm1', source_nodes: ['A'] }] };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 502, json: async () => ({}),
    });
    await switchToL3('m1');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('502'));
  });

  it('handles unparseable error body for structure', async () => {
    state.l2GraphViewModel = { nodes: [{ id: 'm1', source_nodes: ['A'] }] };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 503, json: async () => { throw new Error('x'); },
    });
    await switchToL3('m1');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('503'));
  });

  it('calls renderError on network error', async () => {
    state.l2GraphViewModel = { nodes: [{ id: 'm1', source_nodes: ['A'] }] };
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('netfail'));
    await switchToL3('m1');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('netfail'));
  });

  it('uses "network error" fallback in catch', async () => {
    state.l2GraphViewModel = { nodes: [{ id: 'm1', source_nodes: ['A'] }] };
    vi.spyOn(globalThis, 'fetch').mockRejectedValue({});
    await switchToL3('m1');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('network error'));
  });

  it('handles module with undefined source_nodes', async () => {
    state.l2GraphViewModel = { nodes: [{ id: 'm1' }] };
    await switchToL3('m1');
    expect(graph.initGraph).toHaveBeenCalledWith('graph-container', { nodes: [], edges: [] });
  });
});

// ── switchToL1 ────────────────────────────────────────────────────

describe('switchToL1', () => {
  it('clears selection and renders L1 when l1GraphViewModel exists', () => {
    state.l1GraphViewModel = { nodes: [] };
    state.selectedFeatureId = 'f';
    state.selectedModuleId = 'm';
    switchToL1();
    expect(state.layerState).toBe('L1');
    expect(state.selectedFeatureId).toBeNull();
    expect(state.selectedModuleId).toBeNull();
    expect(graph.initGraph).toHaveBeenCalledWith('graph-container', state.l1GraphViewModel);
  });

  it('restores cytoscape selection when state.selectedId is set', () => {
    state.l1GraphViewModel = { nodes: [{ id: 'f1' }] };
    state.selectedId = 'f1';
    const nodeStub = { select: vi.fn() };
    state.cytoscapeInstance = { getElementById: vi.fn(() => nodeStub) };
    switchToL1();
    expect(state.cytoscapeInstance.getElementById).toHaveBeenCalledWith('f1');
    expect(nodeStub.select).toHaveBeenCalled();
  });

  it('does not throw when cytoscape returns null node', () => {
    state.l1GraphViewModel = { nodes: [] };
    state.selectedId = 'ghost';
    state.cytoscapeInstance = { getElementById: vi.fn(() => null) };
    expect(() => switchToL1()).not.toThrow();
  });

  it('does not call cytoscape when selectedId is null', () => {
    state.l1GraphViewModel = { nodes: [] };
    state.selectedId = null;
    const getById = vi.fn();
    state.cytoscapeInstance = { getElementById: getById };
    switchToL1();
    expect(getById).not.toHaveBeenCalled();
  });

  it('calls loadL1Graph when l1GraphViewModel is null', async () => {
    state.l1GraphViewModel = null;
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200, json: async () => ({ nodes: [] }),
    });
    switchToL1();
    // loadL1Graph is async — wait a tick
    await new Promise(r => setTimeout(r, 0));
    // initGraph called with the freshly loaded VM
    expect(graph.initGraph).toHaveBeenCalled();
  });
});

// ── switchToL2FromL3 ──────────────────────────────────────────────

describe('switchToL2FromL3', () => {
  it('switches state and re-renders L2 when l2GraphViewModel exists', () => {
    state.l2GraphViewModel = { nodes: [] };
    state.selectedModuleId = 'm1';
    switchToL2FromL3();
    expect(state.layerState).toBe('L2');
    expect(state.selectedModuleId).toBeNull();
    expect(graph.initGraph).toHaveBeenCalledWith('graph-container', state.l2GraphViewModel);
  });

  it('calls switchToL2 with selectedFeatureId when l2GraphViewModel is null', async () => {
    state.l2GraphViewModel = null;
    state.selectedFeatureId = 'feat-1';
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 404, json: async () => ({}),
    });
    state.l1GraphViewModel = { nodes: [{ id: 'feat-1', label: 'F' }] };
    switchToL2FromL3();
    await new Promise(r => setTimeout(r, 0));
    expect(state.selectedFeatureId).toBe('feat-1');
  });

  it('does nothing when l2GraphViewModel and selectedFeatureId both missing', () => {
    state.l2GraphViewModel = null;
    state.selectedFeatureId = null;
    expect(() => switchToL2FromL3()).not.toThrow();
    expect(graph.initGraph).not.toHaveBeenCalled();
  });
});

// ── loadLayerExplanation ──────────────────────────────────────────

describe('loadLayerExplanation', () => {
  it('sets state.layerExplanation and renders p tag on success', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200, json: async () => ({ explanation: 'hello world' }),
    });
    await loadLayerExplanation('feat-1', 'l2');
    expect(state.layerExplanation).toBe('hello world');
    const el = document.getElementById('layer-explanation');
    expect(el.querySelector('.layer-explanation-text').textContent).toBe('hello world');
  });

  it('does not insert p when explanation is empty', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200, json: async () => ({ explanation: '' }),
    });
    await loadLayerExplanation('feat-1', 'l2');
    expect(state.layerExplanation).toBeNull();
    const el = document.getElementById('layer-explanation');
    expect(el.querySelector('p')).toBeNull();
  });

  it('clears state and DOM on 404', async () => {
    state.layerExplanation = 'stale';
    const el = document.getElementById('layer-explanation');
    el.textContent = 'leftover';
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 404, json: async () => ({}),
    });
    await loadLayerExplanation('feat-1', 'l2');
    expect(state.layerExplanation).toBeNull();
    expect(el.textContent).toBe('');
  });

  it('returns early on !ok non-404 without touching state', async () => {
    state.layerExplanation = 'preserved';
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 500, json: async () => ({}),
    });
    await loadLayerExplanation('feat-1', 'l2');
    expect(state.layerExplanation).toBe('preserved');
  });

  it('returns early when #layer-explanation absent', async () => {
    const el = document.getElementById('layer-explanation');
    el.id = 'layer-explanation-tmp';
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200, json: async () => ({ explanation: 'x' }),
    });
    try {
      await loadLayerExplanation('feat-1', 'l2');
      // state.layerExplanation should NOT be set
      expect(state.layerExplanation).toBeNull();
    } finally {
      el.id = 'layer-explanation';
    }
  });

  it('silently catches network error', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('boom'));
    await expect(loadLayerExplanation('feat-1', 'l2')).resolves.toBeUndefined();
  });
});

// ── generateL2 ────────────────────────────────────────────────────

describe('generateL2', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('starts polling on ok response with job_id', async () => {
    let callCount = 0;
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ job_id: 'job-1' }) });
      }
      // status poll — return completed immediately
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ status: 'completed' }) });
    });
    const promise = generateL2('feat-1');
    await vi.advanceTimersByTimeAsync(1500);
    await promise;
    expect(callCount).toBeGreaterThanOrEqual(2);
  });

  it('calls renderError on !ok with message', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 500, json: async () => ({ error: { message: 'cannot generate' } }),
    });
    await generateL2('feat-1');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('cannot generate'));
  });

  it('uses status fallback on !ok', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 502, json: async () => ({}),
    });
    await generateL2('feat-1');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('502'));
  });

  it('handles unparseable error body', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 503, json: async () => { throw new Error('x'); },
    });
    await generateL2('feat-1');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('503'));
  });

  it('calls renderError on network failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('offline'));
    await generateL2('feat-1');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('offline'));
  });

  it('uses "network error" fallback in catch', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue({});
    await generateL2('feat-1');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('network error'));
  });
});

// ── generateLayerExplanation ──────────────────────────────────────

describe('generateLayerExplanation', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it('starts polling on ok response', async () => {
    let n = 0;
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => {
      n++;
      if (n === 1) return Promise.resolve({ ok: true, status: 200, json: async () => ({ job_id: 'j' }) });
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ status: 'completed' }) });
    });
    const p = generateLayerExplanation('feat-1', 'l2');
    await vi.advanceTimersByTimeAsync(1500);
    await p;
    expect(n).toBeGreaterThanOrEqual(2);
  });

  it('renderError on !ok', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 500, json: async () => ({ error: { message: 'gen-fail' } }),
    });
    await generateLayerExplanation('feat-1', 'l2');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('gen-fail'));
  });

  it('renderError uses status fallback', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 504, json: async () => ({}),
    });
    await generateLayerExplanation('feat-1', 'l2');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('504'));
  });

  it('handles unparseable error body', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 505, json: async () => { throw new Error('x'); },
    });
    await generateLayerExplanation('feat-1', 'l2');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('505'));
  });

  it('renderError on network failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('down'));
    await generateLayerExplanation('feat-1', 'l2');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('down'));
  });

  it('uses "network error" fallback in catch', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue({});
    await generateLayerExplanation('feat-1', 'l2');
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('network error'));
  });
});

// ── renderBreadcrumb ──────────────────────────────────────────────

describe('renderBreadcrumb', () => {
  it('returns early when #breadcrumb absent', () => {
    const el = document.getElementById('breadcrumb');
    el.id = 'breadcrumb-tmp';
    try {
      expect(() => renderBreadcrumb()).not.toThrow();
    } finally {
      el.id = 'breadcrumb';
    }
  });

  it('L1 — single span.breadcrumb-current, btnBackL1 hidden', () => {
    state.layerState = 'L1';
    renderBreadcrumb();
    const el = document.getElementById('breadcrumb');
    expect(el.querySelectorAll('.breadcrumb-current')).toHaveLength(1);
    expect(el.querySelector('button')).toBeNull();
    expect(els.btnBackL1.hidden).toBe(true);
  });

  it('L2 — 3 parts including L1 link', () => {
    state.layerState = 'L2';
    state.selectedFeatureId = 'feat-1';
    state.l1GraphViewModel = { nodes: [{ id: 'feat-1', label: 'My Feature' }] };
    renderBreadcrumb();
    const el = document.getElementById('breadcrumb');
    expect(el.querySelectorAll('.breadcrumb-link')).toHaveLength(1);
    expect(el.textContent).toContain('My Feature');
    expect(el.textContent).toContain('L2');
    expect(els.btnBackL1.hidden).toBe(false);
  });

  it('L2 — clicking L1 link triggers switchToL1', () => {
    state.layerState = 'L2';
    state.selectedFeatureId = 'feat-1';
    state.l1GraphViewModel = { nodes: [{ id: 'feat-1', label: 'F' }] };
    state.l2GraphViewModel = { nodes: [] };
    renderBreadcrumb();
    const link = document.querySelector('#breadcrumb .breadcrumb-link');
    link.click();
    expect(state.layerState).toBe('L1');
  });

  it('L2 — fallback label when feature missing', () => {
    state.layerState = 'L2';
    state.selectedFeatureId = null;
    renderBreadcrumb();
    const el = document.getElementById('breadcrumb');
    expect(el.textContent).toContain('（未知功能）');
  });

  it('L2 — feature.id when label missing', () => {
    state.layerState = 'L2';
    state.selectedFeatureId = 'feat-x';
    state.l1GraphViewModel = { nodes: [{ id: 'feat-x' }] };
    renderBreadcrumb();
    const el = document.getElementById('breadcrumb');
    expect(el.textContent).toContain('feat-x');
  });

  it('L3 — 5 parts with both L1 and L2 links', () => {
    state.layerState = 'L3';
    state.selectedFeatureId = 'feat-1';
    state.selectedModuleId = 'mod-1';
    state.l1GraphViewModel = { nodes: [{ id: 'feat-1', label: 'Feat' }] };
    state.l2GraphViewModel = { nodes: [{ id: 'mod-1', label: 'Mod' }] };
    renderBreadcrumb();
    const el = document.getElementById('breadcrumb');
    expect(el.querySelectorAll('.breadcrumb-link')).toHaveLength(3); // L1, feature, L2
    expect(el.textContent).toContain('Feat');
    expect(el.textContent).toContain('Mod');
  });

  it('L3 — fallback module label', () => {
    state.layerState = 'L3';
    state.selectedModuleId = null;
    renderBreadcrumb();
    const el = document.getElementById('breadcrumb');
    expect(el.textContent).toContain('（未知模組）');
  });

  it('L3 — module.id fallback when label missing', () => {
    state.layerState = 'L3';
    state.selectedModuleId = 'mod-x';
    state.l2GraphViewModel = { nodes: [{ id: 'mod-x' }] };
    renderBreadcrumb();
    expect(document.getElementById('breadcrumb').textContent).toContain('mod-x');
  });

  it('L3 — clicking feature breadcrumb triggers switchToL2', async () => {
    state.layerState = 'L3';
    state.selectedFeatureId = 'feat-1';
    state.selectedModuleId = 'mod-1';
    state.l1GraphViewModel = { nodes: [{ id: 'feat-1', label: 'F' }] };
    state.l2GraphViewModel = { nodes: [{ id: 'mod-1', label: 'M' }] };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 404, json: async () => ({}),
    });
    renderBreadcrumb();
    const links = document.querySelectorAll('#breadcrumb .breadcrumb-link');
    // links[1] is the feature breadcrumb
    links[1].click();
    await new Promise(r => setTimeout(r, 0));
    expect(state.layerState).toBe('L2');
  });

  it('L3 — clicking L2 link triggers switchToL2FromL3', () => {
    state.layerState = 'L3';
    state.selectedFeatureId = 'feat-1';
    state.selectedModuleId = 'mod-1';
    state.l1GraphViewModel = { nodes: [{ id: 'feat-1', label: 'F' }] };
    state.l2GraphViewModel = { nodes: [{ id: 'mod-1', label: 'M' }] };
    renderBreadcrumb();
    const links = document.querySelectorAll('#breadcrumb .breadcrumb-link');
    // links[2] is the L2 link
    links[2].click();
    expect(state.layerState).toBe('L2');
  });

  it('skips btnBackL1 toggle when btnBackL1 missing', () => {
    const orig = els.btnBackL1;
    els.btnBackL1 = null;
    try {
      state.layerState = 'L1';
      expect(() => renderBreadcrumb()).not.toThrow();
    } finally {
      els.btnBackL1 = orig;
    }
  });
});

// ── pollUntilComplete ─────────────────────────────────────────────

describe('pollUntilComplete', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it('calls onComplete async when status === completed', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200, json: async () => ({ status: 'completed' }),
    });
    const onComplete = vi.fn().mockResolvedValue(undefined);
    const promise = pollUntilComplete('job-1', onComplete);
    await vi.advanceTimersByTimeAsync(1500);
    await promise;
    expect(onComplete).toHaveBeenCalled();
  });

  it('calls renderError on status === failed with error_message', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200, json: async () => ({ status: 'failed', error_message: 'oops' }),
    });
    const p = pollUntilComplete('j', vi.fn());
    await vi.advanceTimersByTimeAsync(1500);
    await p;
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('oops'));
  });

  it('uses 未知錯誤 fallback when error_message missing', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200, json: async () => ({ status: 'failed' }),
    });
    const p = pollUntilComplete('j', vi.fn());
    await vi.advanceTimersByTimeAsync(1500);
    await p;
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('未知錯誤'));
  });

  it('continues polling on intermediate status', async () => {
    let count = 0;
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => {
      count++;
      return Promise.resolve({
        ok: true, status: 200,
        json: async () => ({ status: count < 3 ? 'running' : 'completed' }),
      });
    });
    const onComplete = vi.fn();
    const p = pollUntilComplete('j', onComplete);
    await vi.advanceTimersByTimeAsync(1500 * 3);
    await p;
    expect(onComplete).toHaveBeenCalled();
    expect(count).toBe(3);
  });

  it('clears interval silently on !res.ok', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 500, json: async () => ({}),
    });
    const onComplete = vi.fn();
    const p = pollUntilComplete('j', onComplete);
    await vi.advanceTimersByTimeAsync(1500);
    await p;
    expect(onComplete).not.toHaveBeenCalled();
    expect(uiDetail.renderError).not.toHaveBeenCalled();
  });

  it('clears interval silently on fetch catch', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('net'));
    const onComplete = vi.fn();
    const p = pollUntilComplete('j', onComplete);
    await vi.advanceTimersByTimeAsync(1500);
    await p;
    expect(onComplete).not.toHaveBeenCalled();
  });

  it('renderError on timeout after maxAttempts', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200, json: async () => ({ status: 'running' }),
    });
    const p = pollUntilComplete('j', vi.fn());
    await vi.advanceTimersByTimeAsync(1500 * 61);
    await p;
    expect(uiDetail.renderError).toHaveBeenCalledWith(expect.stringContaining('任務逾時'));
  });
});

// ── renderFeatureList ─────────────────────────────────────────────

describe('renderFeatureList', () => {
  it('returns early when #feature-list absent', () => {
    const list = document.getElementById('feature-list');
    list.id = 'feature-list-tmp';
    try {
      expect(() => renderFeatureList({ nodes: [] }, 'L1')).not.toThrow();
    } finally {
      list.id = 'feature-list';
    }
  });

  it('shows empty-state when viewModel is null', () => {
    renderFeatureList(null, 'L1');
    const list = document.getElementById('feature-list');
    expect(list.querySelector('.empty-state').textContent).toBe('此層級沒有節點。');
  });

  it('shows empty-state when nodes is missing', () => {
    renderFeatureList({}, 'L1');
    const list = document.getElementById('feature-list');
    expect(list.querySelector('.empty-state')).not.toBeNull();
  });

  it('L1 — renders confidence badge and description', () => {
    const vm = { nodes: [{ id: 'a', label: 'A', confidence: 'High', description: 'desc' }] };
    renderFeatureList(vm, 'L1');
    const list = document.getElementById('feature-list');
    expect(list.querySelector('.feature-card-label').textContent).toBe('A');
    expect(list.querySelector('.feature-card-desc').textContent).toBe('desc');
    expect(list.querySelector('.confidence-badge-high').textContent).toBe('High');
  });

  it('L1 — falls back to id when label missing', () => {
    renderFeatureList({ nodes: [{ id: 'only-id' }] }, 'L1');
    expect(document.querySelector('.feature-card-label').textContent).toBe('only-id');
  });

  it('L1 — applies active class when node.id === selectedId', () => {
    state.selectedId = 'a';
    renderFeatureList({ nodes: [{ id: 'a' }, { id: 'b' }] }, 'L1');
    const cards = document.querySelectorAll('.feature-card');
    expect(cards[0].classList.contains('active')).toBe(true);
    expect(cards[1].classList.contains('active')).toBe(false);
  });

  it('L1 — sets data-node-id', () => {
    renderFeatureList({ nodes: [{ id: 'xyz' }] }, 'L1');
    expect(document.querySelector('.feature-card').dataset.nodeId).toBe('xyz');
  });

  it('L1 — no confidence badge when confidence absent', () => {
    renderFeatureList({ nodes: [{ id: 'a' }] }, 'L1');
    expect(document.querySelector('.confidence-badge')).toBeNull();
  });

  it('L1 + diff_available — shows diff-tag with mapped label', () => {
    state.updateModel = {
      diff_available: true,
      changes: [{ id: 'a', change_type: 'added' }],
    };
    renderFeatureList({ nodes: [{ id: 'a' }] }, 'L1');
    const tag = document.querySelector('.diff-tag-added');
    expect(tag).not.toBeNull();
    expect(tag.textContent).toBe('+ 新增');
  });

  it('L1 + diff_available — removed label', () => {
    state.updateModel = { diff_available: true, changes: [{ id: 'a', change_type: 'removed' }] };
    renderFeatureList({ nodes: [{ id: 'a' }] }, 'L1');
    expect(document.querySelector('.diff-tag-removed').textContent).toBe('- 移除');
  });

  it('L1 + diff_available — attribute_changed label', () => {
    state.updateModel = { diff_available: true, changes: [{ id: 'a', change_type: 'attribute_changed' }] };
    renderFeatureList({ nodes: [{ id: 'a' }] }, 'L1');
    expect(document.querySelector('.diff-tag-attribute_changed').textContent).toBe('~ 屬性變更');
  });

  it('L1 + diff_available — dependency_changed label', () => {
    state.updateModel = { diff_available: true, changes: [{ id: 'a', change_type: 'dependency_changed' }] };
    renderFeatureList({ nodes: [{ id: 'a' }] }, 'L1');
    expect(document.querySelector('.diff-tag-dependency_changed').textContent).toBe('≠ 依賴變更');
  });

  it('L1 + diff_available — unknown change_type fallback', () => {
    state.updateModel = { diff_available: true, changes: [{ id: 'a', change_type: 'weird' }] };
    renderFeatureList({ nodes: [{ id: 'a' }] }, 'L1');
    expect(document.querySelector('.diff-tag-weird').textContent).toBe('weird');
  });

  it('L1 + diff_available — no tag when no matching change', () => {
    state.updateModel = { diff_available: true, changes: [{ id: 'other', change_type: 'added' }] };
    renderFeatureList({ nodes: [{ id: 'a' }] }, 'L1');
    expect(document.querySelector('.diff-tag-added')).toBeNull();
  });

  it('L1 + diff_available — no tag when match has no change_type', () => {
    state.updateModel = { diff_available: true, changes: [{ id: 'a' }] };
    renderFeatureList({ nodes: [{ id: 'a' }] }, 'L1');
    expect(document.querySelector('[class*="diff-tag"]')).toBeNull();
  });

  it('L1 + diff_available — handles missing changes array', () => {
    state.updateModel = { diff_available: true };
    renderFeatureList({ nodes: [{ id: 'a' }] }, 'L1');
    expect(document.querySelector('[class*="diff-tag"]')).toBeNull();
  });

  it('L2 — desc is confidence_reason, confidence badge appears', () => {
    renderFeatureList({ nodes: [{ id: 'a', confidence: 'Low', confidence_reason: 'because' }] }, 'L2');
    expect(document.querySelector('.feature-card-desc').textContent).toBe('because');
    expect(document.querySelector('.confidence-badge-low')).not.toBeNull();
  });

  it('L3 — desc is file, type badge appears', () => {
    renderFeatureList({ nodes: [{ id: 'a', file: 'a.py', type: 'class' }] }, 'L3');
    expect(document.querySelector('.feature-card-desc').textContent).toBe('a.py');
    const badge = document.querySelector('.confidence-badge');
    expect(badge.textContent).toBe('class');
  });

  it('L3 — no type badge when type absent', () => {
    renderFeatureList({ nodes: [{ id: 'a' }] }, 'L3');
    expect(document.querySelector('.confidence-badge')).toBeNull();
  });

  it('DIFF — change-badge with symbol + change_type, card has change-<type> class', () => {
    renderFeatureList({ nodes: [{ id: 'a', change_type: 'added' }] }, 'DIFF');
    const card = document.querySelector('.feature-card');
    expect(card.classList.contains('change-added')).toBe(true);
    const badge = document.querySelector('.change-badge');
    expect(badge.textContent).toContain('added');
  });

  it('DIFF — no badge when change_type missing, card still has change- class', () => {
    renderFeatureList({ nodes: [{ id: 'a' }] }, 'DIFF');
    const card = document.querySelector('.feature-card');
    expect(card.classList.contains('change-')).toBe(true);
    expect(document.querySelector('.change-badge')).toBeNull();
  });

  it('L1 click — sets selectedFeatureId, calls renderDetailPanelL1 with callbacks, syncs active', () => {
    state.l1GraphViewModel = { nodes: [{ id: 'a' }] };
    state.cytoscapeInstance = {
      elements: vi.fn(() => ({ unselect: vi.fn() })),
      getElementById: vi.fn(() => ({ select: vi.fn() })),
      animate: vi.fn(),
    };
    renderFeatureList({ nodes: [{ id: 'a' }, { id: 'b' }] }, 'L1');
    const cards = document.querySelectorAll('.feature-card');
    cards[1].click();
    expect(state.selectedFeatureId).toBe('b');
    expect(uiDetail.renderDetailPanelL1).toHaveBeenCalledWith({ id: 'b' }, expect.objectContaining({ onEnterL2: expect.any(Function) }));
    expect(cards[1].classList.contains('active')).toBe(true);
    expect(cards[0].classList.contains('active')).toBe(false);
  });

  it('L1 click — uses cytoscape unselect + select + animate', () => {
    const selectFn = vi.fn();
    const unselect = vi.fn();
    state.cytoscapeInstance = {
      elements: vi.fn(() => ({ unselect })),
      getElementById: vi.fn(() => ({ select: selectFn })),
      animate: vi.fn(),
    };
    renderFeatureList({ nodes: [{ id: 'a' }] }, 'L1');
    document.querySelector('.feature-card').click();
    expect(unselect).toHaveBeenCalled();
    expect(selectFn).toHaveBeenCalled();
    expect(state.cytoscapeInstance.animate).toHaveBeenCalled();
  });

  it('L1 click — no cytoscape instance: still updates DOM and detail panel', () => {
    state.cytoscapeInstance = null;
    renderFeatureList({ nodes: [{ id: 'a' }] }, 'L1');
    document.querySelector('.feature-card').click();
    expect(uiDetail.renderDetailPanelL1).toHaveBeenCalled();
  });

  it('L1 click — cytoscape getElementById returns null: no throw, no animate', () => {
    state.cytoscapeInstance = {
      elements: vi.fn(() => ({ unselect: vi.fn() })),
      getElementById: vi.fn(() => null),
      animate: vi.fn(),
    };
    renderFeatureList({ nodes: [{ id: 'a' }] }, 'L1');
    expect(() => document.querySelector('.feature-card').click()).not.toThrow();
    expect(state.cytoscapeInstance.animate).not.toHaveBeenCalled();
  });

  it('L2 click — sets selectedModuleId, calls renderDetailPanelL2 with both callbacks', () => {
    renderFeatureList({ nodes: [{ id: 'm1' }] }, 'L2');
    document.querySelector('.feature-card').click();
    expect(state.selectedModuleId).toBe('m1');
    expect(uiDetail.renderDetailPanelL2).toHaveBeenCalledWith({ id: 'm1' }, expect.objectContaining({
      onEnterL3: expect.any(Function),
      onGenerateLayerExplanation: expect.any(Function),
    }));
  });

  it('L3 click — calls renderDetailPanelL3 with node', () => {
    renderFeatureList({ nodes: [{ id: 'n1' }] }, 'L3');
    document.querySelector('.feature-card').click();
    expect(uiDetail.renderDetailPanelL3).toHaveBeenCalledWith({ id: 'n1' });
  });

  it('DIFF click — calls renderDetailPanelDiff with node', () => {
    renderFeatureList({ nodes: [{ id: 'n1', change_type: 'added' }] }, 'DIFF');
    document.querySelector('.feature-card').click();
    expect(uiDetail.renderDetailPanelDiff).toHaveBeenCalledWith({ id: 'n1', change_type: 'added' });
  });
});

// ── renderL2NotAnalyzed ───────────────────────────────────────────

describe('renderL2NotAnalyzed', () => {
  it('renders not-analyzed block in feature-list with button, hint, and code', () => {
    state.l1GraphViewModel = { nodes: [{ id: 'f1', label: 'My Feature' }] };
    renderL2NotAnalyzed('f1');
    const list = document.getElementById('feature-list');
    const block = list.querySelector('.not-analyzed-state');
    expect(block).not.toBeNull();
    expect(block.querySelector('.not-analyzed-title').textContent).toContain('My Feature');
    expect(block.querySelector('button.action-button').textContent).toBe('生成 L2 分析');
    expect(block.querySelector('.not-analyzed-hint')).not.toBeNull();
    expect(block.querySelector('.not-analyzed-cmd')).not.toBeNull();
  });

  it('renders title-only block in graph-container (no button, no hint)', () => {
    renderL2NotAnalyzed('f1');
    const container = document.getElementById('graph-container');
    const block = container.querySelector('.not-analyzed-state');
    expect(block).not.toBeNull();
    expect(block.querySelector('.not-analyzed-title')).not.toBeNull();
    expect(block.querySelector('button')).toBeNull();
    expect(block.querySelector('.not-analyzed-hint')).toBeNull();
  });

  it('button click disables button, shows 生成中, calls generateL2', async () => {
    vi.useFakeTimers();
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status: 500, json: async () => ({ error: { message: 'x' } }),
    });
    renderL2NotAnalyzed('f1');
    const btn = document.querySelector('#feature-list button.action-button');
    btn.click();
    expect(btn.disabled).toBe(true);
    expect(btn.textContent).toBe('生成中…');
    await vi.runOnlyPendingTimersAsync();
    vi.useRealTimers();
  });

  it('falls back to "（未知功能）" when featureId is empty', () => {
    renderL2NotAnalyzed(null);
    expect(document.querySelector('.not-analyzed-title').textContent).toContain('（未知功能）');
  });

  it('falls back to featureId when l1 node has no label', () => {
    state.l1GraphViewModel = { nodes: [{ id: 'feat-x' }] };
    renderL2NotAnalyzed('feat-x');
    expect(document.querySelector('.not-analyzed-title').textContent).toContain('feat-x');
  });

  it('skips feature-list update when element missing', () => {
    const list = document.getElementById('feature-list');
    list.id = 'feature-list-tmp';
    try {
      expect(() => renderL2NotAnalyzed('f1')).not.toThrow();
    } finally {
      list.id = 'feature-list';
    }
  });

  it('skips graph-container update when element missing', () => {
    const container = document.getElementById('graph-container');
    container.id = 'graph-container-tmp';
    try {
      expect(() => renderL2NotAnalyzed('f1')).not.toThrow();
    } finally {
      container.id = 'graph-container';
    }
  });
});

// ── switchToMindmap ───────────────────────────────────────────────

describe('switchToMindmap', () => {
  it('writes data to sessionStorage and opens popup window', () => {
    state.projectStatus = { project_path: '/my/proj' };
    state.l1GraphViewModel = { nodes: [{ id: 'n1', label: 'N1' }] };
    state.updateModel = {
      diff_available: true,
      changes: [{ id: 'n1', change_type: 'added', risk_flags: [] }],
    };
    const openSpy = vi.spyOn(window, 'open').mockReturnValue({});
    switchToMindmap();
    const stored = JSON.parse(sessionStorage.getItem('mindmap-data'));
    expect(stored.project).toBe('/my/proj');
    expect(stored.nodes).toHaveLength(1);
    expect(stored.diffNodes).toHaveLength(1);
    expect(stored.diffAvailable).toBe(true);
    expect(openSpy).toHaveBeenCalledWith(
      './mindmap-popup.html',
      'mindmap',
      expect.stringContaining('width=960'),
    );
  });

  it('uses "專案" fallback when projectStatus missing', () => {
    vi.spyOn(window, 'open').mockReturnValue({});
    switchToMindmap();
    const stored = JSON.parse(sessionStorage.getItem('mindmap-data'));
    expect(stored.project).toBe('專案');
    expect(stored.nodes).toEqual([]);
    expect(stored.diffNodes).toEqual([]);
    expect(stored.diffAvailable).toBe(false);
  });
});
