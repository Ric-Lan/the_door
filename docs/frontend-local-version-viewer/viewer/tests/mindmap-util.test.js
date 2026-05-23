import { selectDiffBadge, DIFF_BADGE } from '../js/mindmap-util.js';

describe('selectDiffBadge', () => {
  it('returns null when node id not in diffNodes', () => {
    expect(selectDiffBadge('foo', [])).toBeNull();
    expect(selectDiffBadge('foo', [{ id: 'bar', change_type: 'added' }])).toBeNull();
  });
  it('returns added badge with correct palette + text', () => {
    const b = selectDiffBadge('x', [{ id: 'x', change_type: 'added' }]);
    expect(b).toBe(DIFF_BADGE.added);
    expect(b.text).toBe('+ 新增');
    expect(b.fill).toBe('#d4edda');
  });
  it('removed badge', () => {
    expect(selectDiffBadge('x', [{ id: 'x', change_type: 'removed' }]).text).toBe('− 移除');
  });
  it('attribute_changed → ~ 修改', () => {
    expect(selectDiffBadge('x', [{ id: 'x', change_type: 'attribute_changed' }]).text).toBe('~ 修改');
  });
  it('dependency_changed reuses modified palette but distinct text', () => {
    const b = selectDiffBadge('x', [{ id: 'x', change_type: 'dependency_changed' }]);
    expect(b.text).toBe('≠ 依賴');
    expect(b.fill).toBe('#ffe0cc');
  });
  it('unknown change_type → null', () => {
    expect(selectDiffBadge('x', [{ id: 'x', change_type: 'weird' }])).toBeNull();
  });
  it('null diffNodes safe', () => {
    expect(selectDiffBadge('x', null)).toBeNull();
  });
});
