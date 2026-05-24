"""Tests for CheckpointRenderer: CLI CHECKPOINT interaction rendering."""
from __future__ import annotations

import pytest
from unittest.mock import patch
from io import StringIO

from the_door.core.flow_guard import CheckpointOption, Decision, FlowGuard
from the_door.cli.checkpoint_renderer import CheckpointRenderer


@pytest.fixture
def guard():
    return FlowGuard()


@pytest.fixture
def renderer(guard):
    return CheckpointRenderer(guard)


@pytest.fixture
def two_option_decision(guard):
    return guard.check(
        "test-cp",
        "needs a choice",
        [
            CheckpointOption("A", "Option Alpha", "next_tool(arg='A')"),
            CheckpointOption("B", "Option Beta"),
        ],
    )


def test_prompt_output_contains_checkpoint_name(renderer, two_option_decision, capsys):
    with patch("builtins.input", return_value="A"):
        renderer.prompt(two_option_decision)
    out = capsys.readouterr().out
    assert "[CHECKPOINT: test-cp]" in out


def test_prompt_output_contains_status(renderer, two_option_decision, capsys):
    with patch("builtins.input", return_value="A"):
        renderer.prompt(two_option_decision)
    out = capsys.readouterr().out
    assert "needs a choice" in out


def test_prompt_output_contains_option_keys_and_labels(renderer, two_option_decision, capsys):
    with patch("builtins.input", return_value="A"):
        renderer.prompt(two_option_decision)
    out = capsys.readouterr().out
    assert "A)" in out
    assert "Option Alpha" in out
    assert "B)" in out
    assert "Option Beta" in out


def test_prompt_shows_next_call_when_nonempty(renderer, two_option_decision, capsys):
    with patch("builtins.input", return_value="A"):
        renderer.prompt(two_option_decision)
    out = capsys.readouterr().out
    assert "next_tool(arg='A')" in out


def test_prompt_valid_uppercase_returns_choice(renderer, two_option_decision, capsys):
    with patch("builtins.input", return_value="A"):
        result = renderer.prompt(two_option_decision)
    assert result == "A"


def test_prompt_valid_lowercase_returns_normalized(renderer, two_option_decision, capsys):
    with patch("builtins.input", return_value="a"):
        result = renderer.prompt(two_option_decision)
    assert result == "A"


def test_prompt_invalid_then_valid_shows_error_and_retries(renderer, two_option_decision, capsys):
    with patch("builtins.input", side_effect=["Z", "B"]):
        result = renderer.prompt(two_option_decision)
    out = capsys.readouterr().out
    assert result == "B"
    assert "Z" in out or "無效" in out or "invalid" in out.lower()


def test_prompt_single_option(guard, capsys):
    decision = guard.check("cp", "s", [CheckpointOption("A", "Only option")])
    renderer = CheckpointRenderer(guard)
    with patch("builtins.input", return_value="A"):
        result = renderer.prompt(decision)
    assert result == "A"


def test_prompt_already_resolved_returns_chosen_without_input(guard, renderer):
    decision = guard.check("cp", "s", [CheckpointOption("A", "X")], choice="A")
    assert decision.is_resolved
    # Should NOT call input at all
    with patch("builtins.input", side_effect=Exception("should not be called")):
        result = renderer.prompt(decision)
    assert result == "A"


def test_prompt_eof_raises(renderer, two_option_decision):
    with patch("builtins.input", side_effect=EOFError):
        with pytest.raises(EOFError):
            renderer.prompt(two_option_decision)
