# 步驟 10–11 — index.html 接線 + 舊檔清除

## 前置條件

**必須先確認：**
- [ ] 步驟 0–9 全部完成
- [ ] `npm run test:coverage` 全部通過，100% 覆蓋率
- [ ] 啟動伺服器，舊 `app.js` 版本功能正常（作為基準）

---

## 步驟 10 — index.html 修改

### 變更內容

```html
<!-- 移除 -->
<script src="./app.js"></script>

<!-- 改為 -->
<script type="module" src="./js/app.js"></script>
```

### 約束

- `<script src="./lib/cytoscape.min.js">` 必須在 module script **之前**（現有順序正確，勿動）
- `type="module"` 的腳本是 deferred，DOM 載入完成後才執行 → `dom.js` 頂層的 `getElementById` 可安全執行

### 完整修改後的 script 區塊

```html
<script src="./lib/cytoscape.min.js"></script>
<!-- （此行之間可以有其他非模組 script，但通常不需要） -->
<script type="module" src="./js/app.js"></script>
```

---

## 驗證流程（步驟 10 完成後）

1. 啟動伺服器：`the-door ui "C:\Users\Ric\Desktop\test-targets\the-door-v105" --no-browser --port 8765`
2. 開啟瀏覽器，`Ctrl+Shift+R`（hard refresh）
3. 開啟 DevTools Console，確認無 JS 錯誤
4. 逐一驗證以下功能：

| 功能 | 預期結果 |
|---|---|
| 頁面載入 | 頂部標題、summary text 顯示 |
| 模式切換（差異/舊版/新版） | 按鈕 active 狀態切換，list 內容更新 |
| 功能卡片點擊 | detail panel 顯示對應內容 |
| 關聯圖開關 | 圖形抽屜滑入/滑出 |
| 重新分析 modal | 開關正常，路徑空白時顯示錯誤 |
| 版本選擇器（若有） | A/B 下拉切換更新 count badge |
| L1→L2 進入 | 點擊「進入 L2」後切換，麵包屑出現 |
| 麵包屑返回 | 點擊 L1 連結回到 L1 層 |
| 心智圖按鈕 | sessionStorage 有資料，popup 開啟 |
| count badge | 差異模式下 新增/移除/修改 數字正確 |

---

## 步驟 11 — 刪除舊 viewer/app.js

**前置條件：** 步驟 10 驗證全部通過。

```
viewer/app.js  ← 刪除此檔
```

**注意**：此動作不可逆（git 中仍有歷史記錄，但需要 git restore 才能還原）。確認步驟 10 全部 OK 再刪。

---

## 最終確認

- [ ] `npm run test:coverage` — 全部 100% 通過
- [ ] 瀏覽器無 Console 錯誤
- [ ] 所有功能驗證項目打勾
- [ ] 舊 `viewer/app.js` 已刪除
- [ ] `git status` 確認無多餘未追蹤檔案
