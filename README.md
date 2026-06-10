English | [繁體中文](README.zh-TW.md)

# The Door

Translates code structure and changes into functional-language diagrams — so non-technical stakeholders can verify what was actually built.

> Translation direction: technical language → functional language. Diagrams are not decoration — they are the verification interface.

**This README has two parts:**

- **[Part 1 — For users](#part-1--for-users)** — what The Door is, and the commands a person runs.
- **[Part 2 — For AI agents](#part-2--for-ai-agents)** — how an MCP-driven agent operates The Door (the one path, the tools, the gate). The authoritative full guide is [`CLAUDE.md`](CLAUDE.md).

---

# Part 1 — For users

## What is this

The Door is a CLI tool + MCP Server + local UI. Driven by an MCP-capable AI platform (Claude Code, Kiro, …), it reads your codebase and translates it into "functional language" — plain descriptions of what the system does, what changed, and whether anything looks wrong.

**The Door bundles no LLM provider and needs no API key.** The AI agent driving it *is* the LLM: The Door extracts code structure deterministically, the agent produces the natural-language layer, and The Door persists it. (Mechanics in [Part 2](#the-one-path--zero-api-key).)

**Who it's for:** PMs, project managers, release managers, QA, clients — anyone who needs to confirm that deliverables match commitments, without reading code.

## Core capabilities

| Capability | Description |
|---|---|
| Feature translation | Code → functional-language diagram (interactive + Mermaid fallback) + agent-authored narrative |
| Version diff | What changed between two versions, risks surfaced first |
| Incremental update | Re-analyze only the features whose source nodes changed — the diff itself is pure AST, no LLM call |
| Scope verification | PM defines sprint scope → auto-compare → flag out-of-scope items |
| Vulnerability scan | Known CVEs in dependencies, integrated into the feature diagram |
| Feature evolution | Multi-version timeline tracking when features appeared and how often they changed |
| Doubt tracking | Anomaly detected → flagged → assigned → resolved (with escalation on timeout) |
| Feature detail panel | Per-feature drill-down: trigger description, confidence rationale, and source node list — visible in the viewer's single-version mode |
| Scope-aware edges | Cross-file relations carry a `resolution` tag (`scope_rule` / `import_alias` / `name_match` / `skipped_dynamic`) so the agent can weight high- vs low-confidence edges instead of treating all name matches equally |
| Edge noise residue | The `edge_residue` MCP tool filters high-fanout noise and aggregates dynamic-dispatch edges into caller-level hints (deterministic, zero-token); the snapshot and viewer still keep the full facts |
| Local UI | Browser workbench, interactive diagrams, three-layer navigation (L1 → L2 → L3), display-only |

## Install

```bash
pip install the-door
```

Requires Python ≥ 3.10. Optional: `osv-scanner` (vulnerability scan).

## Quick start

**When you're cold-starting and unsure what state a project is in, run this first:**

```bash
the-door status ./my-project
```

It reports whether the project has been analyzed, whether the source has changed since the last snapshot, and prints a **`Next:`** block — the exact next step for **your** situation. (If that next step is "analyze", an AI agent does it — see [Part 2](#part-2--for-ai-agents).)

**Visualize an analyzed project in the browser:**

```bash
the-door ui ./my-project
```

Opens a three-panel workbench at `http://127.0.0.1:8765`: left = feature list / change list (risk-prioritized), center = interactive diagram, right = detail panel. Three-layer navigation: L1 feature overview → L2 module diagram → L3 source node graph. The viewer is display-only — it reads persisted snapshots and never calls an LLM.

## Other human-runnable commands

These are pure, deterministic, and need no AI agent:

**CLI diff against an earlier snapshot** (inspect without changing anything):

```bash
the-door diff ./my-project --baseline v1.0
```

**Backfill a snapshot that's missing its persisted structure** — if `analyze_changes` reports that a baseline has no persisted AST (typically because the snapshot predates the structures cache) and you still have the original source on disk:

```bash
the-door extract --as-version v1.0 ./baseline-source
```

This re-extracts the AST and saves it under `.the-door/structures/<vid>.json.gz`, after which incremental analysis works normally. No API key needed.

> The two analysis workflows — **first analysis** (establish a baseline) and **incremental update** (after the source changed) — are agent-driven, not CLI commands. There is no `the-door analyze`. See [Part 2](#part-2--for-ai-agents).

## Snapshot references

Any command or tool that takes a baseline argument (`--baseline`, `inherit_from`) accepts five reference forms:

| Form | Example | Notes |
|---|---|---|
| Snapshot label | `v1.0.0`, `my-baseline` | Set explicitly at `snapshot_write` time |
| Git tag | `v1.0.0` | The tag attached to the commit at snapshot time |
| Date | `2026-05-06` | Resolves to the most recent snapshot on or before |
| Commit SHA (≥7 chars) | `8de9b18` | |
| UUID | full `version_id` | Useful when chaining tool calls |

The viewer's version picker prefers `git_tags[0]` → `label` → `version_id`, so URLs you share are usually human-readable.

---

# Part 2 — For AI agents

> **You are an MCP-compatible AI agent (Claude Code, Kiro, …) driving The Door. This section is your on-ramp.**
> The **authoritative, complete operating guide is [`CLAUDE.md`](CLAUDE.md)** — read it before calling any tool. It has the full decision tree, every tool's input/output schema, and the incremental / backfill chains. This part orients you; `CLAUDE.md` is the single source of truth.

## The one path — zero API key

The Door has **no LLM provider** and **no `analyze` / `update` / `config` commands**. Every step that needs natural language is performed by you, the agent, over MCP (agent-as-LLM). There is exactly one path:

```
extract_structure  →  (you identify L1 features)  →  edge_residue  →  snapshot_write
```

`extract_structure` and `edge_residue` are deterministic and run locally; **you** supply the natural-language layer; `snapshot_write` persists it. The "I need an API key" framing is wrong here — in this project, **you are the LLM**.

## MCP setup

Add this to your AI platform's MCP config:

```json
{
  "mcpServers": {
    "the-door": { "command": "the-door", "args": ["mcp-serve"] }
  }
}
```

(Dev / from-source variant and `python -m the_door` notes are in [`CLAUDE.md`](CLAUDE.md).)

## The tools you'll call

| Tool | Use when |
|---|---|
| `system_status` (or `the-door status`) | **Always first.** Reports state + a `Next:` block — the authoritative next step. |
| `extract_structure` | Get nodes / edges / topology, then **you** group nodes into L1 features. |
| `edge_residue` | Persist edge-noise residue **and stamp the execution checklist** (zero-token, deterministic). Required before `snapshot_write`. |
| `snapshot_write` | Persist the L1 features you identified. Use `inherit_from` to chain off a baseline. |
| `snapshot_patch` | Backfill `source_nodes` into an existing snapshot in-place (same `version_id`). |
| `analyze_changes` | Incremental: list the features affected by changes against a baseline. |

Then you can simply act on natural-language requests:

> "Analyze `./my-project` and give me the L1 feature diagram."
> "Compare `./old` and `./new` — what changed?"

The full step-by-step chains (single version, backfill, incremental) and the exact JSON shapes live in [`CLAUDE.md`](CLAUDE.md).

## The execution gate — what will block you, and why

A PreToolUse gate **structurally enforces** the one path. You can't talk your way around it; you satisfy it by running the steps in order.

- **`edge_residue` first.** It stamps `.the-door/checklist.json` (recording the analyzed node set, a contract version, and a per-file `(mtime, size)` fingerprint).
- **`snapshot_write` / `snapshot_patch` are denied** unless the checklist is **current**, the `source_nodes` you're writing are **covered** by the stamped node set, and **no analyzed file has changed** since the stamp (deletion / in-place modification → staleness deny). If you edited code after `edge_residue`, re-run `edge_residue`.
- **Native code-exec is blocked.** Ad-hoc inline `python -c` / standalone `.py` scripts that bypass the MCP tools are denied; `python -m` (pytest / pip / the_door), `pytest`, `pip`, `git`, and `the-door` are allowed.

When a call is denied, the gate's stderr tells you the next step and points back to the single authority (`system_status` / `the-door status`). That message is the source of truth for what to do next.

## → Read this next

[`CLAUDE.md`](CLAUDE.md) — the complete agent decision tree, tool schemas, and operating chains. Start there before driving The Door.

---

# Reference

## Architecture (one-line summary)

```
Code → AST extraction (tree-sitter, 305+ languages)
     → Topology analysis (dependency ordering, fully local)
     → [agent-as-LLM translation OR cached baseline structure]
     → Output validation + Mermaid diagram + JSON report
     → Local UI (display-only diagram workbench)
```

Two paths from the same front-end: the **agent-as-LLM path** (first analysis or re-analysis, driven by your MCP agent) and the **incremental path** (compare current AST to a persisted baseline, no LLM). Everything is local-first — The Door bundles no provider and makes no LLM network call of its own.

> **Terminal state — zero API key (丙案 / T5).** The Door once shipped optional LLM providers and `analyze` / `update` key-paths. Those have been fully retired: there is no provider, no API key, and no provider configuration. The single supported path is agent-as-LLM, structurally enforced by a PreToolUse execution-order gate. See the [CHANGELOG](CHANGELOG.md) for the campaign log.

## License

Dual-licensed:

- **Community Edition** — [AGPL-3.0](LICENSE). Free to use and modify. If you distribute or run a modified version as a network service, you must open-source your modifications under the same terms.
- **Commercial Edition** — If you need to use The Door in a proprietary product or closed-source service without the AGPL-3.0 copyleft obligation, contact the maintainer via the issue tracker.

## Documentation

- [Agent Guide (`CLAUDE.md`)](CLAUDE.md) — Full decision tree for MCP-compatible AI agents (the authoritative agent entry point)
- [User Guide](docs/USER-GUIDE.md) — Every command and flag
- [Product Spec](docs/the-door-spec-v4.1.md) — Design philosophy and architecture decisions
- [Diagram Language Spec](docs/phase-0a/) — L1/L2 diagram language definition
- [Frontend Spec](docs/frontend-local-version-viewer/spec.md) — Local UI design spec
