import { describe, it, expect } from 'vitest';
import {
  buildViewModelFromReport,
  buildL1ViewModelFromStatic,
  snapshotLabel,
} from '../js/viewmodel.js';

describe('buildViewModelFromReport', () => {
  it('returns minimal ViewModel from empty report', () => {
    const vm = buildViewModelFromReport({});
    expect(vm.mode).toBe('update-report');
    expect(vm.diff_available).toBe(false);
    expect(vm.summary).toBe('（無摘要）');
    expect(vm.change_counts).toEqual({ added: 0, removed: 0, attribute_changed: 0, dependency_changed: 0 });
    expect(vm.risk_counts).toEqual({ out_of_scope: 0, vulnerability: 0, semantic_drift: 0 });
    expect(vm.changes).toEqual([]);
    expect(vm.details).toEqual({});
    expect(vm.interrupted).toBe(false);
    expect(vm.source).toBe('UpdateReport');
  });

  it('sets diff_available=true when l1_changes is non-empty', () => {
    const vm = buildViewModelFromReport({
      l1_changes: [{ feature_id: 'feat-1', change_type: 'added', risk_flags: [] }],
    });
    expect(vm.diff_available).toBe(true);
  });

  it('preserves l0_summary from report', () => {
    const vm = buildViewModelFromReport({ l0_summary: 'my summary' });
    expect(vm.summary).toBe('my summary');
  });

  it('counts change_counts correctly from l1_changes', () => {
    const vm = buildViewModelFromReport({
      l1_changes: [
        { feature_id: 'f1', change_type: 'added', risk_flags: [] },
        { feature_id: 'f2', change_type: 'added', risk_flags: [] },
        { feature_id: 'f3', change_type: 'removed', risk_flags: [] },
        { feature_id: 'f4', change_type: 'attribute_changed', risk_flags: [] },
        { feature_id: 'f5', change_type: 'dependency_changed', risk_flags: [] },
      ],
    });
    expect(vm.change_counts).toEqual({ added: 2, removed: 1, attribute_changed: 1, dependency_changed: 1 });
  });

  it('counts risk_counts correctly from risk_flags', () => {
    const vm = buildViewModelFromReport({
      l1_changes: [
        { feature_id: 'f1', change_type: 'added', risk_flags: ['out_of_scope', 'vulnerability'] },
        { feature_id: 'f2', change_type: 'removed', risk_flags: ['semantic_drift', 'out_of_scope'] },
      ],
    });
    expect(vm.risk_counts).toEqual({ out_of_scope: 2, vulnerability: 1, semantic_drift: 1 });
  });

  it('builds details map from l2_details with before/after labels', () => {
    const vm = buildViewModelFromReport({
      l1_changes: [{ feature_id: 'feat-1', change_type: 'attribute_changed', risk_flags: [] }],
      l2_details: [{
        feature_id: 'feat-1',
        change_type: 'attribute_changed',
        baseline_label: 'Old Label',
        current_label: 'New Label',
        baseline_description: 'old desc',
        current_description: 'new desc',
        scope_state: 'in_scope',
        related_vulnerabilities: ['cve-1'],
        affected_relations: ['rel-1'],
      }],
    });
    expect(vm.details['feat-1']).toBeDefined();
    expect(vm.details['feat-1'].before.label).toBe('Old Label');
    expect(vm.details['feat-1'].after.label).toBe('New Label');
    expect(vm.details['feat-1'].source).toBe('UpdateReport.l2_details');
    expect(vm.details['feat-1'].scope_state).toBe('in_scope');
    expect(vm.details['feat-1'].related_vulnerabilities).toEqual(['cve-1']);
    expect(vm.details['feat-1'].affected_relations).toEqual(['rel-1']);
  });

  it('uses 未提供 fallbacks when l2_details fields are missing', () => {
    const vm = buildViewModelFromReport({
      l1_changes: [{ feature_id: 'feat-1', change_type: 'attribute_changed', risk_flags: [] }],
      l2_details: [{ feature_id: 'feat-1', change_type: 'attribute_changed' }],
    });
    expect(vm.details['feat-1'].before.label).toBe('未提供');
    expect(vm.details['feat-1'].before.description).toBe('未提供');
    expect(vm.details['feat-1'].after.label).toBe('未提供');
    expect(vm.details['feat-1'].after.description).toBe('未提供');
    expect(vm.details['feat-1'].scope_state).toBeNull();
    expect(vm.details['feat-1'].related_vulnerabilities).toEqual([]);
    expect(vm.details['feat-1'].affected_relations).toEqual([]);
  });

  it('creates fallback detail for l1_changes without l2 entry', () => {
    const vm = buildViewModelFromReport({
      l1_changes: [{ feature_id: 'feat-x', change_type: 'added', risk_flags: [], current_label: 'X' }],
      l2_details: [],
    });
    expect(vm.details['feat-x']).toBeDefined();
    expect(vm.details['feat-x'].before.label).toBe('未提供');
    expect(vm.details['feat-x'].after.label).toBe('X');
    expect(vm.details['feat-x'].source).toBe('UpdateReport.l1_changes');
  });

  it('sets interrupted=true when report.interrupted is true', () => {
    const vm = buildViewModelFromReport({ interrupted: true });
    expect(vm.interrupted).toBe(true);
  });

  it('maps l1_changes to changes array with correct shape', () => {
    const vm = buildViewModelFromReport({
      l1_changes: [{
        feature_id: 'feat-1',
        change_type: 'added',
        risk_flags: ['out_of_scope'],
        current_label: 'Feature A',
        baseline_label: null,
      }],
    });
    expect(vm.changes).toHaveLength(1);
    expect(vm.changes[0]).toMatchObject({
      id: 'feat-1',
      change_type: 'added',
      risk_flags: ['out_of_scope'],
      current_label: 'Feature A',
      baseline_label: null,
      source: 'UpdateReport.l1_changes',
    });
  });

  it('ignores unknown change_type in change_counts', () => {
    const vm = buildViewModelFromReport({
      l1_changes: [{ feature_id: 'f1', change_type: 'unknown_type', risk_flags: [] }],
    });
    expect(vm.change_counts).toEqual({ added: 0, removed: 0, attribute_changed: 0, dependency_changed: 0 });
  });

  it('ignores unknown risk_flag in risk_counts', () => {
    const vm = buildViewModelFromReport({
      l1_changes: [{ feature_id: 'f1', change_type: 'added', risk_flags: ['unknown_flag'] }],
    });
    expect(vm.risk_counts).toEqual({ out_of_scope: 0, vulnerability: 0, semantic_drift: 0 });
  });

  it('handles null risk_flags on l1_changes items', () => {
    const vm = buildViewModelFromReport({
      l1_changes: [{ feature_id: 'f1', change_type: 'added' }],
    });
    expect(vm.changes[0].risk_flags).toEqual([]);
    expect(vm.risk_counts).toEqual({ out_of_scope: 0, vulnerability: 0, semantic_drift: 0 });
  });
});

describe('buildL1ViewModelFromStatic', () => {
  it('maps graphData nodes to features with correct fields', () => {
    const graphData = {
      nodes: [
        { id: 'feat-1', label: 'Feature 1', confidence: 'high', description: 'desc', trigger_description: 'trig' },
        { id: 'feat-2', label: 'Feature 2', confidence: 'medium', description: 'desc2', trigger_description: null },
      ],
      edges: [],
    };
    const result = buildL1ViewModelFromStatic(graphData);
    expect(result.features).toHaveLength(2);
    expect(result.features[0]).toEqual({
      id: 'feat-1',
      label: 'Feature 1',
      confidence: 'high',
      description: 'desc',
      trigger_description: 'trig',
      source: 'L1Output.features',
    });
    expect(result.stats.feature_count).toBe(2);
  });

  it('returns empty features and count=0 when nodes is null', () => {
    const result = buildL1ViewModelFromStatic({ nodes: null });
    expect(result.features).toEqual([]);
    expect(result.stats.feature_count).toBe(0);
  });

  it('returns empty features and count=0 when nodes is missing', () => {
    const result = buildL1ViewModelFromStatic({});
    expect(result.features).toEqual([]);
    expect(result.stats.feature_count).toBe(0);
  });
});

describe('snapshotLabel', () => {
  it('returns （未知） for null', () => {
    expect(snapshotLabel(null)).toBe('（未知）');
  });

  it('returns （未知） for undefined', () => {
    expect(snapshotLabel(undefined)).toBe('（未知）');
  });

  it('returns first git tag when git_tags is non-empty', () => {
    expect(snapshotLabel({ git_tags: ['v1.0.0', 'v1.0.1'] })).toBe('v1.0.0');
  });

  it('returns label when no git_tags', () => {
    expect(snapshotLabel({ label: 'my-label' })).toBe('my-label');
  });

  it('returns formatted timestamp when no tag or label', () => {
    expect(snapshotLabel({ timestamp: '2026-05-14T12:34:56' })).toBe('2026-05-14 12:34');
  });

  it('returns （無時間） for empty snapshot', () => {
    expect(snapshotLabel({})).toBe('（無時間）');
  });

  it('prefers git_tags over label', () => {
    expect(snapshotLabel({ git_tags: ['v1.0.0'], label: 'my-label' })).toBe('v1.0.0');
  });

  it('prefers label over timestamp', () => {
    expect(snapshotLabel({ label: 'my-label', timestamp: '2026-05-14T12:34:56' })).toBe('my-label');
  });
});
