import { state } from './state.js';
import { els } from './dom.js';
import { featureCard } from './ui-list.js';
import { featureVerdict } from './ui-integration.js';

// 算一組功能的 high/medium/整合(backed) 數，給收合統計用。
function computeStats(features) {
  let high = 0, med = 0, backed = 0;
  for (const f of features) {
    if (f.confidence === 'high') high++;
    else if (f.confidence === 'medium') med++;
    if (featureVerdict(state.integration, f.id) === 'backed') backed++;
  }
  return { high, med, backed };
}

function statsEl(features) {
  const wrap = document.createElement('span');
  wrap.className = 'block-stats';
  const { high, med, backed } = computeStats(features);
  if (high) {
    const s = document.createElement('span');
    s.className = 'confidence-badge confidence-badge-high';
    s.textContent = 'high ' + high;
    wrap.appendChild(s);
  }
  if (med) {
    const s = document.createElement('span');
    s.className = 'confidence-badge confidence-badge-medium';
    s.textContent = 'medium ' + med;
    wrap.appendChild(s);
  }
  if (backed) {
    const s = document.createElement('span');
    s.className = 'block-stat-integ';
    s.textContent = '✓ ' + backed;
    wrap.appendChild(s);
  }
  return wrap;
}

function cardsGrid(features, callbacks) {
  const grid = document.createElement('div');
  grid.className = 'block-cards';
  for (const f of features) {
    grid.appendChild(featureCard(f, f.id === state.selectedId, callbacks));
  }
  return grid;
}

// 把區塊的 related_features（id）映射回 state 裡完整的 feature 物件；
// 被篩選掉（不在 visible map）的成員自動略過。
function resolveFeatures(block, featById) {
  return (block.features || [])
    .map(f => featById.get(f.feature_id))
    .filter(Boolean);
}

function renderTopBlock(top, children, featById, callbacks) {
  const own = resolveFeatures(top, featById);
  const childSections = [];
  const childFeatures = [];
  for (const c of children) {
    const cf = resolveFeatures(c, featById);
    if (!cf.length) continue;
    childFeatures.push(...cf);
    const subH = document.createElement('div');
    subH.className = 'block-sub-header';
    subH.textContent = c.label;
    childSections.push(subH, cardsGrid(cf, callbacks));
  }
  const allVisible = [...own, ...childFeatures];
  if (!allVisible.length) return null; // 全被篩掉 → 不顯示此區塊

  const header = document.createElement('div');
  header.className = 'block-header';
  const chev = document.createElement('span');
  chev.className = 'block-chev';
  chev.textContent = '▾';
  const name = document.createElement('span');
  name.className = 'block-name';
  name.textContent = top.label;
  const count = document.createElement('span');
  count.className = 'block-count';
  count.textContent = allVisible.length;
  header.append(chev, name, count);
  if (top.is_new_this_version) {
    const nb = document.createElement('span');
    nb.className = 'block-new';
    nb.textContent = '本版新增';
    header.appendChild(nb);
  }
  header.appendChild(statsEl(allVisible));

  const body = document.createElement('div');
  body.className = 'block-body';
  if (own.length) body.appendChild(cardsGrid(own, callbacks));
  childSections.forEach(el => body.appendChild(el));

  header.addEventListener('click', () => {
    header.classList.toggle('collapsed');
    body.classList.toggle('hidden');
  });

  const wrap = document.createElement('div');
  wrap.className = 'block-group';
  wrap.append(header, body);
  return wrap;
}

export function renderBlockList(callbacks) {
  const list = els.featureList;
  list.textContent = '';
  list.classList.add('blocks-mode');  // 取消外層卡片 grid，讓區塊垂直堆疊
  els.listTitle.textContent = state.mode === 'baseline' ? '舊版功能' : '新版功能';
  els.listSource.textContent = '依區塊分類';

  const blocks = state.blocks?.blocks ?? [];
  const visibleFeatures = state._filteredFeatures ?? state.l1Model?.features ?? [];
  const featById = new Map(visibleFeatures.map(f => [f.id, f]));

  const tops = blocks.filter(b => !b.parent_block_id);
  const childrenOf = pid => blocks.filter(b => b.parent_block_id === pid);

  let rendered = 0;
  for (const top of tops) {
    const el = renderTopBlock(top, childrenOf(top.block_id), featById, callbacks);
    if (el) { list.appendChild(el); rendered++; }
  }
  if (!rendered) {
    const d = document.createElement('div');
    d.className = 'empty-state';
    d.textContent = '無符合篩選的功能。';
    list.appendChild(d);
  }
}
