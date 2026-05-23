import { state } from './state.js';

const TYPE_TAG = {
  added:              '+ 新增',
  removed:            '− 移除',
  attribute_changed:  '~ 修改',
  dependency_changed: '≠ 依賴',
};

export function buildDisplayLabel(node) {
  const tag = TYPE_TAG[node.change_type];
  return tag ? `${tag}\n${node.label}` : node.label;
}

export function buildCytoscapeElements(viewModel) {
  const nodes = (viewModel.nodes || []).map((node) => {
    const { id, label, ...rest } = node;
    return { data: { id, label, displayLabel: buildDisplayLabel(node), ...rest } };
  });

  const featuresById = {};
  (viewModel.nodes || []).forEach((n) => { featuresById[n.id] = n; });

  const confRank = { high: 3, medium: 2, low: 1 };
  const lowestConf = (a, b) =>
    (confRank[a] ?? 2) <= (confRank[b] ?? 2) ? a : b;

  const edges = (viewModel.edges || []).map((edge) => {
    const { source, target, ...rest } = edge;
    const src = featuresById[source];
    const tgt = featuresById[target];
    const lc = lowestConf(src?.confidence ?? 'medium', tgt?.confidence ?? 'medium');
    return { data: { id: source + '-' + target, source, target, lowestConfidence: lc, ...rest } };
  });

  return [...nodes, ...edges];
}

export function buildCytoscapeStyle(_layerState) {
  return [
    {
      selector: 'node',
      style: {
        'label': 'data(displayLabel)',
        'text-valign': 'center',
        'text-halign': 'center',
        'font-size': '24px',
        'font-weight': '600',
        'color': '#17202a',
        'text-outline-width': 0,
        'text-wrap': 'wrap',
        'text-max-width': '280px',
        'background-color': '#fbfcfd',
        'border-width': 3,
        'border-color': '#d7dde5',
        'border-style': 'solid',
        'width': 'label',
        'height': 'label',
        'padding': '22px',
        'shape': 'roundrectangle',
      },
    },
    {
      selector: "node[change_type = 'added']",
      style: { 'background-color': '#d4edda', 'border-color': '#28a745', 'color': '#1d6e34' },
    },
    {
      selector: "node[change_type = 'removed']",
      style: { 'background-color': '#f8d7da', 'border-color': '#dc3545', 'color': '#9a1a1a' },
    },
    {
      selector: "node[change_type = 'attribute_changed']",
      style: { 'background-color': '#ffe0cc', 'border-color': '#fd7e14', 'color': '#7a4e00' },
    },
    {
      selector: "node[change_type = 'dependency_changed']",
      style: { 'background-color': '#ffe0cc', 'border-color': '#fd7e14', 'color': '#7a4e00' },
    },
    {
      selector: "node[confidence = 'high']",
      style: { 'border-style': 'solid', 'border-width': 3 },
    },
    {
      selector: "node[confidence = 'medium']",
      style: { 'border-style': 'dashed', 'border-width': 2 },
    },
    {
      selector: "node[confidence = 'low']",
      style: { 'border-style': 'dotted', 'border-width': 2 },
    },
    {
      selector: 'node:selected',
      style: { 'border-color': '#0f766e', 'border-width': 4, 'border-style': 'solid' },
    },
    {
      selector: 'edge',
      style: {
        'width': 2,
        'line-color': '#667085',
        'target-arrow-color': '#667085',
        'target-arrow-shape': 'triangle',
        'arrow-scale': 1.2,
        'curve-style': 'bezier',
        'font-size': '10px',
        'color': '#555',
        'opacity': 0.7,
      },
    },
    {
      selector: "edge[lowestConfidence = 'medium']",
      style: { 'line-style': 'dashed', 'opacity': 0.55 },
    },
    {
      selector: "edge[lowestConfidence = 'low']",
      style: { 'line-style': 'dotted', 'opacity': 0.45 },
    },
    {
      selector: 'edge:selected',
      style: { 'line-color': '#2196f3', 'target-arrow-color': '#2196f3' },
    },
  ];
}

export function buildMermaidText(viewModel) {
  const nodes = viewModel.nodes || [];
  const edges = viewModel.edges || [];
  const lines = ['flowchart LR'];

  nodes.forEach((node) => {
    const safeId = String(node.id).replace(/[^a-zA-Z0-9_]/g, '_');
    const label = (node.label || node.id).replace(/"/g, '#quot;');
    lines.push('  ' + safeId + '["' + label + '"]');
  });

  edges.forEach((edge) => {
    const safeSource = String(edge.source).replace(/[^a-zA-Z0-9_]/g, '_');
    const safeTarget = String(edge.target).replace(/[^a-zA-Z0-9_]/g, '_');
    lines.push('  ' + safeSource + ' --> ' + safeTarget);
  });

  if (nodes.length === 0) {
    lines.push('  empty["（無節點）"]');
  }

  return lines.join('\n');
}

export function renderMermaidFallback(viewModel, layerState) {
  const graphContainer = document.getElementById('graph-container');
  const fallbackEl = document.getElementById('mermaid-fallback');

  if (graphContainer) graphContainer.style.display = 'none';
  if (!fallbackEl) return;

  fallbackEl.style.display = 'block';
  fallbackEl.textContent = '';

  const indicator = document.createElement('div');
  indicator.className = 'fallback-indicator';
  indicator.textContent = '互動式圖形不可用（Cytoscape.js 未載入或初始化失敗），顯示文字圖形（' + layerState + ' 層）';
  fallbackEl.appendChild(indicator);

  const pre = document.createElement('pre');
  pre.className = 'mermaid-output';
  pre.textContent = buildMermaidText(viewModel);
  fallbackEl.appendChild(pre);
}

export function bindCytoscapeEvents(cy, callbacks) {
  const { onNodeTap } = callbacks || {};
  cy.on('tap', 'node', function (evt) {
    const nodeData = evt.target.data();
    if (onNodeTap) onNodeTap(nodeData);
  });
}

export function syncFeatureListSelection(_cy, featureId) {
  const featureList = document.getElementById('feature-list');
  if (!featureList) return;
  featureList.querySelectorAll('[data-node-id]').forEach((el) => {
    el.classList.toggle('active', el.dataset.nodeId === featureId);
  });
}

export function renderLegend() {
  const panel = document.getElementById('legend-panel');
  if (!panel) return;
  panel.textContent = '';

  const items = [
    { color: '#4caf50', label: '新增' },
    { color: '#f44336', label: '移除' },
    { color: '#ff9800', label: '修改' },
    { color: '#9e9e9e', label: '未變更' },
  ];

  items.forEach(({ color, label }) => {
    const item = document.createElement('span');
    item.className = 'legend-item';
    const swatch = document.createElement('span');
    swatch.className = 'legend-swatch';
    swatch.style.background = color;
    item.append(swatch, document.createTextNode(label));
    panel.appendChild(item);
  });
}

export function initZoomControls(cy) {
  const zoomControls = document.getElementById('zoom-controls');
  if (zoomControls) zoomControls.hidden = false;

  const fitBtn = document.getElementById('btn-zoom-fit');
  const inBtn  = document.getElementById('btn-zoom-in');
  const outBtn = document.getElementById('btn-zoom-out');

  if (fitBtn) fitBtn.onclick = () => {
    cy.fit(undefined, 60);
    if (cy.zoom() > 0.7) { cy.zoom(0.7); cy.center(); }
  };
  if (inBtn) inBtn.onclick = () => cy.zoom({
    level: cy.zoom() * 1.25,
    renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
  });
  if (outBtn) outBtn.onclick = () => cy.zoom({
    level: cy.zoom() / 1.25,
    renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
  });
}

export function hideZoomControls() {
  const zoomControls = document.getElementById('zoom-controls');
  if (zoomControls) zoomControls.hidden = true;
}

export function openGraphDrawer() {
  const drawer = document.getElementById('graph-drawer');
  const backdrop = document.getElementById('graph-backdrop');
  drawer?.classList.add('open');
  drawer?.removeAttribute('aria-hidden');
  if (backdrop) backdrop.hidden = false;
  if (state.cytoscapeInstance) {
    setTimeout(() => state.cytoscapeInstance.fit(undefined, 40), 320);
  }
}

export function closeGraphDrawer() {
  const drawer = document.getElementById('graph-drawer');
  const backdrop = document.getElementById('graph-backdrop');
  drawer?.classList.remove('open');
  drawer?.setAttribute('aria-hidden', 'true');
  if (backdrop) backdrop.hidden = true;
}

export function initGraph(containerId, viewModel) {
  const container = document.getElementById(containerId);

  if (!viewModel || !viewModel.nodes || viewModel.nodes.length === 0) {
    if (container) {
      container.textContent = '';
      const emptyDiv = document.createElement('div');
      emptyDiv.className = 'empty-state';
      emptyDiv.textContent = '此層級目前沒有節點資料。';
      container.appendChild(emptyDiv);
    }
    return;
  }

  if (typeof window.cytoscape === 'undefined') {
    renderMermaidFallback(viewModel, state.layerState);
    return;
  }

  if (container) container.textContent = '';

  try {
    const cy = window.cytoscape({
      container,
      elements: buildCytoscapeElements(viewModel),
      style: buildCytoscapeStyle(state.layerState),
      layout: { name: 'breadthfirst', directed: true, padding: 30, spacingFactor: 1.8, avoidOverlap: true },
      minZoom: 0.2,
      maxZoom: 4,
      wheelSensitivity: 0.15,
    });
    state.cytoscapeInstance = cy;
    state.cytoscapeAvailable = true;
    cy.one('layoutstop', () => {
      cy.nodes().forEach((node) => {
        if (node.width  && node.width()  < 260) node.style('width',  260);
        if (node.height && node.height() <  90) node.style('height',  90);
      });
    });
  } catch (_) {
    renderMermaidFallback(viewModel, state.layerState);
  }
}
