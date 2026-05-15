import { describe, it, expect, beforeEach, vi } from 'vitest';
import { changeSymbol, changeListButton, featureCard, renderChangeList } from '../js/ui-list.js';
import { state } from '../js/state.js';
import { els } from '../js/dom.js';

function resetState() {
  state.updateModel = null;
  state.l1Model = null;
  state.mode = 'baseline';
  state.versionDiff = null;
  state.selectedId = null;
  state.versionA = null;
  state.versionB = null;
}

beforeEach(() => {
  resetState();
  els.featureList.textContent = '';
  els.listTitle.textContent = '';
  els.listSource.textContent = '';
});

// ── changeSymbol ───────────────────────────────────────────────────

describe('changeSymbol', () => {
  it('returns "+" for added', () => expect(changeSymbol('added')).toBe('+'));
  it('returns "-" for removed', () => expect(changeSymbol('removed')).toBe('-'));
  it('returns "~" for attribute_changed', () => expect(changeSymbol('attribute_changed')).toBe('~'));
  it('returns "!=" for dependency_changed', () => expect(changeSymbol('dependency_changed')).toBe('!='));
  it('returns "?" for unknown type', () => expect(changeSymbol('unknown')).toBe('?'));
});

// ── changeListButton ───────────────────────────────────────────────

describe('changeListButton', () => {
  it('returns a button with class feature-card and changed', () => {
    const item = { id: 'feat-1', label: 'Feature 1', change_type: 'added' };
    const btn = changeListButton(item, false, {});
    expect(btn.tagName).toBe('BUTTON');
    expect(btn.classList.contains('feature-card')).toBe(true);
    expect(btn.classList.contains('changed')).toBe(true);
  });

  it('contains .feature-card-label with item.label', () => {
    const item = { id: 'feat-1', label: 'My Feature', change_type: 'added' };
    const btn = changeListButton(item, false, {});
    expect(btn.querySelector('.feature-card-label').textContent).toBe('My Feature');
  });

  it('contains .change-badge with symbol and change_type', () => {
    const item = { id: 'feat-1', label: 'F1', change_type: 'removed' };
    const btn = changeListButton(item, false, {});
    const badge = btn.querySelector('.change-badge');
    expect(badge).not.toBeNull();
    expect(badge.classList.contains('change-removed')).toBe(true);
    expect(badge.textContent).toBe('- removed');
  });

  it('adds .active class when isActive is true', () => {
    const item = { id: 'feat-1', label: 'F1', change_type: 'added' };
    const btn = changeListButton(item, true, {});
    expect(btn.classList.contains('active')).toBe(true);
  });

  it('does not add .active class when isActive is false', () => {
    const item = { id: 'feat-1', label: 'F1', change_type: 'added' };
    const btn = changeListButton(item, false, {});
    expect(btn.classList.contains('active')).toBe(false);
  });

  it('calls callbacks.onSelect with item.id on click', () => {
    const onSelect = vi.fn();
    const item = { id: 'feat-42', label: 'F', change_type: 'added' };
    const btn = changeListButton(item, false, { onSelect });
    btn.click();
    expect(onSelect).toHaveBeenCalledWith('feat-42');
  });

  it('reads description from updateModel.details (after)', () => {
    state.updateModel = {
      diff_available: true,
      details: { 'feat-1': { after: { description: 'New desc' }, before: null } },
    };
    const item = { id: 'feat-1', label: 'F', change_type: 'added' };
    const btn = changeListButton(item, false, {});
    expect(btn.querySelector('.feature-card-desc').textContent).toBe('New desc');
  });

  it('falls back to before.description when after is missing', () => {
    state.updateModel = {
      diff_available: true,
      details: { 'feat-1': { before: { description: 'Old desc' } } },
    };
    const item = { id: 'feat-1', label: 'F', change_type: 'removed' };
    const btn = changeListButton(item, false, {});
    expect(btn.querySelector('.feature-card-desc').textContent).toBe('Old desc');
  });

  it('does not throw when callbacks is null', () => {
    const item = { id: 'feat-1', label: 'F', change_type: 'added' };
    const btn = changeListButton(item, false, null);
    expect(() => btn.click()).not.toThrow();
  });
});

// ── featureCard ────────────────────────────────────────────────────

describe('featureCard', () => {
  it('returns button with class feature-card but not changed when no change_type', () => {
    const feature = { id: 'feat-1', label: 'F1', description: 'desc' };
    const btn = featureCard(feature, false, {});
    expect(btn.classList.contains('feature-card')).toBe(true);
    expect(btn.classList.contains('changed')).toBe(false);
  });

  it('adds .changed class when change_type is present', () => {
    const feature = { id: 'feat-1', label: 'F1', change_type: 'added' };
    const btn = featureCard(feature, false, {});
    expect(btn.classList.contains('changed')).toBe(true);
  });

  it('adds .active class when isActive is true', () => {
    const feature = { id: 'feat-1', label: 'F1' };
    const btn = featureCard(feature, true, {});
    expect(btn.classList.contains('active')).toBe(true);
  });

  it('contains .feature-card-label and .feature-card-desc', () => {
    const feature = { id: 'feat-1', label: 'My Feature', description: 'Desc text' };
    const btn = featureCard(feature, false, {});
    expect(btn.querySelector('.feature-card-label').textContent).toBe('My Feature');
    expect(btn.querySelector('.feature-card-desc').textContent).toBe('Desc text');
  });

  it('renders .confidence-badge when confidence is present', () => {
    const feature = { id: 'feat-1', label: 'F1', confidence: 'high' };
    const btn = featureCard(feature, false, {});
    const badge = btn.querySelector('.confidence-badge');
    expect(badge).not.toBeNull();
    expect(badge.classList.contains('confidence-badge-high')).toBe(true);
    expect(badge.textContent).toBe('high');
  });

  it('omits .confidence-badge when confidence is absent', () => {
    const feature = { id: 'feat-1', label: 'F1' };
    const btn = featureCard(feature, false, {});
    expect(btn.querySelector('.confidence-badge')).toBeNull();
  });

  it('calls callbacks.onSelect with feature.id on click', () => {
    const onSelect = vi.fn();
    const feature = { id: 'feat-99', label: 'F', description: '' };
    const btn = featureCard(feature, false, { onSelect });
    btn.click();
    expect(onSelect).toHaveBeenCalledWith('feat-99');
  });

  it('does not throw when callbacks is null', () => {
    const feature = { id: 'feat-1', label: 'F' };
    const btn = featureCard(feature, false, null);
    expect(() => btn.click()).not.toThrow();
  });
});

// ── renderChangeList ───────────────────────────────────────────────

describe('renderChangeList — mode=diff, updateModel', () => {
  it('fills featureList with changeListButton and sets listTitle="變更清單"', () => {
    state.mode = 'diff';
    state.updateModel = {
      diff_available: true,
      changes: [
        { id: 'feat-1', label: 'Feature 1', change_type: 'added' },
        { id: 'feat-2', label: 'Feature 2', change_type: 'removed' },
      ],
    };
    const onSelect = vi.fn();
    renderChangeList({ onSelect });
    expect(els.listTitle.textContent).toBe('變更清單');
    const btns = els.featureList.querySelectorAll('.feature-card');
    expect(btns).toHaveLength(2);
    expect(btns[0].classList.contains('changed')).toBe(true);
  });

  it('renders empty-state when changes list is empty', () => {
    state.mode = 'diff';
    state.updateModel = { diff_available: true, changes: [] };
    renderChangeList({ onSelect: vi.fn() });
    const empty = els.featureList.querySelector('.empty-state');
    expect(empty).not.toBeNull();
    expect(empty.textContent).toBe('無變更項目。');
  });
});

describe('renderChangeList — mode=diff, versionDiff path', () => {
  it('builds change list from versionDiff.node_states when no diff_available', () => {
    state.mode = 'diff';
    state.updateModel = null;
    state.l1Model = {
      features: [
        { id: 'feat-1', label: 'F1' },
        { id: 'feat-2', label: 'F2' },
      ],
    };
    state.versionDiff = {
      node_states: { 'feat-1': 'added', 'feat-2': 'unchanged' },
    };
    renderChangeList({ onSelect: vi.fn() });
    expect(els.listTitle.textContent).toBe('變更清單');
    const btns = els.featureList.querySelectorAll('.feature-card');
    expect(btns).toHaveLength(1);
  });

  it('renders empty-state when all features are unchanged in versionDiff', () => {
    state.mode = 'diff';
    state.updateModel = null;
    state.l1Model = { features: [{ id: 'feat-1', label: 'F1' }] };
    state.versionDiff = { node_states: { 'feat-1': 'unchanged' } };
    renderChangeList({ onSelect: vi.fn() });
    const empty = els.featureList.querySelector('.empty-state');
    expect(empty).not.toBeNull();
    expect(empty.textContent).toBe('兩個版本之間無功能差異。');
  });

  it('uses empty nodeStates when versionDiff has no node_states field', () => {
    state.mode = 'diff';
    state.updateModel = null;
    state.l1Model = { features: [{ id: 'feat-1', label: 'F1' }] };
    state.versionDiff = {};
    renderChangeList({ onSelect: vi.fn() });
    const empty = els.featureList.querySelector('.empty-state');
    expect(empty).not.toBeNull();
  });

  it('treats missing l1Model as empty features in versionDiff path', () => {
    state.mode = 'diff';
    state.updateModel = null;
    state.l1Model = null;
    state.versionDiff = { node_states: { 'feat-1': 'added' } };
    renderChangeList({ onSelect: vi.fn() });
    const empty = els.featureList.querySelector('.empty-state');
    expect(empty).not.toBeNull();
    expect(empty.textContent).toBe('兩個版本之間無功能差異。');
  });

  it('renders empty-state when mode=diff but no updateModel and no versionDiff', () => {
    state.mode = 'diff';
    state.updateModel = null;
    state.versionDiff = null;
    renderChangeList({ onSelect: vi.fn() });
    const empty = els.featureList.querySelector('.empty-state');
    expect(empty).not.toBeNull();
    expect(empty.textContent).toBe('無變更項目。');
  });
});

describe('renderChangeList — mode=baseline / current', () => {
  it('sets listTitle="舊版功能" and fills featureCard buttons for mode=baseline', () => {
    state.mode = 'baseline';
    state.l1Model = {
      features: [
        { id: 'feat-1', label: 'Feature 1', description: 'desc' },
      ],
    };
    renderChangeList({ onSelect: vi.fn() });
    expect(els.listTitle.textContent).toBe('舊版功能');
    const btns = els.featureList.querySelectorAll('.feature-card');
    expect(btns).toHaveLength(1);
  });

  it('sets listTitle="新版功能" for mode=current', () => {
    state.mode = 'current';
    state.l1Model = { features: [{ id: 'feat-1', label: 'F1' }] };
    renderChangeList({ onSelect: vi.fn() });
    expect(els.listTitle.textContent).toBe('新版功能');
  });

  it('renders "L1 ViewModel 載入中…" when l1Model is null', () => {
    state.mode = 'baseline';
    state.l1Model = null;
    renderChangeList({ onSelect: vi.fn() });
    const empty = els.featureList.querySelector('.empty-state');
    expect(empty).not.toBeNull();
    expect(empty.textContent).toBe('L1 ViewModel 載入中…');
  });

  it('renders "無功能資料。" when l1Model exists but features is empty', () => {
    state.mode = 'baseline';
    state.l1Model = { features: [] };
    renderChangeList({ onSelect: vi.fn() });
    const empty = els.featureList.querySelector('.empty-state');
    expect(empty).not.toBeNull();
    expect(empty.textContent).toBe('無功能資料。');
  });
});
