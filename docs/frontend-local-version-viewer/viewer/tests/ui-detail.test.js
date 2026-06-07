import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  renderDetailPanel,
  renderDiffDetailPanel,
  renderSingleVersionDetailPanel,
  renderDetailPanelL1,
  renderDetailPanelL2,
  renderDetailPanelL3,
  renderDetailPanelDiff,
  renderEmpty,
  renderError,
  renderNoSelection,
  toggleDiffSort,
  applyDiffSort,
  detailSection,
  listDetailSection,
  attributionSection,
} from '../js/ui-detail.js';
import { state } from '../js/state.js';
import { els } from '../js/dom.js';

function resetState() {
  state.updateModel = null;
  state.l1Model = null;
  state.mode = 'baseline';
  state.selectedId = null;
  state.versionA = null;
  state.versionB = null;
  state.diffSortMode = 'risk';
  state.diffGraphViewModel = null;
  state.l2GraphViewModel = null;
  state.layerExplanation = null;
  state.selectedFeatureId = null;
  state.versionDiff = null;
}

beforeEach(() => {
  resetState();
  els.detailContent.className = 'detail-content';
  els.detailContent.textContent = '';
  els.detailSource.textContent = '';
  els.featureList.textContent = '';
  els.summaryText.textContent = '';
  els.btnDiff.disabled = false;
  els.btnBaseline.disabled = false;
  els.btnCurrent.disabled = false;
  const layerExpl = document.getElementById('layer-explanation');
  if (layerExpl) { layerExpl.textContent = ''; layerExpl.style.display = ''; }
});

// ── detailSection ──────────────────────────────────────────────────

describe('detailSection', () => {
  it('returns section.detail-section with h3 and p containing text', () => {
    const s = detailSection('My Title', 'My text');
    expect(s.tagName).toBe('SECTION');
    expect(s.className).toBe('detail-section');
    expect(s.querySelector('h3').textContent).toBe('My Title');
    expect(s.querySelector('p').textContent).toBe('My text');
    expect(s.querySelector('p').className).toBe('');
  });

  it('sets p.className="missing" and textContent="未提供" when text is null', () => {
    const s = detailSection('Title', null);
    const p = s.querySelector('p');
    expect(p.className).toBe('missing');
    expect(p.textContent).toBe('未提供');
  });

  it('sets p.className="missing" when text is undefined', () => {
    const s = detailSection('Title', undefined);
    expect(s.querySelector('p').className).toBe('missing');
  });
});

// ── listDetailSection ──────────────────────────────────────────────

describe('listDetailSection', () => {
  it('returns section with ul.source-list and li per item', () => {
    const s = listDetailSection('Sources', ['a.js', 'b.js']);
    const ul = s.querySelector('ul.source-list');
    expect(ul).not.toBeNull();
    const items = ul.querySelectorAll('li');
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toBe('a.js');
    expect(items[1].textContent).toBe('b.js');
  });

  it('returns p.missing when items is empty', () => {
    const s = listDetailSection('Sources', []);
    expect(s.querySelector('ul')).toBeNull();
    expect(s.querySelector('p.missing')).not.toBeNull();
    expect(s.querySelector('p.missing').textContent).toBe('未提供');
  });

  it('JSON.stringifies non-string items', () => {
    const s = listDetailSection('Items', [{ id: 1 }]);
    const li = s.querySelector('li');
    expect(li.textContent).toBe(JSON.stringify({ id: 1 }));
  });
});

// ── attributionSection ─────────────────────────────────────────────

describe('attributionSection', () => {
  it('returns div.attribution with code element containing source', () => {
    const div = attributionSection('L1Output.features');
    expect(div.className).toBe('attribution');
    expect(div.querySelector('code').textContent).toBe('L1Output.features');
  });

  it('falls back to "unknown" when source is falsy', () => {
    expect(attributionSection(null).querySelector('code').textContent).toBe('unknown');
    expect(attributionSection('').querySelector('code').textContent).toBe('unknown');
  });
});

// ── renderEmpty ────────────────────────────────────────────────────

describe('renderEmpty', () => {
  it('appends .empty-state div to parent without clearing it', () => {
    const parent = document.createElement('div');
    parent.textContent = 'existing';
    renderEmpty(parent, 'No data');
    expect(parent.children).toHaveLength(1);
    expect(parent.textContent).toContain('existing');
    expect(parent.querySelector('.empty-state').textContent).toBe('No data');
  });
});

// ── renderError ────────────────────────────────────────────────────

describe('renderError', () => {
  it('sets summaryText, inserts .error-box, disables mode buttons', () => {
    renderError('Something went wrong');
    expect(els.summaryText.textContent).toBe('資料載入失敗。');
    expect(els.featureList.querySelector('.error-box').textContent).toBe('Something went wrong');
    expect(els.btnDiff.disabled).toBe(true);
    expect(els.btnBaseline.disabled).toBe(true);
    expect(els.btnCurrent.disabled).toBe(true);
  });
});

// ── renderNoSelection ──────────────────────────────────────────────

describe('renderNoSelection', () => {
  it('sets detailSource and detailContent to empty-state', () => {
    renderNoSelection();
    expect(els.detailSource.textContent).toBe('尚未選取');
    expect(els.detailContent.className).toContain('empty-state');
    expect(els.detailContent.textContent).toBe('選取左側項目以查看詳情。');
  });
});

// ── renderDetailPanel ──────────────────────────────────────────────

describe('renderDetailPanel', () => {
  it('calls renderDiffDetailPanel when mode=diff', () => {
    state.mode = 'diff';
    // No detail → renderNoSelection is called, which proves renderDiffDetailPanel ran
    renderDetailPanel();
    expect(els.detailSource.textContent).toBe('尚未選取');
  });

  it('calls renderSingleVersionDetailPanel when mode=baseline', () => {
    state.mode = 'baseline';
    // No feature → renderNoSelection is called
    renderDetailPanel();
    expect(els.detailSource.textContent).toBe('尚未選取');
  });
});

// ── renderDiffDetailPanel ──────────────────────────────────────────

describe('renderDiffDetailPanel', () => {
  it('calls renderNoSelection when no detail for selectedId', () => {
    state.updateModel = { details: {} };
    state.selectedId = 'feat-1';
    renderDiffDetailPanel();
    expect(els.detailSource.textContent).toBe('尚未選取');
  });

  it('renders .before-after structure when detail exists', () => {
    state.selectedId = 'feat-1';
    state.updateModel = {
      details: {
        'feat-1': {
          source: 'UpdateReport',
          before: { label: 'Old Name', description: 'Old desc' },
          after:  { label: 'New Name', description: 'New desc' },
          scope_state: 'in_scope',
          related_vulnerabilities: [],
          affected_relations: [],
        },
      },
    };
    renderDiffDetailPanel();
    expect(els.detailSource.textContent).toBe('UpdateReport');
    expect(els.detailContent.querySelector('.before-after')).not.toBeNull();
    expect(els.detailContent.querySelector('.ba-panel.before')).not.toBeNull();
    expect(els.detailContent.querySelector('.ba-panel.after')).not.toBeNull();
  });

  it('shows "未提供" in before panel when before has no label or description', () => {
    state.selectedId = 'feat-1';
    state.updateModel = {
      details: {
        'feat-1': {
          source: 'S',
          before: {},
          after: {},
          related_vulnerabilities: [],
          affected_relations: [],
        },
      },
    };
    renderDiffDetailPanel();
    const beforeText = els.detailContent.querySelector('.ba-panel.before .ba-text');
    expect(beforeText.textContent).toBe('未提供');
  });

  it('renders related_vulnerabilities and affected_relations sections', () => {
    state.selectedId = 'feat-1';
    state.updateModel = {
      details: {
        'feat-1': {
          source: 'S',
          before: { label: 'A' },
          after: { label: 'B' },
          related_vulnerabilities: ['CVE-001'],
          affected_relations: ['dep-a'],
        },
      },
    };
    renderDiffDetailPanel();
    const lis = els.detailContent.querySelectorAll('ul.source-list li');
    expect(lis.length).toBeGreaterThanOrEqual(2);
  });
});

// ── renderSingleVersionDetailPanel ────────────────────────────────

describe('renderSingleVersionDetailPanel', () => {
  it('calls renderNoSelection when feature not found', () => {
    state.l1Model = { features: [] };
    state.selectedId = 'feat-nonexistent';
    renderSingleVersionDetailPanel();
    expect(els.detailSource.textContent).toBe('尚未選取');
  });

  it('calls renderNoSelection when l1Model is null', () => {
    state.l1Model = null;
    state.selectedId = 'feat-1';
    renderSingleVersionDetailPanel();
    expect(els.detailSource.textContent).toBe('尚未選取');
  });

  it('renders feature sections when feature is found', () => {
    state.selectedId = 'feat-1';
    state.l1Model = {
      features: [{
        id: 'feat-1',
        label: 'My Feature',
        description: 'Desc',
        trigger_description: 'Trigger',
        confidence: 'high',
        confidence_reason: 'Reason',
        source_nodes: ['Node.method'],
        source: 'L1Output',
      }],
    };
    renderSingleVersionDetailPanel();
    expect(els.detailSource.textContent).toBe('L1Output');
    const h3s = [...els.detailContent.querySelectorAll('h3')].map(h => h.textContent);
    expect(h3s).toContain('功能名稱');
    expect(h3s).toContain('描述');
    expect(h3s).toContain('Source nodes');
  });

  it('appends Enter L2 button when callbacks.onEnterL2 is provided', () => {
    state.selectedId = 'feat-1';
    state.l1Model = { features: [{ id: 'feat-1', label: 'F', source: 'src' }] };
    const onEnterL2 = vi.fn();
    renderSingleVersionDetailPanel({ onEnterL2 });
    const btn = els.detailContent.querySelector('button.action-button');
    expect(btn).not.toBeNull();
    expect(btn.textContent).toBe('進入 L2');
    btn.click();
    expect(onEnterL2).toHaveBeenCalledWith('feat-1');
  });

  it('omits Enter L2 button when no callbacks given', () => {
    state.selectedId = 'feat-1';
    state.l1Model = { features: [{ id: 'feat-1', label: 'F', source: 'src' }] };
    renderSingleVersionDetailPanel();
    const enterL2 = [...els.detailContent.querySelectorAll('button.action-button')]
      .find(b => b.textContent === '進入 L2');
    expect(enterL2).toBeUndefined();
  });

  it('omits Enter L2 button when callbacks.onEnterL2 is missing', () => {
    state.selectedId = 'feat-1';
    state.l1Model = { features: [{ id: 'feat-1', label: 'F', source: 'src' }] };
    renderSingleVersionDetailPanel({});
    const enterL2 = [...els.detailContent.querySelectorAll('button.action-button')]
      .find(b => b.textContent === '進入 L2');
    expect(enterL2).toBeUndefined();
  });
});

// ── renderDetailPanel dispatcher with callbacks ──────────────────

describe('renderDetailPanel dispatcher — passes callbacks through', () => {
  it('forwards onEnterL2 to renderSingleVersionDetailPanel (non-diff mode)', () => {
    state.mode = 'baseline';
    state.selectedId = 'feat-1';
    state.l1Model = { features: [{ id: 'feat-1', label: 'F', source: 'src' }] };
    const onEnterL2 = vi.fn();
    renderDetailPanel({ onEnterL2 });
    const btn = els.detailContent.querySelector('button.action-button');
    expect(btn).not.toBeNull();
    btn.click();
    expect(onEnterL2).toHaveBeenCalledWith('feat-1');
  });

  it('ignores callbacks in diff mode (no Enter L2 button in diff view)', () => {
    state.mode = 'diff';
    state.selectedId = 'feat-1';
    state.updateModel = {
      details: {
        'feat-1': {
          source: 'src',
          before: { label: 'b', description: 'bd' },
          after: { label: 'a', description: 'ad' },
        },
      },
    };
    renderDetailPanel({ onEnterL2: vi.fn() });
    const enterL2 = [...els.detailContent.querySelectorAll('button.action-button')]
      .find(b => b.textContent === '進入 L2');
    expect(enterL2).toBeUndefined();
  });
});

// ── renderDetailPanelL1 ────────────────────────────────────────────

describe('renderDetailPanelL1', () => {
  it('sets detailSource and renders label, description, confidence, trigger sections', () => {
    const node = { id: 'feat-1', label: 'F1', description: 'Desc', confidence: 'high', trigger_description: null };
    renderDetailPanelL1(node);
    expect(els.detailSource.textContent).toBe('L1Output.features[feature_id=feat-1]');
    const h3s = [...els.detailContent.querySelectorAll('h3')].map(h => h.textContent);
    expect(h3s).toContain('功能名稱');
    expect(h3s).toContain('描述');
    expect(h3s).toContain('信心等級');
    expect(h3s).toContain('觸發說明');
  });

  it('shows "未提供" for missing trigger_description', () => {
    const node = { id: 'feat-1', label: 'F1' };
    renderDetailPanelL1(node);
    const sections = els.detailContent.querySelectorAll('section');
    const triggerSection = [...sections].find(s => s.querySelector('h3')?.textContent === '觸發說明');
    expect(triggerSection.querySelector('p.missing')).not.toBeNull();
  });

  it('renders "進入 L2" button', () => {
    const node = { id: 'feat-1', label: 'F1' };
    renderDetailPanelL1(node);
    const btn = [...els.detailContent.querySelectorAll('button')].find(b => b.textContent === '進入 L2');
    expect(btn).not.toBeNull();
  });

  it('calls callbacks.onEnterL2 with node.id on button click', () => {
    const onEnterL2 = vi.fn();
    const node = { id: 'feat-42', label: 'F' };
    renderDetailPanelL1(node, { onEnterL2 });
    els.detailContent.querySelector('button.action-button').click();
    expect(onEnterL2).toHaveBeenCalledWith('feat-42');
  });

  it('does not throw when callbacks is empty (no onEnterL2)', () => {
    const node = { id: 'feat-1', label: 'F' };
    renderDetailPanelL1(node, {});
    expect(() => els.detailContent.querySelector('button.action-button').click()).not.toThrow();
  });
});

// ── renderDetailPanelL2 ────────────────────────────────────────────

describe('renderDetailPanelL2', () => {
  it('sets detailSource and renders label, confidence, source_nodes', () => {
    const node = { id: 'mod-1', label: 'Module 1', confidence: 'medium', source_nodes: ['A', 'B'] };
    renderDetailPanelL2(node);
    expect(els.detailSource.textContent).toBe('L2Output.modules[module_id=mod-1]');
    const h3s = [...els.detailContent.querySelectorAll('h3')].map(h => h.textContent);
    expect(h3s).toContain('模組名稱');
    expect(h3s).toContain('信心等級');
    expect(h3s).toContain('Source Nodes');
  });

  it('renders anomaly section when l2GraphViewModel.anomalies is non-empty', () => {
    state.l2GraphViewModel = {
      anomalies: [{ anomaly_type: 'drift', explanation: 'semantic change' }],
    };
    const node = { id: 'mod-1', label: 'M1', confidence: 'high', source_nodes: [] };
    renderDetailPanelL2(node);
    expect(els.detailContent.querySelector('.anomaly-item')).not.toBeNull();
    expect(els.detailContent.querySelector('.anomaly-item').textContent).toContain('drift');
  });

  it('does not render anomaly section when no anomalies', () => {
    state.l2GraphViewModel = { anomalies: [] };
    const node = { id: 'mod-1', label: 'M1', confidence: 'high', source_nodes: [] };
    renderDetailPanelL2(node);
    expect(els.detailContent.querySelector('.anomaly-item')).toBeNull();
  });

  it('renders "進入 L3" button that calls callbacks.onEnterL3', () => {
    const onEnterL3 = vi.fn();
    const node = { id: 'mod-1', label: 'M', confidence: 'low', source_nodes: [] };
    renderDetailPanelL2(node, { onEnterL3 });
    const btn = [...els.detailContent.querySelectorAll('button')].find(b => b.textContent === '進入 L3');
    btn.click();
    expect(onEnterL3).toHaveBeenCalledWith('mod-1');
  });

  it('renders "展開說明" button', () => {
    const node = { id: 'mod-1', label: 'M', confidence: 'low', source_nodes: [] };
    renderDetailPanelL2(node);
    const btn = [...els.detailContent.querySelectorAll('button')].find(b => b.textContent === '展開說明');
    expect(btn).not.toBeNull();
  });

  it('shows layer-explanation when layerExplanation is set and expandBtn clicked', () => {
    state.layerExplanation = 'Some explanation text';
    const node = { id: 'mod-1', label: 'M', confidence: 'low', source_nodes: [] };
    renderDetailPanelL2(node);
    const expandBtn = [...els.detailContent.querySelectorAll('button')].find(b => b.textContent === '展開說明');
    expandBtn.click();
    const layerExpl = document.getElementById('layer-explanation');
    expect(layerExpl.style.display).toBe('block');
  });

  it('inserts "生成 L2 說明" button when no layerExplanation and calls onGenerateLayerExplanation', () => {
    state.layerExplanation = null;
    state.selectedFeatureId = 'feat-1';
    const onGenerateLayerExplanation = vi.fn();
    const node = { id: 'mod-1', label: 'M', confidence: 'low', source_nodes: [] };
    renderDetailPanelL2(node, { onGenerateLayerExplanation });
    const expandBtn = [...els.detailContent.querySelectorAll('button')].find(b => b.textContent === '展開說明');
    expandBtn.click();
    const layerExpl = document.getElementById('layer-explanation');
    const genBtn = layerExpl.querySelector('button');
    expect(genBtn.textContent).toBe('生成 L2 說明');
    genBtn.click();
    expect(onGenerateLayerExplanation).toHaveBeenCalledWith('feat-1', 'l2');
  });

  it('does not throw when expandBtn clicked with null layer-explanation element', () => {
    state.layerExplanation = null;
    const layerExpl = document.getElementById('layer-explanation');
    layerExpl.id = 'layer-explanation-disabled';
    const node = { id: 'mod-1', label: 'M', confidence: 'low', source_nodes: [] };
    renderDetailPanelL2(node);
    const expandBtn = [...els.detailContent.querySelectorAll('button')].find(b => b.textContent === '展開說明');
    expect(() => expandBtn.click()).not.toThrow();
    layerExpl.id = 'layer-explanation';
  });

  it('does not throw when layerExplanation is set but element missing', () => {
    state.layerExplanation = 'exists';
    const layerExpl = document.getElementById('layer-explanation');
    layerExpl.id = 'layer-explanation-disabled';
    const node = { id: 'mod-1', label: 'M', confidence: 'low', source_nodes: [] };
    renderDetailPanelL2(node);
    const expandBtn = [...els.detailContent.querySelectorAll('button')].find(b => b.textContent === '展開說明');
    expect(() => expandBtn.click()).not.toThrow();
    layerExpl.id = 'layer-explanation';
  });
});

// ── renderDetailPanelL3 ────────────────────────────────────────────

describe('renderDetailPanelL3', () => {
  it('sets detailSource and renders label, type, file sections', () => {
    const node = { id: 'node-1', label: 'MyClass', type: 'class', file: 'src/my.py' };
    renderDetailPanelL3(node);
    expect(els.detailSource.textContent).toBe('StructureJSON.nodes[node_id=node-1]');
    const h3s = [...els.detailContent.querySelectorAll('h3')].map(h => h.textContent);
    expect(h3s).toContain('名稱');
    expect(h3s).toContain('類型');
    expect(h3s).toContain('檔案');
  });
});

// ── renderDetailPanelDiff ──────────────────────────────────────────

describe('renderDetailPanelDiff', () => {
  it('sets detailSource and renders change_type, current_label, baseline_label, risk_flags', () => {
    const node = {
      id: 'feat-1',
      change_type: 'added',
      current_label: 'New Feature',
      baseline_label: null,
      risk_flags: ['vulnerability'],
    };
    renderDetailPanelDiff(node);
    expect(els.detailSource.textContent).toBe('UpdateReport.l1_changes[feature_id=feat-1]');
    const h3s = [...els.detailContent.querySelectorAll('h3')].map(h => h.textContent);
    expect(h3s).toContain('變更類型');
    expect(h3s).toContain('現在名稱');
    expect(h3s).toContain('原始名稱');
    expect(h3s).toContain('風險標記');
    const li = els.detailContent.querySelector('ul.source-list li');
    expect(li.textContent).toBe('vulnerability');
  });
});

// ── toggleDiffSort ─────────────────────────────────────────────────

describe('toggleDiffSort', () => {
  it('sets state.diffSortMode', () => {
    toggleDiffSort('semantic', () => {});
    expect(state.diffSortMode).toBe('semantic');
  });

  it('does not call renderFeatureList when no diffGraphViewModel', () => {
    state.diffGraphViewModel = null;
    const renderFn = vi.fn();
    toggleDiffSort('risk', renderFn);
    expect(renderFn).not.toHaveBeenCalled();
  });

  it('calls renderFeatureList with sorted viewModel when diffGraphViewModel exists', () => {
    const nodes = [
      { id: 'a', change_type: 'removed', risk_flags: [] },
      { id: 'b', change_type: 'added',   risk_flags: [] },
    ];
    state.diffGraphViewModel = { nodes, edges: [] };
    const renderFn = vi.fn();
    toggleDiffSort('risk', renderFn);
    expect(renderFn).toHaveBeenCalledOnce();
    const [calledVm, calledMode] = renderFn.mock.calls[0];
    expect(calledMode).toBe('DIFF');
    expect(calledVm.nodes).toHaveLength(2);
    // 'added' (priority 3) should come before 'removed' (priority 6) in risk sort
    expect(calledVm.nodes[0].id).toBe('b');
  });
});

// ── applyDiffSort ──────────────────────────────────────────────────

describe('applyDiffSort — risk sort', () => {
  it('does not mutate the original array', () => {
    const nodes = [
      { id: 'a', change_type: 'removed', risk_flags: [] },
      { id: 'b', change_type: 'added',   risk_flags: [] },
    ];
    const original = [...nodes];
    applyDiffSort(nodes, 'risk');
    expect(nodes[0].id).toBe(original[0].id);
    expect(nodes[1].id).toBe(original[1].id);
  });

  it('sorts by RISK_PRIORITY ascending (lower = more important)', () => {
    const nodes = [
      { id: 'no-risk',  change_type: 'added',   risk_flags: [] },
      { id: 'vuln',     change_type: 'added',   risk_flags: ['vulnerability'] },
      { id: 'oos',      change_type: 'added',   risk_flags: ['out_of_scope'] },
    ];
    const sorted = applyDiffSort(nodes, 'risk');
    expect(sorted[0].id).toBe('oos');      // priority 0
    expect(sorted[1].id).toBe('vuln');     // priority 1
    expect(sorted[2].id).toBe('no-risk');  // priority 3
  });

  it('falls back to CHANGE_PRIORITY when risk is equal', () => {
    const nodes = [
      { id: 'removed',    change_type: 'removed',    risk_flags: [] },
      { id: 'added',      change_type: 'added',      risk_flags: [] },
      { id: 'attr',       change_type: 'attribute_changed', risk_flags: [] },
      { id: 'dep',        change_type: 'dependency_changed', risk_flags: [] },
    ];
    const sorted = applyDiffSort(nodes, 'risk');
    expect(sorted[0].id).toBe('added');
    expect(sorted[1].id).toBe('attr');
    expect(sorted[2].id).toBe('dep');
    expect(sorted[3].id).toBe('removed');
  });

  it('handles unknown risk flags (priority 99, capped at 3)', () => {
    const nodes = [
      { id: 'unknown-risk', change_type: 'added', risk_flags: ['future_flag'] },
      { id: 'vuln',         change_type: 'added', risk_flags: ['vulnerability'] },
    ];
    const sorted = applyDiffSort(nodes, 'risk');
    expect(sorted[0].id).toBe('vuln');
  });

  it('handles unknown change_type (priority 7)', () => {
    const nodes = [
      { id: 'unknown', change_type: 'unknown_type', risk_flags: [] },
      { id: 'removed', change_type: 'removed',      risk_flags: [] },
    ];
    const sorted = applyDiffSort(nodes, 'risk');
    expect(sorted[0].id).toBe('removed');  // priority 6 < 7
  });
});

describe('applyDiffSort — semantic sort', () => {
  it('sorts by semantic magnitude descending (most changed first)', () => {
    const nodes = [
      { id: 'small', current_label: 'abc', baseline_label: 'abc', current_description: '', baseline_description: '' },
      { id: 'large', current_label: 'xyz', baseline_label: 'aaa', current_description: 'new long desc', baseline_description: '' },
    ];
    const sorted = applyDiffSort(nodes, 'semantic');
    expect(sorted[0].id).toBe('large');
    expect(sorted[1].id).toBe('small');
  });

  it('handles nodes with missing label/description fields', () => {
    const nodes = [
      { id: 'a', current_label: 'hello' },
      { id: 'b' },
    ];
    expect(() => applyDiffSort(nodes, 'semantic')).not.toThrow();
    const sorted = applyDiffSort(nodes, 'semantic');
    expect(sorted[0].id).toBe('a'); // 'hello' vs '' has non-zero magnitude
  });

  it('does not mutate original array in semantic mode', () => {
    const nodes = [
      { id: 'a', current_label: 'xyz', baseline_label: '' },
      { id: 'b', current_label: 'abc', baseline_label: 'abc' },
    ];
    applyDiffSort(nodes, 'semantic');
    expect(nodes[0].id).toBe('a');
  });

  it('handles node where a is longer than b in levenshtein calc', () => {
    // covers a.length > b.length branch in _levenshteinApprox
    const nodes = [
      { id: 'long',  current_label: 'hello world', baseline_label: 'hi' },
      { id: 'short', current_label: 'x',           baseline_label: 'x' },
    ];
    const sorted = applyDiffSort(nodes, 'semantic');
    expect(sorted[0].id).toBe('long');
  });
});

// ── Branch coverage: ?? and || fallbacks ──────────────────────────

describe('renderDiffDetailPanel — ?? fallbacks', () => {
  it('uses ?? [] for null related_vulnerabilities and affected_relations', () => {
    state.selectedId = 'feat-1';
    state.updateModel = {
      details: {
        'feat-1': {
          source: 'S',
          before: { label: 'A' },
          after:  { label: 'B' },
          related_vulnerabilities: null,
          affected_relations: null,
        },
      },
    };
    expect(() => renderDiffDetailPanel()).not.toThrow();
    // both sections should render as "未提供" (empty list)
    const missingPs = els.detailContent.querySelectorAll('p.missing');
    expect(missingPs.length).toBeGreaterThanOrEqual(2);
  });
});

describe('renderSingleVersionDetailPanel — ?? fallback', () => {
  it('uses ?? [] when source_nodes is null', () => {
    state.selectedId = 'feat-1';
    state.l1Model = {
      features: [{ id: 'feat-1', label: 'F', source_nodes: null, source: 'S' }],
    };
    expect(() => renderSingleVersionDetailPanel()).not.toThrow();
    const p = [...els.detailContent.querySelectorAll('p')].find(p => p.textContent === '未提供' && p.classList.contains('missing'));
    expect(p).not.toBeNull();
  });
});

describe('renderDetailPanelL2 — || [] fallbacks', () => {
  it('uses || [] when node.source_nodes is null', () => {
    const node = { id: 'mod-1', label: 'M', confidence: 'low', source_nodes: null };
    expect(() => renderDetailPanelL2(node)).not.toThrow();
  });

  it('uses || [] when l2GraphViewModel is null (anomalies)', () => {
    state.l2GraphViewModel = null;
    const node = { id: 'mod-1', label: 'M', confidence: 'low', source_nodes: [] };
    renderDetailPanelL2(node);
    expect(els.detailContent.querySelector('.anomaly-item')).toBeNull();
  });
});

describe('renderDetailPanelDiff — || [] fallback', () => {
  it('uses || [] when risk_flags is null', () => {
    const node = { id: 'feat-1', change_type: 'added', current_label: 'A', baseline_label: null, risk_flags: null };
    expect(() => renderDetailPanelDiff(node)).not.toThrow();
  });
});

describe('applyDiffSort — ?? and || fallback coverage', () => {
  it('handles nodes with no risk_flags field in risk sort', () => {
    const nodes = [
      { id: 'a', change_type: 'added' },
      { id: 'b', change_type: 'removed' },
    ];
    expect(() => applyDiffSort(nodes, 'risk')).not.toThrow();
    const sorted = applyDiffSort(nodes, 'risk');
    expect(sorted[0].id).toBe('a');
  });

  it('covers second ?? 7 when b.change_type is unknown and a is known', () => {
    // a.change_type known (3), b.change_type unknown (7): 3 - 7 = -4, a first
    const nodes = [
      { id: 'a', change_type: 'added',        risk_flags: [] },
      { id: 'b', change_type: 'future_change', risk_flags: [] },
    ];
    const sorted = applyDiffSort(nodes, 'risk');
    expect(sorted[0].id).toBe('a');
  });
});

describe('toggleDiffSort — default renderFeatureList', () => {
  it('does not throw when called without renderFeatureList callback', () => {
    state.diffGraphViewModel = null;
    expect(() => toggleDiffSort('risk')).not.toThrow();
  });

  it('calls default no-op when diffGraphViewModel exists and no callback given', () => {
    state.diffGraphViewModel = { nodes: [{ id: 'a', change_type: 'added', risk_flags: [] }], edges: [] };
    expect(() => toggleDiffSort('risk')).not.toThrow();
    expect(state.diffSortMode).toBe('risk');
  });
});

describe('applyDiffSort — ?? 99 on a side with known flag', () => {
  it('covers RISK_PRIORITY[f] ?? 99 on a-side when a has known flag and b has unknown', () => {
    // sort([vuln, unknown]) — comparator: a=vuln (known, ?? doesn't fire), b=unknown (?? fires)
    const nodes = [
      { id: 'vuln',    change_type: 'added', risk_flags: ['vulnerability'] },
      { id: 'unknown', change_type: 'added', risk_flags: ['future_flag'] },
    ];
    const sorted = applyDiffSort(nodes, 'risk');
    expect(sorted[0].id).toBe('vuln'); // priority 1 < 3
  });
});

describe('renderStructuralDiffDetail (via renderDiffDetailPanel)', () => {
  it('shows version A and version B descriptions side by side', () => {
    state.mode = 'diff';
    state.updateModel = null;
    state.selectedId = 'feat-1';
    state.versionDiff = {
      node_states: { 'feat-1': 'attribute_changed' },
      node_details: {
        'feat-1': {
          baseline_label: '舊名',
          baseline_description: '舊版描述內容',
          current_label: '新名',
          current_description: '新版描述內容',
        },
      },
    };
    renderDiffDetailPanel();
    const text = els.detailContent.textContent;
    expect(text).toContain('舊版描述內容');
    expect(text).toContain('新版描述內容');
    expect(els.detailContent.querySelectorAll('.before-after').length).toBe(1);
  });

  it('drops the tautological 變更摘要 block', () => {
    state.mode = 'diff';
    state.updateModel = null;
    state.selectedId = 'feat-1';
    state.versionDiff = {
      node_states: { 'feat-1': 'attribute_changed' },
      node_details: {
        'feat-1': {
          baseline_label: '舊名',
          baseline_description: '舊述',
          current_label: '新名',
          current_description: '新述',
        },
      },
    };
    renderDiffDetailPanel();
    expect(els.detailContent.textContent).not.toContain('變更摘要');
    expect(els.detailContent.textContent).not.toContain('新舊版本之間');
  });

  it('shows an absence message for an added feature (no version A)', () => {
    state.mode = 'diff';
    state.updateModel = null;
    state.selectedId = 'feat-new';
    state.versionDiff = {
      node_states: { 'feat-new': 'added' },
      node_details: {
        'feat-new': {
          baseline_label: null,
          baseline_description: null,
          current_label: '全新功能',
          current_description: '只在新版存在',
        },
      },
    };
    renderDiffDetailPanel();
    expect(els.detailContent.textContent).toContain('版本A尚無此功能');
    expect(els.detailContent.textContent).toContain('只在新版存在');
  });

  it('shows an absence message for a removed feature (no version B)', () => {
    state.mode = 'diff';
    state.updateModel = null;
    state.selectedId = 'feat-gone';
    state.versionDiff = {
      node_states: { 'feat-gone': 'removed' },
      node_details: {
        'feat-gone': {
          baseline_label: '舊功能',
          baseline_description: '只在舊版存在',
          current_label: null,
          current_description: null,
        },
      },
    };
    renderDiffDetailPanel();
    expect(els.detailContent.textContent).toContain('此功能已於版本B移除');
    expect(els.detailContent.textContent).toContain('只在舊版存在');
  });

  it('shows 未提供 for an attribute_changed feature with an empty version A description', () => {
    state.mode = 'diff';
    state.updateModel = null;
    state.selectedId = 'feat-1';
    state.versionDiff = {
      node_states: { 'feat-1': 'attribute_changed' },
      node_details: {
        'feat-1': {
          baseline_label: '名稱',
          baseline_description: '',
          current_label: '名稱',
          current_description: '有內容的新描述',
        },
      },
    };
    renderDiffDetailPanel();
    const text = els.detailContent.textContent;
    expect(text).toContain('未提供');
    expect(text).not.toContain('版本A尚無此功能');
    expect(text).toContain('有內容的新描述');
  });
});

// ── shouldShowWarningBanner ────────────────────────────────────────

import { shouldShowWarningBanner } from '../js/ui-detail.js';

describe('shouldShowWarningBanner', () => {
  it('true only when added + low confidence', () => {
    expect(shouldShowWarningBanner({ change_type: 'added', confidence: 'low' })).toBe(true);
    expect(shouldShowWarningBanner({ change_type: 'added', confidence: 'high' })).toBe(false);
    expect(shouldShowWarningBanner({ change_type: 'attribute_changed', confidence: 'low' })).toBe(false);
    expect(shouldShowWarningBanner(null)).toBe(false);
  });
});

// ── S3.3 regression: user-notes + diff-explanation wiring ─────────

describe('ui-detail regression — user notes + diff explanation sections', () => {
  it('renders .user-notes-section when renderDetailPanelDiff is called', () => {
    const node = {
      id: 'feat-x',
      change_type: 'attribute_changed',
      current_label: 'X',
      baseline_label: 'X-old',
      risk_flags: [],
    };
    renderDetailPanelDiff(node);
    expect(document.getElementById('notes-tab-pane').querySelector('.user-notes-section')).not.toBeNull();
  });

  it('renders .diff-explanation-section when renderDetailPanelDiff is called', () => {
    const node = {
      id: 'feat-x',
      change_type: 'attribute_changed',
      current_label: 'X',
      baseline_label: 'X-old',
      risk_flags: [],
    };
    renderDetailPanelDiff(node);
    expect(els.detailContent.querySelector('.diff-explanation-section')).not.toBeNull();
  });

  it('renders .user-notes-section when renderSingleVersionDetailPanel finds a feature (baseline mode)', () => {
    state.mode = 'baseline';
    state.selectedId = 'feat-x';
    state.l1Model = {
      features: [{ id: 'feat-x', label: 'X', description: 'd', source: 'L1Output' }],
    };
    renderSingleVersionDetailPanel();
    expect(document.getElementById('notes-tab-pane').querySelector('.user-notes-section')).not.toBeNull();
  });

  it('renders BOTH .user-notes-section AND .diff-explanation-section when renderDiffDetailPanel runs', () => {
    state.mode = 'diff';
    state.selectedId = 'feat-x';
    state.updateModel = {
      details: {
        'feat-x': {
          source: 'UpdateReport',
          before: { label: 'A' },
          after:  { label: 'B' },
          related_vulnerabilities: [],
          affected_relations: [],
        },
      },
    };
    renderDiffDetailPanel();
    expect(document.getElementById('notes-tab-pane').querySelector('.user-notes-section')).not.toBeNull();
    expect(els.detailContent.querySelector('.diff-explanation-section')).not.toBeNull();
  });
});

describe('renderDetailPanel diff-mode width modifier', () => {
  it('adds workspace--diff class when mode is diff', () => {
    state.mode = 'diff';
    state.updateModel = { details: {} };
    state.selectedId = null;
    renderDetailPanel();
    const ws = els.detailContent.closest('.workspace');
    expect(ws).not.toBeNull();
    expect(ws.classList.contains('workspace--diff')).toBe(true);
  });

  it('removes workspace--diff class when mode is single-version', () => {
    state.mode = 'diff';
    state.updateModel = { details: {} };
    state.selectedId = null;
    renderDetailPanel();
    state.mode = 'baseline';
    state.l1Model = { features: [] };
    renderDetailPanel();
    const ws = els.detailContent.closest('.workspace');
    expect(ws.classList.contains('workspace--diff')).toBe(false);
  });
});
