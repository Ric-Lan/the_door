"""Round-trip tests for the snapshot store's optional FeatureSummary fields.

``trigger_description`` and ``source_nodes`` were added to FeatureSummary to
support viewer drill-down. These tests pin the on-disk representation
(absent vs present, list serialization) so future refactors don't silently
drop the data again — which is the exact bug that surfaced in the viewer's
L1 detail panel showing an empty 觸發方式 section.
"""
from __future__ import annotations

import json

import pytest

from the_door.core.diff.snapshot_store import SnapshotEntry, SnapshotStore
from the_door.core.extraction.structure_serializer import write_versioned_structure
from the_door.models import (
    FeatureSummary,
    RelationSummary,
    StructureJSON,
    VersionSnapshot,
)


@pytest.fixture
def store(tmp_path):
    return SnapshotStore(tmp_path)


def _write_via_create_snapshot(store, l1_snapshot, **kwargs):
    """Use create_snapshot (the production write path) and return the new
    snapshot's version_id so callers can reload via get_snapshot."""
    snap = store.create_snapshot(
        l1_snapshot=l1_snapshot,
        feature_relations=[],
        analyzed_files=[],
        trigger="manual",
        **kwargs,
    )
    return snap.version_id


class TestFeatureSummaryOnDiskShape:
    def test_minimal_summary_omits_optional_keys(self, store, tmp_path):
        fs = FeatureSummary(
            feature_id="feat-a",
            label="Auth",
            description="...",
            source_node_count=3,
            confidence="high",
        )
        vid = _write_via_create_snapshot(store, {"feat-a": fs}, label="min")

        snap_file = tmp_path / ".the-door" / "snapshots" / f"{vid}.json"
        raw = json.loads(snap_file.read_text(encoding="utf-8"))
        entry = raw["l1_snapshot"]["feat-a"]
        assert "trigger_description" not in entry, \
            "absent trigger_description must be omitted, not serialized as null"
        assert "source_nodes" not in entry, \
            "empty source_nodes must be omitted to keep the on-disk file small"

    def test_populated_summary_round_trips(self, store):
        fs = FeatureSummary(
            feature_id="feat-a",
            label="Auth",
            description="Authentication flow",
            source_node_count=2,
            confidence="high",
            trigger_description="User submits login form",
            source_nodes=("src/auth.py::login", "src/auth.py::Session"),
        )
        vid = _write_via_create_snapshot(store, {"feat-a": fs}, label="full")

        loaded = store.get_snapshot(vid)
        assert loaded is not None
        round_fs = loaded.l1_snapshot["feat-a"]
        assert round_fs.trigger_description == "User submits login form"
        assert round_fs.source_nodes == (
            "src/auth.py::login", "src/auth.py::Session",
        )
        # tuple, not list — preserves frozen-dataclass hashability
        assert isinstance(round_fs.source_nodes, tuple)

    def test_legacy_snapshot_without_new_fields_still_loads(self, tmp_path):
        """A snapshot file produced by an older version of the codebase
        (no trigger_description, no source_nodes keys) must deserialize
        with trigger_description=None and source_nodes=()."""
        snapdir = tmp_path / ".the-door" / "snapshots"
        snapdir.mkdir(parents=True)
        legacy = {
            "version_id": "v-legacy",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "trigger": "manual",
            "commit_hash": None,
            "git_tags": [],
            "label": "legacy",
            "l1_snapshot": {
                "feat-a": {
                    "label": "Auth",
                    "description": "...",
                    "source_node_count": 3,
                    "confidence": "high",
                }
            },
            "l1_5_snapshot": {},
            "feature_relations_snapshot": [],
            "vulnerabilities_snapshot": [],
            "analyzed_files": [],
        }
        (snapdir / "v-legacy.json").write_text(json.dumps(legacy), encoding="utf-8")

        store = SnapshotStore(tmp_path)
        loaded = store.get_snapshot("v-legacy")
        assert loaded is not None
        fs = loaded.l1_snapshot["feat-a"]
        assert fs.trigger_description is None
        assert fs.source_nodes == ()

    def test_create_snapshot_overrides_caller_source_node_count(self, store, tmp_path):
        fs = FeatureSummary(
            feature_id="feat-x",
            label="x",
            description="d",
            confidence="high",
            source_node_count=99,
            source_nodes=("a", "b"),
        )
        snapshot = store.create_snapshot(
            l1_snapshot={"feat-x": fs},
            feature_relations=[],
            analyzed_files=[],
        )
        on_disk = json.loads((tmp_path / ".the-door" / "snapshots" / f"{snapshot.version_id}.json").read_text())
        assert on_disk["l1_snapshot"]["feat-x"]["source_node_count"] == 2


class TestContractVersionStamp:
    """S7 P1/P2/P7：snapshot 出生契約戳（contract_version）持久化。

    戳＝出生事實（與 commit_hash/timestamp 同類），在 create_snapshot 蓋戳、
    serde round-trip 保真；舊快照（無 contract_version 鍵）deserialize→None＝
    unknown（O3），schema additive 不拒。
    """

    def test_create_snapshot_stamps_current_contract_version(self, store):
        """P1：新建快照蓋當前契約戳。"""
        from the_door.models.snapshot import SNAPSHOT_CONTRACT_VERSION

        snap = store.create_snapshot(
            l1_snapshot={}, feature_relations=[], analyzed_files=[],
        )
        assert snap.contract_version == SNAPSHOT_CONTRACT_VERSION

    def test_contract_version_round_trips(self, store):
        """P2：戳寫入磁碟並讀回保真。"""
        from the_door.models.snapshot import SNAPSHOT_CONTRACT_VERSION

        vid = _write_via_create_snapshot(store, {}, label="stamped")
        loaded = store.get_snapshot(vid)
        assert loaded is not None
        assert loaded.contract_version == SNAPSHOT_CONTRACT_VERSION

    def test_contract_version_serialized_on_disk(self, store, tmp_path):
        """P2：on-disk JSON 帶 contract_version 鍵。"""
        from the_door.models.snapshot import SNAPSHOT_CONTRACT_VERSION

        vid = _write_via_create_snapshot(store, {}, label="stamped")
        snap_file = tmp_path / ".the-door" / "snapshots" / f"{vid}.json"
        raw = json.loads(snap_file.read_text(encoding="utf-8"))
        assert raw["contract_version"] == SNAPSHOT_CONTRACT_VERSION

    def test_legacy_snapshot_without_contract_version_loads_as_none(self, tmp_path):
        """P7/O3：舊快照（無 contract_version 鍵）→ None、schema validate 通過、不炸。"""
        snapdir = tmp_path / ".the-door" / "snapshots"
        snapdir.mkdir(parents=True)
        legacy = {
            "version_id": "v-prestamp",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "trigger": "manual",
            "commit_hash": None,
            "git_tags": [],
            "label": "prestamp",
            "l1_snapshot": {},
            "l1_5_snapshot": {},
            "feature_relations_snapshot": [],
            "vulnerabilities_snapshot": [],
            "analyzed_files": [],
        }
        (snapdir / "v-prestamp.json").write_text(json.dumps(legacy), encoding="utf-8")

        store = SnapshotStore(tmp_path)
        loaded = store.get_snapshot("v-prestamp")
        assert loaded is not None
        assert loaded.contract_version is None

    def test_stamped_snapshot_passes_schema_on_write(self, store):
        """P7：帶 contract_version 的新快照經 _write_snapshot fail-closed schema 校驗通過。"""
        # create_snapshot 內部呼 _write_snapshot（schema fail-closed）；不拋即通過。
        snap = store.create_snapshot(
            l1_snapshot={}, feature_relations=[], analyzed_files=[], trigger="manual", label="x",
        )
        assert snap.contract_version is not None


class TestProjectSummaryRoundTrip:
    """project_summary：snapshot 級非技術簡介（agent-as-LLM 綜合 L1 產出）。

    None＝未綜合（誠實缺席）；on-disk 無條件帶鍵（schema↔serializer 雙射約束，
    同 commit_hash 慣例）；舊快照缺鍵→None。
    """

    def test_project_summary_round_trips(self, store):
        snap = store.create_snapshot(
            l1_snapshot={}, feature_relations=[], analyzed_files=[],
            trigger="manual", label="with-summary",
            project_summary="這個系統提供登入與報表匯出。",
        )
        loaded = store.get_snapshot(snap.version_id)
        assert loaded is not None
        assert loaded.project_summary == "這個系統提供登入與報表匯出。"

    def test_project_summary_defaults_to_none(self, store):
        snap = store.create_snapshot(
            l1_snapshot={}, feature_relations=[], analyzed_files=[],
        )
        loaded = store.get_snapshot(snap.version_id)
        assert loaded.project_summary is None

    def test_project_summary_key_emitted_even_when_none(self, store, tmp_path):
        snap = store.create_snapshot(
            l1_snapshot={}, feature_relations=[], analyzed_files=[],
        )
        raw = json.loads(
            (tmp_path / ".the-door" / "snapshots" / f"{snap.version_id}.json")
            .read_text(encoding="utf-8")
        )
        assert "project_summary" in raw
        assert raw["project_summary"] is None

    def test_legacy_snapshot_without_project_summary_loads_as_none(self, tmp_path):
        snapdir = tmp_path / ".the-door" / "snapshots"
        snapdir.mkdir(parents=True)
        legacy = {
            "version_id": "v-nosummary",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "trigger": "manual",
            "commit_hash": None,
            "git_tags": [],
            "label": "nosummary",
            "l1_snapshot": {},
            "l1_5_snapshot": {},
            "feature_relations_snapshot": [],
            "vulnerabilities_snapshot": [],
            "analyzed_files": [],
        }
        (snapdir / "v-nosummary.json").write_text(json.dumps(legacy), encoding="utf-8")
        loaded = SnapshotStore(tmp_path).get_snapshot("v-nosummary")
        assert loaded is not None
        assert loaded.project_summary is None


class TestNullSeverityRoundTrip:
    """F-severity-default V3：None-severity 漏洞經 fail-closed 落盤口通過＋round-trip 保 None。"""

    def test_none_severity_vuln_passes_failclosed_write_and_round_trips(self, store):
        from the_door.models import VulnerabilityEntry

        entry = VulnerabilityEntry(
            cve_id="CVE-X", package="p", version="1",
            severity=None, cvss=None, source="osv-scanner", evidence="",
        )
        # create_snapshot 內含 _write_snapshot fail-closed schema 校驗——None-severity 須通過
        snap = store.create_snapshot(
            l1_snapshot={}, feature_relations=[], analyzed_files=[],
            trigger="manual", label="null-sev", vulnerabilities=[entry],
        )
        loaded = store.get_snapshot(snap.version_id)
        assert loaded is not None
        assert len(loaded.vulnerabilities_snapshot) == 1
        assert loaded.vulnerabilities_snapshot[0].severity is None


def test_deserialize_legacy_drift_warns_and_normalizes(tmp_path):
    snap_dir = tmp_path / ".the-door" / "snapshots"
    snap_dir.mkdir(parents=True)
    vid = "abc12345-0000-0000-0000-000000000000"
    (snap_dir / f"{vid}.json").write_text(json.dumps({
        "version_id": vid,
        "timestamp": "2026-01-01T00:00:00Z",
        "trigger": "manual",
        "label": None,
        "git_tags": [],
        "commit_hash": None,
        "analyzed_files": [],
        "feature_relations_snapshot": [],
        "l1_snapshot": {
            "feat-x": {
                "feature_id": "feat-x", "label": "x", "description": "d",
                "trigger_description": "td",
                "confidence": "high",
                "source_node_count": 5,
                "source_nodes": [],
            }
        },
    }))
    with pytest.warns(UserWarning, match=r"source_nodes_drift.*feat-x"):
        snap = SnapshotStore(tmp_path).get_snapshot(vid)
    fs = snap.l1_snapshot["feat-x"]
    assert fs.source_node_count == 0
    assert fs.source_nodes == ()


def _sample_structure() -> StructureJSON:
    return StructureJSON(files=[], nodes=[], edges=[], topology=[])


def test_list_analyzed_versions_marks_has_persisted_structure(tmp_path):
    import time
    store = SnapshotStore(tmp_path)
    s1 = store.create_snapshot(l1_snapshot={}, feature_relations=[], analyzed_files=[])
    time.sleep(0.002)
    s2 = store.create_snapshot(l1_snapshot={}, feature_relations=[], analyzed_files=[])
    write_versioned_structure(tmp_path, s2.version_id, _sample_structure(), None)
    entries = store.list_analyzed_versions()
    assert len(entries) == 2
    by_id = {e.version_id: e for e in entries}
    assert by_id[s1.version_id].has_persisted_structure is False
    assert by_id[s2.version_id].has_persisted_structure is True
    assert by_id[s1.version_id].label is None
    assert by_id[s2.version_id].label is None
    assert entries[0].version_id == s2.version_id


class TestSourceNodesNotInDiff:
    """source_nodes is a viewer-display field, not a diff signal. Adding,
    removing, or reordering nodes must NOT classify the feature as
    attribute_changed — that should only happen for label/description.
    """

    def test_source_nodes_difference_does_not_trigger_attribute_changed(self):
        from the_door.core.diff.diff_engine import DiffEngine

        baseline_fs = FeatureSummary(
            feature_id="feat-a",
            label="Auth",
            description="Login flow",
            source_node_count=2,
            confidence="high",
            source_nodes=("src/a.py::x", "src/a.py::y"),
        )
        current_fs = FeatureSummary(
            feature_id="feat-a",
            label="Auth",
            description="Login flow",  # same!
            source_node_count=3,
            confidence="high",
            source_nodes=("src/a.py::x", "src/a.py::y", "src/a.py::z"),
        )
        baseline = VersionSnapshot(
            version_id="base", timestamp="2026-05-16T00:00:00+00:00",
            trigger="manual", l1_snapshot={"feat-a": baseline_fs},
        )
        current = VersionSnapshot(
            version_id="curr", timestamp="2026-05-16T01:00:00+00:00",
            trigger="manual", l1_snapshot={"feat-a": current_fs},
        )

        engine = DiffEngine()
        result = engine.compute_l1_diff(baseline, current)

        node_diff = next(nd for nd in result.node_diffs if nd.node_id == "feat-a")
        assert node_diff.diff_state == "unchanged", (
            f"source_nodes change leaked into diff state: {node_diff.diff_state}"
        )
