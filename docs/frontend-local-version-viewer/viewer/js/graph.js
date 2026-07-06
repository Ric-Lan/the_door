import { computeFlowLayout } from './flow-layout.js';

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

function _drawFlowEdges(_flow, _edges, _cardMap, _integration, _backEdges) {
  // Task 3 實作：SVG 箭頭邊 + integration 色 + back-edge 虛線
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
