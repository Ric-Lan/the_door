# L1 Feature Detail Fields: Pipeline Fix + Data Backfill

**Date:** 2026-05-27  
**Status:** Approved  
**Scope:** v1.2.2 snapshot backfill + pipeline fix for single-version viewer

---

## Problem

The single-version viewer detail panel shows three fields — 觸發方式 (`trigger_description`), 信心理由 (`confidence_reason`), Source Nodes (`source_nodes`) — that always display「未提供」for v1.2.2 snapshots. Two root causes:

1. **Pipeline gap**: `confidence_reason` and `source_nodes` are not forwarded anywhere in the backend→frontend path. `trigger_description` is forwarded but v1.2.2 snapshot has no value.
2. **Missing snapshot data**: v1.2.2 has `source_node_count: 0` and no values for all three fields.

---

## Design

### Part 1 — Extend `snapshot_patch` MCP Tool

Add an optional `feature_metadata_by_feature` parameter alongside the existing `source_nodes_by_feature`:

**Input schema addition:**
```json
{
  "feature_metadata_by_feature": {
    "<feature_id>": {
      "trigger_description": "string",
      "confidence_reason": "string"
    }
  },
  "source_nodes_by_feature": {
    "<feature_id>": ["node_id", "..."]
  }
}
```

**Behaviour:**
- Both parameters are optional and independent; either can be omitted.
- Only provided fields are written; unprovided fields on existing features are not cleared.
- Operation is in-place: same `version_id`, same `timestamp`, no new snapshot is created.
- Features not found in the target snapshot are reported under `skipped_features` in the response.

**Response:**
```json
{
  "version_id": "...",
  "patched_features": ["feat-a", "feat-b"],
  "skipped_features": []
}
```

**Files to modify:**
- `the_door/src/the_door/core/diff/snapshot_store.py` — add `patch_feature_metadata()` method
- `the_door/src/the_door/mcp/server.py` — expose new parameter on `snapshot_patch` tool
- `the_door/src/the_door/core/ui/api_handlers.py` (if wired through HTTP as well)

---

### Part 2 — Pipeline Fix (Backend → Frontend)

Three files each need two new fields added.

#### `the_door/src/the_door/core/ui/api_handlers.py` — `handle_get_l1`

```python
l1_snapshot_dict = {
    fid: {
        "label": fs.label,
        "confidence": fs.confidence,
        "description": fs.description,
        "trigger_description": fs.trigger_description,
        "confidence_reason": fs.confidence_reason,   # add
        "source_nodes": fs.source_nodes or [],        # add
    }
    for fid, fs in snapshot.l1_snapshot.items()
}
```

#### `the_door/src/the_door/core/ui/graph_view_model.py` — `build_l1_graph_view_model_from_snapshot`

```python
nodes = [
    {
        "id": feature_id,
        "label": summary["label"],
        "confidence": summary["confidence"],
        "description": summary["description"],
        "trigger_description": summary.get("trigger_description"),
        "confidence_reason": summary.get("confidence_reason"),   # add
        "source_nodes": summary.get("source_nodes") or [],       # add
    }
    for feature_id, summary in l1_snapshot.items()
]
```

#### `docs/frontend-local-version-viewer/viewer/js/layers.js` — `loadL1Graph`

```js
state.l1Model = {
  features: (state.l1GraphViewModel.nodes || []).map((n) => ({
    id: n.id,
    label: n.label,
    confidence: n.confidence,
    description: n.description,
    trigger_description: n.trigger_description,
    confidence_reason: n.confidence_reason,   // add
    source_nodes: n.source_nodes || [],       // add
    source: "L1Output.features",
  })),
  stats: { feature_count: (state.l1GraphViewModel.nodes || []).length },
};
```

---

### Part 3 — v1.2.2 Data Backfill (Agent-as-LLM)

Agent produces values for all 13 features using:
- v1.2.2 `label` + `description` as input context
- v1.0.5 `source_nodes` lists as structural reference for `source_nodes`
- Functional reasoning for `trigger_description` and `confidence_reason`

**Per-feature output shape:**
```json
{
  "trigger_description": "使用者在 <situation> 時觸發此功能。（一句話）",
  "confidence_reason": "<說明 high/medium 的理由>",
  "source_nodes": ["ClassName", "function_name", "..."]
}
```

**Execution:**
1. Agent generates data for all 13 features inline.
2. Calls `snapshot_patch` (after Part 1 is implemented) with both `feature_metadata_by_feature` and `source_nodes_by_feature`.
3. Target: v1.2.2 snapshot (`e735e228-1d9e-4e15-8702-fe0d17b00eb0`).

**Source nodes strategy:** v1.2.2 has no source_nodes. Copy the relevant class/function names from v1.0.5's `source_nodes` lists, using short form (no file path prefix). For features added in v1.2.2 (`feat-incremental-analysis`), infer from the description and related v1.0.5 nodes.

---

## Success Criteria

- In the viewer, single-version mode, selecting v1.2.2 and clicking any feature shows actual content in 觸發方式, 信心理由, and Source Nodes — not「未提供」.
- `snapshot_patch` called with `feature_metadata_by_feature` returns `patched_features` listing all 13 feature IDs.
- Existing tests pass; new tests cover: (a) `patch_feature_metadata` in snapshot_store, (b) `handle_get_l1` forwarding new fields, (c) `build_l1_graph_view_model_from_snapshot` including new fields.

---

## Execution Order

1. **Task 01** — Extend `snapshot_patch`: add `patch_feature_metadata()` to `SnapshotStore` + wire into MCP server tool
2. **Task 02** — Fix pipeline: `handle_get_l1` + `build_l1_graph_view_model_from_snapshot` + `layers.js`
3. **Task 03** — Agent generates and writes v1.2.2 backfill data via `snapshot_patch`

Tasks 01 and 02 are independent and can run in parallel. Task 03 depends on Task 01.

---

## Out of Scope

- Backfilling v1.0.0 and v1.0.5 snapshots
- Adding these fields to the diff view detail panel
- Generating L2 or L3 data
