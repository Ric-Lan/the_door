# Task 7: 前端 — Project Switcher 下拉選單

**Depends on:** Task 6 (GET /api/group 存在)

**Files:**
- Create: `docs/frontend-local-version-viewer/viewer/js/project-switcher.js`
- Modify: `docs/frontend-local-version-viewer/viewer/js/api.js`
- Modify: `docs/frontend-local-version-viewer/viewer/js/app.js`
- Modify: `docs/frontend-local-version-viewer/viewer/index.html`
- Create: `docs/frontend-local-version-viewer/viewer/tests/project-switcher.test.js`

**工作目錄**：`docs/frontend-local-version-viewer/viewer/`（npm 指令在此執行）

---

- [ ] **Step 1: 新建失敗測試 `docs/frontend-local-version-viewer/viewer/tests/project-switcher.test.js`**

```javascript
import { describe, it, expect } from "vitest";
import {
  buildSwitcherItems,
  toastMessage,
  shouldShowSwitcher,
} from "../js/project-switcher.js";

describe("buildSwitcherItems", () => {
  it("returns empty array when group is null", () => {
    expect(buildSwitcherItems(null)).toEqual([]);
  });

  it("returns all members with isCurrent flag", () => {
    const group = {
      members: [
        { id: "001", name: "ms-ts",    path: "/a", is_current: true },
        { id: "002", name: "color-go", path: "/b", is_current: false },
      ],
    };
    const items = buildSwitcherItems(group);
    expect(items).toHaveLength(2);
    expect(items[0].isCurrent).toBe(true);
    expect(items[1].isCurrent).toBe(false);
    expect(items[0].name).toBe("ms-ts");
  });
});

describe("toastMessage", () => {
  it("returns CLI command string for the member path", () => {
    const member = { name: "color-go", path: "C:/test-targets/color-go" };
    const msg = toastMessage(member);
    expect(msg).toContain("the-door ui");
    expect(msg).toContain("C:/test-targets/color-go");
  });
});

describe("shouldShowSwitcher", () => {
  it("returns false when group is null", () => {
    expect(shouldShowSwitcher(null)).toBe(false);
  });

  it("returns false when group has fewer than 2 members", () => {
    expect(shouldShowSwitcher({ members: [{ id: "001" }] })).toBe(false);
  });

  it("returns true when group has 2 or more members", () => {
    expect(shouldShowSwitcher({ members: [{ id: "001" }, { id: "002" }] })).toBe(true);
  });
});
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/project-switcher.test.js 2>&1 | head -15
```

Expected: `Cannot find module '../js/project-switcher.js'`

- [ ] **Step 3: 新建 `docs/frontend-local-version-viewer/viewer/js/project-switcher.js`**

```javascript
/**
 * Project switcher — pure functions for the group-aware project dropdown.
 *
 * Data shape expected from GET /api/group:
 *   { group: { members: [{id, name, path, is_current}] } | null }
 */

/**
 * Map API group.members into switcher item objects.
 * @param {object|null} group
 * @returns {{ id: string, name: string, path: string, isCurrent: boolean }[]}
 */
export function buildSwitcherItems(group) {
  if (!group || !Array.isArray(group.members)) return [];
  return group.members.map((m) => ({
    id: m.id,
    name: m.name,
    path: m.path,
    isCurrent: m.is_current === true,
  }));
}

/**
 * Return true if the switcher should be rendered (group with ≥2 members).
 * @param {object|null} group
 * @returns {boolean}
 */
export function shouldShowSwitcher(group) {
  return !!(group && Array.isArray(group.members) && group.members.length >= 2);
}

/**
 * Build the inline toast message instructing the user how to open a project.
 * @param {{ name: string, path: string }} member
 * @returns {string}
 */
export function toastMessage(member) {
  return `請在終端機執行：the-door ui ${member.path}`;
}

/**
 * Render the project switcher dropdown into a <select> container element.
 * @param {HTMLSelectElement} container
 * @param {{ id, name, path, isCurrent }[]} items
 * @param {(member: {name:string, path:string}) => void} onSelect
 */
export function renderSwitcherDropdown(container, items, onSelect) {
  container.innerHTML = "";
  items.forEach((item) => {
    const opt = document.createElement("option");
    opt.value = item.path;
    opt.textContent = (item.isCurrent ? "✓ " : "  ") + item.name;
    opt.selected = item.isCurrent;
    opt.dataset.name = item.name;
    container.appendChild(opt);
  });
  container.onchange = (e) => {
    const path = e.target.value;
    const name = e.target.selectedOptions[0]?.dataset.name ?? path;
    if (items.find((i) => i.path === path)?.isCurrent) return;
    onSelect({ name, path });
  };
}

/**
 * Show an inline toast below the topbar for 3 seconds.
 * Creates or reuses #project-switcher-toast element.
 * @param {string} message
 */
export function showToast(message) {
  let toast = document.getElementById("project-switcher-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "project-switcher-toast";
    toast.style.cssText = [
      "position:fixed", "top:48px", "left:50%", "transform:translateX(-50%)",
      "background:#1e1e2e", "color:#cdd6f4", "padding:8px 16px",
      "border-radius:6px", "font-size:13px", "z-index:9999",
      "box-shadow:0 2px 8px rgba(0,0,0,0.4)", "font-family:monospace",
    ].join(";");
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.style.display = "block";
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => { toast.style.display = "none"; }, 3000);
}
```

- [ ] **Step 4: 確認純函式測試通過**

```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/project-switcher.test.js 2>&1 | tail -10
```

Expected: 全部 PASSED

- [ ] **Step 5: 在 `api.js` 末尾加 `fetchGroup()`**

```javascript
export async function fetchGroup() {
  const res = await fetch(`${API_BASE}/api/group`, { cache: "no-store" });
  return res.json();
}
```

- [ ] **Step 6: 修改 `app.js` — 加 imports 和初始化**

在 `app.js` 的 import 區塊末尾加：

```javascript
import { fetchGroup } from "./api.js";
import { shouldShowSwitcher, buildSwitcherItems, renderSwitcherDropdown, showToast, toastMessage } from "./project-switcher.js";
```

在頁面初始化函式（`init()` 或 `DOMContentLoaded` handler）裡，在現有 fetchProjectStatus / fetchSnapshots 呼叫之後加：

```javascript
try {
  const groupData = await fetchGroup();
  initProjectSwitcher(groupData?.group ?? null);
} catch (_) {
  // group API unavailable — switcher stays hidden
}
```

加入 `initProjectSwitcher` 函式定義：

```javascript
function initProjectSwitcher(group) {
  const container = document.getElementById("project-switcher");
  if (!container) return;
  if (!shouldShowSwitcher(group)) {
    container.style.display = "none";
    return;
  }
  container.style.display = "";
  const items = buildSwitcherItems(group);
  renderSwitcherDropdown(container, items, (member) => {
    showToast(toastMessage(member));
  });
}
```

- [ ] **Step 7: 修改 `index.html` — 在 version-selector-bar 之前插入 project-switcher**

在 `docs/frontend-local-version-viewer/viewer/index.html` 找到：

```html
        <!-- 版本選擇器（多 snapshot 時顯示） -->
        <div id="version-selector-bar" class="version-selector-bar">
```

在其**前面**插入（同縮排層級）：

```html
        <!-- 專案切換器（同群成員時顯示） -->
        <select id="project-switcher" class="vsb-select" style="display:none" title="切換專案"></select>

```

完成後該區段應為：

```html
        <!-- 專案切換器（同群成員時顯示） -->
        <select id="project-switcher" class="vsb-select" style="display:none" title="切換專案"></select>

        <!-- 版本選擇器（多 snapshot 時顯示） -->
        <div id="version-selector-bar" class="version-selector-bar">
```

- [ ] **Step 8: 確認前端測試全套通過**

```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run 2>&1 | tail -15
```

Expected: 全部 PASSED（含既有 version_picker / ui-notes 等測試）

- [ ] **Step 9: Commit**

```bash
cd docs/frontend-local-version-viewer/viewer && git add js/project-switcher.js js/api.js js/app.js index.html tests/project-switcher.test.js
git commit -m "feat(viewer): add project-switcher dropdown with inline toast for group members"
```
