"""Contract: SnapshotEntry shape from Task 01 (SnapshotStore.list_analyzed_versions)
matches what Task 02 (StateInspector) reads.

Producer side: Task 01 (01-core-data.md Task 01.5) — defines + emits SnapshotEntry.
Consumer side: Task 02 (02-guidance-engine.md Task 02.3) — reads via inspect()'s step 4.
"""
import pytest


@pytest.mark.contract
def test_snapshotentry_field_set_matches_consumer_expectation(tmp_path):
    from the_door.core.diff.snapshot_store import SnapshotStore
    store = SnapshotStore(tmp_path)
    store.create_snapshot(l1_snapshot={}, feature_relations=[], analyzed_files=[])
    entries = store.list_analyzed_versions()
    assert len(entries) == 1
    producer_entry = entries[0]

    from the_door.core.guidance.state import StateInspector
    state = StateInspector(tmp_path).inspect()
    consumer_entry = state.snapshots[0]

    assert type(producer_entry).__name__ == type(consumer_entry).__name__
    assert producer_entry.version_id == consumer_entry.version_id
    assert producer_entry.has_persisted_structure == consumer_entry.has_persisted_structure
    assert producer_entry.label == consumer_entry.label
    assert producer_entry.git_tags == consumer_entry.git_tags
    assert producer_entry.timestamp == consumer_entry.timestamp
