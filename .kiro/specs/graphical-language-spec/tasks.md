# Implementation Plan: Graphical Language Specification (Phase 0a 圖形語言規範)

## Overview

Phase 0a 的交付物全部是規範文件與 paper prototype（MD 純文字格式），不涉及程式碼實作。

交付物放在 `docs/phase-0a/` 目錄下，共 3 份文件：
1. `visual-language-spec.md` — 視覺語言規範（詞彙 + 疊加規則 + 層級切換 + MD 格式）
2. `paper-prototype.md` — Paper Prototype（含 Planted Doubts + 測試任務）
3. `doubt-path-concept.md` — 疑義路徑概念設計

## Tasks

- [x] 1. 建立視覺語言規範文件 (Visual Language Specification)
  - [x] 1.1 建立 L1 功能總覽層視覺詞彙
    - 建立 `docs/phase-0a/visual-language-spec.md` 文件
    - 定義 L1 節點形狀表：使用者觸發 `[U]` 圓角矩形、定時觸發 `[S]` 平行四邊形、事件觸發 `[E]` 菱形
    - 定義 L1 邊語意表：完成後觸發（實線）、依賴結果（虛線）、推斷關係（點線）
    - 定義 L1 群組機制：subgraph 聚集相關功能，功能語言標題，不暗示階層
    - 列出語言規則：禁止技術詞彙，提供正確/錯誤範例
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 1.2 建立 L1.5 結構概覽層視覺詞彙
    - 新增 L1.5 章節
    - 定義 L1.5 節點形狀表：結構區塊（圓角矩形）、基礎設施區塊（圓柱/subgraph）
    - 定義 L1.5 邊語意表：直接呼叫（實線）、事件通知（虛線）、資料流（粗線）
    - 定義節點標籤格式：`模組名稱 — 功能說明`，附正確/錯誤範例
    - 定義觸發機制人話標籤對照表（HTTP → 由使用者請求觸發 等）
    - 定義基礎設施收攏區塊與 L2 展開指示器 `[+]`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 1.3 建立 L2 功能連動圖層視覺詞彙
    - 新增 L2 章節
    - 定義 L2 節點形狀表：模組（圓角矩形）、子模組（較小圓角矩形）、外部依賴（平行四邊形）
    - 定義 L2 邊語意表：靜態呼叫（實線）、推斷關係（虛線 + `[推斷]` 標籤）、資料依賴（粗線）
    - 定義異常標示完整表格：5 種異常類型 × 填充色 × 符號 × classDef 名稱 × 嚴重程度
    - 定義多異常共存規則與所有異常 classDef 定義
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 1.4 建立 Diff 視覺符號與範圍邊界詞彙
    - 新增 Diff 章節：節點符號（+/−/~/≠）、邊符號、未變更降調、優先序、摘要面板、觸發方式標頭
    - 新增範圍邊界章節：✓/⚠/○ 三種狀態、角標徽章、摘要面板、疑義路徑入口
    - 列出所有 Diff + unchanged classDef 定義
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.7, 6.1, 6.2, 6.3, 6.4_

  - [x] 1.5 建立視覺疊加規則與層級切換規範
    - 新增視覺疊加規則章節：通道分配策略、Mermaid classDef 限制、異常與信心共存規則、多指標優先序、衝突解決規則、Diff + 範圍合併摘要
    - 新增層級切換章節：L1↔L1.5 Tab 切換、L2 點擊展開、展開指示器、當前層級指示器、完整導航場景
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 9.2, 9.5, 9.6, 9.7, 9.8_

  - [x] 1.6 建立完整視覺詞彙總表與 MD 格式規範
    - 新增完整詞彙總表：彙整所有層級的語意→視覺編碼映射，納入 Phase 0b 信心標示（引用不重新定義），確認無重複編碼
    - 新增 MD 純文字格式規範章節：節點/邊/狀態標記語法、層級結構表示法、Mermaid 對照表
    - 提供一個完整 MD 範例涵蓋 L1、L1.5、Diff 視圖
    - _Requirements: 9.1, 9.3, 9.4, 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 2. Checkpoint — 視覺語言規範審查
  - 確認 visual-language-spec.md 完整涵蓋 Req 1–6, 9, 10 的所有視覺元素
  - 確認所有視覺區分都有至少兩個獨立通道
  - 確認 Phase 0b 的 6 種信心標示 classDef 未被修改或覆蓋
  - 確認無兩個不同語意共用相同的（形狀 + 顏色 + 符號）組合

- [x] 3. 建立 Paper Prototype 文件 (Paper Prototype with Planted Doubts)
  - [x] 3.1 建立場景與 L1 + L1.5 視圖
    - 建立 `docs/phase-0a/paper-prototype.md` 文件
    - 設計虛構「線上商店」系統場景說明
    - 用 MD 純文字格式繪製 L1 功能總覽（8 個功能節點 + 關係）
    - 用 MD 純文字格式繪製 L1.5 結構概覽（5 個區塊 + 基礎設施 + 關係）
    - 包含 Planted Doubt #1：`[+] 批次匯出功能`（新增 + 超出範圍 ⚠）
    - _Requirements: 8.1, 8.2_

  - [x] 3.2 建立 L2 + Diff 視圖與疑義路徑場景
    - 用 MD 純文字格式繪製 L2 詳細視圖（訂單模組展開）
    - 包含 Planted Doubt #2：`inventory_checker` 標記 ⚠ 邏輯死路
    - 展示層級切換場景：L1 → Tab L1.5 → 點擊展開 L2 → 發現異常 → 收合
    - 用 MD 純文字格式繪製 Diff 視圖（v1.2.0 → v1.3.0），含所有變更類型與 Diff + 範圍合併摘要
    - 設計疑義路徑互動場景：使用者發現 ⚠ → 點擊 → 看到詳情 → 選擇下一步
    - 定義測試任務清單（4 項任務，10 分鐘時限）與 Go 標準（80% 通過率）
    - _Requirements: 4.5, 5.6, 7.7, 8.1, 8.3, 8.4, 8.5_

- [x] 4. 建立疑義路徑概念設計文件 (Doubt-Path Concept Design)
  - 建立 `docs/phase-0a/doubt-path-concept.md` 文件
  - 定義三階段流程：識別（Identify）→ 追蹤（Track）→ 解決（Resolve）
  - 定義識別階段入口點：異常標示（L2）、範圍邊界警告、信心標示（Phase 0b）
  - 定義追蹤階段 metadata：誰發現、何時、哪個節點、什麼類型、追蹤狀態
  - 定義概念層級狀態機流程圖（發現 → 調查 → 解釋/修復/升級）
  - 定義超時升級概念（具體規則在 Phase 3）
  - 明確標註：此為概念層級設計，完整狀態機在 Phase 3 實作
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [x] 5. Final Checkpoint — Phase 0a 全部交付物驗收
  - 確認以下 3 份文件全部完成：
    1. `docs/phase-0a/visual-language-spec.md` — 視覺語言規範
    2. `docs/phase-0a/paper-prototype.md` — Paper Prototype（含 Planted Doubts）
    3. `docs/phase-0a/doubt-path-concept.md` — 疑義路徑概念設計
  - 逐項檢查一致性清單：
    1. 視覺詞彙表無重複編碼
    2. 所有視覺區分有雙通道
    3. Phase 0b classDef 未被覆蓋
    4. Diff 符號 +/−/~/≠ 在 MD 和 Mermaid 中正確顯示
    5. 疑義路徑每個階段有明確「下一步」
    6. Paper prototype 含超出範圍 Planted Doubt
    7. Paper prototype 含異常標示 Planted Doubt
  - 確認所有 10 項需求（Req 1–10）都被涵蓋

## Notes

- Phase 0a 的交付物全部是 Markdown 文件，不涉及 Python 程式碼
- Property-based testing 不適用，測試策略為人工審查 + paper prototype 使用者測試
- 所有視覺規範必須與 Phase 0b 信心標示（6 種狀態 × 三通道）完全相容
- Diff 符號使用 ASCII（+/−/~/≠），不使用 emoji
- 疑義路徑為概念層級設計，完整狀態機在 Phase 3 實作
- 需求覆蓋：Req 1→1.1, Req 2→1.2, Req 3→1.3, Req 4→1.5+3.2, Req 5→1.4+3.2, Req 6→1.4, Req 7→4, Req 8→3, Req 9→1.5+1.6, Req 10→1.6
