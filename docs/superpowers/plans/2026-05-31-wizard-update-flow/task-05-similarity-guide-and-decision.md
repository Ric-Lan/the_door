# Task 05 — B 路：結構比對指示頁 + 相似度判讀/決策頁

**內容分類：** B 分支中段兩頁。出結構比對指令卡 → 判讀準則 + 兩顆決策按鈕 + baseline 缺結構引導文字。

**設計來源：** spec §4.4、§4.5、§6、§10.8。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`（`transition` 加 `NEXT_FROM_SIM_GUIDE` / `DECIDE_VERSION` / `DECIDE_NEWPROJECT`；`renderPage` 加 `PAGE_SIMILARITY_GUIDE` / `PAGE_SIMILARITY_DECISION`）
- Test: `docs/frontend-local-version-viewer/viewer/tests/wizard-update-flow.test.js`（append）

---

- [ ] **Step 1: 寫 reducer 失敗測試**

append：

```javascript
describe('similarity gate reducer', () => {
  const atGuide = { ...getInitialState(), page: 'PAGE_SIMILARITY_GUIDE', updateFlow: 'new_data',
    newDataPath: '/d/v2', baselineRef: 'v1.2.2' };
  it('NEXT_FROM_SIM_GUIDE advances to PAGE_SIMILARITY_DECISION', () => {
    const s = transition(atGuide, { type: 'NEXT_FROM_SIM_GUIDE' });
    expect(s.page).toBe('PAGE_SIMILARITY_DECISION');
  });
  it('DECIDE_VERSION advances to PAGE_VERSION_GUIDE', () => {
    const s = transition({ ...atGuide, page: 'PAGE_SIMILARITY_DECISION' }, { type: 'DECIDE_VERSION' });
    expect(s.page).toBe('PAGE_VERSION_GUIDE');
  });
  it('DECIDE_NEWPROJECT keeps page (redirect handled as side effect)', () => {
    const s = transition({ ...atGuide, page: 'PAGE_SIMILARITY_DECISION' }, { type: 'DECIDE_NEWPROJECT' });
    expect(s.page).toBe('PAGE_SIMILARITY_DECISION');
  });
});
```

> `DECIDE_NEWPROJECT` 不改 page；導回首頁是 render 層的 side effect（呼叫 redirectFn），reducer 維持純函式。

- [ ] **Step 2: 跑測試確認失敗**

```bash
cd docs/frontend-local-version-viewer/viewer
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "similarity gate reducer" --reporter=verbose 2>&1 | tail -15
```
Expected: FAIL。

- [ ] **Step 3: 加 reducer cases**

`transition` 內，`NEXT_FROM_NEW_DATA` case 後加：

```javascript
    case 'NEXT_FROM_SIM_GUIDE':
      return { ...state, page: 'PAGE_SIMILARITY_DECISION' };

    case 'DECIDE_VERSION':
      return { ...state, page: 'PAGE_VERSION_GUIDE' };

    case 'DECIDE_NEWPROJECT':
      return { ...state };  // page 不變；導頁由 render side effect 處理
```

- [ ] **Step 4: 跑測試確認通過**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "similarity gate reducer" --reporter=verbose 2>&1 | tail -10
```
Expected: PASS。

- [ ] **Step 5: 寫結構比對指示頁 render 失敗測試**

append：

```javascript
describe('PAGE_SIMILARITY_GUIDE render', () => {
  function render(state) {
    const c = document.createElement('div');
    renderPage(c, state, () => {}, () => {}, {});
    return c;
  }
  it('shows a compare command embedding path and baseline', () => {
    const c = render({ ...getInitialState(), page: 'PAGE_SIMILARITY_GUIDE',
      updateFlow: 'new_data', newDataPath: '/d/v2', baselineRef: 'v1.2.2' });
    const cmd = c.querySelector('[data-compare-cmd]');
    expect(cmd).not.toBeNull();
    expect(cmd.textContent).toContain('/d/v2');
    expect(cmd.textContent).toContain('v1.2.2');
  });
});
```

- [ ] **Step 6: 跑測試確認失敗**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "PAGE_SIMILARITY_GUIDE render" --reporter=verbose 2>&1 | tail -12
```
Expected: FAIL。

- [ ] **Step 7: 實作 `PAGE_SIMILARITY_GUIDE` render case**

在 `renderPage` switch（`PAGE_NEW_DATA` case 之後）插入：

```javascript
    case 'PAGE_SIMILARITY_GUIDE': {
      const cmd = `extract_structure(codebase_path="${state.newDataPath}")  ` +
        `# 然後把回傳的 nodes 與基準版本「${state.baselineRef}」的快照節點比對，` +
        `算出沿用幾個 / 變動幾個 → 回報相似度百分比`;
      wrap.innerHTML = `
        <p class="wizard-eyebrow eyebrow">步驟 / 結構比對</p>
        <h2>先讓 agent 跑一次結構比對</h2>
        <p class="wizard-subtitle lede">wizard 不會自己算。把下面指令交給你的 agent，它會回報新資料跟基準版本的相似度。</p>
        <div class="wizard-field field">
          <label>交給 agent 執行的指令</label>
          <pre data-compare-cmd>${cmd}</pre>
        </div>
        <p class="hint">若 agent 回報「基準版本缺結構資料、無法比對」，請先跑
          <code>the-door extract --as-version ${state.baselineRef} &lt;baseline 原始碼路徑&gt;</code>
          補檔（不需 API key），再回來。</p>
        <div class="actions">
          <button class="wizard-btn-ghost btn btn-ghost" data-back="PAGE_NEW_DATA">← 上一步</button>
          <span class="spacer"></span>
          <button class="wizard-btn-primary btn btn-primary" data-sim-next>我已拿到相似度 ${I.arrow}</button>
        </div>
      `;
      wrap.querySelector('[data-sim-next]').addEventListener('click',
        () => dispatch({ type: 'NEXT_FROM_SIM_GUIDE' }));
      bindBack(wrap);
      break;
    }
```

- [ ] **Step 8: 寫判讀/決策頁 render 失敗測試**

append：

```javascript
describe('PAGE_SIMILARITY_DECISION render', () => {
  function render(dispatch = () => {}, redirectFn = () => {}) {
    const c = document.createElement('div');
    renderPage(c, { ...getInitialState(), page: 'PAGE_SIMILARITY_DECISION',
      updateFlow: 'new_data', newDataPath: '/d/v2', baselineRef: 'v1.2.2' },
      dispatch, redirectFn, {});
    return c;
  }
  it('shows threshold guidance and two decision buttons', () => {
    const c = render();
    expect(c.textContent).toContain('六成');
    expect(c.querySelector('[data-decide-version]')).not.toBeNull();
    expect(c.querySelector('[data-decide-newproject]')).not.toBeNull();
  });
  it('version button dispatches DECIDE_VERSION', () => {
    const calls = [];
    const c = render(a => calls.push(a.type));
    c.querySelector('[data-decide-version]').click();
    expect(calls).toContain('DECIDE_VERSION');
  });
  it('new-project button redirects to /wizard.html', () => {
    let redirected = null;
    const c = render(() => {}, (u) => { redirected = u; });
    c.querySelector('[data-decide-newproject]').click();
    expect(redirected).toBe('/wizard.html');
  });
});
```

- [ ] **Step 9: 跑測試確認失敗**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "PAGE_SIMILARITY_DECISION render" --reporter=verbose 2>&1 | tail -15
```
Expected: FAIL。

- [ ] **Step 10: 實作 `PAGE_SIMILARITY_DECISION` render case**

在 `renderPage` switch（`PAGE_SIMILARITY_GUIDE` case 之後）插入：

```javascript
    case 'PAGE_SIMILARITY_DECISION': {
      wrap.innerHTML = `
        <p class="wizard-eyebrow eyebrow">步驟 / 判讀</p>
        <h2>這份新資料算不算同一個專案？</h2>
        <p class="wizard-subtitle lede">對照 agent 回報的相似度，自己決定走哪一條。</p>
        <div class="wizard-mode-note mode-note">
          <span>判讀準則：相似度（沿用功能比例）<strong>高於約六成</strong>視為同專案的新版本，做版本差異比較；
          <strong>低於約六成</strong>表示差異過大，當作另一個新專案處理。邊界情況由你裁量。</span>
        </div>
        <div class="wizard-options opts">
          <button class="wizard-option-btn opt" data-decide-version>
            <span class="ico">${I.refresh}</span>
            <span class="tx"><strong>當作版本比較</strong><span>產生對基準版本做差異解析的指令。</span></span>
            ${I.arrow}
          </button>
          <button class="wizard-option-btn opt" data-decide-newproject>
            <span class="ico">${I.scan}</span>
            <span class="tx"><strong>當作新專案</strong><span>回首頁，把這份資料當全新專案分析。</span></span>
            ${I.arrow}
          </button>
        </div>
        <div class="actions">
          <button class="wizard-btn-ghost btn btn-ghost" data-back="PAGE_SIMILARITY_GUIDE">← 上一步</button>
        </div>
      `;
      wrap.querySelector('[data-decide-version]').addEventListener('click',
        () => dispatch({ type: 'DECIDE_VERSION' }));
      wrap.querySelector('[data-decide-newproject]').addEventListener('click',
        () => { dispatch({ type: 'DECIDE_NEWPROJECT' }); redirectFn('/wizard.html'); });
      bindBack(wrap);
      break;
    }
```

> `redirectFn` 是 `renderPage` 的既有參數（既有 view 動作就用它導頁）。「當新專案」導回 `/wizard.html` 首頁，
> 使用者在首頁用既有「切換專案 / 首次分析」流程處理新資料夾——符合 spec §4.5「導回首頁既有流程」。

- [ ] **Step 11: 跑測試確認通過 + 全套不退步**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js --reporter=verbose 2>&1 | tail -15
./node_modules/.bin/vitest.cmd run 2>&1 | tail -6
```
Expected: 新檔全綠；全套 853 passed 不退步。

- [ ] **Step 12: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js docs/frontend-local-version-viewer/viewer/tests/wizard-update-flow.test.js
git commit -m "feat(wizard): similarity compare guide + decision page (B branch gate)"
```

## Done when
- [ ] 結構比對頁指令卡含路徑與 baseline、附 baseline 缺結構引導文字
- [ ] 判讀頁有六成準則文字 + 兩顆決策按鈕
- [ ] 當版本 → `PAGE_VERSION_GUIDE`；當新專案 → 導回 `/wizard.html`
- [ ] 全套不退步

> ⚠️ 跨 task 暫態：本 task 完成後，`PAGE_SIMILARITY_DECISION` 的「當版本」會導向 `PAGE_VERSION_GUIDE`，
> 但該頁的 render 內容在 **Task 06** 才實作。在 Task 06 完成前，點「當版本」會看到空白 wizard-card
> （renderPage switch 無 default、不會崩）。這是增量實作的正常暫態，Task 06 補完即正常。
