# v1.0.5 Source Fixture — Design

**Date:** 2026-05-18
**Status:** Approved, pending implementation
**Owner:** ad-hoc maintenance task (post incremental-analysis spec)

## Goal

Unblock `tests/scenario/test_v105_incremental_flow.py` steps 4 and 7 by adding a
test fixture that provides v1.0.5 source files on disk (in addition to the
`.the-door/` snapshots that the existing `v105_fixture` already copies). This
makes the canonical incremental-analysis scenario end-to-end test exercise the
real main-program code path:

```
fixture (input only) → main program (produces results) → test assertions (check results)
```

Today, step 4 of the scenario test is `pytest.skip(...)`'d because it requires
v1.0.5 source on disk, and the existing fixture deliberately only copies
`.the-door/`. Step 7 is also skipped, gated on `04-cli-ux Task 04.2` which has
since landed (a free win).

## Non-goals

- Un-narrow `04.5` / `04.6` narrow-scope tests. They are GREEN today; their
  unwind is logged as separate follow-ups.
- Un-narrow `05.4` / `05.8` narrow-scope tests. Investigation showed they do
  not actually need source files — the original narrowing was a name
  mismatch (`seeded_v105_fixture` vs `v105_fixture`), not a source gap.
  Their unwind is also follow-up.
- Rename `v105_fixture` or alias `seeded_v105_fixture`. The existing fixture
  works; the spec-vs-real naming gap is documented in memory follow-up #35.

## Design

### §1 — New fixture: `v105_fixture_with_source`

Add to `the_door/tests/conftest.py`, parallel to the existing `v105_fixture`:

```python
@pytest.fixture
def v105_fixture_with_source(tmp_path):
    """Writable copy of v105 test target — BOTH .the-door/ snapshots AND v1.0.5 source.

    Same resolution rules as v105_fixture:
    1. THE_DOOR_V105_FIXTURE env var (must point at an existing dir with .the-door/)
    2. _V105_DEFAULT (Windows path used during spec development)
    3. pytest.skip if neither is available

    Difference from v105_fixture: copies the full project tree (source + .the-door/),
    so callers can run AST extraction / incremental_pipeline against tmp_path.
    """
    src = Path(os.environ.get(_V105_ENV, _V105_DEFAULT))
    if not (src / ".the-door").is_dir():
        pytest.skip(f"v105 fixture not available at {src}; set {_V105_ENV} to override")
    shutil.copytree(src, tmp_path, dirs_exist_ok=True)
    return tmp_path
```

Key properties:

- **Parallel to existing `v105_fixture`** — does not modify or remove it.
  Callers that only need `.the-door/` keep using the lighter fixture for speed.
- **Same source-resolution semantics** — env var → default path → skip.
  Identical contract, only the copy scope differs.
- **`dirs_exist_ok=True`** — Python 3.8+. The conftest `_clean_tmp_path`
  autouse fixture already ensures tmp_path is empty at test start; this flag
  hardens against future semantics changes.
- **Returns `tmp_path`** — same as `v105_fixture`, callers treat it as a
  project root.

### §2 — Scenario test changes

Modify `the_door/tests/scenario/test_v105_incremental_flow.py`.

**Switch fixture:**

```python
def test_v105_incremental_flow(v105_fixture_with_source):
    project = v105_fixture_with_source
    _step_1_inspect_returns_one_snapshot(project)
    state = _step_2_inspector_emits_systemstate(project)
    _step_3_suggester_recommends_incremental(state)
    diff = _step_4_compute_affected_features_isolates_feat_ui_server(project)
    new_snapshot = _step_5_snapshot_write_inherits_unchanged_features(project, diff)
    _step_6_viewer_diff_api_returns_attribute_changed_only(project, new_snapshot)
    _step_7_status_cli_emits_next_block(project)
```

Steps 1–3, 5, 6 work unchanged — they only need `.the-door/`, and the new
fixture is a superset.

**Un-skip step 4:**

```python
def _step_4_compute_affected_features_isolates_feat_ui_server(project):
    """Removed by: 03-pipeline-mcp Task 03.1 + Task 03.2."""
    from the_door.core.pipeline.incremental_pipeline import run_incremental_pipeline
    result = run_incremental_pipeline(codebase_path=project, baseline_ref="v1.0.0")
    affected_ids = {af.feature_id for af in result.diff.affected_features}
    assert affected_ids == {"feat-ui-server"}, f"unexpected affected: {affected_ids}"
    return result.diff
```

Real API name + signature + field names will be verified during implementation
via grep — see "Implementation discovery" below.

**Un-skip step 7:**

```python
def _step_7_status_cli_emits_next_block(project):
    """Removed by: 04-cli-ux Task 04.2."""
    from click.testing import CliRunner
    from the_door.cli.main import cli
    result = CliRunner(mix_stderr=False).invoke(cli, ["status", str(project)])
    assert result.exit_code == 0
    assert "Next:" in result.stderr
```

Real `cli` import path and the stderr-vs-stdout location of `Next:` will be
verified during implementation.

### Why this matters — the E2E principle

The scenario test is the canonical end-to-end gate for incremental analysis:

```
v105_fixture_with_source           ← input only
    ↓
run_incremental_pipeline           ← main code produces affected features
    ↓
snapshot_write_tool(inherit_from)  ← main code writes new snapshot
    ↓
APIHandlers.handle_diff_versions   ← main code computes the diff
    ↓
the-door status CLI                ← main code renders Next: block
    ↓
test assertions                    ← check what the main program produced
```

Before this change, step 4 skips, which cascades — step 5/6 still run but
exercise only the `inherit_from` contract directly (not the full pipeline).
After this change, the full chain exercises end-to-end, and any drift between
unit-tested components surfaces here.

## Implementation discovery (verify before editing)

The spec mentions APIs that the implementer must verify against current code:

1. `from the_door.core.pipeline.incremental_pipeline import run_incremental_pipeline`
   — confirm the module path and function name. Grep `run_incremental_pipeline`
   in `the_door/src/the_door/core/pipeline/` (or wherever the 03.2 task put it).
2. `result.diff.affected_features` and `af.feature_id` — confirm the attribute
   chain by reading the dataclass / model that `run_incremental_pipeline` returns.
3. `from the_door.cli.main import cli` and `result.stderr` containing `"Next:"`
   — confirm by grepping `def status` in `the_door/src/the_door/cli/` and
   checking which click context emits the `Next:` block (stderr is the
   convention from S1 / 04.2).

Adapt naming silently when reality differs from the spec's literal text;
document any adapt in the commit body.

## Risks

| # | Risk | Likelihood | Mitigation |
|---|---|---|---|
| A | `run_incremental_pipeline` API name/signature differs from spec | High | Grep first, adapt the import + call site. Spec adapt documented in commit body. |
| B | `affected_ids == {"feat-ui-server"}` is wrong against real v1.0.0/v1.0.5 (empty, or includes more features) | Medium | Print actual `affected_ids` first. Root-cause: (i) widen assertion to `"feat-ui-server" in affected_ids` and mark DONE_WITH_CONCERNS, or (ii) fix 03.1 if signature comparison is wrong, or (iii) adjust the v1.0.0 baseline. Decide based on what surfaces. |
| C | Step 5 / 6 reveal existing bugs once the chain is fully exercised | Low | Fix the bug — it is in-scope (this PR's purpose is exactly to surface such drift). |

### Fallback policy

If Risk B's root cause is too deep to fix in this PR:

- Widen the assertion to `"feat-ui-server" in affected_ids` (still real, just
  permissive about extras).
- Mark DONE_WITH_CONCERNS in the handoff.
- Open a follow-up for "03.1 affected_features precision".
- Step 4 still goes from skip → real execution; this is progress even with a
  loose assertion.

Do **not** fall back to re-narrowing or stubbing — that defeats the task's
purpose.

## Done criteria

1. `v105_fixture_with_source` added to `the_door/tests/conftest.py` with the
   spec'd docstring and source-resolution semantics.
2. `tests/scenario/test_v105_incremental_flow.py::test_v105_incremental_flow`
   uses the new fixture and `_step_4_*` is un-skipped + PASSES.
3. `_step_7_*` is un-skipped + PASSES.
4. `_step_5_*` and `_step_6_*` continue to PASS (no regressions from the
   chain being fully exercised).
5. Full Python suite: `pytest -q --no-header` reports ≥ 692 passed (no
   regression from the current baseline) and skipped count drops by ~1–2
   (depending on how many of step 4 / step 7 land as un-skipped).

## Out of scope (deferred)

- 04.5 / 04.6 narrow-scope unwind — follow-ups #11, #14 (handoff
  `2026_05_18_04complete.md`).
- 05.4 / 05.8 narrow-scope unwind — follow-up #35 + #36 (handoff
  `2026_05_18_c.md`); root cause is naming not source.
- `seeded_v105_fixture` alias / rename — same #35.
- Adding more scenario tests against different v-pair fixtures — future spec
  if needed.
