# Implementation Plan: Phase 5 即時動態層（Realtime Dynamic Layer）

## Overview

在 Phase 1–4 的完整分析能力之上，實作版本更新自動管線（Update Pipeline）與互動式逐層展開報告（Update Report）。實作順序依循依賴關係：資料模型 + JSON schema → analyze pipeline 提取 + analyze_cmd 重構 → pipeline orchestrator → report renderer → CLI 指令 → MCP tool → 最終整合。每個 task 遵循 TDD：property/unit tests 作為 sub-tasks 伴隨實作。Property-based tests 使用 Hypothesis 搭配 `@settings(max_examples=100)` 和 ASCII-only 字串以確保 Windows 相容性。

Phase 5 是 orchestration layer，不新增任何分析引擎。所有分析能力完全委派給 Phase 1–4 的既有模組。

## Tasks

- [x] 1. 定義 Phase 5 資料模型與 JSON schema
  - [x] 1.1 新增 pipeline + report dataclasses 到 models.py
    - 在 `src/the_door/models.py` 新增 `# Phase 5: Realtime Dynamic Layer (Pipeline + Report) models` 區段
    - 新增 11 個 frozen dataclasses：`AnalyzeConfig`、`AnalyzeResult`、`StepTimeouts`、`PipelineConfig`、`PipelineStep`、`PipelineSummary`、`L1ChangeEntry`、`L2DetailEntry`、`L3Appendix`、`UpdateReport`、`PipelineResult`
    - 新增 3 個 exception classes：`PipelineError`（含 step_name）、`AnalyzeError`、`CostConfirmationRequired`（含 estimated_cost + total_tokens）
    - 遵循既有慣例：`frozen=True`、`field(default_factory=...)` 用於可變預設值
    - _Requirements: 1.2, 1.5, 2.5, 2.6, 4.1, 4.2, 4.3, 4.4, 4.5, 7.1, 7.3, 11.1, 11.2, 11.3, 11.4, 12.4_

  - [x] 1.2 建立 update-report JSON schema
    - 使用 fsWrite 建立 `the_door/schemas/update-report.schema.json`（Draft 2020-12）
    - 定義必要欄位：report_version（string）、generated_at（string, date-time）、pipeline_summary（object，含 old_path, new_path, total_duration_ms, steps array）、l0_summary（string）、l1_changes（array）、l2_details（array）、l3_appendix（object）
    - pipeline_summary.steps 項目：step_name（string）、status（enum: completed/failed/skipped）、duration_ms（integer|null）、error_message（string|null）
    - l1_changes 項目：feature_id（string）、change_type（enum: added/removed/attribute_changed/dependency_changed）、risk_flags（array of enum strings）、current_label（string）、baseline_label（string|null）
    - l2_details 項目：feature_id、change_type、current_label、current_description、baseline_label、baseline_description、scope_state（enum|null）、related_vulnerabilities（array）、affected_relations（array）
    - l3_appendix：diff_result_json（object|null）、scope_result_json（object|null）、timeline_result_json（object|null）、pipeline_summary（object|null）
    - interrupted（boolean, default false）
    - _Requirements: 7.2, 11.1, 11.2, 11.3, 11.4_

  - [ ]* 1.3 撰寫資料模型 unit tests
    - 建立 `the_door/tests/unit/core/pipeline/` 目錄含 `__init__.py`
    - 測試 frozen immutability、default factory values、field types
    - 測試 exception classes：PipelineError 含 step_name、CostConfirmationRequired 含 estimated_cost + total_tokens
    - _Requirements: 11.1, 11.2, 11.3_

- [x] 2. 提取 Analyze Pipeline 核心函式
  - [x] 2.1 建立 core/pipeline 套件並實作 analyze_pipeline.py
    - 建立 `src/the_door/core/pipeline/__init__.py`
    - 建立 `src/the_door/core/pipeline/analyze_pipeline.py`
    - 從 `cli/analyze_cmd.py` 提取分析編排邏輯為可複用核心函式：
      - `run_analyze_pipeline(codebase_path, config, *, progress_callback)` → AnalyzeResult
      - 流程：計算檔案指紋 → 載入 config → 並行 AST extraction + vulnerability scan → 拓撲分析 → 成本估算 → LLM batch reading → 自動建立 snapshot → 回傳 AnalyzeResult
    - 實作 `compute_file_fingerprint(codebase_path)` → dict[relative_path → (size, mtime)]
      - 只包含 AST 可處理的原始碼檔案（同 ASTExtractor 的檔案發現邏輯）
    - 實作 `validate_snapshot_fingerprint(stored, current)` → bool
      - 比對 key set + 每個檔案的 size + mtime
    - 指紋儲存在 `.the-door/fingerprints/<snapshot_version_id>.json`，與 snapshot 分開儲存
    - _Requirements: 1.3, 1.5, 14.4, 14.5, 14.6_

  - [x] 2.2 重構 analyze_cmd.py 委派給 analyze_pipeline
    - 修改 `src/the_door/cli/analyze_cmd.py`，將分析編排邏輯委派給 `run_analyze_pipeline()`
    - CLI 層只負責：解析 Click 參數 → 組裝 AnalyzeConfig → 呼叫 run_analyze_pipeline() → 處理 CostConfirmationRequired（互動確認）→ 顯示結果
    - 確保重構後所有既有 267 個 tests 仍然通過（行為等價）
    - _Requirements: 1.3_

  - [ ]* 2.3 撰寫 analyze_pipeline unit tests
    - 建立 `the_door/tests/unit/core/pipeline/test_analyze_pipeline.py`
    - 測試：compute_file_fingerprint 正確計算路徑+大小+mtime
    - 測試：validate_snapshot_fingerprint 一致時回傳 True、不一致時回傳 False
    - 測試：檔案新增/刪除/修改均視為不一致
    - 測試：run_analyze_pipeline 呼叫正確的底層模組（mock）
    - 測試：漏洞掃描失敗不影響分析結果
    - 測試：CostConfirmationRequired 在超過閾值時拋出
    - _Requirements: 1.3, 14.4, 14.5, 14.6_

- [x] 3. Checkpoint — 驗證資料模型、schema、analyze pipeline 提取
  - 確保所有 tests 通過（既有 267 + 新增 tests），詢問使用者是否有問題。
  - 驗證 analyze_cmd 重構後行為等價（既有 tests 無 regression）。

- [x] 4. 實作 Pipeline Orchestrator
  - [x] 4.1 實作 pipeline_orchestrator.py
    - 建立 `src/the_door/core/pipeline/pipeline_orchestrator.py`
    - 實作 `PipelineOrchestrator` class：
      - `run(config, *, progress_callback)` → PipelineResult
      - 步驟執行順序：(1) analyze_old → (2) analyze_new → (3) diff → (4) scope_verify → (5) timeline → (6) report
    - 實作 `_run_analyze_step(path, step_name, config)` → (PipelineStep, AnalyzeResult | None)
      - 計算當前檔案指紋 → 檢查既存指紋 → 指紋一致則使用既存 snapshot → 否則執行 run_analyze_pipeline()
      - 儲存新的指紋檔案（以 snapshot.version_id 為檔名）
    - 實作 `_run_diff_step(old_snapshot, new_snapshot)` → (PipelineStep, DiffResult | None)
    - 實作 `_run_scope_step(scope_name, new_path, new_l1_output: L1Output)` → (PipelineStep, ScopeResult | None)
      - 注意：`new_l1_output` 型別為 `L1Output`（不是 dict），與 `ScopeVerifier.verify()` 簽名一致
    - 實作 `_run_timeline_step(new_path)` → (PipelineStep, TimelineResult | None)
    - 錯誤處理：analyze 失敗 → 管線終止；diff/scope/timeline 失敗 → 標記 failed，繼續執行
    - 路徑驗證：不存在、非目錄、相同路徑 → PipelineError
    - SIGINT 處理：signal handler，完成當前步驟後停止，設定 interrupted=True
    - 步驟超時：StepTimeouts 配置（analyze=300s, 其他=30s）
    - 進度回報：`[步驟 N/M] 正在執行：<step_name>...` / `[步驟 N/M] ✓ <step_name>（耗時 X.Xs）` / `[步驟 N/M] ✗ <step_name> — <error_message>`
    - 管線開始前顯示預估總耗時（基於檔案數量）
    - 管線完成時輸出總結（總耗時、成功/失敗/跳過步驟數）
    - skip_timeline=True → timeline 步驟 skipped；scope_name=None → scope_verify 步驟 skipped
    - force_reanalyze=True → 跳過指紋驗證，強制重新分析
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.2, 3.3, 3.4, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 12.4, 12.5, 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

  - [ ]* 4.2 撰寫 property test：Step status partition completeness（Property 1）
    - **Property 1: Step status partition completeness**
    - 對任何 PipelineResult，completed + failed + skipped 步驟數等於管線定義的總步驟數
    - 建立 `the_door/tests/property/test_pipeline_properties.py`，含共用 Hypothesis 策略
    - **Validates: Requirements 2.5, 12.4**

  - [ ]* 4.3 撰寫 property test：Analyze failure terminates pipeline（Property 2）
    - **Property 2: Analyze failure terminates pipeline**
    - 若 analyze 步驟失敗，PipelineResult 不含 diff_result、scope_result、timeline_result
    - **Validates: Requirements 2.1**

  - [ ]* 4.4 撰寫 property test：Non-critical failure continuation（Property 3）
    - **Property 3: Non-critical failure continuation**
    - diff/scope/timeline 失敗時，其他成功步驟的結果仍保留
    - **Validates: Requirements 2.2, 2.3, 2.4**

  - [ ]* 4.5 撰寫 property test：Skip logic correctness（Property 4）
    - **Property 4: Skip logic correctness**
    - analyze/diff 永不 skipped；skip_timeline=True → timeline skipped；scope_name=None → scope_verify skipped
    - **Validates: Requirements 3.2, 3.3, 3.4**

  - [ ]* 4.6 撰寫 pipeline orchestrator unit tests
    - 建立 `the_door/tests/unit/core/pipeline/test_pipeline_orchestrator.py`
    - 測試：步驟執行順序驗證（mock 所有底層模組）
    - 測試：analyze 失敗後管線終止，後續步驟全部 skipped
    - 測試：diff/scope/timeline 失敗後繼續執行
    - 測試：skip_timeline / scope_name=None 的跳過行為
    - 測試：相同路徑拒絕（PipelineError）
    - 測試：force_reanalyze 強制重新分析
    - 測試：SIGINT 處理（模擬信號）
    - 測試：步驟超時處理
    - 測試：進度訊息格式
    - 測試：既存 snapshot 指紋驗證通過時跳過重新分析
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.2, 3.3, 3.4, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 12.4, 12.5, 14.1, 14.2, 14.3_

- [x] 5. Checkpoint — 驗證 Pipeline Orchestrator
  - 確保所有 tests 通過，詢問使用者是否有問題。

- [x] 6. 實作 Report Renderer
  - [x] 6.1 實作 report_renderer.py
    - 建立 `src/the_door/core/pipeline/report_renderer.py`
    - 實作 `ReportRenderer` class：
      - `render_markdown(result: PipelineResult) -> str`：互動式 Markdown 報告
        - 目錄（Table of Contents）
        - L0 摘要（`<details open>`）：一句話結論
        - L1 變更總覽（`<details open>`）：風險優先排序（⚠ 超出範圍 → 🔴⚑ 漏洞 → 🔵 語意漂移 → 🟢 新增 → 🟠 修改 → 🔴 移除）
        - L2 細節展開（`<details>`）：每個功能的變更前後對比
        - L3 技術附錄（`<details>`）：完整 JSON + 管線統計
        - 每個可展開區段含 expand_hint
        - 失敗步驟顯示錯誤訊息（非空白）
        - interrupted=True 時顯示中斷提示
      - `render_json(result: PipelineResult) -> dict`：結構化 JSON 報告
        - 符合 update-report.schema.json
        - 含 report_version、generated_at、pipeline_summary、l0_summary、l1_changes、l2_details、l3_appendix
      - `render_mermaid(result: PipelineResult) -> str`：Mermaid 圖形報告
        - 複用 DiffRenderer.render_l1_diff() 生成 diff 圖形
        - 複用 ScopeRenderer.render_l1_diff_with_scope() 疊加 scope badges（若有）
        - 漏洞標記用文字摘要（複用 VulnerabilityRenderer.format_summary_header()），不用節點邊框
        - 頂部合併摘要面板（Mermaid comment %%）
      - `_build_l0_summary(result)` → str：一句話結論
        - 格式：「本次更新：新增 N 個功能、修改 M 個功能、移除 K 個功能」+ 風險提示
        - 無異常時：「本次更新在預期範圍內，未發現異常」
      - `_build_l1_changes(result)` → list[L1ChangeEntry]：風險優先排序
      - `_build_merged_summary_panel(result)` → list[str]：合併摘要面板
    - 使用功能語言（「功能」而非「節點」或「模組」）
    - 複用 escape_mermaid_label 共用函式
    - UTF-8 編碼寫入檔案
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 12.1, 12.2, 12.5, 15.1, 15.2, 15.3_

  - [ ]* 6.2 撰寫 property test：L0 summary count consistency（Property 5）
    - **Property 5: L0 summary count consistency**
    - L0 摘要中的數字與 l1_changes 計數完全一致；無風險項目時顯示正面結論
    - 建立 `the_door/tests/property/test_report_properties.py`，含共用 Hypothesis 策略
    - **Validates: Requirements 4.2, 5.4, 12.5**

  - [ ]* 6.3 撰寫 property test：L1 risk-first ordering（Property 6）
    - **Property 6: L1 risk-first ordering**
    - l1_changes 按風險優先排序：out_of_scope → vulnerability → semantic_drift → added → modified → removed
    - **Validates: Requirements 4.3, 5.1, 5.2, 5.3, 5.5**

  - [ ]* 6.4 撰寫 property test：Report-DiffResult count consistency（Property 7）
    - **Property 7: Report-DiffResult count consistency**
    - l1_changes 中各 change_type 計數與 DiffResult.summary 完全一致
    - **Validates: Requirements 12.1**

  - [ ]* 6.5 撰寫 property test：Report-ScopeResult flag consistency（Property 8）
    - **Property 8: Report-ScopeResult flag consistency**
    - l1_changes 中 out_of_scope risk_flag 的 feature_ids 與 ScopeResult 中 out_of_scope 的 feature_ids 完全一致
    - **Validates: Requirements 12.2**

  - [ ]* 6.6 撰寫 property test：JSON schema conformance（Property 9）
    - **Property 9: JSON schema conformance**
    - render_json() 輸出通過 update-report.schema.json 驗證
    - **Validates: Requirements 7.2, 11.1, 11.2, 11.3**

  - [ ]* 6.7 撰寫 property test：JSON report round-trip（Property 10）
    - **Property 10: JSON report round-trip**
    - UpdateReport 序列化為 JSON 再反序列化回來產生等價物件
    - **Validates: Requirements 7.4, 11.4**

  - [ ]* 6.8 撰寫 property test：Failed step visibility in report（Property 11）
    - **Property 11: Failed step visibility in report**
    - 失敗步驟在 Markdown 和 JSON 報告中均有失敗提示，不為空白
    - **Validates: Requirements 15.3**

  - [ ]* 6.9 撰寫 report renderer unit tests
    - 建立 `the_door/tests/unit/core/pipeline/test_report_renderer.py`
    - 測試：Markdown 格式 — details/summary 標籤、open 屬性、TOC、expand_hint
    - 測試：JSON 格式 — schema 驗證、round-trip、必要欄位
    - 測試：Mermaid 格式 — 複用 DiffRenderer、合併摘要面板、漏洞文字摘要
    - 測試：L0 摘要 — 數字正確性、正面/負面結論
    - 測試：L1 排序 — 風險優先（out_of_scope → vulnerability → semantic_drift → added → modified → removed）
    - 測試：部分結果 — 失敗步驟的提示文字（非空白）
    - 測試：interrupted 標記的顯示
    - 測試：功能語言使用（「功能」而非「節點」）
    - 測試：UTF-8 編碼
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 12.1, 12.2, 12.5, 15.1, 15.2, 15.3_

- [x] 7. Checkpoint — 驗證 Report Renderer
  - 確保所有 tests 通過，詢問使用者是否有問題。

- [x] 8. 實作 CLI 指令
  - [x] 8.1 實作 update CLI 指令
    - 建立 `src/the_door/cli/update_cmd.py`
    - 實作 `@click.command("update")`：
      - `old_path` 位置引數（`click.Path(exists=True)`）
      - `new_path` 位置引數（`click.Path(exists=True)`）
      - `--scope <scope-name>`：scope definition 名稱
      - `--json`：輸出結構化 JSON 報告
      - `--render`：輸出 Mermaid diff 圖形
      - `--offline`：漏洞掃描離線模式
      - `--skip-timeline`：跳過時間軸更新
      - `--provider <name>`：LLM provider 覆蓋
      - `--yes` / `-y`：跳過成本確認
      - `-o <file>`：輸出到檔案（UTF-8）
      - `--force-reanalyze`：強制重新分析
    - CLI 層負責：組裝 PipelineConfig（含 AnalyzeConfig）→ 呼叫 PipelineOrchestrator.run() → 選擇 render 格式 → 輸出
    - 進度訊息輸出到 stderr，報告內容輸出到 stdout
    - 處理 CostConfirmationRequired（click.confirm 互動確認）
    - 處理 PipelineError（stderr 錯誤訊息，exit code 1）
    - 驗證 old_path ≠ new_path（相同路徑顯示錯誤）
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9, 9.10, 9.11, 9.12_

  - [x] 8.2 在 main.py 註冊 update 指令
    - 在 `src/the_door/cli/main.py` 中 import `update_cmd`
    - 透過 `main.add_command(update_cmd)` 註冊
    - _Requirements: 9.1_

  - [ ]* 8.3 撰寫 update CLI unit tests
    - 建立 `the_door/tests/unit/cli/test_update_cmd.py`
    - 使用 click.testing.CliRunner 測試：
      - 預設 Markdown 輸出
      - --json 旗標
      - --render 旗標
      - --scope 旗標
      - --offline 旗標
      - --skip-timeline 旗標
      - --provider 旗標
      - --yes 旗標
      - -o 檔案輸出
      - --force-reanalyze 旗標
      - 無效路徑錯誤訊息
      - 相同路徑錯誤訊息
      - 進度訊息輸出到 stderr
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9, 9.10, 9.11, 9.12_

- [x] 9. Checkpoint — 驗證 CLI 指令
  - 確保所有 tests 通過，詢問使用者是否有問題。

- [x] 10. 實作 MCP Tool
  - [x] 10.1 實作 update MCP tool
    - 建立 `src/the_door/mcp/tools/update_tool.py`
    - 定義 `TOOL_SCHEMA`：required: old_path, new_path；optional: scope_name, offline_vuln（default false）, skip_timeline（default false）, output_format（enum: json/markdown/mermaid, default json）
    - 實作 `async def execute(arguments)` → 對應格式的 UpdateReport
    - MCP 環境下 AnalyzeConfig.skip_cost_confirm 預設為 True
    - 錯誤處理：無效路徑、相同路徑、分析失敗 → 結構化錯誤回應
    - _Requirements: 13.1, 13.2_

  - [x] 10.2 在 server.py 註冊 update tool
    - 在 `src/the_door/mcp/server.py` 中 import `update_tool`
    - 新增 1 個 `Tool(...)` 到 `list_tools()`（共 18 tools）
    - 新增 1 個 dispatch branch 到 `call_tool()`
    - _Requirements: 13.1_

  - [ ]* 10.3 撰寫 MCP update tool unit tests
    - 建立 `the_door/tests/unit/mcp/test_update_tool.py`
    - 測試：tool 註冊（list_tools 含 update tool）
    - 測試：execute 各 output_format 選項（json/markdown/mermaid）
    - 測試：錯誤回應格式（無效路徑、相同路徑）
    - 測試：skip_cost_confirm 預設為 True
    - _Requirements: 13.1, 13.2_

- [x] 11. Final checkpoint — 完整整合驗證
  - 確保所有 tests 通過（既有 267 + 所有新增 Phase 5 tests），詢問使用者是否有問題。
  - 驗證 Phase 1–4 既有功能無 regression。
  - 驗證 `the-door update` 指令可正常執行。
  - 驗證 MCP `update` tool 可正常回應。
  - 驗證既有 17 個 MCP tools 仍正常運作。

## Notes

- 標記 `*` 的 tasks 為 optional，可跳過以加速 MVP
- 每個 task 引用具體 requirements 以確保可追溯性
- Checkpoints 確保增量驗證
- Property tests 驗證設計文件中的 11 個正確性屬性
- Unit tests 驗證具體範例和邊界條件
- 所有檔案 I/O 必須使用 `encoding="utf-8"` 以確保 Windows 相容性
- Hypothesis 策略使用 ASCII-only 字串（Windows cp950 編碼問題）
- 設計使用 Python — 無需語言選擇
- Phase 5 是 orchestration layer，不新增任何分析引擎
- analyze_pipeline 從 analyze_cmd 提取後，CLI 和 Pipeline_Orchestrator 共用同一份邏輯
- 檔案指紋獨立儲存在 `.the-door/fingerprints/`，不修改 VersionSnapshot schema
- PipelineConfig 用 composition 包含 AnalyzeConfig，避免欄位重複
- MCP update tool 預設 JSON 格式、skip_cost_confirm=True
- 進度訊息輸出到 stderr，報告內容輸出到 stdout
- SIGINT 處理：完成當前步驟後停止，生成部分報告
- Mermaid 漏洞標記用文字摘要（摘要面板），不用節點邊框（Phase 5 不觸發 L2 分析）
