English | [繁體中文](README.zh-TW.md)

# The Door

Translates code structure and changes into functional-language diagrams — so non-technical stakeholders can verify what was actually built.

> Translation direction: technical language → functional language. Diagrams are not decoration — they are the verification interface.

---

## What Is This

The Door is a CLI tool + MCP Server + local UI. Driven by an MCP-capable AI platform (Claude Code, Kiro, …), it reads your codebase and translates it into "functional language" — plain descriptions of what the system does, what changed, and whether anything looks wrong.

**The Door bundles no LLM provider and needs no API key.** The AI agent driving it *is* the LLM: The Door extracts code structure deterministically, the agent produces the natural-language layer, and The Door persists it. See [Zero API key — one path](#zero-api-key--one-path).

**Who it's for:** PMs, project managers, release managers, QA, clients — anyone who needs to confirm that deliverables match commitments, without reading code.

**Core capabilities:**

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

---

## Install

```bash
pip install the-door
```

Requires Python ≥ 3.10. Optional: `osv-scanner` (vulnerability scan).

---

## Zero API key — one path

The Door has **no LLM provider** and **no `analyze` / `update` / `config` commands**. Every step that needs natural language is performed by the AI agent over MCP (agent-as-LLM). There is exactly one path:

```
extract_structure  →  (agent identifies L1 features)  →  edge_residue  →  snapshot_write
```

`extract_structure` and `edge_residue` are deterministic and run locally; the agent supplies the natural-language layer; `snapshot_write` persists it. A PreToolUse gate enforces this order: `edge_residue` stamps an execution checklist, and the gate denies `snapshot_write` unless that checklist is current and the nodes being written are covered by it. The full tool-call sequence is documented in [`CLAUDE.md`](CLAUDE.md).

---

## Two Ways In

### 1. `the-door status` — when you're not sure what state your project is in

```bash
the-door status ./my-project
```

It reports whether the project has been analyzed, whether the source has changed since the last snapshot, and prints a **`Next:`** block — the exact next step for **your** situation. Run this first when cold-starting.

### 2. MCP via an AI platform — the analysis path

If you use **Claude Code**, **Kiro IDE**, or any other MCP-compatible AI tool, the AI performs the analysis itself — The Door only reads code and writes results.

Add this to your AI platform's MCP config:

```json
{
  "mcpServers": {
    "the-door": { "command": "the-door", "args": ["mcp-serve"] }
  }
}
```

Then just talk to the AI:
> "Analyze `./my-project` and give me the L1 feature diagram."
> "Compare `./old` and `./new` — what changed?"

The exact tool-call sequence the AI follows is documented in [`CLAUDE.md`](CLAUDE.md).

---

## Typical Workflows

### A. First analysis (establish a baseline) — agent-driven

Through MCP, ask your AI agent to analyze the project. It runs `extract_structure` → identifies the L1 features → `edge_residue` → `snapshot_write`, saving a snapshot to `.the-door/snapshots/`. No API key, no provider — the agent is the LLM.

There is no `the-door analyze` CLI command; first analysis is always agent-driven.

### B. After your source has changed (incremental)

Ask your agent to run `analyze_changes` against the baseline. It returns only the features whose source nodes changed; the agent re-derives just those and calls `snapshot_write` with `inherit_from` so unchanged features are inherited. The diff itself is **pure AST** — no LLM call.

Need a CLI diff against an earlier snapshot without changing anything?

```bash
the-door diff ./my-project --baseline v1.0
```

### C. Visualize in the browser

```bash
the-door ui ./my-project
```

Opens a three-panel workbench at `http://127.0.0.1:8765`: left = feature list / change list (risk-prioritized), center = interactive diagram, right = detail panel. Three-layer navigation: L1 feature overview → L2 module diagram → L3 source node graph. The viewer is display-only — it reads persisted snapshots and never calls an LLM.

### D. Backfill a snapshot that's missing its persisted structure

If `analyze_changes` reports that the baseline has no persisted AST (typically because the snapshot predates the structures cache) and you still have the original source on disk:

```bash
the-door extract --as-version v1.0 ./baseline-source
```

No API key needed — this re-extracts the AST and saves it under `.the-door/structures/<vid>.json.gz`, after which incremental analysis works normally.

---

## Snapshot References

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

---

## License

Dual-licensed:

- **Community Edition** — [AGPL-3.0](LICENSE). Free to use and modify. If you distribute or run a modified version as a network service, you must open-source your modifications under the same terms.
- **Commercial Edition** — If you need to use The Door in a proprietary product or closed-source service without the AGPL-3.0 copyleft obligation, contact the maintainer via the issue tracker.

---

## Documentation

- [Agent Guide (`CLAUDE.md`)](CLAUDE.md) — Full decision tree for MCP-compatible AI agents
- [User Guide](docs/USER-GUIDE.md) — Every command and flag
- [Product Spec](docs/the-door-spec-v4.1.md) — Design philosophy and architecture decisions
- [Diagram Language Spec](docs/phase-0a/) — L1/L2 diagram language definition
- [Frontend Spec](docs/frontend-local-version-viewer/spec.md) — Local UI design spec
