# T5-A（＋T5-P）spec：analyze key-path 終局退場（零 API-key）

> **日期**：2026-06-08　**狀態**：spec（待雙審 → plan → 雙審 → inline TDD → ff-merge）
> **承接**：丙案種子 §4 基礎原則1（單一路徑）、§10.7 T5（終局刪除）、D2（T5 最後）。使用者裁定＝**最大刀**：全碼一次到底＋併 T5-P＋改 CLAUDE.md。
> **前置已備**：T2(edge_residue)／T5-V(viewer 生成退場)／C3+C4(gate) 皆 merged；agent-as-LLM L1（extract_structure→snapshot_write）為唯一保留生成路。
> **性質**：大規模減法。**終態＝零 API-key 接口、零 provider、零成本閘、零 BatchReader、viewer 純 display**。

---

## 1. 命題與目標

移除整條「有 key 的 analyze/update」路徑，使 The Door 回到種子 §4 基礎原則1 的**單一路徑**（只剩 agent-as-LLM）。同時刪除 provider 核心（T5-P）與成本閘，並改寫權威指南 CLAUDE.md 為單一路徑。

**保留（agent-as-LLM 與純結構/顯示）**：`extract_structure`、`snapshot_write`、`snapshot_patch`、`edge_residue`、`scan`、`diff`、`scope_*`、`doubt_*`、`snapshot_create/list/prune`、`timeline`、`history`、`project_list`、`system_status`、`analyze_changes`、`localize_data_model`、`verify_data_model_contract`、`validate_output`；CLI `status`/`extract`/`diff`/`ui`；viewer 全部 GET display；diff 報告 render（`report_renderer`＋UpdateReport 系模型）。

---

## 2. 移除清單（按區，spike 已驗）

### 2a. MCP 工具（4）— `mcp/server.py` 去註冊（import／list_tools Tool／call_tool elif）＋刪檔
- `analyze_tool.py`（create_provider+BatchReader）
- `update_tool.py`（PipelineOrchestrator）
- `estimate_tool.py`（CostEstimator）
- `regenerate_tool.py`（**已是 stub**，無實質；連帶刪）

### 2b. CLI 命令（5）— `cli/main.py` 去註冊（import＋add_command）＋刪檔
- `analyze_cmd.py`、`update_cmd.py`、`estimate_cmd.py`、`regenerate_cmd.py`、`wizard_cmd.py`
- **保留**：`status`/`extract`/`diff`/`ui`（及其它非 key 命令）。

### 2c. core engine — 刪檔
- `core/reading/batch_reader.py`（唯一 `prompts.py` 消費者）
- `core/llm/prompts.py`
- `core/rendering/cost_estimator.py`
- `core/pipeline/analyze_pipeline.py`
- `core/pipeline/pipeline_orchestrator.py`
- 🔴 **`core/pipeline/report_renderer.py`（移除，雙審 critical 修正）**：它整支 API 建於 `PipelineResult`（update-報告**產生器**），屬 update 路徑；消費者 update_cmd／analysis.py／update_tool 全移除。顯示路徑 catalog.py/view_model.py **直接讀持久化 UpdateReport JSON**、不經此 ⟹ 安全移除。
  - ⚠ 確認 `core/vulnerability/vulnerability_renderer.py` 是 report_renderer 的**被依賴方**（report_renderer import 它），**非**反向；vulnerability_renderer 續存活（scan/diff 顯示）。

### 2d. viewer 後端 — handler／router／job_store 級聯
- 刪 `core/ui/api/handlers/analysis.py`（POST /api/analyze、/api/update、GET /api/update/status）。
- `core/ui/api/router.py`：移除三條 analyze/update/status route（**確認** status 端點無其它用途）。
- 🔴 **JobStore 級聯**：`try_create_job` 唯一生產者＝analysis.py（spike 2.x）⟹ 刪 analysis.py 後 `core/ui/job_store.py` 零生產者 ⟹ **刪 job_store.py**＋`APIContext` 的 `job_store_fn`/`job_store`（`context.py`）＋`server.py` 注入點（`UIServer._job_store`）。確認無其它消費者。
- error_codes：移除僅 analyze/update/job 用的孤兒碼（`job_not_found`/`job_already_running`/analyze 專屬；impl 時 grep 複核）。

### 2e. viewer 前端（唯一正式版 `viewer/`）— 刪 update/wizard UI
- 刪 `js/ui-modal.js`（update modal＋submitUpdate＋polling）、`js/ui-wizard.js`（wizard）。
- `js/api.js`：移除 `postUpdate`/`fetchJobStatus`（及 analyze 相關 fetch）。
- `app.js`：移除 wizard/modal wiring。`index.html`：移除 update-modal／wizard DOM。`styles.css`：移除 wizard/modal 樣式。
- ✅ **保留 `js/onboarding.js`**（`renderOnboardingCard`＝next-action 卡片**顯示**，非 key-bound）。

### 2f. models — 外科瘦身（`models/pipeline.py`＋`models/__init__.py`）
- **刪**：`AnalyzeConfig`、`AnalyzeResult`、`StepTimeouts`、`PipelineConfig`、`PipelineStep`、`PipelineSummary`、`PipelineResult`、`PipelineError`、`AnalyzeError`、`CostConfirmationRequired`。
- ✅ **保留**：`L1ChangeEntry`、`L2DetailEntry`、`L3Appendix`、`DiffChangeExplanation`、`UpdateReport`（**模型存活**——`catalog`/`view_model`/`graph_view_model` 直接讀持久化 UpdateReport JSON 顯示；**產生器 report_renderer 移除**，兩者解耦）。
- `models/__init__.py` 對應更新 export 集（移除已刪型別、保留存活型別）。

### 2g. provider 核心（T5-P）— 刪檔＋config 瘦身
- 刪 `core/llm/provider.py`、`openai_provider.py`、`anthropic_provider.py`、`ollama_provider.py`。
- `models/config.py`（`TheDoorConfig`）：移除 provider/api-key/model/cost 欄位（`default_provider`、`*_api_key`、`*_model`、`ollama_url`、`cost_warning_threshold`、`timeout_seconds`/`max_retries` 若僅 provider 用）。**保留**非 provider 欄位（impl 時逐欄驗）。
- `config_manager.py`：`ConfigError` 是否仍被保留路徑用？（grep；diff handler 已於 T5-V 移除其用；若僅 provider 用則連帶清，否則保留）。

### 2h. CLAUDE.md — 改寫成單一路徑
- 移除 Branch 1a/3 的「with API key」葉、`analyze`/`update`/`estimate` 命令列、API-key 設定段、決策樹中 provider 相關分支（37 處）。
- 重述為：唯一路徑＝`extract_structure → (agent 產 L1) → edge_residue → snapshot_write`（C3 gate 已強制序）；version 更新＝重 extract＋`snapshot_write inherit_from`＋`analyze_changes`；diff＝`diff`/viewer 顯示。保留 status/extract/ui/diff/MCP 表（去除已刪工具列）。

---

## 3. 測試 fallout（~25 Python ＋ ~13 JS）
- **刪**：`test_analyze_tool*`、`test_analyze_pipeline*`、`test_pipeline_orchestrator*`、`test_batch_reader*`(5)、`test_cost_estimator`、`test_providers`、`test_analysis`、`test_handle_post_analyze_adapter`、`test_server_analyze`、`test_analyze_cmd_context_mode`、`test_models_analyze_config`、`test_reading_properties`、`test_rendering_properties`(若僅測 cost/analyze)、`_invocation_recipes`（analyze recipe 段）、`test_response_envelope_coverage`（analyze 段）、`test_progress_reporter_e2e`/`test_batch_reader_projection`/`test_analyze_pipeline_versioned_structure`(integration)。
- **JS 刪**：`ui-modal.test.js`、`ui-wizard.test.js`、`wizard-*.test.js`(×8)、`wizard-update-flow.test.js`、`progress-view.test.js`、`api.test.js`(update/analyze fetch 段)。**保留** `onboarding.test.js`。
- **保留並驗**：所有 agent-as-LLM／結構／diff-display 測續綠（零回歸護欄）。
- ⚠ **逐檔複核**：上列「(若…)」者 impl 時 grep 確認是否真孤兒，避免誤刪仍測存活碼者。

---

## 4. 範圍邊界
**In**：§2 全部（含 T5-P provider 刪除、CLAUDE.md 改寫）。
**Out**：
- ❌ 既有 jq hooks 轉 python（C3+C4 F1，另刀）。
- ❌ C2 checklist schema／C5 README（另刀）。
- ❌ 改 agent-as-LLM／diff/scan/scope 任何行為（純保留）。
- ❌ 動 `report_renderer`/UpdateReport 系顯示行為（保留；僅在確認耦合 analyze 型時才最小調整）。

---

## 5. 已發現問題 / findings（執行時必須承認）
- **F1（JobStore 級聯）**：刪 analyze/update ⟹ JobStore 零生產者 ⟹ 連 job_store.py／context.job_store／status 端點／JS polling 一併死。**不可只刪 analyze 而留 JobStore**（會留死碼）。
- **F2（models 外科性）**：`models/pipeline.py` 一半型別存活（diff 報告顯示）。**禁止整檔刪**；逐型別判生死。
- **F3（report_renderer＝移除，雙審已定）**：它建於 `PipelineResult`、消費者全移除、顯示路徑讀 JSON 不經它 ⟹ **移除**（非保留）。UpdateReport 系**模型**保留。
- **F4（config/ConfigError 殘留）**：`ConfigError`、config 欄位可能被非 provider 路徑引用；逐一 grep，僅 provider 專屬才刪。
- **F5（onboarding 存活）**：`onboarding.js` 是顯示非 key-bound，**保留**（勿因關鍵字誤刪）。
- **F6（CLAUDE.md 權威性）**：留著舊 analyze/update 敘述＝文件說謊；必須同刀改寫，否則違反「文件→工具→程式引導」一致性。
- **F7（C4 自擋）**：本 session C4 active；commit 用 `git commit -F`，Bash 勿含 `python -c`/`python x.py` 字面。

---

## 6. 驗收 / TDD（紅→綠；刪除型 cut）
- **刪除型 red**＝移除碼＋移除其專屬測；**保留型**＝既有存活測續綠。
- 分區驗證（每區跑相關子集綠）：MCP(`tests/unit/mcp/`)／CLI(`tests/unit/cli/`)／viewer(`tests/unit/core/ui/`、integration ui)／core/models／全套。
- **終局護欄（全綠才 merge）**：
  - `grep -rn create_provider src/` → 零；`provider.py`/4 impl 不存在。
  - `grep -rn "BatchReader\|CostEstimator\|analyze_pipeline\|PipelineOrchestrator" src/` → 零。
  - MCP `list_tools` 不含 analyze/update/estimate/regenerate；CLI `--help` 不含 analyze/update/estimate/regenerate/wizard。
  - `python -m pytest -q` 全套 0 failed；viewer `npm test` 0 failed（gate=0 red）。
  - `the-door status`/`extract`/`diff`/`ui` 與 agent-as-LLM MCP 鏈 smoke 不破。
  - CLAUDE.md 無殘留 analyze/update/api-key 指引（grep 複核）。

---

## 7. Forward-coherence（終態）
- 達成種子 §4 基礎原則1：**單一 agent-as-LLM 路徑、零 API-key**。C3 gate 強制其序、C4 封逃生口 ⟹ 控制經結構在唯一路徑上閉環。
- `edge_projection`（T2 工具化存活）在 BatchReader 刪後唯一消費者＝`edge_residue` 工具——順序鎖（種子 §9.4）最終兌現。
- 剩餘後續：C2(checklist coverage 升級 C3)／C5(README)／F1(jq hooks)／viewer 純-display 後續打磨。

---

## 8. 雙審待查點（給 reviewer）
- §2c report_renderer 是否耦合 analyze 型（F3）；§2g config 哪些欄位/ConfigError 真孤兒（F4）。
- §2d JobStore 級聯是否漏消費者（context/server/JS）；status 端點移除後 JS polling 是否全清。
- §2f models 生死分界是否正確（UpdateReport 系存活、Analyze/Pipeline 系刪）。
- §2e onboarding 與 wizard 的 DOM/CSS 共用元素拆分（勿誤刪 onboarding 用到的共用樣式）。
- §2h CLAUDE.md 改寫是否完整移除 key 敘述、且不破壞 agent-as-LLM 指引正確性。
- 切分風險：本刀 ~60 檔，是否分區分次 commit（仍同一 ff-merge 前全綠）以降風險。
