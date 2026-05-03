# Requirements Document

## Introduction

The Door Phase 4 — 歷史時間軸層（History Timeline Layer）在既有的 SnapshotStore（多版本快照）和 DiffEngine（兩版比對）基礎上，擴展為多版本時間軸分析與視覺化。本層的核心目標是讓驗核者能回答：「這個功能在過去三個月的演進路徑是否符合承諾」。具體交付物包括：功能演進時間軸（每個功能從何時出現、中間改了幾次、現在狀態）、以次數為基礎的版本保留策略、語意漂移偵測（spec §12.2：description 變更 → 🔵 標記）、以及 Mermaid 時間軸圖形渲染。本層建立在 Phase 1-full–3 全部驗證完成的基礎上，複用既有的 SnapshotStore、DiffEngine、escape_mermaid_label 等共用元件。

## Glossary

- **The_Door_CLI**: Python 命令列工具，執行 AST 提取、拓撲分析、LLM 翻譯、輸出驗證、Mermaid 渲染、版本比對、漏洞掃描、範圍驗核，以及本階段新增的歷史時間軸功能
- **Timeline_Engine**: 多版本時間軸分析引擎，接收一組 VersionSnapshot 序列，為每個功能計算首次出現時間、變更次數、當前狀態、語意漂移事件等演進資訊。Pure function，無 I/O
- **Feature_Timeline**: 單一功能的完整演進記錄，包含：feature_id、首次出現的 snapshot 時間戳、最後出現的 snapshot 時間戳、變更次數（label 或 description 變更）、語意漂移事件列表、當前狀態（active/removed）
- **Timeline_Result**: Timeline_Engine 的完整輸出，包含所有功能的 Feature_Timeline 列表、分析的 snapshot 數量、時間範圍、以及聚合統計
- **Semantic_Drift_Event**: 語意漂移事件記錄，當功能的 label 未變但 description 實質改變時觸發（spec §12.2）。記錄：snapshot 版本、舊 description、新 description、時間戳
- **Timeline_Renderer**: 將 Timeline_Result 渲染為 Mermaid 時間軸圖形或純文字的元件，顯示功能演進的視覺化時間軸，包含新增/移除/變更/語意漂移標記
- **Retention_Engine**: 執行版本保留策略的元件。以快照數量為單位（非時間），根據使用者設定的 max_snapshots 上限決定哪些 snapshot 應保留、哪些應清理。手動快照和有 git_tags 的快照受保護，不計入上限。Pure function，無 I/O
- **Version_Snapshot**: 已存在的版本快照資料結構（Phase 2），包含 version_id、timestamp、trigger（"commit" | "manual"）、l1_snapshot、l1_5_snapshot、commit_hash、git_tags、label 等欄位
- **Snapshot_Store**: 已存在的快照儲存層（Phase 2），管理 `.the-door/snapshots/` 目錄中的 JSON 快照檔案。目前提供 create/get/list/resolve，Phase 4 需擴展 delete 方法
- **MCP_Server**: Model Context Protocol 伺服器，暴露 The Door 核心功能為 MCP tools（既有 15 個 tools，本階段新增時間軸相關 tools）

## Requirements

### Requirement 1: 多版本時間軸分析引擎

**User Story:** 身為驗核者，我希望系統能分析多個版本快照，為每個功能建立完整的演進時間軸，以便我能追蹤功能從何時出現、改了幾次、現在是什麼狀態。

#### Acceptance Criteria

1. WHEN 一組 VersionSnapshot 序列（按 timestamp 排序）被提供時，THE Timeline_Engine SHALL 為每個曾出現在任一 snapshot 中的功能產生一筆 Feature_Timeline 記錄
2. THE Feature_Timeline SHALL 包含以下欄位：feature_id、first_seen_timestamp（功能首次出現的 snapshot 時間戳）、last_seen_timestamp（功能最後出現的 snapshot 時間戳）、change_count（label 或 description 變更的次數）、current_state（"active" 若功能存在於最新 snapshot，"removed" 若不存在）、current_label（最新 snapshot 中的 label，若已移除則為最後已知 label）、drift_events（語意漂移事件列表）
3. THE Timeline_Engine SHALL 透過 feature_id（VersionSnapshot.l1_snapshot 的 key）在各 snapshot 之間追蹤同一功能
4. WHEN 一個功能在連續兩個 snapshot 之間的 label 或 description 發生變更時，THE Timeline_Engine SHALL 將 change_count 加 1（confidence 變更不計入 change_count，因為 confidence 是 LLM 自評的元資料，不是功能本身的屬性）
5. THE Timeline_Engine SHALL 為 pure function：接收 list[VersionSnapshot] 回傳 Timeline_Result，無 I/O，給定相同輸入產出相同結果
6. FOR ALL snapshot 序列，Timeline_Result 中的 Feature_Timeline 數量 SHALL 等於所有 snapshot 中出現過的不重複 feature_id 總數（完整性）

### Requirement 2: 語意漂移偵測

**User Story:** 身為驗核者，我希望系統能偵測功能名稱未變但說明實質改變的情況（語意漂移），以便我能重新確認功能範圍是否擴大。

#### Acceptance Criteria

1. WHEN 一個功能在連續兩個 snapshot 之間的 label 保持不變但 description 發生變更時，THE Timeline_Engine SHALL 產生一筆 Semantic_Drift_Event
2. THE Semantic_Drift_Event SHALL 包含：snapshot_version_id（偵測到漂移的 snapshot）、previous_description（前一版 description）、new_description（新版 description）、timestamp（偵測到漂移的 snapshot 時間戳）
3. WHEN 一個功能的 label 和 description 同時變更時，THE Timeline_Engine SHALL 將其歸類為一般屬性變更（change_count +1），不產生 Semantic_Drift_Event（因為 label 變更已明確表示功能改變）
4. THE Timeline_Engine SHALL 在 Feature_Timeline 的 drift_events 列表中累積該功能的所有語意漂移事件，按時間排序
5. FOR ALL snapshot 序列，若功能的 label 在兩個連續 snapshot 之間未變且 description 也未變，THE Timeline_Engine SHALL 不產生 Semantic_Drift_Event（無漂移時不誤報）

### Requirement 3: 版本保留策略（以次數為基礎）

**User Story:** 身為系統管理者，我希望能控制保留多少個快照，並選擇是否啟用自動清理，以便在儲存空間和歷史追蹤之間取得平衡。

#### Acceptance Criteria

1. THE Retention_Engine SHALL 以快照數量為單位執行保留策略：使用者設定 max_snapshots 上限（預設值 50），超過上限時從最舊的非保護快照開始清理
2. THE Retention_Engine SHALL 將以下快照視為「受保護」，不計入 max_snapshots 上限且不會被清理：(a) 手動快照（trigger="manual"）、(b) 有 git_tags 的快照（git_tags 非空列表）
3. THE Retention_Engine SHALL 接收三個參數：snapshot 列表、max_snapshots 上限值、enabled 旗標（預設 true）。WHEN enabled 為 false 時，所有 snapshot 均歸入 to_retain（不清理任何快照）
4. THE Retention_Engine SHALL 回傳兩個列表：to_retain（應保留的 snapshot version_id 列表）和 to_remove（應清理的 snapshot version_id 列表）
5. THE Retention_Engine SHALL 為 pure function：給定相同的 snapshot 列表、max_snapshots 和 enabled，產出的保留決策完全相同
6. FOR ALL 輸入，to_retain 和 to_remove 的聯集 SHALL 等於輸入的全部 snapshot（無遺漏、無重複），且交集為空
7. THE 保留策略設定 SHALL 儲存在 `.the-door/retention-config.json`（project-level），格式為 `{"max_snapshots": 50, "enabled": true}`。若檔案不存在，使用預設值

### Requirement 4: 版本保留策略執行

**User Story:** 身為開發者，我希望有 CLI 指令能執行版本清理，以便我能控制快照儲存空間。

#### Acceptance Criteria

1. THE The_Door_CLI SHALL 提供 `the-door snapshot prune <codebase-path>` 指令，根據保留策略計算並刪除過期的 snapshot 檔案
2. WHEN `the-door snapshot prune` 執行時，THE The_Door_CLI SHALL 先顯示將被刪除的 snapshot 列表（version_id、timestamp、trigger、label），並要求使用者確認後才執行刪除
3. THE `the-door snapshot prune` 指令 SHALL 支援 `--dry-run` 旗標，僅顯示將被刪除的 snapshot 列表而不實際刪除
4. THE `the-door snapshot prune` 指令 SHALL 支援 `--force` 旗標，跳過確認直接執行刪除
5. THE `the-door snapshot prune` 指令 SHALL 支援 `--max <N>` 旗標，覆蓋 retention-config.json 中的 max_snapshots 值（僅本次執行有效）
6. IF 沒有任何 snapshot 需要清理，THEN THE The_Door_CLI SHALL 顯示訊息表示所有 snapshot 均在保留範圍內
7. THE SnapshotStore SHALL 擴展 `delete_snapshot(version_id: str)` 方法，刪除對應的 JSON 檔案。若檔案不存在則靜默忽略

### Requirement 5: 功能演進時間軸 Mermaid 渲染

**User Story:** 身為驗核者，我希望看到功能演進的視覺化時間軸圖形，以便我能一眼掌握每個功能的生命週期。

#### Acceptance Criteria

1. THE Timeline_Renderer SHALL 將 Timeline_Result 渲染為 Mermaid 圖形語法，以時間為橫軸、功能為縱軸，顯示每個功能在各版本中的狀態
2. THE Timeline_Renderer SHALL 使用以下視覺標記：🟢 表示功能首次出現、🔴 表示功能被移除、🟠 表示功能屬性變更、🔵 表示語意漂移（description 變更但 label 未變）、⚪ 表示功能無變化
3. THE Timeline_Renderer SHALL 在圖形頂部包含摘要面板（Mermaid comment `%%`），顯示：分析的版本數量、時間範圍、活躍功能數、已移除功能數、語意漂移事件總數
4. WHEN 功能有語意漂移事件時，THE Timeline_Renderer SHALL 在對應的時間點標記 🔵 並附加提示文字「功能說明已更新，請重新確認」
5. THE Timeline_Renderer SHALL 產生語法正確的 Mermaid 文字，能通過 Mermaid.js 解析而無錯誤
6. THE Timeline_Renderer SHALL 複用既有的 escape_mermaid_label 共用函式處理特殊字元

### Requirement 6: 功能演進摘要文字輸出

**User Story:** 身為驗核者，我希望能以純文字格式查看功能演進摘要，以便在不支援 Mermaid 的環境中也能使用。

#### Acceptance Criteria

1. THE Timeline_Renderer SHALL 提供純文字輸出格式，為每個功能顯示：功能名稱、首次出現時間、變更次數、當前狀態、語意漂移次數
2. WHEN 功能有語意漂移事件時，THE Timeline_Renderer SHALL 在純文字輸出中列出每次漂移的時間和 description 變更摘要
3. THE 純文字輸出 SHALL 按功能的 first_seen_timestamp 排序（最早出現的功能排在前面）
4. THE 純文字輸出 SHALL 使用功能語言（「功能」而非「節點」或「模組」），與既有的 Diff summary panel 風格一致

### Requirement 7: 歷史時間軸 CLI 指令

**User Story:** 身為開發者，我希望有 CLI 指令能查看功能演進時間軸，以便從命令列追蹤功能歷史。

#### Acceptance Criteria

1. THE The_Door_CLI SHALL 新增 `the-door timeline <codebase-path>` 指令，從 `.the-door/snapshots/` 載入所有 snapshot，執行 Timeline_Engine 分析，並輸出功能演進時間軸。既有的 `the-door history` 指令保持不變（顯示敘事鏈）
2. THE `the-door timeline` 指令 SHALL 預設輸出純文字格式的功能演進摘要
3. THE `the-door timeline` 指令 SHALL 支援 `--render` 旗標，輸出 Mermaid 時間軸圖形
4. THE `the-door timeline` 指令 SHALL 支援 `--json` 旗標，輸出完整的 Timeline_Result JSON
5. THE `the-door timeline` 指令 SHALL 支援 `--feature <feature_id>` 旗標，僅顯示指定功能的演進歷史
6. THE `the-door timeline` 指令 SHALL 支援 `--since <date>` 旗標（ISO 8601 格式），僅分析指定日期之後的 snapshot
7. THE `the-door timeline` 指令 SHALL 支援 `-o <file>` 旗標，將輸出寫入檔案（UTF-8 編碼，Windows 相容）
8. IF 沒有任何 snapshot 存在，THEN THE The_Door_CLI SHALL 顯示訊息指示使用者先執行 `the-door analyze` 或 `the-door snapshot create`

### Requirement 8: 單一功能詳細演進查詢

**User Story:** 身為驗核者，我希望能查看單一功能的詳細演進歷史，包含每次變更的具體內容，以便深入追蹤特定功能的變化。

#### Acceptance Criteria

1. WHEN `--feature <feature_id>` 旗標被指定時，THE The_Door_CLI SHALL 輸出該功能的完整演進記錄，包含：每個版本中的 label、description、confidence、source_node_count（對應 FeatureSummary 的欄位）
2. THE 單一功能詳細輸出 SHALL 標記每個版本之間的變更類型：「首次出現」、「屬性變更」、「語意漂移」、「無變化」、「已移除」
3. WHEN 功能發生語意漂移時，THE 詳細輸出 SHALL 並列顯示前後兩版的 description，以便驗核者比較差異
4. THE 單一功能詳細輸出 SHALL 包含該功能的版本對應資訊：每個 snapshot 的 commit_hash、git_tags、label（若有）
5. IF 指定的 feature_id 不存在於任何 snapshot 中，THEN THE The_Door_CLI SHALL 顯示錯誤訊息並列出可用的 feature_id 清單

### Requirement 9: 時間軸資料格式

**User Story:** 身為開發者，我希望時間軸分析結果遵循正式的 JSON schema，以便下游消費可靠且一致。

#### Acceptance Criteria

1. THE Timeline_Result SHALL 符合 `timeline-result.schema.json` schema（jsonschema Draft 2020-12），定義必要欄位：snapshot_count（分析的 snapshot 數量）、time_range_start（最早 snapshot 時間戳，空序列時為 null）、time_range_end（最新 snapshot 時間戳，空序列時為 null）、feature_timelines（Feature_Timeline 陣列）、summary（聚合統計：active_count、removed_count、total_drift_events）
2. THE Feature_Timeline SHALL 定義必要欄位：feature_id（字串）、first_seen_timestamp（ISO8601）、last_seen_timestamp（ISO8601）、change_count（整數 ≥ 0）、current_state（enum: "active", "removed"）、current_label（字串）、drift_events（Semantic_Drift_Event 陣列）
3. FOR ALL 有效的 Timeline_Result，序列化為 JSON 再反序列化回來 SHALL 產生等價的物件（round-trip property）

### Requirement 10: 時間軸正確性屬性

**User Story:** 身為開發者，我希望時間軸引擎滿足形式化的正確性屬性，以便時間軸結果在數學上一致且可信賴。

#### Acceptance Criteria

1. FOR ALL snapshot 序列，Timeline_Result 中每個 Feature_Timeline 的 first_seen_timestamp SHALL 小於或等於 last_seen_timestamp（時間順序一致性）
2. FOR ALL snapshot 序列，Timeline_Result 中每個 Feature_Timeline 的 change_count SHALL 小於或等於（snapshot 總數 - 1）（變更次數上界：每對連續 snapshot 之間最多產生一次變更）
3. FOR ALL snapshot 序列，current_state 為 "active" 的功能 SHALL 存在於最新 snapshot 的 l1_snapshot 中；current_state 為 "removed" 的功能 SHALL 不存在於最新 snapshot 的 l1_snapshot 中（狀態一致性）
4. FOR ALL snapshot 序列，每個 Semantic_Drift_Event 的 timestamp SHALL 對應到一個實際存在的 snapshot 的 timestamp（漂移事件可追溯性）
5. FOR ALL snapshot 序列，若只有一個 snapshot，THE Timeline_Engine SHALL 產生 change_count 為 0 且 drift_events 為空的 Feature_Timeline（單一版本基線）
6. FOR ALL snapshot 序列 S，對 S 執行時間軸分析兩次 SHALL 產生完全相同的 Timeline_Result（冪等性）

### Requirement 11: 保留策略正確性屬性

**User Story:** 身為開發者，我希望保留策略引擎滿足形式化的正確性屬性，以便保留決策可預測且不會意外刪除重要快照。

#### Acceptance Criteria

1. FOR ALL snapshot 列表，手動快照（trigger="manual"）SHALL 永遠出現在 to_retain 列表中（手動快照永久保留）
2. FOR ALL snapshot 列表，有 git_tags（非空列表）的 snapshot SHALL 永遠出現在 to_retain 列表中（tagged 版本永久保留）
3. FOR ALL snapshot 列表，WHEN enabled=false 時，所有 snapshot SHALL 出現在 to_retain 列表中，to_remove 為空（停用清理時不刪除任何快照）
4. FOR ALL snapshot 列表，to_retain 和 to_remove 的聯集 SHALL 等於輸入的全部 snapshot，且交集為空（分割完整性）
5. FOR ALL snapshot 列表和相同參數，對相同輸入執行保留策略兩次 SHALL 產生完全相同的結果（冪等性）
6. FOR ALL snapshot 列表，to_remove 中的 snapshot 數量 SHALL 等於 max(0, 非保護快照數量 - max_snapshots)（清理數量可預測）

### Requirement 12: MCP Server 時間軸工具

**User Story:** 身為 AI medium 開發者，我希望有 MCP tools 能查詢功能演進時間軸，以便 MCP clients 能程式化地存取 Phase 4 功能。

#### Acceptance Criteria

1. THE MCP_Server SHALL 暴露 `timeline` tool，接受 codebase_path（必填）和可選的 feature_id 與 since 日期參數，回傳 Timeline_Result JSON。既有的 `history` tool 保持不變（回傳敘事鏈）
2. THE MCP_Server SHALL 暴露 `snapshot_prune` tool，接受 codebase_path（必填）和可選的 dry_run 旗標與 max_snapshots 覆蓋值，回傳保留策略計算結果（to_retain 和 to_remove 列表）
3. WHEN MCP tool 遇到錯誤（無 snapshot、無效參數）時，THE MCP_Server SHALL 回傳結構化的錯誤回應，包含人類可讀的錯誤訊息，與既有 MCP 錯誤處理模式一致
