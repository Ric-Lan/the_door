import { describe, it, expect, beforeEach } from 'vitest';
import { renderPage, getInitialState } from '../js/ui-wizard.js';

function mountProgress(stateOverrides = {}) {
  const c = document.createElement('div');
  document.body.appendChild(c);
  renderPage(c, {
    ...getInitialState(),
    page: 'PROGRESS',
    hasApiKey: true,
    ...stateOverrides,
  }, () => {}, () => {}, {});
  return c;
}

describe('renderPage PROGRESS integration (spec §4.2 ⓕ)', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('mounts shared progress view inside .wizard-card', () => {
    const c = mountProgress({ steps: [], currentStep: null, progress: null });
    const card = c.querySelector('.wizard-card');
    expect(card).not.toBeNull();
    // smoke: shared module produced the phasebar shell
    expect(card.querySelector('.wizard-phasebar')).not.toBeNull();
    expect(card.querySelector('.wizard-steplist')).not.toBeNull();
  });

  it('agent mode (!hasApiKey) does NOT mount phasebar (terminal block instead)', () => {
    const c = mountProgress({ hasApiKey: false, projectPath: '/x', label: 'v1' });
    expect(c.querySelector('.wizard-phasebar')).toBeNull();
    expect(c.querySelector('.wizard-agent-params')).not.toBeNull();
  });
});
