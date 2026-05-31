import { describe, it, expect } from 'vitest';
import { getInitialState, transition, renderPage } from '../js/ui-wizard.js';

function atUpdateMode() {
  let s = transition(getInitialState(), {
    type: 'STATUS_LOADED', hasSnapshots: true, hasApiKey: false,
    projectPath: '/p', fileCount: 3,
  });
  return transition(s, { type: 'SELECT_ACTION', action: 'update' });
}

describe('update mode branch', () => {
  it('SELECT_ACTION update lands on PAGE_UPDATE_MODE', () => {
    expect(atUpdateMode().page).toBe('PAGE_UPDATE_MODE');
  });
  it('PICK_REGEN goes to PAGE_REGEN_GUIDE and tags flow=regen', () => {
    const s = transition(atUpdateMode(), { type: 'PICK_REGEN' });
    expect(s.page).toBe('PAGE_REGEN_GUIDE');
    expect(s.updateFlow).toBe('regen');
  });
  it('PICK_NEW_DATA goes to PAGE_NEW_DATA and tags flow=new_data', () => {
    const s = transition(atUpdateMode(), { type: 'PICK_NEW_DATA' });
    expect(s.page).toBe('PAGE_NEW_DATA');
    expect(s.updateFlow).toBe('new_data');
  });
  it('SNAPSHOTS_LOADED stores list + derives knownVersionIds', () => {
    const snaps = [{ version_id: 'u1', label: 'v1', git_tags: [] },
                   { version_id: 'u2', label: 'v2', git_tags: [] }];
    const s = transition(atUpdateMode(), { type: 'SNAPSHOTS_LOADED', snapshots: snaps });
    expect(s.snapshots).toEqual(snaps);
    expect(s.knownVersionIds).toEqual(['u1', 'u2']);
  });
});

describe('PAGE_UPDATE_MODE render', () => {
  function render(state) {
    const container = document.createElement('div');
    renderPage(container, state, () => {}, () => {}, {});
    return container;
  }
  it('shows two option buttons: regen and new-data', () => {
    const c = render({ ...getInitialState(), page: 'PAGE_UPDATE_MODE', hasSnapshots: true });
    expect(c.querySelector('[data-pick="regen"]')).not.toBeNull();
    expect(c.querySelector('[data-pick="new-data"]')).not.toBeNull();
  });
});
