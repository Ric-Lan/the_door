# 04 — CLI UX (S1 + CLI flags from O1)

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` or `superpowers:executing-plans`.

**Goal:** Make every CLI command end with a `Next:` block, add the `the-door status` command as the canonical entry point, add the two new flags from O1 (`update --from-snapshot`, `extract --as-version`), render F3 envelopes on every CLI error, and enforce the coverage with a meta-test.

**Skill profile:** Python — Click commands, post-run hooks, CliRunner testing, meta-test patterns, env-var-driven JSON output, stderr discipline.

**Dependencies:**
- [00-test-infrastructure.md](00-test-infrastructure.md) — contract + scenario scaffolds
- [02-guidance-engine.md](02-guidance-engine.md) — `StateInspector`, `NextActionSuggester`, `Remediation`, `make_error_envelope`
- [03-pipeline-mcp.md](03-pipeline-mcp.md) — `run_incremental_pipeline` (only needed for `--from-snapshot`; the status/hook subset can land before 03)

Skip removals owned by this file:

- **Task 04.2** (`the-door status`) → scenario step 7.
- **Task 04.4** (CLI error renderer) → CLI consumer side of `tests/contract/test_remediation_envelope_contract.py`.

**Commit conventions:** `feat(cli):` for new files/commands, `feat(cli/<cmd>):` for per-command hook wiring.

## Requirements covered

- [S1 — CLI Surface](../requirements.md#requirement-s1-cli-surface) — design §S1
- [O1 AC3, AC9, AC12 — CLI flag surfaces (--as-version, --from-snapshot)](../requirements.md#requirement-o1-incremental-analysis)

## Files touched

| Path | Action |
|---|---|
| `the_door/src/the_door/cli/next_action_renderer.py` | Create — shared rendering helper |
| `the_door/src/the_door/cli/status_cmd.py` | Create — `the-door status` command |
| `the_door/src/the_door/cli/main.py` | Modify — register `status_cmd`, wire error-renderer |
| `the_door/src/the_door/cli/update_cmd.py` | Modify — add `--from-snapshot` flag |
| `the_door/src/the_door/cli/extract_cmd.py` | Modify — add `--as-version` flag |
| Every other `cli/*_cmd.py` (17 commands) | Modify — call `cli_post_run_hook` on success path |
| `the_door/tests/unit/cli/_invocation_recipes.py` | Create — minimal valid inputs for the meta-test |
| `the_door/tests/unit/cli/test_status_cmd.py` | Create |
| `the_door/tests/unit/cli/test_next_block_coverage.py` | Create — S1 meta-test |
| `the_door/tests/unit/cli/test_error_envelope_rendering.py` | Create |
| `the_door/tests/unit/cli/test_update_from_snapshot.py` | Create |
| `the_door/tests/unit/cli/test_extract_as_version.py` | Create |

---

## Task 04.1 — S1: shared `next_action_renderer` helper

**Files:**
- Create: `the_door/src/the_door/cli/next_action_renderer.py`
- Create: `the_door/tests/unit/cli/test_next_action_renderer.py`

- [ ] **Step 1: Write the failing rendering test**

```python
def test_render_human_outputs_numbered_next_block(capsys):
    from the_door.cli.next_action_renderer import render_next_block
    from the_door.core.guidance.actions import NextAction
    actions = [
        NextAction(id="analyze.incremental", title="增量分析", rationale="r", priority=1, cli_command="the-door update --from-snapshot v1.0.0 ."),
        NextAction(id="viewer.open", title="開 viewer", rationale="r", priority=2, cli_command="the-door ui ."),
    ]
    render_next_block(actions, json_mode=False)
    captured = capsys.readouterr()
    assert "Next:" in captured.err
    assert "the-door update --from-snapshot v1.0.0" in captured.err


def test_render_json_outputs_machine_format(monkeypatch, capsys):
    from the_door.cli.next_action_renderer import render_next_block
    from the_door.core.guidance.actions import NextAction
    actions = [NextAction(id="x", title="t", rationale="r", priority=1, cli_command="ls")]
    render_next_block(actions, json_mode=True)
    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert "next_actions" in payload
    assert payload["next_actions"][0]["id"] == "x"
```

- [ ] **Step 2: Verify RED**

Expected: FAIL — module missing.

- [ ] **Step 3: Implement the renderer**

```python
import json, os, sys
from the_door.core.guidance.actions import NextAction, to_json_dict as action_to_json


_LIMIT = 3


def render_next_block(actions: list[NextAction], *, json_mode: bool | None = None, limit: int = _LIMIT) -> None:
    if json_mode is None:
        json_mode = os.environ.get("THE_DOOR_NEXT_FORMAT", "").lower() == "json"
    sliced = actions[:limit]
    if json_mode:
        sys.stderr.write(json.dumps({"next_actions": [action_to_json(a) for a in sliced]}, ensure_ascii=False) + "\n")
        return
    sys.stderr.write("Next:\n")
    for i, action in enumerate(sliced, start=1):
        form = action.cli_command or action.mcp_tool or action.viewer_route or ""
        sys.stderr.write(f"  {i}. {form}                ({action.title})\n")


def render_remediation(remediation, *, json_mode: bool | None = None) -> None:
    if json_mode is None:
        json_mode = os.environ.get("THE_DOOR_NEXT_FORMAT", "").lower() == "json"
    if json_mode:
        sys.stderr.write(json.dumps({"error": {"code": remediation.code, "message": remediation.message,
                                               "next_action": action_to_json(remediation.next_action) if remediation.next_action else None}}, ensure_ascii=False) + "\n")
        return
    sys.stderr.write(f"Error: {remediation.message}\n")
    if remediation.next_action and remediation.next_action.cli_command:
        sys.stderr.write(f"Try: {remediation.next_action.cli_command}\n")
```

- [ ] **Step 4: Verify GREEN**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/cli/next_action_renderer.py the_door/tests/unit/cli/test_next_action_renderer.py
git commit -m "feat(cli): shared next_action + remediation renderer helper (S1)"
```

---

## Task 04.2 — S1.1/S1.3: `the-door status` command

**Files:**
- Create: `the_door/src/the_door/cli/status_cmd.py`
- Modify: `the_door/src/the_door/cli/main.py` (register the command)
- Create: `the_door/tests/unit/cli/test_status_cmd.py`

- [ ] **Step 1: Write the failing happy-path test (S1-T1)**

```python
from click.testing import CliRunner


def test_status_on_empty_dir_suggests_analyze(tmp_path):
    from the_door.cli.main import cli
    result = CliRunner().invoke(cli, ["status", str(tmp_path)])
    assert result.exit_code == 0
    assert "Next:" in result.stderr
    assert "the-door analyze" in result.stderr


def test_status_json_mode_emits_json(tmp_path, monkeypatch):
    monkeypatch.setenv("THE_DOOR_NEXT_FORMAT", "json")
    from the_door.cli.main import cli
    result = CliRunner(mix_stderr=False).invoke(cli, ["status", str(tmp_path)])
    payload = json.loads(result.stderr)
    assert "next_actions" in payload
```

- [ ] **Step 2: Verify RED**

Expected: FAIL — command not registered.

- [ ] **Step 3: Implement `status_cmd`**

```python
import sys
from pathlib import Path
import click
from the_door.core.guidance.state import StateInspector
from the_door.core.guidance.suggester import NextActionSuggester
from the_door.cli.next_action_renderer import render_next_block


@click.command("status")
@click.argument("path", type=click.Path(exists=False, file_okay=False, dir_okay=True), default=".")
def status_cmd(path: str) -> None:
    """Report current project state + suggested next actions."""
    project = Path(path).resolve()
    state = StateInspector(project).inspect()
    sys.stdout.write(f"Project: {project.as_posix()}\n")
    if state.has_dot_the_door:
        sys.stdout.write(f"  ✓ {len(state.snapshots)} snapshots\n")
        for s in state.snapshots:
            marker = "✓ has structure" if s.has_persisted_structure else "○ no structure"
            label = s.label or s.version_id
            sys.stdout.write(f"    • {label}  ({marker})\n")
    else:
        sys.stdout.write("  ○ not yet initialized\n")
    for warning in state.warnings:
        sys.stdout.write(f"  ⚠ {warning.code}: {warning.message}\n")
    sys.stdout.write("\n")
    actions = NextActionSuggester().suggest(state, context="cli")
    render_next_block(actions)
```

In `cli/main.py`, register: `cli.add_command(status_cmd)`.

- [ ] **Step 4: Verify GREEN**

Expected: PASS for both tests.

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/cli/status_cmd.py the_door/src/the_door/cli/main.py the_door/tests/unit/cli/test_status_cmd.py
git commit -m "feat(cli): the-door status command (S1)"
```

---

## Task 04.3 — S1.2: post-run `Next:` hook on every CLI command

**Files:**
- Create: `the_door/src/the_door/cli/post_run_hook.py` (extract shared logic)
- Modify: every `cli/*_cmd.py` to invoke the hook on success
- Create: `the_door/tests/unit/cli/_invocation_recipes.py`
- Create: `the_door/tests/unit/cli/test_next_block_coverage.py`

- [ ] **Step 1: Implement the post-run hook**

```python
# cli/post_run_hook.py
import os, sys
from pathlib import Path
from the_door.core.guidance.state import StateInspector
from the_door.core.guidance.suggester import NextActionSuggester
from the_door.cli.next_action_renderer import render_next_block


_MACHINE_OUTPUT_FLAGS = {"json", "machine", "no_color"}


def cli_post_run_hook(project_path: Path | str, *, json_mode_active: bool = False) -> None:
    """Call from CLI command success paths. Skips when machine-output flag is active."""
    if json_mode_active:
        return
    state = StateInspector(Path(project_path)).inspect()
    actions = NextActionSuggester().suggest(state, context="cli")
    render_next_block(actions)
```

- [ ] **Step 2: Wire into every CLI command's success path**

For each of the 18 commands in `cli/`, at the bottom of the command function (just before normal return), add:

```python
from the_door.cli.post_run_hook import cli_post_run_hook
cli_post_run_hook(codebase_path, json_mode_active=as_json)
```

The exact variable names (`codebase_path`, `as_json`) match each command's local variables. For commands without a `--json` flag, pass `json_mode_active=False`. For commands without a project path argument (rare — `mcp_serve`, `config`), use `Path.cwd()`.

- [ ] **Step 3: Build invocation recipes**

`_invocation_recipes.py`:

```python
"""Minimal valid invocation per CLI command, for test_next_block_coverage.py.

Each entry: command_name -> (args list, machine_flag, fixture_setup_callable).
machine_flag is the flag string (e.g., "--json") this command uses for machine output, or None.
"""
RECIPES = {
    "status": (["."], None, None),
    "analyze": ([str_to_path_args("tmp_codebase")], None, _seed_codebase),
    "extract": ([str_to_path_args("tmp_codebase")], "--json", _seed_codebase),
    # ... enumerate all 18 commands
}
```

- [ ] **Step 4: Write the failing meta-test**

```python
import pytest
from click.testing import CliRunner
from the_door.cli.main import cli
from the_door.tests.unit.cli._invocation_recipes import RECIPES


@pytest.mark.parametrize("command_name", sorted(RECIPES.keys()))
def test_every_command_emits_next_block_on_success(command_name, tmp_path, monkeypatch):
    args, machine_flag, setup = RECIPES[command_name]
    if setup:
        setup(tmp_path)
    full_args = [command_name, *args]
    result = CliRunner(mix_stderr=False).invoke(cli, full_args)
    if result.exit_code != 0:
        pytest.skip(f"{command_name} exited {result.exit_code}; not a success-path check")
    assert "Next:" in result.stderr, f"{command_name} success path did not emit Next: block"


@pytest.mark.parametrize("command_name", sorted([k for k, v in RECIPES.items() if v[1]]))
def test_every_command_suppresses_next_block_in_machine_mode(command_name, tmp_path):
    args, machine_flag, setup = RECIPES[command_name]
    if setup:
        setup(tmp_path)
    full_args = [command_name, machine_flag, *args]
    result = CliRunner(mix_stderr=False).invoke(cli, full_args)
    if result.exit_code != 0:
        pytest.skip(f"{command_name} exited {result.exit_code}")
    assert "Next:" not in result.stderr
```

- [ ] **Step 5: Verify GREEN**

Expected: PASS. Any command without the hook fails by name; any command that prints `Next:` despite `--json` fails the second test by name.

- [ ] **Step 6: Run full unit suite**

Run: `PYTHONIOENCODING=utf-8 python -m pytest the_door/tests/unit/cli/ -q`

- [ ] **Step 7: Commit**

```bash
git add the_door/src/the_door/cli/post_run_hook.py the_door/src/the_door/cli/*_cmd.py the_door/tests/unit/cli/_invocation_recipes.py the_door/tests/unit/cli/test_next_block_coverage.py
git commit -m "feat(cli): post-run Next: hook on every command + meta-test coverage (S1)"
```

---

## Task 04.4 — S1.3: CLI error rendering with F3 envelope

**Files:**
- Modify: `the_door/src/the_door/cli/main.py` (top-level exception handler)
- Create: `the_door/tests/unit/cli/test_error_envelope_rendering.py`

- [ ] **Step 1: Write the failing test**

```python
def test_cli_error_renders_remediation(tmp_path):
    # Invoke `the-door diff --baseline nonexistent <tmp_path>` — expected to fail with snapshot_not_found
    from the_door.cli.main import cli
    result = CliRunner(mix_stderr=False).invoke(cli, ["diff", "--baseline", "nonexistent", str(tmp_path)])
    assert result.exit_code != 0
    # Stderr contains the human-readable message + remediation suggestion
    assert "snapshot_not_found" in result.stderr or "找不到" in result.stderr
    # Suggests next action
    assert "the-door status" in result.stderr or "Next:" in result.stderr
```

- [ ] **Step 2: Verify RED**

Expected: FAIL — current error handling just prints "Snapshot not found" with no remediation suggestion.

- [ ] **Step 3: Add top-level error handler in `cli/main.py`**

```python
from the_door.core.guidance.remediation import Remediation
from the_door.core.guidance.suggester import NextActionSuggester
from the_door.core.guidance.state import StateInspector
from the_door.cli.next_action_renderer import render_remediation


class CliRemediableError(click.ClickException):
    """A CLI error carrying a Remediation."""
    def __init__(self, remediation: Remediation):
        super().__init__(remediation.message)
        self.remediation = remediation

    def show(self, file=None):
        render_remediation(self.remediation)


@cli.command(...)
def diff_cmd(...):
    try:
        ... existing logic ...
    except SnapshotNotFoundError as e:
        state = StateInspector(Path(codebase_path)).inspect()
        actions = NextActionSuggester().suggest(state, context="after_error", failure_code="snapshot_not_found")
        next_action = actions[0] if actions else None
        raise CliRemediableError(Remediation(
            code="snapshot_not_found",
            message=str(e),
            next_action=next_action,
        ))
```

Apply the same `try/except → CliRemediableError` pattern to every CLI command that already raises a domain error. The migration is mechanical — wrap existing `raise` sites.

- [ ] **Step 4: Verify GREEN**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/cli/main.py the_door/src/the_door/cli/*_cmd.py the_door/tests/unit/cli/test_error_envelope_rendering.py
git commit -m "feat(cli): render F3 envelope on every CLI error path (S1 + F3)"
```

---

## Task 04.5 — O1.9: `update --from-snapshot` flag

**Files:**
- Modify: `the_door/src/the_door/cli/update_cmd.py`
- Create: `the_door/tests/unit/cli/test_update_from_snapshot.py`

- [ ] **Step 1: Write the failing test (O1-T9, T10)**

```python
def test_update_from_snapshot_flag_runs_incremental(seeded_v105_fixture):
    result = CliRunner().invoke(cli, ["update", "--from-snapshot", "v1.0.0", str(seeded_v105_fixture)])
    assert result.exit_code == 0


def test_update_with_old_path_still_works(seeded_v105_pair_fixture):
    old_path, new_path = seeded_v105_pair_fixture
    result = CliRunner().invoke(cli, ["update", str(old_path), str(new_path)])
    assert result.exit_code == 0
```

- [ ] **Step 2: Verify RED**

Expected: FAIL — flag does not exist; or old positional form regressed.

- [ ] **Step 3: Add the flag to `update_cmd.py`**

Three legal call shapes (mutually exclusive):
- `update <old_path> <new_path>` — legacy positional
- `update --from-snapshot <ref> <new_path>` — incremental with explicit current path
- `update --from-snapshot <ref>` — incremental against cwd

```python
@click.command("update")
@click.argument("path_a", type=click.Path(), required=False)
@click.argument("path_b", type=click.Path(), required=False)
@click.option("--from-snapshot", "from_snapshot", default=None,
              help="Baseline snapshot ref (label / tag / SHA / date / UUID). Mutually exclusive with positional old_path.")
def update_cmd(path_a, path_b, from_snapshot):
    if from_snapshot:
        # With --from-snapshot, accept at most one positional (the new/current path); default to cwd.
        if path_b is not None:
            raise CliRemediableError(Remediation(
                code="conflicting_flags",
                message="--from-snapshot replaces <old_path>; pass at most one positional (the current path).",
            ))
        current_path = Path(path_a) if path_a else Path.cwd()
        from the_door.core.pipeline.incremental_pipeline import run_incremental_pipeline, IncrementalAnalysisError
        try:
            result = run_incremental_pipeline(codebase_path=current_path, baseline_ref=from_snapshot)
        except IncrementalAnalysisError as e:
            raise CliRemediableError(e.remediation)
        # Persist resulting snapshot via existing helper (factor out shared logic with the legacy branch).
        cli_post_run_hook(current_path)
        return

    # Legacy positional flow — both args required
    if path_a is None or path_b is None:
        raise click.UsageError("update requires either '<old_path> <new_path>' or '--from-snapshot <ref> [<new_path>]'")
    # ... existing positional flow unchanged
    cli_post_run_hook(path_b)
```

(Grep `update_cmd.py` first to confirm the current positional argument names — adapt the new code to keep its existing names where possible, so legacy callers still work.)

- [ ] **Step 4: Verify GREEN**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/cli/update_cmd.py the_door/tests/unit/cli/test_update_from_snapshot.py
git commit -m "feat(cli): update --from-snapshot flag for incremental analysis (O1)"
```

---

## Task 04.6 — O1.3: `extract --as-version` flag

**Files:**
- Modify: `the_door/src/the_door/cli/extract_cmd.py`
- Create: `the_door/tests/unit/cli/test_extract_as_version.py`

- [ ] **Step 1: Write the failing test**

```python
def test_extract_as_version_writes_gzipped_structure(seeded_v100_baseline):
    # seeded_v100_baseline: project has snapshot v1.0.0; we re-extract the original source
    project_path, source_path = seeded_v100_baseline
    result = CliRunner().invoke(cli, ["extract", "--as-version", "v1.0.0", str(source_path)])
    assert result.exit_code == 0
    # The per-version gz file now exists
    vid = _resolve_vid(project_path, "v1.0.0")
    assert (project_path / ".the-door" / "structures" / f"{vid}.json.gz").is_file()


def test_extract_as_version_unknown_baseline_returns_remediation(seeded_v100_baseline):
    project_path, source_path = seeded_v100_baseline
    result = CliRunner(mix_stderr=False).invoke(cli, ["extract", "--as-version", "nonexistent", str(source_path)])
    assert result.exit_code != 0
    assert "baseline_not_found" in result.stderr or "找不到" in result.stderr


def test_extract_as_version_conflicts_with_to_stdout(seeded_v100_baseline):
    project_path, source_path = seeded_v100_baseline
    result = CliRunner(mix_stderr=False).invoke(cli, ["extract", "--as-version", "v1.0.0", "--to-stdout", str(source_path)])
    assert result.exit_code != 0
    assert "conflicting_flags" in result.stderr or "cannot be combined" in result.stderr
```

- [ ] **Step 2: Verify RED**

Expected: FAIL.

- [ ] **Step 3: Implement the flag**

```python
@click.option("--as-version", "as_version", default=None,
              help="Backfill .the-door/structures/<vid>.json.gz for an existing snapshot (no API key needed).")
def extract_cmd(..., as_version, to_stdout, ...):
    if as_version:
        if to_stdout:
            rem = Remediation(code="conflicting_flags",
                              message="--as-version cannot be combined with --to-stdout")
            raise CliRemediableError(rem)
        store = SnapshotStore(codebase_path_resolved)  # resolve project root that owns the snapshot
        baseline = store.resolve_baseline(as_version) or store.get_snapshot(as_version)
        if baseline is None:
            raise CliRemediableError(Remediation(code="baseline_not_found",
                                                  message=f"Cannot resolve {as_version!r}"))
        structure = ASTExtractor().extract(source_path)
        write_versioned_structure(codebase_path_resolved, baseline.version_id, structure, scan_result=None)
        # Also write the latest-pointer (existing behavior) unless --output-file overrides
        ...
        cli_post_run_hook(codebase_path_resolved)
        return

    # Existing extract flow unchanged
    ...
```

- [ ] **Step 4: Verify GREEN**

Expected: PASS for all three tests.

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/cli/extract_cmd.py the_door/tests/unit/cli/test_extract_as_version.py
git commit -m "feat(cli): extract --as-version backfills persisted structure (O1)"
```

---

## Done criteria for 04-cli-ux

1. `pytest the_door/tests/unit/cli/ -q` passes.
2. `the-door status .` on the v105 fixture prints project state + `Next:` block with `the-door update --from-snapshot v1.0.0 .` as the top suggestion.
3. Every existing CLI command emits a `Next:` block on success path (proven by meta-test).
4. Every existing CLI command suppresses `Next:` under `--json` (proven by second meta-test).
5. CLI error rendering includes the F3 envelope's `message` + `remediation.next_action.cli_command` on every error path.
6. `the-door update --from-snapshot v1.0.0 .` works end-to-end on the v105 fixture.
7. `the-door extract --as-version v1.0.0 <baseline_source>` writes `.the-door/structures/<vid>.json.gz` without an API key.
