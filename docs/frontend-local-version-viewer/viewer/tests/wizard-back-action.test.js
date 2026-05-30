import { describe, it, expect, beforeEach } from 'vitest';
import { getInitialState, transition, renderPage } from '../js/ui-wizard.js';

describe('BACK transition (spec §4.3)', () => {
  it('returns to target page, preserves other state', () => {
    const before = {
      ...getInitialState(),
      page: 'PAGE_LABEL',
      action: 'analyze',
      excludesRaw: 'tests/',
      label: 'v1.0.0',
      fileCount: 42,
    };
    const after = transition(before, { type: 'BACK', target: 'PAGE_SETUP' });
    expect(after.page).toBe('PAGE_SETUP');
    expect(after.action).toBe('analyze');
    expect(after.excludesRaw).toBe('tests/');
    expect(after.label).toBe('v1.0.0');
    expect(after.fileCount).toBe(42);
  });

  it('BACK to PAGE_ACTION from PAGE_SETUP', () => {
    const s = transition({ ...getInitialState(), page: 'PAGE_SETUP' },
      { type: 'BACK', target: 'PAGE_ACTION' });
    expect(s.page).toBe('PAGE_ACTION');
  });

  it('BACK to PAGE_LABEL from PAGE_CONFIRM (analyze path)', () => {
    const s = transition({ ...getInitialState(), page: 'PAGE_CONFIRM', action: 'analyze' },
      { type: 'BACK', target: 'PAGE_LABEL' });
    expect(s.page).toBe('PAGE_LABEL');
  });

  it('BACK to PAGE_ACTION from PAGE_CONFIRM (update path)', () => {
    const s = transition({ ...getInitialState(), page: 'PAGE_CONFIRM', action: 'update' },
      { type: 'BACK', target: 'PAGE_ACTION' });
    expect(s.page).toBe('PAGE_ACTION');
  });

  it('unknown target still sets page (caller responsibility)', () => {
    // We allow any string target; validation is at button binding time.
    const s = transition(getInitialState(), { type: 'BACK', target: 'FOO' });
    expect(s.page).toBe('FOO');
  });
});

describe('上一步 button bindings (spec §4.2 ⓑ/ⓓ)', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  function mount(state) {
    const c = document.createElement('div');
    document.body.appendChild(c);
    const actions = [];
    const dispatch = (a) => actions.push(a);
    renderPage(c, { ...getInitialState(), ...state }, dispatch, () => {}, {});
    return { c, actions };
  }

  it('PAGE_SETUP has .wizard-btn-ghost → dispatches BACK target=PAGE_ACTION', () => {
    const { c, actions } = mount({ page: 'PAGE_SETUP' });
    const btn = c.querySelector('.wizard-btn-ghost');
    expect(btn).not.toBeNull();
    btn.click();
    expect(actions).toContainEqual({ type: 'BACK', target: 'PAGE_ACTION' });
  });

  it('PAGE_LABEL has .wizard-btn-ghost → dispatches BACK target=PAGE_SETUP', () => {
    const { c, actions } = mount({ page: 'PAGE_LABEL' });
    c.querySelector('.wizard-btn-ghost').click();
    expect(actions).toContainEqual({ type: 'BACK', target: 'PAGE_SETUP' });
  });

  it('PAGE_CONFIRM analyze path → BACK target=PAGE_LABEL', () => {
    const { c, actions } = mount({ page: 'PAGE_CONFIRM', action: 'analyze' });
    c.querySelector('.wizard-btn-ghost').click();
    expect(actions).toContainEqual({ type: 'BACK', target: 'PAGE_LABEL' });
  });

  it('PAGE_CONFIRM update path → BACK target=PAGE_ACTION', () => {
    const { c, actions } = mount({ page: 'PAGE_CONFIRM', action: 'update' });
    c.querySelector('.wizard-btn-ghost').click();
    expect(actions).toContainEqual({ type: 'BACK', target: 'PAGE_ACTION' });
  });
});
