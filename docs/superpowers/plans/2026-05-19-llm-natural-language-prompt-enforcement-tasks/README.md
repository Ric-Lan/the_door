# LLM Natural-Language Prompt Enforcement — Task Documents

This directory splits the source plan
[`../2026-05-19-llm-natural-language-prompt-enforcement.md`](../2026-05-19-llm-natural-language-prompt-enforcement.md)
into three self-contained, independently shippable task documents — one per
phase. Each file is a complete `writing-plans` document: a fresh agent can pick
one up and execute it end-to-end without reading the others.

## Why split this way

The source plan's three phases are explicitly "self-contained and shippable
independently." Splitting by phase keeps each task document focused on one
prompt surface, one code area, and one commit-able outcome.

| # | File | Scope | Touches |
|---|---|---|---|
| 01 | [01-l1-feature-description-prompt.md](01-l1-feature-description-prompt.md) | Create the L1 system prompt that does not exist today and wire it through the two `batch_reader` provider calls. | `core/llm/prompts.py` (new), `core/reading/batch_reader.py` |
| 02 | [02-l2-anomaly-prompt.md](02-l2-anomaly-prompt.md) | Rewrite the L2 anomaly prompt to enforce a per-module checklist over the 3 AST-judgeable anomaly types. | `core/ui/l2_generator.py` |
| 03 | [03-diff-explanation-prompt.md](03-diff-explanation-prompt.md) | Strengthen the diff-explanation prompt with an explicit forbidden-jargon list and worked examples. | `core/ui/api_handlers.py` |

## Dependency order

```
01-l1-feature-description-prompt ──(creates core/llm/prompts.py)
02-l2-anomaly-prompt             ──(independent)
03-diff-explanation-prompt       ──(independent)
```

01 must land before any future work that imports from `core/llm/prompts.py`.
02 and 03 have no dependency on 01 or each other — they may proceed in any
order or in parallel. There is no shared test harness between the three.

## Shared design principle

The deeper the layer, the less it should be LLM-translated:

- **L1** (feature) = non-technical reader critical-need; natural language is thickest.
- **L2** (module) = developer territory; label + interactions only, thin.
- **L3** (node) = pure structure; zero natural language.
- **Function-level code translation** = out of scope (open the file directly).

Cross-cutting critical-need information (anomalies / diffs / changes) must
bubble up to L1 and be expressed in natural language.

## Out of scope (applies to all three files)

- L2 module description / responsibility fields (violates "the deeper, the less NL").
- L3 natural language (pure structural layer).
- Function-level code translation.
- Vulnerability data plumbing into L2 (separate follow-up plan — see below).
- Runtime LLM-output gating (separate follow-up plan — see below).
- Viewer front-end display bugs.
- Pipeline structural changes (snapshot persistence, diff_engine rules).

## Why no validator module / forbidden-jargon detector

A previous draft proposed a `nl_quality.py` regex-based validator. Removed because:

- It would be used in exactly one test (verifying a prompt's own examples don't
  violate its own rules).
- Pattern enforcement at runtime (gating LLM output) is not in scope.
- A regex like `[A-Za-z_][A-Za-z0-9_]*\s*\(` for "function call" produces false
  positives on English control flow (`if (`, `for (`).
- Maintaining a forbidden list in three places (L1 prompt text, diff_explanation
  prompt text, validator code) creates drift risk.

Inline assertions in the prompt-content tests achieve the same goal at much
smaller cost.

## Out-of-Plan Follow-ups

Real concerns, but out of scope for every file here:

1. **Plumb vulnerability data into `L2Generator`** — `StructureJSON` has no
   `vulnerabilities` field; `L2Generator.generate(feature_id, structure)` takes
   only two parameters. To enable `vuln_high` / `vuln_medium` anomaly emission,
   `VulnerabilityEntry` must be threaded from `analyze_pipeline.py` to the L2
   call site. Structural pipeline change — separate plan.
2. **Runtime LLM-output gating** — check LLM output against forbidden jargon and
   warn / retry. Requires deciding failure handling. Separate plan.
3. **L1 description quality verification on existing snapshots** — re-run analyze
   on `the-door-v105` to produce snapshots reflecting the strengthened L1 prompt
   and visually verify on the viewer. Operational, not implementation.
