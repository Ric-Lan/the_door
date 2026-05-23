import { statusBadge } from '../js/ui-doubt.js';

describe('statusBadge', () => {
  it('open → 未解決 low palette', () => {
    expect(statusBadge('open')).toEqual({ className: 'confidence-badge confidence-badge-low', label: '未解決' });
  });
  it('assigned → 處理中 medium', () => {
    expect(statusBadge('assigned').label).toBe('處理中');
  });
  it('resolved → 已解決 high', () => {
    expect(statusBadge('resolved').label).toBe('已解決');
  });
  it('escalated → custom red', () => {
    expect(statusBadge('escalated').label).toBe('已升級');
  });
  it('unknown → fallback to open', () => {
    expect(statusBadge('garbage').label).toBe('未解決');
  });
});
