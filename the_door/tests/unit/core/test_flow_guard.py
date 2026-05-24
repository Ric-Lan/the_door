import pytest
from the_door.core.flow_guard import CheckpointOption, Decision, FlowGuard


@pytest.fixture
def guard():
    return FlowGuard()


@pytest.fixture
def options():
    return [
        CheckpointOption(key="A", label="Option A"),
        CheckpointOption(key="B", label="Option B"),
    ]


def test_choice_none_returns_unresolved(guard, options):
    decision = guard.check("test-checkpoint", "pending", options, choice=None)
    assert decision.is_resolved is False
    assert decision.chosen is None


def test_valid_choice_returns_resolved(guard, options):
    decision = guard.check("test-checkpoint", "pending", options, choice="A")
    assert decision.is_resolved is True
    assert decision.chosen == "A"


def test_invalid_choice_key_returns_unresolved(guard, options):
    decision = guard.check("test-checkpoint", "pending", options, choice="Z")
    assert decision.is_resolved is False
    assert decision.chosen is None


def test_choice_case_insensitive(guard, options):
    decision = guard.check("test-checkpoint", "pending", options, choice="a")
    assert decision.is_resolved is True
    assert decision.chosen == "A"


def test_empty_options_raises(guard):
    with pytest.raises(ValueError, match="options must not be empty"):
        guard.check("test-checkpoint", "pending", [], choice=None)


def test_duplicate_option_keys_raises(guard):
    dup_options = [
        CheckpointOption(key="A", label="First A"),
        CheckpointOption(key="A", label="Second A"),
    ]
    with pytest.raises(ValueError, match="duplicate option key: A"):
        guard.check("test-checkpoint", "pending", dup_options)


def test_decision_is_resolved_false_when_chosen_none():
    d = Decision(checkpoint_name="x", status="s", options=[], chosen=None)
    assert d.is_resolved is False


def test_decision_is_resolved_true_when_chosen_set():
    d = Decision(checkpoint_name="x", status="s", options=[], chosen="A")
    assert d.is_resolved is True


def test_checkpoint_option_next_call_default():
    opt = CheckpointOption(key="A", label="Option A")
    assert opt.next_call == ""
