import { computeFlowLayout, edgeKey } from './flow-layout.js';

const TYPE_TAG = {
  added:              '+ 新增',
  removed:            '− 移除',
  attribute_changed:  '~ 修改',
  dependency_changed: '≠ 依賴',
};

const EDGE_COLOR = { gap: '#dc2626', backed: '#16a34a', default: '#94a3b8' };

export function buildIntegrationIndex(integration) {
  const idx = new Map();
  for (const r of integration?.relations || []) {
    idx.set(edgeKey(r.from_feature, r.to_feature), r.verdict);
  }
  return idx;
}

export function edgeStyle(edge, integrationIndex, backEdges) {
  const k = edgeKey(edge.source, edge.target);
  const verdict = integrationIndex.get(k);
  return {
    color: EDGE_COLOR[verdict] || EDGE_COLOR.default,
    dashed: backEdges.has(k),
  };
}

export function buildDisplayLabel(node) {
  const tag = TYPE_TAG[node.change_type];
  return tag ? `${tag}\n${node.label}` : node.label;
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
    { color: '#94a3b8', label: '→ 左＝入口 · 右＝底層' },
    { color: '#dc2626', label: '紅邊＝宣稱依賴沒接上' },
    { color: '#94a3b8', label: '虛線邊＝循環' },
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

export function openGraphDrawer() {
  const drawer = document.getElementById('graph-drawer');
  const backdrop = document.getElementById('graph-backdrop');
  drawer?.classList.add('open');
  drawer?.removeAttribute('aria-hidden');
  if (backdrop) backdrop.hidden = false;
}

export const CONF_LABEL = { high: '高信心', medium: '中信心', low: '低信心', unknown: '未評估' };
const TYPE_TAG_CLASS = {
  added: 'tag-added', removed: 'tag-removed',
  attribute_changed: 'tag-modified', dependency_changed: 'tag-modified',
};

function _buildNodeCard(node, onNodeClick) {
  const card = document.createElement('div');
  const conf = node.confidence || 'unknown';  // 未評估誠實化：缺值不謊報 high
  card.className = 'gv-node conf-' + conf;
  if (node.change_type) card.classList.add(node.change_type);
  card.dataset.nodeId = node.id;
  if (node.change_type && TYPE_TAG[node.change_type]) {
    const tag = document.createElement('div');
    tag.className = 'gv-node-tag ' + (TYPE_TAG_CLASS[node.change_type] || '');
    tag.textContent = TYPE_TAG[node.change_type];
    card.appendChild(tag);
  }
  const title = document.createElement('div');
  title.className = 'gv-node-title';
  title.textContent = node.label || node.id;
  card.appendChild(title);
  const meta = document.createElement('div');
  meta.className = 'gv-node-meta';
  const parts = [CONF_LABEL[conf] || conf];
  if (node.source_node_count) parts.push(node.source_node_count + ' nodes');
  meta.textContent = parts.join(' · ');
  card.appendChild(meta);
  if (onNodeClick) card.addEventListener('click', () => onNodeClick(node));
  return card;
}

const SVG_NS = 'http://www.w3.org/2000/svg';

function _makeArrowMarker(id, color) {
  const m = document.createElementNS(SVG_NS, 'marker');
  m.setAttribute('id', id);
  m.setAttribute('viewBox', '0 0 10 10');
  m.setAttribute('refX', '9');
  m.setAttribute('refY', '5');
  m.setAttribute('markerWidth', '7');
  m.setAttribute('markerHeight', '7');
  m.setAttribute('orient', 'auto-start-reverse');
  const p = document.createElementNS(SVG_NS, 'path');
  p.setAttribute('d', 'M 0 0 L 10 5 L 0 10 z');
  p.setAttribute('fill', color);
  m.appendChild(p);
  return m;
}

function _drawFlowEdges(flow, edges, cardMap, integration, backEdges) {
  const flowRect = flow.getBoundingClientRect();
  if (!flowRect.width) return; // jsdom / 未布局：沿用既有 early-return 慣例
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.classList.add('gv-edges');
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('width', flow.scrollWidth);
  svg.setAttribute('height', flow.scrollHeight);
  const defs = document.createElementNS(SVG_NS, 'defs');
  defs.appendChild(_makeArrowMarker('gv-arrow-gap', EDGE_COLOR.gap));
  defs.appendChild(_makeArrowMarker('gv-arrow-backed', EDGE_COLOR.backed));
  defs.appendChild(_makeArrowMarker('gv-arrow-default', EDGE_COLOR.default));
  svg.appendChild(defs);

  const idx = buildIntegrationIndex(integration);
  edges.forEach(edge => {
    const src = cardMap[edge.source];
    const tgt = cardMap[edge.target];
    if (!src || !tgt) return;
    const { color, dashed } = edgeStyle(edge, idx, backEdges);
    const sr = src.getBoundingClientRect();
    const tr = tgt.getBoundingClientRect();
    // 錨點（spec §4）：一般邊＝源卡右緣中點→目標卡左緣中點；back-edge＝源卡左緣→目標卡右緣
    let x1, y1, x2, y2;
    if (!dashed) {
      x1 = sr.right - flowRect.left;  y1 = sr.top + sr.height / 2 - flowRect.top;
      x2 = tr.left - flowRect.left;   y2 = tr.top + tr.height / 2 - flowRect.top;
    } else {
      x1 = sr.left - flowRect.left;   y1 = sr.top + sr.height / 2 - flowRect.top;
      x2 = tr.right - flowRect.left;  y2 = tr.top + tr.height / 2 - flowRect.top;
    }
    const line = document.createElementNS(SVG_NS, 'line');
    line.setAttribute('x1', x1); line.setAttribute('y1', y1);
    line.setAttribute('x2', x2); line.setAttribute('y2', y2);
    line.setAttribute('stroke', color);
    line.setAttribute('stroke-width', '1.5');
    if (dashed) line.setAttribute('stroke-dasharray', '6 4');
    const markerId = color === EDGE_COLOR.gap ? 'gv-arrow-gap'
      : color === EDGE_COLOR.backed ? 'gv-arrow-backed' : 'gv-arrow-default';
    line.setAttribute('marker-end', `url(#${markerId})`);
    svg.appendChild(line);
  });
  flow.insertBefore(svg, flow.firstChild);
}

export function renderFlowGraph(container, viewModel, onNodeClick) {
  container.textContent = '';
  const wrapper = document.createElement('div');
  wrapper.className = 'gv-flow-wrapper';
  const flow = document.createElement('div');
  flow.className = 'gv-flow';
  const nodeById = new Map((viewModel.nodes || []).map(n => [n.id, n]));
  const layout = computeFlowLayout(viewModel);
  const cardMap = {};

  const bandsRow = document.createElement('div');
  bandsRow.className = 'gv-bands';
  layout.bands.forEach(subs => {
    const band = document.createElement('div');
    band.className = 'gv-band';
    subs.forEach(ids => {
      const sub = document.createElement('div');
      sub.className = 'gv-subcol';
      ids.forEach(id => {
        const card = _buildNodeCard(nodeById.get(id), onNodeClick);
        sub.appendChild(card);
        cardMap[id] = card;
      });
      band.appendChild(sub);
    });
    bandsRow.appendChild(band);
  });
  flow.appendChild(bandsRow);

  if (layout.isolated.length) {
    const iso = document.createElement('div');
    iso.className = 'gv-isolated-row';
    const title = document.createElement('div');
    title.className = 'gv-isolated-title';
    title.textContent = '未宣告關聯';
    iso.appendChild(title);
    const sub = document.createElement('div');
    sub.className = 'gv-subcol';
    layout.isolated.forEach(id => {
      const card = _buildNodeCard(nodeById.get(id), onNodeClick);
      sub.appendChild(card);
      cardMap[id] = card;
    });
    iso.appendChild(sub);
    flow.appendChild(iso);
  }

  wrapper.appendChild(flow);
  container.appendChild(wrapper);
  const edges = viewModel.edges || [];
  if (edges.length) {
    requestAnimationFrame(() =>
      _drawFlowEdges(flow, edges, cardMap, viewModel.integration, layout.backEdges));
  }
}

export function closeGraphDrawer() {
  const drawer = document.getElementById('graph-drawer');
  const backdrop = document.getElementById('graph-backdrop');
  drawer?.classList.remove('open');
  drawer?.setAttribute('aria-hidden', 'true');
  if (backdrop) backdrop.hidden = true;
}

export function initGraph(containerId, viewModel, onNodeClick) {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (!viewModel || !viewModel.nodes || viewModel.nodes.length === 0) {
    container.textContent = '';
    const emptyDiv = document.createElement('div');
    emptyDiv.className = 'empty-state';
    emptyDiv.textContent = '此層級目前沒有節點資料。';
    container.appendChild(emptyDiv);
    return;
  }

  renderFlowGraph(container, viewModel, onNodeClick);
}
