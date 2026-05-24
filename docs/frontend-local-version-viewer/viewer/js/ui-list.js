import { state } from './state.js';
import { els } from './dom.js';

const CONF_PRIORITY = { low: 0, medium: 1, high: 2 };
const TYPE_PRIORITY = { removed: 0, attribute_changed: 1, dependency_changed: 1, added: 2, null: 9 };

export function applyCardFilters(features, { conf, type } = {}) {
  return features.filter(f => {
    if (conf === 'high'     && f.confidence !== 'high') return false;
    if (conf === 'medium'   && f.confidence !== 'medium') return false;
    if (conf === 'low'      && f.confidence !== 'low') return false;
    if (conf === 'not-high' && f.confidence === 'high') return false;
    if (type === 'added'    && f.change_type !== 'added') return false;
    if (type === 'removed'  && f.change_type !== 'removed') return false;
    if (type === 'modified' && !['attribute_changed','dependency_changed'].includes(f.change_type)) return false;
    if (type === 'none'     && f.change_type != null) return false;
    return true;
  });
}

export function sortCards(features, mode) {
  const arr = [...features];
  if (mode === 'risk' || !mode) {
    return arr.sort((a, b) => {
      const ra = (a.anomaly_count > 0 ? 0 : 1) * 10 + (CONF_PRIORITY[a.confidence] ?? 2);
      const rb = (b.anomaly_count > 0 ? 0 : 1) * 10 + (CONF_PRIORITY[b.confidence] ?? 2);
      return ra - rb;
    });
  }
  if (mode === 'alpha')  return arr.sort((a, b) => (a.label ?? '').localeCompare(b.label ?? ''));
  if (mode === 'source') return arr.sort((a, b) => (b.source_nodes?.length ?? 0) - (a.source_nodes?.length ?? 0));
  if (mode === 'type')   return arr.sort((a, b) => (TYPE_PRIORITY[a.change_type] ?? 9) - (TYPE_PRIORITY[b.change_type] ?? 9));
  return arr;
}

export function applyRiskFilter(features, riskOnly) {
  if (!riskOnly) return features;
  return features.filter(f => f.anomaly_count > 0 || f.confidence === 'low');
}

export function changeSymbol(changeType) {
  const map = {
    added:              '+',
    removed:            '-',
    attribute_changed:  '~',
    dependency_changed: '!=',
  };
  return map[changeType] ?? '?';
}

function renderEmpty(parent, message) {
  const div = document.createElement('div');
  div.className = 'empty-state';
  div.textContent = message;
  parent.appendChild(div);
}

export function changeListButton(item, isActive, callbacks) {
  const card = document.createElement('button');
  card.type = 'button';
  card.className = 'feature-card changed' + (isActive ? ' active' : '');
  card.dataset.nodeId = item.id;

  const labelEl = document.createElement('span');
  labelEl.className = 'feature-card-label';
  labelEl.textContent = item.label;

  const descEl = document.createElement('span');
  descEl.className = 'feature-card-desc';
  const detail = state.updateModel?.details?.[item.id];
  const l1Desc = (state.l1Model?.features ?? []).find(f => f.id === item.id)?.description;
  descEl.textContent =
    detail?.after?.description || detail?.before?.description || l1Desc || '';

  const metaEl = document.createElement('div');
  metaEl.className = 'feature-card-meta';
  const badge = document.createElement('span');
  badge.className = 'change-badge change-' + item.change_type;
  badge.textContent = changeSymbol(item.change_type) + ' ' + item.change_type;
  metaEl.appendChild(badge);

  card.append(labelEl, descEl, metaEl);
  card.addEventListener('click', () => callbacks?.onSelectChange?.(item.id));
  return card;
}

export function featureCard(feature, isActive, callbacks) {
  const card = document.createElement('button');
  card.type = 'button';
  const isChanged = feature.change_type != null;
  card.className = 'feature-card' + (isChanged ? ' changed' : '') + (isActive ? ' active' : '');
  card.dataset.nodeId = feature.id;

  const labelEl = document.createElement('span');
  labelEl.className = 'feature-card-label';
  labelEl.textContent = feature.label;

  const descEl = document.createElement('span');
  descEl.className = 'feature-card-desc';
  descEl.textContent = feature.description || '';

  const metaEl = document.createElement('div');
  metaEl.className = 'feature-card-meta';
  if (feature.confidence) {
    const badge = document.createElement('span');
    badge.className = 'confidence-badge confidence-badge-' + feature.confidence.toLowerCase();
    badge.textContent = feature.confidence;
    metaEl.appendChild(badge);
  }

  card.append(labelEl, descEl, metaEl);
  card.addEventListener('click', () => callbacks?.onSelectFeature?.(feature));
  return card;
}

export function renderChangeList(callbacks) {
  const list = els.featureList;
  list.textContent = '';

  if (state.mode === 'diff') {
    if (!state.updateModel?.diff_available && state.versionDiff) {
      els.listTitle.textContent  = '變更清單';
      els.listSource.textContent = '/api/diff';
      const nodeStates = state.versionDiff.node_states || {};
      const changedFeatures = (state.l1Model?.features ?? []).filter(
        f => nodeStates[f.id] && nodeStates[f.id] !== 'unchanged'
      );
      if (!changedFeatures.length) {
        renderEmpty(list, '兩個版本之間無功能差異。');
        return;
      }
      changedFeatures.forEach(feature => {
        const change = {
          id: feature.id,
          label: feature.label,
          change_type: nodeStates[feature.id],
        };
        list.appendChild(changeListButton(change, change.id === state.selectedId, callbacks));
      });
      return;
    }

    const changes = state.updateModel?.changes ?? [];
    els.listTitle.textContent  = '變更清單';
    els.listSource.textContent = 'UpdateReport.l1_changes';

    if (!changes.length) {
      renderEmpty(list, '無變更項目。');
      return;
    }

    changes.forEach((change) => {
      list.appendChild(changeListButton(change, change.id === state.selectedId, callbacks));
    });
    return;
  }

  const features = state._filteredFeatures ?? state.l1Model?.features ?? [];
  els.listTitle.textContent  = state.mode === 'baseline' ? '舊版功能' : '新版功能';
  els.listSource.textContent = 'L1Output.features';

  if (!features.length) {
    renderEmpty(list, state.l1Model ? '無功能資料。' : 'L1 ViewModel 載入中…');
    return;
  }

  features.forEach((feature) => {
    list.appendChild(featureCard(feature, feature.id === state.selectedId, callbacks));
  });
}
