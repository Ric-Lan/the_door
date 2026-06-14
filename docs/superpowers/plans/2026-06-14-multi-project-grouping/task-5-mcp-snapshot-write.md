# Task 5: MCP — `snapshot_write` 加 group hint

**Depends on:** Task 1 (registry.py 新方法)

**Files:**
- Modify: `the_door/src/the_door/mcp/tools/snapshot_write_tool.py`
- Modify: `the_door/tests/unit/mcp/tools/test_snapshot_write_tool.py`

---

- [ ] **Step 1: 在 `test_snapshot_write_tool.py` 末尾加入兩個新測試**

> 先確認現有測試用到的 imports：`stamp_stage`, `STAGE_EDGE_RESIDUE`, `SNAPSHOT_CONTRACT_VERSION`, `_run`, `_feature`。這些都在 test 檔最上方已定義。直接在檔案末尾 append。

```python
# ── group fields in snapshot_write response ──────────────────────────────────

def test_snapshot_write_includes_group_when_project_in_group(tmp_path, monkeypatch):
    """snapshot_write response contains group field when project is grouped."""
    from the_door.core.registry import ProjectRegistry
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    reg.create_group("my-group")
    reg.add_to_group("my-group", str(tmp_path))
    monkeypatch.setattr("the_door.mcp.tools.snapshot_write_tool.ProjectRegistry", lambda: reg)
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["a"],
                contract_version=SNAPSHOT_CONTRACT_VERSION)
    result = _run({"codebase_path": str(tmp_path), "l1_features": [_feature()], "label": "v1"})
    assert result.get("group") is not None
    assert result["group"]["name"] == "my-group"


def test_snapshot_write_group_null_with_hint_when_ungrouped(tmp_path, monkeypatch):
    """snapshot_write response has group=null and hint when project is ungrouped."""
    from the_door.core.registry import ProjectRegistry
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    reg.register(str(tmp_path))
    monkeypatch.setattr("the_door.mcp.tools.snapshot_write_tool.ProjectRegistry", lambda: reg)
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["a"],
                contract_version=SNAPSHOT_CONTRACT_VERSION)
    result = _run({"codebase_path": str(tmp_path), "l1_features": [_feature()], "label": "v1"})
    assert result.get("group") is None
    assert "hint" in result
    assert "the-door group add" in result["hint"]
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/mcp/tools/test_snapshot_write_tool.py::test_snapshot_write_includes_group_when_project_in_group -v 2>&1 | tail -10
```

Expected: `AssertionError: assert None is not None`（`result.get("group")` 回 None）

- [ ] **Step 3: 修改 `snapshot_write_tool.py` — 在成功路徑末尾加 group 欄位**

在 `snapshot_write_tool.py` 找到這兩行（execute() 最後的成功 return，位於約 line 384–385）：

```python
    payload["execution_ledger"] = _ledger_with_snapshot_write(codebase_path, sw_details)
    return wrap(payload, project_path=Path(codebase_path), context="mcp")
```

替換為：

```python
    payload["execution_ledger"] = _ledger_with_snapshot_write(codebase_path, sw_details)
    _reg = ProjectRegistry()
    _proj = _reg.get_by_path(codebase_path)
    _grp = _reg.get_group_for_project(_proj["id"]) if _proj else None
    if _grp:
        payload["group"] = _grp
    else:
        payload["group"] = None
        payload["hint"] = UNGROUPED_HINT
    return wrap(payload, project_path=Path(codebase_path), context="mcp")
```

> `ProjectRegistry` 在 execute() 內 line 348 已有局部 import（`from the_door.core.registry import ProjectRegistry`）；同一行改為 `from the_door.core.registry import ProjectRegistry, UNGROUPED_HINT`，無需在檔案頂部再加 import。

- [ ] **Step 4: 確認測試通過**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/mcp/tools/test_snapshot_write_tool.py -v 2>&1 | tail -15
```

Expected: 全部 PASSED（含原有測試）

- [ ] **Step 5: Commit**

```bash
cd the_door && git add the_door/src/the_door/mcp/tools/snapshot_write_tool.py the_door/tests/unit/mcp/tools/test_snapshot_write_tool.py
git commit -m "feat(mcp): snapshot_write response includes group info and ungrouped hint"
```
