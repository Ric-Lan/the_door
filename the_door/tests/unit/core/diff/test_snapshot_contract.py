"""Contract tests for the snapshot persistence schema.

Pins snapshot.schema.json as a living contract bound to _serialize_snapshot:
  - both a maximal (manual, all optional present) and a minimal (commit,
    label=null, no optional fields) snapshot must validate;
  - field-name BIJECTION: every object level's declared schema properties
    equal the keys serialize actually emits (catches phantom + missing fields);
  - serialize/deserialize round-trip equivalence;
  - strict mode (additionalProperties:false) rejects unknown fields.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from the_door.core.diff.snapshot_store import SnapshotStore, _get_snapshot_schema
from the_door.models import (
    BlockSummary, DatabaseFreshness, FeatureSummary, RelationSummary,
    VersionSnapshot, VulnerabilityEntry,
)

_V = jsonschema.Draft202012Validator


def _store(tmp_path) -> SnapshotStore:
    return SnapshotStore(tmp_path, store_root=tmp_path)


def _maximal_snapshot() -> VersionSnapshot:
    """trigger=manual, every optional field populated (union of emittable keys)."""
    return VersionSnapshot(
        version_id="v-max", timestamp="2026-06-03T00:00:00+00:00", trigger="manual",
        l1_snapshot={"feat-x": FeatureSummary(
            feature_id="feat-x", label="L", description="D", source_node_count=2,
            confidence="high", trigger_description="because",
            source_nodes=("A.m", "B.n"), confidence_reason="reason")},
        analyzed_files=["a.py"], commit_hash="abc1234", git_tags=["v1.0.0"],
        label="manual-label",
        l1_5_snapshot={"blk-1": BlockSummary(
            block_id="blk-1", label="BL", responsibility="R", confidence="medium")},
        feature_relations_snapshot=[RelationSummary(
            from_feature="feat-x", to_feature="feat-y", relation="depends_on")],
        vulnerabilities_snapshot=[VulnerabilityEntry(
            cve_id="CVE-1", package="p", version="1", severity="high",
            cvss=7.5, source="osv")],
        vulnerability_db_freshness=DatabaseFreshness(
            timestamp="2026-06-03T00:00:00+00:00", mode="online", stale_warning=None),
        codebase_path=Path("/proj"),
    )


def _minimal_snapshot() -> VersionSnapshot:
    """trigger=commit, label=None, no optional L1 fields, empty collections."""
    return VersionSnapshot(
        version_id="v-min", timestamp="2026-06-03T00:00:00+00:00", trigger="commit",
        l1_snapshot={"feat-x": FeatureSummary(
            feature_id="feat-x", label="L", description="D",
            source_node_count=0, confidence="low")},
        analyzed_files=[], commit_hash=None, git_tags=[], label=None,
        l1_5_snapshot={}, feature_relations_snapshot=[],
        vulnerabilities_snapshot=[], vulnerability_db_freshness=None,
        codebase_path=None,
    )


@pytest.mark.parametrize("builder", [_maximal_snapshot, _minimal_snapshot])
def test_serialized_snapshot_validates_against_schema(tmp_path, builder):
    store = _store(tmp_path)
    data = store._serialize_snapshot(builder())
    jsonschema.validate(data, _get_snapshot_schema(), cls=_V)  # must not raise


def test_schema_serialize_field_bijection(tmp_path):
    """Every object level: declared schema properties == emitted keys (both ways).

    Uses the MAXIMAL snapshot as the union of emittable keys (serialize emits
    some L1 fields conditionally — see spec §7.1)."""
    store = _store(tmp_path)
    data = store._serialize_snapshot(_maximal_snapshot())
    schema = _get_snapshot_schema()

    top = schema["properties"]
    l1 = top["l1_snapshot"]["additionalProperties"]["properties"]
    l15 = top["l1_5_snapshot"]["additionalProperties"]["properties"]
    rel = top["feature_relations_snapshot"]["items"]["properties"]
    vuln = top["vulnerabilities_snapshot"]["items"]["properties"]
    fresh = top["vulnerability_db_freshness"]["properties"]

    assert set(top) == set(data)
    assert set(l1) == set(data["l1_snapshot"]["feat-x"])
    assert set(l15) == set(data["l1_5_snapshot"]["blk-1"])
    assert set(rel) == set(data["feature_relations_snapshot"][0])
    assert set(vuln) == set(data["vulnerabilities_snapshot"][0])
    assert set(fresh) == set(data["vulnerability_db_freshness"])


@pytest.mark.parametrize("builder", [_maximal_snapshot, _minimal_snapshot])
def test_snapshot_round_trip_equivalence(tmp_path, builder):
    store = _store(tmp_path)
    data = store._serialize_snapshot(builder())
    assert store._serialize_snapshot(store._deserialize_snapshot(data)) == data


def test_strict_schema_rejects_unknown_field(tmp_path):
    store = _store(tmp_path)
    data = store._serialize_snapshot(_maximal_snapshot())
    data["junk_field"] = "x"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, _get_snapshot_schema(), cls=_V)
