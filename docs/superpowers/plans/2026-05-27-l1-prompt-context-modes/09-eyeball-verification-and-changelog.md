# Task 09 — Eyeball Verification + CHANGELOG / README

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收尾任務。執行可觀察的 detail vs minimal 比對驗收（spec §11 acceptance proxy），確認 detail 模式對非技術讀者更友善。更新 `CHANGELOG.md` 與 `README.md` 標示 v1.4.x 引入「detail context mode + 多語言 ASTNode 充實」。

**Architecture:** 純手動驗證 + 文件更新。無新增測試（既有測試已覆蓋程式邏輯）。

**Tech Stack:** the-door CLI, 文字編輯器, 手動比對。

**Test Coverage Requirement:** 無新增程式碼，所以無 line coverage 要求。但必須跑完整 `pytest the_door/tests/ -q` 一次確認綠燈，並補 CHANGELOG / README 自身的 lint（若 repo 有 markdown lint hook）。

---

## Background（自含）

spec §11 acceptance criteria 中有一條可觀察的 proxy：

> 於 test-target v105 v1.2.2 + 多語言 fixture 各跑 detail 與 minimal 一次。由 spec 作者抽 10 個 feature description 對比，detail 模式違反 §4.2 風格規則（出現函式名 / 檔名 / API 路徑 / camelCase / 縮寫）的條目數 ≤ minimal 模式。

spec §4.2 風格規則禁止 description / trigger_description 出現：
- 函式名（含 `(` 的識別字、camelCase / snake_case 函式名）
- API endpoint（如 `/api/` 開頭）
- 檔名（`.py`、`.js`、`.ts` 等）
- 縮寫（AST、JSON-RPC、API、DOM、HTTP、URL、CVSS、CVE 等）
- camelCase 識別字

本任務手動跑兩次分析、各抽 10 個 description 用上述規則計分，記錄結果。

完成後更新 release 文件 — `CHANGELOG.md` 加 entry、`README.md` 提及 `--minimal-context` flag（如該檔目前列出 CLI flag 清單）。

---

## Files

- 無新增程式檔
- Modify: `CHANGELOG.md`
- Modify: `README.md`（如該檔列出 CLI flag 清單）
- Modify: 主 repo 根目錄 `docs/frontend-local-version-viewer/README.md` 或其他 README（若它們提到 analyze 流程）— **僅在實際引用到時才動**
- 新增（紀錄文件）: `docs/superpowers/plans/2026-05-27-l1-prompt-context-modes/09-verification-log.md`（驗證結果存檔）

---

## Steps

### Step 1 — Run full test suite

- [ ] **Step 1: Confirm full pytest green**

Run: `pytest the_door/tests/ -q`
Expected: 全綠（既有 + 前 8 個任務新增的測試全部 pass）。如有 failure，回到對應任務修正後再進入本任務。

### Step 2 — Prepare verification environment

- [ ] **Step 2: Confirm test-target v105 v1.2.2 available**

Confirm `C:\Users\Ric\Desktop\test-targets\the-door-v105` 存在，且該專案的 v1.2.2 snapshot 可被 the-door 處理。如不存在，跳過 Python 部分，只跑多語言 fixture 驗證。

- [ ] **Step 3: Confirm multilang fixture available**

`the_door/tests/fixtures/multilang/` 下應有 6 個 sample 檔（前置任務建立）。如缺，先回 Task 03 補足再進入本任務。

### Step 3 — Run detail vs minimal analysis

> **Labelling strategy（修正自前版幻覺）**：The Door 的 `analyze` CLI **沒有 `--label` flag**（已 grep 確認）。Snapshot label 來自 git tag（auto-snapshot creation in `analyze_pipeline.py:_create_auto_snapshot`）。本驗證採「複製 test target 到分隔目錄、每個目錄各跑一次」的策略，用目錄名區別兩次分析的 snapshot；不依賴 CLI labelling flag。

- [ ] **Step 4: Prepare two isolated copies of each test target**

```bash
# Python 測試標的（v105 v1.2.2）
cp -r "C:\Users\Ric\Desktop\test-targets\the-door-v105" \
      "C:\Users\Ric\Desktop\test-targets\v105-detail"
cp -r "C:\Users\Ric\Desktop\test-targets\the-door-v105" \
      "C:\Users\Ric\Desktop\test-targets\v105-minimal"

# Multilang fixture（先複製到 /tmp 或專用目錄，避開 repo 內 .the-door/ 互相干擾）
cp -r "<repo-root>/the_door/tests/fixtures/multilang" \
      "C:\Users\Ric\Desktop\test-targets\multilang-detail"
cp -r "<repo-root>/the_door/tests/fixtures/multilang" \
      "C:\Users\Ric\Desktop\test-targets\multilang-minimal"
```

每個目錄產生獨立的 `.the-door/snapshots/`，互不干擾。

> 注意：本任務需要 API key 來實際呼叫 LLM。如無 API key，跳到 Step 9 的 agent-as-LLM 替代路徑。

- [ ] **Step 5: Analyze Python test-target — detail mode (default)**

```bash
the-door analyze "C:\Users\Ric\Desktop\test-targets\v105-detail"
```

預期輸出含「Wrote snapshot ...」。記錄回傳的 `version_id`（或 snapshot 對應的 git tag / label）作為 detail 組識別碼。

- [ ] **Step 6: Analyze same test-target — minimal mode**

```bash
the-door analyze "C:\Users\Ric\Desktop\test-targets\v105-minimal" \
  --minimal-context
```

預期完成；token 用量可從 stderr progress 訊息對比。

- [ ] **Step 7: Analyze multilang fixture — detail mode**

```bash
the-door analyze "C:\Users\Ric\Desktop\test-targets\multilang-detail"
```

- [ ] **Step 8: Analyze multilang fixture — minimal mode**

```bash
the-door analyze "C:\Users\Ric\Desktop\test-targets\multilang-minimal" \
  --minimal-context
```

### Step 4 — Score the outputs

- [ ] **Step 9: Score 10 feature descriptions per mode**

對每組（python-detail / python-minimal / multilang-detail / multilang-minimal）開啟 viewer：

```bash
the-door ui "C:\Users\Ric\Desktop\test-targets\the-door-v105"  # 端口預設 8765
```

抽出每組前 10 個 feature 的 `description` + `trigger_description`，用以下 checklist 計分：

| # | feature_id | description 違反項計數 | trigger_description 違反項計數 |
|---|---|---|---|
| 1 | feat-xxx | 0 | 0 |
| ... | ... | ... | ... |

違反項定義（每出現一個獨立違規記 1 點）：
- 含 `(` 字元的識別字（如 `analyze()`）
- 含 `.py` / `.js` / `.ts` / `.rs` / `.go` / `.rb` / `.php` / `.cs` / `.java` 副檔名
- 含 `/api/` 或其他 `/...` 路徑
- 含全大寫縮寫（AST, API, JSON, HTTP, URL, DOM, CSS, MCP, CVE, CVSS — 至少 2 個連續大寫字元）
- 含 camelCase（首字母小寫、含至少一個內部大寫的字串）

把計分結果寫進 `docs/superpowers/plans/2026-05-27-l1-prompt-context-modes/09-verification-log.md`。

- [ ] **Step 10: 若無 API key，用 agent-as-LLM 替代路徑**

如 step 5-8 因無 API key 失敗，改走 MCP agent-as-LLM 流程（見專案根目錄 CLAUDE.md「Agent-as-LLM chain」）：

對每個目錄跑 `extract_structure` MCP tool 取得 nodes，由執行此任務的 agent 親自產 L1 features 兩次（一次「假裝只看 node_id」、一次「使用完整 node 詳情」），用 `snapshot_write` 寫入兩個版本，再進行 Step 9 計分。

> 此路徑不驗證實際 LLM 行為差異，只驗證「程式管線在兩種模式下都跑得通且產出形式正確」。完整品質驗證仍以有 API key 跑 Step 4-7 為主。

### Step 5 — Document verification result

- [ ] **Step 11: Write verification log**

Create `docs/superpowers/plans/2026-05-27-l1-prompt-context-modes/09-verification-log.md`：

```markdown
# Detail vs Minimal Verification Log

**Date:** YYYY-MM-DD
**Tester:** [name]
**API key available:** [yes / no — if no, agent-as-LLM path used]

## Method

Spec §11 acceptance proxy: count style-rule violations in 10 feature
descriptions per mode.

## Python test-target v105 v1.2.2

| Mode    | Total violations across 10 features |
|---------|--------------------------------------|
| detail  | N |
| minimal | M |

Verdict: detail ≤ minimal? [yes / no]

## Multilang fixture

| Mode    | Total violations across 10 features (or "<10 features" if fewer) |
|---------|------------------------------------------------------------------|
| detail  | N |
| minimal | M |

Verdict: detail ≤ minimal? [yes / no]

## Notes / surprises

- ...
```

填入實際數字後 commit 此檔。

- [ ] **Step 12: Decision gate**

如果驗證結果 detail > minimal（即 detail 模式違規數更高），代表 spec §4.2 規則 5（禁止 docstring passthrough）未生效或 prompt 規則不夠強。**不要 ship**。回到 Task 05 強化 prompt 規則，再重跑 Step 5-11。

如果驗證結果 detail ≤ minimal，繼續 Step 13。

### Step 6 — Update CHANGELOG and README

- [ ] **Step 13: Update CHANGELOG.md**

Open `CHANGELOG.md` at repo root (or `the_door/CHANGELOG.md` if it lives under the package). Add a new entry at the top:

```markdown
## v1.4.0 — 2026-XX-XX

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
```

填入實際 release 日期（commit 當天）。

- [ ] **Step 14: Update README.md**

如 `README.md` 或 `the_door/README.md` 有列 CLI flag 範例，加入 `--minimal-context` 範例。例如：

```markdown
# Token-conscious usage

如 LLM token 預算有限，可加 `--minimal-context` 退回原本「只送 node_id」
的低成本模式（v1.3.6 之前的行為）：

    the-door analyze ./my-project --minimal-context

預設不加 flag 時，會送節點完整詳情給 LLM，翻譯品質較高。
```

如 README 沒有 CLI flag 清單，本步驟可略過（CHANGELOG 已是 release notes）。

- [ ] **Step 15: Update CLAUDE.md（如有跨檔說明）**

確認 repo 根 `CLAUDE.md` 的 「Commands & MCP tool reference」表格中，`the-door analyze` / `the-door update` 不需強制更動 — 兩者皆向後相容。如有「指令選項」段落提及 flag 清單，新增 `--minimal-context` 一行。

如 CLAUDE.md 沒列 flag，跳過此步。

### Step 7 — Final commit

- [ ] **Step 16: Run full test suite one last time**

Run: `pytest the_door/tests/ -q`
Expected: 全綠。

- [ ] **Step 17: Commit verification log + docs**

```bash
git add docs/superpowers/plans/2026-05-27-l1-prompt-context-modes/09-verification-log.md CHANGELOG.md README.md CLAUDE.md
git commit -m "docs: v1.4.0 release notes for L1 detail context mode + multilang enrichment

Verification log records detail vs minimal style-rule violation counts
against test-target v105 v1.2.2 + multilang fixture. CHANGELOG entry
covers all surface changes (CLI flag, MCP input, prompt rule, walker
enrichment) with backward-compat callouts."
```

> 若 README.md / CLAUDE.md 未變更，從 `git add` 移除即可。

---

## Acceptance Criteria

- [ ] `pytest the_door/tests/ -q` 全綠
- [ ] Detail 模式對 Python 與多語言 fixture 各跑一次成功
- [ ] Minimal 模式對 Python 與多語言 fixture 各跑一次成功
- [ ] `09-verification-log.md` 存在且填上實際違規計數
- [ ] Detail 模式的違規計數 ≤ Minimal 模式（否則回 Task 05 強化 prompt）
- [ ] `CHANGELOG.md` 含 v1.4.0 entry，涵蓋 4 個 Added、1 個 Changed、3 個 Notes
- [ ] CHANGELOG 明確說明：output schema 不變、token 用量會上升、`extract_structure` 不受影響
- [ ] 若 README.md 列 CLI flag 清單，已加入 `--minimal-context` 範例
- [ ] Final commit 訊息引用 verification log 為 release 依據
