// CJK-aware word-level diff using LCS (~70 lines)
const CJK_RE = /[　-〿㐀-䶿一-鿿豈-﫿]/;

export function tokenize(s) {
  const out = [];
  let buf = '';
  for (const ch of s) {
    if (CJK_RE.test(ch)) {
      if (buf) { out.push(buf); buf = ''; }
      out.push(ch);
    } else if (/\s/.test(ch)) {
      if (buf) { out.push(buf); buf = ''; }
      out.push(ch);
    } else if (/[^\w]/.test(ch)) {
      if (buf) { out.push(buf); buf = ''; }
      out.push(ch);
    } else {
      buf += ch;
    }
  }
  if (buf) out.push(buf);
  return out;
}

function lcs(a, b) {
  const m = a.length, n = b.length;
  const dp = Array.from({ length: m + 1 }, () => new Int32Array(n + 1));
  for (let i = m - 1; i >= 0; i--)
    for (let j = n - 1; j >= 0; j--)
      dp[i][j] = a[i] === b[j] ? dp[i+1][j+1] + 1 : Math.max(dp[i+1][j], dp[i][j+1]);
  const ops = [];
  let i = 0, j = 0;
  while (i < m && j < n) {
    if (a[i] === b[j])                { ops.push({ type: 'equal',  text: a[i] }); i++; j++; }
    else if (dp[i+1][j] >= dp[i][j+1]) { ops.push({ type: 'remove', text: a[i] }); i++; }
    else                               { ops.push({ type: 'add',    text: b[j] }); j++; }
  }
  while (i < m) ops.push({ type: 'remove', text: a[i++] });
  while (j < n) ops.push({ type: 'add',    text: b[j++] });
  // merge consecutive same-type
  const merged = [];
  for (const o of ops) {
    const last = merged[merged.length - 1];
    if (last && last.type === o.type) last.text += o.text;
    else merged.push({ ...o });
  }
  return merged;
}

export function wordDiff(before, after) {
  return lcs(tokenize(before), tokenize(after));
}
