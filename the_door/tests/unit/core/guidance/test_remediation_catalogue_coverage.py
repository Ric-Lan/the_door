"""Task 05.8 — F3.3 / F3.6 remediation catalogue coverage meta-test.

Pins all four in-scope api_handlers.py error sites against the standard F3
envelope shape:

    {"error": {"code", "message", "source", "remediation": {...}}}

Hand-seeds a minimal v1.0.0 snapshot via the shared ``seed_baseline_snapshot``
helper so the meta-test stays hermetic — no v1.0.5 source tree required.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.ui.api_handlers import APIHandlers
from the_door.core.ui.job_store import JobStore
from the_door.models import FeatureSummary
from tests._seed_helpers import seed_baseline_snapshot


def _make_handlers(project_root: Path) -> APIHandlers:
    return APIHandlers(project_root=project_root, job_store=JobStore())


def _seed_v100_snapshot(project_root: Path):
    """Hand-seed a single v1.0.0 snapshot with one feature, return it."""
    return seed_baseline_snapshot(
        project_root,
        label="v1.0.0",
        features={
            "feat-baseline": FeatureSummary(
                feature_id="feat-baseline",
                label="Baseline feature",
                description="baseline",
                source_node_count=1,
                confidence="high",
                source_nodes=("node-a",),
            )
        },
    )


def _known_vid(project_root: Path) -> str | None:
    """Return the version_id of the seeded v1.0.0 baseline."""
    snap = SnapshotStore(project_root).resolve_baseline("v1.0.0")
    return snap.version_id if snap else None


# ---------------------------------------------------------------------------
# Parametrized meta-test for the three "direct call" in-scope sites.
# The fourth site (handle_diff_versions generic-error path) needs a
# monkeypatch and lives in its own test below.
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_root(tmp_path):
    """Hand-seeded project_root with one v1.0.0 snapshot."""
    _seed_v100_snapshot(tmp_path)
    return tmp_path


_IN_SCOPE_SITES = [
    # (name, lambda taking handlers -> (status, body), expected error code)
    (
        "handle_diff_versions_baseline_unresolvable",
        lambda h: h.handle_diff_versions(baseline_id="nope", current_id="nope2"),
        "snapshot_not_found",
    ),
    (
        "handle_diff_versions_current_unresolvable",
        lambda h: h.handle_diff_versions(
            baseline_id=_known_vid(h._project_root), current_id="nope"
        ),
        "snapshot_not_found",
    ),
    (
        "handle_get_l1_no_data",
        # Empty project_root naturally has no L1 data — call without a
        # version_id so the latest-snapshot path also returns None.
        lambda h: h.handle_get_l1(),
        "no_l1_data",
    ),
]


@pytest.mark.parametrize("name,call,expected_code", _IN_SCOPE_SITES)
def test_in_scope_handler_returns_standard_envelope(
    name, call, expected_code, seeded_root, tmp_path_factory
):
    # `handle_get_l1_no_data` must run against an *empty* project_root so the
    # latest-snapshot fallback returns None. The other two rows need a seeded
    # baseline.
    if expected_code == "no_l1_data":
        root = tmp_path_factory.mktemp("empty_root")
    else:
        root = seeded_root
    handlers = _make_handlers(root)
    status, body = call(handlers)

    assert "error" in body, f"{name} missing top-level error key (body={body!r})"
    err = body["error"]
    assert err["code"] == expected_code, f"{name} code mismatch: {err.get('code')}"
    assert err.get("source"), f"{name} missing source"
    assert err.get("message"), f"{name} missing message"

    assert "remediation" in err, f"{name} missing remediation block"
    rem = err["remediation"]
    assert rem is not None, f"{name} remediation must not be null"
    assert rem.get("code") is not None, f"{name} remediation.code missing"
    assert rem.get("message"), f"{name} remediation.message missing"
    # next_action may be None per envelope contract, but for these sites it
    # MUST be populated with a concrete recovery action.
    assert rem.get("next_action") is not None, f"{name} next_action missing"
    assert "id" in rem["next_action"], f"{name} next_action missing id"


def test_handle_diff_versions_generic_error_uses_envelope(seeded_root, monkeypatch):
    """The 4th in-scope site — generic except path in handle_diff_versions.

    Triggering it requires forcing DiffEngine.compute_l1_diff to raise.
    """
    handlers = _make_handlers(seeded_root)
    vid = _known_vid(seeded_root)
    assert vid is not None, "fixture failure: v1.0.0 snapshot not seeded"

    def _boom(*_a, **_kw):
        raise RuntimeError("simulated diff failure")

    monkeypatch.setattr(
        "the_door.core.diff.diff_engine.DiffEngine.compute_l1_diff",
        _boom,
    )

    status, body = handlers.handle_diff_versions(baseline_id=vid, current_id=vid)
    assert status == 500, body
    err = body["error"]
    assert err["code"] == "diff_error"
    assert err.get("source") == "handle_diff_versions"
    assert err.get("message"), "diff_error missing message"

    rem = err.get("remediation")
    assert rem is not None, "diff_error must carry a remediation block"
    assert rem["code"] == "diff_error"
    assert rem.get("message")
    assert rem.get("next_action") is not None
    assert "id" in rem["next_action"]
