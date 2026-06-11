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


def test_wrap_injects_verification_guidance(tmp_path):
    from the_door.mcp.tools._response_envelope import wrap
    from the_door.core.guidance.verification_guidance import verification_guidance
    wrapped = wrap({"result": "ok"}, project_path=tmp_path, context="mcp")
    assert wrapped["verification_guidance"] == verification_guidance()


def test_wrap_guidance_coexists_with_next_actions(tmp_path):
    from the_door.mcp.tools._response_envelope import wrap
    wrapped = wrap({"result": "ok"}, project_path=tmp_path, context="mcp")
    assert "next_actions" in wrapped and isinstance(wrapped["next_actions"], list)
    assert "verification_guidance" in wrapped
    assert wrapped["result"] == "ok"


def test_wrap_checkpoint_envelope_has_no_guidance(tmp_path):
    from the_door.mcp.tools._response_envelope import wrap
    from the_door.core.flow_guard import Decision, CheckpointOption
    # chosen 預設 None → is_resolved=False → 走 checkpoint 早回路徑
    decision = Decision(
        checkpoint_name="cp", status="unresolved",
        options=[CheckpointOption(key="k", label="l", next_call="c")],
    )
    env = wrap({"_decision": decision}, project_path=tmp_path, context="mcp")
    assert env["result"] is None
    assert "verification_guidance" not in env
