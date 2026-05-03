# Requirements Document

## Introduction

The Door Phase 5 — 即時動態層（Realtime Dynamic Layer）是一條自動化管線（orchestration layer），將 Phase 1–4 的既有能力串接為一個完整的版本更新分析流程。使用者手動指定舊版路徑與新版路徑，系統自動執行兩版各自的 analyze（含 extract + topology + LLM 翻譯 + 漏洞掃描 + auto-snapshot）→ diff 計算 → scope verify（若有 scope definition）→ timeline 更新，最終輸出一份互動式逐層展開的版本更新報告。

**核心定位：** Phase 5 不新增任何分析引擎，所有分析能力完全複用 Phase 1–4 現有模組。Phase 5 的價值在於 orchestration（管線編排）和 presentation（展開順序設計），讓非工程師人員（PM、SPM、發布經理、QA/PO、甲方/上層）能以符合其閱讀習慣的順序，逐層理解一次版本更新的完整影響。

**「即時」的定義：** 不是邊寫程式碼邊顯示變化，而是對一個已完成的程式包進行前後版本的修正關係連結。基礎層（extract + analyze）應執行完全辨認，不做增量或部分分析。

**風險回應：** Spec §10 提到「動態焦慮：即時動態可能製造焦慮而非清晰」。Phase 5 的 UX 設計以「逐層展開」回應此風險——預設只顯示最高層摘要，使用者主動點擊才展開細節，避免一次性資訊過載。

本層建立在 Phase 1-full–4 全部驗證完成的基礎上，複用既有的 AST Extraction、Topology Analysis、LLM Translation、SnapshotStore、DiffEngine、DiffRenderer、VulnerabilityScanner、ScopeVerifier、TimelineEngine、TimelineRenderer 等共用元件。

## Glossary

- **The_Door_CLI**: Python 命令列工具，執行 AST 提取、拓撲分析、LLM 翻譯、輸出驗證、Mermaid 渲染、版本比對、漏洞掃描、範圍驗核、歷史時間軸，以及本階段新增的版本更新管線功能
- **Update_Pipeline**: 版本更新自動管線，接收舊版路徑與新版路徑，依序呼叫 Phase 1–4 的既有模組完成完整的版本更新分析。Pure orchestration，不包含任何新的分析邏輯
- **Pipeline_Orchestrator**: 管線編排引擎，負責協調各分析步驟的執行順序、錯誤處理、進度回報。接收 Pipeline_Config 回傳 Pipeline_Result
- **Pipeline_Config**: 管線執行設定，包含：old_path（舊版路徑）、new_path（新版路徑）、scope_name（可選，scope definition 名稱）、offline_vuln（可選，漏洞掃描使用離線模式）、skip_timeline（可選，跳過時間軸更新）、output_dir（可選，輸出目錄）、provider（可選，LLM provider 覆蓋）、skip_cost_confirm（可選，跳過成本確認）、force_reanalyze（可選，強制重新分析即使已有 snapshot）、step_timeout_seconds（可選，各步驟超時秒數，預設 analyze=300/其他=30）
- **Pipeline_Result**: 管線執行的完整結果，包含：各步驟的執行狀態與耗時、DiffResult、ScopeResult（若有）、VulnerabilitySummary（若有）、TimelineResult（若有）、以及最終的 Update_Report
- **Pipeline_Step**: 管線中的單一執行步驟，包含：step_name、status（completed/failed/skipped，僅記錄終態）、started_at、completed_at、duration_ms、error_message（若失敗）。pending/running 狀態僅在 progress_callback 即時回報中使用，不記錄在 Pipeline_Result 中
- **Update_Report**: 版本更新報告，以非工程師的閱讀順序組織所有分析結果。包含四個展開層級：L0 摘要（一句話結論）、L1 變更總覽（功能級別變更清單）、L2 細節展開（每個變更的具體內容）、L3 技術附錄（完整 JSON 資料）
- **Report_Renderer**: 將 Pipeline_Result 渲染為互動式逐層展開報告的元件。支援三種輸出格式：互動式 Markdown（主線）、結構化 JSON、Mermaid 圖形
- **Version_Snapshot**: 已存在的版本快照資料結構（Phase 2），包含 version_id、timestamp、trigger、l1_snapshot、l1_5_snapshot、commit_hash、git_tags、label 等欄位
- **Diff_Engine**: 已存在的版本比對引擎（Phase 2），計算兩個 snapshot 之間的 L1/L1.5 差異
- **Scope_Verifier**: 已存在的範圍驗核元件（Phase 3），比對 scope definition 與 L1 分析結果
- **Vulnerability_Scanner**: 已存在的漏洞掃描元件（Phase 2.5），呼叫 osv-scanner 掃描已知漏洞
- **Timeline_Engine**: 已存在的時間軸分析引擎（Phase 4），分析多版本功能演進
- **Snapshot_Store**: 已存在的快照儲存層（Phase 2），管理 `.the-door/snapshots/` 目錄中的 JSON 快照檔案
- **MCP_Server**: Model Context Protocol 伺服器，暴露 The Door 核心功能為 MCP tools（既有 17 個 tools，本階段新增管線相關 tools）

## Requirements

### Requirement 1: 版本更新管線編排引擎

**User Story:** 身為 PM/發布經理，我希望指定舊版路徑和新版路徑後，系統能自動完成所有分析步驟，以便我不需要逐一執行多個指令就能得到完整的版本更新報告。

#### Acceptance Criteria

1. WHEN 舊版路徑（old_path）和新版路徑（new_path）被提供時，THE Pipeline_Orchestrator SHALL 依序執行以下步驟：(a) 對舊版執行 analyze（內含 extract + topology + LLM 翻譯 + 漏洞掃描 + auto-snapshot，複用既有 analyze 管線）、(b) 對新版執行 analyze（同上）、(c) 以舊版 snapshot 為 baseline、新版 snapshot 為 current 執行 diff、(d) 若 Pipeline_Config 包含 scope_name 則對新版的 L1 結果執行 scope verify、(e) 執行 timeline 更新（載入新版路徑下所有 snapshot 分析演進）、(f) 將所有結果組裝為 Update_Report
2. THE Pipeline_Orchestrator SHALL 為每個步驟記錄 Pipeline_Step 狀態，包含：step_name、status、started_at、completed_at、duration_ms，以便使用者追蹤管線進度
3. THE Pipeline_Orchestrator SHALL 呼叫 Phase 1–4 的既有核心模組 API（ASTExtractor、TopologyAnalyzer、BatchReader、SnapshotStore、DiffEngine、ScopeVerifier、TimelineEngine 等），不透過 CLI subprocess。目前 analyze 的編排邏輯位於 `cli/analyze_cmd.py`，Phase 5 SHALL 將此邏輯提取為可複用的核心函式（例如 `core/pipeline/analyze_pipeline.py`），供 Pipeline_Orchestrator 和 CLI 共同使用
4. THE Pipeline_Orchestrator SHALL 為 pure orchestration：不包含任何新的分析邏輯，所有分析能力完全委派給既有模組
5. FOR ALL 相同的 Pipeline_Config 輸入（且底層 LLM 回應相同），THE Pipeline_Orchestrator SHALL 產生相同的步驟執行序列（執行順序確定性）

### Requirement 2: 管線錯誤處理與部分結果

**User Story:** 身為 PM/發布經理，我希望管線中某個步驟失敗時，系統能繼續執行後續可獨立運作的步驟並回傳部分結果，以便我不會因為單一步驟失敗而完全無法取得分析結果。

#### Acceptance Criteria

1. IF 舊版或新版的 analyze 步驟失敗或超時，THEN THE Pipeline_Orchestrator SHALL 終止管線並回傳錯誤，因為後續所有步驟都依賴分析結果
2. IF diff 步驟失敗，THEN THE Pipeline_Orchestrator SHALL 將 diff 步驟標記為 failed 並繼續執行 scope verify 和 timeline 步驟（這些步驟可獨立運作）
3. IF scope verify 步驟失敗（例如 scope definition 不存在），THEN THE Pipeline_Orchestrator SHALL 將該步驟標記為 failed 並繼續執行後續步驟
4. IF timeline 步驟失敗，THEN THE Pipeline_Orchestrator SHALL 將該步驟標記為 failed，管線仍可產出部分報告
5. THE Pipeline_Result SHALL 包含所有步驟的狀態，讓 Report_Renderer 能根據可用的結果生成部分報告，並在報告中標示哪些區段因步驟失敗而無法生成
6. FOR ALL Pipeline_Result，completed 步驟數 + failed 步驟數 + skipped 步驟數 SHALL 等於管線中的總步驟數（步驟狀態完整性）

### Requirement 3: 管線步驟可選跳過

**User Story:** 身為開發者，我希望能選擇性跳過某些分析步驟（如漏洞掃描或時間軸更新），以便在不需要完整分析時加快管線執行速度。

#### Acceptance Criteria

1. WHEN Pipeline_Config 的 offline_vuln 為 true 時，THE Pipeline_Orchestrator SHALL 在呼叫 analyze 時傳入 offline 旗標，使漏洞掃描使用本地 OSV 資料庫（漏洞掃描是 analyze 管線的一部分，不可單獨跳過，但可切換為離線模式）
2. WHEN Pipeline_Config 的 skip_timeline 為 true 時，THE Pipeline_Orchestrator SHALL 跳過 timeline 更新步驟，將其標記為 skipped
3. THE Pipeline_Orchestrator SHALL 始終執行 analyze（含 extract + topology + LLM 翻譯 + 漏洞掃描 + auto-snapshot）和 diff 步驟，這些是管線的核心步驟，不可跳過
4. WHEN scope_name 未在 Pipeline_Config 中指定時，THE Pipeline_Orchestrator SHALL 跳過 scope verify 步驟，將其標記為 skipped（scope verify 需要明確的 scope definition）

### Requirement 4: 互動式逐層展開報告結構

**User Story:** 身為非工程師人員（PM/SPM/發布經理），我希望版本更新報告按照我的閱讀習慣逐層展開，以便我能先看到最重要的結論，再按需深入細節。

#### Acceptance Criteria

1. THE Report_Renderer SHALL 將 Pipeline_Result 組織為四個展開層級：L0 摘要（預設展開）、L1 變更總覽（預設展開）、L2 細節展開（預設收合）、L3 技術附錄（預設收合）
2. THE L0 摘要 SHALL 包含一句話結論，格式為：「本次更新：新增 N 個功能、修改 M 個功能、移除 K 個功能」加上風險提示（若有高風險漏洞或超出範圍項目）
3. THE L1 變更總覽 SHALL 按以下順序列出變更：(a) 超出範圍的變更（⚠，若有 scope verify 結果）、(b) 新增的功能（🟢）、(c) 修改的功能（🟠）、(d) 移除的功能（🔴）、(e) 漏洞摘要（若有）、(f) 語意漂移警告（若有）
4. THE L2 細節展開 SHALL 為每個變更的功能提供：變更前後的 label 和 description 對比、影響的依賴關係、scope 狀態（若有）、相關漏洞（若有）
5. THE L3 技術附錄 SHALL 包含：完整的 DiffResult JSON、完整的 ScopeResult JSON（若有）、完整的 TimelineResult JSON（若有）、管線執行統計（各步驟耗時）
6. THE Report_Renderer SHALL 使用功能語言（「功能」而非「節點」或「模組」），與既有的 Diff_Summary_Panel 和 Scope_Summary_Panel 風格一致

### Requirement 5: 報告展開順序設計（非工程師閱讀順序）

**User Story:** 身為非工程師人員，我希望報告的展開順序反映我的關注優先級，以便我能最快找到需要注意的項目。

#### Acceptance Criteria

1. THE L1 變更總覽 SHALL 將超出範圍的變更（⚠）排在最前面，因為這是非工程師最需要立即關注的項目（「工程師做了計畫外的事」）
2. THE L1 變更總覽 SHALL 將有高風險漏洞的功能以 🔴⚑ 標記並排在同類變更的最前面，因為安全風險需要優先處理
3. THE L1 變更總覽 SHALL 將有語意漂移（🔵）的功能以明確提示標記：「功能說明已更新，請重新確認」，因為語意漂移代表功能範圍可能擴大
4. WHEN 報告中沒有超出範圍項目、沒有高風險漏洞、沒有語意漂移時，THE L0 摘要 SHALL 顯示正面結論：「本次更新在預期範圍內，未發現異常」
5. THE 展開順序 SHALL 遵循「風險優先、變更次之、穩定最後」的原則：風險項目（超出範圍、漏洞、語意漂移）→ 實質變更（新增、修改、移除）→ 無變化項目（不顯示在 L1，僅在 L2 可查）

### Requirement 6: 互動式 Markdown 報告格式

**User Story:** 身為非工程師人員，我希望報告以 Markdown 格式輸出，並使用 HTML details/summary 標籤實現逐層展開，以便在任何支援 Markdown 的環境中都能互動式閱讀。

#### Acceptance Criteria

1. THE Report_Renderer SHALL 生成 Markdown 格式的報告，使用 HTML `<details>` 和 `<summary>` 標籤實現可展開/收合的區段
2. THE L0 摘要和 L1 變更總覽 SHALL 預設為展開狀態（`<details open>`），L2 細節和 L3 技術附錄 SHALL 預設為收合狀態（`<details>`）
3. THE 每個可展開區段 SHALL 包含展開提示文字（expand_hint），例如：「點擊展開 3 個功能的變更細節」、「點擊查看完整 JSON 資料」
4. THE 報告 SHALL 在頂部包含目錄（Table of Contents），列出所有 L1 層級的區段標題，方便快速跳轉
5. THE 報告 SHALL 使用 UTF-8 編碼寫入檔案，確保 Windows 相容性
6. THE 報告 SHALL 在沒有 HTML 渲染支援的環境中（純文字終端）仍然可讀——`<details>` 標籤內的內容在純文字模式下全部可見

### Requirement 7: 結構化 JSON 報告格式

**User Story:** 身為開發者或 AI medium，我希望能以結構化 JSON 格式取得版本更新報告，以便程式化消費和自訂呈現。

#### Acceptance Criteria

1. THE Report_Renderer SHALL 支援 JSON 輸出格式，將 Update_Report 序列化為結構化 JSON，包含所有四個層級的內容
2. THE JSON 報告 SHALL 符合 Requirement 11 定義的 `update-report.schema.json` schema
3. THE JSON 報告中的每個 l1_changes 項目 SHALL 包含：feature_id、change_type（added/removed/attribute_changed/dependency_changed）、risk_flags（陣列，可能包含 out_of_scope/vulnerability/semantic_drift）、current_label、baseline_label（若有）
4. FOR ALL 有效的 Pipeline_Result，序列化為 JSON 報告再反序列化回來 SHALL 產生等價的物件（round-trip property）

### Requirement 8: Mermaid 圖形報告格式

**User Story:** 身為非工程師人員，我希望版本更新報告包含 Mermaid 圖形，以便我能以視覺化方式理解變更。

#### Acceptance Criteria

1. THE Report_Renderer SHALL 支援 Mermaid 輸出格式，複用既有的 DiffRenderer 生成 diff 圖形
2. WHEN scope verify 結果可用時，THE Report_Renderer SHALL 複用既有的 ScopeRenderer 在 diff 圖形上疊加 scope badges
3. WHEN vulnerability 結果可用時，THE Report_Renderer SHALL 在合併摘要面板中以文字形式呈現漏洞摘要（複用 VulnerabilityRenderer.format_summary_header()），不在圖形節點上疊加邊框樣式。原因：Phase 5 管線不觸發 L2 分析，而 L1 漏洞邊框高亮需要 L2 anomalies 資料。若使用者需要節點級漏洞標記，應使用 `the-door analyze` + `the-door render` 的完整流程
4. THE Mermaid 輸出 SHALL 在圖形頂部包含合併摘要面板（Mermaid comment `%%`），整合 diff 摘要、scope 摘要、漏洞摘要為一個統一面板
5. THE Report_Renderer SHALL 產生語法正確的 Mermaid 文字，能通過 Mermaid.js 解析而無錯誤
6. THE Report_Renderer SHALL 複用既有的 escape_mermaid_label 共用函式處理特殊字元

### Requirement 9: 版本更新管線 CLI 指令

**User Story:** 身為開發者/PM，我希望有一個 CLI 指令能一鍵執行完整的版本更新分析管線，以便從命令列快速取得版本更新報告。

#### Acceptance Criteria

1. THE The_Door_CLI SHALL 新增 `the-door update <old-path> <new-path>` 指令，執行完整的版本更新管線並輸出互動式 Markdown 報告
2. THE `the-door update` 指令 SHALL 支援 `--scope <scope-name>` 旗標，指定要使用的 scope definition 進行範圍驗核
3. THE `the-door update` 指令 SHALL 支援 `--json` 旗標，輸出結構化 JSON 報告而非 Markdown
4. THE `the-door update` 指令 SHALL 支援 `--render` 旗標，輸出 Mermaid diff 圖形（含 scope badges 和漏洞標記）
5. THE `the-door update` 指令 SHALL 支援 `--offline` 旗標，使漏洞掃描使用本地 OSV 資料庫（傳遞給底層 analyze 管線）
6. THE `the-door update` 指令 SHALL 支援 `--skip-timeline` 旗標，跳過時間軸更新步驟
7. THE `the-door update` 指令 SHALL 支援 `--provider <name>` 旗標，覆蓋 config.toml 中的預設 LLM provider（傳遞給底層 analyze 管線）
8. THE `the-door update` 指令 SHALL 支援 `--yes` / `-y` 旗標，跳過 LLM 成本確認（傳遞給底層 analyze 管線）
9. THE `the-door update` 指令 SHALL 支援 `-o <file>` 旗標，將報告寫入檔案（UTF-8 編碼，Windows 相容）
10. THE `the-door update` 指令 SHALL 在執行過程中顯示進度資訊，包含當前步驟名稱和已完成步驟數
11. THE `the-door update` 指令 SHALL 支援 `--force-reanalyze` 旗標，強制重新分析兩個版本（即使已有既存 snapshot）
12. IF 舊版路徑或新版路徑不存在或不是目錄，THEN THE The_Door_CLI SHALL 顯示錯誤訊息指示路徑無效

### Requirement 10: 管線進度回報與時間預估

**User Story:** 身為使用者，我希望在管線執行過程中能看到即時進度、預估剩餘時間，並能在需要時中斷管線，以便我能掌控整個分析過程。

#### Acceptance Criteria

1. THE Pipeline_Orchestrator SHALL 在管線開始前顯示預估總耗時，基於兩個 codebase 的檔案數量估算（例如：「預估分析時間：約 2–5 分鐘（舊版 120 個檔案 + 新版 135 個檔案）」）
2. THE Pipeline_Orchestrator SHALL 在每個步驟開始時輸出進度訊息，格式為：「[步驟 N/M] 正在執行：<step_name>...」
3. THE Pipeline_Orchestrator SHALL 在每個步驟完成時輸出完成訊息，格式為：「[步驟 N/M] ✓ <step_name>（耗時 X.Xs）」
4. IF 某個步驟失敗，THE Pipeline_Orchestrator SHALL 輸出警告訊息，格式為：「[步驟 N/M] ✗ <step_name> — <error_message>（繼續執行後續步驟）」
5. THE Pipeline_Orchestrator SHALL 在管線完成時輸出總結訊息，包含：總耗時、成功步驟數、失敗步驟數、跳過步驟數
6. THE 進度訊息 SHALL 輸出到 stderr，報告內容輸出到 stdout，以便管線輸出可被重導向而不混入進度訊息
7. THE Pipeline_Orchestrator SHALL 支援使用者中斷（Ctrl+C / SIGINT）：收到中斷信號時，完成當前正在執行的步驟（不強制終止），然後以已完成的步驟結果生成部分報告，並在報告中標示「管線已被使用者中斷」
8. THE Pipeline_Orchestrator SHALL 為每個步驟設定超時上限（預設：analyze 步驟 300 秒、diff 步驟 30 秒、scope verify 步驟 30 秒、timeline 步驟 30 秒）。超時的步驟視為 failed，管線繼續執行後續步驟

### Requirement 11: 版本更新報告資料格式

**User Story:** 身為開發者，我希望版本更新報告遵循正式的 JSON schema，以便下游消費可靠且一致。

#### Acceptance Criteria

1. THE Update_Report SHALL 符合 `update-report.schema.json` schema（jsonschema Draft 2020-12），定義必要欄位：report_version（schema 版本字串）、generated_at（ISO8601 時間戳）、pipeline_summary（物件，包含 old_path、new_path、total_duration_ms、steps 陣列）、l0_summary（字串）、l1_changes（陣列）、l2_details（陣列）、l3_appendix（物件）
2. THE Pipeline_Step SHALL 定義必要欄位：step_name（字串）、status（enum: "completed", "failed", "skipped"）、duration_ms（整數或 null）、error_message（字串或 null）
3. THE l1_changes 項目 SHALL 定義必要欄位：feature_id（字串）、change_type（enum: "added", "removed", "attribute_changed", "dependency_changed"）、risk_flags（字串陣列）、current_label（字串）、baseline_label（字串或 null）
4. FOR ALL 有效的 Update_Report，序列化為 JSON 再反序列化回來 SHALL 產生等價的物件（round-trip property）

### Requirement 12: 管線正確性屬性

**User Story:** 身為開發者，我希望版本更新管線滿足形式化的正確性屬性，以便管線結果可預測且可信賴。

#### Acceptance Criteria

1. FOR ALL Pipeline_Result，l1_changes 中的功能清單 SHALL 與 DiffResult 中的變更清單一致：l1_changes 中 change_type 為 "added" 的功能數量等於 DiffResult 的 added_count，以此類推（管線結果與底層引擎一致性）
2. FOR ALL Pipeline_Result，若 scope verify 步驟成功完成，l1_changes 中標記 risk_flag "out_of_scope" 的功能 SHALL 與 ScopeResult 中 scope_state 為 "out_of_scope" 的功能完全一致（scope 結果一致性）
3. FOR ALL Pipeline_Config，對相同的舊版和新版路徑執行管線兩次（且底層 LLM 回應相同），SHALL 產生相同的 l1_changes 清單（冪等性）
4. FOR ALL Pipeline_Result，pipeline_summary.steps 中的步驟數量 SHALL 等於管線定義的總步驟數，且每個步驟的 status 為 "completed"、"failed" 或 "skipped" 之一（步驟完整性）
5. FOR ALL Pipeline_Result，l0_summary 中提到的數字（新增 N 個、修改 M 個、移除 K 個）SHALL 與 l1_changes 中對應 change_type 的計數完全一致（摘要與明細一致性）

### Requirement 13: MCP Server 版本更新管線工具

**User Story:** 身為 AI medium 開發者，我希望有 MCP tool 能觸發版本更新管線，以便 MCP clients 能程式化地執行完整的版本更新分析。

#### Acceptance Criteria

1. THE MCP_Server SHALL 暴露 `update` tool，接受 old_path（必填）、new_path（必填）、scope_name（可選）、offline_vuln（可選，預設 false）、skip_timeline（可選，預設 false）、output_format（可選，"json" 預設 或 "markdown" 或 "mermaid"），回傳對應格式的 Update_Report
2. WHEN MCP tool 遇到錯誤（無效路徑、分析失敗）時，THE MCP_Server SHALL 回傳結構化的錯誤回應，包含人類可讀的錯誤訊息，與既有 MCP 錯誤處理模式一致

### Requirement 14: 舊版新版路徑解析

**User Story:** 身為非工程師人員，我希望能指定兩個版本的目錄路徑，系統自動辨識並處理，以便我不需要了解 git 操作就能比較版本。

#### Acceptance Criteria

1. THE Pipeline_Orchestrator SHALL 接受兩個本地目錄路徑作為舊版（old_path）和新版（new_path），每個路徑指向一個 codebase 根目錄
2. THE Pipeline_Orchestrator SHALL 驗證兩個路徑均存在且為目錄，若任一路徑無效則回傳明確的錯誤訊息
3. WHEN 兩個路徑指向同一個目錄時，THE Pipeline_Orchestrator SHALL 回傳錯誤訊息：「舊版路徑和新版路徑不可相同」
4. THE Pipeline_Orchestrator SHALL 對兩個路徑各自獨立執行分析，確保舊版分析的 snapshot 儲存在舊版路徑的 `.the-door/snapshots/` 下，新版分析的 snapshot 儲存在新版路徑的 `.the-door/snapshots/` 下，互不干擾
5. WHEN 舊版路徑已有既存的 snapshot（例如先前已執行過 analyze），THE Pipeline_Orchestrator SHALL 比對上次分析時記錄的檔案指紋與當前 codebase 的檔案指紋（檔案路徑 + 檔案大小 + 最後修改時間）。指紋一致的定義為：檔案集合（路徑清單）完全相同，且每個檔案的大小和最後修改時間均未變。任何檔案的新增、刪除或修改均視為不一致，觸發重新分析。使用者可透過 `--force-reanalyze` 旗標強制重新分析
6. WHEN 使用既存 snapshot 時，THE Pipeline_Orchestrator SHALL 在進度訊息中顯示：「舊版使用既存分析結果（建立於 YYYY-MM-DD HH:MM，指紋驗證通過）」

### Requirement 15: 報告正確性屬性

**User Story:** 身為開發者，我希望報告渲染滿足形式化的正確性屬性，以便報告內容與底層資料一致。

#### Acceptance Criteria

1. FOR ALL Pipeline_Result，互動式 Markdown 報告中 L1 變更總覽列出的功能數量 SHALL 等於 l1_changes 陣列的長度（Markdown 與 JSON 一致性）
2. FOR ALL Pipeline_Result，Mermaid 圖形報告中的已變更節點數量 SHALL 等於 DiffResult.summary.total_changed_count（Mermaid 與 DiffResult 一致性）
3. FOR ALL Pipeline_Result，若某步驟標記為 failed，報告中對應的區段 SHALL 包含失敗提示而非空白（失敗可見性）
