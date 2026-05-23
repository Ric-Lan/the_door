import { state } from './state.js';
import { els } from './dom.js';
import { appendUserNotesSection } from './ui-notes.js';
import { appendDiffExplanationSection } from './ui-diff-explanation.js';
import { appendNextActionsSection } from './ui-next-actions.js';
import { wordDiff } from './diff-util.js';

export function shouldShowWarningBanner(feature) {
  return feature?.change_type === 'added' && feature?.confidence === 'low';
}

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function renderBeforeAfter(before, after) {
  if (!before && !after) return '';
  const segments = wordDiff(before ?? '', after ?? '');
  const beforeHtml = segments
    .filter(s => s.type !== 'add')
    .map(s => s.type === 'remove' ? `<mark class="diff-mark diff-mark-remove">${escapeHtml(s.text)}</mark>` : escapeHtml(s.text))
    .join('');
  const afterHtml = segments
    .filter(s => s.type !== 'remove')
    .map(s => s.type === 'add' ? `<mark class="diff-mark diff-mark-add">${escapeHtml(s.text)}</mark>` : escapeHtml(s.text))
    .join('');
  return `<div class="diff-before-after">
    <div class="diff-panel diff-panel-before"><strong>修改前</strong><br>${beforeHtml}</div>
    <div class="diff-panel diff-panel-after"><strong>修改後</strong><br>${afterHtml}</div>
  </div>`;
}

export function renderEmpty(parent, message) {
  const div = document.createElement('div');
  div.className = 'empty-state';
  div.textContent = message;
  parent.appendChild(div);
}

export function renderError(message) {
  els.summaryText.textContent = '資料載入失敗。';
  els.featureList.textContent = '';
  const box = document.createElement('div');
  box.className = 'error-box';
  box.textContent = message;
  els.featureList.appendChild(box);
  els.btnDiff.disabled     = true;
  els.btnBaseline.disabled = true;
  els.btnCurrent.disabled  = true;
}

export function renderNoSelection() {
  els.detailSource.textContent = '尚未選取';
  els.detailContent.className  = 'detail-content empty-state';
  els.detailContent.textContent = '選取左側項目以查看詳情。';
}

export function detailSection(title, text) {
  const wrap = document.createElement('section');
  wrap.className = 'detail-section';
  const h = document.createElement('h3');
  h.textContent = title;
  const p = document.createElement('p');
  const isMissing = text === null || text === undefined;
  p.textContent = isMissing ? '未提供' : String(text);
  if (isMissing) p.className = 'missing';
  wrap.append(h, p);
  return wrap;
}

export function listDetailSection(title, items) {
  const wrap = document.createElement('section');
  wrap.className = 'detail-section';
  const h = document.createElement('h3');
  h.textContent = title;
  wrap.appendChild(h);
  if (!items.length) {
    const p = document.createElement('p');
    p.className = 'missing';
    p.textContent = '未提供';
    wrap.appendChild(p);
    return wrap;
  }
  const ul = document.createElement('ul');
  ul.className = 'source-list';
  items.forEach(item => {
    const li = document.createElement('li');
    li.textContent = typeof item === 'string' ? item : JSON.stringify(item);
    ul.appendChild(li);
  });
  wrap.appendChild(ul);
  return wrap;
}

export function attributionSection(source) {
  const div = document.createElement('div');
  div.className = 'attribution';
  div.textContent = '資料來源：';
  const code = document.createElement('code');
  code.textContent = source || 'unknown';
  div.appendChild(code);
  return div;
}

export function renderDetailPanel(callbacks = {}) {
  if (state.mode === 'diff') {
    renderDiffDetailPanel();
  } else {
    renderSingleVersionDetailPanel(callbacks);
  }
}

const CHANGE_TYPE_LABEL = {
  added:              '新增',
  removed:            '移除',
  attribute_changed:  '屬性變更',
  dependency_changed: '相依變更',
};

function _versionDescPanel(side, versionLabel, description, absentText) {
  const panel = document.createElement('div');
  panel.className = 'ba-panel ' + side;
  const labelEl = document.createElement('div');
  labelEl.className = 'ba-label';
  labelEl.textContent = versionLabel;
  const textEl = document.createElement('div');
  textEl.className = 'ba-text';
  if (description) {
    textEl.textContent = description;
  } else {
    textEl.textContent = absentText;
    textEl.classList.add('missing');
  }
  panel.append(labelEl, textEl);
  return panel;
}

function renderStructuralDiffDetail() {
  const id = state.selectedId;
  const changeType = state.versionDiff?.node_states?.[id];
  if (!id || !changeType) {
    renderNoSelection();
    return;
  }
  const detail = state.versionDiff?.node_details?.[id] ?? {};
  els.detailSource.textContent = '/api/diff';
  const content = els.detailContent;
  content.className = 'detail-content';
  content.textContent = '';

  const chip = document.createElement('div');
  chip.className = 'change-badge change-' + changeType;
  chip.textContent = CHANGE_TYPE_LABEL[changeType] ?? changeType;
  content.appendChild(chip);

  content.appendChild(detailSection('功能名稱',
    detail.current_label ?? detail.baseline_label ?? id));

  const baWrap = document.createElement('div');
  baWrap.className = 'before-after';
  baWrap.appendChild(_versionDescPanel(
    'before', '版本A', detail.baseline_description,
    changeType === 'added' ? '版本A尚無此功能' : '未提供'));
  baWrap.appendChild(_versionDescPanel(
    'after', '版本B', detail.current_description,
    changeType === 'removed' ? '此功能已於版本B移除' : '未提供'));
  content.appendChild(baWrap);

  content.appendChild(attributionSection('/api/diff'));
  appendDiffExplanationSection(content, id);
  appendUserNotesSection(content, 'diff', state.versionA, state.versionB, id);
}

export function renderDiffDetailPanel() {
  const detail = state.updateModel?.details?.[state.selectedId];
  if (!detail) {
    if (state.versionDiff && state.selectedId) {
      renderStructuralDiffDetail();
      return;
    }
    renderNoSelection();
    return;
  }
  els.detailSource.textContent = detail.source;
  const content = els.detailContent;
  content.className = 'detail-content';
  content.textContent = '';

  const baWrap = document.createElement('div');
  baWrap.className = 'before-after';

  const baBefore = document.createElement('div');
  baBefore.className = 'ba-panel before';
  const baBeforeLabel = document.createElement('div');
  baBeforeLabel.className = 'ba-label';
  baBeforeLabel.textContent = 'Before';
  const baBeforeText = document.createElement('div');
  baBeforeText.className = 'ba-text';
  baBeforeText.textContent =
    [detail.before.label, detail.before.description].filter(Boolean).join(' — ') || '未提供';
  baBefore.append(baBeforeLabel, baBeforeText);

  const baAfter = document.createElement('div');
  baAfter.className = 'ba-panel after';
  const baAfterLabel = document.createElement('div');
  baAfterLabel.className = 'ba-label';
  baAfterLabel.textContent = 'After';
  const baAfterText = document.createElement('div');
  baAfterText.className = 'ba-text';
  baAfterText.textContent =
    [detail.after.label, detail.after.description].filter(Boolean).join(' — ') || '未提供';
  baAfter.append(baAfterLabel, baAfterText);

  baWrap.append(baBefore, baAfter);
  content.appendChild(baWrap);

  content.appendChild(detailSection('範圍狀態', detail.scope_state));
  content.appendChild(listDetailSection('相關漏洞',   detail.related_vulnerabilities ?? []));
  content.appendChild(listDetailSection('受影響關係', detail.affected_relations     ?? []));
  content.appendChild(attributionSection(detail.source));
  appendDiffExplanationSection(content, state.selectedId);
  appendUserNotesSection(content, 'diff', state.versionA, state.versionB, state.selectedId);
  appendNextActionsSection(content, detail);
}

export function renderSingleVersionDetailPanel(callbacks = {}) {
  const features = state.l1Model?.features ?? [];
  const feature = features.find(f => f.id === state.selectedId);
  if (!feature) {
    renderNoSelection();
    return;
  }
  els.detailSource.textContent = feature.source;
  const content = els.detailContent;
  content.className = 'detail-content';
  content.textContent = '';
  content.appendChild(detailSection('功能名稱',   feature.label));
  content.appendChild(detailSection('描述',       feature.description));
  content.appendChild(detailSection('觸發方式',   feature.trigger_description));
  content.appendChild(detailSection('信心等級',   feature.confidence));
  content.appendChild(detailSection('信心理由',   feature.confidence_reason));
  content.appendChild(listDetailSection('Source nodes', feature.source_nodes ?? []));
  if (callbacks.onEnterL2) {
    const enterL2Btn = document.createElement('button');
    enterL2Btn.type = 'button';
    enterL2Btn.className = 'action-button';
    enterL2Btn.textContent = '進入 L2';
    enterL2Btn.addEventListener('click', () => callbacks.onEnterL2(feature.id));
    content.appendChild(enterL2Btn);
  }
  content.appendChild(attributionSection(feature.source));
  appendUserNotesSection(content, state.mode, state.versionA, state.versionB, feature.id);
  appendNextActionsSection(content, feature);
}

export function renderDetailPanelL1(node, callbacks = {}) {
  els.detailSource.textContent = 'L1Output.features[feature_id=' + node.id + ']';
  const content = els.detailContent;
  content.className = 'detail-content';
  content.textContent = '';
  content.appendChild(detailSection('功能名稱', node.label));
  content.appendChild(detailSection('描述',     node.description));
  content.appendChild(detailSection('信心等級', node.confidence));
  content.appendChild(detailSection('觸發說明', node.trigger_description));
  const enterL2Btn = document.createElement('button');
  enterL2Btn.type = 'button';
  enterL2Btn.className = 'action-button';
  enterL2Btn.textContent = '進入 L2';
  enterL2Btn.addEventListener('click', () => callbacks.onEnterL2?.(node.id));
  content.appendChild(enterL2Btn);
  content.appendChild(attributionSection('L1Output.features[feature_id=' + node.id + ']'));
}

export function renderDetailPanelL2(node, callbacks = {}) {
  els.detailSource.textContent = 'L2Output.modules[module_id=' + node.id + ']';
  const content = els.detailContent;
  content.className = 'detail-content';
  content.textContent = '';
  content.appendChild(detailSection('模組名稱', node.label));
  content.appendChild(detailSection('信心等級', node.confidence));
  content.appendChild(listDetailSection('Source Nodes', node.source_nodes || []));

  const anomalies = state.l2GraphViewModel?.anomalies || [];
  if (anomalies.length > 0) {
    const anomalySection = document.createElement('section');
    anomalySection.className = 'detail-section';
    const h = document.createElement('h3');
    h.textContent = '異常';
    anomalySection.appendChild(h);
    anomalies.forEach(a => {
      const item = document.createElement('div');
      item.className = 'anomaly-item';
      item.textContent = a.anomaly_type + '：' + a.explanation;
      anomalySection.appendChild(item);
    });
    content.appendChild(anomalySection);
  }

  const enterL3Btn = document.createElement('button');
  enterL3Btn.type = 'button';
  enterL3Btn.className = 'action-button';
  enterL3Btn.textContent = '進入 L3';
  enterL3Btn.addEventListener('click', () => callbacks.onEnterL3?.(node.id));
  content.appendChild(enterL3Btn);

  const expandBtn = document.createElement('button');
  expandBtn.type = 'button';
  expandBtn.className = 'action-button';
  expandBtn.textContent = '展開說明';
  expandBtn.addEventListener('click', () => {
    const layerExplanationEl = document.getElementById('layer-explanation');
    if (state.layerExplanation) {
      if (layerExplanationEl) layerExplanationEl.style.display = 'block';
    } else {
      if (layerExplanationEl) {
        layerExplanationEl.textContent = '';
        const genBtn = document.createElement('button');
        genBtn.type = 'button';
        genBtn.className = 'action-button';
        genBtn.textContent = '生成 L2 說明';
        genBtn.addEventListener('click', () =>
          callbacks.onGenerateLayerExplanation?.(state.selectedFeatureId, 'l2')
        );
        layerExplanationEl.appendChild(genBtn);
      }
    }
  });
  content.appendChild(expandBtn);

  content.appendChild(attributionSection('L2Output.modules[module_id=' + node.id + ']'));
}

export function renderDetailPanelL3(node) {
  els.detailSource.textContent = 'StructureJSON.nodes[node_id=' + node.id + ']';
  const content = els.detailContent;
  content.className = 'detail-content';
  content.textContent = '';
  content.appendChild(detailSection('名稱', node.label));
  content.appendChild(detailSection('類型', node.type));
  content.appendChild(detailSection('檔案', node.file));
  content.appendChild(attributionSection('StructureJSON.nodes[node_id=' + node.id + ']'));
}

export function renderDetailPanelDiff(node) {
  els.detailSource.textContent = 'UpdateReport.l1_changes[feature_id=' + node.id + ']';
  const content = els.detailContent;
  content.className = 'detail-content';
  content.textContent = '';
  content.appendChild(detailSection('變更類型', node.change_type));
  content.appendChild(detailSection('現在名稱', node.current_label));
  content.appendChild(detailSection('原始名稱', node.baseline_label));
  content.appendChild(listDetailSection('風險標記', node.risk_flags || []));
  content.appendChild(attributionSection('UpdateReport.l1_changes[feature_id=' + node.id + ']'));
  appendDiffExplanationSection(content, node.id);
  appendUserNotesSection(content, 'diff', state.versionA, state.versionB, node.id);
  appendNextActionsSection(content, node);
}

export function toggleDiffSort(mode, renderFeatureList = () => {}) {
  state.diffSortMode = mode;
  if (state.diffGraphViewModel) {
    const sorted = applyDiffSort(state.diffGraphViewModel.nodes, mode);
    const sortedVm = Object.assign({}, state.diffGraphViewModel, { nodes: sorted });
    renderFeatureList(sortedVm, 'DIFF');
  }
}

function _semanticMagnitude(node) {
  const a1 = node.current_label       || '';
  const b1 = node.baseline_label      || '';
  const a2 = node.current_description  || '';
  const b2 = node.baseline_description || '';
  return _levenshteinApprox(a1, b1) + _levenshteinApprox(a2, b2);
}

function _levenshteinApprox(a, b) {
  if (!a && !b) return 0;
  const maxLen = Math.max(a.length, b.length);
  let common = 0;
  const shorter = a.length <= b.length ? a : b;
  const longer  = a.length <= b.length ? b : a;
  for (let i = 0; i < shorter.length; i++) {
    if (longer.includes(shorter[i])) common++;
  }
  return Math.round(maxLen * (1 - common / maxLen));
}

export function applyDiffSort(nodes, mode) {
  if (mode === 'semantic') {
    return [...nodes].sort((a, b) => _semanticMagnitude(b) - _semanticMagnitude(a));
  }
  const RISK_PRIORITY   = { out_of_scope: 0, vulnerability: 1, semantic_drift: 2 };
  const CHANGE_PRIORITY = { added: 3, attribute_changed: 4, dependency_changed: 5, removed: 6 };
  return [...nodes].sort((a, b) => {
    const riskA = Math.min(...(a.risk_flags || []).map(f => RISK_PRIORITY[f] ?? 99), 3);
    const riskB = Math.min(...(b.risk_flags || []).map(f => RISK_PRIORITY[f] ?? 99), 3);
    if (riskA !== riskB) return riskA - riskB;
    return (CHANGE_PRIORITY[a.change_type] ?? 7) - (CHANGE_PRIORITY[b.change_type] ?? 7);
  });
}
