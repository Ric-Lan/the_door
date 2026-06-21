import pytest

from the_door.core.classification.block_validator import (
    BlockValidationError,
    validate_blocks,
)
from the_door.models import BlockSummary


def _b(bid, feats=(), parent=None):
    return BlockSummary(
        block_id=bid, label=bid + " 群組功能說明", responsibility="職責說明",
        related_features=tuple(feats), parent_block_id=parent,
    )


def test_valid_two_level_tree_passes():
    blocks = {
        "blk-top": _b("blk-top"),
        "blk-leaf": _b("blk-leaf", ["feat-a", "feat-b"], parent="blk-top"),
        "blk-solo": _b("blk-solo", ["feat-c"]),
    }
    validate_blocks(blocks, {"feat-a", "feat-b", "feat-c"})


def test_three_levels_rejected():
    blocks = {
        "blk-top": _b("blk-top"),
        "blk-mid": _b("blk-mid", parent="blk-top"),
        "blk-leaf": _b("blk-leaf", ["feat-a"], parent="blk-mid"),
    }
    with pytest.raises(BlockValidationError) as e:
        validate_blocks(blocks, {"feat-a"})
    assert e.value.code == "block.too_deep"


def test_dangling_parent_rejected():
    blocks = {"blk-leaf": _b("blk-leaf", ["feat-a"], parent="blk-missing")}
    with pytest.raises(BlockValidationError) as e:
        validate_blocks(blocks, {"feat-a"})
    assert e.value.code == "block.dangling_parent"


def test_parent_with_features_rejected():
    blocks = {
        "blk-top": _b("blk-top", ["feat-a"]),
        "blk-leaf": _b("blk-leaf", ["feat-b"], parent="blk-top"),
    }
    with pytest.raises(BlockValidationError) as e:
        validate_blocks(blocks, {"feat-a", "feat-b"})
    assert e.value.code == "block.parent_has_features"


def test_duplicate_membership_rejected():
    blocks = {
        "blk-1": _b("blk-1", ["feat-a"]),
        "blk-2": _b("blk-2", ["feat-a"]),
    }
    with pytest.raises(BlockValidationError) as e:
        validate_blocks(blocks, {"feat-a"})
    assert e.value.code == "block.duplicate_membership"


def test_unknown_feature_rejected():
    blocks = {"blk-1": _b("blk-1", ["feat-ghost"])}
    with pytest.raises(BlockValidationError) as e:
        validate_blocks(blocks, {"feat-a"})
    assert e.value.code == "block.unknown_feature"


def test_unclassified_feature_rejected():
    blocks = {"blk-1": _b("blk-1", ["feat-a"])}
    with pytest.raises(BlockValidationError) as e:
        validate_blocks(blocks, {"feat-a", "feat-b"})
    assert e.value.code == "block.unclassified"
