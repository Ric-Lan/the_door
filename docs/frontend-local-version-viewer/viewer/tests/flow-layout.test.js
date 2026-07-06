// tests/flow-layout.test.js
import { describe, it, expect } from 'vitest';
import {
  edgeKey, detectBackEdges, splitIsolated, assignColumns,
  computeFlowLayout, MAX_PER_SUBCOL,
} from '../js/flow-layout.js';

const E = (s, t) => ({ source: s, target: t });

describe('detectBackEdges', () => {
  it('無環圖回空集合', () => {
    expect(detectBackEdges(['a', 'b', 'c'], [E('a', 'b'), E('b', 'c')]).size).toBe(0);
  });
  it('二節點環標出一條 back-edge', () => {
    const be = detectBackEdges(['a', 'b'], [E('a', 'b'), E('b', 'a')]);
    expect(be.size).toBe(1);
    expect(be.has(edgeKey('b', 'a'))).toBe(true); // 決定性：DFS 從字典序 'a' 起，b→a 是回邊
  });
  it('self-loop 忽略不計', () => {
    expect(detectBackEdges(['a'], [E('a', 'a')]).size).toBe(0);
  });
});

describe('splitIsolated', () => {
  it('無任何邊的節點進 isolated', () => {
    const r = splitIsolated(['a', 'b', 'x'], [E('a', 'b')]);
    expect(r.linked).toEqual(['a', 'b']);
    expect(r.isolated).toEqual(['x']);
  });
  it('只有 self-loop 的節點視為孤島', () => {
    const r = splitIsolated(['a', 'b', 's'], [E('a', 'b'), E('s', 's')]);
    expect(r.isolated).toEqual(['s']);
  });
});

describe('assignColumns（顯示欄：0＝最左＝entry）', () => {
  it('鏈 a→b→c：a 欄 0、b 欄 1、c 欄 2（被依賴最深在最右）', () => {
    const col = assignColumns(['a', 'b', 'c'], [E('a', 'b'), E('b', 'c')], new Set());
    expect(col.get('a')).toBe(0);
    expect(col.get('b')).toBe(1);
    expect(col.get('c')).toBe(2);
  });
  it('菱形 a→b, a→c, b→d, c→d：d 最右、a 最左', () => {
    const col = assignColumns(['a', 'b', 'c', 'd'],
      [E('a', 'b'), E('a', 'c'), E('b', 'd'), E('c', 'd')], new Set());
    expect(col.get('a')).toBe(0);
    expect(col.get('b')).toBe(1);
    expect(col.get('c')).toBe(1);
    expect(col.get('d')).toBe(2);
  });
  it('back-edge 不參與 depth 計算', () => {
    const be = new Set([edgeKey('b', 'a')]);
    const col = assignColumns(['a', 'b'], [E('a', 'b'), E('b', 'a')], be);
    expect(col.get('a')).toBe(0);
    expect(col.get('b')).toBe(1);
  });
});

describe('computeFlowLayout', () => {
  const vm = (nodes, edges) => ({ nodes: nodes.map(id => ({ id, label: id })), edges });

  it('integration-demo 形狀：order → auth/report/user → db 三欄', () => {
    const r = computeFlowLayout(vm(
      ['feat-order', 'feat-auth', 'feat-report', 'feat-user', 'feat-db'],
      [E('feat-order', 'feat-auth'), E('feat-order', 'feat-report'), E('feat-order', 'feat-user'),
       E('feat-auth', 'feat-db'), E('feat-report', 'feat-db'), E('feat-user', 'feat-db')]));
    expect(r.bands).toHaveLength(3);
    expect(r.bands[0][0]).toEqual(['feat-order']);
    expect(r.bands[1][0]).toEqual(['feat-auth', 'feat-report', 'feat-user']); // 欄內字典序
    expect(r.bands[2][0]).toEqual(['feat-db']);
    expect(r.isolated).toEqual([]);
  });

  it('超過 MAX_PER_SUBCOL 折子欄', () => {
    const ids = Array.from({ length: MAX_PER_SUBCOL + 2 }, (_, i) => `leaf-${String(i).padStart(2, '0')}`);
    const edges = ids.map(id => E('root', id));
    const r = computeFlowLayout(vm(['root', ...ids], edges));
    expect(r.bands[1]).toHaveLength(2);                      // 10 卡 → 2 子欄
    expect(r.bands[1][0]).toHaveLength(MAX_PER_SUBCOL);
    expect(r.bands[1][1]).toHaveLength(2);
  });

  it('全孤島：bands 空、全進 isolated', () => {
    const r = computeFlowLayout(vm(['a', 'b'], []));
    expect(r.bands).toEqual([]);
    expect(r.isolated).toEqual(['a', 'b']);
  });

  it('決定性：同輸入兩次呼叫深相等', () => {
    const input = vm(['c', 'a', 'b'], [E('a', 'b'), E('b', 'c'), E('c', 'a')]);
    const r1 = computeFlowLayout(input);
    const r2 = computeFlowLayout(input);
    expect(r1.bands).toEqual(r2.bands);
    expect([...r1.backEdges].sort()).toEqual([...r2.backEdges].sort());
  });
});
