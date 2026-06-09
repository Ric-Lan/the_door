#!/usr/bin/env python3
"""C3 gate (丙案), C2-upgraded: gate mcp__the-door__snapshot_write on the checklist.

PreToolUse hook. Reads the hook event JSON on stdin and the target codebase's
`.the-door/checklist.json`, then verifies (in order; any failure → exit 2 deny
with a stderr message teaching the next step — call the `edge_residue` MCP tool):

  1. existence  — checklist present + parseable, with the `edge_residue` stage
                  stamped (≡ the original C3 artifact-existence check).
  2. currency   — checklist `contract_version` == the current contract version.
  3. coverage   — every source_node the agent is about to write (from
                  l1_features[] ∪ updated_features[]) is ⊆ the node set the
                  edge_residue stage actually covered (validity reading: the
                  agent may not reference un-analyzed / fabricated nodes; this
                  also catches "added nodes but didn't re-run edge_residue").

Deferred (NOT detected here — see spec §2.5): deletion / in-place modification
staleness, mtime/content recompute (a PreToolUse hook must not re-extract AST).

jq-free, stdlib-only (cannot rely on the_door being importable). The field-name
literals below are pinned against `the_door/core/checklist.py` by a drift test.
Fail-open on unparseable stdin / missing codebase_path → exit 0 (never brick a
call it cannot reason about). A MISSING checklist, by contrast, is a deny — that
is the gate's whole job.
"""
import json
import os
import sys

# Pinned against the_door.core.checklist constants (see test_execution_gates.py).
CHECKLIST_FILENAME = "checklist.json"
STAGE_EDGE_RESIDUE = "edge_residue"
FIELD_STAGES = "stages"
FIELD_COVERED_NODES = "covered_nodes"
FIELD_CONTRACT_VERSION = "contract_version"
# Pinned against the_door.models.snapshot.SNAPSHOT_CONTRACT_VERSION.
CURRENT_CONTRACT_VERSION = "1"


def _deny(msg: str) -> int:
    """Write the deny message as UTF-8 bytes (cp950-safe) and return 2."""
    try:
        sys.stderr.buffer.write(msg.encode("utf-8"))
        sys.stderr.buffer.flush()
    except Exception:
        try:
            sys.stderr.write(msg)
        except Exception:
            pass
    return 2


def _source_nodes(tool_input: dict) -> list:
    out = []
    for key in ("l1_features", "updated_features"):
        for feat in tool_input.get(key) or []:
            if isinstance(feat, dict):
                out.extend(feat.get("source_nodes") or [])
    return out


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # cannot parse → don't block
    tool_input = data.get("tool_input") or {}
    codebase_path = tool_input.get("codebase_path") or ""
    if not codebase_path:
        return 0  # nothing to gate on

    artifact = os.path.join(codebase_path, ".the-door", CHECKLIST_FILENAME)
    teach = (
        "請先呼叫 MCP 工具 `edge_residue`（codebase_path=" + codebase_path + "）"
        "產生／更新 " + artifact + " 後再 snapshot_write。\n"
    )

    # 1. existence + parse
    try:
        with open(artifact, "r", encoding="utf-8") as f:
            checklist = json.load(f)
    except Exception:
        return _deny(
            "⛔ snapshot_write 被擋（丙案 C2/C3）：尚無可用的 checklist。\n" + teach
        )
    stages = checklist.get(FIELD_STAGES) or {}
    stage = stages.get(STAGE_EDGE_RESIDUE)
    if not isinstance(stage, dict):
        return _deny(
            "⛔ snapshot_write 被擋（丙案 C2/C3）：checklist 尚未蓋 edge_residue 關。\n" + teach
        )

    # 2. currency
    if checklist.get(FIELD_CONTRACT_VERSION) != CURRENT_CONTRACT_VERSION:
        return _deny(
            "⛔ snapshot_write 被擋（丙案 C2）：checklist contract_version 過期"
            "（需 " + CURRENT_CONTRACT_VERSION + "）。\n" + teach
        )

    # 3. coverage (validity: source_nodes ⊆ covered_nodes)
    covered = set(stage.get(FIELD_COVERED_NODES) or [])
    src = _source_nodes(tool_input)
    missing = [n for n in src if n not in covered]
    if missing:
        sample = ", ".join(missing[:5])
        return _deny(
            "⛔ snapshot_write 被擋（丙案 C2 node-coverage）：以下 source_nodes 不在 "
            "edge_residue 涵蓋範圍（可能程式已變動或 node_id 不符）：" + sample + "\n" + teach
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
