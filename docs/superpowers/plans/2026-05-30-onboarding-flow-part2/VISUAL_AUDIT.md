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
