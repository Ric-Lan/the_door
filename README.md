English | [繁體中文](README.zh-TW.md)

# The Door

> Built for non-technical stakeholders who need to verify what was actually built — without reading code.

The Door translates your codebase into plain functional diagrams: what the system does, what changed between versions, and whether deliverables match commitments.

**This tool is designed to be operated by AI, not by you directly.** The Door exposes an MCP server; an AI agent (Claude Code, Kiro, or any MCP-compatible platform) reads your code, produces the functional descriptions, and saves them locally. You open a browser to review the results. No API key required.

> **How to use this document:** Read this page to understand what The Door does. Then hand it — along with [`CLAUDE.md`](CLAUDE.md) — to your AI agent and ask it to get started.

---

## Contents

1. [Tech Stack](#1-tech-stack)
2. [Setting Up Files for Analysis](#2-setting-up-files-for-analysis)
3. [How AI Gets Started](#3-how-ai-gets-started)
4. [CLI Reference](#4-cli-reference)
5. [Snapshot References](#5-snapshot-references)
6. [Architecture](#6-architecture)
7. [License](#7-license)
8. [Documentation](#8-documentation)

---

## 1. Tech Stack

| Layer | Technology |
|---|---|
| Code extraction | Python ≥ 3.10, tree-sitter (305+ languages) |
| MCP server | `the-door mcp-serve` — called by your AI agent |
| Local UI | Vanilla JS (no bundler), served by `the-door ui` |
| Storage | Local `.the-door/` folder inside your target project |
| LLM | **Your AI agent** — The Door bundles no provider and needs no API key |

> ⚠️ **Operating system: tested on Windows only.** macOS and Linux have not been verified. Use at your own discretion on other platforms.

### AI Model Recommendation

| Model | Recommendation |
|---|---|
| Claude Sonnet 4.x | ✅ Recommended |
| Claude Opus 4.8 | ❌ **Extremely not recommended** — tends to deviate from the agent-as-LLM path and introduces assumptions about LLM providers that do not exist in this project |
| Other MCP-capable models | Use at your own discretion |

---

## 2. Setting Up Files for Analysis

The Door analyzes a directory you point it at. To track multiple versions of the same project, keep each version as a separate directory:

```
test-targets/
  my-app-v1.0/      ← complete source snapshot of version 1.0
  my-app-v1.1/      ← complete source snapshot of version 1.1
  my-app-v1.2/      ← ...
```

The Door saves its analysis results inside the target directory:

```
my-app-v1.0/
  .the-door/
    snapshots/      ← persisted L1 feature snapshots
    structure-view/ ← cached AST artifacts
    checklist.json  ← execution gate record
```

**Rules:**
- Each version directory should be a complete, standalone copy of the source (not a git worktree or symlink)
- Do not move or rename `.the-door/` — snapshot labels and UUIDs are stored there
- You can point multiple project directories at the same running `the-door ui` instance

---

## 3. How AI Gets Started

> **If you are an AI agent reading this:** your authoritative operating guide is [`CLAUDE.md`](CLAUDE.md). Read it before calling any tool. What follows is the orientation summary.

The Door has no `analyze` command and no LLM provider. **You, the agent, are the LLM.** All results are persisted locally — The Door makes no LLM network call of its own.

### Step 0 — MCP setup

Add to your AI platform's MCP config:

```json
{
  "mcpServers": {
    "the-door": { "command": "the-door", "args": ["mcp-serve"] }
  }
}
```

### Step 1 — Always check status first

```bash
the-door status ./my-project
```

Reports the project state and prints a `Next:` block — the exact next command for your situation.

---

### Path A — Brand new directory (never analyzed before)

**When to use:** `.the-door/` does not exist; this is the first analysis of this version.

```
extract_structure  →  (you identify L1 features)  →  edge_residue  →  snapshot_write
```

1. Call `extract_structure` — get the L0 structure index
2. Read the structure; group nodes by functional purpose to identify L1 features
3. Call `edge_residue` — stamp the execution checklist (required before writing)
4. Call `snapshot_write` — persist the L1 features you identified

---

### Path B — Existing snapshot, adding a new version

**When to use:** A previous version is already analyzed; you now have a new version's source in a separate directory and want to record it and compare it against the baseline.

Before proceeding, **ask the user which analysis mode to use:**

> "I see you already have a snapshot for `[old version label]`. To analyze the new version, which approach would you like?
> - **B1 Full re-analysis:** Identify all features from scratch, ignoring the previous snapshot. Best when the architecture has changed significantly.
> - **B2 Inherited analysis + diff (recommended):** Only re-derive features that actually changed; stable features carry over their existing descriptions automatically. You can also generate a plain-language summary of what changed in this version."

Wait for the user's confirmation before proceeding.

#### B1 — Full re-analysis

**Why choose this:** Major architectural refactor or feature reorganization where the previous descriptions no longer map to the new structure.

Same flow as Path A. Use a new `label` in `snapshot_write`; do not pass `inherit_from`.

#### B2 — Inherited analysis + diff (recommended)

**Why choose this:** Most version updates change only a subset of features. Inheritance keeps stable feature descriptions consistent across versions and saves analysis time. The optional `version_narrative` step lets non-technical readers see "what changed in this version" in plain language.

```
analyze_changes  →  (re-derive affected features only)  →  edge_residue  →  snapshot_write (inherit_from)
                 →  (optional) snapshot_patch to add version_narrative
```

1. Call `analyze_changes` — get the list of affected features
2. Re-derive descriptions for affected features only (unchanged features are not rewritten)
3. Call `edge_residue` — re-stamp the checklist
4. Call `snapshot_write` with `inherit_from=<old version label>` — unchanged features inherit automatically
5. (Optional) Call `snapshot_patch` with `version_narratives` — a plain-language sentence describing what this version did

---

### Finally — Open the viewer

```bash
the-door ui ./my-project
```

Opens a three-panel workbench at `http://127.0.0.1:8765`. The viewer is display-only — it reads persisted snapshots and never calls an LLM.

Full tool chains, tool schemas, and gate details: [`CLAUDE.md`](CLAUDE.md).

---

## 4. CLI Reference

These commands are deterministic and need no AI agent:

| Command | Purpose |
|---|---|
| `the-door status <path>` | Check project state; prints `Next:` block with the recommended next step |
| `the-door ui <path>` | Start the local viewer at `http://127.0.0.1:8765` |
| `the-door diff <path> --baseline <ref>` | CLI diff between two snapshots |
| `the-door extract --as-version <label> <path>` | Backfill persisted AST structure for an existing snapshot |
| `the-door mcp-serve` | Start the MCP server (called by your AI platform, not manually) |

> The two analysis workflows — first analysis and incremental update — are agent-driven via MCP, not CLI commands.

---

## 5. Snapshot References

Any command or tool that takes a baseline argument (`--baseline`, `inherit_from`) accepts:

| Form | Example |
|---|---|
| Snapshot label | `v1.0.0`, `my-baseline` |
| Git tag | `v1.0.0` |
| Date | `2026-05-06` (most recent snapshot on or before that date) |
| Commit SHA (≥7 chars) | `8de9b18` |
| UUID | full `version_id` |

---

## 6. Architecture

```
Code → AST extraction (tree-sitter, 305+ languages)
     → Topology analysis (dependency ordering, fully local)
     → [agent-as-LLM translation OR cached baseline structure]
     → Output validation + JSON report
     → Local UI (display-only diagram workbench)
```

Everything runs locally. The Door makes no LLM network call of its own.

---

## 7. License

Dual-licensed:

- **Community Edition** — [AGPL-3.0](LICENSE). Free to use and modify. If you distribute or run a modified version as a network service, you must open-source your modifications under the same terms.
- **Commercial Edition** — If you need to use The Door in a proprietary product or closed-source service without the AGPL-3.0 copyleft obligation, contact the maintainer via the issue tracker.

---

## 8. Documentation

- [Agent Guide (`CLAUDE.md`)](CLAUDE.md) — Full decision tree for MCP-compatible AI agents (the authoritative agent entry point)
- [User Guide](docs/USER-GUIDE.md) — Every command and flag
- [Product Spec](docs/the-door-spec-v4.1.md) — Design philosophy and architecture decisions
- [Diagram Language Spec](docs/phase-0a/) — L1/L2 diagram language definition
- [Frontend Spec](docs/frontend-local-version-viewer/spec.md) — Local UI design spec
