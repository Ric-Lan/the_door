# Task 08 — B 路：翻譯與否分岔頁 → Viewer

**內容分類：** B 分支「當版本」終站。出 LLM 翻譯指令（選跑）+ 說明 + 進 Viewer。含全流程目視驗收。

**設計來源：** spec §4.8、§3.2、§10.11。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`（`renderPage` 加 `PAGE_TRANSLATE_CHOICE`）
- Test: `docs/frontend-local-version-viewer/viewer/tests/wizard-update-flow.test.js`（append）

> 本頁無新 reducer case——「進 Viewer」是 render 層的 redirect side effect（用既有 `redirectFn`）。

---

- [ ] **Step 1: 寫 render 失敗測試**

append：

```javascript
describe('PAGE_TRANSLATE_CHOICE render', () => {
  function render(redirectFn = () => {}) {
    const c = document.createElement('div');
    renderPage(c, { ...getInitialState(), page: 'PAGE_TRANSLATE_CHOICE', updateFlow: 'new_data',
      newDataPath: '/d/v2', baselineRef: 'v1.2.2', detectedRef: 'v1.3.0' },
      () => {}, redirectFn, {});
    return c;
  }
  it('shows a translate instruction card referencing the new version', () => {
    const c = render();
    const cmd = c.querySelector('[data-translate-cmd]');
    expect(cmd).not.toBeNull();
    expect(cmd.textContent).toContain('v1.3.0');
  });
  it('explains both paths still show the diff', () => {
    const c = render();
    expect(c.textContent).toContain('差異');
  });
  it('enter-viewer button redirects to /index.html', () => {
    let redirected = null;
    const c = render((u) => { redirected = u; });
    c.querySelector('[data-enter-viewer]').click();
    expect(redirected).toBe('/index.html');
  });
});
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
cd docs/frontend-local-version-viewer/viewer
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "PAGE_TRANSLATE_CHOICE render" --reporter=verbose 2>&1 | tail -15
```
Expected: FAIL。

- [ ] **Step 3: 實作 `PAGE_TRANSLATE_CHOICE` render case**

在 `renderPage` switch（`PAGE_VERSION_DETECT` case 之後）插入：

```javascript
    case 'PAGE_TRANSLATE_CHOICE': {
      const ref = state.detectedRef;
      const translateCmd = `# 對新版本「${ref}」重跑 L1 自然語言解析：\n` +
        `extract_structure(codebase_path="${state.newDataPath}")  → 產生每個功能的自然語言 label/description →\n` +
        `snapshot_write(codebase_path="${state.newDataPath}", l1_features=[...], label="${ref}", inherit_from="${state.baselineRef}")`;
      wrap.innerHTML = `
        <p class="wizard-eyebrow eyebrow">步驟 / 進入 Viewer</p>
        <h2>要先跑自然語言翻譯嗎？</h2>
        <p class="wizard-subtitle lede">兩條路都能在 Viewer 看到差異項目。差別只在功能名稱好不好讀。</p>
        <div class="wizard-mode-note mode-note">
          <span>跑翻譯 → Viewer 顯示<strong>自然語言</strong>差異；不跑直接進 → 仍看得到<strong>差異拓樸</strong>，
          但功能名稱是技術性短名、沒有翻譯。</span>
        </div>
        <div class="wizard-field field">
          <label>（選跑）自然語言翻譯指令</label>
          <pre data-translate-cmd>${translateCmd}</pre>
        </div>
        <div class="actions">
          <button class="wizard-btn-ghost btn btn-ghost" data-back="PAGE_VERSION_DETECT">← 上一步</button>
          <span class="spacer"></span>
          <button class="wizard-btn-primary btn btn-primary" data-enter-viewer>進入 Viewer ${I.arrow}</button>
        </div>
      `;
      wrap.querySelector('[data-enter-viewer]').addEventListener('click',
        () => redirectWithTransition('/index.html', redirectFn));
      bindBack(wrap);
      break;
    }
```

> `redirectWithTransition` 是既有 helper（檔案頂端 export），既有 view 動作就用它導頁帶轉場。
> 它第二參數接 `redirectFn`，測試傳入的 `redirectFn` 會被呼叫並收到 `/index.html`。

- [ ] **Step 4: 跑測試確認通過**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "PAGE_TRANSLATE_CHOICE render" --reporter=verbose 2>&1 | tail -12
```
Expected: PASS。

> 註：`redirectWithTransition` 內部用 `setTimeout` 620ms 才呼叫 `redirectFn`。若測試未等待會收不到。
> 對策：測試改用 `vi.useFakeTimers()` + `vi.runAllTimers()`，或把斷言包進 `await new Promise(r => setTimeout(r, 650))`。
> 若嫌麻煩，可改為直接斷言 `redirectWithTransition` 有被觸發的副作用（`.wizard-shell.leaving` class）——
> 但既有測試慣例是驗 redirectFn 收到的 URL，建議用 fake timers。實作測試時擇一，確保 GREEN。

- [ ] **Step 5: 全套驗收**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js --reporter=verbose 2>&1 | tail -15
./node_modules/.bin/vitest.cmd run 2>&1 | tail -8
```
Expected: 新檔全綠；全套維持 **853 passed + 8 pre-existing failures**（數字不增不減）。

- [ ] **Step 6: 目視驗收（全流程）**

確認 editable install 指向本 worktree：
```bash
pip show the-door | grep Editable
# 不對就：pip install -e ./the_door
```
啟動：
```
the-door ui "C:\Users\Ric\Desktop\test-targets\the-door-v105" --no-browser --port 8765
```
開 http://localhost:8765/wizard.html，走完整兩條分支：
- **A 路**：更新分析 → 分岔 → 重生 → 選版本 → 出重生指令卡
- **B 路**：更新分析 → 分岔 → 引入新資料 → 填路徑+選 baseline → 結構比對指令卡 → 判讀頁
  → 當版本 → 建立快照指令卡 → 偵測頁 → 翻譯與否頁 → 進 Viewer
- **B 路新專案出口**：判讀頁 → 當新專案 → 導回首頁

- [ ] **Step 7: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js docs/frontend-local-version-viewer/viewer/tests/wizard-update-flow.test.js
git commit -m "feat(wizard): translate-or-direct choice page; enter viewer (B branch terminal)"
```

## Done when
- [ ] 翻譯指令卡引用新版本識別、說明兩條路都看得到差異
- [ ] 「進入 Viewer」導 `/index.html`
- [ ] 全套不退步
- [ ] 目視走完 A + B 兩條分支 + 新專案出口
