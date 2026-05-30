import { describe, it, expect, beforeEach } from 'vitest';
import { renderPage, getInitialState } from '../js/ui-wizard.js';

function noopDispatch() {}
function noopRedirect() {}
const stubApi = {
  getStatus: () => Promise.resolve({}),
  postAnalyze: () => Promise.resolve({}),
  getJobStatus: () => Promise.resolve({}),
  setProject: () => Promise.resolve({}),
};

function mount(state) {
  const c = document.createElement('div');
  document.body.appendChild(c);
  renderPage(c, state, noopDispatch, noopRedirect, stubApi);
  return c;
}

describe('renderPage shell (spec §4.1)', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('renders .wizard-shell at root for PAGE_ACTION', () => {
    const c = mount({ ...getInitialState(), page: 'PAGE_ACTION', hasApiKey: true });
    expect(c.querySelector('.wizard-shell')).not.toBeNull();
    expect(c.querySelector('.wizard-shell .wizard-rail')).not.toBeNull();
    expect(c.querySelector('.wizard-shell .wizard-content')).not.toBeNull();
    expect(c.querySelector('.wizard-shell .wizard-content .wizard-screen')).not.toBeNull();
  });

  it('places existing .wizard-card inside .wizard-screen', () => {
    const c = mount({ ...getInitialState(), page: 'PAGE_ACTION', hasApiKey: true });
    expect(c.querySelector('.wizard-screen .wizard-card')).not.toBeNull();
  });

  it('rail stepper has 6 .wizard-step items', () => {
    const c = mount({ ...getInitialState(), page: 'PAGE_SETUP' });
    expect(c.querySelectorAll('.wizard-stepper .wizard-step').length).toBe(6);
  });

  it('rail stage maps: PAGE_ACTION → 0', () => {
    const c = mount({ ...getInitialState(), page: 'PAGE_ACTION', hasApiKey: true });
    const fill = c.querySelector('.wizard-stepper-fill');
    expect(fill).not.toBeNull();
    expect(fill.style.height).toMatch(/0%|calc\(0/);
  });

  it('rail stage maps: PAGE_SETUP → 1 → height = 20%', () => {
    const c = mount({ ...getInitialState(), page: 'PAGE_SETUP' });
    const fill = c.querySelector('.wizard-stepper-fill');
    expect(fill.style.height).toMatch(/20%|calc\(20/);
  });

  it('rail stage maps: PROGRESS → 4 → height = 80%', () => {
    const c = mount({ ...getInitialState(), page: 'PROGRESS', hasApiKey: true });
    const fill = c.querySelector('.wizard-stepper-fill');
    expect(fill.style.height).toMatch(/80%|calc\(80/);
  });

  it('door-light lit only when PROGRESS + status completed', () => {
    const c1 = mount({ ...getInitialState(), page: 'PROGRESS', status: 'running' });
    expect(c1.querySelector('.wizard-door-light').classList.contains('lit')).toBe(false);
    document.body.innerHTML = '';
    const c2 = mount({ ...getInitialState(), page: 'PROGRESS', status: 'completed' });
    expect(c2.querySelector('.wizard-door-light').classList.contains('lit')).toBe(true);
  });

  it('screen has data-page attribute matching current page', () => {
    const c = mount({ ...getInitialState(), page: 'PAGE_CONFIRM', hasApiKey: true, action: 'analyze' });
    expect(c.querySelector('.wizard-screen').getAttribute('data-page')).toBe('PAGE_CONFIRM');
  });
});
