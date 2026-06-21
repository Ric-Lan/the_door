"""BlockHandlers.get_blocks：回兩層樹 + 成員；無 l1_5 回空；無快照 404。"""
import tempfile
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.handlers.blocks import BlockHandlers
from the_door.models import BlockSummary, FeatureSummary


def _ctx(root):
    return APIContext(lambda: Path(root), lambda *_a, **_k: None)


def _seed(cp, with_blocks=True):
    store = SnapshotStore(Path(cp))
    blocks = {}
    if with_blocks:
        blocks = {
            "blk-top": BlockSummary("blk-top", "品質與安全群組說明", "把關品質"),
            "blk-leaf": BlockSummary(
                "blk-leaf", "輸出與範圍驗證子群組", "驗證輸出",
                related_features=("feat-a",), parent_block_id="blk-top",
            ),
            "blk-core": BlockSummary(
                "blk-core", "核心分析引擎群組說明", "抽取分析",
                related_features=("feat-b",), is_new_this_version=True,
            ),
        }
    return store.create_snapshot(
        l1_snapshot={
            "feat-a": FeatureSummary("feat-a", "輸出驗證", "驗證描述", 1, "high"),
            "feat-b": FeatureSummary("feat-b", "抽取", "抽取描述", 1, "medium"),
        },
        feature_relations=[], analyzed_files=[], trigger="manual", label="v1",
        l1_5_snapshot=blocks,
    )


def test_get_blocks_returns_tree():
    cp = tempfile.mkdtemp()
    snap = _seed(cp)
    status, body = BlockHandlers(_ctx(cp)).get_blocks(version_id=snap.version_id)
    assert status == 200
    by_id = {b["block_id"]: b for b in body["blocks"]}
    assert by_id["blk-leaf"]["parent_block_id"] == "blk-top"
    assert by_id["blk-leaf"]["features"][0]["feature_id"] == "feat-a"
    assert by_id["blk-leaf"]["features"][0]["confidence"] == "high"
    assert by_id["blk-core"]["is_new_this_version"] is True


def test_get_blocks_empty_when_no_l1_5():
    cp = tempfile.mkdtemp()
    snap = _seed(cp, with_blocks=False)
    status, body = BlockHandlers(_ctx(cp)).get_blocks(version_id=snap.version_id)
    assert status == 200
    assert body["blocks"] == []


def test_get_blocks_404_no_snapshot():
    cp = tempfile.mkdtemp()
    status, body = BlockHandlers(_ctx(cp)).get_blocks(version_id="missing")
    assert status == 404
