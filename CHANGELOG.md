# Changelog

All notable changes to The Door are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

---

## v1.7.3 — 2026-06-13

立體化結構（撥離索引＋分層消費通道）全週期 ＋ viewer provenance 標示。
皆純加法，契約版號不動（`SNAPSHOT_CONTRACT_VERSION` 仍 `"1"`）。

### Added
- **立體化結構（縱軸＝粒度）**：新套件 `core/structure_view/` ——
  `region_partition`（頂層段聚類＋流向矩陣）／`peel_membrane`（撥離膜，enum 僅
  `one_way_consumer`、閾值 50:1＋min50、證據附稽核；禁可達性訊號）／`node_view`
  （L2 統一 `node_id` 定址、零 join）／`structure_index`（L0 索引＋artifact 落
  `.the-door/structure-view/`：index.json＋regions/<id>.json.gz＋structure.full.json.gz）。
- **`extract_structure` 回 L0 撥離索引**（自身專案首口 2.8M→3.5K 字元）；全量結構
  落 structure-view artifact，按區域/批次drill-down 消費。
- **`validate_output` 可選 `codebase_path`**：從 structure-view artifact 讀全量結構
  （`structure_json` inline 仍優先），補齊 agent-as-LLM 鏈的程式端驗證接縫。
- **viewer 版本選單 provenance 標示**：`/api/snapshots` 附 bare `provenance`
  （current/legacy/unknown，`derive_provenance` 單一詞彙來源）；前端對舊契約快照標
  「（舊契約）」、pre-stamp 快照標「（無契約戳）」，current 不加字。

### Changed
- CLAUDE.md agent-as-LLM 鏈步驟 1 改 L0 索引消費法（讀索引→按 peel 標示裁決→
  區域 artifact drill-down→批次順序規劃閱讀）。

### Notes
- 消費層驗收（自己驗自己）：四筆失敗實錄 F-a..F-d 全數不復發；「翻譯更正確/更省」
  效力誠實標 **medium**（單樣本自驗，不升格通用）。詳
  `docs/superpowers/specs/2026-06-12-stereoscopic-structure-acceptance.md`。

---

## v1.7.2 — 2026-06-12

dogfood 暴露問題的逐項處理：低信心交叉驗證引導（新）＋ Cut1 operational-classification ＋
C7 繼承不譯 gate ＋ cp950 IO 修正。皆純加法，契約版號不動（`SNAPSHOT_CONTRACT_VERSION` 仍 `"1"`）。

### Added
- **非-high 信心交叉驗證引導**：每個 MCP 工具回應（`_response_envelope.wrap` 正常路徑）附一條
  靜態、建議式的 `verification_guidance`，指向已註冊證據工具（第一版＝`extract_structure`）。
  定位＝infra **surface 不 judge**（不掃 payload、不偵測 confidence；觸發與否由消費端 LLM 自評）。
  「觸發處境」＝非-high 信心＝{未評估(None) ∪ 中信心 ∪ 低信心}，引導分清兩成因（未評估→補做評估；
  中/低→補強證據）。checkpoint envelope 不附。新模組 `core/guidance/verification_guidance.py`。
- **`analyze_changes` unmapped_nodes 三桶摘要（Cut1）**：非操作性 unmapped_nodes 改以
  `core/classification/operational_classifier.py` 摘要，payload 大幅縮減（v170 −71%）。

### Changed
- **`server.py` 工具名單一來源**：抽 `_build_tools()` ＋衍生 `REGISTERED_TOOL_NAMES` frozenset，
  供「引導工具名 ∈ 已註冊集」invariant 可列舉驗證（Tool 定義內容不變、僅搬移）。

### Fixed
- **C7 繼承不譯 gate（丙案軌2）**：`snapshot_write` 對未變動 feature 的 description 立 immutability
  gate（inherited_hashes sha256；不確定 fail-open）。
- **cp950 非-ASCII 輸出崩潰**：強制 UTF-8 stdout/stderr，避免 Windows cp950 終端輸出非-ASCII 時崩潰。

### Notes
- 純加法／IO／packaging 性質，snapshot schema 不動 → `SNAPSHOT_CONTRACT_VERSION` 仍 `"1"`。
- 引導的 efficacy 層（「實質改變 LLM 行為→更忠實翻譯」）誠實標 **low 信心**、未洗成定論
  （spec §6.2 方法論：efficacy＝LLM@分級信心，非 phantom 驗證）。

---

## v1.7.1 — 2026-06-11

修 v1.7.0 的發版級 packaging bug：pip 非-editable 安裝後找不到 JSON schemas，核心流程壞掉。

### Fixed
- **JSON schemas 未隨 wheel 打包 ＋ runtime 路徑寫死 dev 佈局**：實機測 v1.7.0 非-editable
  `pip install` 時 `snapshot_write` 報 `[Errno 2] ... snapshot.schema.json` 找不到。雙重病灶
  ＝①schemas 放在套件外（`the_door/schemas/`，非 `src/the_door/` 內）→ build wheel 排除；
  ②4 個載入點用 `Path(__file__).parent×5 / "schemas"` 假設 dev/editable 佈局，裝起來少 `src/`
  一層 → overshoot 到 `<python>/Lib/schemas`。pytest 對源碼樹永遠綠、過去都用 editable install
  ⟹ 從未被非-editable install 暴露。修正：`git mv` 11 schema 進 `src/the_door/schemas/`；
  `snapshot_store` / `doubt_store` / `scope_verifier` / `schema_check` 改用
  `importlib.resources.files("the_door") / "schemas"`（dev+裝起來皆 robust）；pyproject 加
  `[tool.setuptools.package-data]` ＋ 新增 `MANIFEST.in`。影響面＝snapshot_write／validate／
  doubt／scope 等所有 schema 載入。新增 `tests/unit/test_schema_packaging.py`（路徑解析＋打包設定釘樁）防退化。

### Notes
- 純 packaging/路徑修正，schema 內容不動 → 契約版號不動（`SNAPSHOT_CONTRACT_VERSION` 仍 `"1"`）。
- Python 1420 passed / 0 failed；viewer 532 passed / 0 red；wheel 實證含 11 schema。

---

## v1.7.0 — 2026-06-10

「丙案＝控制經結構強制」campaign：把執行模型重塑成「工具化 + blocking hook gate」，讓 agent 走唯一一條結構性強制的 agent-as-LLM 路徑；並據此**終局移除所有 API-key 介面**（provider、`analyze` / `update` 鏈、provider 設定）。終態＝零 API key、單一路徑。軌2 的執行序 gate 已全到位＝C2（checklist schema）＋C3（snapshot_write gate）＋C4（擋原生 code-exec）＋C6（跑完回報）＋C5（單一權威）＋水平推廣（snapshot_patch）＋staleness（mtime+size 指紋）。

### Added
- **`edge_residue` MCP 工具（T2）**：零-token／零-key 的確定性工具，把邊噪音殘餘（高 fanout 過濾、動態 dispatch caller 級聚合）落盤 `.the-door/edge-residue.json`，供 agent 觀察；同時是 L1 鏈的免-key 補件。
- **執行序 blocking-hook gate（C3 + C4）**：`snapshot_write` 在目標 codebase 無前置 artifact 前被 deny、stderr 教學指回 `edge_residue`（兌現 extract→residue→write 順序鎖）；co-require 的 C4 擋臨時 inline-python／獨立 `.py` 腳本繞過 MCP 工具的逃生口。放行 `python -m`(pytest／the_door／pip)／pytest／pip／git／the-door。
- **checklist schema gate（C2）**：把 C3 的「artifact 存在性」升級成結構化、versioned 的執行 checklist（`.the-door/checklist.json`，掛 `SNAPSHOT_CONTRACT_VERSION`）。`edge_residue` 完成時自動蓋章並記錄 covered node 集；C3 gate 改驗三件＝stage 已蓋章＋contract_version 當前＋**node-coverage**（要寫的 `source_nodes` ⊆ 已涵蓋集，validity 讀法）。新增 `core/checklist.py`（單一真相來源）＋ drift-pin（hook 字面 vs 模組常數，含負向驗證）。完整 staleness（刪除/原地改）由下方 staleness 條目兌現。
- **chain-report ledger（C6）**：`snapshot_write` 成功時在 checklist 蓋 `snapshot_write` stage，並把執行 ledger（各關 `stamped_at` ＋ 摘要，剝除龐大 `covered_nodes`／`source_files` 只留計數）嵌入工具回應，讓使用者有事實基礎核對「各關是否執行／產物／結果」、非黑箱（基礎原則 7「跑完回報」）。蓋章 fail-soft（只 `except OSError`——snapshot 已落盤、不因事後紀錄失敗謊報工作失敗）＋記憶體補本防「payload 有 version_id、ledger 卻缺 snapshot_write」自相矛盾。純資訊層、零 gate 改動。
- **entry-authority（C5）**：修正工具自動生成的 guidance（StateInspector ＋ NextActionSuggester，即 `the-door status` 的權威）涵蓋 `edge_residue` 關——原本「有 structure、無 snapshot」直接建議 `snapshot_write`，agent 機械跟隨 `next_actions` 會撞 C3 deny；現 `next_actions` 正確涵蓋 `edge_residue`，且 C3 deny 訊息指回單一可讀權威（`system_status` 工具／`the-door status`）。刻意**不建靜態 README checklist**（手寫 checklist＝漂移點；既有自動生成 guidance 即單一權威）。
- **水平推廣 gate（snapshot_patch）**：把 C2／C3 的 node-coverage gate 擴到第二個 `source_nodes` 寫入口 `snapshot_patch`（經 `source_nodes_by_feature`）。共用同一 hook、統一原則「gate node-writes」＝metadata-only patch 豁免、`tool_name` 缺失安全退化成 engage（過度 gate、絕不漏 gate）。證據裁定唯讀工具（`diff`／`analyze_changes`／`extract_structure`／`snapshot_create`）已自驗、不 gate（避免冗餘軟層）。`.claude/settings.json` 加 `snapshot_patch` matcher。
- **staleness 偵測（mtime+size 指紋）**：兌現 C2 deferred 的完整 staleness。`edge_residue` 蓋章時記錄每個已發現檔案的 `(mtime_ns, size)` 指紋（`stages.edge_residue.source_files`）；C3 gate 新增第 4 道檢查，**stat-only 比對（不重抽 AST）**偵測檔案**刪除**或**原地修改**（node_id 不變）後仍寫 snapshot 的 staleness → deny、教先重跑 `edge_residue`。`.the-door/*.json` 因副檔名過濾不入指紋集 → 無自產物 self-deny。殘餘 honest-deferred＝新增未追蹤檔未被引用、對抗式 mtime 重置。
- **`python -m the_door` 進入點**：新增 `the_door/__main__.py` 轉接 console-script 進入點，讓開發環境的 MCP 設定可用 `python -m the_door mcp-serve`。
- **退場護欄測試**：`test_retired_keypath_surfaces.py` 釘樁已退場的 CLI 命令與 MCP 工具不得復現。

### Changed
- **唯一路徑文件化**：`CLAUDE.md`、`README` 改寫成單一 agent-as-LLM 路徑（extract_structure → agent 產 L1 → edge_residue → snapshot_write），移除所有「需要 API key」敘述與決策分叉。
- **既有 jq-based guard hook 轉 python**：本機 jq 系統性缺席會讓 jq hook 靜默失效；prototype-edit 守衛與 `the-door serve` 守衛改為純 python（與 C3／C4 一致、jq-free、fail-open）。

### Removed
- **LLM provider 全棧（T5-P）**：`core/llm/{provider,openai_provider,anthropic_provider,ollama_provider}.py`、`config_manager.py`、`TheDoorConfig` / `CostEstimate` 模型、`the-door config` 命令、`SystemState.has_api_key` / `api_provider` 偵測。The Door 不再內建任何 provider 或 API-key 設定。
- **analyze key-path 全棧（T5-A）**：`the-door analyze` / `update` / `estimate` / `regenerate` CLI 命令與同名 MCP 工具；`analyze_pipeline` / `pipeline_orchestrator` / `report_renderer` / `batch_reader` / `cost_estimator` / prompts 等核心執行器；viewer 後端 analyze/update/status 端點與 job store。
- **viewer 生成路退場（T5-V）**：L2／層解釋／diff 解釋三條 key-bound POST 生成路與前端 onboarding 精靈（wizard）／update modal；viewer 改為純顯示（保留所有 GET 與 onboarding 卡）。
- **dead code 清理**：`response_parser.py` + `ParseResult`（provider 移除後成孤兒）。
- models facade：79 → 68 個型別（移除 analyze/pipeline 執行型別、provider 設定型別、ParseResult）。

### Notes
- **測試基線**：Python 1407 passed / 0 failed、viewer 532 passed / 0 failed。
- **契約版本不 bump**（仍 `"1"`）：本 campaign 的 schema 變更皆純加法（checklist `stages`／`covered_nodes`／`source_files`、edge_residue 蓋章欄）；移除 `SystemState.has_api_key` / `api_provider` 屬於 `/api/status` 輸出的減法變更，已同步更新契約測試。符合 `docs/contract-versioning.md` §6。

---

## v1.6.5 — 2026-06-07

「乙案＝膜模型」campaign：重塑輸出對消費端的意義表徵——意義由結構承載、缺值誠實化（不自鑄中點/等級）、膜詞彙單一來源；並完成 viewer 人類面整膜與測試基線清理。

### Added
- **Snapshot 契約版本戳**：`SNAPSHOT_CONTRACT_VERSION`（初值 `"1"`）＋ `VersionSnapshot.contract_version` 出生戳；provenance（current/legacy/unknown）經 diff／analyze_changes／snapshot_list MCP 投影給 agent。維護紀律＝`docs/contract-versioning.md`。
- **膜 primitive 多變體**（SignalPosition／NoisePosition／RelayedVerdict／PresenceFlagPosition…）：於 agent 邊界投影 confidence／scope／diff_state／change_type／risk_flags／vulnerability 等軸的封閉集意義；各軸詞彙單一來源 module。
- **Viewer 膜詞彙 drift-guard**：`tests/membrane-vocabulary.test.js` 讀 checked-in schema enum 斷言 viewer 消費點涵蓋封閉集，＋反向掃描防新消費點漏接。

### Changed
- **缺值誠實化（fact-finder，不自鑄）**：confidence 缺值 → `null`（schema `oneOf`+null），不再自鑄 `medium`；vulnerability severity／cvss 缺值 → `null`（不捏 CVSS 中點，保留 OSV evidence）；edge-noise／scope／diff_state 缺值退 `NoisePosition(indeterminate)`。
- **人類面渲染誠實化**：viewer graph／list／diff-explanation 對未評估 confidence 渲染「未評估」中性態，停止 `|| 'high'`／`?? 'medium'`／`|| 'low'` 謊報等級。
- **Viewer 圖層**：cytoscape → DOM grid 遷移殘留死碼清除（移除未用的 cytoscape 機制與 373KB lib、zoom／mermaid DOM）。

### Fixed
- diff-explanation confidence 缺值謊報「低信心」→「未評估」。
- viewer 測試基線 8 個 pre-existing red 綠化（對齊已重構的 grid／notes-tab production，非環境問題）。

### Notes
- **契約版本不 bump**（仍 `"1"`）：本次 schema 變更皆純加法（confidence／severity 容 `null`、新增 `contract_version`／`evidence` 欄），舊快照既有值意義不變、缺欄誠實 load 成 `unknown`——符合 `docs/contract-versioning.md` §3。

---

## v1.6.0 — 2026-06-04

**內部維護性釋出（refactoring campaign）。** 本版主體是一輪「逐刀 spec → plan → TDD → 本地 merge」的內部重構：把過大的模組與寫了多遍的政策，逐一收斂成單一真相來源（single source of truth）的結構。**對使用者面（CLI / MCP / viewer）的行為與輸出逐位元不變**，唯一的對外新增是下方 Added 列出的唯讀稽核與 API 文件產生器。全程以 characterization / TDD 安全網先行，**1447 passed、零回歸**，新模組覆蓋率補到 100%。

### Added
- **`audit_conformance()` — 唯讀快照契約稽核**：對既有 / legacy snapshot 做唯讀的契約符合度檢查，不重產、不改 schema（為後續 output-direction 工作預留的稽核入口；目前為 snapshot store 內部能力）。
- **AI-agent API index + 錯誤碼目錄產生器**：doc generators 從 `core/ui/api/` 自動產出路由索引與錯誤碼目錄，供 agent 讀取。
- **集中式 `ERROR_CODES` 登記表**：21 個 HTTP 端點的錯誤碼集中登記（回應值英文、route summary 維持繁中），補登先前 17 + 18 個缺漏碼並加上 drift guard 防再度漂移。

### Changed（內部結構 — 零行為改動）
- **HTTP API 層拆分**：`api_handlers.py`（1234 行 / 21 端點）→ `core/ui/api/` 套件 —— `APIContext` 共享依賴袋 + 集中 `ROUTES` 路由表 + 6 個領域 handler（Project / Analysis / Catalog / Graph / Diff / Annotation），`server.py` 縮成純殼、只做 router 分派。
- **`models.py` 套件化**：1004 行單檔 → `models/` 每領域子模組 + re-export 門面（公開 surface 不變、DRIFT=0），新增 DSM 結構不變式測試（無環 + 邊集 + SDP）守住相依方向。
- **pipeline `run()` 拉直**：把分散的中斷守衛收斂進單一 `_partial` 路徑，正常 / 失敗 / 中斷 / summary / validate 五條路徑全 characterize。
- **`BaselineResolver` 抽出（Finding B-1）**：把分散 5 處的快照參照文法（label / git tag / date / SHA / UUID，含 UUID 分支）收編成單一純解析器，消費端去重。
- **`DoubtLifecycle` 抽出（Finding B-2）**：把疑義狀態轉換政策（原寫四遍：轉換表 / 5 個動詞 / tool if-elif / CLI if-elif）收成單一宣告式生命週期（純零 I/O、效果 by-target），落盤集中為單次，tool 與 CLI 共讀 `store.transition`，5 個動詞留薄殼，行為 / 輸出逐字不變。

### Hardened
- **快照持久化契約對賬（Finding A）**：snapshot schema 改 strict + 新增 `_get_snapshot_schema` loader；所有寫入收斂進單一 `_write_snapshot` chokepoint 做 fail-closed 契約校驗，杜絕繞過驗證的落盤路徑。

### Removed
- 清掉無參照的自我分析 dogfood 殘留檔。

### Tests
- 1447 passed、46 skipped、1 xfailed、**零回歸**；新增 / 改動模組（`core/ui/api/`、`models/`、pipeline run、BaselineResolver、DoubtLifecycle）覆蓋率補到 100%。

---

## v1.5.6 — 2026-05-31

### Added
- **資料模型契約驗證（Data-Model Contract Verification）**：全新旁路分析層（仿 `core/vulnerability/` 範式），把「程式碼實際碰到的資料欄位」對「宣告的資料模型」做雙向契約 diff（write gap / coverage gap / match）。不上 LLM 翻譯路徑、不改 extraction/ASTNode/L1-L3/snapshot。
  - **Tier 0（全本地零 token，預設跑）**：`DataModelLocalizer` 用既有 `ExtractionResult` 節點 + 目錄走訪，依跨語言 name/dir/檔名啟發式（`core/datamodel/datamodel_hints.py`）定位「資料模型觸點」（持久化疑似節點 + schema 檔候選），產定位圖。
  - **Tier 1（on-demand、檔案層交付）**：agent-as-LLM 讀候選**檔案**正規化出宣告欄位集與程式碼觸點欄位集，`ContractVerifier` 做雙向契約 diff，寫 `.the-door/datamodel/contract.json` + 回摘要。不寫任何 framework-specific schema parser（格式容忍度外包給 agent）。
  - **新 CLI**：`verify-data-model <path>`（Tier 0 定位）+ `--deep`（額外印候選檔清單與 Tier 1 交付指令，不呼叫 LLM）。
  - **新 MCP 工具**：`localize_data_model`（Tier 0 序列化）、`verify_data_model_contract`（Tier 1 契約 diff + 持久化）。
  - 新增同儕子套件 `core/datamodel/`（models / hints / localizer / verifier / renderer），全純函式/值物件，逐單元 TDD、新模組覆蓋率 100%。

---

## v1.5.5 — 2026-05-31

### Added
- **Wizard 更新分析引導流程（引導式 + 相似度分流）**：把精靈的「更新分析」從直跳確認頁改成引導式分岔流程。純前端引導、零新 HTTP endpoint，所有「執行」步驟由 wizard 產生指令卡交給使用者的 agent 跑（agent-as-LLM），唯一新增後端互動是讀既有的唯讀 `GET /api/snapshots`。
  - **A 路（重生）**：`PAGE_UPDATE_MODE` → `PAGE_REGEN_GUIDE` — 選既有版本 → 出重生指令卡（沿用原標籤）。
  - **B 路（引入新資料）**：`PAGE_NEW_DATA`（路徑 + baseline 選擇）→ `PAGE_SIMILARITY_GUIDE`（結構比對指令卡）→ `PAGE_SIMILARITY_DECISION`（六成相似度判讀準則 + 兩條決策）→ 當版本：`PAGE_VERSION_GUIDE`（`snapshot_write(inherit_from=...)` 指令、標籤即時更新）→ `PAGE_VERSION_DETECT`（唯讀偵測新快照）→ `PAGE_TRANSLATE_CHOICE`（選跑自然語言翻譯 + 進 Viewer）→ `/index.html`；當新專案：導回 `/wizard.html` 首頁。
  - 新增純 helper `resolveSnapshotRef`（識別字串優先序 `git_tags[0] → label → version_id`，不沿用停在 `label→null` 的 `_snapLabel`）+ api client `getSnapshots`。
  - rail 階段（`STAGE` map）補上 8 個新頁對應；文字輸入一律用 `change` 事件避免 `renderPage` 全量重建導致失焦。

### Fixed
- **css hygiene allowlist**：放寬 `wizard-css-units` / `wizard-shell-css` 的 border-radius 白名單接受 `0`（visual v2 將 `.wizard-shell .wizard-card` 改為 `border-radius:0` 的方角卡片）。

### Tests
- +38 JS tests（`wizard-update-flow.test.js` 新建 + `ui-wizard.test.js` reducer/render 改接）；893 passed、0 regression（餘 8 個為與本流程無關的 pre-existing failures）。

---

## v1.5.1 — 2026-05-30

### Fixed
- **Wizard visual port (first pass)**: PAGE_ACTION/SETUP/LABEL/CONFIRM 補上 prototype 視覺層 — eyebrow（每頁皆有）、27px hero heading、lede prose、icon-card 選項 (`.opt > .ico + .tx + .arrow`)、switch-zone 一列式 footer (`.sz-label` + `.switch-row`)、summary 4 row（操作/排除目錄/版本標籤/執行模式）。Icon library `I = {scan/refresh/eye/arrow/info/warn/lines/clock}` 移植進 `ui-wizard.js`。Legacy `.wizard-card` bordered framing 在 `.wizard-shell` 內被中和（border/box-shadow/max-width neutralised）讓 `.wizard-screen` 全幅顯示。Pre-existing FIX-1~5 + 老 test-asserted class 名（`.wizard-option-btn` / `.wizard-eyebrow` / `.wizard-mode-note` 等）保留並列以維持 853 JS 測試綠燈。佈局尚未 100% 對齊 prototype（rail 寬度、screen padding、選項卡片間距仍有差異），待後續 spec 重新撰寫後再迭代。

---

## v1.5.0 — 2026-05-30

### Added
- **Onboarding flow Part 2**: 雙欄精靈外殼（左門外暗面 + 右門內明亮）+ 進度視覺化（phasebar + steplist + 即時檔案 feed）+ 跨頁穿門轉場（spec §0-§9）
- **後端 progress 契約**: `UpdateJob.progress` 欄位（`files_done` / `files_total` / `current_file` / `current_root`）由新 `ProgressReporter` 抽象從 `ASTExtractor` / `BatchReader` 內部 file loop 寫入；`handle_get_update_status` payload 暴露給前端
- **handle_post_analyze adapter**: 精靈 analyze 走 `run_analyze_pipeline` 經 per-request closure 映射為 `[步驟 N/6]` 訊息與 modal `PipelineOrchestrator.run` 對齊（spec §5.1）
- **Viewer modal 進度設計一致化**: `ui-modal.js renderPipelineProgress` 改用 phasebar/steplist/feed（與精靈 PROGRESS 同設計）
- **「上一步」鈕**: PAGE_SETUP / PAGE_LABEL / PAGE_CONFIRM 三處新增 `.wizard-btn-ghost`；通用化 `{ type: 'BACK', target }` action 支援 analyze 與 update 兩條路徑（spec §4.3）
- **`errorOriginPage` state 欄位**: PAGE_ERROR rail stage 由 origin 推回，避免 STATUS_ERROR 在 LOADING 階段被誤顯示為「分析中」（spec §4.1）

### Changed
- 新增共用前端模組 `viewer/js/progress-view.js`（`renderProgressInnerHTML` / `appendPlLine` / `updateProgressCount`）+ `viewer/js/phase-status.js`（`phaseStatus` 4-way + `PHASE_BUCKETS` + `STEP_LABELS`）— 精靈 PAGE_PROGRESS 與 modal `renderPipelineProgress` 共用同一 render 路徑（spec §7 一致化）
- `styles.css` 加 11 個 Part 2 token（terminal / radius / rail 系列）+ 共用進度區（`/* Progress (shared) */`）
- `wizard.css` 加 shell + rail + screen 動畫 + mode-note + ghost button + agent-* + transient；字體 token (`--font-sans` / `--font-mono`) 限定 `.wizard-shell` 後代 scope（不入 styles.css :root 避免 7 處 fallback regression）
- `wizard.html` 移除 `.wizard-root` wrapper（雙欄自滿版）

### Removed
- `styles.css:846-870` 舊 `.step-*` chips 規則（已被 `.wizard-phasebar` / `.wizard-sl-row*` 取代）

### Tests
- 1a/1b: +18 Python tests（progress_reporter / adapter / payload / e2e）
- 2-9: +35 JS tests（shell / phasebar / feed / back / error-origin / transition）
- coverage 維持 100%

---

## v1.4.6 — 2026-05-30

### Edge noise projection (post-v1.4.5 增量)

- **`Edge.resolution` 加 `name_match_ambiguous` 枚舉值**：高 fanout（候選 > N）的裸名匹配標為 ambiguous
- **新增 `core/llm/edge_projection.py` 純函式投影層**：drop ambiguous + 把 `skipped_dynamic` 邊聚合成 `aggregate_call_hints`
- **BatchReader detail mode payload 加 `aggregate_call_hints` 欄位**；minimal mode 不變
- **L1 prompt 教 LLM 看 hint 但不可寫成依賴**

#### Dogfood §7.2 驗收

| Target | 投影前邊數 | 投影後邊數 | drop% | callers with hints |
|---|---|---|---|---|
| `the_door/src/the_door` | 2044 | 1935 | 5.3% | 18 |
| `test-targets/the-door-v105` | 3413 | 3167 | 7.2% | 47 |

`FANOUT_THRESHOLD = 3`（由 dogfood histogram p75/p90 分佈決定：兩 repo p75=1 p90=1，均遠低於門檻，維持預設值）

#### 向後相容

- 既有 snapshot 反序列化不報錯
- source-level guard 釘住 `core/diff/` 不引用 `edge.resolution`，新枚舉值不會造成 diff 假 churn
- viewer 不需要改動

---

## [1.4.5] — 2026-05-29

### Added
- **Scope-aware edge resolution** for all 7 supported languages (Python / TypeScript / Java / Go / Rust / Ruby / PHP / C#).
  - New `ScopeRules` declarative config per language defining import / function / method / inheritance resolution strategies.
  - New `Edge.resolution` field with four values: `scope_rule` (high confidence), `import_alias` (high confidence), `name_match` (low-confidence fallback), `skipped_dynamic` (dynamic-dispatch context — not trusted).
  - LLM prompt teaches the model how to weight edges by resolution provenance.
- New `ScopeContext` dataclass carrying per-file scope state (import aliases, caller class).
- **Receiver-aware method-call resolution**：`Receiver.method()` 形式的呼叫會把 receiver 透過 import alias 或 local class 名解析回 `Class.method`，`self.method()` / `this.method()` 在 method 內也會解析回 `caller_class.method`。Chained call `a.b.c()` 採 immediate-receiver 慣例（receiver = `b`）。
- BatchReader detail payload 現在包含 batch 內的 `edges`，讓 L1 LLM 直接看到 resolution 標籤。

### Changed
- `EdgeBuilder.build_edges()` 新增 optional `configs` 參數（向後相容）。
- `ASTExtractor` 把 `LANGUAGE_CONFIGS` 傳給 `EdgeBuilder`。
- Edge dedup key 維持 `(from, to, type)`；`resolution` 不入 key（讓 scope_rule 邊取代同對 name_match 重複）。
- `_detect_imports` 產生的 import 邊 resolution 從 `name_match` 改為 `import_alias`（語意修正：import 邊定義上就是 alias-based）。

### Backward compatibility
- 舊 snapshot 無 `resolution` 欄位反序列化時自動補 `"name_match"`（不需 migration）。
- `Edge(from_node=..., to_node=..., type=...)` 不帶 `resolution` 仍可用（預設 `"name_match"`）。
- 公開 API 簽名未破壞；`build_edges(nodes, trees)` 仍可用。

### Dogfood acceptance (§7.2)
- `the_door` 自身：name_match 28.8% / high-confidence 71.2% ✅
- `test-targets/the-door-v105`：name_match 30.8% / high-confidence 69.2% ✅
- 兩個 target 都過 `name_match ≤ 40%` 且 `scope_rule + import_alias ≥ 50%`。

---

## [1.4.0] — 2026-05-28

### Added
- **Detail context mode for L1 analysis（預設啟用）**：`the-door analyze`
  與 `the-door update` 現在預設把每個節點的完整 signature、docstring、
  decorators / annotations、檔案路徑送給 LLM，提升非技術讀者的描述
  品質。原有「只送 node_id」行為保留，可用 `--minimal-context` opt-out。
- **多語言 ASTNode 充實**：`_walk_config_driven` 透過擴充後的
  `LanguageConfig` 為 Java / Go / Rust / Ruby / PHP / C# 6 種語言抽取
  parameters、return_type、docstring、decorators。Python 與 TypeScript /
  JavaScript 既有 walker 不變。
- MCP `analyze_tool` 接受 optional `context_mode` 欄位（`detail` /
  `minimal`，預設 `detail`）。
- L1 system prompt 新增硬性規則 5：禁止直接複製 docstring / comments /
  decorators / signature 進 description 或 trigger_description。

### Changed
- `BatchReader` 引入共用 `_serialize_payload` helper，由 `_process_batch`、
  `_maybe_split`、`regenerate` 共同使用。確保切批估算與實送 payload 一致。

### Notes
- Output schema 完全不變。既有 `.the-door/snapshots/` 檔案無需 migration。
- 新模式下 token 用量會明顯上升（估算 5-15 倍）。對成本敏感的工作流可
  加 `--minimal-context`。
- `extract_structure` MCP tool 不受影響。

---

## [1.3.6] — 2026-05-27

### Added
- **L1 Feature Detail Fields**：Viewer 單版本模式詳情欄新增三個欄位：
  - `trigger_description`（觸發方式）：說明該 feature 在什麼情境下被觸發
  - `confidence_reason`（信心理由）：說明 high/medium 信心度的依據
  - `source_nodes`（Source Nodes）：對應的原始碼節點清單
- **`snapshot_patch` 擴充**：`patch_snapshot()` 新增 `feature_metadata_by_feature` 參數，
  可在不更動 `version_id` 的情況下寫入 `trigger_description` / `confidence_reason`；
  MCP tool schema 同步更新，`source_nodes_by_feature` 移出 `required`，
  `patched_features` 回傳值從 count integer 改為 feature ID list。
- **Pipeline 轉發**：`handle_get_l1` → `build_l1_graph_view_model_from_snapshot` →
  `layers.js loadL1Graph` 全路徑轉發新欄位，含防禦性預設值（`source_nodes: []`）。

---

## [1.3.5] — 2026-05-27

### Added
- **Dynamic Project Switching**：新增 `POST /api/set-project`，讓 UIServer 在執行期切換
  分析目標目錄，無需重啟 server。
  - `JobStore.get_running_job_id()` — 查詢當前執行中 job ID
  - `APIHandlers` callable injection（backward compatible）— `project_root`/`job_store`
    改為 callable property，支援 `project_root_fn`/`job_store_fn`/`switch_project_fn` 注入
  - `UIServer._switch_project(new_path, force)` — thread-safe（`threading.Lock`），
    回傳 `switched` / `conflict` / `error`
  - `handle_post_set_project`：路徑驗證（存在、是目錄、可讀）+ 409 conflict 支援
  - Wizard UI（`ui-wizard.js`）新增切換專案區塊：輸入框、切換按鈕、conflict 確認介面

---

## [1.3.1] — 2026-05-26

### Added
- **Wizard UI 入口**：`the-door ui` 改為開啟 `wizard.html` 結構化問卷，引導使用者
  設定分析目標並觸發分析。包含 `/api/analyze` POST endpoint、`ui-wizard.js` 狀態機、
  `wizard.html` / `wizard.css`。

---

## [1.2.3] — 2026-05-24

### Added
- **FlowGuard 程式級流程強制**：新增 `FlowGuard` + `Decision` + `CheckpointOption`
  系統，在關鍵決策點以程式邏輯拋出 checkpoint，取代僅依賴文件的引導方式。
  MCP 層回傳 `{"result": null, ...checkpoint...}`，CLI 層以 `CheckpointRenderer`
  阻塞 stdin，agent 無法拿到資料就無法繼續。
- **Store 解耦（ProjectIdentity）**：新增 `ProjectIdentity` + `StoreResolutionResult`，
  將 snapshot store 遷移至 `~/.the-door/store/<UUID>/`，與 source codebase 路徑分離。
  `VersionSnapshot` 新增 `codebase_path` 欄位記錄來源路徑。
- **MCP CHECKPOINT 強制點**：
  - `system_status_tool`：`unanalyzed-versions-detected`（問題 #1/#4）
  - `snapshot_write`：`new-features-detected` + inherit_from merge bug 修復（問題 #7）
  - `analyze_changes`：`source-path-broken` + `source_path` 參數（問題 #8/#10）
- **CLI CHECKPOINT 強制點**：
  - `analyze_cmd`：`no-api-key`（問題 #2）
  - `status_cmd`：`project-not-initialized` + `unanalyzed-versions-detected`（問題 #3/#4）
  - `extract_cmd`：`backfill-complete` + `_count_empty_source_nodes`（問題 #9/#11）

### Fixed
- `snapshot_write` + `inherit_from` 過濾掉新增 feature 的 merge 邏輯 bug（問題 #7）
- `analyze_changes` 在 store/source 路徑分離時無法運作（問題 #10）

### Internal
- `.kiro/specs/flow-guard-store-decoupling/`：FlowGuard spec + 5 份 task 文件
- 測試覆蓋：898 passed + 45 skipped；新增 contract / integration / unit 全覆蓋

---

## [1.2.2] — 2026-05-23

### Added
- **多語言 L1 抽取（Stream A）**：以 `language_configs.py` config-driven 架構取代
  `_walk_generic`，新增 Rust / Java / Ruby / PHP / C# / Go / Python / TypeScript / JavaScript
  逐語言節點型別對照表；修復 Go methods、orphaned method_types 抽取失效。
  測試覆蓋率 100%（unit + regression + property）。
- **Claude Code hooks（Stream D）**：新增 3 條開發守衛 hook（UserPromptSubmit、
  PostToolUse、Stop），確保前端唯一正式版路徑與 UI 啟動指令。
- **Viewer 設計系統套用（Stream B）**：依 design system v1.1.1 全面更新
  design token、topbar（版本 pill、logo 狀態、risk filter button）、
  list filter bar（信心/類型/排序純函式 pipeline）、CJK-aware word-level diff、
  notes 折疊卡片、doubt 詳情視圖、心智圖 diff badge + anomaly badge + L1 節點尺寸。
- **Diff 詳情面板（Stream C）**：`/api/diff` 回應加入 `node_details` map；
  詳情欄在 structural diff 模式下顯示版本 A/B 說明文字對比；詳情欄加寬。
- **版本選擇器 dropdown 修復**：版本 A/B pill 恢復 `<select>` 下拉；
  `populateVersionSelectors()` 正確掛載。
- **備註 tab**：詳情面板新增「詳情 / 備註」分頁切換，備註區塊移至獨立 tab pane。
- **關聯圖 grid 卡片 layout**：以 CSS grid 卡片取代 Cytoscape 節點圖，
  呈現變更類型色彩與信心度邊框；SVG edge overlay 由 `requestAnimationFrame` 繪製。

### Internal
- `.kiro/specs/consolidated-roadmap-2026-05-23/`：4 工作流合併 spec（10 節）
  + 5 份 task 文件。

---

## [1.2.1] — 2026-05-20

### Added
- **L1 System Prompt**：新增 `L1_SYSTEM_PROMPT`，針對非技術讀者強制輸出規則，
  透過 `batch_reader` provider 傳入所有 L1 分析呼叫。
- **L2 Anomaly Checklist**：`per-module anomaly checklist` 針對 3 種可由 AST 判斷
  的異常類型（過大模組、孤立節點、循環相依）強制執行。
- **Diff Explanation Prompt 強化**：新增 forbidden list + examples，
  防止 LLM 產出過於模糊或重複的差異推論。

---

## [1.2.0] — 2026-05-18

### Added
- **增量分析完整實作**：`compute_affected_features`、`incremental_pipeline`
  orchestrator、`analyze_changes` MCP tool、`snapshot_write` 支援 `inherit_from`
  + `updated_features`，實現跨 snapshot 增量更新。
- **Guidance Engine**：`SystemState` frozen dataclass、`StateInspector`（50ms 限制）、
  `NextActionSuggester` 規則表 + after-error boost、`Remediation` + 標準錯誤信封（F3）。
- **CLI UX**：`the-door status`、`--from-snapshot` 增量旗標、`extract --as-version`
  backfill、所有 CLI 命令加入 post-run Next: hook 與 F3 error envelope。
- **MCP Surface**：`system_status`、`analyze_changes` tool；所有 MCP 工具回應
  統一注入 `next_actions`；shared response envelope helper。
- **Viewer 模組化**：`js/` 拆分為 state / dom / api / viewmodel / graph /
  ui-detail / ui-list / ui-topbar / ui-notes / ui-diff-explanation /
  ui-modal / layers / app.js 共 13 個模組；TDD 逐步實作（Steps 0–10）。
- **Viewer 功能**：`ui-detail.js` 接線真實 notes + diff-explanation；
  `buildMindmapData` 統一 diff 資料來源；onboarding card；Next Actions 區塊；
  版本比較 count badge 修正；state-aware branding；CSS token 統一。
- **Snapshot 強化**：per-version gzipped structure 讀寫；`list_analyzed_versions`；
  `source_nodes` 持久化；`source_node_count` 推導；node_id 碰撞後綴（P3）。
- **測試基礎建設**：Hypothesis property test patterns；contract test skeletons；
  v105 scenario gate（7 steps）；`_seed_helpers` 整合 7 個 call site。

### Changed
- `CLAUDE.md` 重構為決策樹格式，以 `the-door status` 為唯一起點。
- README 重構為 UX-sequence-focused onboarding guide（407 → 182 行）。

---

## [1.1.0] — 2026-05-13

### Added
- **使用者備註（RI-3）**：右側詳情欄新增本地備註系統。備註依 `mode + version key + feature_id`
  嚴格隔離，存為 append-only JSONL（`NoteStore`）。支援 GET/POST `/api/notes`，
  UI 以 `<details>/<summary>` 折疊呈現，每次載入自動讀取歷史備註。
- **輸出語言選擇（RI-4）**：重新分析 Modal 新增語言 select（預設 `zh-Hant`，支援 `en`）。
  選擇值透過 `POST /api/update` 傳入 pipeline，寫入 `PipelineConfig.output_language`
  與 `UpdateReport.output_language`。
- **差異推論（RI-5）**：差異比較模式右側詳情欄新增「差異推論」區塊。使用者手動觸發
  `POST /api/diff-explanations/<id>/generate`，LLM 依差異資料產生自然語言推論（影響、目的、
  連動資源、注意事項、信心水準）。結果存入獨立 JSONL cache（`DiffExplanationStore`），
  不覆寫 `UpdateReport`。A 版/B 版單一模式不顯示此區塊。
- `DiffChangeExplanation` dataclass（frozen）：記錄 LLM 差異推論結果，
  含 `confidence`（high/medium/low）、`language`、`generated_at` 等欄位。
- `NoteStore`、`DiffExplanationStore`：兩個獨立 append-only JSONL store，
  位於 `.the-door/user-notes/` 與 `.the-door/diff-explanations/`。
- API 端點：`GET/POST /api/notes`、`GET /api/diff-explanations/<id>`、
  `POST /api/diff-explanations/<id>/generate`（共新增 4 個端點）。

### Changed
- **Topbar 視覺強化（RI-2b）**：count badge 符號（+/-/~/⚠）改為中文標籤（新增/移除/修改/注意）。
  所有 Topbar 控制項加入原生 `title` tooltip。`.mode-button.active` 改用
  `var(--accent-soft)` 背景 + `var(--accent)` 文字色，視覺可辨識度提升。
- `UpdateReport` 新增 `output_language: str = "zh-Hant"` 與
  `diff_change_explanations: list[DiffChangeExplanation]` 欄位（有預設值，向下相容）。
- `PipelineConfig` 新增 `output_language: str = "zh-Hant"` 欄位。

### Internal
- 新增 hook stub 架構（RI-2）：`_appendDiffExplanationSection`、`_appendUserNotesSection`
  從三個 render 函式呼叫，讓 RI-3/RI-5 只需填入對應函式，不修改 render path。
- 測試數：447 → 647（新增 207 個測試，含 unit、server routing、static viewer 測試）。

---

## [1.0.6] — 2026-05-10

### Added
- `snapshot_write` MCP tool: AI agents can now write their own L1 analysis results
  directly into the snapshot store without requiring an external LLM API key.
  Enables the full MCP agent-mode pipeline: `extract_structure` → analyze → `snapshot_write` → `diff` → UI.
- `CLAUDE.md`: Defines the MCP multi-tool orchestration sequence for AI platforms
  (Claude Code, Kiro IDE, etc.) acting as the analysis LLM.
- `extract_structure` response now includes `analyzed_files` field (list of analyzed file paths).
- `ProjectRegistry`: Auto-registers analyzed projects in `~/.the-door/registry.json`.
- `the-door projects` CLI command: lists all registered projects.
- `project_list` MCP tool: AI can query registered projects via MCP.
- `the-door ui` now supports interactive project picker when called without a path argument.
- UI server: `GET /api/diff?baseline=<version_id>&current=<version_id>` endpoint for
  computing L1 diff between two snapshots by version ID.

### Changed
- README MCP Quick Start: Added reference to `CLAUDE.md` for tool orchestration details.
- UI version selector: version A now defaults to the older (baseline) snapshot,
  version B to the newer (current) snapshot — previously reversed.
- CLAUDE.md Mode B pipeline: removed `validate_output` step (format incompatible with
  Mode B output); added cross-directory snapshot workaround for `diff`.
- Frontend: API base URL now uses `window.location.host` instead of hardcoded port 8765.

### Fixed
- MCP agent-mode pipeline was previously undocumented, causing AI platforms to fail
  to chain tools correctly when attempting no-API-key analysis.
- UI graph drawer now opens automatically on page load when snapshot data is available.
- Frontend version comparison logic overhauled to correctly trigger diff overlay when
  switching versions via the version selector.

---

## [1.0.5] — 2026-05-09

### Changed
- License: Switched from AGPL-3.0 + Commons Clause to dual licensing
  (AGPL-3.0 Community Edition + Commercial License on request).
- README: Split into English (`README.md`) and Traditional Chinese (`README.zh-TW.md`)
  with language switcher. Restructured into Quick Start / Detailed Reference sections.
  Added MCP path documentation.

### Fixed
- L2 graph view model now exposes `confidence_reason` field.

---

## [1.0.4] — 2026-05-09

### Fixed
- L2 mindmap boxes now auto-size with CJK-aware text measurement.
- Anomaly nodes show orange border and badge on all L2 nodes when parent has anomalies.
- L2 source count and confidence displayed as pill badges; removed grey dot indicator.
- Richer L1/L2 node content, dynamic SVG width, reduced whitespace padding.
- Mindmap popup layout redesigned: auto-scale SVG, slide-in detail panel, toolbar legend.

### Added
- Info panel and legend in mindmap popup.
- Project name now displays as basename in mindmap popup header.
- Diff type tags on L1 feature list on the main page.

---

## [1.0.3] — 2026-05-09

### Added
- `mindmap-popup.html`: New dedicated popup window with SVG column tree view and
  visual indicators (anomaly, diff type, confidence).
- Mindmap navigation rewritten to use `sessionStorage` + `window.open` for popup mode.

### Removed
- V1 inline mindmap view removed from `index.html`, `styles.css`, `app.js`, and tests.

---

## [1.0.2] — 2026-05-09

### Added
- `renderMindmap`: Full mindmap render pipeline (all 10 unit assertions green).
- `loadMindmapL2`: Progressive L2 data loading with client-side cache.
- `switchToMindmap`: Navigation function with breadcrumb layer support.
- Mindmap View CSS styles.
- Topbar buttons and `mindmap-view` div in `index.html`.

---

## [1.0.1] — 2026-05-09

### Added
- Mindmap unit test harness (TDD scaffold, all tests initially failing).
- `createMindmapL1Node`: Renders L1 feature nodes in mindmap (T1–T3 pass).
- `_renderMindmapL2Section`: Renders L2 sub-feature sections (T4–T7 pass).
- `mindmapL2Cache` state, element refs, and button event listeners wired up.

---

## [1.0.0] — 2026-05-06

### Added
- Phase UI-1: Local Report Viewer — `ViewModelConverter`, static HTML/CSS/JS viewer.
- Phase UI-2: Local API Server — `UIServer` with 7 REST API endpoints, `JobStore`
  for async analysis jobs.
- Phase UI-3: Interactive Graph — Cytoscape.js-based graph with L1/L2/L3 navigation,
  `GraphViewModel_Converter`, `L2Generator`, 6 additional API endpoints.
- Integration tests: 36 end-to-end tests covering all 13 API endpoints.
- Self-analysis: The Door analyzed its own source (541 nodes, 13 features).
- `the-door ui` CLI command to launch the local UI server.
- `__init__.py` version bumped from 0.1.0 to 1.0.0.
- LICENSE copyright year updated to 2025–2026.

---

## Version History Reference

| Version | Release Date | Key Change |
|---------|-------------|-----------|
| 1.2.2 | 2026-05-23 | Multilang extraction + Viewer design system + Diff detail panel + 3 regression fixes |
| 1.2.1 | 2026-05-20 | L1 system prompt + L2 anomaly checklist + diff explanation prompt 強化 |
| 1.2.0 | 2026-05-18 | 增量分析 + Guidance Engine + CLI UX + MCP surface + Viewer 模組化 |
| 1.1.0 | 2026-05-13 | 使用者備註、輸出語言選擇、差異推論、Topbar 強化 |
| 1.0.6 | 2026-05-10 | `snapshot_write` MCP tool + `CLAUDE.md` agent orchestration + ProjectRegistry |
| 1.0.5 | 2026-05-09 | Dual license + bilingual README + `confidence_reason` |
| 1.0.4 | 2026-05-09 | Mindmap popup polish: CJK sizing, anomaly badges, SVG layout |
| 1.0.3 | 2026-05-09 | Mindmap V2 popup window (SVG column tree, sessionStorage navigation) |
| 1.0.2 | 2026-05-09 | Full mindmap render pipeline (renderMindmap, loadMindmapL2, CSS) |
| 1.0.1 | 2026-05-09 | Mindmap TDD scaffold + L1/L2 node builders |
| 1.0.0 | 2026-05-06 | Full release: Phase UI-1/2/3 Interactive Graph + 36 integration tests |
