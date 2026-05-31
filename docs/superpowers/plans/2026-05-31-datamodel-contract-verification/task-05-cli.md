# Task 05 — CLI 指令 `verify-data-model`

**內容分類：** CLI 入口。預設跑 Tier 0 定位 + 呈現；`--deep` 額外印候選檔清單 + 給 agent 的 Tier 1 指令（**不呼叫 LLM**）。

**設計來源：** spec §7.1。依賴 Task 02（localizer）、Task 04（renderer）。

**Files:**
- Create: `the_door/src/the_door/cli/verify_datamodel_cmd.py`
- Modify: `the_door/src/the_door/cli/main.py`（import + `main.add_command`）
- Create: `the_door/tests/unit/cli/test_verify_datamodel_cmd.py`

---

- [ ] **Step 1: 寫失敗測試**

`the_door/tests/unit/cli/test_verify_datamodel_cmd.py`：

```python
from click.testing import CliRunner

from the_door.cli.verify_datamodel_cmd import verify_datamodel_cmd


def _make_project(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "user.py").write_text("def save_user(name):\n    return name\n", encoding="utf-8")
    (tmp_path / "init.sql").write_text("CREATE TABLE u(id int);\n", encoding="utf-8")
    return tmp_path


def test_default_runs_tier0(tmp_path):
    _make_project(tmp_path)
    result = CliRunner().invoke(verify_datamodel_cmd, [str(tmp_path)])
    assert result.exit_code == 0
    assert "Data-Model Localization (Tier 0)" in result.output
    assert "name contains 'save'" in result.output  # code candidate reason (deterministic)
    assert "init.sql" in result.output              # schema candidate (relpath)
    assert "Next (Tier 1" not in result.output      # no --deep


def test_deep_lists_candidate_files_and_instructions(tmp_path):
    _make_project(tmp_path)
    result = CliRunner().invoke(verify_datamodel_cmd, [str(tmp_path), "--deep"])
    assert result.exit_code == 0
    assert "Next (Tier 1" in result.output
    assert "read: init.sql" in result.output
    assert "verify_data_model_contract" in result.output
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd the_door && python -m pytest tests/unit/cli/test_verify_datamodel_cmd.py -q`
Expected: FAIL（`ModuleNotFoundError: ...verify_datamodel_cmd`）。

- [ ] **Step 3: 實作 verify_datamodel_cmd.py**

`the_door/src/the_door/cli/verify_datamodel_cmd.py`：

```python
"""CLI verify-data-model — Tier 0 local localization (+ --deep candidate list for agent Tier 1)."""
from __future__ import annotations

import click

from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.datamodel.datamodel_localizer import DataModelLocalizer
from the_door.core.datamodel.datamodel_renderer import render_localization


@click.command("verify-data-model")
@click.argument("codebase_path")
@click.option("--deep", is_flag=True, default=False,
              help="Emit the candidate file list + agent Tier 1 instructions (no LLM call).")
def verify_datamodel_cmd(codebase_path: str, deep: bool) -> None:
    """Localize data-model touch points (Tier 0); --deep prints the Tier 1 hand-off."""
    result = ASTExtractor().extract(codebase_path)
    loc = DataModelLocalizer().localize(result, codebase_path)
    click.echo(render_localization(loc))
    if deep:
        click.echo("")
        click.echo("Next (Tier 1, hand to your agent — no API key needed):")
        files = sorted(
            {c.file for c in loc.code_candidates} | {c.file for c in loc.schema_candidates}
        )
        for f in files:
            click.echo(f"  read: {f}")
        click.echo("  then call MCP verify_data_model_contract with the normalized field-sets.")
```

- [ ] **Step 4: 跑測試確認通過**

Run: `cd the_door && python -m pytest tests/unit/cli/test_verify_datamodel_cmd.py -q`
Expected: PASS。

- [ ] **Step 5: 註冊到 main.py**

在 `the_door/src/the_door/cli/main.py` 的 import 區塊（與其他 `from the_door.cli.*_cmd import` 同段）加：

```python
from the_door.cli.verify_datamodel_cmd import verify_datamodel_cmd
```

並在 `main.add_command(...)` 區塊（與其他 `main.add_command` 同段）加：

```python
main.add_command(verify_datamodel_cmd)
```

- [ ] **Step 6: 驗證指令已掛上**

Run: `cd the_door && python -m the_door --help`
Expected: 指令清單含 `verify-data-model`。

- [ ] **Step 7: 跑覆蓋率**

Run: `cd the_door && python -m pytest tests/unit/cli/test_verify_datamodel_cmd.py --cov=the_door/src/the_door/cli/verify_datamodel_cmd.py --cov-report=term-missing -q`
Expected: PASS；verify_datamodel_cmd.py **100%**。

- [ ] **Step 8: Commit**

```bash
cd the_door
git add src/the_door/cli/verify_datamodel_cmd.py src/the_door/cli/main.py tests/unit/cli/test_verify_datamodel_cmd.py
git commit -m "feat(cli): verify-data-model command (Tier 0 + --deep hand-off)"
```

## Done when
- [ ] 預設輸出 Tier 0 定位（含 code/schema 候選）
- [ ] `--deep` 額外印候選檔清單 + Tier 1 指令、不呼叫 LLM
- [ ] `verify-data-model` 出現在 `--help`
- [ ] verify_datamodel_cmd.py 覆蓋率 100%
