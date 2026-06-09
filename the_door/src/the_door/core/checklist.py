"""C2 (丙案): execution checklist — single source of truth (write side).

The checklist is a per-codebase artifact recording which control-flow stages
have been completed (and with what node coverage), so the PreToolUse gate can
verify execution order with more than bare artifact existence (see
`.claude/hooks/c3_gate_snapshot_write.py`).

The gate hook is stdlib-only and does NOT import this module (it cannot rely on
the_door being on PYTHONPATH); it duplicates the field names below as string
literals. A drift-pin test (`test_execution_gates.py`) asserts the hook's
literals match these constants.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

CHECKLIST_FILENAME = "checklist.json"

# Stage keys
STAGE_EDGE_RESIDUE = "edge_residue"

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
    covered_nodes: list[str],
    contract_version: str,
) -> dict:
    """Record `stage` as completed in the checklist, then write it back.

    Loads the existing checklist (rebuilds if missing / corrupt), sets the stage
    entry (covered_nodes sorted + deduped, node_count derived, UTC stamp), and
    overwrites contract_version to the latest (single stamping point). Returns
    the written checklist dict.
    """
    data = read_checklist(codebase_path)
    if not isinstance(data, dict):
        data = {}
    stages = data.get(FIELD_STAGES)
    if not isinstance(stages, dict):
        stages = {}
    deduped = sorted(set(covered_nodes))
    stages[stage] = {
        FIELD_STAMPED_AT: datetime.now(timezone.utc).isoformat(),
        FIELD_NODE_COUNT: len(deduped),
        FIELD_COVERED_NODES: deduped,
    }
    data[FIELD_STAGES] = stages
    data[FIELD_CONTRACT_VERSION] = contract_version

    path = checklist_path(codebase_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data
