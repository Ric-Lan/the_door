import { describe, it, expect } from 'vitest';
import { featureVerdict, integrationBadge } from '../js/ui-integration.js';

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
