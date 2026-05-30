# Onboarding Flow Part 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the Claude-Design 「精靈 → Viewer 進場體驗」 prototype into the vanilla viewer: dual-pane wizard shell (rail + content), unified progress UI (phasebar + steplist + file-level feed), back navigation, cross-page door-threshold transition, and matching `ui-modal.js` progress redesign.

**Architecture:** Backend adds `ProgressReporter` abstraction + `progress` payload field so both精靈 `run_analyze_pipeline` and Viewer modal `PipelineOrchestrator.run` emit identical 6-step structure + file-level progress. Frontend wraps existing `wizard-card` in a new `wizard-shell` with left rail (door metaphor + stepper) and right content. Shared progress CSS lives in `styles.css` (consumed by both wizard and main viewer). State machine gains a single `BACK` action with `target` payload and `errorOriginPage` field for correct rail-stage on errors.

**Tech Stack:** Python (`pytest` + `pytest-cov`), JS vanilla ES modules + `vitest` (jsdom), no build step.

**Spec:** `docs/superpowers/specs/2026-05-30-onboarding-flow-part2-design.md` (commit `2bca117`).

---

## Task index

| # | File | Owner area | Test runner |
|---|---|---|---|
| 1a | [task-01a-progress-reporter.md](task-01a-progress-reporter.md) | Backend: `ProgressReporter` abstraction + `ASTExtractor`/`BatchReader` hooks + `handle_post_analyze` adapter | `pytest` |
| 1b | [task-01b-job-progress-payload.md](task-01b-job-progress-payload.md) | Backend: `UpdateJob.progress` field + `handle_get_update_status` payload | `pytest` |
| 2  | [task-02-css-shared-progress.md](task-02-css-shared-progress.md) | `styles.css` shared progress region + tokens A | `vitest` |
| 3  | [task-03-css-shell-rail.md](task-03-css-shell-rail.md) | `wizard.css` shell + rail + tokens B | `vitest` |
| 4  | [task-04-render-page-shell.md](task-04-render-page-shell.md) | `ui-wizard.js` renderPage shell + `errorOriginPage` state | `vitest` |
| 5  | [task-05-mode-note-badge.md](task-05-mode-note-badge.md) | PAGE_ACTION mode-note + PAGE_CONFIRM badge | `vitest` |
| 6  | [task-06-progress-phasebar-feed.md](task-06-progress-phasebar-feed.md) | PROGRESS phasebar + steplist + file feed（建立 `phase-status.js` + 共用 `progress-view.js`） | `vitest` |
| 7  | [task-07-back-transition.md](task-07-back-transition.md) | `BACK` transition + 上一步 buttons | `vitest` |
| 8  | [task-08-modal-consistency.md](task-08-modal-consistency.md) | `ui-modal.js renderPipelineProgress` redesign + remove 6 chips rules | `vitest` |
| 9  | [task-09-threshold-transition.md](task-09-threshold-transition.md) | Cross-page threshold transition + `.onboarding-card` viewerIn | `vitest` |
| 10 | [task-10-release-artefacts.md](task-10-release-artefacts.md) | CHANGELOG v1.4.7 + bilingual README + manual visual audit | manual |

## Dependency graph

```
1a ─────┬──→ 1b ──→ 6 ──┐
        │               ├──→ 8 ──→ 9 ──→ 10
2 ──┬───┴──→ 3 ──→ 4 ──→ 5 ──┤
    │                        └──→ 7 ──┘
    └──→ 8
```

- **1a is critical path root.** Must produce `[步驟 N/6]` message stream + file-level reporter before consumers.
- **1b** unblocks frontend consumers of `progress.*` payload (6, 8).
- **2, 3** independent CSS tasks; can run parallel.
- **4** depends on 3 (DOM uses `.wizard-shell` class from 3).
- **5, 6, 7** depend on 4 (mutate renderPage cases); can run parallel among themselves.
- **6** also depends on 1b (consumes progress payload); produces shared `progress-view.js` module.
- **8** depends on 2 (shared CSS) + 6 (imports `progress-view.js` — `renderProgressInnerHTML` / `appendPlLine`).
- **9** depends on 4 (uses `.wizard-shell.leaving`); runs near end.
- **10** runs last (release artefacts + visual audit).

## Test runner reference

**Python (root: repo root):**
```bash
pytest the_door/tests/unit/core/pipeline/ -v
pytest the_door/tests/unit/core/ui/ -v
pytest the_door/tests/integration/ -v
# Coverage:
pytest --cov=the_door --cov-report=term-missing the_door/tests/
```

**JS (root: `docs/frontend-local-version-viewer/viewer/`):**
```bash
cd docs/frontend-local-version-viewer/viewer
npm test                      # vitest run
npm run test:coverage         # with coverage
```

**Local server smoke test (after frontend tasks):**
```bash
the-door ui "C:\Users\Ric\Desktop\test-targets\the-door-v105" --no-browser --port 8765
```
Open http://localhost:8765/wizard.html — must render dual-pane shell without console errors.

## Coverage requirement

100% line + branch coverage for all new modules and modified functions. Each task's final step runs coverage check; if any uncovered line in modified scope, add a test before commit.

## Spec compliance checklist (verified against each task)

- §0.4 第 1 條「不可造假進度」→ task 1a/1b/6 (no fake data, all from backend payload)
- §0.4 第 2 條「不污染主 Viewer」→ task 2/3 (token scope discipline)
- §0.4 第 3 條「狀態機只在必要例外處動」→ task 4 (errorOriginPage) + task 7 (BACK)
- §0.4 第 4 條「px + 6px 圓角」→ task 2/3 (covered by existing `wizard-css-units.test.js`)
- §3.1 動畫安全紀律 → task 2 grep assertion + task 9 viewerIn rule
- §5.1 entry-point + adapter → task 1a
- §5.1 progress payload → task 1b
- §5.3 phaseStatus 4 種回傳 → task 6
- §7 modal 一致化 → task 8
- §9 自動測試清單 → 各 task 包含
- §11 來源檔對照 → 各 task `Files` 區段引用
