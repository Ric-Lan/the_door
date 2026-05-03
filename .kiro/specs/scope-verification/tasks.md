# Implementation Plan: Phase 3 Scope Verification Layer (範圍驗核層)

## Overview

在 Phase 2.5（漏洞資訊層）之上實作範圍驗核與疑義路徑兩大能力。依賴順序：data models + JSON schemas → ScopeVerifier（pure function 核心）→ DoubtStore（狀態機 + 持久化）→ ScopeRenderer（Mermaid 角標徽章 + 摘要面板）→ CLI 命令 → MCP tools → 整合連接。每個任務包含測試。Property-based tests 使用 Hypothesis（`@settings(max_examples=100)`），Windows 上使用 ASCII-only 字串。

## Tasks

- [x] 1. 定義 Phase 3 data models 與 JSON schemas
  - [x] 1.1 新增 scope + doubt dataclasses 到 models.py
    - 新增 10 個 dataclasses 到 `src/the_door/models.py`：`ScopeFeatureEntry`、`ScopeDefinition`、`ScopeEntry`、`ScopeCounts`、`ScopeResult`（frozen=True）；`StateTransition`、`Resolution`（frozen=True）；`DoubtRecord`（非 frozen — 狀態轉換需修改）；`DoubtSummary`（frozen=True）
    - 新增 4 個 exception classes：`ScopeDefinitionError`、`DoubtNotFoundError`、`InvalidTransitionError`、`DoubtTerminalError`
    - 遵循既有慣例：`frozen=True` 用於不可變值物件，`field(default_factory=...)` 用於可變預設值
    - _Requirements: 1.1, 2.3, 6.1, 6.3, 7.3, 17.1, 17.2_

  - [x] 1.2 建立 JSON schema 檔案
    - 建立 `schemas/scope-definition.schema.json`（Draft 2020-12）：required fields: scope_name（minLength:1）、features（minItems:1，items 含 feature_id + optional expected_label）；optional: description
    - 建立 `schemas/doubt-record.schema.json`（Draft 2020-12）：required fields: doubt_id（UUID format）、source_node、doubt_type（enum）、current_state（enum: 6 states）、created_by、created_at、updated_at、state_history；optional: assigned_to、resolution
    - 兩個 schema 皆使用 `additionalProperties: false`
    - _Requirements: 17.1, 17.2, 17.3_

  - [ ]* 1.3 撰寫 unit tests：exception classes message format
    - 建立 `tests/unit/core/scope/` 目錄含 `__init__.py`
    - 測試 4 個 exception classes 的自訂 `__init__` 和 message format：
      - `ScopeDefinitionError(file_path, message)` → message 含 file_path
      - `DoubtNotFoundError(doubt_id)` → message 含 doubt_id
      - `InvalidTransitionError(current_state, target_state)` → message 含兩個 state
      - `DoubtTerminalError(doubt_id, current_state)` → message 含 doubt_id + state
    - 不測試 frozen/default factory（Python 語言特性，非業務邏輯）
    - _Requirements: 1.1, 6.1, 7.3_

- [x] 2. 實作 ScopeVerifier（範圍比對引擎）
  - [x] 2.1 建立 core/scope package 並實作 ScopeVerifier
    - 建立 `src/the_door/core/scope/__init__.py`
    - 建立 `src/the_door/core/scope/scope_verifier.py` 含 `ScopeVerifier` class
    - 實作 `verify(scope_def, l1_output) -> ScopeResult`（pure function，無 I/O）：
      - 以 feature_id 字串比對分類：同時存在 → in_scope_complete (✓)；僅 L1 → out_of_scope (⚠)；僅 scope_def → in_scope_incomplete (○)
      - 產生 ScopeResult 含所有 ScopeEntry + ScopeCounts 聚合計數
    - 實作 `parse_scope_definition(file_path) -> ScopeDefinition`：讀取 JSON（encoding="utf-8"）→ jsonschema 驗證 → 轉換為 dataclass
    - 實作 `serialize_scope_definition(scope_def) -> dict`：round-trip 用
    - 實作 Scope Definition 檔案存儲邏輯：
      - 預設存儲路徑：`.the-door/scopes/<scope-name-kebab>.json`
      - scope name → kebab-case 檔名轉換（`scope_name_to_filename()` utility）
      - scope name 查找：從 `.the-door/scopes/` 目錄依 scope name 解析檔案路徑
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 12.1, 13.1_

  - [ ]* 2.2 撰寫 property tests：Scope 比對核心性質
    - **Property 1: Scope Definition Round-Trip** — 任意合法 ScopeDefinition 序列化為 JSON 再解析回來，產生等價物件
    - **Property 2: Scope Partition Completeness** — 任意 ScopeDefinition + L1Output，ScopeResult 包含所有 unique feature_ids 恰好一次；三態集合互斥且聯集等於全集
    - **Property 3: Scope Comparison Idempotence** — 同一輸入執行兩次 verify()，產生完全相同的 ScopeResult
    - 建立 `tests/property/test_scope_properties.py`，含共用 Hypothesis strategies（ASCII-only 字串）
    - **Validates: Requirements 1.7, 2.1, 2.4, 2.5, 2.6, 18.1, 18.2, 18.6**

  - [ ]* 2.3 撰寫 unit tests：ScopeVerifier
    - 建立 `tests/unit/core/scope/test_scope_verifier.py`
    - 測試：具體分類範例（3 種 scope state）、空 L1 output（全部 in_scope_incomplete）、空 scope definition features（schema 驗證拒絕）、重複 feature_id 處理、schema 驗證錯誤（malformed JSON、缺少欄位）、parse error 訊息含檔案路徑、round-trip 序列化
    - 測試存儲路徑：scope name → kebab-case 轉換、預設路徑建立、scope name 查找（存在 + 不存在）
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3_

- [x] 3. 實作 DoubtStore（疑義存儲與狀態機）
  - [x] 3.1 建立 doubt_store.py 並實作 CRUD + 狀態機
    - 建立 `src/the_door/core/scope/doubt_store.py` 含 `DoubtStore` class
    - 定義 `VALID_TRANSITIONS` dict 與 `TERMINAL_STATES` set
    - 實作 CRUD：`create_doubt()`（UUID v4 + discovered 初始狀態）、`get_doubt()`、`list_doubts()`（含篩選 + 排序，暫不含 timeout 檢查）、`get_summary()`、`has_active_doubt()`
    - 實作 `_transition()` 內部方法：驗證合法性 → 建立 StateTransition → 更新 current_state + state_history + updated_at → 持久化
    - 實作狀態轉換：`assign()`、`explain()`、`fix()`、`escalate()`、`resolve_escalation()`
    - 實作序列化：`_serialize_doubt()`、`_deserialize_doubt()`、`_persist()`
    - 所有 JSON I/O 使用 `encoding="utf-8"`（Windows 相容）
    - jsonschema 驗證 doubt-record.schema.json（寫入前驗證 + 載入時驗證）
    - 損壞 JSON 檔案：跳過 + log warning
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 10.1, 10.2, 10.3, 10.4, 10.5, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

  - [x] 3.2 實作 timeout 機制並整合到 list_doubts
    - 實作 `check_timeouts(doubt)`：
      - discovered 狀態：從 `created_at` 算起，超過 discovery_timeout_days → escalated（actor="system_timeout"）
      - investigating 狀態：從 `state_history` 最後一筆 entry 的 `timestamp` 算起，超過 investigation_timeout_days → escalated
      - 手動轉為 investigating 後 discovery timeout 不再適用
      - 使用 UTC 時間戳比較
    - 實作 `_load_timeout_config()`：從 `.the-door/scope-config.json` 載入，預設 discovery=3 天、investigation=7 天；檔案不存在用預設值
    - 整合到 `list_doubts()`：查詢前先對所有 discovered/investigating 疑義執行 timeout 檢查（lazy evaluation）
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ]* 3.3 撰寫 property tests：狀態機、round-trip 與 timeout
    - **Property 7: Doubt Record Round-Trip** — 任意合法 DoubtRecord 序列化為 JSON 再反序列化，產生等價物件
    - **Property 8: State Machine Transition Validity** — 任意合法轉換序列，每次轉換皆在 VALID_TRANSITIONS 中；N 次轉換後 state_history 長度為 N，最後一筆 to_state 等於 current_state
    - **Property 9: Terminal State Completeness** — 任意終態 DoubtRecord，resolution 非 null 且含合法 type/description/resolved_by/resolved_at；不允許進一步轉換
    - **Property 10: Timeout Boundary Correctness** — discovered 狀態超過 discovery_timeout_days → 升級；未超過 → 不升級；investigating 同理；手動轉為 investigating 後 discovery timeout 不再適用
    - 建立 `tests/property/test_doubt_properties.py`，含共用 Hypothesis strategies（ASCII-only 字串）
    - **Validates: Requirements 6.2, 6.4, 6.5, 6.6, 7.6, 8.1, 8.2, 8.5, 18.3, 18.4, 18.5, 18.7**

  - [ ]* 3.4 撰寫 unit tests：DoubtStore
    - 建立 `tests/unit/core/scope/test_doubt_store.py`
    - 測試 CRUD：create doubt（UUID v4 格式、discovered 初始狀態）、get doubt（存在 + 不存在）、list doubts（篩選 by state/type/source_node/active_only、排序 by created_at desc）、summary 聚合計數
    - 測試狀態轉換：assign（discovered→investigating）、explain（investigating→explained）、fix（investigating→fixed）、escalate（discovered/investigating→escalated）、resolve_escalation（escalated→explained/fixed/accepted_risk）
    - 測試錯誤：不合法轉換（InvalidTransitionError）、終態操作（DoubtTerminalError）、doubt 不存在（DoubtNotFoundError）
    - 測試 timeout：discovery timeout 到期自動升級、investigation timeout 到期自動升級（基準為 state_history 最後一筆 timestamp）、手動 assign 取消 discovery timeout、scope-config.json 自訂值、scope-config.json 不存在用預設值
    - 測試 UTF-8 編碼、損壞 JSON 檔案處理、schema 驗證失敗
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 10.1, 10.2, 10.3, 10.4, 10.5, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

- [x] 4. Checkpoint — 驗證 data models、schemas、ScopeVerifier、DoubtStore
  - 執行所有測試確認無 regression：`pytest the_door/tests/ -x`
  - 確認 ScopeVerifier.verify() 為 pure function（無 I/O 副作用）
  - 確認 DoubtStore 狀態轉換表與需求 Req 6 AC2 完全一致

- [x] 5. 實作 ScopeVerifier orchestration（自動建立疑義）
  - [x] 5.1 實作 verify_and_create_doubts() orchestration method
    - 在 `ScopeVerifier` 中實作 `verify_and_create_doubts(scope_def, l1_output, doubt_store) -> tuple[ScopeResult, list[DoubtRecord]]`：
      1. 呼叫 `verify()` 取得 ScopeResult
      2. 對每個 out_of_scope 項目：檢查 `doubt_store.has_active_doubt()`，若無則 `create_doubt(doubt_type="out_of_scope")`
      3. 對每個 in_scope_incomplete 項目：同上，doubt_type="in_scope_incomplete"
      4. 回傳 (ScopeResult, new_doubts)
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [ ]* 5.2 撰寫 property test：自動建立疑義完整性
    - **Property 11: Auto Doubt Creation Completeness** — 任意含 out_of_scope / in_scope_incomplete 的 ScopeResult，verify_and_create_doubts 為每個項目建立恰好一個 DoubtRecord（除非已有活躍疑義）；不建立重複疑義
    - **Validates: Requirements 9.1, 9.2, 9.3**

  - [ ]* 5.3 撰寫 unit tests：verify_and_create_doubts
    - 測試：out_of_scope 自動建立 doubt、in_scope_incomplete 自動建立 doubt、已有活躍 doubt 不重複建立、已有終態 doubt 可建立新 doubt、回傳 new_doubts 清單正確
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 6. 實作 ScopeRenderer（Mermaid 角標徽章 + 摘要面板）
  - [x] 6.1 建立 scope_renderer.py 並實作 ScopeRenderer
    - 建立 `src/the_door/core/scope/scope_renderer.py` 含 `ScopeRenderer` class
    - 定義 `SCOPE_BADGES` dict：in_scope_complete→"✓"、out_of_scope→"⚠"、in_scope_incomplete→"○"
    - 實作 `build_scope_badge(scope_state) -> str`：產生 `"✓<sup>scope</sup>"` 等
    - 實作 `render_scope_summary_panel(scope_result) -> list[str]`：
      - 格式：`%% 📋 {scope_name} 範圍驗核` + 各狀態計數行
      - ✓ 行永遠顯示（即使 count=0）；⚠ 行在 count=0 時省略，非零時附加「（需調查）」後綴；○ 行在 count=0 時省略
    - 實作 `render_l1_with_scope(l1_output, scope_result, ...)` → Mermaid text：
      - 複用 `escape_mermaid_label()`、`resolve_marker_state()`、`MARKER_DEFS` 等既有工具
      - 標籤格式：`"{confidence_icon} {feature_label} {scope_badge}<sup>scope</sup>"`
      - in_scope_incomplete placeholder node：`style node stroke-dasharray:5 5`（inline style，不用 classDef）
      - 不使用 classDef 做 scope 標記
    - 實作 `render_merged_summary_panel(scope_result, diff_result) -> list[str]`：Diff+Scope 合併面板
    - 實作 `render_l1_diff_with_scope(diff_result, scope_result, ...)` → Mermaid text：
      - 標籤格式：`"{confidence_icon} {vuln_symbol} {diff_symbol} {feature_label} {scope_badge}<sup>scope</sup>"`
      - 合併面板取代獨立 diff + scope panels
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 16.1, 16.2, 16.3, 16.4, 16.5_

  - [ ]* 6.2 撰寫 property tests：渲染正確性
    - **Property 4: Scope Badge Rendering Correctness** — 任意 ScopeResult + L1Output，渲染結果含正確 scope badge symbol 在標籤末端；不含 scope classDef；confidence icon 在開頭、scope badge 在末端；placeholder node 有 stroke-dasharray
    - **Property 5: Scope Rendering Backward Compatibility** — 無 scope 結果時，ScopeRenderer 輸出與既有 MermaidRenderer 相同；不改變 confidence/diff/anomaly/vulnerability classDef
    - **Property 6: Summary Panel Count Consistency** — 摘要面板計數與 ScopeResult.counts 一致；✓ 行永遠顯示；⚠/○ 行在 count=0 時省略；面板標題含 scope_name
    - **Property 12: Multi-Indicator Label Format** — 任意含 confidence + vuln + diff + scope 的節點，標籤格式為 `"{confidence_icon} {vuln_symbol} {diff_symbol} feature_label {scope_badge}<sup>scope</sup>"`
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.3, 4.4, 4.5, 16.2, 16.5**

  - [ ]* 6.3 撰寫 unit tests：ScopeRenderer
    - 建立 `tests/unit/core/scope/test_scope_renderer.py`
    - 測試：scope badge 產生（3 種狀態）、summary panel 格式（含/不含 ⚠/○ 行）、placeholder node（虛線邊框 inline style）、merged panel 格式、diff+scope 共存標籤、confidence icon + scope badge 共存、backward compatibility（無 scope 時輸出不變）、Mermaid-unsafe 字元 escaping
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 16.1, 16.2, 16.3, 16.4, 16.5_

- [x] 7. Checkpoint — 驗證 ScopeVerifier orchestration 與 ScopeRenderer
  - 執行所有測試確認無 regression：`pytest the_door/tests/ -x`
  - 確認 scope badge 不使用 classDef（只在 label 層操作）
  - 確認 backward compatibility：無 scope 時輸出與既有 MermaidRenderer 相同

- [x] 8. 實作 Scope CLI 命令
  - [x] 8.1 建立 scope_cmd.py 並實作 scope 子命令群組
    - 建立 `src/the_door/cli/scope_cmd.py`
    - 實作 `scope verify <codebase-path> --scope <scope-file>` 命令：
      - 載入 Scope Definition（支援檔案路徑或 scope name 從 `.the-door/scopes/` 查找）
      - 載入最新 L1 分析產出
      - 執行 `verify_and_create_doubts()`
      - 預設輸出 human-readable summary；`--json` 輸出 ScopeResult JSON；`--render` 輸出帶 scope badges 的 Mermaid 圖
      - 無 L1 分析產出時顯示錯誤訊息
    - 實作 `scope create <scope-name>` 命令：建立空 Scope Definition + 列出可用 feature_ids 供參考
    - 實作 `scope list` 命令：列出 `.the-door/scopes/` 中所有 scope definition
    - 實作 `scope show <scope-name>` 命令：顯示指定 scope definition 內容
    - 所有輸出使用 `encoding="utf-8"`
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 13.1, 13.2, 13.3, 13.4_

  - [x] 8.2 建立 doubt_cmd.py 並實作 doubt 子命令群組
    - 建立 `src/the_door/cli/doubt_cmd.py`
    - 實作 `doubt list`：顯示活躍疑義（doubt_id 縮寫前 8 字元）；支援 `--state`、`--type`、`--json` 篩選
    - 實作 `doubt show <doubt-id>`：顯示完整 DoubtRecord（含 state_history + resolution）
    - 實作 `doubt assign <doubt-id> <assignee>`：discovered → investigating
    - 實作 `doubt resolve <doubt-id> --as <explained|fixed|accepted_risk> --reason <reason>`：
      - 狀態分派邏輯：investigating + explained → explain()；investigating + fixed → fix()；escalated + any → resolve_escalation()；其他組合 → 錯誤
    - 實作 `doubt escalate <doubt-id> --reason <reason>`：手動升級
    - 所有輸出使用 `encoding="utf-8"`
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8_

  - [x] 8.3 在 main.py 註冊新 CLI 命令
    - 在 `src/the_door/cli/main.py` 中 import `scope_group` 和 `doubt_group`
    - 透過 `main.add_command()` 註冊
    - _Requirements: 12.1, 14.1_

  - [ ]* 8.4 撰寫 unit tests：CLI 命令
    - 建立 `tests/unit/cli/test_scope_cmd.py`：測試 scope verify（human/json/mermaid 輸出）、scope create、scope list、scope show、無 L1 分析產出錯誤訊息、scope name 查找
    - 建立 `tests/unit/cli/test_doubt_cmd.py`：測試 doubt list（含篩選 + JSON 輸出）、doubt show、doubt assign、doubt resolve（狀態前提條件分派）、doubt escalate、doubt_id 縮寫、終態錯誤訊息
    - 使用 `click.testing.CliRunner`
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 13.1, 13.2, 13.3, 13.4, 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8_

- [x] 9. Checkpoint — 驗證 CLI 命令
  - 執行所有測試確認無 regression：`pytest the_door/tests/ -x`
  - 手動驗證 `the-door scope --help` 和 `the-door doubt --help` 顯示正確子命令

- [x] 10. 實作 MCP tools
  - [x] 10.1 實作 scope_verify MCP tool
    - 建立 `src/the_door/mcp/tools/scope_verify_tool.py`
    - 定義 `TOOL_SCHEMA`：required: scope_file；optional: codebase_path
    - 實作 `async def execute(arguments) -> dict`：執行 scope verification，回傳 ScopeResult JSON
    - 錯誤回傳遵循既有 MCP 模式：`{"error": True, "message": "..."}`
    - _Requirements: 15.1, 15.5_

  - [x] 10.2 實作 scope_create MCP tool
    - 建立 `src/the_door/mcp/tools/scope_create_tool.py`
    - 定義 `TOOL_SCHEMA`：required: scope_name；optional: codebase_path
    - 實作 `async def execute(arguments) -> dict`：建立空 Scope Definition，回傳檔案路徑
    - _Requirements: 15.2, 15.5_

  - [x] 10.3 實作 doubt_list MCP tool
    - 建立 `src/the_door/mcp/tools/doubt_list_tool.py`
    - 定義 `TOOL_SCHEMA`：optional: codebase_path、state、type
    - 實作 `async def execute(arguments) -> dict`：回傳 DoubtRecord list JSON
    - _Requirements: 15.3, 15.5_

  - [x] 10.4 實作 doubt_transition MCP tool
    - 建立 `src/the_door/mcp/tools/doubt_transition_tool.py`
    - 定義 `TOOL_SCHEMA`：required: doubt_id、target_state、actor；optional: reason、assignee、codebase_path
    - 實作 `async def execute(arguments) -> dict`：執行狀態轉換，回傳更新後的 DoubtRecord JSON
    - _Requirements: 15.4, 15.5_

  - [x] 10.5 在 server.py 註冊新 MCP tools
    - 在 `src/the_door/mcp/server.py` 中 import 4 個新 tool modules
    - 新增 4 個 `Tool(...)` entries 到 `list_tools()`
    - 新增 4 個 dispatch branches 到 `call_tool()`
    - _Requirements: 15.1, 15.2, 15.3, 15.4_

  - [ ]* 10.6 撰寫 unit tests：MCP tools
    - 建立 `tests/unit/mcp/test_scope_doubt_tools.py`
    - 測試：tool registration（4 個新 tools 出現在 list_tools）、scope_verify execute、scope_create execute、doubt_list execute（含篩選）、doubt_transition execute（合法 + 不合法轉換）、錯誤回傳格式
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_

- [x] 11. Checkpoint — 驗證 MCP tools
  - 執行所有測試確認無 regression：`pytest the_door/tests/ -x`
  - 確認 MCP server list_tools 回傳 15 個 tools（既有 11 + 新增 4）

- [x] 12. Final checkpoint — 完整整合驗證
  - Ensure all tests pass（既有 322 + 所有 Phase 3 新增 tests），ask the user if questions arise.
  - 驗證既有 Phase 1、Phase 2、Phase 2.5 功能無 regression
  - 驗證 scope badge 不影響既有 classDef（confidence/diff/anomaly/vulnerability）
  - 驗證 Diff+Scope 合併面板正確取代獨立面板

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties（12 properties from design）
- Unit tests validate specific examples and edge cases
- All file I/O must use `encoding="utf-8"` for Windows compatibility
- Hypothesis strategies use ASCII-only strings（cp950 encoding issue on Windows）
- The design uses Python — no language selection needed
- ScopeVerifier.verify() 為 pure function（無 I/O）；verify_and_create_doubts() 為 orchestration（帶 I/O 副作用）
- ScopeRenderer compose 而非 copy：複用 escape_mermaid_label()、resolve_marker_state()、MARKER_DEFS、DiffRenderer.DIFF_SYMBOLS
- Scope badges 用 label-embedded symbols（`✓<sup>scope</sup>`），不用 classDef
- Placeholder node 用 inline style（`stroke-dasharray:5 5`），不佔用 classDef slot
- Timeout 配置存於 `.the-door/scope-config.json`（project-level，與 user-level config.toml 分離）
- Timeout escalation 用 lazy evaluation（查詢時檢查，非背景 daemon）
- list_doubts 全量掃描在 Phase 3 規模（數十到數百 doubts）可接受
- CLI doubt resolve 有狀態分派邏輯：依 current_state 決定呼叫的 DoubtStore 方法
- Summary panel：✓ 行永遠顯示，⚠/○ 行在 count=0 時省略
