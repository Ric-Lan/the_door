import { wordDiff, tokenize } from '../js/diff-util.js';

describe('tokenize', () => {
  it('CJK chars are individual tokens', () => {
    expect(tokenize('你好世界')).toEqual(['你','好','世','界']);
  });
  it('ASCII words stay as units', () => {
    expect(tokenize('hello world')).toEqual(['hello',' ','world']);
  });
  it('mixed CJK + ASCII', () => {
    expect(tokenize('我 use API')).toEqual(['我',' ','use',' ','API']);
  });
});

describe('wordDiff', () => {
  it('identical strings → all equal', () => {
    const r = wordDiff('hello', 'hello');
    expect(r.every(seg => seg.type === 'equal')).toBe(true);
  });
  it('appending text → equal + add', () => {
    const r = wordDiff('hello', 'hello world');
    expect(r.find(s => s.type === 'add')?.text).toContain('world');
  });
  it('CJK token-level diff', () => {
    const r = wordDiff('使用者可在設定頁查看', '使用者可在通知中心查看');
    expect(r.some(s => s.type === 'remove' && s.text.includes('設定'))).toBe(true);
    expect(r.some(s => s.type === 'add' && s.text.includes('通知'))).toBe(true);
  });
});
