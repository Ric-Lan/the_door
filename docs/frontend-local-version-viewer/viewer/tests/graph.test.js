import { describe, it, expect, beforeEach } from 'vitest';
import {
  renderLegend,
  openGraphDrawer,
  closeGraphDrawer,
  initGraph,
  renderGridGraph,
  buildDisplayLabel,
} from '../js/graph.js';

// NOTE: 圖層已從 cytoscape 遷移為 DOM grid（graph.js renderGridGraph）。原 cytoscape/mermaid/zoom
// 機制（buildCytoscapeElements/Style、buildMermaidText、renderMermaidFallback、bindCytoscapeEvents、
// initZoomControls/hideZoomControls、syncFeatureListSelection）已連同其測一併移除（無 production caller）。

beforeEach(() => {
  document.getElementById('graph-container').textContent = '';
  document.getElementById('graph-container').style.display = '';
  const drawer = document.getElementById('graph-drawer');
  drawer.classList.remove('open');
  drawer.setAttribute('aria-hidden', 'true');
  document.getElementById('graph-backdrop').hidden = true;
  document.getElementById('legend-panel').textContent = '';
});

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

describe('initGraph', () => {
  it('shows .empty-state when viewModel is null', () => {
    expect(() => initGraph('graph-container', null)).not.toThrow();
    expect(document.querySelector('#graph-container .empty-state')).not.toBeNull();
  });

  it('shows .empty-state when nodes is empty', () => {
    expect(() => initGraph('graph-container', { nodes: [], edges: [] })).not.toThrow();
    expect(document.querySelector('#graph-container .empty-state')).not.toBeNull();
  });

  it('renders .gv-node grid cards for each node (current DOM-grid renderer)', () => {
    initGraph('graph-container', { nodes: [{ id: 'n1', label: 'N1' }, { id: 'n2', label: 'N2' }], edges: [] });
    expect(document.querySelectorAll('#graph-container .gv-node')).toHaveLength(2);
  });

  it('renders a .gv-grid-wrapper into the container', () => {
    initGraph('graph-container', { nodes: [{ id: 'n1', label: 'N1' }], edges: [] });
    expect(document.querySelector('#graph-container .gv-grid-wrapper')).not.toBeNull();
  });

  it('node card title reflects the node label', () => {
    initGraph('graph-container', { nodes: [{ id: 'n1', label: 'Hello' }], edges: [] });
    expect(document.querySelector('#graph-container .gv-node-title').textContent).toBe('Hello');
  });
});

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

// ── H1 confidence honesty (未評估 ≠ 謊報等級) ──────────────────────
describe('H1 confidence honesty', () => {
  it('grid node with confidence="unknown" gets conf-unknown class, not conf-high', () => {
    const container = document.createElement('div');
    renderGridGraph(container, { nodes: [{ id: 'n1', label: 'N1', confidence: 'unknown' }], edges: [] }, () => {});
    const card = container.querySelector('.gv-node');
    expect(card.classList.contains('conf-unknown')).toBe(true);
    expect(card.classList.contains('conf-high')).toBe(false);
  });

  it('grid node with MISSING confidence does NOT fall back to conf-high (no lying)', () => {
    const container = document.createElement('div');
    renderGridGraph(container, { nodes: [{ id: 'n1', label: 'N1' }], edges: [] }, () => {});
    const card = container.querySelector('.gv-node');
    expect(card.classList.contains('conf-high')).toBe(false);
    expect(card.classList.contains('conf-unknown')).toBe(true);
  });
});
