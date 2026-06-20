import { describe, it, expect } from 'vitest';
import { featureVerdict, integrationBadge, renderIntegrationPanel } from '../js/ui-integration.js';

describe('featureVerdict', () => {
  const integ = { features: { a: 'gap', b: 'backed', c: 'undetermined', d: 'none' } };
  it('returns verdict for a known feature', () => {
    expect(featureVerdict(integ, 'a')).toBe('gap');
    expect(featureVerdict(integ, 'b')).toBe('backed');
  });
  it('returns null for "none" (no static deps)', () => {
    expect(featureVerdict(integ, 'd')).toBe(null);
  });
  it('returns null when missing or no integration', () => {
    expect(featureVerdict(integ, 'zzz')).toBe(null);
    expect(featureVerdict(null, 'a')).toBe(null);
  });
});

describe('integrationBadge', () => {
  it('builds a span with the right symbol+class for gap', () => {
    const el = integrationBadge('gap');
    expect(el.tagName).toBe('SPAN');
    expect(el.classList.contains('integration-badge')).toBe(true);
    expect(el.classList.contains('integration-gap')).toBe(true);
    expect(el.textContent).toContain('❌');
  });
  it('uses ✅ for backed, ⚠ for undetermined', () => {
    expect(integrationBadge('backed').textContent).toContain('✅');
    expect(integrationBadge('undetermined').textContent).toContain('⚠');
  });
  it('returns null for null/none', () => {
    expect(integrationBadge(null)).toBe(null);
    expect(integrationBadge('none')).toBe(null);
  });
});

describe('renderIntegrationPanel', () => {
  const integ = {
    rollup: { backed: 2, gap: 1, undetermined: 1, conceptual: 0, not_assessed: 0 },
    relations: [
      { from_feature: 'feat-user', to_feature: 'feat-db', verdict: 'gap' },
      { from_feature: 'feat-cache', to_feature: 'feat-redis', verdict: 'undetermined' },
      { from_feature: 'feat-order', to_feature: 'feat-db', verdict: 'backed' },
    ],
  };
  it('shows rollup summary and one row per gap/undetermined', () => {
    const root = document.createElement('div');
    renderIntegrationPanel(root, integ, {});
    expect(root.textContent).toContain('1');           // gap 數
    expect(root.querySelectorAll('.integration-row').length).toBe(2);  // gap + undetermined（backed 不列）
  });
  it('clicking a gap row calls onSelectFeature with from_feature', () => {
    const root = document.createElement('div');
    const picked = [];
    renderIntegrationPanel(root, integ, { onSelectFeature: id => picked.push(id) });
    root.querySelector('.integration-row').click();
    expect(picked).toContain('feat-user');
  });
  it('shows 未評估 empty state when structure missing', () => {
    const root = document.createElement('div');
    renderIntegrationPanel(root, { structure_missing: true, rollup: {}, relations: [] }, {});
    expect(root.textContent).toContain('未評估');
  });
  it('shows 未評估 (not "all connected") when everything is not_assessed', () => {
    const root = document.createElement('div');
    const allUntyped = {
      rollup: { backed: 0, gap: 0, undetermined: 0, conceptual: 0, not_assessed: 24 },
      relations: [{ from_feature: 'a', to_feature: 'b', verdict: 'not_assessed' }],
    };
    renderIntegrationPanel(root, allUntyped, {});
    expect(root.textContent).toContain('未評估');
    expect(root.textContent).not.toContain('都接上了');
  });
});
