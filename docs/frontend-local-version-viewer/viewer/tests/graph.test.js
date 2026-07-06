import { describe, it, expect, beforeEach } from 'vitest';
import {
  renderLegend,
  openGraphDrawer,
  closeGraphDrawer,
  initGraph,
  renderFlowGraph,
  buildDisplayLabel,
  buildIntegrationIndex,
  edgeStyle,
} from '../js/graph.js';
import { edgeKey } from '../js/flow-layout.js';

// NOTE: 圖層已從 cytoscape 遷移為 DOM 流程圖（graph.js renderFlowGraph）。原 cytoscape/mermaid/zoom
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

describe('buildIntegrationIndex / edgeStyle', () => {
  const integration = { relations: [
    { from_feature: 'feat-a', to_feature: 'feat-db', verdict: 'gap' },
    { from_feature: 'feat-a', to_feature: 'feat-b',  verdict: 'backed' },
    { from_feature: 'feat-a', to_feature: 'feat-c',  verdict: 'not_assessed' },
  ] };

  it('gap 邊為紅', () => {
    const idx = buildIntegrationIndex(integration);
    expect(edgeStyle({ source: 'feat-a', target: 'feat-db' }, idx, new Set()).color).toBe('#dc2626');
  });
  it('backed 邊為綠', () => {
    const idx = buildIntegrationIndex(integration);
    expect(edgeStyle({ source: 'feat-a', target: 'feat-b' }, idx, new Set()).color).toBe('#16a34a');
  });
  it('not_assessed 與查無資料皆為灰（不洗成綠）', () => {
    const idx = buildIntegrationIndex(integration);
    expect(edgeStyle({ source: 'feat-a', target: 'feat-c' }, idx, new Set()).color).toBe('#94a3b8');
    expect(edgeStyle({ source: 'zz', target: 'yy' }, idx, new Set()).color).toBe('#94a3b8');
  });
  it('integration 為 null → 空 index → 全灰', () => {
    const idx = buildIntegrationIndex(null);
    expect(idx.size).toBe(0);
    expect(edgeStyle({ source: 'feat-a', target: 'feat-db' }, idx, new Set()).color).toBe('#94a3b8');
  });
  it('back-edge 標 dashed', () => {
    const be = new Set([edgeKey('b', 'a')]);
    expect(edgeStyle({ source: 'b', target: 'a' }, buildIntegrationIndex(null), be).dashed).toBe(true);
    expect(edgeStyle({ source: 'a', target: 'b' }, buildIntegrationIndex(null), be).dashed).toBe(false);
  });
});

describe('renderLegend', () => {
  it('包含方向/整合/循環三個新圖例項（共 7 項）', () => {
    renderLegend();
    expect(document.querySelectorAll('#legend-panel .legend-item')).toHaveLength(7);
    expect(document.getElementById('legend-panel').textContent).toContain('左＝入口');
    expect(document.getElementById('legend-panel').textContent).toContain('沒接上');
    expect(document.getElementById('legend-panel').textContent).toContain('循環');
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

  it('renders a .gv-flow-wrapper into the container', () => {
    initGraph('graph-container', { nodes: [{ id: 'n1', label: 'N1' }], edges: [] });
    expect(document.querySelector('#graph-container .gv-flow-wrapper')).not.toBeNull();
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

describe('renderFlowGraph 分層布局', () => {
  it('鏈 a→b 產生兩個 .gv-band，a 在第一欄', () => {
    const container = document.createElement('div');
    renderFlowGraph(container,
      { nodes: [{ id: 'b', label: 'B' }, { id: 'a', label: 'A' }],
        edges: [{ source: 'a', target: 'b' }] }, () => {});
    const bands = container.querySelectorAll('.gv-band');
    expect(bands).toHaveLength(2);
    expect(bands[0].querySelector('.gv-node-title').textContent).toBe('A');
    expect(bands[1].querySelector('.gv-node-title').textContent).toBe('B');
  });

  it('無邊節點進 .gv-isolated-row，標題為 未宣告關聯', () => {
    const container = document.createElement('div');
    renderFlowGraph(container,
      { nodes: [{ id: 'a', label: 'A' }, { id: 'x', label: 'X' }, { id: 'b', label: 'B' }],
        edges: [{ source: 'a', target: 'b' }] }, () => {});
    const iso = container.querySelector('.gv-isolated-row');
    expect(iso).not.toBeNull();
    expect(iso.querySelector('.gv-isolated-title').textContent).toBe('未宣告關聯');
    expect(iso.querySelectorAll('.gv-node')).toHaveLength(1);
  });

  it('無孤島時不渲染 .gv-isolated-row', () => {
    const container = document.createElement('div');
    renderFlowGraph(container,
      { nodes: [{ id: 'a', label: 'A' }, { id: 'b', label: 'B' }],
        edges: [{ source: 'a', target: 'b' }] }, () => {});
    expect(container.querySelector('.gv-isolated-row')).toBeNull();
  });

  it('卡片 click handler 保留（點擊回傳 node）', () => {
    const container = document.createElement('div');
    let clicked = null;
    renderFlowGraph(container,
      { nodes: [{ id: 'a', label: 'A' }], edges: [] }, (n) => { clicked = n; });
    container.querySelector('.gv-node').click();
    expect(clicked.id).toBe('a');
  });
});

// ── H1 confidence honesty (未評估 ≠ 謊報等級) ──────────────────────
describe('H1 confidence honesty', () => {
  it('flow node with confidence="unknown" gets conf-unknown class, not conf-high', () => {
    const container = document.createElement('div');
    renderFlowGraph(container, { nodes: [{ id: 'n1', label: 'N1', confidence: 'unknown' }], edges: [] }, () => {});
    const card = container.querySelector('.gv-node');
    expect(card.classList.contains('conf-unknown')).toBe(true);
    expect(card.classList.contains('conf-high')).toBe(false);
  });

  it('flow node with MISSING confidence does NOT fall back to conf-high (no lying)', () => {
    const container = document.createElement('div');
    renderFlowGraph(container, { nodes: [{ id: 'n1', label: 'N1' }], edges: [] }, () => {});
    const card = container.querySelector('.gv-node');
    expect(card.classList.contains('conf-high')).toBe(false);
    expect(card.classList.contains('conf-unknown')).toBe(true);
  });

  it('card meta renders confidence-badge with same classes as main list', () => {
    const container = document.createElement('div');
    renderFlowGraph(container,
      { nodes: [{ id: 'n1', label: 'N1', confidence: 'high' },
                { id: 'n2', label: 'N2', confidence: 'low' },
                { id: 'n3', label: 'N3' }], edges: [] }, () => {});
    const badges = container.querySelectorAll('.gv-node-meta .confidence-badge');
    expect(badges).toHaveLength(3);
    expect(container.querySelector('.confidence-badge-high').textContent).toBe('高信心');
    expect(container.querySelector('.confidence-badge-low').textContent).toBe('低信心');
    // 缺值＝unknown：badge 掛 -unknown（無專屬色規則、落基底灰），不得掛 high 色
    expect(container.querySelector('.confidence-badge-unknown').textContent).toBe('未評估');
  });
});
