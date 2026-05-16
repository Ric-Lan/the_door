# 06 — Documentation (S4)

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` or `superpowers:executing-plans`.

**Goal:** Restructure `CLAUDE.md` from the current "Mode A / Mode B parallel description" form into a decision-tree shape that leads readers from "I just installed this" to "I'm running the exact right command for my situation" in one read. Make `the-door status` the documented entry point.

**Skill profile:** Technical writing — information architecture, decision-tree clarity, audience awareness (the readers are both humans and AI agents). No code. Validation is content-based.

**Dependencies:** Every other task file must have landed first — this file documents the new commands, MCP tools, and workflow they introduce. Specifically:
- `the-door status` from [04-cli-ux.md](04-cli-ux.md) (Task 04.2)
- `the-door update --from-snapshot` from [04-cli-ux.md](04-cli-ux.md) (Task 04.5)
- `the-door extract --as-version` from [04-cli-ux.md](04-cli-ux.md) (Task 04.6)
- `analyze_changes` MCP tool from [03-pipeline-mcp.md](03-pipeline-mcp.md) (Task 03.5)
- `system_status` MCP tool from [03-pipeline-mcp.md](03-pipeline-mcp.md) (Task 03.4)
- `snapshot_write` `inherit_from` extension from [03-pipeline-mcp.md](03-pipeline-mcp.md) (Task 03.6)

**Commit conventions:** `docs(claude_md):`.

## Requirements covered

- [S4 — Documentation Surface](../requirements.md#requirement-s4-documentation-surface) — design §S4

## Files touched

| Path | Action |
|---|---|
| `CLAUDE.md` | Replace top-level structure with decision-tree form; preserve old terminology in a glossary section at the bottom |

---

## Task 06.1 — S4.1/S4.2: Restructure CLAUDE.md to decision-tree form

**Files:**
- Modify: `CLAUDE.md` (single file, full rewrite of the body, glossary section preserved at bottom)

- [ ] **Step 1: Read the current CLAUDE.md**

Read the existing file end-to-end. List the existing top-level sections and the example commands they reference. Confirm the current ordering: "Mode A (External LLM)" → "Mode B (Agent-as-LLM)" → "Snapshot Reference Format" → "Key Constraints".

- [ ] **Step 2: Draft the new outline as a plain-text checklist**

The target outline:

```
# The Door — AI Agent Guide

## ⚠️ Start here: `the-door status`
[Brief — always run this first; it tells you the state and prints Next:]

## Decision tree
[Five branches, each ending in exactly one command — no parallel "or" leaves]

### Branch 1 — Have you analyzed this project before?
- No → `the-door analyze <path>` (with API key)
   OR `extract_structure` MCP → `snapshot_write` MCP (without API key)
- Yes → continue to Branch 2

### Branch 2 — Has the source changed since the last snapshot?
- No → "Want to inspect / visualize?" → `the-door ui <path>` OR `the-door diff --baseline <prev> <path>`
- Yes → continue to Branch 3

### Branch 3 — Do you have an API key?
- Yes → `the-door update --from-snapshot <label> <path>`
- No → MCP `analyze_changes` → agent updates affected features → MCP `snapshot_write` with `inherit_from`

### Branch 4 — `the-door update --from-snapshot` says "no persisted structure for baseline" — what now?
- Still have baseline source on disk → `the-door extract --as-version <baseline_label> <baseline_source>` (backfill, no API key needed)
- No baseline source → re-run full analysis with `the-door analyze <current_path>` (loses historical baseline)

### Branch 5 — None of the above feels right
- → `the-door status` and follow its Next: block

## Commands & MCP tool reference
[Compact table — name, what it does, link to spec for details]

## Snapshot reference formats
[Carry over from current CLAUDE.md — labels / tags / dates / SHA / UUID all work]

## Glossary (backward compatibility)
- Mode A (legacy term): External LLM via API key. Now: "with API key" branches above.
- Mode B (legacy term): Agent-as-LLM. Now: "without API key" branches above.
- (Plus other terms readers might cache from old docs.)

## MCP server setup
[Carry over from current CLAUDE.md unchanged]
```

- [ ] **Step 3: Apply S4.4 requirement — `the-door status` as documented entry point**

The "Start here" section must put `the-door status` first. Every "what now?" question downstream must answer with "run `the-door status`" as a fallback.

- [ ] **Step 4: Apply S4.3 — every leaf shows the exact command + expected output**

For each terminal branch, include a code block showing the exact command + the abridged Next: block the user will see. Example:

```bash
$ the-door analyze ./my-project
✓ Extracted 169 files / 1431 nodes
✓ Wrote snapshot abc12345-... labeled "v1.0.0"

Next:
  1. the-door ui ./my-project          (open viewer)
  2. the-door diff --baseline v1.0.0   (CLI diff next version)
```

- [ ] **Step 5: Apply S4.5 — backward-compat glossary**

The glossary must contain entries for at least: "Mode A", "Mode B", "snapshot reference", "Next: block". Each entry links to the new structure's relevant section.

- [ ] **Step 6: Apply S4.6 — no internal data structures**

Do not document `SystemState` fields, `NextAction` schema, or `Remediation.code` enums in CLAUDE.md. Link to `.kiro/specs/incremental-analysis/design.md` for those.

- [ ] **Step 7: Write the new CLAUDE.md**

Replace the body. Preserve the existing `## ⚠️ 開發環境速查` block at the top — it is local dev environment guidance, not a flow doc, and stays load-bearing for future sessions.

- [ ] **Step 8: Verify content rules manually**

Run a self-check checklist (no code):

- [ ] `grep "the-door status" CLAUDE.md` finds the term in the "Start here" section AND in at least one branch.
- [ ] `grep -n "Mode A\|Mode B" CLAUDE.md` finds matches ONLY in the Glossary section (no occurrence above it).
- [ ] Every decision-tree leaf names exactly one command. No "or"-style branching at the leaf.
- [ ] Every code block shows the abridged Next: block.
- [ ] No section describes internal data structures.

- [ ] **Step 9: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude_md): restructure to decision-tree with the-door status as entry point (S4)"
```

---

## Done criteria for 06-docs

1. `grep "the-door status" CLAUDE.md` returns ≥ 2 lines (Start here section + at least one fallback in a branch).
2. `grep "Mode A\|Mode B" CLAUDE.md` returns matches only in the Glossary section.
3. A new reader (human or agent) reads the file once and ends with one specific next command to run — no ambiguity at any decision-tree leaf.
4. CLAUDE.md does not duplicate spec-internal data structures (SystemState fields, NextAction schema). Spec references are via `.kiro/specs/incremental-analysis/design.md` links.
5. The existing `## ⚠️ 開發環境速查` block remains at the top, unchanged.
