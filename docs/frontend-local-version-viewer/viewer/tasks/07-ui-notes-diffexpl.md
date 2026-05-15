# 步驟 7 — ui-notes.js + ui-diff-explanation.js

## 概覽

| 模組 | 來源行號（app.js） | 預估行數 | 依賴 |
|---|---|---|---|
| `js/ui-notes.js` | 2337–2479 | ~145 | `state.js`, `api.js` |
| `js/ui-diff-explanation.js` | 2481–2654 | ~175 | `state.js`, `api.js` |

兩個模組完全自包含，不依賴其他 UI 模組。

---

## js/ui-notes.js

### 匯出介面

```js
export function appendUserNotesSection(container, mode, versionA, versionB, featureId)
```

### 規格

在 container 底部插入 `.user-notes-section`，含：

**靜態結構：**
- `<h3>使用者備註</h3>`
- `.user-notes-form`：name input（maxLength=40）、comment textarea（maxLength=2000, rows=3）、submit button、error `<p>`（hidden）
- `.user-notes-history`（非同步填充）

**初始載入（非同步）：**
- GET `/api/notes?mode=<mode>&feature_id=<featureId>[&version_a=...][&version_b=...]`
- 成功且有 notes → 插入 `.user-notes-history-label` + 各 `<details class="user-note">`
- 失敗 → 靜默忽略（non-fatal）

**每個 note 的結構（`<details>`）：**
- `<summary>` = note.display_name
- `<p>` = note.comment
- `<p class="note-time">` = created_at 前 16 碼，T→空格

**Submit 行為：**
- name 空 → 顯示錯誤 "名稱不可為空。"，不 submit
- comment 空 → 顯示錯誤 "意見不可為空。"，不 submit
- 成功 → 清空 inputs，新 note 插入 history 頂部
- 失敗 → 顯示錯誤訊息

---

## js/ui-diff-explanation.js

### 匯出介面

```js
export function appendDiffExplanationSection(container, featureId)
```

### 規格

在 container 底部插入 `.diff-explanation-section`，含：

**靜態結構：**
- `<h3>差異推論</h3>`
- `.diff-explanation-content`（填充說明文字）
- `<button>生成差異推論</button>`（若無快取時顯示）

**初始載入（非同步）：**
- GET `/api/diff-explanation/<featureId>?<params>`（params 含 versionA、versionB、mode）
- 有快取結果 → 直接顯示文字，隱藏按鈕
- 無快取（404）→ 顯示按鈕

**點擊「生成差異推論」：**
- 按鈕 disabled，文字改為 "生成中…"
- POST `/api/diff-explanation/<featureId>/generate`（payload 含 versionA、versionB、mode）
- 成功 → 顯示結果，隱藏按鈕
- 失敗 → 按鈕 re-enable，顯示錯誤

---

## 測試規格

### tests/ui-notes.test.js

| 測試案例 | 驗證 |
|---|---|
| appendUserNotesSection — 結構 | 含 h3、name input、textarea、submit button |
| appendUserNotesSection — submit（name 空） | errorEl 顯示，fetch 未呼叫 |
| appendUserNotesSection — submit（comment 空） | errorEl 顯示，fetch 未呼叫 |
| appendUserNotesSection — submit 成功 | POST /api/notes，inputs 清空，note 插入 history |
| appendUserNotesSection — submit 失敗 | errorEl 顯示 network 錯誤 |
| 初始載入成功（有 notes） | history 含 .user-note details |
| 初始載入成功（無 notes） | history 空，無 heading |
| 初始載入失敗 | 靜默，不 throw，section 仍存在 |

### tests/ui-diff-explanation.test.js

| 測試案例 | 驗證 |
|---|---|
| appendDiffExplanationSection — 結構 | 含 h3、content div |
| 初始載入（有快取） | 顯示文字，不顯示生成按鈕 |
| 初始載入（404/無快取） | 顯示生成按鈕 |
| 點擊生成按鈕 | 按鈕 disabled，POST 呼叫 |
| 生成成功 | 顯示結果，按鈕消失 |
| 生成失敗 | 按鈕 re-enable，錯誤訊息顯示 |

---

## TDD 步驟（每個模組）

1. **RED**：寫測試，確認失敗
2. **GREEN**：建立模組，最小實作
3. **REFACTOR**：整理

## 驗證檢查清單

- [ ] `npm test tests/ui-notes.test.js` — 全部通過
- [ ] `npm test tests/ui-diff-explanation.test.js` — 全部通過
- [ ] 啟動伺服器，detail panel 底部顯示備註與差異推論區塊
