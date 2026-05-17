import json


def test_render_human_outputs_numbered_next_block(capsys):
    from the_door.cli.next_action_renderer import render_next_block
    from the_door.core.guidance.actions import NextAction
    actions = [
        NextAction(id="analyze.incremental", title="增量分析", rationale="r", priority=1, cli_command="the-door update --from-snapshot v1.0.0 ."),
        NextAction(id="viewer.open", title="開 viewer", rationale="r", priority=2, cli_command="the-door ui ."),
    ]
    render_next_block(actions, json_mode=False)
    captured = capsys.readouterr()
    assert "Next:" in captured.err
    assert "the-door update --from-snapshot v1.0.0" in captured.err


def test_render_json_outputs_machine_format(monkeypatch, capsys):
    from the_door.cli.next_action_renderer import render_next_block
    from the_door.core.guidance.actions import NextAction
    actions = [NextAction(id="x", title="t", rationale="r", priority=1, cli_command="ls")]
    render_next_block(actions, json_mode=True)
    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert "next_actions" in payload
    assert payload["next_actions"][0]["id"] == "x"
