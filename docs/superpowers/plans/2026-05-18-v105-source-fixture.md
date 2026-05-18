# v1.0.5 Source Fixture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `v105_fixture` to provide a full v1.0.0 → v1.0.5 incremental test bed (v1.0.5 source + v1.0.0 source + backfilled baseline AST) so that `scenario/test_v105_incremental_flow.py` step 4 + step 7 can un-skip.

**Architecture:** Single fixture extension in `the_door/tests/conftest.py`. Workflow inside the fixture: (1) copy v1.0.5 project (source + `.the-door/`) into `tmp_path`; (2) stage a `tmp_path/_baseline_v100/` directory with v1.0.0 source + a copy of `tmp_path/.the-door/` (so that `the-door extract --as-version v1.0.0` can resolve the snapshot label and write the gz); (3) invoke the extract CLI in-process via `CliRunner`; (4) copy the resulting `_baseline_v100/.the-door/structures/<vid>.json.gz` back into `tmp_path/.the-door/structures/`. The scenario test is then a pure consumer — no test-side scaffolding.

The CLI's `extract --as-version` command has no `--target` flag (its `codebase_path` positional is used for both source extraction AND `.the-door/` lookup), so we stage the baseline in a sibling directory and copy the persisted structure back. This is invisible to the scenario test.

**Tech Stack:** Python 3.11+, pytest, Click `CliRunner` (in-process CLI invocation), `shutil.copytree`.

---

## Pre-flight verification

Before starting Task 1, confirm:

- v1.0.0 test target source on disk at `C:\Users\Ric\Desktop\test-targets\the-door-v100` (run `dir` / `ls`).
- v1.0.5 test target on disk at `C:\Users\Ric\Desktop\test-targets\the-door-v105` with `.the-door/snapshots/` populated.
- `the-door` package importable (`python -c "from the_door.cli.main import main"` exits 0).

If any precondition fails, fixture will `pytest.skip` cleanly — the plan still applies, but expect the scenario test to skip on this machine.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `the_door/tests/conftest.py` | Modify (extend `v105_fixture`, lines 198–219) | Stage v105 source + v100 source + backfill v1.0.0 persisted AST |
| `the_door/tests/scenario/test_v105_incremental_flow.py` | Modify (lines 56–68 and 134–141) | Un-skip step 4 + step 7; replace skip block with real call |

No new files. No production code changes. No tests added — we are enabling existing scenario steps.

---

## Task 1: RED — un-skip step 4 against the OLD fixture and confirm the failure mode

**Goal:** Prove the spec-identified gap is exactly the gap that fails. Before changing the fixture, switch step 4 from `pytest.skip` to the real `run_incremental_pipeline` call and watch it raise `IncrementalAnalysisError("no_persisted_structure_for_baseline")`. This is the spec's TDD RED step.

**Files:**
- Modify: `the_door/tests/scenario/test_v105_incremental_flow.py:56-68`

- [ ] **Step 1.1: Un-skip step 4 (RED)**

Replace lines 63–68 (`pytest.skip(...)` + 4 comment lines) with the real call. New body of `_step_4_compute_affected_features_isolates_feat_ui_server`:

```python
def _step_4_compute_affected_features_isolates_feat_ui_server(project):
    """Removed by: 03-pipeline-mcp Task 03.1 + Task 03.2 (compute_affected_features +
    incremental_pipeline orchestrator) + v105-source-fixture (this work).
    """
    from the_door.core.pipeline.incremental_pipeline import run_incremental_pipeline
    result = run_incremental_pipeline(codebase_path=project, baseline_ref="v1.0.0")
    affected_ids = {af.feature_id for af in result.diff.affected_features}
    assert "feat-ui-server" in affected_ids, f"expected feat-ui-server in {affected_ids}"
    return result.diff
```

- [ ] **Step 1.2: Run scenario test, expect step 4 to fail with the documented error**

Run: `cd the_door && python -m pytest tests/scenario/test_v105_incremental_flow.py -v --tb=short`

Expected (RED): the test runs through step 1–3, then fails at step 4 with `the_door.core.pipeline.incremental_pipeline.IncrementalAnalysisError: no_persisted_structure_for_baseline` (or equivalent — exact exception type may be a wrapping class; look for the `no_persisted_structure_for_baseline` error code in the traceback).

If the failure mode is different (e.g. missing source, NoneType on `result.diff`, etc.), STOP and re-evaluate: the spec's premise may be incomplete. Note the actual failure, then proceed to Task 2 with that knowledge.

If the test passes here, something else has changed since the spec was written — the gap is already closed. STOP and reassess.

- [ ] **Step 1.3: Do NOT commit RED yet**

Leave the file modified. Task 2's GREEN commit will land both fixture and test changes together (atomic step 4 enablement).

---

## Task 2: GREEN — extend `v105_fixture` with v1.0.0 source + backfill

**Goal:** Replace the existing `v105_fixture` body in `conftest.py` so that `tmp_path` contains v1.0.5 source + `.the-door/` AND `tmp_path/.the-door/structures/<v1.0.0-vid>.json.gz` exists. This is the spec's TDD GREEN step.

**Files:**
- Modify: `the_door/tests/conftest.py:198-219`

- [ ] **Step 2.1: Replace `_V105_*` block and `v105_fixture` body**

At the bottom of `conftest.py`, replace the existing block starting at line 198 (`_V105_DEFAULT = ...`) through line 219 (`return tmp_path`) with:

```python
# ============================================================================
# v105 scenario fixture
# ============================================================================


_V105_DEFAULT = Path(r"C:\Users\Ric\Desktop\test-targets\the-door-v105")
_V105_ENV = "THE_DOOR_V105_FIXTURE"
_V100_DEFAULT = Path(r"C:\Users\Ric\Desktop\test-targets\the-door-v100")
_V100_ENV = "THE_DOOR_V100_FIXTURE"


@pytest.fixture
def v105_fixture(tmp_path):
    """Full E2E fixture for the v1.0.0 → v1.0.5 incremental flow.

    Source resolution (independent env vars per side):
    - v1.0.5: THE_DOOR_V105_FIXTURE | _V105_DEFAULT | skip if missing .the-door/
    - v1.0.0: THE_DOOR_V100_FIXTURE | _V100_DEFAULT | skip if missing dir

    Layout inside tmp_path after setup:
        tmp_path/                       v1.0.5 source + .the-door/
        tmp_path/.the-door/structures/  v1.0.0 persisted AST (backfilled)
        tmp_path/_baseline_v100/        v1.0.0 source (kept for traceability)

    Pre-flight: invokes `the-door extract --as-version v1.0.0 _baseline_v100`
    via Click's CliRunner (in-process) to populate the v1.0.0 persisted AST,
    then copies the resulting structures/ payload into tmp_path/.the-door/.

    Returns tmp_path — the v1.0.5 project root the scenario test operates on.
    """
    from click.testing import CliRunner
    from the_door.cli.main import main

    v105_src = Path(os.environ.get(_V105_ENV, _V105_DEFAULT))
    v100_src = Path(os.environ.get(_V100_ENV, _V100_DEFAULT))
    if not (v105_src / ".the-door").is_dir():
        pytest.skip(f"v105 fixture not available at {v105_src}; set {_V105_ENV}")
    if not v100_src.is_dir():
        pytest.skip(f"v100 source not available at {v100_src}; set {_V100_ENV}")

    # 1. Copy v1.0.5 project tree (source + .the-door/) into tmp_path.
    shutil.copytree(v105_src, tmp_path, dirs_exist_ok=True)

    # 2. Stage v1.0.0 source + a copy of v1.0.5's .the-door/ in _baseline_v100/.
    #    The .the-door/ copy is required because `extract --as-version` resolves
    #    the snapshot label against the codebase_path's snapshot store.
    baseline_dir = tmp_path / "_baseline_v100"
    shutil.copytree(v100_src, baseline_dir)
    shutil.copytree(tmp_path / ".the-door", baseline_dir / ".the-door")

    # 3. Backfill v1.0.0 persisted AST inside _baseline_v100/.the-door/structures/.
    result = CliRunner().invoke(
        main,
        ["extract", "--as-version", "v1.0.0", str(baseline_dir)],
        catch_exceptions=False,
    )
    if result.exit_code != 0:
        pytest.skip(
            f"backfill failed (exit={result.exit_code}): "
            f"{(result.stderr or result.output or '')[:400]}"
        )

    # 4. Copy the produced structures/ payload into tmp_path/.the-door/.
    src_structures = baseline_dir / ".the-door" / "structures"
    dst_structures = tmp_path / ".the-door" / "structures"
    shutil.copytree(src_structures, dst_structures, dirs_exist_ok=True)

    return tmp_path
```

Notes for the implementer:
- `CliRunner().invoke(main, [...])` returns a `Result` object; check `exit_code`. `result.stderr` is available because `main` writes errors there.
- `catch_exceptions=False` makes unexpected exceptions propagate (so we don't silently swallow bugs in extract).
- `shutil.copytree(..., dirs_exist_ok=True)` is required because `tmp_path` already exists (created by pytest) and `tmp_path/.the-door/structures/` may already exist after step 3 if v105 was somehow seeded with structures (defensive — currently it has none).

- [ ] **Step 2.2: Run the scenario test, expect step 4 to PASS**

Run: `cd the_door && python -m pytest tests/scenario/test_v105_incremental_flow.py -v --tb=short`

Expected (GREEN for step 4): step 4's assertion `"feat-ui-server" in affected_ids` passes. Steps 5 and 6 should continue to pass as before. Step 7 still skips (we un-skip it in Task 3).

If step 4 fails with a different assertion error (e.g. `affected_ids = set()` or `affected_ids = {'feat-other'}`), see Risk B in the spec — print the actual set, root-cause: is the diff layer reading the right baseline? Stop and surface to the user with the actual `affected_ids` value.

If step 5 or 6 begins failing (they passed before this change), see Risk C — the fuller chain may surface a latent bug. Apply the 30-LOC scope cutoff: fix-in-place if small, defer otherwise.

- [ ] **Step 2.3: Sanity check — verify the backfill artifact exists**

Add a temporary `print` inside step 4 (before the pipeline call) — `print(list((project / ".the-door" / "structures").glob("*.json.gz")))` — and rerun once. Confirm exactly one `<vid>.json.gz` file is listed. Remove the print after confirmation. (Optional debug aid, not committed.)

- [ ] **Step 2.4: Commit (step 4 enabled)**

```bash
git add the_door/tests/conftest.py the_door/tests/scenario/test_v105_incremental_flow.py
git commit -m "test(scenario): un-skip step 4 with v1.0.0 baseline AST backfill in v105_fixture

v105_fixture now copies both v1.0.5 source and v1.0.0 source into tmp_path,
then invokes \`the-door extract --as-version v1.0.0\` (in-process via CliRunner)
to backfill the persisted baseline AST gz. This is the CLAUDE.md Branch 4
setup, performed inside the fixture so the scenario test stays a pure consumer.

Step 4 of test_v105_incremental_flow now passes:
  affected_ids includes 'feat-ui-server' (asserted with 'in' for conservatism;
  TIGHTEN to '==' once exact membership is verified)."
```

---

## Task 3: GREEN — un-skip step 7 (status CLI Next: block)

**Goal:** Step 7 was blocked on Task 04.2 (status CLI), which has landed. This step is independent of the fixture work but the spec couples it (free win). The scenario test goes from 1 `pytest.skip` to 0.

**Files:**
- Modify: `the_door/tests/scenario/test_v105_incremental_flow.py:134-141`

- [ ] **Step 3.1: Un-skip step 7**

Replace lines 136–141 (`pytest.skip(...)` + 5 comment lines) with the real call. New body of `_step_7_status_cli_emits_next_block`:

```python
def _step_7_status_cli_emits_next_block(project):
    """Removed by: 04-cli-ux Task 04.2 (the-door status command)."""
    from click.testing import CliRunner
    from the_door.cli.main import main
    result = CliRunner(mix_stderr=False).invoke(main, ["status", str(project)])
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "Next:" in result.stderr
```

Notes:
- `mix_stderr=False` keeps stderr separate so we can grep for `Next:` exclusively in stderr (where `next_action_renderer.py:18` writes it).
- Import is `from the_door.cli.main import main` (verified — not `cli`).

- [ ] **Step 3.2: Run scenario test, expect ALL steps to PASS**

Run: `cd the_door && python -m pytest tests/scenario/test_v105_incremental_flow.py -v --tb=short`

Expected: the single test `test_v105_incremental_flow` passes (no skip). Steps 1–7 all execute.

- [ ] **Step 3.3: Commit (step 7 enabled, scenario fully green)**

```bash
git add the_door/tests/scenario/test_v105_incremental_flow.py
git commit -m "test(scenario): un-skip step 7 (status CLI Next: block)

Task 04.2 has landed; status CLI emits 'Next:' on stderr.
test_v105_incremental_flow now has zero pytest.skip() calls and runs
the full v1.0.0 → v1.0.5 chain end-to-end."
```

---

## Task 4: Full suite verification

**Goal:** Confirm the full Python test suite count matches the spec's done criteria (#5) and nothing regressed elsewhere.

- [ ] **Step 4.1: Run full Python suite**

Run: `cd the_door && python -m pytest -q`

Expected baseline (per handoff 2026-05-18 C): 692 passed, 46 skipped.
Expected after this work: 693 passed, 45 skipped (+1 passed, −1 skipped — the scenario test as a whole flips from skipped to passed once both `pytest.skip()` calls are removed).

If counts differ:
- More skips than expected: another test broke. Find it (`pytest --tb=short` or grep last run for `FAIL`). Apply 30-LOC scope cutoff (fix or defer).
- Fewer passes: regression. STOP and investigate.

- [ ] **Step 4.2: No commit — verification only**

The state to commit is the state already on disk after Tasks 2 and 3.

---

## Task 5: TIGHTEN — promote `in` to `==` if the affected set is exact

**Goal:** Per spec TDD step 4 — if `affected_ids == {"feat-ui-server"}` exactly, tighten the assertion. Otherwise leave `in` and document why.

**Files:**
- Modify: `the_door/tests/scenario/test_v105_incremental_flow.py:56-68` (assertion line only)

- [ ] **Step 5.1: Read the actual `affected_ids` value**

Temporarily add `print(affected_ids)` inside step 4 (just before the assert), run the scenario test once, capture the set. Remove the print after.

Run: `cd the_door && python -m pytest tests/scenario/test_v105_incremental_flow.py -v -s`

(`-s` so prints aren't captured.)

- [ ] **Step 5.2: Decide based on actual value**

- If `affected_ids == {"feat-ui-server"}` (exact match): change the assertion to:
  ```python
  assert affected_ids == {"feat-ui-server"}, f"expected exactly feat-ui-server, got {affected_ids}"
  ```
  Continue to step 5.3.

- If `affected_ids` is a superset (e.g. `{"feat-ui-server", "feat-other"}`): keep `in`, but add a comment with the actual set for traceability:
  ```python
  # As of v1.0.0 → v1.0.5: affected = {"feat-ui-server", "feat-other"}.
  # Using 'in' here is intentional — the diff layer is allowed to attribute
  # touches to multiple features when nodes are shared.
  assert "feat-ui-server" in affected_ids, f"expected feat-ui-server in {affected_ids}"
  ```
  Skip to step 5.4 (commit comment change only).

- If `affected_ids` does NOT contain `"feat-ui-server"`: this is Risk B from the spec — STOP, escalate to the user with the actual set and a hypothesis. Do not commit.

- [ ] **Step 5.3: (Exact case) Run the scenario test to verify TIGHTEN passes**

Run: `cd the_door && python -m pytest tests/scenario/test_v105_incremental_flow.py -v`

Expected: PASS.

- [ ] **Step 5.4: Commit (TIGHTEN)**

For exact case:
```bash
git add the_door/tests/scenario/test_v105_incremental_flow.py
git commit -m "test(scenario): TIGHTEN step 4 assertion to exact set

Empirical affected_ids for v1.0.0 → v1.0.5 is exactly {'feat-ui-server'},
so the assertion is promoted from membership to equality."
```

For superset case:
```bash
git add the_door/tests/scenario/test_v105_incremental_flow.py
git commit -m "test(scenario): document actual affected_ids superset for step 4

Diff layer attributes v1.0.0 → v1.0.5 touches to multiple features
(see comment). Membership assert stays."
```

---

## Task 6: Merge to main

**Goal:** Per user preference (continuous run), ff-merge into main now.

- [ ] **Step 6.1: Verify branch ahead of main + clean tree**

Run: `git status && git log --oneline main..HEAD`

Expected:
- Clean working tree
- Branch ahead of main by 2 spec + N impl commits (likely 4–5 total: 2 spec, 1 step-4 enable, 1 step-7 enable, 0 or 1 TIGHTEN)

- [ ] **Step 6.2: Switch to main, ff-merge**

The objective-knuth-e87410 worktree is checked out to its own branch; main is in a different worktree (`C:/Users/Ric/Desktop/the_door`). Do the ff-merge from THAT directory:

```bash
git -C C:/Users/Ric/Desktop/the_door merge --ff-only claude/objective-knuth-e87410
git -C C:/Users/Ric/Desktop/the_door log --oneline -6
```

Expected: ff-merge succeeds; main now points at the same commit as our branch HEAD.

- [ ] **Step 6.3: Do NOT push, do NOT delete branch**

Per user's accumulated preferences (preference #1 from older handoffs): don't push or delete branches without explicit ask. Stop here. Report final state and ask whether to push.

---

## Self-Review

**Spec coverage:**
- §1 (extend v105_fixture in place) → Task 2.1 ✓
- §2 step 4 un-skip → Task 1.1 (RED) + Task 2.2 (GREEN) ✓
- §2 step 7 un-skip → Task 3.1 ✓
- TDD ordering (RED → GREEN → TIGHTEN) → Tasks 1, 2, 3, 5 in order ✓
- Risks A/B/C/D → flagged inline at Task 2.2 and Task 5.2 ✓
- 30-LOC scope cutoff → mentioned in Task 2.2, Task 4.1 ✓
- Done criteria (1)–(5) → covered by Tasks 2.1, 2.2 (step 4), 3.1 (step 7), 4.1 (full suite count) ✓
- Out-of-scope items (04.5/04.6/05.4/05.8 unwind, fixture alias, session cache, v100_fixture) — explicitly NOT in any task. ✓

**Placeholder scan:** No "TBD", "implement later", "handle edge cases" — every step has either complete code or exact commands.

**Type consistency:**
- `AffectedFeature.feature_id` — used in Task 1.1 and Task 5.2, matches the field at `feature_attribution.py:39`.
- `run_incremental_pipeline(codebase_path, baseline_ref)` — single call site in Task 1.1, matches `incremental_pipeline.py:75` signature.
- `CliRunner().invoke(main, [...])` pattern — matches existing usage in `tests/unit/cli/test_extract_as_version.py:57`.
- `_V100_DEFAULT` / `_V100_ENV` — defined and used only inside `v105_fixture` (Task 2.1).
- Spec said `subprocess.run(["the-door", ...])`; plan uses in-process `CliRunner` instead — same E2E principle (real main-program code), but avoids PATH dependency. Documented as a deliberate adjustment in the Architecture section.

**Deliberate divergences from the spec (with reasons):**
1. **In-process `CliRunner` vs `subprocess.run`** — both are "real main-program code" per the E2E principle. CliRunner is in-process, faster, no PATH dependency, and matches existing test patterns (`tests/unit/cli/test_extract_as_version.py`). Documented.
2. **Spec said `the-door extract --as-version v1.0.0 --target <tmp_path> _baseline_v100`** — `--target` flag does not exist. Plan instead copies `tmp_path/.the-door/` into `_baseline_v100/.the-door/` so the extract CLI's `codebase_path` argument can do both source-read and structures-write, then copies the produced `structures/` back to `tmp_path/.the-door/structures/`. Spec § "Verify before committing" explicitly anticipates this adjustment.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-18-v105-source-fixture.md`. User chose continuous-run, so executing inline via `superpowers:executing-plans`. No mid-run checkpoints unless Risk B/C/D fires.
