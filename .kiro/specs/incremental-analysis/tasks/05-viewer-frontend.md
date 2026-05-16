# 05 — Viewer Frontend (S3 + viewer-side O2)

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` or `superpowers:executing-plans`.

**Goal:** Repair the two viewer regressions (detail-panel notes/diff-explanation sections after `app.js` refactor + mindmap reading the wrong diff source), add the onboarding card for empty projects, expose `/api/status`, fix the diff API to accept label/tag/SHA references (O2 backend), and make the viewer's version picker send human-readable labels.

**Skill profile:** JavaScript — vanilla JS modules, viewer state machine, sessionStorage, pure data-shaping functions, JS unit testing (vitest/jest). Plus Python — HTTP API handler edits in `api_handlers.py`, including snapshot reference resolution fallback and the new `/api/status` endpoint.

**Dependencies:**
- [00-test-infrastructure.md](00-test-infrastructure.md) — contract + scenario scaffolds
- [02-guidance-engine.md](02-guidance-engine.md) — `StateInspector`, `NextActionSuggester`, `to_json_dict` (needed for `/api/status`)
- [01-core-data.md](01-core-data.md) — `SnapshotStore.list_analyzed_versions` (for picker's data source)

Skip removals owned by this file:

- **Task 05.3** (`/api/status`) → consumer side of `tests/contract/test_systemstate_json_contract.py` (the test goes GREEN when both 02.2 and this task have landed).
- **Task 05.4** (`/api/diff` resolver) → scenario step 6.
- **Task 05.8** (api_handlers.py F3 envelope migration) → viewer consumer side of `tests/contract/test_remediation_envelope_contract.py`.

The viewer JS regression fixes (05.1, 05.2) and the new UI tasks (05.6, 05.7) do not have scenario/contract skips — they verify via JS unit tests in `docs/frontend-local-version-viewer/viewer/tests/`.

**Commit conventions:** `fix(viewer):` for regression repairs, `feat(viewer):` for new UI features, `fix(api):` for `api_handlers.py` backend changes.

## Requirements covered

- [S3 — Viewer Surface](../requirements.md#requirement-s3-viewer-surface) — design §S3
- [O2 — Snapshot Reference Resolution](../requirements.md#requirement-o2-snapshot-reference-resolution) — design §O2 (backend handler portion + frontend picker portion)

## Files touched

**JS (viewer frontend):**
| Path | Action |
|---|---|
| `docs/frontend-local-version-viewer/viewer/js/ui-detail.js` | Modify — delete no-op stubs, wire real imports |
| `docs/frontend-local-version-viewer/viewer/js/ui-next-actions.js` | Create — `appendNextActionsSection` helper |
| `docs/frontend-local-version-viewer/viewer/js/layers.js` | Modify — add `buildMindmapData`, update `switchToMindmap` |
| `docs/frontend-local-version-viewer/viewer/js/onboarding.js` | Create — onboarding card renderer |
| `docs/frontend-local-version-viewer/viewer/js/app.js` | Modify — wire onboarding card init, picker label-first |
| `docs/frontend-local-version-viewer/viewer/tests/ui-detail.test.js` | Modify — RED tests for regression fix |
| `docs/frontend-local-version-viewer/viewer/tests/layers.test.js` | Modify — `buildMindmapData` tests |
| `docs/frontend-local-version-viewer/viewer/tests/onboarding.test.js` | Create |
| `docs/frontend-local-version-viewer/viewer/tests/version_picker.test.js` | Modify or create — label-first test |

**Python (backend handlers):**
| Path | Action |
|---|---|
| `the_door/src/the_door/core/ui/api_handlers.py` | Modify — `/api/diff` fallback, add `/api/status`, include `baseline_label/current_label` in diff response, migrate `no_l1_data` + `diff_error` to F3 envelope |
| `the_door/tests/unit/core/ui/test_api_handlers.py` | Modify — O2 tests + `/api/status` test |
| `the_door/tests/unit/core/guidance/test_remediation_catalogue_coverage.py` | Create — F3 meta-test pinning all 4 in-scope error sites |

---

## Task 05.1 — S3.3: detail-panel regression — wire user-notes + diff-explanation

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-detail.js` (lines 1–6 + 3 call sites)
- Modify: `docs/frontend-local-version-viewer/viewer/tests/ui-detail.test.js`

- [ ] **Step 1: Confirm current state**

Grep `ui-detail.js` for the no-op stubs near lines 5–6 (`_appendDiffExplanationSection` and `_appendUserNotesSection`) and the 3 call sites near lines 131–132, 161, 262–263.

Note: the existing stub argument order differs from the real exports' argument order:
- Stub `_appendDiffExplanationSection(_id, _container)` → real `appendDiffExplanationSection(container, featureId)`
- Stub `_appendUserNotesSection(_mode, _id, _vA, _vB, _container)` → real `appendUserNotesSection(container, mode, versionA, versionB, featureId)`

The actual ui-detail.js exports are `renderDetailPanelL1` (baseline / current modes), `renderDetailPanelL2`, `renderDetailPanelL3`, `renderDetailPanelDiff` (diff mode), and `renderSingleVersionDetailPanel` — there is NO `renderFeature` export. The tests below drive the panel entry points directly.

- [ ] **Step 2: Write the failing tests against the real entry points**

```js
import { describe, it, expect, beforeEach } from "vitest";
import { renderDetailPanelL1, renderDetailPanelDiff } from "../js/ui-detail.js";
import { state } from "../js/state.js";  // adapt to the actual state module path

function _sampleNode(id = "feat-x") {
  return { id, label: "X", description: "d" };
}

describe("ui-detail regression — user notes + diff explanation sections", () => {
  beforeEach(() => {
    document.body.innerHTML = '<div class="detail-content"></div>';
    state.selectedId = "feat-x";
    state.versionA = { snapshot: { l1_snapshot: { "feat-x": _sampleNode() } } };
    state.versionB = null;
    state.mode = "baseline";
  });

  it("renders user-notes-section in baseline mode (single version)", () => {
    renderDetailPanelL1(_sampleNode());
    expect(document.querySelector(".user-notes-section")).not.toBeNull();
  });

  it("renders BOTH user-notes-section AND diff-explanation-section in diff mode", () => {
    state.mode = "diff";
    state.versionB = { snapshot: { l1_snapshot: { "feat-x": _sampleNode() } } };
    renderDetailPanelDiff(_sampleNode());
    expect(document.querySelector(".user-notes-section")).not.toBeNull();
    expect(document.querySelector(".diff-explanation-section")).not.toBeNull();
  });
});
```

(The test helpers may need adjustment to match how state is wired in the actual viewer — grep `import { state }` in the viewer JS source to locate. The architectural assertion is: after wiring, calling the real panel-render entry points populates these two sections in the DOM.)

- [ ] **Step 3: Verify RED**

Run: `cd docs/frontend-local-version-viewer/viewer && npm run test -- ui-detail`

Expected: FAIL — current stubs are no-ops, sections don't render.

- [ ] **Step 4: Delete the no-op stubs**

In `ui-detail.js`, delete lines 5–6 (the two `function _appendXSection() {}` stubs). Replace with:

```js
import { appendUserNotesSection } from "./ui-notes.js";
import { appendDiffExplanationSection } from "./ui-diff-explanation.js";
```

- [ ] **Step 5: Fix the 3 call sites**

At lines 132, 161, 263, replace each stub call with calls to the real exports. The signatures from `ui-notes.js` and `ui-diff-explanation.js` are:

- `appendUserNotesSection(container, mode, versionA, versionB, featureId)` — call in all 3 sites
- `appendDiffExplanationSection(container, featureId)` — call only in diff-mode sites (the calls near lines 161, 263)

Adjust each call to match. Grep `appendUserNotesSection` and `appendDiffExplanationSection` in `ui-notes.js`/`ui-diff-explanation.js` to confirm the argument order.

- [ ] **Step 6: Verify GREEN**

Expected: PASS.

- [ ] **Step 7: Run full JS suite**

```bash
cd docs/frontend-local-version-viewer/viewer && npm run test:coverage
```

Expected: no regressions in existing tests.

- [ ] **Step 8: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-detail.js docs/frontend-local-version-viewer/viewer/tests/ui-detail.test.js
git commit -m "fix(viewer): wire ui-detail.js to real notes + diff-explanation sections (S3)"
```

---

## Task 05.2 — S3.4: `buildMindmapData` pure function in `layers.js`

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/layers.js`
- Modify: `docs/frontend-local-version-viewer/viewer/tests/layers.test.js`

- [ ] **Step 1: Write the failing test for `buildMindmapData` shape (S3-T1)**

```js
import { buildMindmapData } from "../js/layers.js";

describe("buildMindmapData", () => {
  it("returns empty diff when neither updateModel nor versionDiff is present", () => {
    const state = { projectStatus: { project_path: "/x" }, l1GraphViewModel: { nodes: [] } };
    const data = buildMindmapData(state);
    expect(data.diffNodes).toEqual([]);
    expect(data.diffAvailable).toBe(false);
  });

  it("prefers updateModel when diff_available=true", () => {
    const state = {
      projectStatus: { project_path: "/x" },
      l1GraphViewModel: { nodes: [] },
      updateModel: { diff_available: true, changes: [{ id: "a", change_type: "attribute_changed" }] },
      versionDiff: { node_states: { b: "modified" } },
    };
    const data = buildMindmapData(state);
    expect(data.diffNodes).toEqual([{ id: "a", change_type: "attribute_changed" }]);
    expect(data.diffAvailable).toBe(true);
  });

  it("falls back to versionDiff when updateModel is absent", () => {
    const state = {
      projectStatus: { project_path: "/x" },
      l1GraphViewModel: { nodes: [] },
      versionDiff: { node_states: { "feat-a": "attribute_changed", "feat-b": "unchanged" } },
    };
    const data = buildMindmapData(state);
    expect(data.diffNodes).toEqual([{ id: "feat-a", change_type: "attribute_changed" }]);
    expect(data.diffAvailable).toBe(true);
  });

  it("falls back to versionDiff when updateModel.diff_available=false", () => {
    const state = {
      projectStatus: { project_path: "/x" },
      l1GraphViewModel: { nodes: [] },
      updateModel: { diff_available: false },
      versionDiff: { node_states: { "feat-c": "modified" } },
    };
    const data = buildMindmapData(state);
    expect(data.diffNodes).toEqual([{ id: "feat-c", change_type: "modified" }]);
  });
});
```

- [ ] **Step 2: Verify RED**

Expected: FAIL — function not exported.

- [ ] **Step 3: Implement `buildMindmapData`**

Add to `layers.js`:

```js
export function buildMindmapData(state) {
  const projectName =
    (state.projectStatus?.project_path ?? "")
      .split(/[\/\\]/)
      .filter(Boolean)
      .pop() || "專案";
  const nodes = state.l1GraphViewModel?.nodes ?? [];

  let diffNodes = [];
  let diffAvailable = false;

  if (state.updateModel?.diff_available === true) {
    diffNodes = state.updateModel.changes ?? [];
    diffAvailable = true;
  } else if (state.versionDiff?.node_states) {
    diffNodes = Object.entries(state.versionDiff.node_states)
      .filter(([, st]) => st !== "unchanged")
      .map(([id, change_type]) => ({ id, change_type }));
    diffAvailable = diffNodes.length > 0;
  }

  return { project: projectName, nodes, diffNodes, diffAvailable };
}
```

- [ ] **Step 4: Update `switchToMindmap` near line 541–554**

```js
export function switchToMindmap() {
  const data = buildMindmapData(state);
  sessionStorage.setItem("mindmap-data", JSON.stringify(data));
  window.open("./mindmap-popup.html", "mindmap", "width=960,height=720,resizable=yes,scrollbars=yes");
}
```

- [ ] **Step 5: Verify GREEN**

Expected: PASS for all 4 tests.

- [ ] **Step 6: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/layers.js docs/frontend-local-version-viewer/viewer/tests/layers.test.js
git commit -m "fix(viewer): buildMindmapData consumes both diff sources via precedence (S3)"
```

---

## Task 05.3 — S3.6: `/api/status` endpoint

**Files:**
- Modify: `the_door/src/the_door/core/ui/api_handlers.py`
- Modify: `the_door/tests/unit/core/ui/test_api_handlers.py`

- [ ] **Step 1: Write the failing test (S3-T9)**

The existing handlers in `api_handlers.py` are methods on a class (using `self._project_root`) and return `tuple[int, dict]` — confirmed by grep. The new endpoint follows the same shape.

```python
def test_api_status_returns_state_and_next_actions(tmp_path):
    handlers = ApiHandlers(project_root=tmp_path)  # adapt to the real class name
    status, body = handlers.handle_get_status()
    assert status == 200
    assert "state" in body
    assert "next_actions" in body
```

- [ ] **Step 2: Verify RED**

Expected: FAIL — `handle_get_status` not defined on the handler class.

- [ ] **Step 3: Implement the handler**

```python
from the_door.core.guidance.state import StateInspector, to_json_dict as state_to_json
from the_door.core.guidance.suggester import NextActionSuggester
from the_door.core.guidance.actions import to_json_dict as action_to_json


# Inside the existing api_handlers.py handler class:
def handle_get_status(self) -> tuple[int, dict]:
    """GET /api/status — SystemState + next_actions for the project root."""
    state = StateInspector(self._project_root).inspect()
    actions = NextActionSuggester().suggest(state, context="viewer")
    return 200, {
        "state": state_to_json(state),
        "next_actions": [action_to_json(a) for a in actions],
    }
```

Register `/api/status` -> `handle_get_status` in the route table (grep the existing `/api/diff` registration site to locate the dispatch table).

- [ ] **Step 4: Verify GREEN**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/ui/api_handlers.py the_door/tests/unit/core/ui/test_api_handlers.py
git commit -m "feat(api): GET /api/status returns SystemState + next_actions (S3)"
```

---

## Task 05.4 — O2: `/api/diff` accepts label/tag/SHA, returns labels

**Files:**
- Modify: `the_door/src/the_door/core/ui/api_handlers.py` (lines 348–349 + lines 368–378)
- Modify: `the_door/tests/unit/core/ui/test_api_handlers.py`

- [ ] **Step 1: Write the failing tests (O2-T1, T2, T3)**

`handle_diff_versions` is a method on the api_handlers class returning `tuple[int, dict]`. Tests instantiate the handler and assert on the tuple.

```python
def test_diff_api_resolves_label(seeded_v105_fixture):
    handlers = ApiHandlers(project_root=seeded_v105_fixture)
    status, body = handlers.handle_diff_versions(baseline_id="v1.0.0", current_id="v1.0.5")
    assert status == 200
    assert body["baseline_label"] == "v1.0.0"
    assert body["current_label"] == "v1.0.5"


def test_diff_api_resolves_raw_uuid(seeded_v105_fixture):
    v1_vid = _resolve_vid(seeded_v105_fixture, "v1.0.0")
    v5_vid = _resolve_vid(seeded_v105_fixture, "v1.0.5")
    handlers = ApiHandlers(project_root=seeded_v105_fixture)
    status, _ = handlers.handle_diff_versions(baseline_id=v1_vid, current_id=v5_vid)
    assert status == 200


def test_diff_api_unresolvable_returns_remediation_envelope(seeded_v105_fixture):
    handlers = ApiHandlers(project_root=seeded_v105_fixture)
    status, body = handlers.handle_diff_versions(baseline_id="nonexistent", current_id="v1.0.5")
    assert status == 404
    assert body["error"]["code"] == "snapshot_not_found"
    assert body["error"]["remediation"]["code"] == "snapshot_not_found"
    assert body["error"]["remediation"]["next_action"]["id"] == "system_status.show"
```

- [ ] **Step 2: Verify all 3 RED**

Expected: FAIL — current code calls `get_snapshot(label)` directly and returns 404 with bare envelope.

- [ ] **Step 3: Replace the resolver at lines 348–349**

The existing method uses `store.get_snapshot(<ref>)` directly. Replace with a try-`resolve_baseline`-then-fallback chain, and migrate the bare-dict error returns to the F3 envelope.

```python
def _resolve_snapshot(self, store, ref):
    try:
        result = store.resolve_baseline(ref)
        if result is not None:
            return result
    except SnapshotNotFoundError:
        pass
    return store.get_snapshot(ref)


def handle_diff_versions(self, baseline_id: str, current_id: str) -> tuple[int, dict]:
    from the_door.core.diff.diff_engine import DiffEngine
    store = SnapshotStore(self._project_root)
    baseline = self._resolve_snapshot(store, baseline_id)
    if baseline is None:
        rem = Remediation(
            code="snapshot_not_found",
            message=f"baseline {baseline_id!r} 無法解析",
            next_action=NextAction(id="system_status.show", title="查看可用 snapshots",
                                   rationale="r", priority=1,
                                   cli_command=f"the-door status {self._project_root.as_posix()}"),
        )
        return 404, make_error_envelope(
            code="snapshot_not_found", message=rem.message,
            remediation=rem, source="handle_diff_versions",
        )
    current = self._resolve_snapshot(store, current_id)
    if current is None:
        rem = Remediation(
            code="snapshot_not_found",
            message=f"current {current_id!r} 無法解析",
            next_action=NextAction(id="system_status.show", title="查看可用 snapshots",
                                   rationale="r", priority=1,
                                   cli_command=f"the-door status {self._project_root.as_posix()}"),
        )
        return 404, make_error_envelope(
            code="snapshot_not_found", message=rem.message,
            remediation=rem, source="handle_diff_versions",
        )

    # Existing diff computation, but emit labels alongside ids
    engine = DiffEngine()
    diff_result = engine.compute_l1_diff(baseline, current)
    node_states = {nd.node_id: nd.diff_state for nd in diff_result.node_diffs}
    body = {
        "baseline_id": baseline.version_id,
        "baseline_label": baseline.label,
        "current_id": current.version_id,
        "current_label": current.label,
        "summary": {
            "added": diff_result.summary.added_count,
            "removed": diff_result.summary.removed_count,
            "attribute_changed": diff_result.summary.attribute_changed_count,
            "dependency_changed": diff_result.summary.dependency_changed_count,
            "total_changed": diff_result.summary.total_changed_count,
        },
        "node_states": node_states,
    }
    return 200, body
```

- [ ] **Step 4: Verify GREEN**

Expected: PASS.

- [ ] **Step 5: Write the no-diff-with-next-actions test (O2-T4)**

```python
def test_diff_api_with_no_changes_still_returns_next_actions(seeded_v105_fixture):
    vid = _resolve_vid(seeded_v105_fixture, "v1.0.0")
    handlers = ApiHandlers(project_root=seeded_v105_fixture)
    status, body = handlers.handle_diff_versions(baseline_id=vid, current_id=vid)
    assert status == 200
    assert "next_actions" in body
```

- [ ] **Step 6: Implement `next_actions` injection in diff success path**

Just before `return 200, body`:

```python
state = StateInspector(self._project_root).inspect()
actions = NextActionSuggester().suggest(state, context="viewer")
body["next_actions"] = [action_to_json(a) for a in actions]
```

- [ ] **Step 7: Verify GREEN**

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add the_door/src/the_door/core/ui/api_handlers.py the_door/tests/unit/core/ui/test_api_handlers.py
git commit -m "fix(api): /api/diff accepts label/tag/SHA + returns remediation envelope (O2)"
```

---

## Task 05.5 — S3.7 / O2-T5: viewer version picker sends label, not UUID

**Files:**
- Modify: viewer JS picker file (grep `version_id` + render picker)
- Create or modify: `docs/frontend-local-version-viewer/viewer/tests/version_picker.test.js`

- [ ] **Step 1: Locate the picker render point**

```bash
grep -rn "version_id" docs/frontend-local-version-viewer/viewer/js/
```

Identify where the picker emits the chosen `baseline=` / `current=` query string. Document the path here before editing.

- [ ] **Step 2: Write the failing test**

```js
describe("version picker label-first", () => {
  it("emits git_tags[0] when present", () => {
    const snapshot = { version_id: "uuid-xxx", label: "manual-label", git_tags: ["v1.0.0"] };
    expect(pickRef(snapshot)).toBe("v1.0.0");
  });
  it("falls back to label when no git_tags", () => {
    const snapshot = { version_id: "uuid-xxx", label: "manual-label", git_tags: [] };
    expect(pickRef(snapshot)).toBe("manual-label");
  });
  it("falls back to version_id when no label", () => {
    const snapshot = { version_id: "uuid-xxx", label: null, git_tags: [] };
    expect(pickRef(snapshot)).toBe("uuid-xxx");
  });
});
```

- [ ] **Step 3: Verify RED**

Expected: FAIL — current code uses `version_id` directly.

- [ ] **Step 4: Implement `pickRef` + wire**

```js
export function pickRef(snapshot) {
  if (snapshot.git_tags && snapshot.git_tags.length > 0) return snapshot.git_tags[0];
  if (snapshot.label) return snapshot.label;
  return snapshot.version_id;
}
```

Replace the existing picker code's `snapshot.version_id` with `pickRef(snapshot)`.

- [ ] **Step 5: Verify GREEN**

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ docs/frontend-local-version-viewer/viewer/tests/version_picker.test.js
git commit -m "feat(viewer): picker emits git_tags[0]/label before version_id (O2)"
```

---

## Task 05.6 — S3.1: onboarding card for empty projects

**Files:**
- Create: `docs/frontend-local-version-viewer/viewer/js/onboarding.js`
- Modify: `docs/frontend-local-version-viewer/viewer/js/app.js` — fetch `/api/status`, conditionally render
- Create: `docs/frontend-local-version-viewer/viewer/tests/onboarding.test.js`

- [ ] **Step 1: Write the failing test (S3-T10)**

```js
import { renderOnboardingCard } from "../js/onboarding.js";

describe("onboarding card", () => {
  it("renders when state.has_snapshots === false", () => {
    const container = document.createElement("div");
    const payload = {
      state: { project_path: "/x", has_snapshots: false, has_dot_the_door: false },
      next_actions: [{ id: "analyze.first_time", title: "首次分析", cli_command: "the-door analyze /x", priority: 1, rationale: "r" }],
    };
    renderOnboardingCard(container, payload);
    expect(container.querySelector(".onboarding-card")).not.toBeNull();
    expect(container.textContent).toContain("the-door analyze /x");
  });

  it("does NOT render when state.has_snapshots === true", () => {
    const container = document.createElement("div");
    const payload = { state: { has_snapshots: true }, next_actions: [] };
    renderOnboardingCard(container, payload);
    expect(container.querySelector(".onboarding-card")).toBeNull();
  });
});
```

- [ ] **Step 2: Verify RED**

Expected: FAIL — module missing.

- [ ] **Step 3: Implement `renderOnboardingCard`**

```js
export function renderOnboardingCard(container, payload) {
  if (payload.state?.has_snapshots === true) return;
  const card = document.createElement("div");
  card.className = "onboarding-card";
  const heading = document.createElement("h2");
  heading.textContent = "歡迎使用 The Door";
  card.appendChild(heading);
  const top3 = (payload.next_actions ?? []).slice(0, 3);
  const list = document.createElement("ol");
  for (const action of top3) {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${action.title}</strong><pre>${action.cli_command || action.mcp_tool || action.viewer_route}</pre>`;
    list.appendChild(li);
  }
  card.appendChild(list);
  container.appendChild(card);
}
```

- [ ] **Step 4: Verify GREEN**

Expected: PASS.

- [ ] **Step 5: Wire into `app.js`**

In `app.js` at startup, after the initial fetch:

```js
const statusResp = await fetch("/api/status");
const statusPayload = await statusResp.json();
renderOnboardingCard(document.querySelector(".canvas-area"), statusPayload);
```

- [ ] **Step 6: Run full JS suite**

```bash
cd docs/frontend-local-version-viewer/viewer && npm run test:coverage
```

Expected: green.

- [ ] **Step 7: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/onboarding.js docs/frontend-local-version-viewer/viewer/js/app.js docs/frontend-local-version-viewer/viewer/tests/onboarding.test.js
git commit -m "feat(viewer): onboarding card for empty projects (S3)"
```

---

## Task 05.7 — S3.2: detail panel renders "建議的下一步" section

**Files:**
- Create: `docs/frontend-local-version-viewer/viewer/js/ui-next-actions.js`
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-detail.js` (import + 3 call sites)
- Create: `docs/frontend-local-version-viewer/viewer/tests/ui-next-actions.test.js`

- [ ] **Step 1: Write the failing test**

```js
import { appendNextActionsSection } from "../js/ui-next-actions.js";

it("renders 建議的下一步 section when next_actions present", () => {
  const container = document.createElement("div");
  const feature = { next_actions: [{ id: "x", title: "T", cli_command: "ls", priority: 1, rationale: "r" }] };
  appendNextActionsSection(container, feature);
  expect(container.querySelector(".next-actions-section")).not.toBeNull();
  expect(container.textContent).toContain("ls");
});

it("renders nothing when next_actions empty", () => {
  const container = document.createElement("div");
  appendNextActionsSection(container, { next_actions: [] });
  expect(container.querySelector(".next-actions-section")).toBeNull();
});
```

- [ ] **Step 2: Verify RED**

Expected: FAIL — module missing.

- [ ] **Step 3: Implement and wire**

```js
export function appendNextActionsSection(container, feature) {
  const actions = feature?.next_actions ?? [];
  if (actions.length === 0) return;
  const section = document.createElement("section");
  section.className = "next-actions-section";
  // render heading + ordered list (same shape as onboarding card)
  ...
  container.appendChild(section);
}
```

Add an import + a call to `appendNextActionsSection(container, feature)` at each of the 3 panel-render call sites inside `renderDetailPanelL1` / `renderDetailPanelDiff` (the same 3 sites identified in Task 05.1 — lines ~131, ~161, ~262 after the regression fix lands).

- [ ] **Step 4: Verify GREEN**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-next-actions.js docs/frontend-local-version-viewer/viewer/js/ui-detail.js docs/frontend-local-version-viewer/viewer/tests/ui-next-actions.test.js
git commit -m "feat(viewer): detail panel renders 建議的下一步 section from next_actions (S3)"
```

---

## Task 05.8 — F3.3 / F3.6: migrate remaining api_handlers.py error sites + remediation-catalogue meta-test

**Files:**
- Modify: `the_door/src/the_door/core/ui/api_handlers.py` (lines 307–310 `no_l1_data`, lines 380–385 `diff_error`)
- Create: `the_door/tests/unit/core/guidance/test_remediation_catalogue_coverage.py`

Per design §F3 "Existing error code migration" table, four enumerated sites must carry the F3 envelope by end of this spec. Two are covered by Task 05.4 (`snapshot_not_found` baseline + current). The remaining two are migrated here, then a meta-test pins all four against the standard envelope shape.

- [ ] **Step 1: Write the failing meta-test**

```python
import pytest
from the_door.core.ui.api_handlers import ApiHandlers  # adapt to real class name


def _known_vid(project_root):
    """Return the version_id of any seeded baseline (e.g., 'v1.0.0')."""
    from the_door.core.diff.snapshot_store import SnapshotStore
    snap = SnapshotStore(project_root).resolve_baseline("v1.0.0")
    return snap.version_id if snap else None


def _trigger_diff_generic_error(project_root):
    """Call handle_diff_versions in a way that hits the generic except block.
    Pass two valid version_ids but monkey-patch DiffEngine to raise — implement
    in the test using monkeypatch.setattr."""
    raise NotImplementedError("Inline in the test body via monkeypatch — see below.")


_IN_SCOPE_SITES = [
    # (name, lambda taking handlers -> (status, body), expected remediation code)
    ("handle_diff_versions_baseline_unresolvable",
     lambda h: h.handle_diff_versions(baseline_id="nope", current_id="nope2"),
     "snapshot_not_found"),
    ("handle_diff_versions_current_unresolvable",
     lambda h: h.handle_diff_versions(baseline_id=_known_vid(h._project_root), current_id="nope"),
     "snapshot_not_found"),
    ("handle_get_l1_no_data",
     lambda h: h.handle_get_l1(),
     "no_l1_data"),
]


@pytest.mark.parametrize("name,call,expected_code", _IN_SCOPE_SITES)
def test_in_scope_handler_returns_standard_envelope(name, call, expected_code, seeded_v105_fixture):
    handlers = ApiHandlers(project_root=seeded_v105_fixture)
    status, body = call(handlers)
    assert "error" in body, f"{name} missing top-level error key"
    assert body["error"]["code"] == expected_code
    assert "remediation" in body["error"], f"{name} missing remediation block"
    assert body["error"]["remediation"]["code"] is not None
    assert body["error"]["remediation"]["message"]


def test_handle_diff_versions_generic_error_uses_envelope(seeded_v105_fixture, monkeypatch):
    """The 4th in-scope site — covered separately because triggering it requires monkeypatching."""
    handlers = ApiHandlers(project_root=seeded_v105_fixture)
    v1 = _known_vid(seeded_v105_fixture)
    monkeypatch.setattr(
        "the_door.core.diff.diff_engine.DiffEngine.compute_l1_diff",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("simulated"))
    )
    status, body = handlers.handle_diff_versions(baseline_id=v1, current_id=v1)
    assert status == 500
    assert body["error"]["code"] == "diff_error"
    assert body["error"]["remediation"]["code"] == "diff_error"
```

- [ ] **Step 2: Verify RED for the two un-migrated sites**

Expected: FAIL for `handle_get_l1_no_data` and `handle_diff_versions_generic_error` — current code returns the legacy shape without `remediation`. The two `snapshot_not_found` rows pass (covered by 04.4).

- [ ] **Step 3: Migrate `no_l1_data` (api_handlers.py:307-310)**

```python
return 404, make_error_envelope(
    code="no_l1_data",
    message="尚未為這個專案產出 L1 分析",
    remediation=Remediation(
        code="no_l1_data",
        message="尚未為這個專案產出 L1 分析",
        next_action=NextAction(
            id="analyze.first_time", title="首次分析", rationale="r", priority=1,
            cli_command=f"the-door analyze {self._project_root.as_posix()}",
        ),
    ),
    source="handle_get_l1",
)
```

- [ ] **Step 4: Migrate `diff_error` (api_handlers.py:380-385)**

```python
except Exception as e:
    return 500, make_error_envelope(
        code="diff_error",
        message=f"diff 計算失敗: {e}",
        remediation=Remediation(
            code="diff_error", message=str(e),
            next_action=NextAction(
                id="system_status.show", title="查看狀態", rationale="r", priority=1,
                cli_command=f"the-door status {self._project_root.as_posix()}",
            ),
        ),
        source="handle_diff_versions",
    )
```

- [ ] **Step 5: Verify all 4 rows GREEN**

Expected: PASS for all parametrize cases.

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/core/ui/api_handlers.py the_door/tests/unit/core/guidance/test_remediation_catalogue_coverage.py
git commit -m "feat(api): migrate remaining error sites to F3 envelope + coverage meta-test (F3)"
```

---

## Done criteria for 05-viewer-frontend

1. `cd docs/frontend-local-version-viewer/viewer && npm run test:coverage` passes (≥ 580 tests).
2. `pytest the_door/tests/unit/core/ui/test_api_handlers.py -q` passes.
3. Viewer detail panel renders "使用者備註" section in all 3 modes (baseline/current/diff).
4. Viewer detail panel renders "AI 差異說明" section in diff mode.
5. Viewer mindmap popup, when the user has selected two snapshots, displays `Δ` badges on the L1 nodes whose features changed (sourced via `state.versionDiff.node_states`).
6. Viewer onboarding card visible when opening a project with no `.the-door/`.
7. `/api/diff?baseline=v1.0.0&current=v1.0.5` returns 200 with `baseline_label` + `current_label` + `next_actions` fields.
8. `/api/diff?baseline=bad` returns 404 with the F3 envelope.
9. `/api/status` returns `{state, next_actions}`.
10. Version picker emits `git_tags[0] > label > version_id` as the diff query param.
11. All 4 in-scope `api_handlers.py` error sites (`snapshot_not_found` baseline, `snapshot_not_found` current, `no_l1_data`, `diff_error`) return the F3 envelope — proven by `test_remediation_catalogue_coverage.py` meta-test.
