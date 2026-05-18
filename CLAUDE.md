# The Door — AI Agent Guide

This file tells MCP-compatible AI agents (Claude Code, Kiro, etc.) how to use
The Door's tools. Read this before calling any tool.

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
  1. the-door analyze ./my-project           (首次分析，需要 API key)
  2. extract_structure MCP → snapshot_write  (不需要 API key)
```

If you only read one section of this file, read the `Next:` block from `status`.
Every branch below ends with the same fallback — when in doubt, run `status`.

---

## Decision tree

Five branches. Each leaf is exactly one command. If a branch has an
API-key-dependent fork, it splits into a sub-branch with one command per leaf.

### Branch 1 — Have you analyzed this project before?

Check: does `<path>/.the-door/snapshots/` exist with at least one snapshot?
`the-door status <path>` answers this directly.

- **No** → go to Branch 1a
- **Yes** → continue to Branch 2

#### Branch 1a — First-time analysis: do you have an API key?

- **Yes** →
  ```bash
  $ the-door analyze ./my-project
  ✓ Extracted 169 files / 1431 nodes
  ✓ Wrote snapshot abc12345-... labeled "v1.0.0"

  Next:
    1. the-door ui ./my-project          (open viewer)
    2. the-door diff --baseline v1.0.0   (after next version)
  ```

- **No** → use the MCP `extract_structure` → (you identify L1 features) →
  `snapshot_write` chain. See [Commands & MCP tool reference](#commands--mcp-tool-reference)
  for the agent-as-LLM workflow.

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

### Branch 3 — Source changed: do you have an API key?

- **Yes** →
  ```bash
  $ the-door update --from-snapshot v1.0.0 ./my-project
  ✓ Reused 7/9 L1 features from v1.0.0
  ✓ Re-analyzed 2 changed features
  ✓ Wrote snapshot def67890-... labeled "v1.0.5"

  Next:
    1. the-door ui ./my-project              (visualize the change)
    2. the-door diff --baseline v1.0.0 ./    (CLI diff)
  ```

- **No** → use the MCP `analyze_changes` tool to get the list of affected
  features, update them yourself, then call `snapshot_write` with the
  `inherit_from` argument pointing at the baseline snapshot.

### Branch 4 — `update --from-snapshot` says "no persisted structure for baseline"

The baseline snapshot exists but its full L1 structure was never persisted
(e.g. it predates the snapshot store schema, or only the label was tagged).

- **You still have the baseline source on disk** →
  ```bash
  $ the-door extract --as-version v1.0.0 ./baseline-source
  ✓ Backfilled snapshot v1.0.0 with persisted L1 structure

  Next:
    1. the-door update --from-snapshot v1.0.0 ./my-project
  ```
  (No API key needed — this is a structural backfill, not a re-analysis.)

- **You no longer have the baseline source** →
  ```bash
  $ the-door analyze ./my-project
  ✓ Extracted ... / Wrote snapshot ...

  Next:
    1. the-door ui ./my-project
  ```
  This loses the historical baseline link, but produces a fresh snapshot.

### Branch 5 — None of the above feels right

```bash
$ the-door status ./my-project
```

Read the `Next:` block. It's the source of truth for what the project needs.

---

## Commands & MCP tool reference

| Command / Tool | Use when | API key? |
|---|---|---|
| `the-door status <path>` | Always first. Reports state + `Next:`. | No |
| `the-door analyze <path>` | First-time analysis, full LLM pass. | Yes |
| `the-door update --from-snapshot <ref> <path>` | Incremental re-analysis of a changed source. | Yes |
| `the-door extract --as-version <label> <path>` | Backfill persisted L1 for an existing snapshot. | No |
| `the-door diff --baseline <ref> <path>` | CLI diff between snapshots. | No |
| `the-door ui <path>` | Open the viewer workbench. | No (L2 generation in viewer needs it) |
| `extract_structure` MCP | Agent-as-LLM: get nodes/edges/topology, then YOU produce L1. | No |
| `snapshot_write` MCP | Agent-as-LLM: persist L1 features you identified. Use `inherit_from` to chain off a baseline. | No |
| `analyze_changes` MCP | Agent-as-LLM incremental: list features affected by changes against a baseline. | No |
| `system_status` MCP | Same as `the-door status` but callable from agents. | No |

For the input/output schemas of each MCP tool see
[`.kiro/specs/incremental-analysis/design.md`](.kiro/specs/incremental-analysis/design.md).

### Agent-as-LLM chain (no API key, single version)

1. `extract_structure(codebase_path="./my-project")`
   → Returns `files`, `nodes`, `edges`, `topology`, `analyzed_files`.

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
     ]
   }
   ```
   `feature_id` must start with `feat-`. `confidence` is `high` / `medium` / `low`.

3. `snapshot_write(codebase_path="./my-project", l1_features=[...], relations=[...], label="v1.0.0")`
   → Returns `version_id`, `label`.

### Agent-as-LLM chain (no API key, incremental update)

1. `analyze_changes(codebase_path="./new-project", baseline="v1.0.0")`
   → Returns list of affected `feature_id`s plus their new node membership.

2. You re-derive only the affected features (same JSON shape as above).

3. `snapshot_write(codebase_path="./new-project", l1_features=[...], relations=[...],
   label="v1.0.5", inherit_from="v1.0.0")` — unchanged features are inherited.

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

---

## Glossary (backward compatibility)

Terms used in earlier versions of this guide and where to find them now:

- **Mode A** (legacy term): "External LLM via API key." Now distributed across
  the branches above as the "with API key" leaves — see
  [Branch 1a](#branch-1a--first-time-analysis-do-you-have-an-api-key) and
  [Branch 3](#branch-3--source-changed-do-you-have-an-api-key).
- **Mode B** (legacy term): "Agent-as-LLM, no API key needed." Now distributed
  as the "without API key" leaves — see Branch 1a, Branch 3, and the
  [Agent-as-LLM chain](#agent-as-llm-chain-no-api-key-single-version) sections.
- **Snapshot reference**: any of label / git tag / date / SHA / UUID. See
  [Snapshot reference formats](#snapshot-reference-formats).
- **Next: block**: the trailing section of any CLI command's output that names
  the recommended next command(s). `the-door status` always prints one; most
  other commands print one on success. Treat it as authoritative.
