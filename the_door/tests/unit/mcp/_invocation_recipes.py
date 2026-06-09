"""Minimal valid input per MCP tool, for the meta-test in test_response_envelope_coverage.py.

Each entry: ``tool_module_name -> callable(tmp_path) -> (args, fixture_setup)``.

``fixture_setup`` is currently unused by the meta-test (it's reserved for future
extension) — recipes do all setup work in-place before returning ``args``.

This is a TEST FIXTURE FILE, not a production module.

Strategy
--------

The meta-test in ``test_response_envelope_coverage.py`` accepts two outcomes per
tool:

* Returns a success dict containing ``next_actions`` → assertion passes.
* Returns a dict with a top-level ``error`` key → skipped (F3 error-envelope
  tests cover those paths; we only need to verify the meta-property that
  *success* responses carry ``next_actions``).

Where possible we seed minimal valid state so the tool reaches the success path
and we get real coverage. Tools that genuinely need an LLM call (``analyze``,
``estimate``) or two real codebases (``update``) are intentionally fed inputs
that drive them to their well-formed error envelopes — still useful as a smoke
test that they don't crash and that error envelopes are properly shaped.

Production state pollution is prevented by an autouse fixture in the meta-test
file that monkeypatches ``Path.home`` to ``tmp_path`` and stubs out
``ProjectRegistry.register``.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seeded_project(tmp_path: Path) -> Path:
    """Minimal valid ``.the-door/`` structure (no snapshots, no structure)."""
    (tmp_path / ".the-door" / "snapshots").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".the-door" / "structure.json").write_text("{}", encoding="utf-8")
    return tmp_path


def _project_with_snapshot(tmp_path: Path, *, label: str = "v1.0.0"):
    """Seed ``tmp_path`` with a single baseline snapshot + persisted structure.

    Returns the created ``VersionSnapshot``. Mirrors the helper used in
    tests/unit/mcp/test_analyze_changes_tool.py but kept local.
    """
    from the_door.core.diff.snapshot_store import SnapshotStore
    from the_door.models import FeatureSummary

    _seeded_project(tmp_path)

    store = SnapshotStore(tmp_path)

    nodes = [("file.py::a", 1), ("file.py::b", 2)]
    source_nodes = tuple(node_id for node_id, _ in nodes)
    l1_snapshot: dict[str, FeatureSummary] = {
        "feat-seeded": FeatureSummary(
            feature_id="feat-seeded",
            label="seeded feature",
            description="baseline feature owning the seeded nodes",
            source_node_count=len(source_nodes),
            confidence="high",
            source_nodes=source_nodes,
        )
    }
    snapshot = store.create_snapshot(
        l1_snapshot=l1_snapshot,
        feature_relations=[],
        analyzed_files=["file.py"],
        trigger="manual",
        label=label,
    )

    # Persist a compressed structure so analyze_changes can hit the success path
    struct_dir = tmp_path / ".the-door" / "structures"
    struct_dir.mkdir(parents=True, exist_ok=True)
    struct_path = struct_dir / f"{snapshot.version_id}.json.gz"
    structure_dict = {
        "files": [],
        "nodes": [
            {
                "node_id": node_id,
                "type": "function",
                "name": node_id.split("::", 1)[-1],
                "file": node_id.split("::", 1)[0],
                "language": "python",
                "decorators": [],
                "parameters": [f"p{i}" for i in range(param_count)],
                "return_type": None,
                "docstring": None,
                "comments": [],
            }
            for node_id, param_count in nodes
        ],
        "edges": [],
        "topology": [],
    }
    with gzip.open(struct_path, "wt", encoding="utf-8") as f:
        json.dump(structure_dict, f)

    return snapshot


def _empty_codebase(tmp_path: Path) -> Path:
    """An empty directory that is a valid filesystem path (no .the-door/)."""
    sub = tmp_path / "src"
    sub.mkdir(parents=True, exist_ok=True)
    return sub


# ---------------------------------------------------------------------------
# Recipe table
# ---------------------------------------------------------------------------

Recipe = Callable[[Path], tuple[dict[str, Any], Any]]


# ---- analyze: needs an LLM provider; we accept the error/exception path. ----
# ---- analyze_changes: needs baseline snapshot + persisted structure. -------
def _analyze_changes_recipe(tmp_path: Path) -> tuple[dict[str, Any], None]:
    # No baseline → tool returns error envelope (handled gracefully).
    # We do NOT seed a baseline because successfully running the pipeline
    # requires monkeypatching ASTExtractor.extract — not appropriate from a
    # static recipe. Error envelope is acceptable here.
    project = _seeded_project(tmp_path)
    return (
        {"codebase_path": str(project), "baseline": "nonexistent-baseline"},
        None,
    )


# ---- diff: needs current snapshot; without one → returns error. ------------
def _diff_recipe(tmp_path: Path) -> tuple[dict[str, Any], None]:
    project = _seeded_project(tmp_path)
    return (
        {"codebase_path": str(project), "baseline": "v1.0.0"},
        None,
    )


# ---- doubt_list: empty doubts is valid; should succeed. --------------------
def _doubt_list_recipe(tmp_path: Path) -> tuple[dict[str, Any], None]:
    project = _seeded_project(tmp_path)
    return ({"codebase_path": str(project)}, None)


# ---- doubt_transition: bogus doubt_id → tool returns error dict. -----------
def _doubt_transition_recipe(tmp_path: Path) -> tuple[dict[str, Any], None]:
    project = _seeded_project(tmp_path)
    return (
        {
            "doubt_id": "nonexistent",
            "target_state": "investigating",
            "actor": "tester",
            "assignee": "alice",
            "codebase_path": str(project),
        },
        None,
    )


# ---- history: missing narrative.jsonl → success with empty records. --------
def _history_recipe(tmp_path: Path) -> tuple[dict[str, Any], None]:
    project = _seeded_project(tmp_path)
    return ({"codebase_path": str(project)}, None)


# ---- project_list: succeeds regardless. ------------------------------------
def _project_list_recipe(tmp_path: Path) -> tuple[dict[str, Any], None]:
    return ({}, None)


# ---- render: minimal valid L1 input → success. -----------------------------
def _render_recipe(tmp_path: Path) -> tuple[dict[str, Any], None]:
    project = _seeded_project(tmp_path)
    return (
        {
            "output_json": {
                "l1": {
                    "summary": "test",
                    "features": [],
                    "feature_relations": [],
                }
            },
            "codebase_path": str(project),
        },
        None,
    )


# ---- scan: needs a codebase. Empty codebase → may scan with no deps. -------
def _scan_recipe(tmp_path: Path) -> tuple[dict[str, Any], None]:
    project = _seeded_project(tmp_path)
    return ({"codebase_path": str(project), "offline": True}, None)


# ---- scope_create: writes a scope file → success. --------------------------
def _scope_create_recipe(tmp_path: Path) -> tuple[dict[str, Any], None]:
    project = _seeded_project(tmp_path)
    return (
        {"scope_name": "test-scope", "codebase_path": str(project)},
        None,
    )


# ---- scope_verify: no snapshot → tool returns error dict. ------------------
def _scope_verify_recipe(tmp_path: Path) -> tuple[dict[str, Any], None]:
    project = _seeded_project(tmp_path)
    # Create an empty scope file so file-parse passes before the snapshot check.
    scopes_dir = project / ".the-door" / "scopes"
    scopes_dir.mkdir(parents=True, exist_ok=True)
    scope_file = scopes_dir / "test.json"
    scope_file.write_text(
        json.dumps({"scope_name": "test", "features": []}),
        encoding="utf-8",
    )
    return (
        {"scope_file": str(scope_file), "codebase_path": str(project)},
        None,
    )


# ---- snapshot_create: no prior snapshots → returns error envelope. ---------
def _snapshot_create_recipe(tmp_path: Path) -> tuple[dict[str, Any], None]:
    project = _seeded_project(tmp_path)
    return ({"codebase_path": str(project)}, None)


# ---- snapshot_list: empty snapshot dir → success with empty list. ----------
def _snapshot_list_recipe(tmp_path: Path) -> tuple[dict[str, Any], None]:
    project = _seeded_project(tmp_path)
    return ({"codebase_path": str(project)}, None)


# ---- snapshot_prune: no snapshots → error envelope. ------------------------
def _snapshot_prune_recipe(tmp_path: Path) -> tuple[dict[str, Any], None]:
    project = _seeded_project(tmp_path)
    return ({"codebase_path": str(project), "dry_run": True}, None)


# ---- snapshot_write: minimal valid features → success. ---------------------
def _snapshot_write_recipe(tmp_path: Path) -> tuple[dict[str, Any], None]:
    project = _seeded_project(tmp_path)
    return (
        {
            "codebase_path": str(project),
            "l1_features": [
                {
                    "feature_id": "feat-test",
                    "label": "Test Feature",
                    "description": "A seeded feature for meta-test coverage.",
                    "confidence": "high",
                    "source_nodes": ["file.py::a"],
                }
            ],
            "relations": [],
        },
        None,
    )


# ---- system_status: succeeds with project_path. ----------------------------
def _system_status_recipe(tmp_path: Path) -> tuple[dict[str, Any], None]:
    project = _seeded_project(tmp_path)
    return ({"project_path": str(project)}, None)


# ---- timeline: no snapshots → returns error envelope. ----------------------
def _timeline_recipe(tmp_path: Path) -> tuple[dict[str, Any], None]:
    project = _seeded_project(tmp_path)
    return ({"codebase_path": str(project)}, None)


RECIPES: dict[str, Recipe] = {
    "analyze_changes_tool": _analyze_changes_recipe,
    "diff_tool": _diff_recipe,
    "doubt_list_tool": _doubt_list_recipe,
    "doubt_transition_tool": _doubt_transition_recipe,
    "history_tool": _history_recipe,
    "project_list_tool": _project_list_recipe,
    "render_tool": _render_recipe,
    "scan_tool": _scan_recipe,
    "scope_create_tool": _scope_create_recipe,
    "scope_verify_tool": _scope_verify_recipe,
    "snapshot_create_tool": _snapshot_create_recipe,
    "snapshot_list_tool": _snapshot_list_recipe,
    "snapshot_prune_tool": _snapshot_prune_recipe,
    "snapshot_write_tool": _snapshot_write_recipe,
    "system_status_tool": _system_status_recipe,
    "timeline_tool": _timeline_recipe,
}


# Tools known to RAISE rather than return an error dict when given minimal
# inputs. The meta-test consults this set to skip cleanly rather than failing
# on uncaught exceptions. Keep this list minimal — only add a tool here after
# confirming the failure mode is genuinely environment-bound (e.g. needs a real
# LLM provider) and cannot be reasonably stubbed in a static recipe.
RAISING_TOOLS: frozenset[str] = frozenset()
