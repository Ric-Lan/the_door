# The Door — AI Agent Guide

This file tells MCP-compatible AI agents (Claude Code, Kiro, etc.) how to use
The Door's tools. Read this before calling any tool.

## 🚫 硬規則：唯一路徑＝agent-as-LLM（沒有 API key 接口）

The Door 的終態**只有一條路徑、零 API key**（丙案 T5 已移除所有 provider / `analyze`
/ `update` key-path）。當任何任務涉及「產 L1/L2 snapshot」、「生成 feature 描述或差異
說明」、「需要自然語言內容」時：

**執行任務的 AI agent（也就是你）親自當 LLM**：MCP `extract_structure` → 你產 L1
→ `edge_residue`（補雜訊殘餘）→ `snapshot_write` 持久化。L2/L3、差異說明同理 —
直接讀 snapshot、自己寫敘述、寫回 `.the-door/`。

「我是 agent、LLM 是別人」的 frame 是錯的。在本專案的脈絡下，**你就是 LLM**。
The Door 不再內建任何 LLM provider；沒有「需要 API key」這個選項。

判斷流程：
- 任務需要結構性分析（diff 表、節點計數、topology）→ 純程式（CLI / MCP 工具）
- 任務需要自然語言（feature 描述、變更敘述、L2 模組解釋）→ **你親自產**（agent-as-LLM 鏈）

## ⚠️ 開發環境速查（必讀，任何操作前確認）

| 用途 | 路徑 |
|---|---|
| **前端源碼（唯一正式版）** | `docs/frontend-local-version-viewer/viewer/` |
| ⛔ prototype/ 已廢棄，請勿修改 | `docs/frontend-local-version-viewer/prototype/` |
| Python 後端 | `the_door/src/the_door/` |

**啟動本地伺服器（指令是 `ui`，不是 `serve`）：**

```
the-door ui "C:\Users\Ric\Desktop\test-targets\the-door-v105" --no-browser --port 8765
```

路徑傳入的是 test-target 目錄，不是 repo 本身。
`_resolve_viewer_dir()` 在 `the_door/src/the_door/cli/ui_cmd.py` 以 5 層 `.parent`
從 ui_cmd.py 往上定位到主 repo 的 `docs/frontend-local-version-viewer/viewer`。
前端檔案改完重啟伺服器即生效，不需要 build step。

---

## ⚠️ Start here: `the-door status`

Always run this first. It inspects the project, tells you what state it's in,
and prints a `Next:` block with the exact next command for your situation.

```bash
$ the-door status ./my-project
專案狀態: 尚未分析 (no .the-door/)

Next:
  1. extract_structure MCP → (你產 L1) → edge_residue → snapshot_write
```

If you only read one section of this file, read the `Next:` block from `status`.
Every branch below ends with the same fallback — when in doubt, run `status`.

---

## Decision tree

Five branches. There is exactly one path everywhere — agent-as-LLM, no API key.
When in doubt, run `the-door status <path>` and follow its `Next:` block.

### Branch 1 — Have you analyzed this project before?

Check: does `<path>/.the-door/snapshots/` exist with at least one snapshot?
`the-door status <path>` answers this directly.

- **No** → go to Branch 1a
- **Yes** → continue to Branch 2

#### Branch 1a — First-time analysis (agent-as-LLM)

Use the MCP `extract_structure` → (you identify L1 features) → `edge_residue` →
`snapshot_write` chain. See
[Commands & MCP tool reference](#commands--mcp-tool-reference) for the full
workflow. After it, open `the-door ui ./my-project`.

### Branch 2 — Has the source changed since the last snapshot?

If unsure, run `the-door status <path>` — it reports whether the working tree
matches the latest snapshot.

- **No** (just want to inspect or visualize) → go to Branch 2a
- **Yes** → continue to Branch 3

#### Branch 2a — Inspect / visualize: viewer or CLI?

- **Viewer (interactive workbench)** →
  ```bash
  $ the-door ui ./my-project
  ✓ Serving viewer on http://localhost:8765

  Next:
    1. open http://localhost:8765 in your browser
  ```

- **CLI diff (against an earlier snapshot)** →
  ```bash
  $ the-door diff --baseline v1.0.0 ./my-project
  ✓ Diff v1.0.0 → current: 2 added, 1 attribute_changed, 0 removed

  Next:
    1. the-door ui ./my-project          (visualize the same diff)
  ```

### Branch 3 — Source changed: re-analyze the new version (agent-as-LLM)

Use the MCP `analyze_changes` tool to get the list of affected features against
the baseline, re-derive only those features yourself, then call `snapshot_write`
with the `inherit_from` argument pointing at the baseline snapshot (unchanged
features are inherited). See the
[incremental agent-as-LLM chain](#agent-as-llm-chain-incremental-update).

Then visualize: `the-door ui ./my-project`, or CLI diff:
`the-door diff --baseline v1.0.0 ./my-project`.

### Branch 4 — "no persisted structure for baseline"

The baseline snapshot exists but its full L1 structure was never persisted
(e.g. it predates the snapshot store schema, or only the label was tagged).
If you still have the baseline source on disk, backfill it (no API key — this
is a structural backfill, not a re-analysis):

```bash
$ the-door extract --as-version v1.0.0 ./baseline-source
✓ Backfilled snapshot v1.0.0 with persisted L1 structure
```

Then continue with Branch 3 against the backfilled baseline.

### Branch 5 — None of the above feels right

```bash
$ the-door status ./my-project
```

Read the `Next:` block. It's the source of truth for what the project needs.

---

## Commands & MCP tool reference

No command or tool takes an API key — The Door has no LLM provider.

| Command / Tool | Use when |
|---|---|
| `the-door status <path>` | Always first. Reports state + `Next:`. |
| `the-door extract --as-version <label> <path>` | Backfill persisted L1 for an existing snapshot. |
| `the-door diff --baseline <ref> <path>` | CLI diff between snapshots. |
| `the-door ui <path>` | Open the viewer workbench (display-only). |
| `extract_structure` MCP | Agent-as-LLM: get the L0 region index + drill-down artifacts, then YOU produce L1. |
| `edge_residue` MCP | Agent-as-LLM: persist edge-noise residue for a codebase (zero-token, deterministic). Required before `snapshot_write` (C3 gate). |
| `snapshot_write` MCP | Agent-as-LLM: persist L1 features you identified. Use `inherit_from` to chain off a baseline. |
| `snapshot_patch` MCP | 對既有 snapshot 補 source_nodes（原地更新，不改 version_id）。 |
| `analyze_changes` MCP | Agent-as-LLM incremental: list features affected by changes against a baseline. Also stamps the `analyze_changes` checklist stage (unchanged-feature fingerprints) for the C7 inherited-description gate. |
| `system_status` MCP | Same as `the-door status` but callable from agents. |

For the input/output schemas of each MCP tool see
[`.kiro/specs/incremental-analysis/design.md`](.kiro/specs/incremental-analysis/design.md).

### Agent-as-LLM chain (single version)

1. `extract_structure(codebase_path="./my-project")`
   → Returns an **L0 index** (not the full structure): `totals`, `regions[]`
   (each with node_count / share % / edge flow / batches / `peel` label with
   evidence / `artifact_path`), and a `consumption_guide`. Full
   nodes/edges/topology land in `.the-door/structure-view/` artifacts:
   - Read the index first. Regions labeled `peel: one_way_consumer` (e.g.
     test code) are structurally peripheral — judge from the attached evidence
     (flow counts) whether to skip them for L1 derivation; the data stays on
     disk, nothing is filtered.
   - Drill down per region: `regions/<region_id>.json.gz` holds per-node L2
     views (attrs + in/out edges keyed `from_node_id`/`to_node_id` + topology
     + residue counts) — use these views instead of joining raw lists yourself.
   - Consume in `batch_assignment` order (batch 1 = entry points, 2..5 by
     descending in_degree) to plan reading.
   - `validate_output` no longer needs the structure inline: pass
     `codebase_path` and it reads `structure.full.json.gz` itself.

2. You group `nodes` by functional purpose (not by file or class) and produce:
   ```json
   {
     "l1_features": [
       {
         "feature_id": "feat-<slug>",
         "label": "Short feature name",
         "description": "Plain-language description.",
         "source_node_count": 5,
         "confidence": "high",
         "source_nodes": ["ClassName.method_name", "..."]
       }
     ],
     "relations": [
       { "from_feature": "feat-a", "to_feature": "feat-b", "relation": "depends_on" }
     ],
     "project_summary": "2-4 句、給非技術讀者的專案簡介：這個產品是做什麼的。"
   }
   ```
   `feature_id` must start with `feat-`. `confidence` is `high` / `medium` / `low`.
   `project_summary`（optional）＝把上面 features 的描述**收斂**成非技術讀者看得懂的
   一段話。鐵則：**只能綜合 features 已含的資訊**，不得引入 L1 之外的能力宣稱；低信心
   feature 的能力用保守措辭。viewer 會自動附「綜合自 N 個功能、x 個低信心」誠實尾註
   （你不用自己寫統計）。

3. `edge_residue(codebase_path="./my-project")`
   → Persists `.the-door/edge-residue.json` (edge-noise residue) **and stamps
   `.the-door/checklist.json`** (the execution checklist, recording the node set
   it covered). This is a prerequisite for `snapshot_write` — the C2/C3
   execution-order gate denies `snapshot_write` unless the checklist's
   `edge_residue` stage is stamped, its `contract_version` is current, **and
   every `source_node` you write is within the covered set** (re-run
   `edge_residue` if you changed the code and reference new nodes).

4. `snapshot_write(codebase_path="./my-project", l1_features=[...], relations=[...], project_summary="...", label="v1.0.0")`
   → Returns `version_id`, `label`.（`project_summary` optional；給了就持久化、viewer 顯示。）

### Agent-as-LLM chain (backfill source_nodes into existing snapshot)

Use when a snapshot already exists but its `source_node_count` is 0 / `source_nodes` is empty.

1. `extract_structure(codebase_path="./target-at-that-version")`
   → Returns full `nodes` list with `node_id` in `ClassName.method_name` format.

2. You group `nodes` by feature, producing:
   ```json
   {
     "feat-cli-dispatch": ["main", "analyze_cmd", "ui_cmd"],
     "feat-ast-extraction": ["ASTExtractor", "ASTExtractor.extract", "NodeBuilder"]
   }
   ```

3. `snapshot_patch(codebase_path="./project", version_ref="v1.0.0", source_nodes_by_feature={...})`
   → Returns `version_id`, `patched_features`, `skipped_features`.
   The snapshot is updated **in-place** (same `version_id`, same `timestamp`).

**Do NOT** use grep as a substitute for `extract_structure` — grep only finds top-level
`class`/`def` and misses `ClassName.method_name` node_ids.  
**Do NOT** edit snapshot JSON files directly — use `snapshot_patch`.

### Agent-as-LLM chain (incremental update)

1. `analyze_changes(codebase_path="./new-project", baseline="v1.0.0")`
   → Returns affected `feature_id`s + new node membership. It also stamps the
   `analyze_changes` checklist stage, recording which baseline features are
   **unchanged** (their description fingerprints) — the C7 gate reads this.

2. You re-derive **only the affected features** (same JSON shape as above).
   **繼承的不譯**：do NOT re-describe unchanged features. Either omit them (they
   inherit the baseline text automatically via `inherit_from`) or, if you full-
   replace, keep their `description` byte-identical to the baseline. The C7 gate
   denies a `snapshot_write` that rewrites an unchanged feature's description.

3. `edge_residue(codebase_path="./new-project")` — refresh the edge-residue
   artifact and re-stamp the checklist (C2/C3 gate prerequisite; also refreshes
   the covered node set so the new features' `source_nodes` pass coverage).

4. `snapshot_write(codebase_path="./new-project", updated_features=[...],
   label="v1.0.5", inherit_from="v1.0.0")` — unchanged features are inherited.
   Prefer `updated_features` (carry only the affected ones) over a full
   `l1_features` replacement — it makes the C7 immutability check trivially pass.
   **`project_summary`（簡介）的繼承規則**：affected set **非空**（有 feature 增/刪/改
   ⟹ 產品組成變了）→ 重寫 `project_summary` 一起帶入；affected set **全空** → 省略，
   自動沿用 baseline 的簡介（與「繼承的不譯」同精神：組成沒變、簡介不重寫）。
   注意這是 guide 級約定、非 gate——簡介是聚合產物，C7 只鎖逐 feature 重譯。

> **Gate boundary (honest):** C3/C7 enforce execution order, node coverage,
> file staleness, and inherited-description immutability — all **structural**.
> They do NOT (and structurally cannot) enforce "use tool output instead of
> grepping the source yourself" or "your prose is a faithful translation": those
> are pure-behaviour / intent, which no tool-call hook can gate (種子 §5 固有缺口).
> Those rest on this guide + the C6 execution-ledger report, not a blocking gate.

---

## Snapshot reference formats

When a command or tool takes a `baseline` / `--from-snapshot` / `inherit_from`
argument, the reference can be any of:

- **Snapshot label**: `"v1.0.0"`, `"my-label"`
- **Git tag**: `"v1.0.0"` (tag attached to the commit at snapshot time)
- **Date**: `"2026-05-06"` (resolves to the most recent snapshot on or before)
- **Commit SHA (≥7 chars)**: `"8de9b18"`
- **UUID**: full `version_id` from a previous response

The viewer's version picker emits `git_tags[0]` → `label` → `version_id` in
that order of preference, so you'll usually see human-readable labels in URLs.

---

## MCP server setup

```json
{
  "mcpServers": {
    "the-door": {
      "command": "the-door",
      "args": ["mcp-serve"]
    }
  }
}
```

If running from source (dev environment):

```json
{
  "mcpServers": {
    "the-door": {
      "command": "python",
      "args": ["-m", "the_door", "mcp-serve"],
      "env": { "PYTHONPATH": "<repo>/the_door/src" }
    }
  }
}
```

> `python -m the_door` 透過 `the_door/__main__.py` 轉接到 console-script 進入點
> （`the_door.cli.main:main`）。若這支檔案缺失，`python -m the_door` 會報
> `No module named the_door.__main__`；此時改用上方的 installed 形式
> （`"command": "the-door"`）即可。

---

## Glossary (backward compatibility)

Terms used in earlier versions of this guide and where to find them now:

- **Mode A** (retired): "External LLM via API key." Removed entirely in T5-A
  (丙案) — The Door no longer bundles an LLM provider or any `analyze` / `update`
  key-path. There is no API-key mode.
- **Mode B** (legacy term): "Agent-as-LLM." This is now **the only mode** — see
  Branch 1a, Branch 3, and the
  [Agent-as-LLM chain](#agent-as-llm-chain-single-version) sections.
- **Snapshot reference**: any of label / git tag / date / SHA / UUID. See
  [Snapshot reference formats](#snapshot-reference-formats).
- **Next: block**: the trailing section of any CLI command's output that names
  the recommended next command(s). `the-door status` always prints one; most
  other commands print one on success. Treat it as authoritative.
