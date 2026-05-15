import { describe, it, expect, beforeEach } from 'vitest';
import { renderTopBar, updateLogoMark } from '../js/ui-topbar.js';
import { state } from '../js/state.js';
import { els } from '../js/dom.js';

function resetState() {
  state.updateModel = null;
  state.l1Model = null;
  state.mode = 'baseline';
  state.layerState = 'L1';
  state.versionA = null;
  state.versionB = null;
  state.versionDiff = null;
  state.snapshots = [];
  state.selectedId = null;
}

beforeEach(() => {
  resetState();
  document.querySelector('.mode-switch').hidden = false;
  const logo = document.getElementById('logo-mark');
  logo.dataset.state = 'l1';
  logo.setAttribute('src', './assets/mark-l1.svg');
  els.btnDiff.disabled = false;
  els.btnDiff.classList.remove('active');
  els.btnBaseline.classList.remove('active');
  els.btnCurrent.classList.remove('active');
  els.countRemoved.removeAttribute('hidden');
  els.countModified.removeAttribute('hidden');
  els.countRisk.setAttribute('hidden', '');
  els.countAdded.textContent = '';
  els.countRemoved.textContent = '';
  els.countModified.textContent = '';
  els.btnBaseline.textContent = '舊版';
  els.btnCurrent.textContent = '新版';
  els.summaryText.textContent = '';
});

// ── renderTopBar — mode-switch visibility ──────────────────────────

describe('renderTopBar — .mode-switch visibility', () => {
  it('hides .mode-switch when no diff and no version compare', () => {
    renderTopBar();
    expect(document.querySelector('.mode-switch').hidden).toBe(true);
  });

  it('shows .mode-switch when hasDiff=true', () => {
    state.updateModel = { diff_available: true, changes: [], change_counts: {}, risk_counts: {} };
    state.mode = 'diff';
    renderTopBar();
    expect(document.querySelector('.mode-switch').hidden).toBe(false);
  });

  it('shows .mode-switch when hasVersionCompare', () => {
    state.versionA = 'v1';
    state.versionB = 'v2';
    renderTopBar();
    expect(document.querySelector('.mode-switch').hidden).toBe(false);
  });

  it('does not throw when .mode-switch is absent', () => {
    const ms = document.querySelector('.mode-switch');
    ms.className = 'mode-switch-disabled';
    expect(() => renderTopBar()).not.toThrow();
    ms.className = 'mode-switch';
  });
});

// ── renderTopBar — summaryText ─────────────────────────────────────

describe('renderTopBar — summaryText', () => {
  it('shows updateModel.summary when hasDiff', () => {
    state.updateModel = {
      diff_available: true,
      summary: '有 3 個功能變更。',
      changes: [],
      change_counts: {},
      risk_counts: {},
    };
    renderTopBar();
    expect(els.summaryText.textContent).toBe('有 3 個功能變更。');
  });

  it('falls back to "（無摘要）" when summary is missing', () => {
    state.updateModel = {
      diff_available: true,
      changes: [],
      change_counts: {},
      risk_counts: {},
    };
    renderTopBar();
    expect(els.summaryText.textContent).toBe('（無摘要）');
  });

  it('shows feature count from l1Model.features.length when no diff', () => {
    state.l1Model = { features: [1, 2, 3] };
    renderTopBar();
    expect(els.summaryText.textContent).toBe('功能總覽：共 3 個功能。');
  });

  it('prefers l1Model.stats.feature_count over features.length', () => {
    state.l1Model = { stats: { feature_count: 7 }, features: [1, 2] };
    renderTopBar();
    expect(els.summaryText.textContent).toBe('功能總覽：共 7 個功能。');
  });

  it('shows loading message when no diff and no l1Model', () => {
    renderTopBar();
    expect(els.summaryText.textContent).toBe('（載入中…）');
  });
});

// ── renderTopBar — count badges ────────────────────────────────────

describe('renderTopBar — count badges (mode=diff, hasDiff)', () => {
  it('shows count badges with values from change_counts', () => {
    state.updateModel = {
      diff_available: true,
      summary: 's',
      changes: [],
      change_counts: { added: 2, removed: 1, attribute_changed: 1, dependency_changed: 0 },
      risk_counts: {},
    };
    state.mode = 'diff';
    renderTopBar();
    expect(els.countAdded.getAttribute('hidden')).toBeNull();
    expect(els.countRemoved.getAttribute('hidden')).toBeNull();
    expect(els.countModified.getAttribute('hidden')).toBeNull();
    expect(els.countAdded.textContent).toBe('新增 2');
    expect(els.countRemoved.textContent).toBe('移除 1');
    expect(els.countModified.textContent).toBe('修改 1');
  });

  it('shows countRisk when risk_counts total > 0', () => {
    state.updateModel = {
      diff_available: true,
      summary: 's',
      changes: [],
      change_counts: {},
      risk_counts: { high: 2 },
    };
    state.mode = 'diff';
    renderTopBar();
    expect(els.countRisk.getAttribute('hidden')).toBeNull();
    expect(els.countRisk.textContent).toBe('注意 2');
  });

  it('hides countRisk when risk_counts total is 0', () => {
    state.updateModel = {
      diff_available: true,
      summary: 's',
      changes: [],
      change_counts: {},
      risk_counts: {},
    };
    state.mode = 'diff';
    renderTopBar();
    expect(els.countRisk.getAttribute('hidden')).not.toBeNull();
  });
});

describe('renderTopBar — count badges (hasVersionCompare, versionDiff)', () => {
  it('reads counts from versionDiff.summary when total_changed > 0', () => {
    state.versionA = 'v1';
    state.versionB = 'v2';
    state.versionDiff = { summary: { total_changed: 3, added: 2, removed: 1 } };
    state.mode = 'diff';
    renderTopBar();
    expect(els.countAdded.textContent).toBe('新增 2');
    expect(els.countRemoved.textContent).toBe('移除 1');
  });

  it('hides count-removed/modified/risk when mode is not diff', () => {
    state.mode = 'baseline';
    renderTopBar();
    expect(els.countRemoved.getAttribute('hidden')).not.toBeNull();
    expect(els.countModified.getAttribute('hidden')).not.toBeNull();
    expect(els.countRisk.getAttribute('hidden')).not.toBeNull();
  });
});

// ── renderTopBar — btn labels ──────────────────────────────────────

describe('renderTopBar — button labels', () => {
  it('sets btnBaseline text from snapshotLabel when snapshot found (label)', () => {
    state.snapshots = [{ version_id: 'v1', label: 'Release 1.0' }];
    state.versionA = 'v1';
    renderTopBar();
    expect(els.btnBaseline.textContent).toBe('Release 1.0');
  });

  it('sets btnBaseline text from snapshotLabel when snapshot found (git_tags)', () => {
    state.snapshots = [{ version_id: 'v1', git_tags: ['v1.2.3'] }];
    state.versionA = 'v1';
    renderTopBar();
    expect(els.btnBaseline.textContent).toBe('v1.2.3');
  });

  it('sets btnBaseline text from snapshotLabel when snapshot found (timestamp)', () => {
    state.snapshots = [{ version_id: 'v1', timestamp: '2026-01-15T10:30:00Z' }];
    state.versionA = 'v1';
    renderTopBar();
    expect(els.btnBaseline.textContent).toBe('2026-01-15 10:30');
  });

  it('falls back to "（無時間）" when snapshot has no identifying field', () => {
    state.snapshots = [{ version_id: 'v1' }];
    state.versionA = 'v1';
    renderTopBar();
    expect(els.btnBaseline.textContent).toBe('（無時間）');
  });

  it('falls back to "版本 A" when no snapshot found for versionA', () => {
    state.versionA = 'nonexistent';
    renderTopBar();
    expect(els.btnBaseline.textContent).toBe('版本 A');
  });

  it('falls back to "版本 B" when no snapshot found for versionB', () => {
    state.versionB = 'nonexistent';
    renderTopBar();
    expect(els.btnCurrent.textContent).toBe('版本 B');
  });

  it('disables btnDiff when no diff and no version compare', () => {
    renderTopBar();
    expect(els.btnDiff.disabled).toBe(true);
  });

  it('enables btnDiff when hasDiff', () => {
    state.updateModel = { diff_available: true, changes: [], change_counts: {}, risk_counts: {} };
    renderTopBar();
    expect(els.btnDiff.disabled).toBe(false);
  });

  it('sets btnCurrent text from snapshotLabel when snapB found', () => {
    state.snapshots = [{ version_id: 'v2', label: 'Release 2.0' }];
    state.versionB = 'v2';
    renderTopBar();
    expect(els.btnCurrent.textContent).toBe('Release 2.0');
  });
});

describe('renderTopBar — edge cases', () => {
  it('shows "共 0 個功能。" when l1Model has no stats and no features', () => {
    state.l1Model = {};
    renderTopBar();
    expect(els.summaryText.textContent).toBe('功能總覽：共 0 個功能。');
  });

  it('uses change_counts when versionDiff.summary.total_changed is 0', () => {
    state.versionA = 'v1';
    state.versionB = 'v2';
    state.versionDiff = { summary: { total_changed: 0 } };
    state.updateModel = {
      diff_available: false,
      change_counts: { added: 5, removed: 0 },
      risk_counts: {},
    };
    state.mode = 'diff';
    renderTopBar();
    expect(els.countAdded.textContent).toBe('新增 5');
  });

  it('falls back to empty object for cc when updateModel is null in diff mode', () => {
    state.versionA = 'v1';
    state.versionB = 'v2';
    state.updateModel = null;
    state.versionDiff = null;
    state.mode = 'diff';
    renderTopBar();
    expect(els.countAdded.textContent).toBe('新增 0');
  });

  it('treats versionDiff.summary with no total_changed as 0', () => {
    state.versionA = 'v1';
    state.versionB = 'v2';
    state.versionDiff = { summary: {} };
    state.updateModel = { diff_available: false, change_counts: { added: 3, removed: 0 }, risk_counts: {} };
    state.mode = 'diff';
    renderTopBar();
    expect(els.countAdded.textContent).toBe('新增 3');
  });
});

// ── updateLogoMark ─────────────────────────────────────────────────

describe('updateLogoMark', () => {
  it('sets mark-diff.svg when mode=diff and hasDiff', () => {
    state.mode = 'diff';
    state.updateModel = { diff_available: true };
    updateLogoMark();
    const logo = document.getElementById('logo-mark');
    expect(logo.getAttribute('src')).toBe('./assets/mark-diff.svg');
    expect(logo.dataset.state).toBe('diff');
  });

  it('sets mark-diff.svg when mode=diff and versionDiff exists', () => {
    state.mode = 'diff';
    state.versionDiff = { summary: {} };
    updateLogoMark();
    const logo = document.getElementById('logo-mark');
    expect(logo.getAttribute('src')).toBe('./assets/mark-diff.svg');
  });

  it('sets mark-l3.svg when layerState=L3', () => {
    state.layerState = 'L3';
    updateLogoMark();
    expect(document.getElementById('logo-mark').getAttribute('src')).toBe('./assets/mark-l3.svg');
  });

  it('sets mark-l2.svg when layerState=L2', () => {
    state.layerState = 'L2';
    updateLogoMark();
    expect(document.getElementById('logo-mark').getAttribute('src')).toBe('./assets/mark-l2.svg');
  });

  it('sets mark-l1.svg in all other cases', () => {
    state.layerState = 'L1';
    state.mode = 'baseline';
    const logo = document.getElementById('logo-mark');
    logo.dataset.state = 'diff';
    updateLogoMark();
    expect(logo.getAttribute('src')).toBe('./assets/mark-l1.svg');
  });

  it('does not change src when already at target state', () => {
    const logo = document.getElementById('logo-mark');
    logo.dataset.state = 'l1';
    logo.setAttribute('src', 'sentinel-original.svg');
    state.mode = 'baseline';
    state.layerState = 'L1';
    updateLogoMark();
    expect(logo.getAttribute('src')).toBe('sentinel-original.svg');
  });

  it('does not throw when #logo-mark is absent', () => {
    const logo = document.getElementById('logo-mark');
    logo.id = 'logo-mark-disabled';
    expect(() => updateLogoMark()).not.toThrow();
    logo.id = 'logo-mark';
  });
});
