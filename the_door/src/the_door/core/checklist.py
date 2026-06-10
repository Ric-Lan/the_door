"""C2 (丙案): execution checklist — single source of truth (write side).

The checklist is a per-codebase artifact recording which control-flow stages
have been completed (and with what node coverage), so the PreToolUse gate can
verify execution order with more than bare artifact existence (see
`.claude/hooks/c3_gate_snapshot_write.py`).

The gate hook is stdlib-only and does NOT import this module (it cannot rely on
the_door being on PYTHONPATH); it duplicates the field names below as string
literals. A drift-pin test (`test_execution_gates.py`) asserts the hook's
literals match these constants.

This module is the write side (`stamp_stage`) plus a read-side projection
(`read_ledger`) used by C6 to report the execution chain back to the user.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

CHECKLIST_FILENAME = "checklist.json"

# Stage keys
STAGE_EDGE_RESIDUE = "edge_residue"
STAGE_SNAPSHOT_WRITE = "snapshot_write"

# Canonical chain order for ledger projection; unknown stages sort after these.
STAGE_ORDER = (STAGE_EDGE_RESIDUE, STAGE_SNAPSHOT_WRITE)

# Schema field names (pinned against the gate hook by test).
FIELD_CONTRACT_VERSION = "contract_version"
FIELD_STAGES = "stages"
FIELD_COVERED_NODES = "covered_nodes"
FIELD_NODE_COUNT = "node_count"
FIELD_STAMPED_AT = "stamped_at"


def checklist_path(codebase_path: str | Path) -> Path:
    return Path(codebase_path) / ".the-door" / CHECKLIST_FILENAME


def read_checklist(codebase_path: str | Path) -> dict | None:
    """Return the parsed checklist, or None if missing / unparseable (fail-soft)."""
    path = checklist_path(codebase_path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def stamp_stage(
    codebase_path: str | Path,
    stage: str,
    *,
    contract_version: str,
    covered_nodes: list[str] | None = None,
    details: dict | None = None,
) -> dict:
    """Record `stage` as completed in the checklist, then write it back.

    Loads the existing checklist (rebuilds if missing / corrupt), sets the stage
    entry, and overwrites contract_version to the latest (single stamping point).
    Returns the written checklist dict.

    Stage entry always carries `stamped_at` (UTC). Optionally:

    * `covered_nodes` — when given, writes `covered_nodes` (sorted + deduped) and
      derived `node_count`. The node-coverage gate (C3) reads these for the
      edge_residue stage. Omit for stages with no node-coverage semantics (e.g.
      snapshot_write).
    * `details` — stage-specific facts merged into the entry (e.g. snapshot_write
      records version_id / feature_count). Keys MUST NOT collide with the
      reserved field names (`stage`/`stamped_at`/`node_count`/`covered_nodes`).
    """
    data = read_checklist(codebase_path)
    if not isinstance(data, dict):
        data = {}
    stages = data.get(FIELD_STAGES)
    if not isinstance(stages, dict):
        stages = {}
    entry = {FIELD_STAMPED_AT: datetime.now(timezone.utc).isoformat()}
    if covered_nodes is not None:
        deduped = sorted(set(covered_nodes))
        entry[FIELD_NODE_COUNT] = len(deduped)
        entry[FIELD_COVERED_NODES] = deduped
    if details:
        entry.update(details)
    stages[stage] = entry
    data[FIELD_STAGES] = stages
    data[FIELD_CONTRACT_VERSION] = contract_version

    path = checklist_path(codebase_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def read_ledger(codebase_path: str | Path) -> list[dict]:
    """Project the checklist's stages into an ordered, summarized ledger (C6).

    Each entry: ``{"stage": <name>, "stamped_at": ..., + node_count / details}``.
    The bulky ``covered_nodes`` array is deliberately stripped (node_count is
    kept) so embedding the ledger in a tool response can't be swamped by
    thousands of node ids.

    Known stages (STAGE_ORDER) come first in canonical order; unknown stages
    follow in alphabetical order (forward-compatible with future gate stages).
    Missing / corrupt checklist → [] (fail-soft).
    """
    data = read_checklist(codebase_path)
    if not isinstance(data, dict):
        return []
    stages = data.get(FIELD_STAGES)
    if not isinstance(stages, dict):
        return []
    known = [s for s in STAGE_ORDER if s in stages]
    rest = sorted(s for s in stages if s not in STAGE_ORDER)
    ledger = []
    for name in known + rest:
        entry = dict(stages[name])
        entry.pop(FIELD_COVERED_NODES, None)  # non-destructive; snapshot_write has none
        entry["stage"] = name
        ledger.append(entry)
    return ledger
