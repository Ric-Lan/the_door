def test_registered_tool_names_match_build_tools():
    from the_door.mcp.server import _build_tools, REGISTERED_TOOL_NAMES
    names = {t.name for t in _build_tools()}
    assert names == REGISTERED_TOOL_NAMES
    # 釘樁：第一刀引導要指向的工具確實註冊
    assert "extract_structure" in REGISTERED_TOOL_NAMES
