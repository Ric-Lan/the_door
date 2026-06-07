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

function _drawGridEdges(grid, edges, cardMap) {
  const gridRect = grid.getBoundingClientRect();
  if (!gridRect.width) return;
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.classList.add('gv-edges');
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('width', grid.scrollWidth);
  svg.setAttribute('height', grid.scrollHeight);
  edges.forEach(edge => {
    const src = cardMap[edge.source];
    const tgt = cardMap[edge.target];
    if (!src || !tgt) return;
    const sr = src.getBoundingClientRect();
    const tr = tgt.getBoundingClientRect();
    const x1 = sr.left - gridRect.left + sr.width / 2;
    const y1 = sr.top  - gridRect.top  + sr.height / 2;
    const x2 = tr.left - gridRect.left + tr.width / 2;
    const y2 = tr.top  - gridRect.top  + tr.height / 2;
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', x1); line.setAttribute('y1', y1);
    line.setAttribute('x2', x2); line.setAttribute('y2', y2);
    line.setAttribute('stroke', '#94a3b8');
    line.setAttribute('stroke-width', '1.5');
    const conf = edge.lowestConfidence || 'unknown';
    if (conf === 'medium')  line.setAttribute('stroke-dasharray', '5 4');
    if (conf === 'low')     line.setAttribute('stroke-dasharray', '2 4');
    if (conf === 'unknown') line.setAttribute('stroke-dasharray', '1 3');  // 未評估：與 high 實線可區分
    svg.appendChild(line);
  });
  grid.insertBefore(svg, grid.firstChild);
}

export function renderGridGraph(container, viewModel, onNodeClick) {
  container.textContent = '';
  const wrapper = document.createElement('div');
  wrapper.className = 'gv-grid-wrapper';
  const grid = document.createElement('div');
  grid.className = 'gv-grid';
  const cardMap = {};
  (viewModel.nodes || []).forEach(node => {
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
    grid.appendChild(card);
    cardMap[node.id] = card;
  });
  wrapper.appendChild(grid);
  container.appendChild(wrapper);
  const edges = viewModel.edges || [];
  if (edges.length) requestAnimationFrame(() => _drawGridEdges(grid, edges, cardMap));
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

  renderGridGraph(container, viewModel, onNodeClick);
}
