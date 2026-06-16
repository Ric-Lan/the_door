# Design — Coherence Layer & Incremental Analysis

## Reading Order

This document is structured to match the dependency chain in requirements.md: Foundation → Primitives → Operations → Surfaces. Read top to bottom. Each section completes before the next begins, and downstream sections reference upstream interfaces verbatim — they do not redefine them.

```
Foundation     F1 SystemState        F2 NextAction          F3 Remediation
                  │                        │                      │
                  └───────────┬────────────┴──────────┬───────────┘
                              ▼                       ▼
Primitives     P1 source_nodes invariant   P2 per-version structure   P3 node_id uniqueness
                              │                       │
                              └──────────┬────────────┘
                                         ▼
Operations              O1 incremental analysis            O2 reference resolution
                                         ▼
Surfaces       S1 CLI       S2 MCP       S3 Viewer        S4 Docs
```

**Derivation direction is one-way.** A Surface SHALL NOT cause a redesign of Foundation. If a Surface need cannot be expressed via Foundation as designed, the change is escalated as a Foundation revision (with cascading impact analysis) — not patched at the surface.

### Architecture vs Task-Refinement Layers in This Document

Sections below mix two layers (same convention as requirements.md):

- **Architectural commitments**: module boundaries, dependency direction, type/contract definitions (dataclass field sets, function signatures, on-disk file layout), and the rule tables that ARE the architecture (e.g., F2 suggester rule list). These are binding.
- **Task-time refinement detail**: per-step performance budgets, specific file:line edit instructions, algorithm pseudocode, exact enforcement mechanisms (meta-test implementations), test plan tables. These are retained as starting points for task writers; tasks confirm or refine without spec revision.

Each major section's task-refinable detail is called out via a `> [Task-refine]` block at the end of that section. Everything else in the section is architecturally binding.

What this means in practice:
- Reading at architecture phase: skip the `> [Task-refine]` blocks; the remaining content is what implementers MUST honor.
- At task phase: the detail is the starting draft, not a verification target — tasks edit freely as long as architectural commitments hold.

---

## §F1 — SystemState Model

### Type definitions

All types live in a new file `the_door/src/the_door/core/guidance/state.py`. No new dependencies.

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

ApiProvider = Literal["anthropic", "openai", "ollama"]


@dataclass(frozen=True)
class SnapshotEntry:
    """One entry in SystemState.snapshots. Derived from a snapshot JSON's
    top-level fields plus structure-file existence."""
    version_id: str
    label: str | None
    git_tags: tuple[str, ...]
    commit_hash: str | None
    timestamp: str            # ISO-8601 UTC
    has_persisted_structure: bool  # structures/<vid>.json.gz exists


@dataclass(frozen=True)
class StateWarning:
    """A data-integrity or consistency issue surfaced during inspection.
    Non-fatal — inspection always completes."""
    code: str                 # e.g., "source_nodes_drift", "node_id_collision",
                              # "structure_corrupted", "snapshot_corrupted"
    location: str             # human-readable path, e.g., "snapshot/<vid>/feat-x"
    message: str              # human-readable detail
    remediation_code: str | None  # F3 Remediation.code if a fix exists


@dataclass(frozen=True)
class SystemState:
    project_path: Path
    has_dot_the_door: bool

    # Extraction artifacts (boolean only — counts are lazy, read on display)
    has_structure_json: bool             # .the-door/structure.json exists (cheap is_file())

    # Snapshots
    snapshots: tuple[SnapshotEntry, ...]  # sorted by timestamp DESC

    # L2
    l2_features_analyzed: frozenset[str]  # feature_ids with L2 output files

    # Runtime config
    has_api_key: bool
    api_provider: ApiProvider | None

    # Inspection-time findings
    warnings: tuple[StateWarning, ...]

    # Derived properties — convenience accessors, no new state
    @property
    def has_snapshots(self) -> bool:
        return bool(self.snapshots)

    @property
    def latest_snapshot(self) -> SnapshotEntry | None:
        """First entry (snapshots is sorted timestamp DESC)."""
        return self.snapshots[0] if self.snapshots else None
```

### SystemState → JSON serialization

`/api/status` and the CLI's `--json` mode return JSON. To avoid shape drift between consumers, the conversion rule is fixed here:

| Python type | JSON type | Notes |
|---|---|---|
| `Path` | `str` | use `path.as_posix()` for cross-platform stability |
| `tuple[X, ...]` | array | order preserved |
| `frozenset[str]` | array | sorted ascending — determinism |
| `Literal[...]` | string | the literal value |
| nested `@dataclass(frozen=True)` | object | recurse with same rules |
| `None` | `null` | as-is |
| `bool`, `int`, `str` | same | as-is |

A single helper lives in `core/guidance/state.py`:

```python
def to_json_dict(state: SystemState) -> dict:
    """Serialize SystemState (and contained dataclasses) per the table above.
    Properties (has_snapshots, latest_snapshot) ARE included in the output
    so that JSON consumers don't have to recompute them."""
```

The output JSON includes both the raw fields and the property-derived fields:
```json
{
  "project_path": "/path/to/project",
  "has_dot_the_door": true,
  "has_snapshots": true,
  "latest_snapshot": { ... },
  "snapshots": [ ... ],
  "warnings": [ ... ],
  ...
}
```

### StateInspector

Single class, single public method.

```python
class StateInspector:
    def __init__(self, project_path: Path) -> None: ...

    def inspect(self) -> SystemState:
        """Run inspection. Always returns a valid SystemState.
        Never raises; on per-file errors, emits StateWarnings and continues.
        Target performance: < 50 ms on 200 files / 10 snapshots."""
```

Implementation outline (one method, ~80 lines):

1. `has_dot_the_door = (project_path / ".the-door").is_dir()`
2. Bail-out fast path: if not, return empty `SystemState` with all defaults.
3. `has_structure_json = (project_path / ".the-door/structure.json").is_file()`. **Do NOT read or parse the file** — the detail counts (`node_count`, `file_count`) are out of scope for SystemState; they are lazy-loaded by S1's status command when rendering its detail line.
4. Iterate `.the-door/snapshots/*.json`. For each, **read and `json.loads` the full file** (snapshots are typically 20–80 KB, well within budget) but **do NOT construct `FeatureSummary` objects** — work on the parsed dict directly. Per file:
   - Extract top-level metadata (`version_id`, `label`, `git_tags`, `commit_hash`, `timestamp`).
   - **Drift inspection**: iterate `parsed["l1_snapshot"].items()`. For each `(feature_id, entry)`, if `entry.get("source_node_count", 0) > 0` AND `not entry.get("source_nodes")` (missing key or empty list), emit `StateWarning(code="source_nodes_drift", location=f"snapshot/{version_id}/{feature_id}", message=..., remediation_code="source_nodes_drift")`.
   - Check `.the-door/structures/<vid>.json.gz` existence (`os.path.exists`) for `has_persisted_structure`.
   - On parse error: emit `StateWarning(code="snapshot_corrupted", ...)` and skip.
   - This step replaces the previously-planned ContextVar mechanism for drift detection from the inspector path — see §P1 below for the now-secondary role of ContextVar.
5. Scan `.the-door/l2-outputs/*.json` (filename = `<feature_id>.json`) into `l2_features_analyzed` — use `os.listdir` + filename parsing only, no JSON read.
6. Detect API key:
   - `os.environ.get("ANTHROPIC_API_KEY")` truthy → `("anthropic", True)`.
   - Else `os.environ.get("OPENAI_API_KEY")` truthy → `("openai", True)`.
   - Else read `~/.the-door/config.toml`; if `default_provider` + matching API key present → that provider + True.
   - Else `(None, False)`.
7. Aggregate warnings collected in steps 3–4 (P1 drift warning also flows through here via the ContextVar mechanism; P3 collision warnings live elsewhere — see §P3 for how they reach the inspector via an opt-in channel).
8. Return frozen `SystemState`.

### Performance budget (F1 AC3 = 50 ms total)

Per-step targets, profiled on a 200-file / 10-snapshot / 1500-node project. **Stdlib only** — no `ijson` or other parsing dependencies.

| Step | Target | Reason / required technique |
|---|---|---|
| 1 — `.the-door/` `is_dir()` | < 1 ms | one syscall |
| 2 — bail-out | < 1 ms | early return on missing dir |
| 3 — structure.json existence | < 1 ms | `is_file()` only; **no parsing**. Detail counts (nodes / files) are out of scope for inspect; status command (S1) reads them lazily when rendering |
| 4 — 10 snapshots (read + drift scan) | < 30 ms | `json.loads` each ~50 KB snapshot + dict-level drift check (no FeatureSummary construction). Per snapshot < 3 ms |
| 5 — `l2-outputs` listing | < 3 ms | `os.listdir` + filename split only, no file open |
| 6 — API key detect | < 1 ms | env var lookup + at most one config file read |
| 7 — warning aggregate | < 1 ms | list concat |
| 8 — freeze + return | < 1 ms | dataclass construction |
| **Total budget** | **< 38 ms** | ~12 ms headroom under the 50 ms ceiling |

The acceptance test (F1-T10) measures total elapsed time via `time.perf_counter` and asserts the 50 ms ceiling. If the test fails on real hardware, the most likely culprit is step 4 — confirm via `cProfile` before optimizing.

> **[Task-refine]** The per-step budget table, the 50 ms ceiling, the 8-step implementation outline, and the drift-detection mechanism choice (F1 step 4 direct JSON walk vs P1 deserializer warning) are starting sketches. **Architectural commitments**: (a) `inspect()` is a pure read of `.the-door/` state, no LLM, no network; (b) inspection cost MUST be low enough to run on every CLI invocation without user-perceptible lag; (c) drift detection MUST be reachable via the inspector path. Tasks may refactor the step decomposition or move drift detection between channels as long as those three properties hold.

### Drift warnings sourced from F1 step 4 (primary) and P1 deserialize (auxiliary)

Drift detection now happens in **two unrelated places**, neither dependent on the other:

1. **F1 inspector (primary)** — step 4 reads each snapshot JSON dict and inspects every `l1_snapshot` entry for the drift condition directly. This is the channel that populates `SystemState.warnings`. No object construction, no ContextVar.

2. **P1 `_deserialize_snapshot` (auxiliary)** — when callers that bypass the inspector load a snapshot via `SnapshotStore.get_snapshot()`, the deserializer issues a stdlib `warnings.warn` for drift conditions. This is independent of the inspector and serves to surface drift to log-watching humans + ad-hoc test runs.

Both channels emit the same message format and reference the same Remediation code (`source_nodes_drift`), so downstream tooling that listens to either one observes consistent behavior.

ContextVar is **NOT used**. The previous design's contextvar handoff is removed — direct JSON-dict inspection in step 4 is cheaper and avoids the magic-bridge anti-pattern.

### Test plan (§F1)

| RED | Behavior |
|---|---|
| F1-T1 | `StateInspector(<tmp_dir>).inspect()` on a directory with no `.the-door/` returns `SystemState(has_dot_the_door=False, snapshots=(), warnings=(), ...)` — no exception. |
| F1-T2 | With one valid snapshot + matching structure.gz → `has_persisted_structure=True` for that entry. |
| F1-T3 | With one valid snapshot + missing structure.gz → `has_persisted_structure=False`, no warning (gap, not corruption). |
| F1-T4 | With a corrupted snapshot JSON → warning emitted with `code="snapshot_corrupted"`, inspection completes, other snapshots still listed. |
| F1-T5 | With a corrupted gzipped structure → warning emitted with `code="structure_corrupted"`. |
| F1-T6 | Snapshot containing `source_node_count: 5, source_nodes: []` (drift) → after inspection, `state.warnings` contains `code="source_nodes_drift"` entry pointing at that feature. |
| F1-T7 | Env var `ANTHROPIC_API_KEY=test` → `has_api_key=True, api_provider="anthropic"`. |
| F1-T8 | No env vars, no config → `has_api_key=False, api_provider=None`. |
| F1-T9 | Deterministic: snapshot ordering is timestamp DESC; running `inspect()` twice on stable filesystem returns equal-by-value SystemStates. |
| F1-T10 | Performance: `inspect()` on a fixture with 10 snapshots + 1500-node structure.json completes in < 50ms (measured with `time.perf_counter`). |

---

## §F2 — NextAction Model + Suggester

### Type definitions

`the_door/src/the_door/core/guidance/actions.py`:

```python
from dataclasses import dataclass
from typing import Literal

ActionContext = Literal["cli", "mcp", "viewer", "after_error"]


@dataclass(frozen=True)
class NextAction:
    id: str                              # globally unique, snake_case_dotted
                                         # e.g., "analyze.fresh", "analyze.incremental",
                                         # "snapshot_write.with_inherit_from",
                                         # "viewer.open"
    title: str                           # 1-line human-readable
    rationale: str                       # 1-2 sentence "why this is suggested"
    priority: int                        # 1 (top) to 99 (low)

    # Exactly one of these is set (validated in __post_init__)
    cli_command: str | None = None       # exact command line
    mcp_tool: str | None = None          # MCP tool name
    mcp_arguments: dict | None = None    # required if mcp_tool set
    viewer_route: str | None = None      # path like "/?baseline=v1.0.0&current=v1.0.5"
```

Validation in `__post_init__`: exactly one of `(cli_command, mcp_tool, viewer_route)` is non-None; if `mcp_tool` set, `mcp_arguments` is a dict (may be empty).

### NextActionSuggester

`the_door/src/the_door/core/guidance/suggester.py`:

```python
class NextActionSuggester:
    def suggest(
        self,
        state: SystemState,
        context: ActionContext,
        failure_code: str | None = None,
    ) -> list[NextAction]:
        """Pure deterministic function. Same (state, context, failure_code)
        always returns the same list in the same order.

        `failure_code` is used ONLY when context == "after_error"; ignored
        otherwise. Other contexts SHOULD pass None.
        """
```

### Rule table

The complete decision logic lives in this table. It is implemented as a sequence of small predicates each emitting zero or one NextAction; the result is collected, deduped by `id` (first wins), sorted by `priority`.

| # | Predicate | Action ID | Title | Priority | Surfaces | Action form |
|---|---|---|---|---|---|---|
| R1 | `not state.has_dot_the_door` | `analyze.first_time` | 首次分析這個專案 | 1 | cli, mcp | cli: `the-door analyze <path>` |
| R2 | `not state.has_dot_the_door and not state.has_api_key` | `analyze.first_time.mode_b` | 首次分析（無 API key，agent 模式） | 1 | mcp | mcp: `extract_structure {codebase_path}` |
| R3 | `state.has_structure_json and not state.snapshots` | `snapshot.write_first` | 寫入首個 snapshot | 2 | mcp | mcp: `snapshot_write {...}` |
| R4 | `len(state.snapshots) == 1 and state.has_api_key` | `analyze.incremental` | 分析新版本（繼承既有 baseline） | 2 | cli, mcp | cli: `the-door update --from-snapshot <label>` |
| R5 | `len(state.snapshots) == 1 and not state.has_api_key` | `analyze_changes.fetch_diff` | 計算 AST 差異供 agent 推論 | 2 | mcp | mcp: `analyze_changes {codebase_path, baseline}` |
| R6 | `len(state.snapshots) >= 2` | `viewer.open` | 在 viewer 比對兩個版本 | 3 | cli, viewer | cli: `the-door ui <path>` |
| R7 | `len(state.snapshots) >= 2` | `diff.cli` | 在 CLI 看版本差異 | 4 | cli | cli: `the-door diff --baseline <prev> <path>` |
| R8 | `state.snapshots and not all(s.has_persisted_structure for s in state.snapshots)` | `extract.backfill_structure` | 用 `extract --as-version` 補既有 snapshot 的 persisted structure（無需 API key） | 5 | cli | cli: `the-door extract --as-version <baseline_ref> <baseline_source_path>` |
| R9 | `state.warnings and any(w.code == "source_nodes_drift" for w in state.warnings)` | `analyze.repair_drift` | 重跑 analyze 修復 source_nodes 漂移 | 6 | cli | cli: `the-door analyze <path>` |
| R10 | (any other state) — fallback | `onboarding.read_claude_md` | 閱讀使用指南 | 99 | all | cli: `the-door --help` |
| R11 | (always emit — diagnostic shortcut) | `system_status.show` | 查看目前專案狀態與建議 | 90 | cli, mcp, viewer | cli: `the-door status`; mcp tool: `system_status {}` |

R11 is **always emitted** by the suggester regardless of state. It serves as the universal "I'm lost, what now?" pointer. After-error sub-table maps `snapshot_not_found` and `baseline_not_found` to this action by priority-boosting it (effective priority 1 in those failure contexts) — see the after-error sub-table below.

**Context filtering**: each rule's "Surfaces" column lists which contexts get the action. E.g., R5 only appears for `context="mcp"`; R6 appears for `context in ("cli", "viewer")`. Implementation: each rule predicate also checks `if context in rule.surfaces`.

**After-error context**: when `context="after_error"`, the suggester also receives a `failure_code` (the F3 Remediation code). A separate mini-table maps `failure_code → preferred action_id`:

| Failure code | Preferred action_id |
|---|---|
| `no_persisted_structure_for_baseline` | `extract.backfill_structure` (the "has-source" path; the remediation message also documents the "no-source" fallback as a second suggestion) |
| `baseline_not_found` | `system_status.show` |
| `no_snapshot_for_baseline` | `snapshot.write_first` if no snapshots, else `viewer.open` |
| `snapshot_not_found` | `system_status.show` (the F2 fallback action that lists available snapshots) |
| (unknown) | `onboarding.read_claude_md` |

### Test plan (§F2)

| RED | Behavior |
|---|---|
| F2-T1 | `NextAction(cli_command="x", mcp_tool="y")` raises ValueError ("exactly one") |
| F2-T2 | `NextAction(mcp_tool="x")` without `mcp_arguments` raises ValueError |
| F2-T3 | Suggester on empty state, context="cli" → first action is `analyze.first_time` |
| F2-T4 | Suggester on state with 1 snapshot + api_key, context="cli" → top action is `analyze.incremental` (priority 2) |
| F2-T5 | Suggester on state with 2 snapshots, context="viewer" → top action is `viewer.open` |
| F2-T6 | Suggester on state with `source_nodes_drift` warning → suggests `analyze.repair_drift` (priority 6, may not be top) |
| F2-T7 | Determinism: suggesting twice on equal-by-value state returns equal lists in equal order |
| F2-T8 | Context filtering: state with 1 snapshot + no api key, context="cli" → does NOT include `analyze_changes.fetch_diff` (mcp-only) |
| F2-T9 | After-error context with `failure_code="no_persisted_structure_for_baseline"` → top action is `analyze.refresh_for_increment` |
| F2-T10 | Fallback: state where no rule fires (synthetic edge case) → returns `[NextAction(id="onboarding.read_claude_md", ...)]` |

> **[Task-refine]** The rule table's exact predicate strings, specific action IDs (`analyze.first_time`, `extract.backfill_structure`, ...), specific priority numbers (1–99), the after-error sub-table mapping, and R11's per-context action-form rendering rule are all starting sketches. **Architectural commitments**: (a) the suggester is a pure deterministic function of (state, context, failure_code); (b) every reachable state yields ≥1 suggestion; (c) the rule set MUST be table-driven and externally enumerable for review; (d) action forms are mutually exclusive per the NextAction `__post_init__` validation. Tasks may rename action IDs, re-prioritize, or split/merge rules as long as those properties hold.

---

## §F3 — Remediation Model + Standard Error Envelope

### Type

`the_door/src/the_door/core/guidance/remediation.py`:

```python
@dataclass(frozen=True)
class Remediation:
    code: str                             # e.g., "no_persisted_structure_for_baseline"
    message: str                          # human-readable
    next_action: NextAction | None = None
    docs_url: str | None = None
```

### Standard envelope

The Door's standardized error response shape, returned by:
- HTTP API error handlers
- MCP tool error returns (`{"error": ...}` payload)
- CLI error output (rendered as text, but conceptually same fields)

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
    "source": "<file:fn or handler_name>"
  }
}
```

### Code catalogue

All remediation codes used by this spec's changes. New code paths added by tasks SHALL register here.

| Code | Where raised | Action when triggered |
|---|---|---|
| `no_persisted_structure_for_baseline` | O1 entry when P2 file missing | next_action: `extract.backfill_structure` (has-source path). Remediation message also surfaces the no-source fallback (`analyze.fresh_full`) for users without baseline source |
| `baseline_not_found` | `the-door extract --as-version` when ref does not resolve | next_action: `system_status.show` to list available baselines |
| `snapshot_not_found` | O2 resolve fallback both failing | next_action: `system_status.show` listing available labels |
| `no_snapshot_for_baseline` | O1 entry when baseline ref resolves to nothing | next_action: `snapshot.write_first` |
| `source_nodes_drift` | P1 deserialize, when count > 0 but list empty | next_action: `analyze.repair_drift`; emitted as StateWarning AND remediation |
| `node_id_collision` | P3 extract step | emitted as StateWarning only (not error) |
| `structure_corrupted` | F1 inspection on gzip read failure | next_action: `analyze.repair` |
| `snapshot_corrupted` | F1 inspection on snapshot JSON parse | next_action: `snapshot.repair_or_delete` |
| `conflicting_flags` | CLI flag mutual exclusion violations (e.g., `extract --as-version --to-stdout`) | next_action: `null` — message itself is sufficient |
| `baseline_project_mismatch` | `extract --as-version` when source-path differs from baseline's project root | next_action: `system_status.show` to inspect both projects' snapshot lists |

The codes that emit ONLY as StateWarning (not as Remediation) are documented in F1's warning enum; codes that emit as Remediation accompany an exception or error response.

### Existing error code migration

Existing handlers (e.g., `handle_diff_versions` returning `"snapshot_not_found"`) SHALL gain a `remediation` field. Existing top-level fields (`code`, `message`, `source`) are unchanged → backward-compatible.

In-scope error sites to update (enumerated, exhaustive list):

| File:line | Existing code | Remediation added |
|---|---|---|
| [api_handlers.py:351-355](the_door/src/the_door/core/ui/api_handlers.py:351) | `snapshot_not_found` (baseline) | yes |
| [api_handlers.py:357-361](the_door/src/the_door/core/ui/api_handlers.py:357) | `snapshot_not_found` (current) | yes |
| [api_handlers.py:307-310](the_door/src/the_door/core/ui/api_handlers.py:307) | `no_l1_data` | yes (action: `analyze.first_time`) |
| [api_handlers.py:380-385](the_door/src/the_door/core/ui/api_handlers.py:380) | `diff_error` | yes (generic remediation: `system_status.show`) |

Other error sites in the codebase MAY be left untouched if they are out of this spec's theme; they appear in a "known gaps" list in tasks but are not blockers.

### Enforcement (avoid silent code-without-Remediation gaps)

Meta-test `the_door/tests/unit/core/guidance/test_remediation_catalogue_coverage.py` enforces F3 AC3 for the **enumerated in-scope error sites** (this design's table at §F3 "Existing error code migration" — 4 entries currently). The test:

1. Calls each enumerated handler with inputs that trigger the documented failure path.
2. Asserts the returned error envelope contains the F3-standard `remediation` block with non-null `code` and `message`.
3. Failure mode: a handler that returns the legacy shape (no `remediation` key) fails by handler name.

Out-of-scope error sites elsewhere in the codebase are left untouched in this spec — a separate audit can extend the meta-test's coverage in a future spec.

### Test plan (§F3)

| RED | Behavior |
|---|---|
| F3-T1 | `Remediation(code="x", message="y")` with both `next_action=None` and `docs_url=None` is valid (the case for unknown-recovery errors) |
| F3-T2 | Envelope shape: `_make_error(code, message, remediation, source)` returns exactly the JSON shape in design §F3 |
| F3-T3 | Existing API handler at line 351 returns the envelope with `remediation.code == "snapshot_not_found"` and `next_action.id == "system_status.show"` |
| F3-T4 | Existing CLI error path renders `next_action.cli_command` to stderr (verified via CliRunner capture) |
| F3-T5 | Backward-compat: a consumer reading only the legacy `code`, `message`, `source` fields continues to work — those fields are unchanged |

> **[Task-refine]** The code catalogue's exact entries (specific codes like `no_persisted_structure_for_baseline`, `baseline_not_found`, `conflicting_flags`, etc.) and the existing-error-site migration table (4 specific file:line entries) are starting sketches. **Architectural commitments**: (a) every user-visible error MUST flow through the standard envelope, (b) every code is globally unique within The Door, (c) backward compat with existing API consumers via additive `remediation` field is preserved. Tasks may rename codes, add new ones, or extend the migration list when the grep reveals more sites.

---

## §P1 — Snapshot Store Source-Nodes Invariant

### Changes

| File | Change |
|---|---|
| [snapshot_store.py:170](the_door/src/the_door/core/diff/snapshot_store.py:170) | Serialization: write `"source_node_count": len(fs.source_nodes)` regardless of `fs.source_node_count`. The field becomes derived-on-write. |
| [snapshot_store.py:237](the_door/src/the_door/core/diff/snapshot_store.py:237) | Deserialization: when `fdata["source_node_count"] > 0 and not fdata.get("source_nodes")`, log `warnings.warn` with message including snapshot file + feature_id, then construct `FeatureSummary(source_node_count=0, source_nodes=())`. The inspector (F1) does NOT rely on this path — F1 step 4 detects drift directly at JSON-dict level (cheaper, no FeatureSummary construction). This deserializer-side warning is the auxiliary channel for callers that read snapshots via `get_snapshot()` outside the inspector. |
| [snapshot_write_tool.py:33](the_door/src/the_door/mcp/tools/snapshot_write_tool.py:33) | Drop `"source_node_count"` from `required` list. |
| [snapshot_write_tool.py:109](the_door/src/the_door/mcp/tools/snapshot_write_tool.py:109) | Always compute `source_node_count=len(source_nodes)`; ignore caller value. |
| [timeline_renderer.py:267](the_door/src/the_door/core/timeline/timeline_renderer.py:267) | `len(feature.source_nodes)` instead of `feature.source_node_count`. |

Untouched: `models.py:340` field definition, the JSON schema, integration scripts, docs.

### Rejected alternatives

- **Delete `source_node_count` field entirely**: ~16 files of churn + legacy snapshot compat layer; no functional gain over derived-on-write.
- **Strict assert that input matches**: would crash on existing hand-edited drift; "louder bug" is not "fixed bug."
- **Add reconcile CLI to repair drift from L2 outputs**: legacy hand-edited L2 data isn't authoritative either. The right repair is `the-door analyze`. Tool would be over-design.

### Test plan (§P1)

| RED | Behavior |
|---|---|
| P1-T1 | `create_snapshot` with `FeatureSummary(source_node_count=99, source_nodes=("a","b"))` → on-disk JSON has `"source_node_count": 2` |
| P1-T2 | Deserialize a hand-crafted JSON with drift → returns `FeatureSummary(source_node_count=0, source_nodes=())`; `caplog` captures WARNING naming snapshot file + feature_id |
| P1-T3 | Deserialize same drift JSON inside `inspect()` context → F1 `state.warnings` contains corresponding `StateWarning(code="source_nodes_drift", ...)` |
| P1-T4 | `snapshot_write` MCP tool called without `source_node_count` in feature dict → succeeds; resulting snapshot's count == len(source_nodes) |
| P1-T5 | `timeline_renderer` text output for a feature with `source_nodes=("a","b","c")` and (drifted) `source_node_count=99` → contains `"Source Nodes: 3"` |

> **[Task-refine]** The 5-row "Changes" file:line table and the specific `ContextVar` → direct-JSON-walk migration narrative are starting sketches. **Architectural commitments**: (a) `source_node_count` is derived-on-write — never authoritative input; (b) drift detection is observable via at least one channel reachable from the inspector; (c) field is retained for on-disk backward compat (no schema break).

---

## §P2 — Per-Version Structure Persistence

### File layout

```
.the-door/
├── snapshots/
│   └── <vid>.json                  (unchanged)
├── structures/                     (NEW)
│   └── <vid>.json.gz               (NEW: gzipped StructureJSON)
├── structure.json                  (unchanged: latest-pointer)
└── fingerprints/
    └── <vid>.json                  (unchanged)
```

No `manifest.json`. Listing is derived: iterate `snapshots/`, check `structures/<vid>.json.gz` existence (matches F1 inspector semantics).

### Changes

| File | Change |
|---|---|
| `core/extraction/structure_serializer.py` | Add: `def write_versioned_structure(project_path: Path, version_id: str, structure: StructureJSON, scan_result: ScanResult) -> Path`. Uses `gzip.open(path, 'wt', encoding='utf-8')` + `json.dump(...)`. Returns the written path. |
| `core/diff/snapshot_store.py` | Add: `def get_structure(self, version_id: str) -> StructureJSON \| None`. Reads `structures/<vid>.json.gz`, decompresses, parses, returns `StructureJSON`. On `gzip.BadGzipFile` / `json.JSONDecodeError` / file-not-found: log warning, return None. |
| `core/diff/snapshot_store.py` | Add: `def list_analyzed_versions(self) -> list[SnapshotEntry]`. Iterate `snapshots/` per F1 inspector semantics; each entry's `has_persisted_structure` reflects file existence. |
| [analyze_pipeline.py:179-181](the_door/src/the_door/core/pipeline/analyze_pipeline.py:179) | After `snapshot = _create_auto_snapshot(...)` returns and before `return AnalyzeResult(...)`, call `write_versioned_structure(codebase_path, snapshot.version_id, structure, scan_result)` inside `try/except Exception as e: logger.warning(...); progress(...)`. Failure must be non-fatal — matches `_create_auto_snapshot`'s own non-fatal convention. |

### Rejected alternatives

- **Separate `manifest.json`**: duplicates data already in `snapshots/*.json`. DRY violation.
- **Uncompressed `.json` per version**: 1.8 MB × N versions vs ~200 KB gzipped × N. Gzip is stdlib, zero new deps.

### Test plan (§P2)

| RED | Behavior |
|---|---|
| P2-T1 | `write_versioned_structure` + `get_structure` round trip an arbitrary `StructureJSON` byte-for-byte |
| P2-T2 | `get_structure(<unknown_vid>)` returns None |
| P2-T3 | `get_structure(<vid>)` with corrupt gzip → logs warning, returns None, does not raise |
| P2-T4 | `list_analyzed_versions()` on directory with 2 snapshots and 1 structure → 2 entries, `has_persisted_structure` reflects actual existence, order by timestamp DESC |
| P2-T5 | After `run_analyze_pipeline`, `.the-door/structures/<new_vid>.json.gz` exists and decompresses to the same node count as the in-memory extraction |
| P2-T6 | If `write_versioned_structure` raises during pipeline, `AnalyzeResult` still returned successfully and a warning is logged |

> **[Task-refine]** The exact directory name (`structures/`), file extension (`.json.gz`), helper function name (`write_versioned_structure`), and the specific analyze_pipeline.py insertion site are starting sketches. **Architectural commitments**: (a) per-version AST is persisted alongside snapshot; (b) no `manifest.json` (derivation only); (c) corruption is non-fatal at read time; (d) write failure during pipeline is non-fatal.

---

## §P3 — AST Extractor node_id Uniqueness

### Algorithm

Post-processing pass at the end of `ASTExtractor.extract`. Located in [ast_extractor.py](the_door/src/the_door/core/extraction/ast_extractor.py).

```python
def _disambiguate_node_ids(self, nodes: list[Node]) -> list[Node]:
    """Append #2, #3, ... suffixes to collisions. Deterministic.
    First occurrence (by line_number) keeps the bare id."""
    from collections import defaultdict
    groups: dict[str, list[Node]] = defaultdict(list)
    for n in nodes:
        groups[n.node_id].append(n)

    result = []
    for tentative_id, group in groups.items():
        if len(group) == 1:
            result.append(group[0])
            continue
        # Collision — emit warning and disambiguate
        group_sorted = sorted(group, key=lambda n: (n.file, n.line_number))
        self._emit_warning(StateWarning(
            code="node_id_collision",
            location=group_sorted[0].file,
            message=f"{len(group)} nodes share node_id={tentative_id!r}; suffix-disambiguated",
            remediation_code=None,
        ))
        # First keeps bare id
        result.append(group_sorted[0])
        # Rest get #2, #3, …
        for i, n in enumerate(group_sorted[1:], start=2):
            new_id = f"{tentative_id}#{i}"
            result.append(replace(n, node_id=new_id))
    # Stable ordering: sort by (file, line_number)
    result.sort(key=lambda n: (n.file, n.line_number))
    return result
```

`_emit_warning` appends to a per-extractor warnings list; the caller (analyze pipeline or extract CLI) consumes it. The F1 inspector picks it up via the same mechanism that P1 uses (ContextVar).

### Rejected alternatives

- **Full requalification `<file>::<qualified>::<name>`**: changes every node_id in every existing snapshot's `source_nodes`. Surface area too large. Listed as deferred epic in Non-Requirements.
- **Hash-based disambiguation (e.g., `__init__<hash>`):** non-readable, breaks debug ergonomics. Suffix `#N` is human-readable and trivially diffable.

### Test plan (§P3)

| RED | Behavior |
|---|---|
| P3-T1 | Fixture with two classes both having `__init__` → extract produces node_ids `<file>::__init__` and `<file>::__init__#2`, ordered by line number ascending |
| P3-T2 | Fixture with three same-name items → produces base, `#2`, `#3` |
| P3-T3 | Fixture with no collisions → no `#N` suffixes appear in any node_id (regression: don't introduce suffixes when not needed) |
| P3-T4 | Determinism: extract twice on byte-identical source → byte-identical node_id list |
| P3-T5 | Collision emits a `StateWarning(code="node_id_collision")` reachable via inspector |
| P3-T6 | Property test: any fixture with N items sharing a `<file>::<name>` produces N distinct node_ids |

> **[Task-refine]** The pseudocode (`_disambiguate_node_ids`), exact suffix syntax `#N`, and StateWarning emission mechanism are starting sketches. **Architectural commitments**: (a) every node_id in a single extraction is unique; (b) ordering is deterministic across re-runs; (c) collision emits an observable warning reaching the inspector.

---

## §O1 — Incremental Analysis

### Core pure function

`the_door/src/the_door/core/diff/feature_attribution.py` (NEW):

```python
@dataclass(frozen=True)
class NodeDelta:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    modified: tuple[str, ...]  # signature changed

@dataclass(frozen=True)
class AffectedFeature:
    feature_id: str
    current_label: str
    current_description: str
    current_trigger_description: str | None
    delta: NodeDelta

@dataclass(frozen=True)
class IncrementalDiff:
    baseline_version_id: str
    inherited_features: tuple[FeatureSummary, ...]
    affected_features: tuple[AffectedFeature, ...]
    unmapped_nodes: NodeDelta

def compute_affected_features(
    baseline_structure: StructureJSON,
    current_structure: StructureJSON,
    baseline: VersionSnapshot,
) -> IncrementalDiff:
    """Pure. No I/O, no LLM."""
```

### Algorithm

1. Build `baseline_sig: dict[node_id, signature_hash]` from `baseline_structure.nodes`. Signature = `tuple(name, params_tuple, return_type, decorators_tuple, docstring)` hashed via `hashlib.md5` for stability.
2. Same for `current_sig`.
3. `added = current.keys - baseline.keys`; `removed = baseline.keys - current.keys`; `modified = {k for k in common if baseline_sig[k] != current_sig[k]}`.
4. For each `fs` in `baseline.l1_snapshot.values()`:
   - `owned = set(fs.source_nodes)` (assumed populated; P1 ensures count==len, P2 ensures structure available)
   - `feature_delta = NodeDelta(added & owned, removed & owned, modified & owned)`
   - If any of the three is non-empty: append `AffectedFeature(...)`
   - Else: append `fs` to `inherited_features`
5. `unmapped` = aggregate of `(added | removed | modified) - union(all fs.source_nodes)`.

### Surfaces

| Surface | Form |
|---|---|
| MCP tool: NEW `analyze_changes` | input: `{codebase_path, baseline}`. Output JSON: `{baseline_version_id, inherited_features, affected_features, unmapped_nodes, next_actions}` (S2 always adds next_actions) |
| MCP tool: EXTEND `snapshot_write` | new optional input fields: `inherit_from: str` + `updated_features: list[FeatureDict]`. When both present: load baseline → replace features whose `feature_id` matches → carry the rest verbatim. When absent: existing behavior unchanged. |
| CLI: EXTEND `the-door update` | new flag `--from-snapshot <ref>`. Mutually exclusive with positional `old_path`. When supplied, pipeline skips old-path extraction. |
| pipeline | new file `core/pipeline/incremental_pipeline.py` — thin orchestrator wired by both the MCP tool and the CLI. Pure functions where possible; I/O at edges. |

### Rejected alternatives

- **New top-level CLI command `the-door analyze --inherit-from`**: conceptually overlaps with `the-door update`. Choose extension over duplication.
- **Two MCP tools (`prepare_incremental_diff` + `snapshot_write_incremental`)**: same logic rides on existing `snapshot_write` + one read-only sibling. Two-tool design forces agents through rigid two-step dance for no functional gain.
- **Embedding LLM call in incremental_pipeline**: the LLM call is the agent's responsibility (Mode B) or `analyze_pipeline`'s when API key present (Mode A). `incremental_pipeline` is the **diff-and-merge** logic only; it does not call any LLM directly.

### Test plan (§O1)

| RED | Behavior |
|---|---|
| O1-T1 | `compute_affected_features` with identical baseline and current structures → `affected_features=()`, `inherited_features` has all baseline features, `unmapped_nodes` empty |
| O1-T2 | Add one node whose `node_id` is in `feat-x`'s `source_nodes` → `feat-x` in `affected_features` with `delta.added == (node_id,)`; `inherited_features` excludes `feat-x` |
| O1-T3 | Remove one node from `feat-y`'s `source_nodes` → `feat-y` in `affected_features` with `delta.removed` |
| O1-T4 | Modify a node's signature (params change) that belongs to `feat-z` → `feat-z` in `affected_features` with `delta.modified` |
| O1-T5 | AST diff node belonging to no feature → appears in `unmapped_nodes`, no feature flagged |
| O1-T6 | `snapshot_write` MCP tool with `inherit_from="v1.0.0"` and `updated_features=[{...feat-x...}]` → result has 12 features (11 inherited + 1 replaced) |
| O1-T7 | `snapshot_write` MCP tool without `inherit_from` → existing behavior, no inheritance path touched |
| O1-T8 | `analyze_changes` MCP against baseline whose `structures/<vid>.json.gz` missing → returns F3 envelope with `remediation.code="no_persisted_structure_for_baseline"` and `next_action.cli_command="the-door analyze ..."` |
| O1-T9 | `the-door update --from-snapshot v1.0.0 ./current/` → pipeline runs, writes new snapshot, exits 0 |
| O1-T10 | `the-door update ./old/ ./new/` (existing positional form) → unchanged behavior, no regression |
| O1-T11 | `analyze_changes` response includes top-level `next_actions` with at least one entry pointing at how to call `snapshot_write` with `inherit_from` (S2 contract) |

> **[Task-refine]** The pseudocode for `compute_affected_features`, specific MCP tool names (`analyze_changes`), specific CLI flag (`--from-snapshot`), and the `signature_hash` field choice are starting sketches. **Architectural commitments**: (a) the diff-and-merge logic is a pure function with no LLM call; (b) every entry point (CLI, MCP, snapshot_write extension) shares the same underlying primitive; (c) baseline AST source MUST be reachable without requiring the baseline source code to be on disk (uses P2's persisted structure); (d) backfill path exists for legacy snapshots without API key.

---

## §O2 — Snapshot Reference Resolution

### Verified facts

- [`SnapshotStore.resolve_baseline`](the_door/src/the_door/core/diff/snapshot_store.py:105) only resolves: (1) ISO 8601 date, (2) git tag or commit SHA `[0-9a-f]{7,40}`, (3) manual label exact match.
- It does **NOT** handle raw UUID `version_id` — UUIDs fail the SHA regex due to hyphens.
- Fallback to `get_snapshot(reference)` (raw UUID file lookup) is therefore **load-bearing**, not defensive.

### Changes

| File | Change |
|---|---|
| [api_handlers.py:348-349](the_door/src/the_door/core/ui/api_handlers.py:348) | Replace direct `store.get_snapshot(baseline_id)` with: try `store.resolve_baseline(...)`, on `SnapshotNotFoundError` fall back to `store.get_snapshot(...)`. Repeat for `current_id`. |
| [api_handlers.py:368-378](the_door/src/the_door/core/ui/api_handlers.py:368) | Response payload gains `baseline_label`, `current_label`, `next_actions`. Existing fields unchanged. |
| Viewer version picker | Picker emits the snapshot's label (priority: git_tags[0] > label > version_id fallback) as the chosen reference. Located via grep on viewer/js (single-target grep — see tasks). |

### Test plan (§O2)

| RED | Behavior |
|---|---|
| O2-T1 | `/api/diff?baseline=v1.0.0&current=v1.0.5` on labeled snapshots → 200, payload has `baseline_label="v1.0.0"`, `current_label="v1.0.5"` |
| O2-T2 | `/api/diff?baseline=<valid_uuid>&current=<valid_uuid>` → 200, regression check |
| O2-T3 | `/api/diff?baseline=nonexistent&current=v1.0.5` → 404 with F3 envelope, `remediation.code="snapshot_not_found"`, `next_action.id="system_status.show"` |
| O2-T4 | Diff response with `summary.total_changed=0` still returns `next_actions` list, including a suggestion to inspect another version pair |
| O2-T5 | Viewer picker sends the label string (not UUID) when calling `/api/diff` |

> **[Task-refine]** The exact file:line of the api_handlers.py change and the specific response field names (`baseline_label`, `current_label`) are starting sketches. **Architectural commitments**: (a) any caller can pass label/tag/SHA/date/UUID interchangeably and resolution succeeds when one matches; (b) every response that names a snapshot carries both forms.

---

## §S1 — CLI Surface

### Components

| File | Change |
|---|---|
| `the_door/src/the_door/cli/status_cmd.py` (NEW) | `the-door status [<path>]`. Calls `StateInspector` + `NextActionSuggester(context="cli")`. Renders human-readable summary + numbered next-action list. Supports `THE_DOOR_NEXT_FORMAT=json` for machine output. |
| `the_door/src/the_door/cli/next_action_renderer.py` (NEW) | Single rendering helper shared by all post-command `Next:` output and error-remediation output. ~40 lines. |
| `the_door/src/the_door/cli/main.py` | Register `status_cmd`. |
| EACH existing CLI command (analyze_cmd, extract_cmd, update_cmd, diff_cmd, ui_cmd, scan_cmd, scope_cmd, doubt_cmd, timeline_cmd, validate_cmd, regenerate_cmd, render_cmd, estimate_cmd, history_cmd, projects_cmd, config_cmd, snapshot_cmd) | After successful operation, invoke a single `cli_post_run_hook(state_inspector, context="cli")` that prints `Next:` block to stderr. Skip if `--json` or similar machine-output flag is active (each command exposes its flag set; the hook checks a registered list). |
| Error rendering helper in `cli/main.py` | When a CLI command's exception path runs, render F3 envelope as text including `remediation.next_action.cli_command` if present. |

### Output format

Human form (default):
```
Project: /Users/.../my-project
  ✓ 2 snapshots:
    • v1.0.5 (latest, has structure)
    • v1.0.0 (has structure)
  ✓ Structure: 1431 nodes / 169 files
  ⚠ 1 warning: feat-cli-dispatch source_nodes drift (run `the-door analyze` to repair)

Next:
  1. the-door update --from-snapshot v1.0.0 .       (incremental analysis for new changes)
  2. the-door ui .                                  (open viewer to compare versions)
  3. the-door diff --baseline v1.0.0 .              (CLI diff)
```

JSON form (`THE_DOOR_NEXT_FORMAT=json` env):
```json
{ "state": { /* SystemState */ }, "next_actions": [ /* NextAction[] */ ] }
```

### Enforcement (avoid silent EVERY-X gaps)

A single meta-test `the_door/tests/unit/cli/test_next_block_coverage.py` enforces S1 AC2 at suite level. The test:

1. Imports `main.cli` (the Click root group).
2. Iterates `cli.commands.values()` — Click's authoritative command registry.
3. For each command, invokes the command in-process via `click.testing.CliRunner` with a minimal valid input that exercises the success path. Invocation recipes live in `the_door/tests/unit/cli/_invocation_recipes.py` (a **test fixture file**, not a production module — colocated with the meta-test).
4. Asserts the captured stderr contains the `Next:` token.
5. Failure mode: a command that does not call `cli_post_run_hook` produces stderr without `Next:` → test fails by name, identifying the command.

A command added in the future without the hook fails this meta-test on first run — no possibility of silent drift.

Counterpart for `--json` suppression: a second meta-test invokes each command with its registered `--json` flag (where defined) and asserts the `Next:` token is absent. Commands without a machine-output flag declare `null` in the recipes file to skip this leg.

### Test plan (§S1)

| RED | Behavior |
|---|---|
| S1-T1 | `the-door status` on empty dir → human output mentions `the-door analyze` as top next action; exit 0 |
| S1-T2 | `the-door status` on project with 1 snapshot + api_key → top suggestion is `the-door update --from-snapshot <label>` |
| S1-T3 | `THE_DOOR_NEXT_FORMAT=json the-door status` → stdout is valid JSON matching `{state, next_actions}` shape |
| S1-T4 | `the-door extract <path>` on fresh dir → stderr contains `Next:` block (after the existing "Structure JSON written to..." line) |
| S1-T5 | `the-door extract --json <path>` (existing flag) → stderr has NO `Next:` block (machine-output suppression) |
| S1-T6 | A CLI command that errors (e.g., `the-door diff` with bad baseline) → stderr contains `remediation.message` and the suggested `next_action.cli_command` |
| S1-T7 | Hook helper is invoked exactly once per command (no double-printing on commands that catch and re-raise) |

> **[Task-refine]** The example human-output format, the enumerated 17-cmd hook table, the `THE_DOOR_NEXT_FORMAT=json` env var, the meta-test mechanism's exact step list, and the `_invocation_recipes.py` test-fixture file are starting sketches. **Architectural commitments**: (a) `the-door status` is the entry-point command; (b) every CLI command emits a Next: block on success via a single shared rendering helper; (c) coverage is enforced — silent gaps are not allowed.

---

## §S2 — MCP Surface

### Components

| File | Change |
|---|---|
| `the_door/src/the_door/mcp/tools/system_status_tool.py` (NEW) | Returns `{state, next_actions}` per F1/F2. Schema: no required input. Optional `project_path` (defaults to MCP server's working dir). |
| `the_door/src/the_door/mcp/tools/analyze_changes_tool.py` (NEW) | Per O1. |
| EXTEND `the_door/src/the_door/mcp/tools/snapshot_write_tool.py` | Per O1 (add `inherit_from`, `updated_features` optional fields). |
| EACH MCP tool's response builder | After producing the tool's normal payload, call `suggester.suggest(post_op_state, context="mcp")` and inject `next_actions` at the response root. Centralized via `mcp/tools/_response_envelope.py` (NEW) to avoid per-tool duplication. |
| EACH MCP tool's error path | Use F3 envelope with `context="after_error"` suggestions. |
| [mcp/server.py:17, 113, 188](the_door/src/the_door/mcp/server.py:17) | Register `analyze_changes_tool` and `system_status_tool` at three sites: imports, `list_tools()` schema declaration, dispatch branch. |

### Enforcement (avoid silent EVERY-X gaps)

Meta-test `the_door/tests/unit/mcp/test_response_envelope_coverage.py` enforces S2 AC1 at suite level:

1. Imports `the_door.mcp.server` and resolves the list of registered Tool names.
2. For each tool, locates its module via the import mapping (already enumerated in [server.py:13-21](the_door/src/the_door/mcp/server.py:13)).
3. Invokes `tool_module.handle(arguments=<minimal_valid>, ...)` with a minimal valid input from `the_door/tests/unit/mcp/_invocation_recipes.py` (a **test fixture file**, not a production module — colocated with the meta-test).
4. Asserts the returned dict has a top-level `next_actions` key (may be `[]` for read-only tools, but the key SHALL exist).
5. Failure mode: a tool whose handler does not wrap via `_response_envelope.wrap()` returns a dict without that key → test fails by name, identifying the tool.

A new tool added without envelope wrapping fails this meta-test immediately.

### Test plan (§S2)

| RED | Behavior |
|---|---|
| S2-T1 | `system_status` MCP tool → response has `state` and `next_actions` |
| S2-T2 | EXISTING `snapshot_list` tool → response now also has `next_actions` (additive, no existing field changed) |
| S2-T3 | EXISTING `snapshot_create` tool with bad inputs → error response is F3 envelope |
| S2-T4 | `analyze_changes` with baseline missing persisted structure → F3 envelope error with `next_action.id="analyze.refresh_for_increment"` |
| S2-T5 | `snapshot_write` with `inherit_from + updated_features` → merged result; without those args → unchanged behavior |
| S2-T6 | `next_actions` injection is consistent across all tools (envelope helper is single source) |

> **[Task-refine]** Exact new tool names (`system_status_tool.py`, `analyze_changes_tool.py`), envelope helper module name (`_response_envelope.py`), and the 3 server.py registration site references are starting sketches. **Architectural commitments**: (a) every MCP tool response carries `next_actions`; (b) a centralized envelope helper enforces this; (c) coverage is meta-tested.

---

## §S3 — Viewer Surface

### Components

#### Onboarding card

When viewer's main `/` route loads and `state.has_snapshots === false`:
- Render an onboarding card centered in the canvas area.
- Content sourced from `/api/status` (new endpoint).
- Card shows: project path, `has_dot_the_door` status, top 3 next_actions with their CLI/MCP command shown.

When `state.has_snapshots === true`: existing viewer renders normally; onboarding card is NOT shown.

#### Detail panel wiring (regression fix)

Per §S3 regression analysis:
- [ui-detail.js:1-2](docs/frontend-local-version-viewer/viewer/js/ui-detail.js:1): add `import { appendUserNotesSection } from './ui-notes.js'` and `import { appendDiffExplanationSection } from './ui-diff-explanation.js'`.
- [ui-detail.js:5-6](docs/frontend-local-version-viewer/viewer/js/ui-detail.js:5): delete the two no-op stub definitions.
- Three call sites ([:132](docs/frontend-local-version-viewer/viewer/js/ui-detail.js:132), [:161](docs/frontend-local-version-viewer/viewer/js/ui-detail.js:161), [:263](docs/frontend-local-version-viewer/viewer/js/ui-detail.js:263)): pass `(container, mode, versionA, versionB, featureId)` order per real exports' signature. The diff-explanation call sites take `(container, featureId)`.
- ADDITIONALLY: when the L1 API response gains `next_actions` (per S2 + new endpoint), render a "建議的下一步" section under the existing sections, using a new `ui-next-actions.js` helper.

#### Mindmap data sourcing

`buildMindmapData(state)` pure function in `layers.js`:

```js
export function buildMindmapData(state) {
  const projectName = (state.projectStatus?.project_path ?? "").split(/[\/\\]/).filter(Boolean).pop() || "專案";
  const nodes = state.l1GraphViewModel?.nodes ?? [];

  let diffNodes = [];
  let diffAvailable = false;

  if (state.updateModel?.diff_available === true) {
    diffNodes = state.updateModel.changes ?? [];
    diffAvailable = true;
  } else if (state.versionDiff?.node_states) {
    diffNodes = Object.entries(state.versionDiff.node_states)
      .filter(([_, st]) => st !== "unchanged")
      .map(([id, change_type]) => ({ id, change_type }));
    diffAvailable = diffNodes.length > 0;
  }

  return { project: projectName, nodes, diffNodes, diffAvailable };
}
```

`switchToMindmap` becomes:
```js
export function switchToMindmap() {
  const data = buildMindmapData(state);
  sessionStorage.setItem("mindmap-data", JSON.stringify(data));
  window.open("./mindmap-popup.html", "mindmap", "width=960,height=720,resizable=yes,scrollbars=yes");
}
```

`mindmap-popup.html` is NOT modified. The shape `{id, change_type}` is what the popup already expects ([mindmap-popup.html:393, :523](docs/frontend-local-version-viewer/viewer/mindmap-popup.html:393)).

#### Version picker label-first

Picker passes the human-readable label as the diff API's `baseline` / `current` query param. Combined with O2's API-side resolution, the full pipeline works with labels.

#### New endpoint

`GET /api/status`:
- Handler in [api_handlers.py](the_door/src/the_door/core/ui/api_handlers.py) — new method `handle_get_status`.
- Returns `{state: <SystemState_JSON>, next_actions: <list>}`.
- SystemState JSON serialization: a stable shape spec'd here (frozen field set).

### Test plan (§S3)

| RED | Behavior |
|---|---|
| S3-T1 | `buildMindmapData` with `updateModel=null, versionDiff=null` → `{diffNodes: [], diffAvailable: false}` |
| S3-T2 | With `updateModel.diff_available=true`, `changes=[{id:'a', change_type:'attribute_changed'}]` → `diffNodes` is that array, `diffAvailable=true` |
| S3-T3 | With `updateModel=null`, `versionDiff.node_states={feat-a:"attribute_changed", feat-b:"unchanged"}` → `diffNodes=[{id:'feat-a', change_type:'attribute_changed'}]` |
| S3-T4 | Both present, report `diff_available=true` → prefer report |
| S3-T5 | Both present but report `diff_available=false` → fall through to versionDiff |
| S3-T6 | `renderFeature` in baseline mode → container contains `.user-notes-section` |
| S3-T7 | `renderFeature` in diff mode → both `.user-notes-section` AND `.diff-explanation-section` |
| S3-T8 | Node-selection path in diff mode → both sections rendered |
| S3-T9 | `/api/status` returns valid JSON with `state` and `next_actions` keys |
| S3-T10 | Viewer onboarding card visible only when `state.has_snapshots === false` |
| S3-T11 | Version picker sends label string (e.g., "v1.0.0") not UUID when label exists |

> **[Task-refine]** The exact `buildMindmapData` pseudocode and precedence rule, the exact `ui-detail.js` import order/argument order, the `/api/status` endpoint URL string, and the exact picker priority (git_tags[0] > label > version_id) are starting sketches. **Architectural commitments**: (a) onboarding card appears when project has no snapshots; (b) detail panel renders notes + diff-explanation sections; (c) mindmap consumes a single pure data-shaping function reading both diff sources; (d) viewer sends human-readable refs to the diff API; (e) mindmap-popup.html itself stays untouched.

---

## §S4 — Documentation Surface

### CLAUDE.md restructure

Target outline (replaces current Mode A/B parallel description):

```
# The Door — AI Agent Guide

## Start here: `the-door status`
Always run `the-door status` first. It tells you the project state
and prints `Next:` commands.

## Decision tree
- Do you have `.the-door/`? No → `the-door analyze <path>` (or agent flow if no API key)
- Do you have ≥1 snapshot? No → write one (analyze first)
- Has the source changed since the last snapshot? Yes:
  - With API key → `the-door update --from-snapshot <label> <path>`
  - Without API key → MCP `analyze_changes` → agent updates affected features → MCP `snapshot_write` with `inherit_from`
- Want to inspect a feature in the viewer? → `the-door ui <path>`

## Commands & MCP tool reference
(Brief reference, links to spec for details)

## Glossary (for backward compat)
- Mode A (legacy term): External LLM via API key. Now: covered by the "With API key" branches.
- Mode B (legacy term): Agent-as-LLM. Now: covered by the "Without API key" branches.
```

### Implementation note

CLAUDE.md is at the project root. Single file edit. No code change.

### Test plan (§S4)

| RED | Behavior |
|---|---|
| S4-T1 | `grep "the-door status" CLAUDE.md` finds at least one mention in the "Start here" section |
| S4-T2 | `grep "Mode A\|Mode B" CLAUDE.md` finds matches ONLY in the Glossary section |
| S4-T3 | A new-reader checklist (manual): every decision-tree leaf names exactly one command, no parallel "or"-style branching ambiguity |

(Doc tests are mostly content-driven and verified at task acceptance, not in CI.)

> **[Task-refine]** The exact target outline of CLAUDE.md (specific section headings, glossary placement, the decision-tree branches verbatim) is a starting sketch. **Architectural commitments**: (a) CLAUDE.md is restructured to a decision-tree shape; (b) `the-door status` is the documented entry point; (c) every leaf names exactly one command; (d) old terminology (Mode A / Mode B) is preserved in a glossary for backward compatibility with AI agents that have those terms cached.

---

## Execution Constraints

These are the architectural rules binding any agent (human or AI) implementing tasks against this spec.

1. **TDD discipline is mandatory.** RED-verify with the predicted failure mode (stated in the task) before writing production code. If RED looks different from predicted, stop and re-read the spec — your understanding or the spec is wrong; do not "adapt" the test to match unexpected behavior.

2. **Dependency direction is one-way.** Foundation → Primitives → Operations → Surfaces. A downstream tier MUST NOT cause upstream redesign mid-task. If a Surface task discovers a Foundation contract cannot serve it, stop and report — escalate as a Foundation revision, do not patch laterally.

3. **No new architectural surfaces unless this design names them.** If implementation reveals a needed new file, new MCP tool, new CLI command, or new data shape that has no precedent in this design, stop and update the spec first. Renaming a file or adjusting helper names within an architectural surface this design already authorizes is task-time refinement (not a new surface) and is permitted.

> **[Task-refine]** The pre-existing 9-constraint list (one-task-one-commit, exact file whitelists, no-defensive-code clauses, etc.) was an over-specification of task hygiene that confused architectural binding with task-time discipline. Task documents will re-establish task-hygiene rules (commit granularity, comment policy, verification scope) — that is task-phase territory, not architecture.

### Working list of NEW architectural surfaces this design authorizes

Used by Constraint 3 above. This list is itself task-refinable in non-architectural ways (renaming `state.py` → `inspector.py` is fine; introducing a brand-new MCP tool that isn't here is not).

- Foundation: `core/guidance/` directory housing the SystemState, NextAction, Remediation, and suggester modules (specific filenames task-refinable).
- Operations: a `feature_attribution` module under `core/diff/` (pure function) and an `incremental_pipeline` module under `core/pipeline/` (orchestrator).
- MCP tools: two new tools — one for `system_status`-style state inspection, one for `analyze_changes`-style read-only incremental-diff query. Plus a shared response-envelope helper.
- CLI: a `status` command + a shared next-action renderer helper. Two new flags on existing commands (`update --from-snapshot`, `extract --as-version`-or-equivalent).
- Viewer: a `ui-next-actions.js` helper for the detail panel's "建議的下一步" section.
- Test fixtures: a `colliding_init/` Python source fixture for P3 + invocation-recipe files colocated with the CLI/MCP meta-tests.

---

## Verification Strategy

Per requirement, all RED tests in this spec MUST fail (with the predicted error/message in the task) before any production code in that section is touched.

After each requirement's task batch lands:

| Stage | Verification |
|---|---|
| After F1 batch | `pytest the_door/tests/unit/core/guidance/ -q` — new test file fully passes; full suite still green (~580 → ~590) |
| After F2 batch | F2 test file fully passes; suggester rule-table tests are exhaustive |
| After F3 batch | F3 test file fully passes; existing error paths now return new envelope, existing consumers unaffected |
| After P1+P2+P3 | Full Python suite green; viewer JS suite still green (no touch) |
| After O1+O2 | New incremental flow end-to-end: `the-door update --from-snapshot v1.0.0 <v105_path>` on the existing test target produces a new snapshot with `feat-ui-server` as the only affected feature |
| After S1+S2 | `the-door status` works on a fresh project AND on a project with multiple snapshots; MCP `system_status` ditto |
| After S3 | Viewer onboarding card displays when applicable; detail panel notes section visible in all modes; mindmap shows `Δ` badge in diff mode against snapshot-comparison data |
| After S4 | CLAUDE.md restructure merged; old terms still searchable in glossary |

End-to-end acceptance test (recorded in tasks): re-run the 2026-05-16 session's scenario — "analyze v1.0.5 given v1.0.0 baseline" — entirely through documented commands, with no temp scripts, completing in under 5 minutes wall-clock for an AI agent that has only read CLAUDE.md.

---

## Out-of-Scope Reminders

Carried from requirements.md:
- Restoring v1.0.0 to English in the test target.
- Globally renaming node_id schema.
- Deleting `source_node_count` field.
- Building reconcile/migration CLIs.
- Populating anomaly entries on hand-edited L2 outputs.
- LLM-driven NextActionSuggester.
- Multi-project state, cloud sync, multi-user auth.
- Performance work beyond F1's 50ms target.
- Touching L2 generation, mermaid rendering, or non-diff API handlers.
- Web framework / CLI parser swap.
