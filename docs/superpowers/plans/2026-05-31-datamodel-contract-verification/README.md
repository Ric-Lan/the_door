# 資料模型契約驗證 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增「資料模型契約驗證」旁路層：Tier 0 全本地零 token 定位資料模型觸點；Tier 1 由 agent-as-LLM 正規化欄位集、The Door 做雙向契約 diff。不上 LLM 翻譯路徑、不改 extraction/ASTNode。

**Architecture:** 照 `core/vulnerability/` 旁路分析層範式新增同儕子套件 `core/datamodel/`（models + hints config + localizer + verifier + renderer），再 append 一個 CLI 指令與兩個 MCP 工具。全部純函式/值物件，逐單元 TDD。

**Tech Stack:** Python 3.10+、dataclass(frozen)、click（CLI）、MCP（`async def execute` + `TOOL_SCHEMA`）、pytest（`asyncio.run` 測 async、`click.testing.CliRunner` 測 CLI、`tmp_path` 測檔案）。

**Spec:** [`docs/superpowers/specs/2026-05-31-datamodel-contract-verification-design.md`](../../specs/2026-05-31-datamodel-contract-verification-design.md)

---

## 路徑框架（重要，避免找錯目錄）

- **所有指令一律在內層套件目錄 `the_door/` 下執行**（即 `cd the_door` 後）。該目錄含 `src/`、`tests/`、`pyproject.toml`（`testpaths=["tests"]`）。
- 各 task「**Files:**」區段列的是 **repo 根相對路徑**（`the_door/src/...`、`the_door/tests/...`）；對應到指令的內層 cwd，去掉開頭的 `the_door/` 即為 `src/...` / `tests/...`（`git add` 指令已用內層相對路徑）。
- 覆蓋率一律用 **import-name 形式**（`--cov=the_door.core.datamodel.X`），與 cwd 無關（editable install），不要用檔案路徑。

## 紀律（全任務適用）

- **測試覆蓋率 100%**：每個分支（命中/不命中、空輸入、錯誤路徑）都要有對應斷言。
- **TDD**：每單元紅→綠→commit。先寫會失敗的測試、跑它確認失敗、再寫最小實作。
- **最小架構異動**：**不改** `extraction/`、`ASTNode`、`language_configs.py`、L1/L2/L3、snapshot。
- **不寫 framework-specific schema parser**；格式容忍度交給 agent。
- fixture 只放輸入（建構 `ExtractionResult` / 欄位集 / tmp 檔案樹），主程式產結果、test 斷言結果。

## 既有 API（已 grep 驗證，直接用，勿臆測別的）

- `the_door.models.ASTNode(node_id, type, name, file, language, decorators=[], parameters=[], return_type=None, docstring=None, comments=[])`（frozen dataclass，無行號欄位）。
- `the_door.models.ExtractionResult(nodes=[...], edges=[...])`。
- `the_door.core.extraction.ast_extractor.ASTExtractor().extract(codebase_path: str) -> ExtractionResult`。
- CLI：`@click.command("name")` + `@click.argument` / `@click.option`，於 `cli/main.py` `main.add_command(x_cmd)` 註冊。
- MCP 工具模組：頂層 `TOOL_SCHEMA: dict` + `async def execute(arguments: dict) -> dict`；於 `mcp/server.py` `list_tools` 加 `Tool(name=..., inputSchema=mod.TOOL_SCHEMA)`、`call_tool` 加 `elif name == "...": return await self._dispatch_tool(mod, arguments)`、頂部 `from the_door.mcp.tools import <mod>`。
- `the_door.mcp.tools._response_envelope.wrap(payload: dict, project_path: Path) -> dict`（注入 next_actions；mutate + 回傳）。
- async 工具測法：`asyncio.run(mod.execute({...}))`。

## 檔案地圖

| 檔案 | 責任 | Task |
|---|---|---|
| `core/datamodel/__init__.py` | 空 package marker | 01 |
| `core/datamodel/models.py` | 值物件 dataclasses | 01 |
| `core/datamodel/datamodel_hints.py` | 跨語言啟發式 config + 判定函式 | 01 |
| `core/datamodel/datamodel_localizer.py` | Tier 0 定位器 | 02 |
| `core/datamodel/contract_verifier.py` | Tier 1 雙向契約 diff | 03 |
| `core/datamodel/datamodel_renderer.py` | 報告/JSON 呈現 | 04 |
| `cli/verify_datamodel_cmd.py` + `cli/main.py`(append) | CLI 指令 | 05 |
| `mcp/tools/localize_datamodel_tool.py` + `verify_contract_tool.py` + `mcp/server.py`(append) | MCP 工具 | 06 |

## Task 清單（依責任分類）

| Task | 內容 | 依賴 |
|---|---|---|
| 01 | models + hints config（值物件 + 判定函式） | 無 |
| 02 | localizer（Tier 0，純結構） | 01 |
| 03 | contract_verifier（Tier 1 欄位集 diff） | 01 |
| 04 | renderer（報告 + JSON） | 01 |
| 05 | CLI 指令（接 02+04） | 02, 04 |
| 06 | MCP 兩工具（接 02+03+04） | 02, 03, 04 |

**Critical path：** 01 → (02 ∥ 03 ∥ 04) → 05 → 06。02/03/04 只依賴 01，可並行。

## 完整資料流（驗收對照）

```
verify-data-model <path>            → Tier 0：ASTExtractor.extract → DataModelLocalizer.localize → render_localization
verify-data-model <path> --deep     → Tier 0 + 印候選檔清單 + 給 agent 的 Tier 1 指令（不呼叫 LLM）
MCP localize_data_model             → Tier 0 序列化（候選檔 + 節點名）
MCP verify_data_model_contract      → Tier 1：agent 給兩份欄位集 → ContractVerifier.verify → 寫 .the-door/datamodel/contract.json + 回摘要
```
