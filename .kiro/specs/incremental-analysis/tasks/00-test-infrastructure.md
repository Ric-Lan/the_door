# 00 — Test Infrastructure (Property + Contract + Scenario)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Lay down three test harnesses that downstream task files (01–06) will populate as they implement features. The harnesses target the two failure modes pure example-based TDD does NOT catch:

1. **Residual "didn't think of that case" bugs** → property tests (`hypothesis`) on identified pure functions.
2. **Cross-task continuity drift** → contract tests at each tier seam (one per producer/consumer pair).
3. **Composition-only bugs** → a single end-to-end scenario (v105 baseline + v1.0.5 source) that runs continuously, gated by tier completion via `pytest.skip` markers.

No production code is touched in this file. The output is test scaffolding + dev-dep additions only.

**Skill profile:** Python — `hypothesis` property test design, pytest fixture authoring (conftest.py shared fixtures), `pytest.skip` tier-gating pattern, scenario test composition.

**Dependencies:** None. This file lays the foundation everything else writes against.

**Commit conventions:** `test(infra):` for new test directories / fixtures, `chore(deps):` for the hypothesis dependency.

## What this file does NOT do

- It does **not** assert anything about production behavior (all the tests start as `pytest.skip(...)` placeholders that downstream tasks remove).
- It does **not** introduce new production modules.
- It does **not** pin specific implementations — only the **shape** of the contract / scenario / property invariant.

## Why these three harnesses, in this order

| Harness | Catches | Why now (before 01) |
|---|---|---|
| Property tests | Hidden edge cases in pure functions (e.g., empty inputs, single-element groups, duplicates) | The seed test patterns must exist before any task writes its first pure function — otherwise the temptation is "just add more examples" |
| Contract tests at task seams | Cross-task field/semantic drift | Both producer and consumer task files reference the same contract file — placing the contract before either side prevents two divergent definitions |
| Scenario gate | Composition-only bugs that no unit test would catch | Establishing the scenario steps up-front gives every downstream task an explicit "what step of the scenario does this task unlock" target |

## Files touched

| Path | Action |
|---|---|
| `the_door/pyproject.toml` or `requirements-dev.txt` (whichever the project uses) | Modify — add `hypothesis` to dev dependencies |
| `the_door/tests/conftest.py` | Modify — add shared fixtures used by scenario + contract tests (or create if absent) |
| `the_door/tests/contract/__init__.py` | Create (empty package marker) |
| `the_door/tests/contract/README.md` | Create — explain the seam-contract pattern |
| `the_door/tests/contract/test_snapshot_entry_contract.py` | Create — Task 01 ↔ Task 02 seam |
| `the_door/tests/contract/test_systemstate_json_contract.py` | Create — Task 02 ↔ Task 05 (viewer `/api/status`) seam |
| `the_door/tests/contract/test_remediation_envelope_contract.py` | Create — Task 02 ↔ Task 04 ↔ Task 05 seam |
| `the_door/tests/contract/test_incremental_diff_shape_contract.py` | Create — Task 03 ↔ Task 05 (viewer's diff display) seam |
| `the_door/tests/scenario/__init__.py` | Create (empty package marker) |
| `the_door/tests/scenario/test_v105_incremental_flow.py` | Create — end-to-end gate, all steps initially skipped |
| `the_door/tests/unit/_property_examples.py` | Create — small reference patterns for hypothesis use; downstream tasks copy from here |

---

## Task 00.1 — Add hypothesis to dev dependencies

**Files:**
- Modify: `the_door/pyproject.toml` (or `requirements-dev.txt`)

- [ ] **Step 1: Locate the dev-deps declaration**

Read `the_door/pyproject.toml`. Find the `[project.optional-dependencies]` or `[tool.poetry.group.dev.dependencies]` section (whichever exists). If neither, fall back to `requirements-dev.txt`.

- [ ] **Step 2: Add hypothesis**

```toml
# in pyproject.toml [project.optional-dependencies].dev (or equivalent):
"hypothesis>=6.0",
```

`hypothesis>=6.0` is the long-stable major; pin to current minor only if a wider range causes resolver pain.

- [ ] **Step 3: Install in current env**

```bash
pip install -e ".[dev]"  # or whatever the project's editable-install incantation is
python -c "import hypothesis; print(hypothesis.__version__)"
```

Expected: prints a version ≥ 6.0.

- [ ] **Step 4: Commit**

```bash
git add the_door/pyproject.toml
git commit -m "chore(deps): add hypothesis for property tests in 01-05 (test infra)"
```

---

## Task 00.2 — Add a property-test reference pattern

**Files:**
- Create: `the_door/tests/unit/_property_examples.py`

The downstream task files refer readers here for "how to write a property test." Keep this file tiny and concrete — a single illustrative example each downstream pure function can be modeled after. Do NOT write property tests against production functions yet; this file establishes only the pattern.

- [ ] **Step 1: Write the reference file**

```python
"""Reference patterns for hypothesis property tests.

Downstream task files identify specific production functions (compute_affected_features,
NextActionSuggester, _disambiguate_node_ids, etc.) that should be property-tested.
Each task copies the pattern below and replaces the example with the production
function's invariant.

Do NOT import this file from production code — it is a documentation fixture only.
"""
from __future__ import annotations
from hypothesis import given, strategies as st


# Pattern A — invariant over input shape:
# "for any valid input, the output satisfies P(output)"
@given(st.lists(st.integers(), max_size=20))
def example_reverse_is_involutive(xs):
    """Reversing twice yields the original list — invariant, not a single example."""
    assert list(reversed(list(reversed(xs)))) == xs


# Pattern B — invariant over input/output relationship:
# "for any input X partitioned into (A, B), |A| + |B| == |X|"
@given(st.lists(st.integers(), min_size=0, max_size=20))
def example_partition_total_preserved(xs):
    evens = [x for x in xs if x % 2 == 0]
    odds = [x for x in xs if x % 2 == 1]
    assert len(evens) + len(odds) == len(xs)


# Pattern C — invariant over composition:
# "f(g(x)) == g(f(x)) for commuting f, g, or f(g(x)) == identity for inverses"
# (Use when proving a serializer + deserializer round-trip.)
@given(st.dictionaries(st.text(min_size=1, max_size=10), st.integers(), max_size=10))
def example_json_roundtrip(d):
    import json
    assert json.loads(json.dumps(d)) == d
```

- [ ] **Step 2: Commit**

```bash
git add the_door/tests/unit/_property_examples.py
git commit -m "test(infra): hypothesis reference patterns for downstream property tests"
```

---

## Task 00.3 — Create contract test directory + 4 seam skeletons

**Files:**
- Create: `the_door/tests/contract/__init__.py` (empty)
- Create: `the_door/tests/contract/README.md`
- Create: 4 contract test files (one per tier seam)

Each contract test starts as `pytest.skip("blocked on <task-id>")`. The task that satisfies the producer side removes the skip and replaces it with the real producer call. The task that satisfies the consumer side then asserts on the contract.

- [ ] **Step 1: Write the README**

```markdown
# Contract Tests — Tier Seam Verification

Each file here pins the *interface* between two task tiers. Producer and consumer task
suites both reference these contracts.

## How to consume

- A contract test starts with `pytest.skip("blocked on <task-id>")`.
- When the producer task lands, that task's commit removes the skip from the
  producer-side assertion (the part that constructs the contract value from the
  real producer).
- When the consumer task lands, that task's commit removes the skip from the
  consumer-side assertion (the part that feeds the contract value to the consumer
  and asserts behavior).
- Both sides live in the same test — the seam can only go GREEN when BOTH tiers
  are correct AND aligned.

## Why not put these in `unit/` or `integration/`?

`unit/` tests verify ONE module's behavior. `integration/` tests verify a flow.
Contract tests are neither — they verify that the *boundary* between two modules
agrees on shape and semantics. Misplacing them in either bucket dilutes that signal.
```

- [ ] **Step 2: Write the 4 contract test skeletons**

All four follow the same pattern. The example below is `test_snapshot_entry_contract.py`; mirror the structure for the other three.

`test_snapshot_entry_contract.py`:

```python
"""Contract: SnapshotEntry shape from Task 01 (SnapshotStore.list_analyzed_versions)
matches what Task 02 (StateInspector) reads.

Producer side: Task 01 (01-core-data.md Task 01.5) — defines + emits SnapshotEntry.
Consumer side: Task 02 (02-guidance-engine.md Task 02.3) — reads via inspect()'s step 4.
"""
import pytest


@pytest.mark.contract
def test_snapshotentry_field_set_matches_consumer_expectation(tmp_path):
    pytest.skip("blocked on 01-core-data Task 01.5 (producer) AND 02-guidance-engine Task 02.3 (consumer)")

    # PRODUCER SIDE — remove skip in 01.5 commit, populate this block:
    # from the_door.core.diff.snapshot_store import SnapshotStore
    # ... seed a snapshot, call list_analyzed_versions()
    # entries = SnapshotStore(tmp_path).list_analyzed_versions()
    # assert len(entries) == 1
    # producer_entry = entries[0]

    # CONSUMER SIDE — remove skip in 02.3 commit, populate this block:
    # from the_door.core.guidance.state import StateInspector
    # state = StateInspector(tmp_path).inspect()
    # consumer_entry = state.snapshots[0]

    # SEAM ASSERTIONS — what BOTH sides MUST agree on:
    # assert type(producer_entry).__name__ == type(consumer_entry).__name__
    # assert producer_entry.version_id == consumer_entry.version_id
    # assert producer_entry.has_persisted_structure == consumer_entry.has_persisted_structure
    # assert producer_entry.label == consumer_entry.label
    # assert producer_entry.git_tags == consumer_entry.git_tags
    # assert producer_entry.timestamp == consumer_entry.timestamp
```

`test_systemstate_json_contract.py`:

```python
"""Contract: SystemState JSON shape from Task 02 (to_json_dict) matches what
Task 05 (viewer /api/status handler + onboarding card consumer) reads.

Producer side: 02-guidance-engine.md Task 02.2 — defines to_json_dict.
Consumer side: 05-viewer-frontend.md Task 05.3 — emits via /api/status; Task 05.6 consumes
in the onboarding card (state.has_snapshots, state.project_path, ...).
"""
import pytest


@pytest.mark.contract
def test_systemstate_json_keys_match_viewer_consumer():
    pytest.skip("blocked on 02-guidance-engine Task 02.2 (producer) AND 05-viewer-frontend Task 05.3 (consumer)")

    # PRODUCER SIDE — populated in 02.2:
    # from the_door.core.guidance.state import SystemState, to_json_dict
    # from pathlib import Path
    # state = SystemState(project_path=Path("/x"), has_dot_the_door=False,
    #                     has_structure_json=False, snapshots=(),
    #                     l2_features_analyzed=frozenset(),
    #                     has_api_key=False, api_provider=None, warnings=())
    # produced = to_json_dict(state)

    # CONSUMER SIDE — what the viewer's onboarding card reads (05.6) MUST be present:
    # required_keys = {
    #     "project_path", "has_dot_the_door", "has_snapshots", "latest_snapshot",
    #     "snapshots", "warnings", "has_api_key", "api_provider",
    # }
    # missing = required_keys - set(produced.keys())
    # assert missing == set(), f"viewer consumer needs {missing} but producer doesn't emit them"

    # Also: the api_provider type contract — viewer expects null OR one of three strings
    # assert produced["api_provider"] in (None, "anthropic", "openai", "ollama")
```

`test_remediation_envelope_contract.py`:

```python
"""Contract: F3 error envelope shape — producer is Task 02 (make_error_envelope),
consumers are Task 04 (CLI error renderer) AND Task 05 (viewer /api error handlers + ui error display).

This is a three-way seam. The contract is the JSON shape; all three sides MUST agree.
"""
import pytest


@pytest.mark.contract
def test_error_envelope_shape_satisfies_all_consumers():
    pytest.skip("blocked on 02-guidance-engine Task 02.6 (producer) AND 04-cli-ux Task 04.4 (CLI consumer) AND 05-viewer-frontend Task 05.8 (viewer consumer)")

    # PRODUCER — populated in 02.6:
    # from the_door.core.guidance.remediation import Remediation, make_error_envelope
    # from the_door.core.guidance.actions import NextAction
    # rem = Remediation(code="x", message="m",
    #                   next_action=NextAction(id="a.b", title="t", rationale="r", priority=1,
    #                                          cli_command="ls"))
    # envelope = make_error_envelope(code="x", message="m", remediation=rem, source="here")

    # CONSUMERS — what each side needs:
    # CLI renderer (04.4) needs:
    # assert "error" in envelope
    # assert envelope["error"]["remediation"]["message"]
    # assert envelope["error"]["remediation"]["next_action"]["cli_command"]
    #
    # Viewer error display (05.8) needs:
    # assert envelope["error"]["code"]
    # assert envelope["error"]["source"]
    # assert "remediation" in envelope["error"]
    # # remediation.next_action may be null:
    # assert envelope["error"]["remediation"]["next_action"] is None or \
    #        "id" in envelope["error"]["remediation"]["next_action"]
```

`test_incremental_diff_shape_contract.py`:

```python
"""Contract: IncrementalDiff shape from Task 03 (analyze_changes MCP tool +
compute_affected_features) matches what Task 05 displays in the viewer.

Producer side: 03-pipeline-mcp.md Task 03.5 — analyze_changes JSON output.
Consumer side: 05-viewer-frontend.md (not yet — viewer doesn't display affected_features
list directly today, but a future task will). Until then this contract pins the
producer-to-MCP-agent shape.
"""
import pytest


@pytest.mark.contract
def test_analyze_changes_response_shape():
    pytest.skip("blocked on 03-pipeline-mcp Task 03.5 (producer)")

    # PRODUCER — populated in 03.5:
    # response = await analyze_changes_tool.execute({"codebase_path": ..., "baseline": "v1.0.0"})
    #
    # MCP-AGENT CONSUMER — what an LLM agent reading the response needs:
    # required_top_level = {"baseline_version_id", "baseline_label", "inherited_features",
    #                       "affected_features", "unmapped_nodes", "next_actions"}
    # assert required_top_level <= set(response.keys()) or "error" in response
    #
    # # Each affected feature exposes the delta:
    # for af in response.get("affected_features", []):
    #     assert "feature_id" in af
    #     assert "delta" in af
    #     assert set(af["delta"].keys()) >= {"added", "removed", "modified"}
```

- [ ] **Step 3: Register the `contract` pytest mark**

In `the_door/pyproject.toml` `[tool.pytest.ini_options]` (or `pytest.ini` / `setup.cfg`), add:

```toml
markers = [
    "contract: cross-tier seam contract tests; gated by pytest.skip until both producer and consumer tasks land",
    "scenario: end-to-end scenario tests; gated by pytest.skip until prerequisite tiers land",
]
```

If a `markers = [...]` entry already exists, append the two new entries — do not replace.

- [ ] **Step 4: Run the contract suite (all skips)**

```bash
PYTHONIOENCODING=utf-8 python -m pytest the_door/tests/contract/ -q
```

Expected: 4 tests, all skipped. No errors.

- [ ] **Step 5: Commit**

```bash
git add the_door/tests/contract/ the_door/pyproject.toml
git commit -m "test(infra): contract test skeletons + 'contract' pytest mark for tier seams"
```

---

## Task 00.4 — Create scenario gate (v105 end-to-end)

**Files:**
- Create: `the_door/tests/scenario/__init__.py` (empty)
- Create: `the_door/tests/scenario/test_v105_incremental_flow.py`
- Modify: `the_door/tests/conftest.py` (add `v105_fixture` shared fixture)

The scenario test walks the canonical end-to-end flow that motivates this entire spec: "given a project with a v1.0.0 baseline snapshot + v1.0.5 source, produce a snapshot where only `feat-ui-server` is in `affected_features`." Each step is a `def step_N_...()` helper called from the single top-level test, gated by a `pytest.skip` when the prerequisite task hasn't landed.

- [ ] **Step 1: Add the shared `v105_fixture` fixture**

In `the_door/tests/conftest.py` (create if missing):

```python
import os
import shutil
from pathlib import Path
import pytest


_V105_DEFAULT = Path(r"C:\Users\Ric\Desktop\test-targets\the-door-v105")
_V105_ENV = "THE_DOOR_V105_FIXTURE"


@pytest.fixture
def v105_fixture(tmp_path):
    """A writable copy of the v105 test target's .the-door/ state.

    Source resolution:
    1. THE_DOOR_V105_FIXTURE env var (if set, must point at an existing dir with .the-door/)
    2. The default Windows path used during spec development
    3. pytest.skip if neither is available

    The fixture copies .the-door/ into tmp_path so tests can mutate state safely.
    Source code for v1.0.5 is NOT copied — tests that need the source files use
    their own minimal fixtures.
    """
    src = Path(os.environ.get(_V105_ENV, _V105_DEFAULT))
    if not (src / ".the-door").is_dir():
        pytest.skip(f"v105 fixture not available at {src}; set {_V105_ENV} to override")
    shutil.copytree(src / ".the-door", tmp_path / ".the-door")
    return tmp_path
```

`v105_fixture` returns the project root (a writable tmp_path with `.the-door/` copied in). Tests treat it as the codebase path.

- [ ] **Step 2: Write the scenario test scaffold**

`test_v105_incremental_flow.py`:

```python
"""End-to-end gate: v1.0.0 baseline + v1.0.5 source → snapshot with feat-ui-server affected.

This single test walks the entire flow. Each step is gated on its prerequisite task —
when that task lands, its commit removes the matching skip. When all skips are gone,
the spec is composition-correct.

Removing a skip is the responsibility of the task that satisfies the step. If removing
the skip causes the assertion to fail, the integration is broken — the task is NOT
done, regardless of whether its own unit tests passed.
"""
import pytest


pytestmark = pytest.mark.scenario


def test_v105_incremental_flow(v105_fixture):
    """Walk the canonical scenario step-by-step. Each step's skip is removed by
    the task documented in the step's docstring.
    """
    project = v105_fixture
    _step_1_inspect_returns_one_snapshot(project)
    state = _step_2_inspector_emits_systemstate(project)
    _step_3_suggester_recommends_incremental(state)
    diff = _step_4_compute_affected_features_isolates_feat_ui_server(project)
    new_snapshot = _step_5_snapshot_write_inherits_unchanged_features(project, diff)
    _step_6_viewer_diff_api_returns_attribute_changed_only(project, new_snapshot)
    _step_7_status_cli_emits_next_block(project)


def _step_1_inspect_returns_one_snapshot(project):
    """Removed by: 01-core-data Task 01.5 (SnapshotStore.list_analyzed_versions)."""
    pytest.skip("blocked on 01-core-data Task 01.5")
    # from the_door.core.diff.snapshot_store import SnapshotStore
    # entries = SnapshotStore(project).list_analyzed_versions()
    # assert any(e.label == "v1.0.0" for e in entries)


def _step_2_inspector_emits_systemstate(project):
    """Removed by: 02-guidance-engine Task 02.3 (StateInspector.inspect)."""
    pytest.skip("blocked on 02-guidance-engine Task 02.3")
    # from the_door.core.guidance.state import StateInspector
    # state = StateInspector(project).inspect()
    # assert state.has_dot_the_door is True
    # assert len(state.snapshots) >= 1
    # return state


def _step_3_suggester_recommends_incremental(state):
    """Removed by: 02-guidance-engine Task 02.5 (NextActionSuggester)."""
    pytest.skip("blocked on 02-guidance-engine Task 02.5")
    # from the_door.core.guidance.suggester import NextActionSuggester
    # actions = NextActionSuggester().suggest(state, context="cli")
    # # When API key present + 1 snapshot, top suggestion is incremental analysis
    # if state.has_api_key:
    #     assert actions[0].id == "analyze.incremental"


def _step_4_compute_affected_features_isolates_feat_ui_server(project):
    """Removed by: 03-pipeline-mcp Task 03.1 + Task 03.2 (compute_affected_features +
    incremental_pipeline orchestrator).

    Requires v1.0.5 source on disk OR a stand-in that produces the same AST diff.
    If only .the-door/ is copied (no source), use a synthetic v1.0.5 fixture path.
    """
    pytest.skip("blocked on 03-pipeline-mcp Task 03.1 + 03.2")
    # from the_door.core.pipeline.incremental_pipeline import run_incremental_pipeline
    # result = run_incremental_pipeline(codebase_path=<v1.0.5 source path>, baseline_ref="v1.0.0")
    # affected_ids = {af.feature_id for af in result.diff.affected_features}
    # assert affected_ids == {"feat-ui-server"}, f"unexpected affected: {affected_ids}"
    # return result.diff


def _step_5_snapshot_write_inherits_unchanged_features(project, diff):
    """Removed by: 03-pipeline-mcp Task 03.6 (snapshot_write inherit_from extension)."""
    pytest.skip("blocked on 03-pipeline-mcp Task 03.6")
    # ... call snapshot_write_tool.execute with inherit_from + updated_features ...
    # Assert the resulting snapshot has all baseline features, with feat-ui-server replaced.
    # return new_snapshot


def _step_6_viewer_diff_api_returns_attribute_changed_only(project, new_snapshot):
    """Removed by: 05-viewer-frontend Task 05.4 (api_handlers.py /api/diff with O2)."""
    pytest.skip("blocked on 05-viewer-frontend Task 05.4")
    # from the_door.core.ui.api_handlers import ApiHandlers
    # handlers = ApiHandlers(project_root=project)
    # status, body = handlers.handle_diff_versions(baseline_id="v1.0.0", current_id=new_snapshot.label)
    # assert status == 200
    # assert body["summary"]["attribute_changed"] == 1


def _step_7_status_cli_emits_next_block(project):
    """Removed by: 04-cli-ux Task 04.2 (the-door status command)."""
    pytest.skip("blocked on 04-cli-ux Task 04.2")
    # from click.testing import CliRunner
    # from the_door.cli.main import cli
    # result = CliRunner(mix_stderr=False).invoke(cli, ["status", str(project)])
    # assert result.exit_code == 0
    # assert "Next:" in result.stderr
```

- [ ] **Step 3: Run the scenario test (all skips)**

```bash
PYTHONIOENCODING=utf-8 python -m pytest the_door/tests/scenario/ -q -rs
```

Expected: 1 test (the top-level `test_v105_incremental_flow`), skipped at step 1. `-rs` shows the skip reason — confirm it reads `blocked on 01-core-data Task 01.5`.

- [ ] **Step 4: Verify scenario isolation**

The scenario suite should be runnable on machines without the v105 fixture too — the fixture's `pytest.skip` (Task 00.4 Step 1) handles absence cleanly.

```bash
THE_DOOR_V105_FIXTURE=/nonexistent python -m pytest the_door/tests/scenario/ -q
```

Expected: 1 test, skipped at the FIXTURE level (`v105 fixture not available at /nonexistent`).

- [ ] **Step 5: Commit**

```bash
git add the_door/tests/scenario/ the_door/tests/conftest.py
git commit -m "test(infra): v105 scenario gate with tier-skip markers per step"
```

---

## Task 00.5 — Wire the contract + scenario suites into the standard verification flow

**Files:**
- Modify: `the_door/pyproject.toml` (or `pytest.ini`) — extend the default test discovery
- Modify: every task file 01–06 — add a "remove the matching skip" reminder at each task that satisfies a skip

The scenario/contract suites must run alongside `pytest the_door/tests/unit/ the_door/tests/integration/` whenever someone verifies a task is GREEN. Otherwise downstream tasks can land green-but-misaligned and the drift only surfaces at "all done" time.

- [ ] **Step 1: Update pytest discovery (informational, not strict)**

In `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["the_door/tests"]   # ensures contract/ + scenario/ are picked up by default
```

If `testpaths` already exists, confirm it includes `the_door/tests` (the parent — not just `unit/integration`).

- [ ] **Step 2: Update README's cross-cutting convention #7**

Already done — README.md item 7 now reads "After each task in 01–06: also run `pytest the_door/tests/contract/ the_door/tests/scenario/ -q` to detect drift across tiers; this is what 00 enables."

- [ ] **Step 3: Sanity check — all four suites run**

```bash
PYTHONIOENCODING=utf-8 python -m pytest the_door/tests/unit/ the_door/tests/integration/ the_door/tests/contract/ the_door/tests/scenario/ -q -rs
```

Expected: existing unit + integration tests green; contract suite shows 4 skipped; scenario suite shows 1 skipped (or the fixture skip).

- [ ] **Step 4: Commit**

```bash
git add the_door/pyproject.toml
git commit -m "test(infra): include contract + scenario suites in default test discovery"
```

---

## Done criteria for 00-test-infrastructure

1. `pytest the_door/tests/contract/ -q -rs` shows 4 tests, all skipped with "blocked on" reasons that name specific downstream tasks.
2. `pytest the_door/tests/scenario/ -q -rs` shows 1 test, skipped (either at the fixture level if v105 not present, or at step 1 if it is).
3. `python -c "import hypothesis"` succeeds; `the_door/tests/unit/_property_examples.py` exists with three reference patterns.
4. The `contract` and `scenario` pytest marks are registered (no `PytestUnknownMarkWarning` when running either suite).
5. Running the full test command `pytest the_door/tests/ -q` exits 0 (existing tests still green; new skips don't fail).
6. No production code under `the_door/src/` has been modified.

## What downstream tasks (01–06) inherit from here

- A reference pattern file (`_property_examples.py`) to copy `@given` patterns from when a task identifies a pure function worth property-testing.
- 4 contract files in `tests/contract/` that downstream tasks **must** unblock by removing the matching skip in the same commit that satisfies the producer or consumer side. The task file lists tell you which task owns which removal.
- 1 scenario file in `tests/scenario/` with 7 skipped steps. Each downstream task that satisfies a step removes its skip in the same commit. The scenario test going GREEN end-to-end is part of the spec's "Done criteria."
- A registered `contract` and `scenario` mark — usable via `pytest -m contract` or `pytest -m scenario` for targeted runs.
