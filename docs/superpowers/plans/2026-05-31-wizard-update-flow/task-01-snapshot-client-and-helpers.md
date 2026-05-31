# Task 01 — 快照清單 client + 標籤識別 helper（無 UI）

**內容分類：** 純函式 + API client 方法。本流程的地基，其他 task 都會用到。零 UI、零 reducer 改動。

**設計來源：** spec §5（標籤優先序）、§10.6/§10.7。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`（`createApi` 內加方法；檔案頂層加 export helper）
- Test: `docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js`（沿用既有檔，append 新 describe）

---

- [ ] **Step 1: 寫 `resolveSnapshotRef` 的失敗測試**

在 `tests/ui-wizard.test.js` 結尾 append：

```javascript
import { resolveSnapshotRef } from '../js/ui-wizard.js';

describe('resolveSnapshotRef', () => {
  it('prefers git_tags[0] when present', () => {
    expect(resolveSnapshotRef({ git_tags: ['v1.2.2'], label: 'x', version_id: 'uuid-1' }))
      .toBe('v1.2.2');
  });
  it('falls back to label when no git_tags', () => {
    expect(resolveSnapshotRef({ git_tags: [], label: 'my-label', version_id: 'uuid-1' }))
      .toBe('my-label');
  });
  it('falls back to version_id when no git_tags and no label', () => {
    expect(resolveSnapshotRef({ git_tags: [], label: null, version_id: 'uuid-1' }))
      .toBe('uuid-1');
  });
  it('returns null for nullish input', () => {
    expect(resolveSnapshotRef(null)).toBeNull();
  });
});
```

> 註：既有 `import { ... } from '../js/ui-wizard.js'` 已在檔案頂端；新增的 `resolveSnapshotRef` 可加在頂端那個 import，或如上另開一行 import，vitest 兩者皆可。

- [ ] **Step 2: 跑測試確認失敗**

```bash
cd docs/frontend-local-version-viewer/viewer
./node_modules/.bin/vitest.cmd run tests/ui-wizard.test.js --reporter=verbose 2>&1 | tail -20
```
Expected: FAIL — `resolveSnapshotRef is not a function` / import 解析不到。

- [ ] **Step 3: 實作 `resolveSnapshotRef`**

在 `js/ui-wizard.js` 的 `// ─── Pure helpers ───` 區塊（`parseExcludes` 附近）加：

```javascript
// Snapshot 識別字串優先序：git_tags[0] → label → version_id。
// 注意：刻意不沿用 layers.js 的 _snapLabel（它停在 label→null，會讓無標籤快照產生空指令）。
export function resolveSnapshotRef(snapshot) {
  if (!snapshot) return null;
  if (Array.isArray(snapshot.git_tags) && snapshot.git_tags.length > 0) {
    return snapshot.git_tags[0];
  }
  if (snapshot.label) return snapshot.label;
  return snapshot.version_id ?? null;
}
```

- [ ] **Step 4: 跑測試確認通過**

```bash
./node_modules/.bin/vitest.cmd run tests/ui-wizard.test.js --reporter=verbose 2>&1 | tail -20
```
Expected: PASS（4 個新 case 全綠）。

- [ ] **Step 5: 寫 `getSnapshots` 的失敗測試**

在同檔 append：

```javascript
describe('createApi.getSnapshots', () => {
  it('GETs /api/snapshots and returns parsed body', async () => {
    const fakeFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ snapshots: [{ version_id: 'u1', label: 'v1.0.0', git_tags: [] }] }),
    });
    const api = createApi(fakeFetch);
    const result = await api.getSnapshots();
    expect(fakeFetch).toHaveBeenCalledWith('/api/snapshots');
    expect(result.snapshots[0].label).toBe('v1.0.0');
  });
});
```

- [ ] **Step 6: 跑測試確認失敗**

```bash
./node_modules/.bin/vitest.cmd run tests/ui-wizard.test.js -t "getSnapshots" --reporter=verbose 2>&1 | tail -15
```
Expected: FAIL — `api.getSnapshots is not a function`。

- [ ] **Step 7: 實作 `getSnapshots`**

在 `js/ui-wizard.js` 的 `createApi` 回傳物件中（`getStatus` 旁）加：

```javascript
    getSnapshots() {
      return fetchFn('/api/snapshots').then(_check);
    },
```

- [ ] **Step 8: 跑測試確認通過 + 全套不退步**

```bash
./node_modules/.bin/vitest.cmd run tests/ui-wizard.test.js --reporter=verbose 2>&1 | tail -15
./node_modules/.bin/vitest.cmd run 2>&1 | tail -6
```
Expected: ui-wizard 測試全綠；全套維持 853 passed + 8 pre-existing failures（數字不減）。

- [ ] **Step 9: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js
git commit -m "feat(wizard): resolveSnapshotRef helper + getSnapshots api client"
```

## Done when
- [ ] `resolveSnapshotRef` 4 case 全綠
- [ ] `getSnapshots` 打 `/api/snapshots`、回傳解析後 body
- [ ] 全套 853 passed 不退步
