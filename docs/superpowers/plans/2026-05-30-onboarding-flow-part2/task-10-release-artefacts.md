# Task 10 — CHANGELOG v1.4.7 + bilingual README + manual visual audit

**Goal:** 發版 artefacts + 對照 `part2-prototype/shots/` 完成手動視覺驗收。

**Dependencies:** tasks 1a-9 全部 ship。

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `README.md`（中文）
- Modify: `README.en.md`（英文，若存在；若不存在則只改中文版）
- Create: `docs/superpowers/plans/2026-05-30-onboarding-flow-part2/VISUAL_AUDIT.md`（勾選驗收清單）

---

- [ ] **Step 1: 確認所有前序 task 已 merge / 測試全綠**

```bash
cd "C:\Users\Ric\Desktop\the_door\.claude\worktrees\eager-nightingale-3b8739"
pytest the_door/tests/ -x --tb=short
cd docs/frontend-local-version-viewer/viewer && npm test
```
Expected: 全綠（1289 + new Python tests / 731 + new JS tests）。如有失敗，stop 並回到對應 task 修。

- [ ] **Step 2: 撰寫 CHANGELOG entry v1.4.7**

Modify `CHANGELOG.md` — 在最上方（最新 entry 位置）插入：

```markdown
## v1.4.7 — 2026-05-30

### Added
- **Onboarding flow Part 2**: 雙欄精靈外殼（左門外暗面 + 右門內明亮）+ 進度視覺化（phasebar + steplist + 即時檔案 feed）+ 跨頁穿門轉場（spec §0-§9）
- **後端 progress 契約**: `UpdateJob.progress` 欄位（`files_done` / `files_total` / `current_file` / `current_root`）由新 `ProgressReporter` 抽象從 `ASTExtractor` / `BatchReader` 內部 file loop 寫入；`handle_get_update_status` payload 暴露給前端
- **handle_post_analyze adapter**: 精靈 analyze 走 `run_analyze_pipeline` 經 per-request closure 映射為 `[步驟 N/6]` 訊息與 modal `PipelineOrchestrator.run` 對齊（spec §5.1）
- **Viewer modal 進度設計一致化**: `ui-modal.js renderPipelineProgress` 改用 phasebar/steplist/feed（與精靈 PROGRESS 同設計）
- **「上一步」鈕**: PAGE_SETUP / PAGE_LABEL / PAGE_CONFIRM 三處新增 `.wizard-btn-ghost`；通用化 `{ type: 'BACK', target }` action 支援 analyze 與 update 兩條路徑（spec §4.3）
- **`errorOriginPage` state 欄位**: PAGE_ERROR rail stage 由 origin 推回，避免 STATUS_ERROR 在 LOADING 階段被誤顯示為「分析中」（spec §4.1）

### Changed
- `styles.css` 加 11 個 Part 2 token（terminal / radius / rail 系列）+ 共用進度區（`/* Progress (shared) */`）
- `wizard.css` 加 shell + rail + screen 動畫 + mode-note + ghost button + agent-* + transient；字體 token (`--font-sans` / `--font-mono`) 限定 `.wizard-shell` 後代 scope（不入 styles.css :root 避免 7 處 fallback regression）
- `wizard.html` 移除 `.wizard-root` wrapper（雙欄自滿版）

### Removed
- `styles.css:846-870` 舊 `.step-*` chips 規則（已被 `.wizard-phasebar` / `.wizard-sl-row*` 取代）

### Tests
- 1a/1b: +18 Python tests（progress_reporter / adapter / payload / e2e）
- 2-9: +35 JS tests（shell / phasebar / feed / back / error-origin / transition）
- coverage 維持 100%
```

- [ ] **Step 3: 更新雙語 README core capabilities table**

Modify `README.md`. 找到「核心能力」表格（與 v1.4.6 加 row 的同位置），在表尾加：

```markdown
| **Onboarding 雙欄精靈** | 視覺化的「開門→分析→進入 Viewer」三段體驗，含即時 file-level 進度 feed | v1.4.7 |
```

如 `README.en.md` 存在，同位置加英文 row：
```markdown
| **Dual-pane onboarding wizard** | Door-metaphor entry flow with real-time file-level progress feed | v1.4.7 |
```

- [ ] **Step 4: 啟動本地 server 做視覺驗收**

```bash
the-door ui "C:\Users\Ric\Desktop\test-targets\the-door-v105" --no-browser --port 8765
```
（或任一既有 test target；若需要乾淨空專案，臨時 `mkdir /tmp/empty-proj && cd /tmp/empty-proj && git init`）

開瀏覽器到 http://localhost:8765/wizard.html。

- [ ] **Step 5: 建立 + 完成視覺驗收 checklist**

Path: `docs/superpowers/plans/2026-05-30-onboarding-flow-part2/VISUAL_AUDIT.md`

```markdown
# Onboarding Flow Part 2 — Visual Audit Checklist

對照 `docs/frontend-local-version-viewer/part2-prototype/shots/` 五張金標準截圖逐項確認。

## A. PAGE_ACTION（對照 `action.png`）
- [ ] 雙欄結構：左 rail 暗 teal，右 content 白底
- [ ] Rail brand「The Door / 門 · 啟動精靈」+ door SVG（門關閉、door-light off）
- [ ] Rail 6-step stepper：step 1「選擇操作」.active，其他 .pending
- [ ] Rail foot「CODE → FUNCTIONAL LANGUAGE」
- [ ] Content 區 `.wizard-eyebrow`「步驟 1 / 開始」顯示
- [ ] `.wizard-mode-note` 依 API key 狀態顯示 teal (api) 或 amber (agent) 變體
- [ ] FIX-1 既有 option 卡完整顯示

## B. PAGE_SETUP → PAGE_LABEL → PAGE_CONFIRM（對照 `01-flow.png` ~ `04-flow.png`）
- [ ] 每頁 rail 門隨 stage 開啟（stage 1: 15.6° → stage 3: 46.8°）
- [ ] stepper fill 線高度遞增（20% / 40% / 60%）
- [ ] 當前 step `.active`（白圓 + 光暈）、已過 step `.done`（綠 ✓）
- [ ] 三頁底部均有「← 上一步」`.wizard-btn-ghost`
- [ ] PAGE_CONFIRM badge 與入口 mode-note 配色一致

## C. PROGRESS（對照 `05-flow.png`）
- [ ] Rail 門半開（stage 4，62.4°），stepper fill 80%
- [ ] phasebar 3 段：explore / analyze / report，當前 bucket `.active` indeterminate 動畫
- [ ] steplist 完整 6 步顯示，狀態 icon 正確（✓ / ✗ / ⊘ / spinner / ○）
- [ ] 即時 feed `.wizard-prog-live` 顯示真實 `current_file`（精靈 analyze 模式下含 `[new]` 前綴）
- [ ] 後端 `progress` 為 null 時 `.wizard-prog-live` 不顯示

## D. PROGRESS Agent 模式（對照 `action.png` agent 變體）
- [ ] `.wizard-agent-params` 終端塊 + 可運作的「複製」鈕

## E. PAGE_ERROR
- [ ] STATUS_ERROR 觸發時 rail stage 退回 0（不顯示「分析中」）
- [ ] SUBMIT_ERROR from PAGE_CONFIRM → rail stage 3
- [ ] POLL_FAIL ≥3 from PROGRESS → rail stage 4

## F. 跨頁穿門轉場（對照 `fresh.png`）
- [ ] 完成 → redirect 前 shell 套 `.leaving`、動畫淡出（scale 1.06 + opacity 0 + brightness 1.25）
- [ ] index.html `.onboarding-card` 載入時套 viewerIn（scale 0.99 → 1，無 opacity flicker）

## G. Viewer modal 一致化
- [ ] 開首頁 → 「重新分析」modal → 看到 phasebar + steplist + 即時 feed（與精靈 PROGRESS 完全相同視覺）
- [ ] 舊 `.step-*` chips 已消失

## H. 靜態紀律檢查
- [ ] `grep -n "opacity:\s*0" wizard.css styles.css` 命中僅在 `.wizard-door-light` transition（非 @keyframes）
- [ ] `grep -n "[0-9]rem" wizard.css` 命中 0
- [ ] `grep -n "\.step-item\s*{\|\.step-completed\s*{" styles.css` 命中 0

## 完成狀態
- [ ] 所有項目勾選完畢
- [ ] 截圖留存（若有差異）：路徑記錄於本檔
```

逐項手動勾選；任何 fail 回對應 task 修。

- [ ] **Step 6: Commit release artefacts**

```bash
git add CHANGELOG.md README.md README.en.md \
        docs/superpowers/plans/2026-05-30-onboarding-flow-part2/VISUAL_AUDIT.md
git commit -m "docs(release): v1.4.7 Onboarding Flow Part 2 CHANGELOG + READMEs

CHANGELOG v1.4.7 entry 含 Added / Changed / Removed / Tests 四段。
雙語 README core capabilities 表加「Onboarding 雙欄精靈」row。
新增 VISUAL_AUDIT.md 對照 part2-prototype/shots/ 8 大類驗收項。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

- [ ] **Step 7: Tag v1.4.7（僅在 main 與所有 task 都已 merge 進 main 後）**

如目前在 worktree、尚未 merge 到 main：

```bash
# 先回 main / ff-merge worktree（依使用者偏好決定時機）
git switch main
git merge --ff-only claude/eager-nightingale-3b8739
git tag v1.4.7
git push origin main v1.4.7
```

如直接在 main 開發：

```bash
git tag v1.4.7
git push origin main v1.4.7
```

> 注意：tag 動作需使用者明示授權，agent 不主動 push tag。
