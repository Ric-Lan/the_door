# Phase 0a — 圖形語言規範 文件目錄 (Document Index)

本目錄包含 The Door Phase 0a 的完整圖形語言規範，拆分為獨立的組件文件。
所有視覺編碼皆使用**雙通道設計**（形狀 + 符號、顏色 + 邊框等），確保不依賴單一視覺通道即可區分語意。
本規範必須與 Phase 0b 已完成的信心標示（confidence markers）6 種狀態視覺規範完全相容，不得衝突。

## 文件清單

| 文件名 | 標題 | 說明 | 約行數 |
|---|---|---|---|
| `01-l1-functional-overview.md` | L1 功能總覽層 | L1 節點形狀、邊語意、語言規則、視覺群組 | ~130 |
| `02-l1_5-structural-overview.md` | L1.5 結構概覽層 | L1.5 節點形狀、邊語意、觸發標籤、基礎設施、展開指示器 | ~150 |
| `03-l2-functional-linkage.md` | L2 功能連動圖層 | L2 節點形狀、邊語意、異常標示、classDef、共存規則 | ~200 |
| `04-diff-symbols.md` | Diff 視覺符號 | Diff 節點/邊符號、優先序、classDef、摘要面板、觸發方式 | ~200 |
| `05-scope-boundary.md` | 範圍邊界協定 | 範圍標記 ✓/⚠/○、角標徽章、摘要面板、疑義路徑入口 | ~160 |
| `06-visual-layering-rules.md` | 視覺疊加與共存規則 | 通道分配、classDef 限制、共存規則、優先序表、衝突解決 | ~200 |
| `07-layer-switching.md` | 層級切換視覺規範 | Tab 切換、點擊展開、指示器、導航場景 | ~250 |
| `08-vocabulary-table.md` | 完整視覺詞彙總表 | 所有層級的語意→視覺編碼映射 + 唯一性驗證 | ~130 |
| `09-md-plaintext-format.md` | MD 純文字模擬格式規範 | MD 格式規範 + Mermaid 對照表 + 完整範例 | ~230 |
| `paper-prototype.md` | Paper Prototype | 以 MD 純文字模擬圖呈現的低成本原型 | ~450 |
| `doubt-path-concept.md` | 疑義路徑概念設計 | 疑義從發現到解決的完整處理流程 | ~290 |

## 使用方式

> AI 讀取時先讀本目錄，再依需求精準讀取對應組件文件。

**雙通道設計**的完整說明見 `01-l1-functional-overview.md` §1.1。各組件文件中不再重複此設計理由的詳細解釋。

**MD 純文字表示法**的完整定義見 `09-md-plaintext-format.md`。各層級文件中不再重複 MD 格式範例。

**完整 Paper Prototype 範例**見 `paper-prototype.md`。各層級文件中不再包含完整範例。
