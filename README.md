English | [繁體中文](README.zh-TW.md)

# The Door

Translates code structure and changes into functional-language diagrams — so non-technical stakeholders can verify what was actually built.

> Translation direction: technical language → functional language. Diagrams are not decoration — they are the verification interface.

---

## What Is This

The Door is a CLI tool + MCP Server + local UI. It reads your codebase and (with an LLM, or through an MCP-capable AI platform) translates it into "functional language" — plain descriptions of what the system does, what changed, and whether anything looks wrong.

**Who it's for:** PMs, project managers, release managers, QA, clients — anyone who needs to confirm that deliverables match commitments, without reading code.

**Core capabilities:**

| Capability | Description |
|---|---|
| Feature translation | Code → functional-language diagram (interactive + Mermaid fallback) + natural-language narrative |
| Version diff | What changed between two versions, risks surfaced first |
| Incremental update | Re-analyze only the features whose source nodes changed — no LLM call needed for the diff itself |
| Scope verification | PM defines sprint scope → auto-compare → flag out-of-scope items |
| Vulnerability scan | Known CVEs in dependencies, integrated into the feature diagram |
| Feature evolution | Multi-version timeline tracking when features appeared and how often they changed |
| Doubt tracking | Anomaly detected → flagged → assigned → resolved (with escalation on timeout) |
| Feature detail panel | Per-feature drill-down: trigger description, confidence rationale, and source node list — visible in the viewer's single-version mode |
| Scope-aware edges | Cross-file relations carry a `resolution` tag (`scope_rule` / `import_alias` / `name_match` / `skipped_dynamic`) so the LLM can weight high- vs low-confidence edges instead of treating all name matches equally |
| **Edge noise projection** | LLM 收到的邊已過濾高 fanout 噪音，動態 dispatch 邊聚合成 caller 級 hint；snapshot 與 viewer 仍保留完整事實。 |
| Local UI | Browser workbench, interactive diagrams, three-layer navigation (L1 → L2 → L3) |
| **Dual-pane onboarding wizard** | Door-metaphor entry flow with real-time file-level progress feed | v1.5.0 |

---

## Install

```bash
pip install the-door
```

Requires Python ≥ 3.10. Optional: `osv-scanner` (vulnerability scan), `ollama` (local LLM).

---

## Three Ways In

Pick the one that fits your situation. The first is the safest — it inspects your project and tells you the next command for **your** situation.

### 1. `the-door status` — when you're not sure what state your project is in

```bash
the-door status ./my-project
```

It reports whether the project has been analyzed, whether the source has changed since the last snapshot, and prints a **`Next:`** block — the exact command to run next. Run this before anything else when you're cold-starting.

### 2. MCP via an AI platform — no API key needed

If you use **Claude Code**, **Kiro IDE**, or any other MCP-compatible AI tool, the AI handles the analysis itself — The Door only reads code and writes results.

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

The full tool-call sequence the AI follows is documented in [`CLAUDE.md`](CLAUDE.md).

### 3. CLI direct — when you have your own LLM API key

```bash
the-door config init    # one-time, fill in your OpenAI / Anthropic / Ollama key
the-door analyze ./my-project
```

---

## Typical Workflows

### A. First analysis (establish a baseline)

```bash
the-door analyze ./my-project
```

Runs the full pipeline: AST extraction → LLM feature identification → vulnerability scan → snapshot saved automatically to `.the-door/snapshots/`. The output ends with a **`Next:`** block telling you what to do next.

By default, the full node signature, docstring, and decorators are sent to the LLM for higher-quality descriptions. If you're token-constrained, add `--minimal-context` to revert to the legacy node-id-only mode:

```bash
the-door analyze ./my-project --minimal-context
```

### B. After your source has changed (incremental — no API key needed for the diff)

When you already have a baseline snapshot and just want to see what changed:

```bash
the-door update --from-snapshot v1.0 ./my-project
```

Re-extracts your current AST, diffs it against the baseline's persisted structure, and attributes each change to a feature. This step is **pure AST + diff** — no LLM call, no API key required. Use this in your day-to-day loop after the first `analyze`.

Need a CLI diff against an earlier snapshot without changing anything?

```bash
the-door diff ./my-project --baseline v1.0
```

### C. Visualize in the browser

```bash
the-door ui ./my-project
```

Opens a three-panel workbench at `http://127.0.0.1:8765`: left = feature list / change list (risk-prioritized), center = interactive diagram (Cytoscape.js), right = detail panel. Three-layer navigation: L1 feature overview → L2 module diagram → L3 source node graph. The detail panel surfaces trigger description, confidence rationale, and source nodes for each feature.

### D. Backfill a snapshot that's missing its persisted structure

If `update --from-snapshot` complains that the baseline has no persisted AST (typically because the snapshot predates the structures cache) and you still have the original source on disk:

```bash
the-door extract --as-version v1.0 ./baseline-source
```

No API key needed — this re-extracts the AST and saves it under `.the-door/structures/<vid>.json.gz`, after which `update --from-snapshot` works normally.

---

## Snapshot References

Any command or tool that takes a baseline argument (`--baseline`, `--from-snapshot`, `inherit_from`) accepts five reference forms:

| Form | Example | Notes |
|---|---|---|
| Snapshot label | `v1.0.0`, `my-baseline` | Set explicitly when you ran `analyze` |
| Git tag | `v1.0.0` | The tag attached to the commit at snapshot time |
| Date | `2026-05-06` | Resolves to the most recent snapshot on or before |
| Commit SHA (≥7 chars) | `8de9b18` | |
| UUID | full `version_id` | Useful when chaining tool calls |

The viewer's version picker prefers `git_tags[0]` → `label` → `version_id`, so URLs you share are usually human-readable.

---

## Configuration

`the-door config init` creates `~/.the-door/config.toml`. Three providers are supported — OpenAI, Anthropic, Ollama. Environment variables (`THE_DOOR_OPENAI_KEY`, `THE_DOOR_ANTHROPIC_KEY`, `THE_DOOR_OLLAMA_URL`) take precedence.

For the full reference (every command, every flag, every API endpoint), see [`docs/USER-GUIDE.md`](docs/USER-GUIDE.md).

---

## Architecture (one-line summary)

```
Code → AST extraction (tree-sitter, 305+ languages)
     → Topology analysis (dependency ordering, fully local)
     → [LLM translation OR cached baseline structure]
     → Output validation + Mermaid diagram + JSON report
     → Local UI (interactive diagram workbench)
```

Two paths from the same front-end: the LLM-driven path (first analysis or re-analysis) and the incremental path (compare current AST to a persisted baseline, no LLM). Snapshots are local-first; the only network call is the LLM itself.

> **v1.6.0 — internals hardening (no behavior change).** The HTTP API layer, data models, snapshot reference resolution, and doubt lifecycle were each decomposed into single-source-of-truth modules (`core/ui/api/`, `models/`, `BaselineResolver`, `DoubtLifecycle`), and snapshot persistence now passes through one fail-closed contract chokepoint. CLI / MCP / viewer behavior is byte-for-byte unchanged; see the [CHANGELOG](CHANGELOG.md) for the full campaign log.

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
