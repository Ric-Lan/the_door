# Task 07 — B 路：偵測新版本頁（唯讀掃描）

**內容分類：** B 分支「當版本」第二站。讀快照清單、比對已知集合、確認新版本出現才放行。純唯讀。

**設計來源：** spec §4.7、§10.10。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`（`transition` 加 `VERSION_DETECTED` / `DETECT_RESCAN` / `GOTO_TRANSLATE_CHOICE`；`renderPage` 加 `PAGE_VERSION_DETECT`）
- Test: `docs/frontend-local-version-viewer/viewer/tests/wizard-update-flow.test.js`（append）

---

- [ ] **Step 1: 寫 reducer 失敗測試**

append：

```javascript
describe('version detect reducer', () => {
  const base = { ...getInitialState(), page: 'PAGE_VERSION_DETECT', updateFlow: 'new_data',
    knownVersionIds: ['u1'] };
  it('VERSION_DETECTED stores the detected ref', () => {
    const s = transition(base, { type: 'VERSION_DETECTED', ref: 'v1.3.0' });
    expect(s.detectedRef).toBe('v1.3.0');
  });
  it('DETECT_RESCAN clears detectedRef to allow a fresh scan', () => {
    const s = transition({ ...base, detectedRef: 'x' }, { type: 'DETECT_RESCAN' });
    expect(s.detectedRef).toBeNull();
  });
  it('GOTO_TRANSLATE_CHOICE advances to PAGE_TRANSLATE_CHOICE', () => {
    const s = transition({ ...base, detectedRef: 'v1.3.0' }, { type: 'GOTO_TRANSLATE_CHOICE' });
    expect(s.page).toBe('PAGE_TRANSLATE_CHOICE');
  });
});
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
cd docs/frontend-local-version-viewer/viewer
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "version detect reducer" --reporter=verbose 2>&1 | tail -15
```
Expected: FAIL。

- [ ] **Step 3: 加 reducer cases**

`transition` 內，`NEXT_FROM_VERSION_GUIDE` case 後加：

```javascript
    case 'VERSION_DETECTED':
      return { ...state, detectedRef: action.ref };

    case 'DETECT_RESCAN':
      return { ...state, detectedRef: null };

    case 'GOTO_TRANSLATE_CHOICE':
      return { ...state, page: 'PAGE_TRANSLATE_CHOICE' };
```

- [ ] **Step 4: 跑測試確認通過**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "version detect reducer" --reporter=verbose 2>&1 | tail -10
```
Expected: PASS。

- [ ] **Step 5: 寫偵測頁 render 失敗測試**

append。用一個回傳「比 known 多一個 version_id」的假 api 驗證偵測；用回傳「沒變」的假 api 驗證未偵測。

```javascript
describe('PAGE_VERSION_DETECT render', () => {
  function render(state, dispatch = () => {}, api = {}) {
    const c = document.createElement('div');
    renderPage(c, state, dispatch, () => {}, api);
    return c;
  }
  const baseState = { ...getInitialState(), page: 'PAGE_VERSION_DETECT', updateFlow: 'new_data',
    knownVersionIds: ['u1'] };

  it('dispatches VERSION_DETECTED when a new version_id appears', async () => {
    const calls = [];
    const api = { getSnapshots: () => Promise.resolve({ snapshots: [
      { version_id: 'u2', label: 'v1.3.0', git_tags: [] },
      { version_id: 'u1', label: 'v1.2.2', git_tags: [] },
    ] }) };
    render(baseState, a => calls.push(a), api);
    await Promise.resolve(); await Promise.resolve();
    const detected = calls.find(a => a.type === 'VERSION_DETECTED');
    expect(detected).toBeTruthy();
    expect(detected.ref).toBe('v1.3.0');
  });

  it('shows the detected ref and an enabled next button when detectedRef set', () => {
    const c = render({ ...baseState, detectedRef: 'v1.3.0' });
    expect(c.textContent).toContain('v1.3.0');
    expect(c.querySelector('[data-detect-next]').disabled).toBe(false);
  });

  it('shows a rescan button and no next when not yet detected', () => {
    const c = render({ ...baseState, detectedRef: null });
    expect(c.querySelector('[data-detect-rescan]')).not.toBeNull();
    expect(c.querySelector('[data-detect-next]')).toBeNull();
  });
});
```

- [ ] **Step 6: 跑測試確認失敗**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "PAGE_VERSION_DETECT render" --reporter=verbose 2>&1 | tail -15
```
Expected: FAIL。

- [ ] **Step 7: 實作 `PAGE_VERSION_DETECT` render case**

在 `renderPage` switch（`PAGE_VERSION_GUIDE` case 之後）插入：

```javascript
    case 'PAGE_VERSION_DETECT': {
      const detected = state.detectedRef;
      wrap.innerHTML = `
        <p class="wizard-eyebrow eyebrow">步驟 / 偵測</p>
        <h2>確認新版本已建立</h2>
        ${detected ? `
          <p class="wizard-subtitle lede">偵測到新版本：<strong>${detected}</strong>。可以進下一步了。</p>
          <div class="actions">
            <button class="wizard-btn-ghost btn btn-ghost" data-back="PAGE_VERSION_GUIDE">← 上一步</button>
            <span class="spacer"></span>
            <button class="wizard-btn-primary btn btn-primary" data-detect-next>下一步 ${I.arrow}</button>
          </div>
        ` : `
          <p class="wizard-subtitle lede">尚未偵測到新版本。請確認上一步的指令已執行完成，再重新掃描。</p>
          <div class="actions">
            <button class="wizard-btn-ghost btn btn-ghost" data-back="PAGE_VERSION_GUIDE">← 上一步</button>
            <span class="spacer"></span>
            <button class="wizard-btn-primary btn btn-ghost" data-detect-rescan>重新掃描</button>
          </div>
        `}
      `;
      // 只在尚未偵測到時掃描，避免 re-render 無限重抓
      if (!detected && api && typeof api.getSnapshots === 'function') {
        api.getSnapshots()
          .then(({ snapshots }) => {
            const fresh = snapshots.find(s => !state.knownVersionIds.includes(s.version_id));
            if (fresh) dispatch({ type: 'VERSION_DETECTED', ref: resolveSnapshotRef(fresh) });
          })
          .catch(() => { /* 靜默：使用者可按重新掃描 */ });
      }
      const nextBtn = wrap.querySelector('[data-detect-next]');
      if (nextBtn) nextBtn.addEventListener('click', () => dispatch({ type: 'GOTO_TRANSLATE_CHOICE' }));
      const rescanBtn = wrap.querySelector('[data-detect-rescan]');
      if (rescanBtn) rescanBtn.addEventListener('click', () => dispatch({ type: 'DETECT_RESCAN' }));
      bindBack(wrap);
      break;
    }
```

> `resolveSnapshotRef` 來自 Task 01。掃描只在 `!detected` 時跑，偵測到後 `VERSION_DETECTED` 設值、
> re-render 時 `detected` 為真，不再重抓——避免迴圈。`DETECT_RESCAN` 把 `detectedRef` 清回 null，
> 觸發 re-render 時重新掃描。

- [ ] **Step 8: 跑測試確認通過 + 全套不退步**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js --reporter=verbose 2>&1 | tail -15
./node_modules/.bin/vitest.cmd run 2>&1 | tail -6
```
Expected: 新檔全綠；全套 853 passed 不退步。

- [ ] **Step 9: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js docs/frontend-local-version-viewer/viewer/tests/wizard-update-flow.test.js
git commit -m "feat(wizard): version-detect page (read-only new-snapshot scan)"
```

## Done when
- [ ] 冒出新 version_id → dispatch `VERSION_DETECTED`、顯示識別、下一步可按
- [ ] 沒新版本 → 顯示提示 + 重新掃描鈕、無下一步
- [ ] 下一步進 `PAGE_TRANSLATE_CHOICE`
- [ ] 全套不退步
