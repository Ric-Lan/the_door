import { describe, it, expect } from 'vitest';
import { state } from '../js/state.js';

describe('state', () => {
  it('has all required keys', () => {
    const keys = [
      'updateModel', 'l1Model', 'mode', 'selectedId', 'projectStatus',
      'pollingJobId', 'pollingHandle', 'layerState', 'selectedFeatureId',
      'selectedModuleId', 'l1GraphViewModel', 'l2GraphViewModel',
      'l3GraphViewModel', 'diffGraphViewModel', 'cytoscapeInstance',
      'cytoscapeAvailable', 'diffSortMode', 'layerExplanation',
      'snapshots', 'versionA', 'versionB', 'versionDiff',
    ];
    keys.forEach(k => expect(k in state, `key "${k}" missing`).toBe(true));
  });

  it('initializes nullable fields to null', () => {
    expect(state.updateModel).toBeNull();
    expect(state.l1Model).toBeNull();
    expect(state.selectedId).toBeNull();
    expect(state.projectStatus).toBeNull();
    expect(state.pollingJobId).toBeNull();
    expect(state.pollingHandle).toBeNull();
    expect(state.selectedFeatureId).toBeNull();
    expect(state.selectedModuleId).toBeNull();
    expect(state.l1GraphViewModel).toBeNull();
    expect(state.l2GraphViewModel).toBeNull();
    expect(state.l3GraphViewModel).toBeNull();
    expect(state.diffGraphViewModel).toBeNull();
    expect(state.cytoscapeInstance).toBeNull();
    expect(state.layerExplanation).toBeNull();
    expect(state.versionA).toBeNull();
    expect(state.versionB).toBeNull();
    expect(state.versionDiff).toBeNull();
  });

  it('initializes boolean fields correctly', () => {
    expect(state.cytoscapeAvailable).toBe(false);
  });

  it('initializes string fields with correct defaults', () => {
    expect(state.mode).toBe('baseline');
    expect(state.layerState).toBe('L1');
    expect(state.diffSortMode).toBe('risk');
  });

  it('initializes snapshots as empty array', () => {
    expect(Array.isArray(state.snapshots)).toBe(true);
    expect(state.snapshots).toHaveLength(0);
  });

  it('is mutable — assignments persist on the same object', () => {
    state.mode = 'diff';
    expect(state.mode).toBe('diff');
    state.mode = 'baseline'; // restore
  });
});
