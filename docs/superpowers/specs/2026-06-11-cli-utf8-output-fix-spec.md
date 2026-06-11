# Spec + Plan — CLI UTF-8 output fix (cp950 crash) — 2026-06-11

> 合併 spec+plan（小刀，照慣例 spike→spec→雙審→TDD→ff-merge）。
> 對應 handoff_2026_06_11 §4 open bug **#1**。

## 1. Problem (verified by spike)

`the-door status` crashes on a Windows cp950 / Big5 terminal (and on any
redirected stdout whose locale encoding is cp950):

```
UnicodeEncodeError: 'cp950' codec can't encode character '✓'
  at status_cmd.py:82  click.echo(f"  ✓ {len(state.snapshots)} snapshots")
```

`status` is the command CLAUDE.md mandates running **first**, so the crash is
high-visibility.

### Spike findings (reproduced, `PYTHONIOENCODING=cp950 python -m the_door ...`)

- The killer is the **symbol** chars that are *not* in cp950/Big5:
  `✓` (U+2713) confirmed crashing. `⚠` (U+26A0) is in the same class.
- Bilingual **Chinese** text does **not** crash (cp950 *is* Big5 → encodable;
  it merely mojibakes when piped to a utf-8 consumer).
- `○` (U+25CB), `•` (U+2022) are also in cp950 → the *uninitialized* status
  path (`○ not yet initialized`) does **not** crash. Only the snapshot-present
  path (`✓ N snapshots`) does.
- `the-door --help` does not crash (exit 0).
- The crash surface is **not** one line: 24 non-ASCII `click.echo` sites across
  8 CLI files. Any of them hits the same wall the moment a non-cp950 symbol is
  emitted. A per-char / per-line edit is the wrong altitude.

### Why the existing guard does nothing

`status_cmd.py:47` does `os.environ.setdefault("PYTHONIOENCODING", "utf-8")`.
An env var is only read at **interpreter start**; mutating `os.environ` mid-run
cannot re-encode an already-configured stdout stream. It is dead code, and the
unit test `test_status_sets_pythonioencoding_utf8` asserts this dead mechanism
(false green — `CliRunner` captures into its own StringIO and never exercises
the cp950 stream, so it could never have caught the real bug).

## 2. Decision

Fix once at the single CLI entry funnel: reconfigure `sys.stdout`/`sys.stderr`
to UTF-8 inside the `main()` click-group callback (runs before every
subcommand). This covers all 24 **subcommand-dispatched** echo sites uniformly,
not just `status`. (Coverage boundary: the group callback fires on subcommand
dispatch — *not* for click's eager options `--help`/`--version` or for usage /
parse errors emitted before dispatch. Those paths are out of scope by
construction; `--help` is verified not to crash today.)

- `encoding="utf-8"` — UTF-8 encodes every char the CLI emits → no crash, and
  correct rendering on the modern (utf-8) terminals Claude Code drives.
- `errors="backslashreplace"` — belt-and-suspenders: if utf-8 ever cannot be
  applied to a stream, degrade rather than crash.
- Guard with `try/except (AttributeError, ValueError)`: streams that are not a
  reconfigurable `TextIOWrapper` (pytest capture, certain redirections) simply
  skip — never raise from the fix itself.

Runtime (callback body), not import-time, so importing `the_door.cli.main`
during pytest collection does not mutate pytest's captured streams.

### Rejected alternatives

- **Per-site `stderr.buffer.write(...encode("utf-8"))`** (the C3-hook pattern):
  correct for a single hook with one message, but 24 sites across 8 files would
  be invasive, lossy (loses click formatting), and easy to regress on the next
  added echo.
- **Module-level reconfigure** in `main.py` / `__main__.py`: fires on import,
  would reconfigure pytest's captured stdout during collection and risks
  cross-test interference. Console-script `the-door` (entry `...main:main`)
  also does not import `__main__.py`, so that path would be missed anyway.
- **Set `PYTHONIOENCODING` earlier**: still an env var; cannot retroactively
  re-encode the live stream. Same dead-mechanism failure.

## 3. Scope

In: `the_door/src/the_door/cli/main.py` (add `_force_utf8_io()` + call),
`the_door/src/the_door/cli/status_cmd.py` (remove the dead `setdefault` line),
tests.

Out: `--help` group-docstring rendering (does not crash); changing any of the
24 message strings; touching the C3/C4 hooks (already cp950-safe via
`stderr.buffer`).

## 4. Plan (TDD)

**Task 1 — failing behavioral test (red). THIS IS THE REGRESSION GATE — not
optional, not `@skip`-able.** It is the only test that exercises the real cp950
stream end-to-end (CliRunner cannot — it captures into its own StringIO). The
Task 3 unit test is strictly secondary (helper-local safety).
Add `tests/unit/cli/test_status_cp950_output.py`:
- Fixture builds a tmp project with **one** snapshot so `status` reaches the `✓`
  line (`status_cmd.py:82`, guarded by `if state.has_dot_the_door`). Use the
  exact production write call modeled on `_write_via_create_snapshot` in
  `tests/unit/core/diff/test_snapshot_store_roundtrip.py`:
  `SnapshotStore(tmp).create_snapshot(l1_snapshot={"feat-a": FeatureSummary(...)},
  feature_relations=[], analyzed_files=[], trigger="manual", label="v1")`.
  (Pin this signature before coding — a fixture that stalls on a wrong arg wastes
  the red signal.)
- `subprocess.run([sys.executable, "-m", "the_door", "status", str(tmp)], env=…)`
  with `PYTHONIOENCODING="cp950"`, `capture_output=True`, and a `cwd`/`PYTHONPATH`
  that makes the **edited source** win over the installed wheel.
- **Assert source provenance** (do not assume PYTHONPATH wins): the test must
  confirm the subprocess loaded `the_door` from `<worktree src>`, not
  site-packages. Cheapest reliable way: run the suite's own resolution — invoke
  via `python -m pytest`'s `pythonpath=["src"]` already in effect, and have the
  subprocess inherit a `PYTHONPATH` that the test asserts is honored (e.g. a
  second tiny subprocess assertion of `the_door.__file__`, or pass `cwd=<src>`
  so a bare `the_door` package dir shadows site-packages). If provenance cannot
  be asserted, the red→green signal is unreliable — block on it.
- Assert `returncode == 0` (currently 1) and that the UTF-8 bytes of `✓`
  (`"✓".encode("utf-8")`) appear in stdout (proves utf-8, not crash).
- cp950 codec is bundled in CPython on every OS → test is platform-independent.

**Task 2 — fix (green).**
- `main.py`: add `_force_utf8_io()` helper (reconfigure both streams, guarded),
  call it at the top of the `main()` group callback.
- `status_cmd.py`: delete the dead `os.environ.setdefault("PYTHONIOENCODING", …)`
  line.

**Task 3 — replace the false-green unit test (secondary guard).**
- In `test_status_cmd.py`, replace `test_status_sets_pythonioencoding_utf8`
  (asserts the dead env mechanism) with a test asserting `_force_utf8_io()` is
  idempotent / does not raise on already-utf-8 or non-reconfigurable streams.
- Note: this unit test does **not** by itself guard the regression — it passes
  even if `_force_utf8_io()` is never wired into `main()`. The wiring is guarded
  by Task 1. Keep the other status tests (they pass unchanged).

**Verify:** full `python -m pytest` green (no regression from removing the env
line); re-run the spike command and confirm exit 0.

## 5. Risks

- Reconfiguring to utf-8 means a *legacy Big5 console* will now mojibake the
  Chinese (previously rendered correctly on a Big5 console). Accepted: the bug
  manifests on redirected/piped stdout (the agent's reading context), where
  utf-8 is the desired encoding; the crash is the real defect, and modern
  terminals are utf-8. No char is lost.
- `reconfigure` flushes pending data; called before any output → safe.
