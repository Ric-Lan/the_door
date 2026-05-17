def test_wrap_injects_next_actions(tmp_path):
    from the_door.mcp.tools._response_envelope import wrap

    payload = {"result": "ok"}
    wrapped = wrap(payload, project_path=tmp_path, context="mcp")
    assert "next_actions" in wrapped
    assert isinstance(wrapped["next_actions"], list)
    assert wrapped["result"] == "ok"


def test_wrap_next_actions_are_plain_dicts(tmp_path):
    from the_door.mcp.tools._response_envelope import wrap

    wrapped = wrap({}, project_path=tmp_path, context="mcp")
    for action in wrapped["next_actions"]:
        assert isinstance(action, dict)
        # Must be JSON-serializable
        import json
        json.dumps(action)
