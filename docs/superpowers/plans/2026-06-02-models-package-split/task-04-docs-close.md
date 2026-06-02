# Task 04: 收尾 — 更新 backlog 進度 + spec 狀態

**目的**：把 backlog 的 T2 進度勾選為已實作、把 spec 狀態改為已實作，記錄收斂結果。

**Files:**
- Modify: `docs/refactoring/2026-05-31-refactoring-backlog.md`
- Modify: `docs/superpowers/specs/2026-06-02-models-package-split-design.md`

**前置**：Task 01–03 已 commit、全套件綠。注意 docs 在**外層** repo root 的 `docs/`（非內層 `the_door/`）。

---

- [ ] **Step 1: 更新 backlog 進度**

編輯 `docs/refactoring/2026-05-31-refactoring-backlog.md` 第 92 行，把：
```
- [ ] T2 models.py 套件化（需獨立 spec；size 依據 2026-06-02 已重驗）
```
改為：
```
- [x] T2 models.py 套件化 — 已實作（1004 行單檔 → models/ 套件 10 子模組 + 門面 re-export；CRP 拆出 snapshot；欄位零變更、消費端零改；DSM 不變量測試守住 DAG+邊集+SDP）
```
（若該行實際文字與此處不符，先 Read 該檔確認第 92 行內容，找到 T2 進度勾選列再依此精神更新；不得捏造。）

- [ ] **Step 2: 更新 spec 狀態**

編輯 `docs/superpowers/specs/2026-06-02-models-package-split-design.md` 標頭，把：
```
> **日期**：2026-06-02　**狀態**：設計核准、待寫 plan
```
改為：
```
> **日期**：2026-06-02　**狀態**：已實作（plan: docs/superpowers/plans/2026-06-02-models-package-split/）
```

- [ ] **Step 3: Commit**

```
git add docs/refactoring/2026-05-31-refactoring-backlog.md docs/superpowers/specs/2026-06-02-models-package-split-design.md
git commit -m "docs: mark T2 (models package split) implemented"
```

- [ ] **Step 4: 收尾回報**

回報：
- `models.py`（1004 行 / 79 型別）→ `models/` 套件（10 子模組 + 門面）；
- import-equivalence 安全網（3 測）+ DSM 不變量（5 測）全綠、欄位級 AST 等價驗證通過（79 類別逐欄位相同）；
- 全套件零回歸、覆蓋不降；改動面僅 `models.py`→`models/` + 2 新測試檔，其他 `.py` 零修改；
- 依賴脊椎 `vulnerability→snapshot→diff→pipeline`、SDP 零違規。

接著等使用者決定 merge（依偏好：本地 merge、不主動 push）。
