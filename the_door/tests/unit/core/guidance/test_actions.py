import pytest


def test_nextaction_requires_exactly_one_form():
    from the_door.core.guidance.actions import NextAction

    with pytest.raises(ValueError, match="exactly one"):
        NextAction(id="x", title="t", rationale="r", priority=1,
                   cli_command="ls", mcp_tool="y")

    with pytest.raises(ValueError, match="exactly one"):
        NextAction(id="x", title="t", rationale="r", priority=1)


def test_nextaction_mcp_tool_requires_arguments():
    from the_door.core.guidance.actions import NextAction

    with pytest.raises(ValueError, match="mcp_arguments"):
        NextAction(id="x", title="t", rationale="r", priority=1, mcp_tool="foo")

    NextAction(id="x", title="t", rationale="r", priority=1, mcp_tool="foo", mcp_arguments={})


def test_nextaction_to_json_dict():
    from the_door.core.guidance.actions import NextAction, to_json_dict

    a = NextAction(id="x", title="T", rationale="R", priority=1, cli_command="ls")
    d = to_json_dict(a)
    assert d == {
        "id": "x",
        "title": "T",
        "rationale": "R",
        "priority": 1,
        "cli_command": "ls",
        "mcp_tool": None,
        "mcp_arguments": None,
        "viewer_route": None,
    }
