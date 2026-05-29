import { statusBadge, renderDoubtDetail } from '../js/ui-doubt.js';

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

describe('renderDoubtDetail', () => {
  it('null doubt renders .empty-state placeholder (not .no-selection)', () => {
    const container = document.createElement('div');
    renderDoubtDetail(container, null);
    expect(container.querySelector('.empty-state')).not.toBeNull();
    expect(container.querySelector('.no-selection')).toBeNull();
    expect(container.textContent).toContain('請選擇一個疑義項目');
  });

  it('non-null doubt renders detail panel with title + status badge + fields', () => {
    const container = document.createElement('div');
    renderDoubtDetail(container, {
      title: 'Test doubt',
      anomaly_type: 'orphan',
      description: 'desc',
      status: 'resolved',
      assignee: 'alice',
      source_feature: 'feat-x',
    });
    expect(container.querySelector('.doubt-detail')).not.toBeNull();
    expect(container.querySelector('.doubt-title').textContent).toBe('Test doubt');
    expect(container.querySelector('.confidence-badge-high')).not.toBeNull();
    expect(container.textContent).toContain('orphan');
    expect(container.textContent).toContain('alice');
    expect(container.textContent).toContain('feat-x');
  });

  it('non-null doubt with missing fields renders em dashes via nullish fallback', () => {
    const container = document.createElement('div');
    renderDoubtDetail(container, { status: 'open' });
    // title fallback '（無標題）'
    expect(container.querySelector('.doubt-title').textContent).toBe('（無標題）');
    // each missing field renders '—'
    const fieldValues = container.querySelectorAll('.doubt-field span:nth-child(2)');
    // fields rendered: 異常類型, 說明, 狀態, 指派對象, 來源功能
    // status 'open' renders badge with label '未解決' (not '—'), others render '—'
    expect(fieldValues[0].textContent).toBe('—'); // 異常類型
    expect(fieldValues[1].textContent).toBe('—'); // 說明
    expect(fieldValues[3].textContent).toBe('—'); // 指派對象
    expect(fieldValues[4].textContent).toBe('—'); // 來源功能
  });

  it('escapes HTML in doubt fields', () => {
    const container = document.createElement('div');
    renderDoubtDetail(container, {
      title: '<script>alert(1)</script>',
      status: 'open',
    });
    // Two-pronged assertion (jsdom-version-independent):
    // (1) NO actual <script> element was created — proves escape happened before HTML parse
    // (2) textContent is the literal source string — proves chars are present as text, not markup
    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('.doubt-title').textContent).toBe('<script>alert(1)</script>');
  });
});
