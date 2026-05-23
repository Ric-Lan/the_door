import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import {
  buildCytoscapeElements,
  buildCytoscapeStyle,
  buildMermaidText,
  buildDisplayLabel,
  renderMermaidFallback,
  openGraphDrawer,
  closeGraphDrawer,
  hideZoomControls,
  renderLegend,
  initGraph,
  bindCytoscapeEvents,
  syncFeatureListSelection,
  initZoomControls,
} from '../js/graph.js';

// Reset mutable DOM elements before each test
beforeEach(() => {
  document.getElementById('graph-container').textContent = '';
  document.getElementById('graph-container').style.display = '';
  const mf = document.getElementById('mermaid-fallback');
  mf.style.display = 'none';
  mf.textContent = '';
  const drawer = document.getElementById('graph-drawer');
  drawer.classList.remove('open');
  drawer.setAttribute('aria-hidden', 'true');
  document.getElementById('graph-backdrop').hidden = true;
  document.getElementById('zoom-controls').hidden = true;
  document.getElementById('legend-panel').textContent = '';
});

afterEach(() => {
  delete window.cytoscape;
});

// ── buildCytoscapeElements ────────────────────────────────────────

describe('buildCytoscapeElements', () => {
  it('returns [] for empty viewModel', () => {
    expect(buildCytoscapeElements({ nodes: [], edges: [] })).toEqual([]);
    expect(buildCytoscapeElements({})).toEqual([]);
  });

  it('maps nodes to { data: { id, label, displayLabel, ...rest } }', () => {
    const vm = { nodes: [{ id: 'feat-1', label: 'Feature 1', confidence: 'high' }], edges: [] };
    const elements = buildCytoscapeElements(vm);
    expect(elements).toHaveLength(1);
    expect(elements[0]).toEqual({ data: { id: 'feat-1', label: 'Feature 1', displayLabel: 'Feature 1', confidence: 'high' } });
  });

  it('maps edges to { data: { id, source, target, lowestConfidence, ...rest } }', () => {
    const vm = {
      nodes: [
        { id: 'a', label: 'A', confidence: 'high' },
        { id: 'b', label: 'B', confidence: 'low' },
      ],
      edges: [{ source: 'a', target: 'b' }],
    };
    const elements = buildCytoscapeElements(vm);
    const edge = elements.find(e => e.data.source);
    expect(edge.data.id).toBe('a-b');
    expect(edge.data.source).toBe('a');
    expect(edge.data.target).toBe('b');
    expect(edge.data.lowestConfidence).toBeDefined();
  });

  it('lowestConfidence(high, low) = "low"', () => {
    const vm = {
      nodes: [
        { id: 'a', label: 'A', confidence: 'high' },
        { id: 'b', label: 'B', confidence: 'low' },
      ],
      edges: [{ source: 'a', target: 'b' }],
    };
    const elements = buildCytoscapeElements(vm);
    const edge = elements.find(e => e.data.source === 'a');
    expect(edge.data.lowestConfidence).toBe('low');
  });

  it('lowestConfidence(medium, medium) = "medium"', () => {
    const vm = {
      nodes: [
        { id: 'a', label: 'A', confidence: 'medium' },
        { id: 'b', label: 'B', confidence: 'medium' },
      ],
      edges: [{ source: 'a', target: 'b' }],
    };
    const elements = buildCytoscapeElements(vm);
    const edge = elements.find(e => e.data.source === 'a');
    expect(edge.data.lowestConfidence).toBe('medium');
  });

  it('lowestConfidence defaults to medium when node not found', () => {
    const vm = {
      nodes: [],
      edges: [{ source: 'x', target: 'y' }],
    };
    const elements = buildCytoscapeElements(vm);
    expect(elements[0].data.lowestConfidence).toBe('medium');
  });

  it('lowestConfidence treats unknown confidence as medium (rank 2) on source', () => {
    const vm = {
      nodes: [
        { id: 'a', label: 'A', confidence: 'unknown' },
        { id: 'b', label: 'B', confidence: 'high' },
      ],
      edges: [{ source: 'a', target: 'b' }],
    };
    const elements = buildCytoscapeElements(vm);
    const edge = elements.find(e => e.data.source === 'a');
    // unknown treated as 2, high=3: 2 <= 3 → returns 'unknown' (lower rank)
    expect(edge.data.lowestConfidence).toBe('unknown');
  });

  it('lowestConfidence treats unknown confidence as medium (rank 2) on target', () => {
    const vm = {
      nodes: [
        { id: 'a', label: 'A', confidence: 'high' },
        { id: 'b', label: 'B', confidence: 'unknown' },
      ],
      edges: [{ source: 'a', target: 'b' }],
    };
    const elements = buildCytoscapeElements(vm);
    const edge = elements.find(e => e.data.source === 'a');
    // high=3, unknown treated as 2: 3 <= 2 → false → returns 'unknown' (= b)
    expect(edge.data.lowestConfidence).toBe('unknown');
  });

  it('includes extra node fields in data', () => {
    const vm = {
      nodes: [{ id: 'f1', label: 'F1', confidence: 'high', description: 'desc' }],
      edges: [],
    };
    const elements = buildCytoscapeElements(vm);
    expect(elements[0].data.description).toBe('desc');
  });
});

// ── buildCytoscapeStyle ───────────────────────────────────────────

describe('buildCytoscapeStyle', () => {
  it('returns an array with at least 10 entries', () => {
    const style = buildCytoscapeStyle('L1');
    expect(Array.isArray(style)).toBe(true);
    expect(style.length).toBeGreaterThanOrEqual(10);
  });

  it('base node selector has background-color #fbfcfd', () => {
    const style = buildCytoscapeStyle('L1');
    const nodeRule = style.find(r => r.selector === 'node');
    expect(nodeRule?.style?.['background-color']).toBe('#fbfcfd');
  });

  it('added node has background-color #d4edda', () => {
    const style = buildCytoscapeStyle('L1');
    const rule = style.find(r => r.selector === "node[change_type = 'added']");
    expect(rule?.style?.['background-color']).toBe('#d4edda');
  });

  it('removed node has background-color #f8d7da', () => {
    const style = buildCytoscapeStyle('L1');
    const rule = style.find(r => r.selector === "node[change_type = 'removed']");
    expect(rule?.style?.['background-color']).toBe('#f8d7da');
  });

  it('medium confidence node has border-style dashed', () => {
    const style = buildCytoscapeStyle('L1');
    const rule = style.find(r => r.selector === "node[confidence = 'medium']");
    expect(rule?.style?.['border-style']).toBe('dashed');
  });

  it('selected node has border-color #0f766e', () => {
    const style = buildCytoscapeStyle('L1');
    const rule = style.find(r => r.selector === 'node:selected');
    expect(rule?.style?.['border-color']).toBe('#0f766e');
  });
});

// ── buildMermaidText ──────────────────────────────────────────────

describe('buildMermaidText', () => {
  it('starts with "flowchart LR"', () => {
    const text = buildMermaidText({ nodes: [], edges: [] });
    expect(text).toContain('flowchart LR');
  });

  it('works when nodes and edges are missing (undefined)', () => {
    const text = buildMermaidText({});
    expect(text).toContain('flowchart LR');
  });

  it('includes node label in output', () => {
    const text = buildMermaidText({
      nodes: [{ id: 'feat-1', label: 'My Feature' }],
      edges: [],
    });
    expect(text).toContain('My Feature');
  });

  it('uses node id as label when label is missing', () => {
    const text = buildMermaidText({
      nodes: [{ id: 'feat-1' }],
      edges: [],
    });
    expect(text).toContain('feat-1');
  });

  it('replaces double quotes with #quot; in node labels', () => {
    const text = buildMermaidText({
      nodes: [{ id: 'feat-1', label: 'Say "hello"' }],
      edges: [],
    });
    expect(text).not.toContain('"hello"');
    expect(text).toContain('#quot;hello#quot;');
  });

  it('includes edge arrow in output', () => {
    const text = buildMermaidText({
      nodes: [{ id: 'a', label: 'A' }, { id: 'b', label: 'B' }],
      edges: [{ source: 'a', target: 'b' }],
    });
    expect(text).toContain('-->');
  });
});

// ── renderMermaidFallback ─────────────────────────────────────────

describe('renderMermaidFallback', () => {
  it('hides #graph-container and shows #mermaid-fallback', () => {
    renderMermaidFallback({ nodes: [], edges: [] }, 'L1');
    expect(document.getElementById('graph-container').style.display).toBe('none');
    expect(document.getElementById('mermaid-fallback').style.display).toBe('block');
  });

  it('inserts a .fallback-indicator element', () => {
    renderMermaidFallback({ nodes: [], edges: [] }, 'L1');
    const indicator = document.querySelector('.fallback-indicator');
    expect(indicator).not.toBeNull();
    expect(indicator.textContent).toContain('L1');
  });

  it('inserts a pre.mermaid-output element', () => {
    renderMermaidFallback({ nodes: [], edges: [] }, 'L2');
    const pre = document.querySelector('pre.mermaid-output');
    expect(pre).not.toBeNull();
  });

  it('returns early when #mermaid-fallback is missing', () => {
    const mf = document.getElementById('mermaid-fallback');
    mf.id = 'mermaid-fallback-disabled';
    expect(() => renderMermaidFallback({ nodes: [], edges: [] }, 'L1')).not.toThrow();
    mf.id = 'mermaid-fallback';
  });
});

// ── openGraphDrawer / closeGraphDrawer ────────────────────────────

describe('openGraphDrawer', () => {
  it('adds .open class to #graph-drawer', () => {
    openGraphDrawer();
    expect(document.getElementById('graph-drawer').classList.contains('open')).toBe(true);
  });

  it('removes aria-hidden from #graph-drawer', () => {
    openGraphDrawer();
    expect(document.getElementById('graph-drawer').hasAttribute('aria-hidden')).toBe(false);
  });

  it('sets #graph-backdrop hidden = false', () => {
    openGraphDrawer();
    expect(document.getElementById('graph-backdrop').hidden).toBe(false);
  });

  it('calls cytoscapeInstance.fit when instance exists', async () => {
    vi.useFakeTimers();
    const { state } = await import('../js/state.js');
    const mockFit = vi.fn();
    state.cytoscapeInstance = { fit: mockFit };
    openGraphDrawer();
    vi.runAllTimers();
    expect(mockFit).toHaveBeenCalled();
    state.cytoscapeInstance = null;
    vi.useRealTimers();
  });
});

describe('closeGraphDrawer', () => {
  beforeEach(() => {
    // Start in open state
    document.getElementById('graph-drawer').classList.add('open');
    document.getElementById('graph-drawer').removeAttribute('aria-hidden');
    document.getElementById('graph-backdrop').hidden = false;
  });

  it('removes .open class from #graph-drawer', () => {
    closeGraphDrawer();
    expect(document.getElementById('graph-drawer').classList.contains('open')).toBe(false);
  });

  it('sets aria-hidden = "true" on #graph-drawer', () => {
    closeGraphDrawer();
    expect(document.getElementById('graph-drawer').getAttribute('aria-hidden')).toBe('true');
  });

  it('sets #graph-backdrop hidden = true', () => {
    closeGraphDrawer();
    expect(document.getElementById('graph-backdrop').hidden).toBe(true);
  });
});

// ── hideZoomControls ──────────────────────────────────────────────

describe('hideZoomControls', () => {
  it('sets #zoom-controls hidden = true', () => {
    document.getElementById('zoom-controls').hidden = false;
    hideZoomControls();
    expect(document.getElementById('zoom-controls').hidden).toBe(true);
  });
});

// ── renderLegend ──────────────────────────────────────────────────

describe('renderLegend', () => {
  it('inserts 4 .legend-item elements into #legend-panel', () => {
    renderLegend();
    const items = document.querySelectorAll('#legend-panel .legend-item');
    expect(items).toHaveLength(4);
  });

  it('does not throw when #legend-panel is missing', () => {
    const panel = document.getElementById('legend-panel');
    panel.id = 'legend-panel-disabled';
    expect(() => renderLegend()).not.toThrow();
    panel.id = 'legend-panel';
  });
});

// ── initGraph ─────────────────────────────────────────────────────

describe('initGraph', () => {
  it('shows .empty-state when viewModel is null', () => {
    expect(() => initGraph('graph-container', null)).not.toThrow();
    expect(document.querySelector('#graph-container .empty-state')).not.toBeNull();
  });

  it('shows .empty-state when nodes is empty', () => {
    expect(() => initGraph('graph-container', { nodes: [], edges: [] })).not.toThrow();
    expect(document.querySelector('#graph-container .empty-state')).not.toBeNull();
  });

  it('calls renderMermaidFallback when window.cytoscape is undefined', () => {
    delete window.cytoscape;
    initGraph('graph-container', { nodes: [{ id: 'n1', label: 'N1' }], edges: [] });
    expect(document.getElementById('mermaid-fallback').style.display).toBe('block');
  });

  it('sets cytoscapeInstance and cytoscapeAvailable when cytoscape succeeds', async () => {
    const { state } = await import('../js/state.js');
    const mockCy = {
      one: vi.fn(),
      on: vi.fn(),
      nodes: vi.fn(() => ({ forEach: vi.fn() })),
    };
    window.cytoscape = vi.fn(() => mockCy);
    initGraph('graph-container', { nodes: [{ id: 'n1', label: 'N1' }], edges: [] });
    expect(state.cytoscapeInstance).toBe(mockCy);
    expect(state.cytoscapeAvailable).toBe(true);
  });

  it('layoutstop callback runs node sizing logic', async () => {
    let layoutstopCb;
    const mockNode = {
      width: vi.fn(() => 100),
      height: vi.fn(() => 50),
      style: vi.fn(),
    };
    const mockCy = {
      one: vi.fn((evt, cb) => { if (evt === 'layoutstop') layoutstopCb = cb; }),
      on: vi.fn(),
      nodes: vi.fn(() => ({ forEach: (fn) => fn(mockNode) })),
    };
    window.cytoscape = vi.fn(() => mockCy);
    initGraph('graph-container', { nodes: [{ id: 'n1', label: 'N1' }], edges: [] });
    layoutstopCb();
    expect(mockNode.style).toHaveBeenCalledWith('width', 260);
    expect(mockNode.style).toHaveBeenCalledWith('height', 90);
  });

  it('calls renderMermaidFallback when cytoscape constructor throws', () => {
    window.cytoscape = vi.fn(() => { throw new Error('init failed'); });
    initGraph('graph-container', { nodes: [{ id: 'n1', label: 'N1' }], edges: [] });
    expect(document.getElementById('mermaid-fallback').style.display).toBe('block');
  });
});

// ── bindCytoscapeEvents ───────────────────────────────────────────

describe('bindCytoscapeEvents', () => {
  it('registers tap handler on cy without throwing', () => {
    const mockCy = { on: vi.fn() };
    expect(() => bindCytoscapeEvents(mockCy, { onNodeTap: vi.fn() })).not.toThrow();
    expect(mockCy.on).toHaveBeenCalledWith('tap', 'node', expect.any(Function));
  });

  it('calls onNodeTap callback when a node is tapped', () => {
    let tapHandler;
    const mockCy = { on: vi.fn((evt, sel, fn) => { tapHandler = fn; }) };
    const onNodeTap = vi.fn();
    bindCytoscapeEvents(mockCy, { onNodeTap });
    const mockNode = { data: vi.fn(() => ({ id: 'feat-1', label: 'F' }) ) };
    tapHandler({ target: mockNode });
    expect(onNodeTap).toHaveBeenCalledWith({ id: 'feat-1', label: 'F' });
  });

  it('does not throw when callbacks is null', () => {
    let tapHandler;
    const mockCy = { on: vi.fn((evt, sel, fn) => { tapHandler = fn; }) };
    expect(() => bindCytoscapeEvents(mockCy, null)).not.toThrow();
    // Tap with no onNodeTap should not throw
    const mockNode = { data: vi.fn(() => ({ id: 'n1' })) };
    expect(() => tapHandler({ target: mockNode })).not.toThrow();
  });
});

// ── syncFeatureListSelection ──────────────────────────────────────

describe('syncFeatureListSelection', () => {
  it('adds active class to matching item and removes from others', () => {
    const list = document.getElementById('feature-list');
    list.innerHTML = `
      <button data-node-id="feat-1">F1</button>
      <button data-node-id="feat-2">F2</button>
    `;
    syncFeatureListSelection(null, 'feat-1');
    expect(list.querySelector('[data-node-id="feat-1"]').classList.contains('active')).toBe(true);
    expect(list.querySelector('[data-node-id="feat-2"]').classList.contains('active')).toBe(false);
  });

  it('does not throw when feature-list is empty', () => {
    document.getElementById('feature-list').innerHTML = '';
    expect(() => syncFeatureListSelection(null, 'feat-x')).not.toThrow();
  });

  it('does not throw when #feature-list element is missing', () => {
    const list = document.getElementById('feature-list');
    list.id = 'feature-list-disabled';
    expect(() => syncFeatureListSelection(null, 'feat-x')).not.toThrow();
    list.id = 'feature-list';
  });
});

// ── initZoomControls ──────────────────────────────────────────────

describe('initZoomControls', () => {
  it('shows #zoom-controls and wires button onclick handlers', () => {
    const mockCy = {
      fit: vi.fn(),
      zoom: vi.fn(() => 0.5),
      center: vi.fn(),
      width: vi.fn(() => 800),
      height: vi.fn(() => 600),
    };
    initZoomControls(mockCy);
    expect(document.getElementById('zoom-controls').hidden).toBe(false);
    expect(document.getElementById('btn-zoom-fit').onclick).toBeTypeOf('function');
    expect(document.getElementById('btn-zoom-in').onclick).toBeTypeOf('function');
    expect(document.getElementById('btn-zoom-out').onclick).toBeTypeOf('function');
  });

  it('zoom buttons call cy methods when clicked', () => {
    const mockCy = {
      fit: vi.fn(),
      zoom: vi.fn(() => 0.5),
      center: vi.fn(),
      width: vi.fn(() => 800),
      height: vi.fn(() => 600),
    };
    initZoomControls(mockCy);
    document.getElementById('btn-zoom-fit').onclick();
    document.getElementById('btn-zoom-in').onclick();
    document.getElementById('btn-zoom-out').onclick();
    expect(mockCy.fit).toHaveBeenCalled();
    expect(mockCy.zoom).toHaveBeenCalled();
  });

  it('fit button calls zoom(0.7) and center() when zoom > 0.7', () => {
    const mockCy = {
      fit: vi.fn(),
      zoom: vi.fn(() => 0.9),
      center: vi.fn(),
      width: vi.fn(() => 800),
      height: vi.fn(() => 600),
    };
    initZoomControls(mockCy);
    document.getElementById('btn-zoom-fit').onclick();
    expect(mockCy.center).toHaveBeenCalled();
  });
});

// ── buildDisplayLabel ─────────────────────────────────────────────

describe('buildDisplayLabel', () => {
  it('prepends type tag for added', () => {
    expect(buildDisplayLabel({ label: 'Foo', change_type: 'added' })).toBe('+ 新增\nFoo');
  });
  it('no tag when change_type missing', () => {
    expect(buildDisplayLabel({ label: 'Foo' })).toBe('Foo');
  });
  it('dependency_changed → ≠ 依賴', () => {
    expect(buildDisplayLabel({ label: 'X', change_type: 'dependency_changed' })).toBe('≠ 依賴\nX');
  });
  it('removed → − 移除', () => {
    expect(buildDisplayLabel({ label: 'Bar', change_type: 'removed' })).toBe('− 移除\nBar');
  });
  it('attribute_changed → ~ 修改', () => {
    expect(buildDisplayLabel({ label: 'Baz', change_type: 'attribute_changed' })).toBe('~ 修改\nBaz');
  });
});
