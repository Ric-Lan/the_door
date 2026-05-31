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

describe('regenerate branch', () => {
  it('SET_REGEN_REF stores the chosen ref', () => {
    const base = { ...getInitialState(), page: 'PAGE_REGEN_GUIDE', updateFlow: 'regen' };
    const s = transition(base, { type: 'SET_REGEN_REF', ref: 'v1.2.2' });
    expect(s.regenRef).toBe('v1.2.2');
  });
});

describe('PAGE_REGEN_GUIDE render', () => {
  function render(state) {
    const container = document.createElement('div');
    renderPage(container, state, () => {}, () => {}, {});
    return container;
  }
  it('renders instruction card containing the chosen ref', () => {
    const c = render({ ...getInitialState(), page: 'PAGE_REGEN_GUIDE', updateFlow: 'regen', regenRef: 'v1.2.2' });
    expect(c.querySelector('[data-regen-cmd]')).not.toBeNull();
    expect(c.querySelector('[data-regen-cmd]').textContent).toContain('v1.2.2');
  });
  it('shows a hint to pick a version when no ref chosen yet', () => {
    const c = render({ ...getInitialState(), page: 'PAGE_REGEN_GUIDE', updateFlow: 'regen', regenRef: null });
    expect(c.querySelector('[data-regen-pick]')).not.toBeNull();
  });
});

describe('new-data branch reducer', () => {
  const base = { ...getInitialState(), page: 'PAGE_NEW_DATA', updateFlow: 'new_data' };
  it('SET_NEW_DATA_PATH stores the path', () => {
    const s = transition(base, { type: 'SET_NEW_DATA_PATH', path: '/downloads/v2' });
    expect(s.newDataPath).toBe('/downloads/v2');
  });
  it('SET_BASELINE stores the baseline ref', () => {
    const s = transition(base, { type: 'SET_BASELINE', ref: 'v1.2.2' });
    expect(s.baselineRef).toBe('v1.2.2');
  });
  it('NEXT_FROM_NEW_DATA advances to PAGE_SIMILARITY_GUIDE', () => {
    const s = transition({ ...base, newDataPath: '/d/v2', baselineRef: 'v1.2.2' },
      { type: 'NEXT_FROM_NEW_DATA' });
    expect(s.page).toBe('PAGE_SIMILARITY_GUIDE');
  });
});

describe('PAGE_NEW_DATA render', () => {
  function render(state, dispatch = () => {}) {
    const container = document.createElement('div');
    renderPage(container, state, dispatch, () => {}, {});
    return container;
  }
  it('has a path input and a baseline select', () => {
    const c = render({ ...getInitialState(), page: 'PAGE_NEW_DATA', updateFlow: 'new_data' });
    expect(c.querySelector('[data-newdata-path]')).not.toBeNull();
    expect(c.querySelector('[data-baseline-pick]')).not.toBeNull();
  });
  it('next button is disabled until both path and baseline are set', () => {
    const c = render({ ...getInitialState(), page: 'PAGE_NEW_DATA', updateFlow: 'new_data',
      newDataPath: '', baselineRef: null });
    expect(c.querySelector('[data-newdata-next]').disabled).toBe(true);
  });
  it('next button enabled when both set', () => {
    const c = render({ ...getInitialState(), page: 'PAGE_NEW_DATA', updateFlow: 'new_data',
      newDataPath: '/d/v2', baselineRef: 'v1.2.2' });
    expect(c.querySelector('[data-newdata-next]').disabled).toBe(false);
  });
});

describe('similarity gate reducer', () => {
  const atGuide = { ...getInitialState(), page: 'PAGE_SIMILARITY_GUIDE', updateFlow: 'new_data',
    newDataPath: '/d/v2', baselineRef: 'v1.2.2' };
  it('NEXT_FROM_SIM_GUIDE advances to PAGE_SIMILARITY_DECISION', () => {
    const s = transition(atGuide, { type: 'NEXT_FROM_SIM_GUIDE' });
    expect(s.page).toBe('PAGE_SIMILARITY_DECISION');
  });
  it('DECIDE_VERSION advances to PAGE_VERSION_GUIDE', () => {
    const s = transition({ ...atGuide, page: 'PAGE_SIMILARITY_DECISION' }, { type: 'DECIDE_VERSION' });
    expect(s.page).toBe('PAGE_VERSION_GUIDE');
  });
  it('DECIDE_NEWPROJECT keeps page (redirect handled as side effect)', () => {
    const s = transition({ ...atGuide, page: 'PAGE_SIMILARITY_DECISION' }, { type: 'DECIDE_NEWPROJECT' });
    expect(s.page).toBe('PAGE_SIMILARITY_DECISION');
  });
});

describe('PAGE_SIMILARITY_GUIDE render', () => {
  function render(state) {
    const c = document.createElement('div');
    renderPage(c, state, () => {}, () => {}, {});
    return c;
  }
  it('shows a compare command embedding path and baseline', () => {
    const c = render({ ...getInitialState(), page: 'PAGE_SIMILARITY_GUIDE',
      updateFlow: 'new_data', newDataPath: '/d/v2', baselineRef: 'v1.2.2' });
    const cmd = c.querySelector('[data-compare-cmd]');
    expect(cmd).not.toBeNull();
    expect(cmd.textContent).toContain('/d/v2');
    expect(cmd.textContent).toContain('v1.2.2');
  });
});

describe('PAGE_SIMILARITY_DECISION render', () => {
  function render(dispatch = () => {}, redirectFn = () => {}) {
    const c = document.createElement('div');
    renderPage(c, { ...getInitialState(), page: 'PAGE_SIMILARITY_DECISION',
      updateFlow: 'new_data', newDataPath: '/d/v2', baselineRef: 'v1.2.2' },
      dispatch, redirectFn, {});
    return c;
  }
  it('shows threshold guidance and two decision buttons', () => {
    const c = render();
    expect(c.textContent).toContain('六成');
    expect(c.querySelector('[data-decide-version]')).not.toBeNull();
    expect(c.querySelector('[data-decide-newproject]')).not.toBeNull();
  });
  it('version button dispatches DECIDE_VERSION', () => {
    const calls = [];
    const c = render(a => calls.push(a.type));
    c.querySelector('[data-decide-version]').click();
    expect(calls).toContain('DECIDE_VERSION');
  });
  it('new-project button redirects to /wizard.html', () => {
    let redirected = null;
    const c = render(() => {}, (u) => { redirected = u; });
    c.querySelector('[data-decide-newproject]').click();
    expect(redirected).toBe('/wizard.html');
  });
});
