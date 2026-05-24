# Plan F — Frontend CSS（Task 09）

> **執行分類 F**：前端視覺修正
> **依賴：** 無（可任意時機執行）
> **前端路徑：** `docs/frontend-local-version-viewer/viewer/`
> **Worktree：** `loving-sinoussi-20dcd0`

---

## Task 09 — R9：關聯圖上下間距加長

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/styles.css`

- [ ] **Step 1：修改 CSS**

在 `styles.css` 找到：

```css
.gv-grid {
  position: relative;
  display: grid;
  grid-template-columns: repeat(5, minmax(160px, 1fr));
  grid-auto-rows: 90px;
  gap: 20px;
  max-width: 1100px;
  margin: 0 auto;
}
```

改為：

```css
.gv-grid {
  position: relative;
  display: grid;
  grid-template-columns: repeat(5, minmax(160px, 1fr));
  grid-auto-rows: 90px;
  column-gap: 20px;
  row-gap: 48px;
  max-width: 1100px;
  margin: 0 auto;
}
```

- [ ] **Step 2：視覺驗收**

```
the-door ui C:\Users\Ric\Desktop\test-targets\the-door-v105 --no-browser --port 8765
```

開啟 http://localhost:8765，切換到關聯圖（L1 graph）。

**Pass 標準：** 有邊相連的兩個節點之間，連線不被相鄰節點的卡片遮蓋。

- [ ] **Step 3：Commit**

```
git add docs/frontend-local-version-viewer/viewer/styles.css
git commit -m "fix(viewer): increase relation graph row gap 20px→48px"
```
