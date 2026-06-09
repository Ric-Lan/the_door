# T5-A（＋T5-P）plan：analyze key-path 終局退場（inline TDD 分區）

> **承接 spec**：`2026-06-08-T5-A-analyze-keypath-retirement-spec.md`（雙審通過、report_renderer 邊界已修）。
> **執行模式**：inline，分 7 區依序刪除；每區跑相關測試子集綠，最後全套＋終局護欄全綠才一次 ff-merge（commit 用 `git commit -F`，C4 active）。
> **環境**：pytest cwd 內層 `the_door/`、`PYTHONUTF8=1`；viewer cwd `viewer/`、`npm test`。
> **性質**：大規模刪除（~60 檔）。刪除型 red＝移碼＋移其專屬測；保留型＝存活測續綠。

---

## 通則
- 每區先 `grep` 複核「被刪符號的存活消費者＝0」再刪（避免誤刪傷存活）。
- C4 active：Bash 勿含 `python -c`/`python x.py` 字面；測試一律 `python -m pytest`。
- 分區順序＝入口層→核心→viewer→模型/provider→doc，使中途 import 斷裂最少；但**全綠判定在最後全套**（per-region verify＝smoke；跨區 import 暫斷屬正常，最後全套＋終局護欄才是 merge 判定——雙審 suggestion）。
- 🔴 **驗證手段（雙審 warning）**：`the-door` console script env-broken、MCP 斷線、worktree 無 `__main__.py` ⟹ **一律用 pytest 斷言**：CLI＝`from the_door.cli.main import main; assert "analyze" not in main.commands`（click group 內省）；MCP＝既有 `_list_tools(server)` 斷言工具集。**不用** live `the-door --help`/list_tools。

## 區 1 — MCP 工具退場（analyze/update/estimate/regenerate）
- 刪檔：`mcp/tools/{analyze_tool,update_tool,estimate_tool,regenerate_tool}.py`。
- `mcp/server.py`：移除 4 import、4 個 `Tool(...)`、4 個 `call_tool` elif。
- 刪測：`tests/unit/mcp/test_analyze_tool.py`、`tests/unit/mcp/tools/test_analyze_tool_context_mode.py`；`tests/unit/mcp/test_tools.py` 移除 analyze/update/estimate/regenerate 註冊測（保留其餘工具測）；`_invocation_recipes.py`／`test_response_envelope_coverage.py` 移除 analyze/update 段（grep 確認其餘工具仍用該 helper）。
- Verify：`python -m pytest tests/unit/mcp/ -q`。

## 區 2 — CLI 命令退場（analyze/update/estimate/regenerate/wizard）
- 刪檔：`cli/{analyze_cmd,update_cmd,estimate_cmd,regenerate_cmd,wizard_cmd}.py`。
- `cli/main.py`：移除 5 import＋5 `add_command`。
- 刪測：`test_analyze_cmd_context_mode.py`、`test_update_cmd_context_mode.py`、`test_wizard_cmd.py`、`test_ui_cmd_wizard.py`；cli `_invocation_recipes.py` 移除 analyze/update/wizard 段（grep 確認其餘命令仍用）。
- **改測**：`test_cli_commands.py`（若斷言命令集含 analyze/update/...）→ 改斷言**不含**已刪命令、仍含 status/extract/diff/ui。**保留** `test_update_from_snapshot.py`（agent-as-LLM 增量、非 key——grep 確認）。
- Verify（pytest 斷言）：`python -m pytest tests/unit/cli/ -q`；另測 `from the_door.cli.main import main; set(main.commands) ∌ {analyze,update,estimate,regenerate,wizard}`。

## 區 3 — core engine 刪除
- 刪檔：`core/reading/batch_reader.py`、`core/llm/prompts.py`、`core/rendering/cost_estimator.py`、`core/pipeline/analyze_pipeline.py`、`core/pipeline/pipeline_orchestrator.py`、`core/pipeline/report_renderer.py`。
- 刪測：`test_batch_reader*`(5)、`test_cost_estimator`、`test_analyze_pipeline_context_mode`、`test_pipeline_orchestrator_*`(3)、`test_reading_properties`／`test_rendering_properties`（grep 確認僅測 batch/cost；若測存活碼則只刪相關段）、integration `test_analyze_pipeline_versioned_structure`/`test_batch_reader_projection`/`test_progress_reporter_e2e`（grep 判定）。
- 複核：`vulnerability_renderer` 不反向依賴 report_renderer（續存活）；`edge_projection` 唯一消費者剩 `edge_residue`。
- Verify：`python -m pytest tests/unit/core/ tests/integration/ -q`。

## 區 4 — viewer 後端（handler/router/job_store 級聯）
- 刪檔：`core/ui/api/handlers/analysis.py`、`core/ui/job_store.py`。
- `core/ui/api/router.py`：移除 `/api/analyze`、`/api/update`、`/api/update/status/{job_id}` 三 route。
- `core/ui/api/context.py`：移除 `job_store_fn`/`job_store`；`core/ui/server.py`：移除 `_job_store` 注入與 switch 邏輯（grep 確認無其它消費）。
- `core/ui/api/error_codes.py`：移除孤兒碼（`job_not_found`/`job_already_running`／analyze 專屬；grep 複核）。
- 刪測：`test_analysis`、`test_handle_post_analyze_adapter`、`test_server_analyze`、job_store 測、router_binding 的 analyze/update/status 測段（保留其餘）。
- Verify：`python -m pytest tests/unit/core/ui/ tests/integration/test_router_binding.py tests/integration/test_e2e_ui_server.py -q`。

## 區 5 — viewer 前端（update/wizard UI）
- 刪檔：`viewer/js/ui-modal.js`、`viewer/js/ui-wizard.js`。
- `viewer/js/api.js`：移除 `postUpdate`/`fetchJobStatus`（及 analyze fetch）。
- `viewer/js/app.js`：移除 wizard/modal wiring；`index.html`：移除 update-modal/wizard DOM；`styles.css`：移除 wizard/modal 樣式（**保留 onboarding 共用樣式**）。
- ✅ 保留 `onboarding.js`/`onboarding.test.js`。
- 刪測：`ui-modal.test.js`、`ui-wizard.test.js`、`wizard-*.test.js`(×8)、`wizard-update-flow.test.js`、`progress-view.test.js`；`api.test.js` 移除 update/analyze fetch 測段。
- Verify：`cd viewer && npm test`（gate=0 red）。

## 區 6 — models 瘦身 ＋ provider 刪除（T5-P）＋ config
- `models/pipeline.py`：刪 `AnalyzeConfig/AnalyzeResult/StepTimeouts/PipelineConfig/PipelineStep/PipelineSummary/PipelineResult/PipelineError/AnalyzeError/CostConfirmationRequired`；保留 `L1ChangeEntry/L2DetailEntry/L3Appendix/DiffChangeExplanation/UpdateReport`。
- `models/__init__.py`：對應更新 export（移除已刪、保留存活）。
- 刪檔：`core/llm/{provider,openai_provider,anthropic_provider,ollama_provider}.py`＋`test_providers.py`。
- `models/config.py`：移除 provider/api-key/model/cost 欄位（逐欄 grep 僅 provider 用才刪）；`test_models_analyze_config` 刪。
- `core/llm/config_manager.py`：`ConfigError`／config 載入——grep 存活消費者；僅 provider 用才清，否則保留。
- Verify：`python -m pytest tests/unit/ -q`＋終局 grep（`create_provider`/`BatchReader`/`provider.py` 全零）。

## 區 7 — CLAUDE.md 改寫 ＋ 全套 ＋ ff-merge
- 改寫 CLAUDE.md：移除 Branch 1a/3「with API key」葉、analyze/update/estimate 命令、API-key 段、MCP 表中已刪工具列；重述唯一路徑＝extract_structure→(agent L1)→edge_residue→snapshot_write（C3 gate 序）；version 更新＝re-extract＋snapshot_write inherit_from＋analyze_changes。grep CLAUDE.md 無殘留 analyze/update/api-key 指引。
- **最終 Verify（全綠才 ff-merge）**：spec §6 終局護欄全部通過（Python 全套 0 failed、viewer 0 failed、grep 全零、--help/list_tools 乾淨、CLAUDE.md grep 乾淨）。

## done-state
- [ ] 4 MCP 工具 / 5 CLI 命令 / analyze 路徑 core / viewer update UI / provider 全刪。
- [ ] models 瘦身正確（Analyze/Pipeline 系刪、UpdateReport 系存活）。
- [ ] `grep create_provider|BatchReader|CostEstimator|analyze_pipeline|PipelineOrchestrator|report_renderer src/`＝零；`provider.py`/4 impl 不存在。
- [ ] Python 全套 0 failed；viewer 0 failed。
- [ ] CLAUDE.md 單一路徑、無 key 殘留。

## 不做（釘樁）
- 不動 agent-as-LLM／diff/scan/scope/timeline 行為；不刪 UpdateReport 系顯示；不碰 onboarding；jq hooks/C2/C5 另刀。
