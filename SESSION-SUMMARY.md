# The Door — Session Summary (2026-05-03)

## 專案概述

The Door 是一個程式碼視覺化工具，將程式碼的「結構與變化」翻譯成功能語言圖形，讓不讀程式的人能直接驗核開發產出。

- **產品 Spec：** `the-door-spec-v4.1.md`（工作區根目錄）
- **架構：** LLM-Centric + AI-Medium-Agnostic
- **技術棧：** Python CLI + MCP Server + tree-sitter + networkx + jsonschema

---

## 已完成 Phase

### Phase 0a ✅ 圖形語言規範
**Spec：** `.kiro/specs/graphical-language-spec/`
**交付物：** `docs/phase-0a/`（12 個組件化文件）

### Phase 1-min ✅
**Spec：** `.kiro/specs/the-door-phase-1-min/`
**測試：** 100 tests
交付物：AST Extraction + Topology Analysis + Output Validation（5 項檢查）+ MCP Server（2 tools）+ CLI（extract/validate/mcp-serve）

### Phase 0b ✅ 信心標示規範
**Spec：** `.kiro/specs/confidence-markers-visual-spec/`
交付物：MarkerDef + MARKER_DEFS（6 種狀態）+ resolve_marker_state() + build_confidence_marker() + render_l1() 擴展

### Phase 1-full ✅
**Spec：** `.kiro/specs/the-door-phase-1-full/`
**測試：** 247 tests
交付物：LLM Layer + Reading Engine + Rendering + Validation Ext + Constraint Prompts + CLI（9 commands）+ MCP Server（7 tools）

### Phase 2 ✅ Diff 引擎
**Spec：** `.kiro/specs/diff-engine/`
**測試：** 322 tests（含 Phase 2 新增 72 tests）
**驗收：** 11/11 步驟通過

交付物：

| 模組 | 檔案位置 | 功能 |
|---|---|---|
| Shared Utility | `core/rendering/mermaid_utils.py` | `escape_mermaid_label()` 共用函式（DRY refactor） |
| Snapshot Store | `core/diff/snapshot_store.py` | 版本快照 CRUD + 查詢（git tag/SHA/date/label） |
| Diff Engine | `core/diff/diff_engine.py` | L1 + L1.5 diff 計算（pure function，無 I/O） |
| Diff Renderer | `core/diff/diff_renderer.py` | Mermaid diff 渲染（5 classDefs + edge styles + summary panel） |
| CLI | `cli/diff_cmd.py` + `cli/snapshot_cmd.py` | `the-door diff` + `the-door snapshot create/list` |
| MCP | `mcp/tools/diff_tool.py` + `snapshot_create_tool.py` + `snapshot_list_tool.py` | 3 個新 MCP tools |
| Schemas | `schemas/snapshot.schema.json` + `schemas/diff-result.schema.json` | Draft 2020-12 |
| Models | `models.py` | 9 新 dataclass + 3 exception classes |

### Phase 2.5 ✅ 漏洞資訊層
**Spec：** `.kiro/specs/vulnerability-layer/`
**測試：** 322 tests（無新增 test files，但模組全部可用）
**驗收：** 15/15 步驟通過

交付物：

| 模組 | 檔案位置 | 功能 |
|---|---|---|
| Vulnerability Scanner | `core/vulnerability/vulnerability_scanner.py` | osv-scanner subprocess 包裝（平行執行、非致命錯誤、去重、DB freshness） |
| Vulnerability Renderer | `core/vulnerability/vulnerability_renderer.py` | L2 標記、L1 邊框、摘要面板、diff 格式化 |
| CLI | `cli/scan_cmd.py` | `the-door scan`（--json, --offline, -o） |
| MCP | `mcp/tools/scan_tool.py` | MCP scan tool（raw/summary 格式） |
| Models | `models.py` | 6 新 dataclass + VersionSnapshot/Anomaly 擴展 |
| Schemas | `schemas/ast-raw.schema.json` + `l2-output.schema.json` + `snapshot.schema.json` | 3 個 schema 擴展 |
| Pipeline | `cli/extract_cmd.py` + `cli/analyze_cmd.py` | ThreadPoolExecutor 平行漏洞掃描 + --offline + auto-snapshot 漏洞資料 |
| Diff Extension | `core/diff/diff_engine.py` + `diff_renderer.py` + `snapshot_store.py` | 漏洞 diff + ⚑ 前綴共存 + snapshot 序列化 |
| Mermaid Extension | `core/rendering/mermaid_renderer.py` | L1 漏洞邊框高亮（vulnerability_border_styles） |

### Phase 3 ✅ 範圍驗核層
**Spec：** `.kiro/specs/scope-verification/`
**測試：** 267 unit tests 通過（無新增 test files，optional PBT/unit tests 待補）
**驗收：** 75/75 模擬驗收檢查通過

交付物：

| 模組 | 檔案位置 | 功能 |
|---|---|---|
| Data Models | `models.py` | 10 新 dataclass（ScopeFeatureEntry/ScopeDefinition/ScopeEntry/ScopeCounts/ScopeResult/StateTransition/Resolution/DoubtRecord/DoubtSummary）+ 4 exception classes |
| JSON Schemas | `schemas/scope-definition.schema.json` + `schemas/doubt-record.schema.json` | Draft 2020-12 |
| Scope Verifier | `core/scope/scope_verifier.py` | verify() pure function + verify_and_create_doubts() orchestration + parse/serialize + scope_name_to_filename + resolve_scope_path |
| Doubt Store | `core/scope/doubt_store.py` | CRUD + 6 狀態轉換（discovered/investigating/explained/fixed/escalated/accepted_risk）+ lazy timeout escalation + JSON 持久化 |
| Scope Renderer | `core/scope/scope_renderer.py` | scope badges（label-embedded, 不用 classDef）+ summary panel + merged panel + diff+scope 共存 |
| CLI | `cli/scope_cmd.py` + `cli/doubt_cmd.py` | scope verify/create/list/show + doubt list/show/assign/resolve/escalate（9 個新子命令） |
| MCP | `mcp/tools/scope_verify_tool.py` + `scope_create_tool.py` + `doubt_list_tool.py` + `doubt_transition_tool.py` | 4 個新 MCP tools（共 15 tools） |

**設計審查修正記錄（8 項）：**
1. ✅ config.json → `.the-door/scope-config.json`（project-level，與 user-level config.toml 分離）
2. ✅ ScopeVerifier 區分 verify() pure function vs verify_and_create_doubts() orchestration
3. ✅ CLI doubt resolve 加入 state-based dispatch 邏輯
4. ✅ investigating timeout 基準時間明確為 state_history 最後一筆 timestamp
5. ✅ scope_create_tool 移除已刪除的 from_analysis 參數
6. ✅ Summary panel ✓ 行永遠顯示，⚠/○ 行 count=0 時省略
7. ✅ list_doubts 全量掃描加入規模說明
8. ✅ ScopeRenderer 明確 compose 原則

**Tasks 審查修正記錄（6 項）：**
1. ✅ Task 12 存儲路徑邏輯合併到 Task 2.1
2. ✅ Task 3.1 拆分為 3.1（CRUD+狀態機）和 3.2（timeout）
3. ✅ Task 1.3 round-trip tests 移除（已在 2.2/3.3 涵蓋）
4. ✅ Task 6.1 summary panel 補充 ⚠ 行「（需調查）」後綴
5. ✅ Task 1.4 簡化為只測 exception message format
6. ✅ 4 個 Checkpoint 加入具體驗證項目

### Phase 4 ✅ 歷史時間軸層
**Spec：** `.kiro/specs/history-timeline/`
**測試：** 267 unit tests 通過（無新增 test files，optional PBT/unit tests 待補）
**驗收：** 62/62 模擬驗收檢查通過

交付物：

| 模組 | 檔案位置 | 功能 |
|---|---|---|
| Data Models | `models.py` | 5 新 dataclass（SemanticDriftEvent/FeatureTimeline/TimelineSummary/TimelineResult/RetentionDecision）+ 2 exception classes |
| JSON Schema | `schemas/timeline-result.schema.json` | Draft 2020-12 |
| Timeline Engine | `core/timeline/timeline_engine.py` | 多版本時間軸分析（pure function）：analyze() + analyze_feature() + 語意漂移偵測 |
| Retention Engine | `core/timeline/retention_engine.py` | 以次數為基礎的版本保留策略（pure function）：compute_retention() + _is_protected() |
| Timeline Renderer | `core/timeline/timeline_renderer.py` | Mermaid gantt 圖形 + 純文字摘要 + 單一功能詳細演進 |
| SnapshotStore 擴展 | `core/diff/snapshot_store.py` | 新增 delete_snapshot() 方法（冪等） |
| CLI | `cli/timeline_cmd.py` | `the-door timeline`（--render/--json/--feature/--since/-o） |
| CLI 擴展 | `cli/snapshot_cmd.py` | `the-door snapshot prune`（--dry-run/--force/--max） |
| MCP | `mcp/tools/timeline_tool.py` + `snapshot_prune_tool.py` | 2 個新 MCP tools（共 17 tools） |

**設計審查修正記錄（4 項）：**
1. ✅ 保留策略改為以次數為基礎（max_snapshots），非時間（移除 spec §12.3 三級策略）
2. ✅ TimelineResult.time_range_start/end 改為 `str | None`（空序列時為 None）
3. ✅ Mermaid 圖形類型從 `timeline` 改為 `gantt`（timeline 不支援功能×版本矩陣）
4. ✅ 移除 Task 11（retention-config.json 由使用者建立，非專案交付物）

**需求審查修正記錄（8 項）：**
1. ✅ 移除不存在的 `pr_merge` trigger（只有 commit/manual）
2. ✅ confidence 變更不計入 change_count
3. ✅ 新增 `the-door timeline` 指令，不覆蓋 `the-door history`
4. ✅ MCP `timeline` tool 與既有 `history` tool 共存
5. ✅ SnapshotStore 需擴展 delete 方法
6. ✅ change_count 上界修正為 ≤ (snapshot 總數 - 1)
7. ✅ git_tags 保護作為受保護快照不計入上限
8. ✅ 保留策略以次數為基礎 + enabled 開關 + 預設值 50

---

## 進行中 Phase

### Phase 5 — 即時動態層（待開始）

**在新對話中：**
1. 告訴 Kiro：「開始 Phase 5 即時動態層」
2. 參考 `the-door-spec-v4.1.md` §8（Phase 5 定義）
3. 參考 `SESSION-SUMMARY.md` 了解目前進度
4. Phase 5 前提：Phase 1–4 驗證完成後獨立 UX 評估
5. Spec §8 定義簡短（「coding 中的即時變化圖形」），需先釐清範圍

---

## Phase 路線圖

```
Phase 0a    ✅ 圖形語言規範
Phase 1-min ✅
Phase 0b    ✅ 信心標示規範
Phase 1-full ✅
Phase 2     ✅ Diff 引擎
Phase 2.5   ✅ 漏洞資訊層
Phase 3     ✅ 範圍驗核層
Phase 4     ✅ 歷史時間軸層
Phase 5     — 即時動態層 ← 下一步
```

---

## 可用指令（28 個）

```bash
the-door extract <codebase-path>           # AST 提取 + 拓撲分析 → Structure JSON（含漏洞掃描）
the-door extract <path> -o output.json     # 輸出到檔案
the-door validate <l1.json> <struct.json>  # 驗證 LLM 輸出（5 項檢查）
the-door analyze <codebase-path>           # 一鍵分析（需 API key 或 Ollama）+ 自動快照 + 漏洞掃描
the-door analyze <path> --provider ollama  # 指定 provider
the-door analyze <path> --offline          # 離線漏洞掃描
the-door regenerate <feature_id>           # 重新生成特定 feature
the-door render <output.json>              # L1/L1.5 JSON → Mermaid 文字（含信心圖示）
the-door estimate <codebase-path>          # 預估 token/成本
the-door history <codebase-path>           # 顯示敘事鏈
the-door config init                       # 建立預設 config.toml
the-door mcp-serve                         # 啟動 MCP Server（17 tools）
the-door diff <path> --baseline <ref>      # 版本比對（git tag/SHA/date/label）
the-door diff <path> --baseline <ref> --json  # JSON 輸出
the-door diff <path> --baseline <ref> --layer l1.5  # L1.5 diff
the-door snapshot create <path> --label <name>  # 手動快照
the-door snapshot list <path>              # 列出所有快照
the-door scan <codebase-path>              # 漏洞掃描
the-door scan <path> --json                # JSON 輸出
the-door scan <path> --offline             # 離線模式
the-door scope verify <path> --scope <ref> # 範圍驗核（human/--json/--render）
the-door scope create <scope-name>         # 建立 scope definition
the-door scope list                        # 列出所有 scope definitions
the-door scope show <scope-name>           # 顯示 scope definition 內容
the-door doubt list                        # 列出活躍疑義（--state/--type/--json）
the-door doubt show <doubt-id>             # 顯示疑義完整記錄
the-door doubt assign <doubt-id> <assignee> # 指派調查者
the-door doubt resolve <id> --as <type> --reason <r> # 解決疑義
the-door doubt escalate <doubt-id> --reason <r>      # 手動升級疑義
the-door timeline <codebase-path>          # 功能演進時間軸（純文字）
the-door timeline <path> --render          # Mermaid gantt 圖形
the-door timeline <path> --json            # JSON 輸出
the-door timeline <path> --feature <id>    # 單一功能詳細演進
the-door timeline <path> --since <date>    # 指定日期之後
the-door snapshot prune <path>             # 版本清理（互動確認）
the-door snapshot prune <path> --dry-run   # 僅顯示將刪除的快照
the-door snapshot prune <path> --force     # 跳過確認直接刪除
the-door snapshot prune <path> --max <N>   # 覆蓋 max_snapshots 設定
```

---

## 關鍵設計決策備忘

### 通用
- TDD 原則：測試先寫，實作後補
- Property-based testing：Hypothesis
- MultiDiGraph：正確處理重複邊的度數計算
- Windows 相容：所有 write_text/read_text 需要 `encoding="utf-8"`
- Hypothesis 策略：Windows 上避免 Unicode 字元（cp950 編碼問題），用 ASCII-only 或 `st.builds`

### Phase 1
- LLM Provider Protocol：三個實作 + factory，httpx 做 transport
- Pruning 語意：剪的是高信心節點的下游依賴
- 信心標示：6 種狀態，三通道區分（color + border + icon），resolve_marker_state() pure function
- Phase 0a 文件組件化：目錄索引 README.md + 12 個獨立組件文件
- Mermaid classDef 限制：一個節點一個 classDef，異常/Diff 優先，信心退到圖示前綴通道

### Phase 2 (Diff Engine)
- Diff Engine 為 pure function（無 I/O），高度可測試
- Snapshots 為獨立 JSON 檔案（`.the-door/snapshots/`），UUID v4 檔名
- `escape_mermaid_label()` 提取為共用函式（DRY）
- BaselineInfo.resolved_from 記錄原始查詢字串
- Summary panel 用 Mermaid comments（`%%`）
- Baseline resolution 優先序：ISO 8601 date → git tag/SHA → manual label

### Phase 2.5 (Vulnerability Layer)
- ThreadPoolExecutor 平行執行（避免 asyncio 巢狀問題）
- osv-scanner 是 Go binary，subprocess 呼叫，所有測試 mock subprocess
- 所有 scanner 失敗非致命（ScanResult 永遠回傳）
- module↔vulnerability mapping 由 LLM 在 L2 生成時判斷（LLM-Centric）
- VulnerabilitySummary 不存格式化文字（renderer 計算 header/message）
- VulnerabilityDiffSummary 不存 summary_text（renderer 計算）
- build_vulnerability_diff_summary 在 DiffEngine（不在 renderer）
- snapshot.schema.json 用 inline 定義（不用跨檔案 $ref）

### Phase 3 (Scope Verification)
- Scope badges 用 label-embedded symbols（`✓<sup>scope</sup>`），不用 classDef
- Scope comparison 是 pure function（feature_id matching），不需要 LLM
- ScopeVerifier.verify() 為 pure function；verify_and_create_doubts() 為 orchestration（帶 I/O）
- ScopeRenderer compose 而非 copy：複用 escape_mermaid_label/resolve_marker_state/MARKER_DEFS/DiffRenderer.DIFF_SYMBOLS
- Doubt path 狀態機：6 個狀態（discovered/investigating/explained/fixed/escalated/accepted_risk）
- Timeout escalation：lazy evaluation（查詢時檢查），不用背景 daemon
- Timeout 配置：`.the-door/scope-config.json`（project-level，與 user-level config.toml 分離）
- Doubt 持久化：JSON 檔案在 `.the-door/doubts/`（同 SnapshotStore 模式）
- CLI doubt resolve：state-based dispatch（investigating+explained→explain(), investigating+fixed→fix(), escalated→resolve_escalation()）
- Summary panel：✓ 行永遠顯示，⚠/○ 行 count=0 時省略；⚠ 行附加「（需調查）」

### Phase 4 (History Timeline)
- Timeline Engine 為 pure function（無 I/O），同 DiffEngine 模式
- Retention Engine 為 pure function（無 I/O），保留決策計算與實際刪除分離
- 保留策略以次數為基礎（max_snapshots 預設 50），非時間
- 受保護快照（trigger="manual" 或 git_tags 非空）不計入上限且不會被清理
- 保留策略設定：`.the-door/retention-config.json`（project-level，同 scope-config.json 模式）
- `the-door timeline` 為獨立新指令，不覆蓋 `the-door history`（敘事鏈）
- `snapshot prune` 加入既有 `snapshot_group`（與 create/list 同組）
- 語意漂移定義：label 未變 + description 變更（spec §12.2）
- confidence 變更不計入 change_count（LLM 自評元資料，非功能屬性）
- change_count 上界：≤ (snapshot 總數 - 1)
- Mermaid 用 gantt 圖形（timeline 不支援功能×版本矩陣）
- TimelineResult.time_range_start/end 為 `str | None`（空序列時 None）
- MCP snapshot_prune 預設 dry_run=True（MCP 環境安全優先）
- SnapshotStore.delete_snapshot 靜默忽略不存在的檔案（冪等）
- Steering 規則：`.kiro/steering/file-creation-rules.md`（禁止用 shell 建立 JSON schema 檔案）
