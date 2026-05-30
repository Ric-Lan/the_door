import { describe, it, expect } from 'vitest';
import { phaseStatus, labelFor, PHASE_BUCKETS, STEP_LABELS } from '../js/phase-status.js';

const EXPLORE = PHASE_BUCKETS.find(b => b.id === 'explore');
const ANALYZE = PHASE_BUCKETS.find(b => b.id === 'analyze');
const REPORT  = PHASE_BUCKETS.find(b => b.id === 'report');

describe('PHASE_BUCKETS shape (spec §5.3)', () => {
  it('has 3 buckets explore/analyze/report', () => {
    expect(PHASE_BUCKETS.map(b => b.id)).toEqual(['explore', 'analyze', 'report']);
  });
  it('explore owns analyze_old + analyze_new', () => {
    expect(EXPLORE.steps).toEqual(['analyze_old', 'analyze_new']);
  });
  it('analyze owns diff + scope_verify', () => {
    expect(ANALYZE.steps).toEqual(['diff', 'scope_verify']);
  });
  it('report owns timeline + report', () => {
    expect(REPORT.steps).toEqual(['timeline', 'report']);
  });
});

describe('phaseStatus()', () => {
  it('returns pending when no owned step in list', () => {
    expect(phaseStatus(EXPLORE, [], null)).toBe('pending');
  });

  it('returns active when any owned step is running', () => {
    expect(phaseStatus(EXPLORE,
      [{ step_name: 'analyze_new', status: 'running' }], null)).toBe('active');
  });

  it('returns active when currentStep is in bucket (even if no running)', () => {
    expect(phaseStatus(EXPLORE,
      [{ step_name: 'analyze_new', status: 'pending' }], 'analyze_new')).toBe('active');
  });

  it('returns done when all owned steps completed', () => {
    expect(phaseStatus(REPORT, [
      { step_name: 'timeline', status: 'completed' },
      { step_name: 'report',   status: 'completed' },
    ], null)).toBe('done');
  });

  it('returns done when all owned steps skipped (首次分析 explore bucket)', () => {
    expect(phaseStatus(ANALYZE, [
      { step_name: 'diff',         status: 'skipped' },
      { step_name: 'scope_verify', status: 'skipped' },
    ], null)).toBe('done');
  });

  it('returns done when mix of completed + skipped (首次 explore bucket)', () => {
    expect(phaseStatus(EXPLORE, [
      { step_name: 'analyze_old', status: 'skipped' },
      { step_name: 'analyze_new', status: 'completed' },
    ], null)).toBe('done');
  });

  it('returns failed when any owned step failed (overrides done/active)', () => {
    expect(phaseStatus(REPORT, [
      { step_name: 'timeline', status: 'completed' },
      { step_name: 'report',   status: 'failed' },
    ], null)).toBe('failed');
  });

  it('failed beats running (active) — design原則 1 不可造假進度', () => {
    expect(phaseStatus(EXPLORE, [
      { step_name: 'analyze_old', status: 'failed' },
      { step_name: 'analyze_new', status: 'running' },
    ], 'analyze_new')).toBe('failed');
  });

  it('returns pending when partial completion (missing owned step)', () => {
    expect(phaseStatus(EXPLORE,
      [{ step_name: 'analyze_old', status: 'completed' }], null)).toBe('pending');
  });
});

describe('STEP_LABELS map', () => {
  it('has all 6 canonical step labels', () => {
    expect(Object.keys(STEP_LABELS).sort()).toEqual([
      'analyze_new', 'analyze_old', 'diff', 'report', 'scope_verify', 'timeline',
    ]);
  });
  it('falls back to raw step_name for unknown keys (via labelFor)', () => {
    expect(labelFor('mystery_step')).toBe('mystery_step');
  });
});
