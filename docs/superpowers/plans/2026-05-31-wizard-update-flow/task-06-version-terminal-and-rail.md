# Task 06 — B 路：版本指令終結頁 + rail 階段 + 收尾

**內容分類：** B 分支終點頁（出 `update --from-snapshot` 指令卡）+ rail 階段對應 + 全套驗收。

**設計來源：** spec §4.6、§7（B 路跨資料夾終結於指令卡）、§8（rail 階段）。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`（`renderPage` 加 `PAGE_VERSION_GUIDE`；`STAGE` map 補新頁）
- Test: `docs/frontend-local-version-viewer/viewer/tests/wizard-update-flow.test.js`（append）

---

- [ ] **Step 1: 寫版本終結頁 render 失敗測試**

append：

```javascript
describe('PAGE_VERSION_GUIDE render', () => {
  function render(state) {
    const c = document.createElement('div');
    renderPage(c, state, () => {}, () => {}, {});
    return c;
  }
  it('shows update --from-snapshot command with baseline and new path', () => {
    const c = render({ ...getInitialState(), page: 'PAGE_VERSION_GUIDE',
      updateFlow: 'new_data', newDataPath: '/d/v2', baselineRef: 'v1.2.2' });
    const cmd = c.querySelector('[data-version-cmd]');
    expect(cmd).not.toBeNull();
    expect(cmd.textContent).toContain('--from-snapshot v1.2.2');
    expect(cmd.textContent).toContain('/d/v2');
  });
  it('typing a new label updates the command text live', () => {
    const c = render({ ...getInitialState(), page: 'PAGE_VERSION_GUIDE',
      updateFlow: 'new_data', newDataPath: '/d/v2', baselineRef: 'v1.2.2' });
    const input = c.querySelector('[data-version-label]');
    input.value = 'v1.3.0';
    input.dispatchEvent(new Event('input'));
    expect(c.querySelector('[data-version-cmd]').textContent).toContain('--label v1.3.0');
  });
});
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
cd docs/frontend-local-version-viewer/viewer
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "PAGE_VERSION_GUIDE render" --reporter=verbose 2>&1 | tail -15
```
Expected: FAIL。

- [ ] **Step 3: 實作 `PAGE_VERSION_GUIDE` render case**

在 `renderPage` switch（`PAGE_SIMILARITY_DECISION` case 之後）插入：

```javascript
    case 'PAGE_VERSION_GUIDE': {
      const buildCmd = (label) => {
        const labelPart = label ? ` --label ${label}` : '';
        return `the-door update --from-snapshot ${state.baselineRef}${labelPart} ${state.newDataPath}`;
      };
      wrap.innerHTML = `
        <p class="wizard-eyebrow eyebrow">步驟 / 版本差異</p>
        <h2>交付差異解析指令</h2>
        <p class="wizard-subtitle lede">把下面指令交給你的 agent / 自己執行，對基準版本做版本差異解析。可選填新版本標籤。</p>
        <div class="wizard-field field">
          <label>新版本標籤（選填）</label>
          <input type="text" data-version-label placeholder="v1.3.0">
        </div>
        <div class="wizard-field field">
          <label>指令</label>
          <pre data-version-cmd>${buildCmd('')}</pre>
        </div>
        <div class="actions">
          <button class="wizard-btn-ghost btn btn-ghost" data-back="PAGE_SIMILARITY_DECISION">← 上一步</button>
        </div>
      `;
      const labelInput = wrap.querySelector('[data-version-label]');
      const cmdPre = wrap.querySelector('[data-version-cmd]');
      labelInput.addEventListener('input', e => { cmdPre.textContent = buildCmd(e.target.value.trim()); });
      bindBack(wrap);
      break;
    }
```

> 此頁無論有無 API key 都只出指令卡（spec §7：新資料在當前專案外，`/api/analyze` 指不到，不能自動執行）。

- [ ] **Step 4: 跑測試確認通過**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "PAGE_VERSION_GUIDE render" --reporter=verbose 2>&1 | tail -12
```
Expected: PASS。

- [ ] **Step 5: 寫 rail 階段對應失敗測試**

append：

```javascript
import { railStage } from '../js/ui-wizard.js';

describe('railStage for update-flow pages', () => {
  const mk = (page) => ({ ...getInitialState(), page });
  it('maps new pages to non-negative stages', () => {
    expect(railStage(mk('PAGE_UPDATE_MODE'))).toBe(0);
    expect(railStage(mk('PAGE_NEW_DATA'))).toBe(1);
    expect(railStage(mk('PAGE_SIMILARITY_GUIDE'))).toBe(2);
    expect(railStage(mk('PAGE_SIMILARITY_DECISION'))).toBe(3);
    expect(railStage(mk('PAGE_VERSION_GUIDE'))).toBe(4);
  });
});
```

- [ ] **Step 6: 跑測試確認失敗**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "railStage for update-flow" --reporter=verbose 2>&1 | tail -12
```
Expected: FAIL — 新頁不在 `STAGE` map，全回退 0。

- [ ] **Step 7: 補 `STAGE` map**

在 `js/ui-wizard.js` 的 `const STAGE = {...}` 物件補上新頁（沿用既有 6 個 label slot，不新增 label）：

```javascript
const STAGE = {
  LOADING: 0, PAGE_ACTION: 0, PAGE_UPDATE_MODE: 0, PAGE_REGEN_GUIDE: 0,
  PAGE_SETUP: 1, PAGE_NEW_DATA: 1,
  PAGE_LABEL: 2, PAGE_SIMILARITY_GUIDE: 2,
  PAGE_CONFIRM: 3, PAGE_SIMILARITY_DECISION: 3,
  SUBMITTING: 4, PROGRESS: 4, PAGE_VERSION_GUIDE: 4,
};
```

> `STAGE_LABELS` 不動（仍是既有 6 個）。新頁複用既有階段格，不擴充標籤——YAGNI。

- [ ] **Step 8: 跑測試確認通過 + 全套驗收**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js --reporter=verbose 2>&1 | tail -15
./node_modules/.bin/vitest.cmd run 2>&1 | tail -8
```
Expected: 新檔全綠；全套維持 **853 passed + 8 pre-existing failures**（數字不增不減）。

- [ ] **Step 9: 目視驗收**

確認 editable install 指向本 worktree：
```bash
pip show the-door | grep Editable
# 不對就：pip install -e ./the_door
```
啟動：
```
the-door ui "C:\Users\Ric\Desktop\test-targets\the-door-v105" --no-browser --port 8765
```
開 http://localhost:8765/wizard.html，走一遍：更新分析 → 分岔 → A 重生出指令卡；B 引入新資料 → 結構比對指令卡 → 判讀頁 → 當版本出 `update --from-snapshot` 指令卡 / 當新專案導回首頁。

- [ ] **Step 10: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js docs/frontend-local-version-viewer/viewer/tests/wizard-update-flow.test.js
git commit -m "feat(wizard): version-diff instruction terminal + rail stage mapping"
```

## Done when
- [ ] 版本終結頁出 `update --from-snapshot <baseline> <newpath>` 指令、label 即時更新
- [ ] 新頁 rail 階段對應正確
- [ ] 全套 853 passed 不退步
- [ ] 目視走完 A + B 兩條分支
