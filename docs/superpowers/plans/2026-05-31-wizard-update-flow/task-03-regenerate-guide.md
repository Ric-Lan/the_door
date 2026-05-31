# Task 03 — A 路：重生指示頁

**內容分類：** A 分支單一終點頁。讀快照清單 → 使用者選版本 → 出重生指令卡。可與 Task 04/05 並行（只依賴 01+02）。

**設計來源：** spec §4.2、§5。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`（`transition` 加 `SET_REGEN_REF`；`renderPage` 加 `PAGE_REGEN_GUIDE`）
- Test: `docs/frontend-local-version-viewer/viewer/tests/wizard-update-flow.test.js`（append）

---

- [ ] **Step 1: 寫 `SET_REGEN_REF` reducer 失敗測試**

append 到 `tests/wizard-update-flow.test.js`：

```javascript
describe('regenerate branch', () => {
  it('SET_REGEN_REF stores the chosen ref', () => {
    const base = { ...getInitialState(), page: 'PAGE_REGEN_GUIDE', updateFlow: 'regen' };
    const s = transition(base, { type: 'SET_REGEN_REF', ref: 'v1.2.2' });
    expect(s.regenRef).toBe('v1.2.2');
  });
});
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
cd docs/frontend-local-version-viewer/viewer
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "regenerate branch" --reporter=verbose 2>&1 | tail -15
```
Expected: FAIL — `regenRef` 仍是 null。

- [ ] **Step 3: 加 reducer case**

`js/ui-wizard.js` `transition` 內，`PICK_REGEN` case 後加：

```javascript
    case 'SET_REGEN_REF':
      return { ...state, regenRef: action.ref };
```

- [ ] **Step 4: 跑測試確認通過**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "regenerate branch" --reporter=verbose 2>&1 | tail -10
```
Expected: PASS。

- [ ] **Step 5: 寫重生頁 render 失敗測試**

append：

```javascript
describe('PAGE_REGEN_GUIDE render', () => {
  function render(state) {
    const container = document.createElement('div');
    renderPage(container, state, () => {}, () => {}, {});
    return container;
  }
  it('renders instruction card containing the chosen ref', () => {
    const c = render({ ...getInitialState(), page: 'PAGE_REGEN_GUIDE', updateFlow: 'regen', regenRef: 'v1.2.2' });
    expect(c.querySelector('[data-regen-cmd]')).not.toBeNull();
    expect(c.querySelector('[data-regen-cmd]').textContent).toContain('v1.2.2');
  });
  it('shows a hint to pick a version when no ref chosen yet', () => {
    const c = render({ ...getInitialState(), page: 'PAGE_REGEN_GUIDE', updateFlow: 'regen', regenRef: null });
    expect(c.querySelector('[data-regen-pick]')).not.toBeNull();
  });
});
```

- [ ] **Step 6: 跑測試確認失敗**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "PAGE_REGEN_GUIDE render" --reporter=verbose 2>&1 | tail -15
```
Expected: FAIL — 找不到 `[data-regen-cmd]` / `[data-regen-pick]`。

- [ ] **Step 7: 實作 `PAGE_REGEN_GUIDE` render case**

在 `renderPage` switch（`PAGE_UPDATE_MODE` case 之後）插入：

```javascript
    case 'PAGE_REGEN_GUIDE': {
      const ref = state.regenRef;
      const cmd = ref
        ? `the-door extract --as-version ${ref} .  # 或請 agent：load snapshot「${ref}」→ 重生每個 feature 的 L1 描述 → snapshot_write(label="${ref}", inherit_from="${ref}")`
        : null;
      wrap.innerHTML = `
        <p class="wizard-eyebrow eyebrow">步驟 / 重生</p>
        <h2>重生現有版本的解析</h2>
        <p class="wizard-subtitle lede">選一個既有版本，wizard 會給你一段指令，交給你的 agent 重跑自然語言解析。沿用原本的標籤。</p>
        <div class="wizard-field field">
          <label>選擇要重生的版本</label>
          <select data-regen-pick></select>
        </div>
        ${ref ? `
        <div class="wizard-field field">
          <label>交給 agent 執行的指令</label>
          <pre data-regen-cmd>${cmd}</pre>
        </div>` : `<p class="hint" data-regen-empty>先在上方選一個版本，指令會出現在這裡。</p>`}
        <div class="actions">
          <button class="wizard-btn-ghost btn btn-ghost" data-back="PAGE_UPDATE_MODE">← 上一步</button>
        </div>
      `;
      // 版本清單：呼叫既有 GET /api/snapshots（read-only）
      const sel = wrap.querySelector('[data-regen-pick]');
      if (sel && api && typeof api.getSnapshots === 'function') {
        sel.innerHTML = `<option value="">— 載入中 —</option>`;
        api.getSnapshots()
          .then(({ snapshots }) => {
            sel.innerHTML = `<option value="">— 請選擇 —</option>` + snapshots.map(s => {
              const r = resolveSnapshotRef(s);
              return `<option value="${r}">${r}</option>`;
            }).join('');
          })
          .catch(() => { sel.innerHTML = `<option value="">（讀取版本清單失敗）</option>`; });
        sel.addEventListener('change', e => {
          if (e.target.value) dispatch({ type: 'SET_REGEN_REF', ref: e.target.value });
        });
      }
      bindBack(wrap);
      break;
    }
```

> `bindBack(wrap)` 是既有 helper（既有頁面 `data-back` 都用它）。`resolveSnapshotRef` 來自 Task 01。

- [ ] **Step 8: 跑測試確認通過 + 全套不退步**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js --reporter=verbose 2>&1 | tail -15
./node_modules/.bin/vitest.cmd run 2>&1 | tail -6
```
Expected: 新檔全綠；全套 853 passed 不退步。

- [ ] **Step 9: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js docs/frontend-local-version-viewer/viewer/tests/wizard-update-flow.test.js
git commit -m "feat(wizard): regenerate guide page (A branch terminal)"
```

## Done when
- [ ] 選版本後 `regenRef` 寫入、指令卡顯示該識別字串
- [ ] 未選版本時顯示提示、不顯示指令卡
- [ ] 全套不退步
