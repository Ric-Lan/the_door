import { describe, it, expect, beforeEach } from 'vitest';
import {
  renderProgressInnerHTML,
  appendPlLine,
  updateProgressCount,
} from '../js/progress-view.js';

describe('renderProgressInnerHTML', () => {
  it('returns 3 phase + 6 steplist row + no prog-live when progress=null', () => {
    const html = renderProgressInnerHTML({ steps: [], currentStep: null, progress: null });
    const c = document.createElement('div'); c.innerHTML = html;
    expect(c.querySelectorAll('.wizard-phase').length).toBe(3);
    expect(c.querySelectorAll('.wizard-sl-row').length).toBe(6);
    expect(c.querySelector('.wizard-prog-live')).toBeNull();
  });

  it('handles steps=null gracefully (fallback to empty array)', () => {
    const html = renderProgressInnerHTML({ steps: null, currentStep: null, progress: null });
    const c = document.createElement('div'); c.innerHTML = html;
    expect(c.querySelectorAll('.wizard-sl-row').length).toBe(6);
  });

  it('renders prog-live with count when progress set', () => {
    const html = renderProgressInnerHTML({
      steps: [], currentStep: null,
      progress: { files_done: 5, files_total: 10, current_file: 'a.py', current_root: 'new' },
    });
    const c = document.createElement('div'); c.innerHTML = html;
    expect(c.querySelector('.wizard-prog-live')).not.toBeNull();
    expect(c.querySelector('.wizard-pl-count').textContent).toMatch(/5\s*\/\s*10/);
  });

  it('step status drives data-step-status attr + icon', () => {
    const html = renderProgressInnerHTML({
      steps: [{ step_name: 'analyze_new', status: 'running' }],
      currentStep: 'analyze_new', progress: null,
    });
    const c = document.createElement('div'); c.innerHTML = html;
    const newRow = [...c.querySelectorAll('.wizard-sl-row')].find(r => r.textContent.includes('分析新版'));
    expect(newRow.getAttribute('data-step-status')).toBe('running');
    expect(newRow.querySelector('.wizard-spin')).not.toBeNull();
  });

  it('failed step renders error_message span', () => {
    const html = renderProgressInnerHTML({
      steps: [{ step_name: 'analyze_new', status: 'failed', error_message: 'boom' }],
      currentStep: null, progress: null,
    });
    const c = document.createElement('div'); c.innerHTML = html;
    expect(c.querySelector('.wizard-sl-err').textContent).toBe('boom');
  });

  it('skipped step renders ⊘ icon', () => {
    const html = renderProgressInnerHTML({
      steps: [{ step_name: 'diff', status: 'skipped' }],
      currentStep: null, progress: null,
    });
    const c = document.createElement('div'); c.innerHTML = html;
    const row = [...c.querySelectorAll('.wizard-sl-row')].find(r => r.getAttribute('data-step-status') === 'skipped');
    expect(row.querySelector('.si').textContent).toBe('⊘');
  });

  it('completed step renders ✓ icon', () => {
    const html = renderProgressInnerHTML({
      steps: [{ step_name: 'timeline', status: 'completed' }],
      currentStep: null, progress: null,
    });
    const c = document.createElement('div'); c.innerHTML = html;
    const row = [...c.querySelectorAll('.wizard-sl-row')].find(r => r.getAttribute('data-step-status') === 'completed');
    expect(row.querySelector('.si').textContent).toBe('✓');
  });

  it('failed step in phasebar renders ✗ icon', () => {
    const html = renderProgressInnerHTML({
      steps: [
        { step_name: 'timeline', status: 'completed' },
        { step_name: 'report', status: 'failed' },
      ],
      currentStep: null, progress: null,
    });
    const c = document.createElement('div'); c.innerHTML = html;
    const reportPhase = [...c.querySelectorAll('.wizard-phase')].find(p => p.classList.contains('failed'));
    expect(reportPhase).not.toBeNull();
    expect(reportPhase.querySelector('.pl').textContent).toContain('✗');
  });

  it('done phase in phasebar renders ✓ icon', () => {
    const html = renderProgressInnerHTML({
      steps: [
        { step_name: 'timeline', status: 'completed' },
        { step_name: 'report', status: 'completed' },
      ],
      currentStep: null, progress: null,
    });
    const c = document.createElement('div'); c.innerHTML = html;
    const donePhase = [...c.querySelectorAll('.wizard-phase')].find(p => p.classList.contains('done'));
    expect(donePhase).not.toBeNull();
    expect(donePhase.querySelector('.pl').textContent).toContain('✓');
  });

  it('step with duration_ms renders duration text', () => {
    const html = renderProgressInnerHTML({
      steps: [{ step_name: 'analyze_old', status: 'completed', duration_ms: 2500 }],
      currentStep: null, progress: null,
    });
    const c = document.createElement('div'); c.innerHTML = html;
    const row = [...c.querySelectorAll('.wizard-sl-row')].find(r => r.getAttribute('data-step-status') === 'completed');
    expect(row.querySelector('.dur').textContent).toBe('2.5s');
  });
});

describe('appendPlLine', () => {
  beforeEach(() => { document.body.innerHTML = '<div class="wizard-pl-feed"></div>'; });

  it('appends a .wizard-pl-line with file path text', () => {
    appendPlLine('foo/bar.py');
    expect(document.querySelector('.wizard-pl-feed .wizard-pl-line').textContent).toBe('foo/bar.py');
  });

  it('trims feed to ≤20 lines (FIFO)', () => {
    for (let i = 0; i < 25; i++) appendPlLine(`f${i}.py`);
    const lines = document.querySelectorAll('.wizard-pl-feed .wizard-pl-line');
    expect(lines.length).toBe(20);
    expect(lines[0].textContent).toBe('f5.py');
    expect(lines[19].textContent).toBe('f24.py');
  });

  it('is no-op when scope has no feed', () => {
    document.body.innerHTML = '';
    expect(() => appendPlLine('x.py')).not.toThrow();
  });

  it('respects scope arg', () => {
    document.body.innerHTML = '<div id="A"><div class="wizard-pl-feed"></div></div><div id="B"><div class="wizard-pl-feed"></div></div>';
    const a = document.getElementById('A');
    appendPlLine('only-a.py', a);
    expect(a.querySelector('.wizard-pl-line').textContent).toBe('only-a.py');
    expect(document.getElementById('B').querySelector('.wizard-pl-line')).toBeNull();
  });
});

describe('updateProgressCount', () => {
  beforeEach(() => { document.body.innerHTML = '<span class="wizard-pl-count"></span>'; });
  it('sets text to "done / total"', () => {
    updateProgressCount(3, 10);
    expect(document.querySelector('.wizard-pl-count').textContent).toBe('3 / 10');
  });
  it('no-op when count element absent', () => {
    document.body.innerHTML = '';
    expect(() => updateProgressCount(1, 2)).not.toThrow();
  });
});
