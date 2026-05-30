import { describe, it, expect } from 'vitest';
import { getInitialState, transition } from '../js/ui-wizard.js';

describe('errorOriginPage (spec §4.1)', () => {
  it('getInitialState includes errorOriginPage: null', () => {
    expect(getInitialState().errorOriginPage).toBeNull();
  });

  it('STATUS_ERROR from LOADING records errorOriginPage=LOADING', () => {
    const s = transition({ ...getInitialState(), page: 'LOADING' },
      { type: 'STATUS_ERROR', message: 'boom' });
    expect(s.page).toBe('PAGE_ERROR');
    expect(s.errorOriginPage).toBe('LOADING');
  });

  it('SUBMIT_ERROR from PAGE_CONFIRM records errorOriginPage=PAGE_CONFIRM', () => {
    const s = transition({ ...getInitialState(), page: 'PAGE_CONFIRM' },
      { type: 'SUBMIT_ERROR', message: 'boom' });
    expect(s.errorOriginPage).toBe('PAGE_CONFIRM');
  });

  it('POLL_UPDATE failed from PROGRESS records errorOriginPage=PROGRESS', () => {
    const s = transition({ ...getInitialState(), page: 'PROGRESS' },
      { type: 'POLL_UPDATE', status: 'failed', errorMessage: 'boom' });
    expect(s.errorOriginPage).toBe('PROGRESS');
  });

  it('POLL_FAIL ≥3 from PROGRESS records errorOriginPage=PROGRESS', () => {
    let s = { ...getInitialState(), page: 'PROGRESS', pollFailCount: 2 };
    s = transition(s, { type: 'POLL_FAIL' });
    expect(s.page).toBe('PAGE_ERROR');
    expect(s.errorOriginPage).toBe('PROGRESS');
  });

  it('POLL_FAIL <3 does not change page or errorOriginPage', () => {
    let s = { ...getInitialState(), page: 'PROGRESS', pollFailCount: 0 };
    s = transition(s, { type: 'POLL_FAIL' });
    expect(s.page).toBe('PROGRESS');
    expect(s.errorOriginPage).toBeNull();
  });
});
