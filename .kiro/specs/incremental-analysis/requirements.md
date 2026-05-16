# Requirements Document — Coherence Layer & Incremental Analysis

## Introduction

### Root Cause This Spec Addresses

The Door currently ships as a collection of primitives — `extract`, `analyze`, `snapshot_write`, `diff`, `ui` — without a coherence layer connecting them. Every user (human or AI) is forced to:

1. **Hold the system state in their head**: read `.the-door/` filesystem, guess what's been done.
2. **Map their intent onto which primitive to call**: with no canonical "next action" signal.
3. **Recover from errors with no guidance**: errors describe what failed, not what to do next.
4. **Stitch primitives into a workflow themselves**: `extract` → ??? → `snapshot_write` → ??? → `ui`.

Symptoms observed in a 2026-05-16 session (logged in `.kiro/specs/incremental-analysis/` git history):

- A session attempting "analyze v1.0.5" required hand-written Python in `C:\Temp\`, multiple `the-door extract` round-trips, and 30+ minutes of code-reading to discover that no `update --from-snapshot`-style flow exists.
- `/api/diff?baseline=v1.0.0` returns 404 because the diff API silently demands UUIDs even though the CLI accepts labels.
- Mindmap shows no diff markers because it reads `state.updateModel.changes` (report-based, often null) and ignores `state.versionDiff.node_states` (snapshot-comparison, populated by the user's actual selection).
- Detail panel "使用者備註" silently disappeared after the `app.js` refactor because `ui-detail.js` left two `_appendXSection` no-op stubs untouched.

These are not seven unrelated bugs — they are seven manifestations of the same missing layer.

### What This Spec Builds

A four-tier dependency chain, written so that downstream tiers derive from upstream ones:

```
Foundation         F1 SystemState model      F2 NextAction model     F3 Remediation model
                       │                          │                       │
                       └──────────────┬───────────┴───────────┬───────────┘
                                      │                       │
Primitives          P1 Snapshot store invariants    P2 Per-version structure    P3 AST node_id uniqueness
                                      │                       │
                                      └───────────┬───────────┘
                                                  │
Operations          O1 Incremental analysis                O2 Snapshot reference resolution
                                                  │
                                                  │
Surfaces            S1 CLI    S2 MCP    S3 Viewer    S4 Docs
                       (all four consume Foundation, are powered by Primitives + Operations)
```

**Derivation direction is strictly one-way.** Foundation must be designed without knowing the surfaces; surfaces must consume Foundation interfaces verbatim, not invent their own state. This is the structural property that prevents the rework risk called out in pre-spec review.

### Architecture vs Task-Refinement Convention

Each Requirement below mixes two layers:

- **Architectural commitments** — binding contracts. The implementing task MUST satisfy these verbatim. Examples: responsibility ownership, dependency direction, contract type signatures, invariants.
- **Task-time refinement detail** — working sketches retained for continuity (so the task document doesn't reinvent them). Examples: exact error codes, flag mutex matrices, specific helper function names, performance budget breakdowns, exact CLI flag spelling, exact JSON output formats. These are **starting points**, not contracts. Tasks confirm or refine them; refinements do not require spec revision.

Where a Requirement contains task-refinement detail, a `> [Task-refine]` callout at the end of the Requirement enumerates which ACs (or which clauses of an AC) are detail. Everything else is architecturally binding.

This convention exists so:
1. Reading the spec at architecture phase, you can ignore the `> [Task-refine]` lines and still see all binding contracts.
2. At task phase, the same content serves as a working starting point — no duplication of effort.
3. Drift between layers is observable: a task whose tests fail against an architectural commitment surfaces an architecture gap; a task that finds a refinement clause infeasible just refines it.

### What This Spec Does NOT Build

See the Non-Requirements section at the bottom. Critically: this spec is not a rewrite. Every existing primitive (`extract`, `analyze`, `snapshot_write`, viewer) keeps its current top-level contract; what changes is **what each primitive emits** (state changes, next-action signals) and **what surfaces consume**.

## Glossary

- **SystemState**: A read-only, deterministic snapshot of the project's `.the-door/` directory state plus runtime configuration (API key availability, provider). Single source of truth for "what has been done."
- **NextAction**: A structured recommendation of one operation a user could perform next, given the SystemState and the current ActionContext. Carries an executable form (CLI command, MCP tool call, or viewer route).
- **Remediation**: Structured guidance attached to an error. Every error raised by The Door's code must carry one. Contains a NextAction in most cases.
- **ActionContext**: The surface the user is currently interacting with: `cli`, `mcp`, `viewer`, or `after_error`. Inputs to the suggester. Different surfaces get differently-formatted suggestions.
- **NextActionSuggester**: A pure, deterministic function `(SystemState, ActionContext) -> list[NextAction]`. No LLM, no randomness.
- **Primitive**: A unit of work that mutates `.the-door/` (e.g., snapshot writer) or reads it (e.g., AST extractor). Primitives are responsible for emitting accurate state and surfacing warnings.
- **Operation**: A composed workflow built on top of one or more Primitives. Operations exist because the SystemState + suggester make them discoverable.
- **Surface**: Any user-facing entry point — CLI, MCP, viewer, error message. All surfaces are consumers of Foundation and producers of `next_actions` in their responses.

## Requirements

---

## Foundation Tier

### Requirement F1: SystemState Model

**User Story:** As any consumer (CLI command, MCP tool, viewer API handler, error formatter), I want a single canonical query to obtain the project's current state, so that I do not need to scrape the filesystem myself or reimplement state derivation.

#### Acceptance Criteria

1. WHEN any caller invokes `StateInspector(project_path).inspect()`, THE system SHALL return a `SystemState` containing exactly the fields enumerated in design.md §F1, with no caller-supplied parameters affecting which fields are populated.
2. THE `SystemState` SHALL be a frozen, hashable dataclass — callers SHALL NOT mutate it.
3. THE inspection SHALL complete in < 50 ms on a project with 200 files and 10 snapshots. Rationale: every CLI command runs `inspect()` post-execution to render its `Next:` block (S1 AC2). Three chained `the-door` commands at 50 ms each adds 150 ms of overhead — below the ~200 ms human "instant" threshold. A 200 ms inspection would push that to 600 ms and become user-noticeable. Implementation guidance (per-step budget) is in design §F1.
4. THE inspection SHALL NOT call any LLM, network endpoint, or external process beyond `os.stat` / `pathlib.Path` operations and reading existing JSON files under `.the-door/`.
5. WHEN a snapshot JSON file is corrupted (invalid JSON, missing required field), THE inspection SHALL emit a `StateWarning` for that snapshot AND continue inspection — it SHALL NOT raise.
6. WHEN `.the-door/structure.json` exists but the per-version `structures/<latest_vid>.json.gz` is missing, THE inspection SHALL set `has_structure_json=True` and each `SnapshotEntry.has_persisted_structure` accordingly (a missing per-version file does not invalidate the latest-pointer file). Per-snapshot structure availability is exposed only via `SnapshotEntry.has_persisted_structure`; SystemState does not maintain a separate aggregate set. **Detail counts (structure node count, file count) are NOT carried in SystemState** — they are read on-demand by S1's status command at display time, keeping `inspect()` within budget.
7. THE inspection SHALL detect API key availability by checking, in order: `ANTHROPIC_API_KEY` env var, `OPENAI_API_KEY` env var, `~/.the-door/config.toml`. Result populates `SystemState.has_api_key` (bool) and `SystemState.api_provider` (string or None).
8. WHEN the project has no `.the-door/` directory at all, THE inspection SHALL return a valid `SystemState` with `has_dot_the_door=False` and all dependent fields set to their empty defaults (no exceptions).

> **[Task-refine]** AC3's specific 50 ms threshold and "200 files / 10 snapshots" reference scale, and AC7's exact env-var key names (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`) and config-file path (`~/.the-door/config.toml`) are working sketches. Architectural commitments are: (a) inspection must be cheap enough to run on every CLI command without user-perceptible lag, (b) API key detection must check the user's runtime environment in a defined precedence with environment variables taking priority over config files.

### Requirement F2: NextAction Model + Suggester

**User Story:** As a surface (CLI, MCP, viewer), I want to ask "given the current state and where the user is, what should I tell them to do next?" and get a deterministic, ranked answer, so that every surface presents consistent guidance without re-inventing decision logic.

#### Acceptance Criteria

1. THE `NextAction` SHALL be a frozen dataclass containing exactly the fields enumerated in design.md §F2. Mandatory: `id`, `title`, `rationale`, `priority`. Exactly one of `cli_command`, `mcp_tool` (+ `mcp_arguments`), `viewer_route` SHALL be set per action.
2. THE `NextActionSuggester.suggest(state, context, failure_code=None)` SHALL be a pure function — same `(state, context, failure_code)` always returns the same list in the same order. The `failure_code` parameter is optional, used ONLY when `context="after_error"` to bias suggestions toward the specific failure mode (per design §F2 after-error sub-table). Other contexts SHALL pass `failure_code=None`.
3. THE suggester SHALL return actions sorted by `priority` ascending (1 = top recommendation).
4. THE suggester SHALL contain NO LLM call, NO randomness, NO time-based logic. It is a decision tree over `SystemState` fields.
5. WHEN multiple actions are tied for top priority, THE order between them SHALL be determined by `NextAction.id` lexicographic order — deterministic tie-break.
6. THE suggester's rule set SHALL be enumerable in design.md as a flat table mapping `(state predicate, context)` to `NextAction.id`. Tests assert each row.
7. WHEN no actions apply to the given state (e.g., empty project, no API key, viewer context with nothing to do), THE suggester SHALL return at minimum one fallback action with `id="onboarding.read_claude_md"` pointing at the docs.
8. THE suggester SHALL NOT depend on F3 (Remediation); Remediation depends on the suggester. One-way dependency.

> **[Task-refine]** AC5's specific tie-break mechanism (lexicographic `NextAction.id`) and AC7's exact fallback action id (`onboarding.read_claude_md`) are working sketches. Architectural commitments are: (a) tie-breaks must be deterministic, (b) every state must yield at least one suggestion (no empty output).

### Requirement F3: Remediation Model + Standard Error Envelope

**User Story:** As any user (human or AI) hitting an error, I want every error response to tell me what went wrong AND what command or action will fix it, so that I never reach a dead-end where the next move is "go read the source code."

#### Acceptance Criteria

1. THE `Remediation` SHALL be a frozen dataclass containing exactly: `code` (machine-readable, snake_case), `message` (human-readable), `next_action: NextAction | None`, `docs_url: str | None`.
2. THE Door's standard error envelope (for HTTP responses, MCP tool errors, CLI error output) SHALL be exactly:
   ```json
   {
     "error": {
       "code": "<machine_readable>",
       "message": "<human_readable>",
       "remediation": {
         "code": "<machine_readable>",
         "message": "<human_readable>",
         "next_action": { /* NextAction or null */ },
         "docs_url": "<url or null>"
       },
       "source": "<file_or_handler_identifier>"
     }
   }
   ```
3. EVERY error raised by code that becomes user-visible (CLI exit, MCP tool error response, HTTP 4xx/5xx) **within the scope of this spec** SHALL carry a Remediation. Scope: (a) every handler / code path modified by this spec, (b) every new handler / code path introduced by this spec. Out-of-scope handlers elsewhere in the codebase are a separate audit per the Non-Requirements section. Internal-only errors (assertions, programming bugs that should never user-trip) MAY omit it.
4. WHEN an error's exact recovery action is unknown, THE Remediation `next_action` MAY be `null`, but `message` and `docs_url` SHALL still be populated.
5. THE Remediation `code` namespace SHALL be globally unique across The Door — every distinct user-visible failure mode has one code, enumerated in design.md §F3 catalogue.
6. WHEN an existing error message in current code lacks a Remediation, code modified by this spec SHALL add one; out-of-scope code paths MAY be deferred but SHALL be enumerated in design.md as known gaps.
7. THE standard envelope SHALL be backward-compatible with existing API consumers: the top-level `code`, `message`, `source` fields remain in place; `remediation` is purely additive.

> **[Task-refine]** AC6's "in-scope code paths" enumeration (the specific file:line list of error sites that get migrated to the new envelope) is a working sketch — task phase confirms the actual exhaustive list by grepping the codebase. Architectural commitment is: every user-visible error path that this spec touches MUST carry a Remediation by the end of implementation.

---

## Primitives Tier

### Requirement P1: Snapshot Store Source-Nodes Invariant

**User Story:** As a downstream consumer of a snapshot (incremental analysis in O1, viewer in S3, state inspector in F1), I want `source_node_count` to always equal `len(source_nodes)`, so that I have one trustworthy field instead of having to handle drift between two.

#### Acceptance Criteria

1. WHEN `SnapshotStore.create_snapshot` serializes a `FeatureSummary`, THE system SHALL write `source_node_count = len(fs.source_nodes)` regardless of the caller-supplied value. The field is derived-on-write.
2. WHEN `SnapshotStore` deserializes a legacy snapshot with `source_node_count > 0` AND `source_nodes` empty/absent, THE system SHALL:
   - Emit a `StateWarning(code="source_nodes_drift", location="snapshot/<vid>/<feature_id>", ...)` for inclusion in `SystemState.warnings` (per F1).
   - Return the `FeatureSummary` with `source_nodes=()` and `source_node_count=0`.
   - NOT raise.
3. THE `snapshot_write` MCP tool's input schema SHALL mark `source_node_count` as OPTIONAL (current schema at [snapshot_write_tool.py:33](the_door/src/the_door/mcp/tools/snapshot_write_tool.py:33) marks it required). When provided, the value SHALL be ignored in favor of `len(source_nodes)`.
4. THE `FeatureSummary` dataclass at [models.py:340](the_door/src/the_door/models.py:340) SHALL retain its `source_node_count` field for on-disk backward compatibility; field removal is out of scope.
5. THE `timeline_renderer` at [timeline_renderer.py:267](the_door/src/the_door/core/timeline/timeline_renderer.py:267) — the only verified live reader of the field outside model + (de)serializer code — SHALL be migrated to `len(feature.source_nodes)`.
6. NO migration CLI SHALL be created; legacy drift surfaces as a `StateWarning` and is repaired by re-running `the-door analyze`. Path documented in S4.

> **[Task-refine]** AC5's specific file:line reference (`timeline_renderer.py:267`) is a working sketch — line numbers drift; task phase locates the actual current line via grep. Architectural commitment is: every live reader of the legacy field must be migrated to `len(source_nodes)` as part of this requirement.

### Requirement P2: Per-Version Structure Persistence

**User Story:** As O1 (incremental analysis) and any future cross-version operation, I want each version's AST extraction output (`structure.json`) to be persisted alongside its snapshot, so that I can diff against any prior version without keeping that version's source code on disk.

#### Acceptance Criteria

1. WHEN any code path creates a new snapshot via `SnapshotStore.create_snapshot`, the surrounding pipeline SHALL also write `.the-door/structures/<version_id>.json.gz` containing the gzipped form of that version's `StructureJSON`. The structure write is the **caller's** responsibility, not `create_snapshot`'s — to keep SnapshotStore's contract narrow.
2. THE current `.the-door/structure.json` (latest-pointer file) SHALL continue to exist; this requirement is additive.
3. THE system SHALL NOT maintain a `manifest.json` index. Snapshot listing comes from `.the-door/snapshots/*.json`; structure availability is derivable per snapshot via existence check.
4. THE `SnapshotStore.get_structure(version_id) -> StructureJSON | None` method SHALL return the parsed structure if `structures/<vid>.json.gz` exists, else None.
5. THE `SnapshotStore.list_analyzed_versions() -> list[SnapshotEntry]` (where `SnapshotEntry` is the F1 type) SHALL return one entry per snapshot, ordered by timestamp descending, each entry's `has_persisted_structure` reflecting actual file existence.
6. WHEN a per-version structure file is corrupted (truncated gzip, invalid JSON), `get_structure` SHALL log a warning, emit a `StateWarning(code="structure_corrupted", ...)` reachable via the inspector, and return None. NOT raise.
7. Gzip compression SHALL use Python stdlib `gzip` only — no new third-party dependencies.

> **[Task-refine]** AC7's specific stdlib choice (`gzip`) and AC1's specific directory name (`structures/`) are working sketches. Architectural commitments are: (a) per-version structure persistence MUST NOT introduce new third-party dependencies, (b) the storage location MUST be derivable from `version_id` without an index file.

### Requirement P3: AST Extractor node_id Uniqueness

**User Story:** As any code that indexes nodes by `node_id` (incremental diff in O1, source-node-to-feature mapping in F1's L2 link, viewer L3 drill), I want every node_id from a single extraction to be unique, so that dict lookups don't silently collapse multiple distinct nodes.

#### Acceptance Criteria

1. WHEN `ASTExtractor.extract` would emit two or more nodes sharing the tentative `<file>::<name>` id, THE post-processing step SHALL deterministically suffix the 2nd, 3rd, … occurrences (sorted by `(file_path, line_number)` ascending) with `#2`, `#3`, …
2. THE deterministic ordering SHALL be stable: running extract twice on byte-identical source SHALL produce byte-identical node_id lists.
3. THE bare `<file>::<name>` form SHALL be kept by the first (lowest line number) occurrence. The suffix is only applied to collisions.
4. WHEN any collision occurs during extraction, THE extractor SHALL emit a `StateWarning(code="node_id_collision", location=<file>, message="<count> nodes share name <name>; suffix-disambiguated")` retrievable via the inspector.
5. **Known limitation (documented, not enforced):** when an existing snapshot's `source_nodes` references a bare `<file>::<name>` id AND the current extraction now produces a collision for that name, the bare id in the new extraction refers to the **first by line number**. If that first node differs from the snapshot's original referent (e.g., a new class was inserted above), the O1 incremental flow's signature comparison will reflect this naturally — `modified` if the new occupant has a different signature, `unchanged` if coincidentally identical. There is **no explicit `unmapped_nodes` redirection** for this case; the signature-comparison outcome is the user-visible signal. Fixing this fully requires schema-level requalification (`<file>::<qualified_path>::<name>`), deferred per Non-Requirements.

> **[Task-refine]** AC1's specific suffix format (`#2`, `#3`, ...) is a working sketch. Architectural commitments are: (a) every node_id within one extraction must be unique, (b) ordering must be deterministic, (c) collisions emit observable warnings. The exact suffix syntax (`#N` vs `.N` vs `__N`) is task-time choice.

---

## Operations Tier

### Requirement O1: Incremental Analysis

**User Story:** As a user with a previously analyzed baseline snapshot, I want to analyze a new version of the same codebase by inheriting unchanged features and only re-inferring those touched by the AST diff, so that I don't pay for a full LLM re-analysis and the older source code does not need to remain on disk.

#### Acceptance Criteria

1. WHEN any caller (CLI / MCP / future API) invokes incremental analysis with `(codebase_path, baseline_ref)`, THE system SHALL: (a) resolve baseline via O2, (b) load baseline's persisted structure via P2, (c) extract current AST, (d) compute affected features via the pure function in design §O1, (e) return an `IncrementalDiff` structure.
2. WHEN the baseline's persisted structure is absent (P2 file missing — possible for snapshots predating P2 OR for snapshots whose `analyze` was interrupted), THE system SHALL fail with `Remediation(code="no_persisted_structure_for_baseline", message=..., next_action=...)`. The next_action selection depends on whether the user still has the baseline source:
   - **Has-source case** (the typical "I haven't deleted v1.0.0 yet" path): suggest `the-door extract --as-version <baseline_label> <baseline_source_path>` — this backfills `structures/<vid>.json.gz` without requiring an API key. After backfill, retry the incremental call.
   - **No-source case** (baseline source no longer on disk): suggest `the-door analyze <current_path>` (full fresh analysis, becomes the new baseline). Acknowledge the historical baseline cannot be retrofitted.
   - The remediation message SHALL state both options so the user/agent can pick.
3. A new CLI flag `the-door extract --as-version <baseline-ref> <source-path>` SHALL be added. It:
   - Resolves `<baseline-ref>` via `SnapshotStore.resolve_baseline` to find the target `version_id`.
   - Runs ordinary AST extraction on `<source-path>`.
   - Writes BOTH the latest-pointer `.the-door/structure.json` AND `.the-door/structures/<vid>.json.gz`.
   - Does NOT require an API key (no LLM involvement).
   - Fails with `Remediation(code="baseline_not_found", ...)` if the ref cannot resolve.
   - **Flag interaction with existing extract flags**:
     - `--as-version` is **mutually exclusive with `--to-stdout`** — stdout dump and gz file write have incompatible output semantics. Supplying both SHALL exit with `Remediation(code="conflicting_flags", message="--as-version cannot be combined with --to-stdout", next_action=None)`.
     - `--as-version` combined with `--output-file <path>` is allowed: `--output-file` overrides the latest-pointer destination (existing behavior), AND the gzipped per-version file is always written to `.the-door/structures/<vid>.json.gz` regardless of `--output-file`. The two outputs are independent.
     - `--as-version` requires `<source-path>` to resolve to the same project root as the baseline snapshot's `<codebase_path>`; otherwise the resolved `version_id`'s `.the-door/structures/<vid>.json.gz` would land in a directory unrelated to the baseline. Mismatch SHALL be detected by comparing the project root that contains the baseline snapshot vs. the `source-path` argument; on mismatch, exit with `Remediation(code="baseline_project_mismatch", ...)`.
4. WHEN the AST diff is empty (no added / removed / modified nodes), THE returned `IncrementalDiff.affected_features` SHALL be empty AND `inherited_features` SHALL be byte-identical to the baseline's `FeatureSummary`s. Calling `snapshot_write` with this result writes a snapshot whose `l1_snapshot` differs from the baseline only in metadata (timestamp, version_id).
5. WHEN the AST diff intersects a feature's `source_nodes`, that feature SHALL appear in `affected_features` with: `feature_id`, current `label`, current `description`, current `trigger_description`, and `delta: NodeDelta(added, removed, modified)` — exactly the nodes from the AST diff that belong to this feature.
6. WHEN an AST diff node belongs to no baseline feature's `source_nodes`, it SHALL appear in `unmapped_nodes` (an aggregate `NodeDelta`). NO node is silently dropped.
7. WHEN an agent or LLM supplies updated `label`/`description` for affected features, the wrapping snapshot write SHALL produce a new snapshot whose `l1_snapshot` contains inherited features verbatim + updated features replaced. `feature_relations_snapshot` SHALL be inherited verbatim from the baseline unless explicitly overridden.
8. THE existing `snapshot_write` MCP tool SHALL accept optional `inherit_from: <baseline-ref>` + `updated_features: list[FeatureDict]` (subset). When both present: baseline is loaded, then features whose `feature_id` matches an entry in `updated_features` are replaced; the rest are inherited. When absent: existing behavior unchanged (NO regression).
9. THE existing `the-door update` CLI SHALL accept `--from-snapshot <ref>` as an alternative to the `<old_path>` positional. The two forms are mutually exclusive. When `--from-snapshot` is supplied, the pipeline skips old-path extraction and instead loads baseline structure via P2.
10. A new read-only MCP tool `analyze_changes(codebase_path, baseline)` SHALL be added, returning a JSON object with exactly these top-level keys: `baseline_version_id`, `inherited_features` (list), `affected_features` (list), `unmapped_nodes` (object), and `next_actions` (list, populated per S2). No other top-level keys.
11. THE incremental flow result returned by every entry point SHALL include `next_actions` produced by the F2 suggester. Example actions: `id="snapshot_write.with_inherit_from"` recommending the snapshot write call to commit the result.
12. NO new top-level CLI command SHALL be introduced beyond the `--from-snapshot` flag (a flag, not a new command) and `extract --as-version` (also a flag on the existing `extract` command).

> **[Task-refine]** Several clauses are task-time refinable starting points; their architectural commitments are listed below.
> - AC2's specific suggested CLI commands (`the-door extract --as-version ...`, `the-door analyze ...`) are sketches. **Architectural commitment**: when persisted structure is missing, the remediation MUST distinguish the has-source path (no API key needed) from the no-source fallback (full re-analysis).
> - AC3's `--as-version` flag interaction matrix (mutex with `--to-stdout`, combination with `--output-file`, project-mismatch detection) is a sketch. **Architectural commitment**: a no-API-key backfill mechanism MUST exist; whether it lives on `extract` as a flag or as a separate sub-command is task-time choice. Realistic backfill where source-directory and snapshot-project-directory differ MUST be supported.
> - AC8's exact field names (`inherit_from`, `updated_features`) are sketches. **Architectural commitment**: `snapshot_write` MUST accept enough optional input to express "use this baseline + override these features".
> - AC9's exact flag name (`--from-snapshot`) is a sketch. **Architectural commitment**: the CLI MUST have an entry point that takes a snapshot reference (not an old source path) and the current source path.
> - AC10's exact MCP tool name (`analyze_changes`) and the 4 top-level response keys are sketches. **Architectural commitment**: an MCP read-only tool MUST exist that, given baseline ref + current source, returns the affected/inherited/unmapped decomposition needed for agent-as-LLM workflows.

### Requirement O2: Snapshot Reference Resolution

**User Story:** As a CLI user, viewer user, or MCP caller, I want to reference snapshots by their human-readable form (label, git tag, commit SHA, ISO date) anywhere a snapshot reference is accepted, AND I want every response that mentions a snapshot to carry both the `version_id` and the human-readable label, so that I never have to look up a UUID before making the next call.

#### Acceptance Criteria

1. WHEN `/api/diff?baseline=X&current=Y` is called, the handler SHALL try `SnapshotStore.resolve_baseline(X)` first; on `SnapshotNotFoundError` it SHALL fall back to `get_snapshot(X)` (raw `version_id` lookup); on still-None it SHALL return 404 with the F3 standard envelope, the Remediation pointing at `the-door snapshot list`.
2. **Verified:** `resolve_baseline` does not natively support UUID strings (UUIDs fail the SHA regex due to hyphens). The fallback to `get_snapshot` is load-bearing; both paths must be tried. Reference: [snapshot_store.py:105-133](the_door/src/the_door/core/diff/snapshot_store.py:105).
3. ANY API or MCP response that mentions a snapshot in its payload SHALL include at minimum `version_id` AND `label` (`label` may be null). Example: diff response gains `baseline_label` and `current_label` alongside the existing `baseline_id` and `current_id`.
4. WHEN no diff is found (both versions resolve, but `summary.total_changed == 0`), THE diff response SHALL still be 200, and SHALL include a `next_actions` list per S2 (e.g., `id="picker.compare_other_versions"`).
5. THE existing CLI `the-door diff --baseline` reference parsing (already supports label/tag/date/sha via `resolve_baseline`) SHALL not regress.
6. NO new public method SHALL be added to `SnapshotStore` beyond what P2 already mandates. Resolution improvements live in handlers, not in the store.

> **[Task-refine]** AC1's exact fallback chain implementation (`try resolve_baseline → catch SnapshotNotFoundError → fall back to get_snapshot`) and AC3's exact response field names (`baseline_label`, `current_label`) are sketches. Architectural commitments are: (a) every snapshot reference accepted by The Door MUST accept human-readable forms (label / tag / SHA / date) AND UUID, (b) every response that names a snapshot MUST expose both `version_id` and `label`.

---

## Surfaces Tier

### Requirement S1: CLI Surface

**User Story:** As a user invoking The Door from a terminal, I want a `status` command that tells me where I am, every other command to end with a suggested next step, and every error to tell me how to recover, so that I never need to open a second window to figure out what to do.

#### Acceptance Criteria

1. A new CLI command `the-door status [<path>]` SHALL be added. It SHALL:
   - Default `<path>` to `.` if omitted.
   - Call `StateInspector(path).inspect()`.
   - Call `NextActionSuggester.suggest(state, context="cli")`.
   - Render a human-readable summary: snapshot list, structure availability, warnings, then a numbered list of suggested next actions with their full CLI command.
   - Exit code 0 on success, 1 on inspection error (rare — F1 AC5/8 say inspection rarely raises).
2. EVERY existing CLI command (verified count: 18, exhaustive list in [cli/](the_door/src/the_door/cli/): `analyze`, `config`, `diff`, `doubt`, `estimate`, `extract`, `history`, `mcp_serve`, `projects`, `regenerate`, `render`, `scan`, `scope`, `snapshot`, `timeline`, `ui`, `update`, `validate`) SHALL, on successful exit, print a `Next:` block listing up to 3 suggested actions (drawn from the F2 suggester with the post-command state). Output goes to stderr to avoid polluting piped stdout. The block is suppressed when `--json` or other machine-output flag is set (per-command suppression rules enumerated in design §S1). Enforcement: a single meta-test iterates the Click root group and asserts each command emits the `Next:` token on its success path — see design §S1 Enforcement.
3. EVERY CLI error SHALL print the F3 standard envelope's `message` AND the Remediation's `next_action.cli_command` (if present). The `next_action` SHALL be drawn from the F2 suggester with `context="after_error"`.
4. THE post-command `Next:` block and the error remediation SHALL share a single rendering helper (`cli/next_action_renderer.py`) — no duplicated formatting code across commands.
5. THE format of `Next:` blocks SHALL be machine-readable when `THE_DOOR_NEXT_FORMAT=json` env var is set, emitting JSON to stderr instead of human text. Useful for AI agents wrapping the CLI.
6. NO existing command's positional/flag signature SHALL change (only stderr output is added). Existing scripts continue to work.

> **[Task-refine]** AC1's exact human-output format (the example "✓ 2 snapshots / ⚠ 1 warning" block), AC2's enumerated 18-command list, and AC5's exact env var name `THE_DOOR_NEXT_FORMAT` are sketches. Architectural commitments are: (a) `the-door status` MUST be the canonical "what should I do now" entry point, (b) every CLI command (whatever the current count) MUST emit a Next: block on success, (c) every CLI error MUST carry a Remediation, (d) a machine-readable output mode for the Next: block MUST exist for AI agents wrapping the CLI.

### Requirement S2: MCP Surface

**User Story:** As an AI agent calling The Door's MCP tools, I want every tool result to include a `next_actions` array suggesting which tool to call next given the post-operation state, so that the agent doesn't have to maintain its own model of The Door's state machine.

#### Acceptance Criteria

1. EVERY MCP tool (verified count: 20, exhaustive list in [mcp/tools/](the_door/src/the_door/mcp/tools/)) success response SHALL include a top-level `next_actions: list[dict]` field where each dict is the JSON serialization of a `NextAction`. Read-only listing tools (e.g., `snapshot_list`, `project_list`) MAY return an empty list but the field SHALL be present. Enforcement: a single meta-test iterates registered MCP tools and asserts each tool's `handle()` returns a dict containing `next_actions` on the success path — see design §S2 Enforcement.
2. THE `next_actions` SHALL be drawn from `NextActionSuggester.suggest(post_op_state, context="mcp")`.
3. EVERY MCP tool's error response SHALL follow the F3 standard envelope. The `remediation.next_action` SHALL be drawn from the suggester with `context="after_error"`.
4. THE addition of `next_actions` to existing tool responses SHALL be backward-compatible: existing agents that ignore the field continue to work. No existing field is renamed or removed.
5. A new MCP tool `system_status` SHALL be added with no required arguments, returning the F1 `SystemState` (serialized per design §F1) AND the F2 suggestions for `context="mcp"`. This is the MCP equivalent of `the-door status`.
6. NO new tool SHALL be added beyond `system_status` and the `analyze_changes` from O1 AC9. Surface surface area stays minimal.

> **[Task-refine]** AC1's specific 20-tool count and the example list of exempt tools are sketches. Architectural commitments are: (a) every MCP tool (current count whatever it is) MUST include `next_actions` in success responses, (b) every MCP tool error MUST use the F3 envelope, (c) one new MCP tool MUST exist as the MCP equivalent of `the-door status`.

### Requirement S3: Viewer Surface

**User Story:** As a viewer user, I want the viewer to show me a clear "where am I, what can I do" panel on first load, to render any per-feature suggestions in the detail panel, and to have all the per-feature interactions (user notes, diff explanation) that disappeared after the app.js refactor working again.

#### Acceptance Criteria

1. WHEN the viewer loads and the F1 SystemState's `has_snapshots` property evaluates to `false` (defined as `bool(state.snapshots) == False` — see design §F1 for the property definition), THE main canvas area SHALL render an onboarding card produced by consuming `/api/status` (new endpoint exposing F1 + F2 results). The card SHALL list the top 3 next actions with their CLI / MCP equivalents.
2. WHEN the viewer's detail panel renders a feature (any mode: baseline / current / diff), it SHALL include:
   - "使用者備註" section (rendered by `appendUserNotesSection` from `ui-notes.js`, properly imported and called per design §S3).
   - "AI 差異說明" section in diff mode only (rendered by `appendDiffExplanationSection` from `ui-diff-explanation.js`).
   - "建議的下一步" section consuming `next_actions` from the feature's L1/L2 API response, if any.
3. THE `ui-detail.js` no-op stubs at lines 5–6 SHALL be deleted and replaced with the real imports + call sites adjusted to match the real exports' argument order — per the regression analysis in design §S3.
4. WHEN the user opens the mindmap popup, the data passed via `sessionStorage` SHALL come from a pure function `buildMindmapData(state)` that reads BOTH `state.updateModel` (report-based) and `state.versionDiff` (snapshot-comparison) and prefers `state.updateModel.diff_available === true` per the precedence rule in design §S3.
5. THE mindmap popup HTML (`mindmap-popup.html`) SHALL NOT be modified — the fix lives entirely in the parent viewer's data assembly.
6. A new HTTP endpoint `GET /api/status` SHALL return JSON: `{state: <SystemState>, next_actions: [<NextAction>...]}`, computed via F1 + F2 with `context="viewer"`.
7. THE viewer's version-picker SHALL pass the snapshot's human-readable label (preferring git_tags[0] > label > version_id fallback) as the chosen reference. Diff API requests use this. Combined with O2, the chain works end-to-end with labels.
8. Anomaly rendering in mindmap SHALL remain unchanged. Empty anomaly arrays on hand-edited L2 data is correct behavior, NOT a bug.

> **[Task-refine]** AC3's exact `ui-detail.js` import wiring, AC4's exact `buildMindmapData` function name and precedence rule (`updateModel.diff_available === true` then `versionDiff` fallback), and AC7's exact viewer-picker priority (`git_tags[0] > label > version_id`) are sketches. Architectural commitments are: (a) the detail panel MUST render the "使用者備註" and "AI 差異說明" sections that disappeared after refactor, (b) the mindmap MUST consume both diff data sources (report-based AND snapshot-comparison) via a single pure data-shaping function, (c) the viewer MUST send human-readable references to the diff API when available.

### Requirement S4: Documentation Surface

**User Story:** As a new user (human or AI) opening The Door's docs, I want CLAUDE.md to read as a decision tree leading from "I just installed this" to "I'm running the right command for my situation," so that I don't have to mentally cross-reference parallel mode descriptions.

#### Acceptance Criteria

1. CLAUDE.md SHALL be restructured: section ordering becomes "(1) What you have determines what you do next (decision tree), (2) Commands and tools (reference)." The current "Mode A / Mode B" parallel description is replaced.
2. THE decision tree SHALL handle, at minimum, these branches (each leaf naming exactly one command — no parallel "or" ambiguity at the leaf):
   - "Have you ever analyzed this project before?" → `the-door analyze <path>` (with API key) OR `extract_structure` MCP tool followed by `snapshot_write` (without API key).
   - "Do you have ≥1 snapshot AND want to analyze a new version of the same codebase?" → `the-door update --from-snapshot <ref> <new_path>` (with API key) OR `analyze_changes` MCP followed by `snapshot_write` with `inherit_from` (without API key).
   - "Incremental analysis says baseline lacks persisted structure — what do I do?" → IF baseline source still on disk: `the-door extract --as-version <baseline_ref> <baseline_source_path>` to backfill (no API key needed). IF source no longer available: re-run full analysis on the new version, accepting historical baseline cannot be retrofitted.
   - "Do you have an API key configured?" — this branches each of the above into the "with key" or "without key" leaf as appropriate.
3. EVERY decision-tree leaf SHALL link to a section showing the exact command + expected output + `next_actions` the user will see.
4. THE `the-door status` command SHALL be the documented entry point — every "what now?" question in the docs SHALL answer "run `the-door status`" first.
5. The redirection from old MCP / agent flow docs SHALL preserve backward-compat for existing AI agents reading CLAUDE.md: the old terminology (Mode A / Mode B) appears in a glossary section at the bottom, cross-linked to the new structure.
6. CLAUDE.md SHALL link to the spec's design.md for implementation-level questions, but SHALL NOT itself describe internal data structures (SystemState fields, etc.) — that's spec-internal.

> **[Task-refine]** AC2's exact decision-tree branch wording and example commands are sketches. Architectural commitments are: (a) CLAUDE.md MUST become decision-tree-shaped (no parallel Mode A/B descriptions at the top), (b) `the-door status` MUST be the documented entry point, (c) every leaf MUST name exactly one command — no parallel "or" ambiguity at the bottom of the tree.

---

## Non-Requirements (Explicitly Out of Scope)

The following came up during investigation but are explicitly NOT in this spec. Each carries the reason for exclusion.

| Item | Reason |
|---|---|
| Restoring v1.0.0 to English labels in the test target | User explicitly declined 2026-05-16. |
| Renaming node_id schema globally to `<file>::<qualified_path>::<name>` | P3 suffix-disambiguation is the minimal fix. Full requalification is a separate epic; surface area too large. |
| Deleting `source_node_count` field outright | P1 makes it derived-only. Deletion is a future cleanup commit. |
| Building `the-door snapshot reconcile-source-nodes` migration CLI | P1 AC6 makes drift observable. Repair path is `the-door analyze`, not a special tool. |
| Touching L2 generation flow, mermaid rendering, non-diff API handlers | Out of theme; spec is focused on coherence + incremental analysis. |
| Populating anomaly entries on hand-edited L2 outputs | Anomalies are emitted only by LLM-driven analysis. Empty arrays are correct. |
| LLM-driven `NextActionSuggester` | F2 AC4 explicitly forbids LLM in suggester. Deterministic only. |
| Multi-project state management, cloud sync, user accounts | Out of scope. The Door is single-project, local-filesystem. |
| Redesigning the report-vs-snapshot-comparison diff duality | S3 AC4's `buildMindmapData` consumes both; the duality stays. |
| Replacing the existing CLI argument parser (Click) or HTTP server stack | Surface changes are additive (new flags, new endpoints, new commands). No framework swap. |
| Breaking on-disk snapshot JSON format | P1 AC4 explicitly preserves `source_node_count` field; P2 is additive (new directory); P3 only changes node_id when collisions exist. Old snapshots remain readable. |
| Performance work beyond F1 AC3's 50ms inspection target | Hot-path optimization is not in scope. |
| Web-style auth / CORS / multi-user viewer | The viewer is single-user localhost. |

## Requirement-to-痛點 Cross Reference

For traceability between this spec and the pre-spec investigation:

| 痛點 | Now covered by |
|---|---|
| 1 (no incremental flow) | O1 |
| 2 (no per-version structure) | P2 |
| 3 (source_node_count drift) | P1 |
| 4 (diff API rejects labels) | O2 |
| 5 (CLAUDE.md doc gap) | S4 |
| 6 (node_id duplicates) | P3 |
| 7 (detail panel notes regression) | S3 AC3 |
| 8 (mindmap diff source) | S3 AC4 |
| 9 (no canonical state model) | F1 |
| 10 (no next-action surface) | F2 + S1/S2/S3 consumption |
| 11 (errors without remediation) | F3 |
