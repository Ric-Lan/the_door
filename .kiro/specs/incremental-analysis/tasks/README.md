# Tasks — Coherence Layer & Incremental Analysis

This directory implements [requirements.md](../requirements.md) and [design.md](../design.md). Tasks are split across seven files by **skill profile** — what kind of engineering work the file demands. Each file is self-contained: a fresh agent can pick one up, read its skill profile + dependencies + tasks, and execute end-to-end.

## File layout

| # | File | Scope | Skill profile |
|---|---|---|---|
| 00 | [00-test-infrastructure.md](00-test-infrastructure.md) | Property test setup, contract-test seams between task tiers, v105 end-to-end scenario gate | Python: hypothesis property tests, pytest fixtures, integration scenario design, tier-aware skip markers |
| 01 | [01-core-data.md](01-core-data.md) | P1 + P2 + P3 — snapshot store, per-version structure persistence, AST extractor disambiguation | Python: dataclasses, JSON I/O, gzip, deterministic post-processing, pytest fixtures |
| 02 | [02-guidance-engine.md](02-guidance-engine.md) | F1 + F2 + F3 — entire `core/guidance/` package: state model, inspector, suggester, remediation, envelope | Python: frozen dataclasses, pure-function decision-tree design, JSON serialization, golden-file tests |
| 03 | [03-pipeline-mcp.md](03-pipeline-mcp.md) | O1 + S2 — feature_attribution pure fn, incremental_pipeline, new/extended MCP tools, MCP coverage meta-test | Python: pipeline orchestration, MCP tool authoring + registration, response-envelope DRY |
| 04 | [04-cli-ux.md](04-cli-ux.md) | S1 + the two new CLI flags from O1 — status command, post-run Next: hook, next_action_renderer, CLI meta-test, `update --from-snapshot`, `extract --as-version` | Python: Click commands, post-run hooks, CLI testing (CliRunner), meta-test pattern |
| 05 | [05-viewer-frontend.md](05-viewer-frontend.md) | S3 + viewer-side of O2 — `ui-detail.js` regression fix, `buildMindmapData`, onboarding card, `ui-next-actions.js` helper, version picker label-first, `/api/status` endpoint, `/api/diff` fallback resolver | JavaScript: viewer state, sessionStorage, vanilla JS modules + Python: HTTP API handler edits |
| 06 | [06-docs.md](06-docs.md) | S4 — CLAUDE.md restructure to decision-tree form | Technical writing: information architecture, decision-tree clarity |

## Dependency graph

```
00-test-infrastructure ──→ 01-core-data ─┬─→ 02-guidance-engine ─┬─→ 03-pipeline-mcp ──→ 04-cli-ux (--from-snapshot, --as-version)
                                         │                       │                    └→ remaining 04 tasks (status, hook, meta-test)
                                         │                       └─→ 05-viewer-frontend
                                         └─→ 03-pipeline-mcp (for P2's get_structure)
                                         
06-docs depends on every command/tool above being implemented (writes the user-facing decision tree).
```

**Strict ordering**: 00 first — it lays down the property/contract/scenario test harness everything else writes against. 01 next. Then 02 (entire `core/guidance/`). After 02, files 03, 04 (status+hook subset), and 05 may proceed in parallel. The --from-snapshot/--as-version subset of 04 waits on 03. 06 is last.

## Why 00 exists (and goes first)

Pure example-based TDD has two well-known blind spots that show up across a multi-task spec:

1. **The "I didn't think of that case" residual bug** — A unit's RED test only covers scenarios the author predicted. Edge cases nobody listed pass silently because no test exercises them.
2. **The cross-task continuity gap** — Task A and Task B each pass their unit tests in isolation, but the contract between them drifts. Field-shape mismatches, precondition assumption mismatches, and order-of-operations bugs only surface when you actually compose A and B in production.

00-test-infrastructure addresses both before any production code lands:

- **Property tests** (`hypothesis`) for the pure functions identified as "high blind-spot risk" — covers cases the example tests didn't predict.
- **Contract tests** at each task-tier seam — each contract lives in `tests/contract/` and is imported by both producer and consumer task suites, so drift on either side fails both.
- **Scenario gate** — a single `tests/scenario/test_v105_incremental_flow.py` walks the v105 baseline-to-v105.5 incremental flow end-to-end. Skip markers gate each step on its prerequisite tier landing. After every task lands, the scenario runs further — composition is exercised continuously, not just at "all done."

Files 01–06 reference these harnesses; tasks that satisfy a property/contract/scenario remove the matching skip marker.

## Cross-cutting conventions

These apply to every task file. They are task-hygiene rules — distinct from the architectural Execution Constraints in design §Execution Constraints.

1. **One task = one atomic commit.** Each task ends with a `Commit` step. Do not batch.
2. **TDD discipline.** Every implementation step is preceded by a RED test that fails for the predicted reason. If RED fails differently than predicted, stop and re-read the spec.
3. **No comments explaining the change.** Spec is the documentation. Git blame + commit message suffice. No `# Implements F1 AC3` annotations in the code.
4. **No defensive code beyond an AC.** If no AC mandates handling for a case, do not handle it.
5. **No file reads outside the paths named in the task.** Each task lists every file it touches. Reading sibling files for "context" is not allowed — if a task lacks context you need, stop and report.
6. **No spec edits during execution.** If the spec is wrong, stop and report. Do not "fix as we go."
7. **Verification scope.** "Verify GREEN" = run the specific test file(s) the task created. "Full suite" = `pytest the_door/tests/unit/ the_door/tests/integration/ -q` (Python) or `npm run test:coverage` (JS). After each task in 01–06: **also run** `pytest the_door/tests/contract/ the_door/tests/scenario/ -q` to detect drift across tiers; this is what 00 enables.
8. **Commit-prefix convention.** Use the prefix listed in each task file's `Commit conventions` section.
9. **Removing scenario skip markers is the task's responsibility.** Whenever a task in 01–06 lands a feature gated by a `pytest.skip("blocked on <task-id>")` marker in `tests/scenario/` or `tests/contract/`, the same commit that adds the feature also removes the matching skip. If the scenario step fails after removing the skip, it means the integration is broken — stop and report.

## How to consume a task file

Each task file has:

1. **Header** — file scope + skill profile + dependencies + commit conventions.
2. **Requirements covered** — exact requirement IDs from requirements.md.
3. **Files touched** — every path the file's tasks edit or create.
4. **Tasks** — numbered, each with a `Files` list and `Steps` checklist. Steps are bite-sized (2–5 minutes), with code snippets where steps modify code, exact commands where steps run something.
5. **Done criteria** — what observable behavior demonstrates the file is complete.

## Done criteria for the entire spec

The spec is complete when:

1. Every task file's individual Done criteria are met.
2. `pytest the_door/tests/unit/ the_door/tests/integration/ -q` passes (baseline ~580 → ~625+ after all RED tests become GREEN).
3. `pytest the_door/tests/contract/ the_door/tests/scenario/ -q` passes with **zero remaining `pytest.skip("blocked on ...")` markers** — every tier seam has a live contract; the v105 scenario runs end-to-end.
4. `cd docs/frontend-local-version-viewer/viewer && npm run test:coverage` passes (baseline ~571 → ~590+).
5. End-to-end scenario: `the-door update --from-snapshot v1.0.0 C:\Users\Ric\Desktop\test-targets\the-door-v105` produces a snapshot where only `feat-ui-server` appears in `affected_features`; viewer mindmap shows `Δ` badge on that feature; viewer detail panel renders "使用者備註" + "AI 差異說明" sections.
6. `the-door status` is the documented entry point in CLAUDE.md; every reachable state suggests at least one next action.
