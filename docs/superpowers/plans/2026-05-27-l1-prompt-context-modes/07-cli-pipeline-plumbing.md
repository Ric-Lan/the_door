# Task 07 — CLI + Pipeline Plumbing for `--minimal-context`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `the-door analyze` 與 `the-door update` 兩個 CLI 子命令加入 `--minimal-context` flag（opt-out flag）。Flag 透過 `AnalyzeConfig` 資料類別流轉到 `run_analyze_pipeline`，由它把 `context_mode` 傳給 `BatchReader`。

**Architecture:**
- CLI 層：兩個檔案皆用 **Click**（不是 argparse），新增 `@click.option("--minimal-context", is_flag=True)`
- Config 層：`AnalyzeConfig` dataclass（`models.py:801`）新增 `context_mode: str = "detail"` 欄位
- Pipeline 層：`run_analyze_pipeline` 在 `analyze_pipeline.py:173` 建構 `BatchReader` 時讀 `config.context_mode`
- `PipelineOrchestrator`（`pipeline_orchestrator.py:94`）內部呼叫 `run_analyze_pipeline`，因此 config 已自動透過 orchestrator 流轉，**不需要**新增 `_build_batch_reader` helper

**Tech Stack:** Python 3.11+, Click, pytest, click.testing.CliRunner。

**Test Coverage Requirement:** `AnalyzeConfig` 新欄位、`analyze_cmd` 與 `update_cmd` 的 Click option、`run_analyze_pipeline` 的 BatchReader 建構行 — 三條路徑 100% line coverage。

---

## Background（自含）

實際 codebase 的 CLI / pipeline 架構（前置 grep 驗證）：

**CLI 層**：兩個檔案皆用 Click，不是 argparse：

```python
# the_door/src/the_door/cli/analyze_cmd.py:13-20
@click.command("analyze")
@click.argument("codebase_path", type=click.Path(exists=True))
@click.option("--provider", default=None, help="LLM provider (openai/anthropic/ollama)")
@click.option("--model", default=None, help="Model name override")
@click.option("--yes", "-y", is_flag=True, help="Skip cost confirmation")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path")
@click.option("--offline", is_flag=True, help="Use local OSV database ...")
def analyze_cmd(codebase_path, provider, model, yes, output, offline):
    ...
```

```python
# the_door/src/the_door/cli/update_cmd.py:10-31（節錄）
@click.command("update")
@click.argument("path_a", ...)
@click.option("--from-snapshot", ...)
@click.option("--provider", ...)
def update_cmd(path_a, path_b, from_snapshot, ...):
    ...
```

**Config 層**：`AnalyzeConfig` 在 `the_door/src/the_door/models.py:801`（既有資料類別，已有 `provider / model / skip_cost_confirm / offline_vuln` 欄位）。

**Pipeline 層**：CLI 呼叫 `run_analyze_pipeline(path, config, progress_callback=...)`，後者在 `analyze_pipeline.py:173` 建構 `BatchReader`：

```python
# analyze_pipeline.py:173
reader = BatchReader(llm_provider=llm_provider, structure=structure)
result = asyncio.run(reader.read())
```

**Orchestrator 層**：`PipelineOrchestrator` class 在 `pipeline_orchestrator.py:94` 存在；它在 line 355 呼叫 `run_analyze_pipeline(...)`。**Orchestrator 自己不建構 BatchReader** — 真正的建構點就在 `analyze_pipeline.py:173`。因此只要把 `context_mode` 經由 `AnalyzeConfig` 流到 `run_analyze_pipeline`，orchestrator 流程自動受益。

`BatchReader` 已在前置任務支援 `context_mode: Literal["detail", "minimal"]`，預設 `"detail"`。

---

## Files

- Modify: `the_door/src/the_door/models.py`（AnalyzeConfig 加 `context_mode` 欄位）
- Modify: `the_door/src/the_door/cli/analyze_cmd.py`（加 Click option + 傳入 AnalyzeConfig）
- Modify: `the_door/src/the_door/cli/update_cmd.py`（加 Click option + 傳入 AnalyzeConfig 或對應 config 物件）
- Modify: `the_door/src/the_door/core/pipeline/analyze_pipeline.py`（line 173 BatchReader 建構讀 config.context_mode）
- Test (new): `the_door/tests/unit/cli/test_analyze_cmd_context_mode.py`
- Test (new): `the_door/tests/unit/cli/test_update_cmd_context_mode.py`
- Test (new): `the_door/tests/unit/core/pipeline/test_analyze_pipeline_context_mode.py`

---

## Steps

### Step 1 — Verify actual chain & locate fields

- [ ] **Step 1: Confirm AnalyzeConfig location + existing fields**

Run: `grep -n "class AnalyzeConfig" the_door/src/the_door/models.py`
Expected: 一行命中 (e.g. `801:class AnalyzeConfig:`)。

Run: `sed -n '795,830p' the_door/src/the_door/models.py`（或用編輯器開啟並讀取 AnalyzeConfig 內容）

記錄既有欄位清單，準備在末尾插入 `context_mode`。

- [ ] **Step 2: Confirm BatchReader build location**

Run: `grep -n "BatchReader(" the_door/src/the_door/core/pipeline/analyze_pipeline.py`
Expected: 一處（line ~173 區域）。

Run: `grep -n "BatchReader(" the_door/src/the_door/mcp/tools/analyze_tool.py`
Expected: 一處（在 Task 08 處理，**本任務不動**）。

Run: `grep -rn "BatchReader(" the_door/src/the_door/`
確認除上述兩處外無其他 call site。若有第三處，加入本任務修改清單。

- [ ] **Step 3: Confirm update_cmd's config wiring**

Run: `grep -n "AnalyzeConfig\|run_analyze_pipeline\|run_update_pipeline\|PipelineOrchestrator" the_door/src/the_door/cli/update_cmd.py`

更新流程可能：
- (A) 直接呼叫 `PipelineOrchestrator(...)`，其中傳一個 config 物件
- (B) 直接呼叫 `run_analyze_pipeline` 與 `analyze_cmd` 同樣方式
- (C) 用自己的 `run_update_pipeline`

依實際結果選擇接點：若 update 也走 `AnalyzeConfig`，沿用同一欄位；若走 `PipelineOrchestrator(... config=UpdateConfig ...)`，可能需要在 UpdateConfig（如存在）也加同名欄位。**記錄結果在 commit message**。

### Step 2 — Write failing tests

- [ ] **Step 4: Test AnalyzeConfig new field**

Create or extend `the_door/tests/unit/test_models_analyze_config.py`（若不存在則建立；若存在則 append class）：

```python
"""Tests for AnalyzeConfig context_mode field (Task 07)."""
from __future__ import annotations

import pytest

from the_door.models import AnalyzeConfig


class TestAnalyzeConfigContextMode:
    def test_default_context_mode_is_detail(self):
        cfg = AnalyzeConfig()
        assert cfg.context_mode == "detail"

    def test_accepts_minimal(self):
        cfg = AnalyzeConfig(context_mode="minimal")
        assert cfg.context_mode == "minimal"

    def test_accepts_detail_explicit(self):
        cfg = AnalyzeConfig(context_mode="detail")
        assert cfg.context_mode == "detail"

    def test_invalid_value_in_post_init(self):
        """若 AnalyzeConfig 已有 __post_init__ 驗證機制，
        加入 context_mode 驗證；若沒有，依其慣例（不驗證）即可
        — 由 BatchReader / pipeline 層擋下。"""
        # 此測試在實作時依 AnalyzeConfig 既有慣例決定保留或刪除。
        cfg = AnalyzeConfig(context_mode="weird")
        # 若 AnalyzeConfig 不做驗證：欄位即使是 'weird' 也能建構成功
        # 拒絕由 BatchReader 在 pipeline 執行時 raise ValueError
        assert cfg.context_mode == "weird"
```

- [ ] **Step 5: Test CLI options via click.testing.CliRunner**

Create `the_door/tests/unit/cli/test_analyze_cmd_context_mode.py`:

```python
"""Tests for `--minimal-context` Click option in `the-door analyze`."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from the_door.cli.analyze_cmd import analyze_cmd
from the_door.models import AnalyzeConfig


class TestMinimalContextOption:
    def test_help_shows_minimal_context_flag(self):
        runner = CliRunner()
        result = runner.invoke(analyze_cmd, ["--help"])
        assert result.exit_code == 0
        assert "--minimal-context" in result.output
        # Help text 含 trade-off 說明
        assert "minimal" in result.output.lower() or "token" in result.output.lower()


class TestFlagFlowsIntoAnalyzeConfig:
    @patch("the_door.cli.analyze_cmd.ConfigManager")
    @patch("the_door.cli.analyze_cmd.run_analyze_pipeline")
    def test_default_passes_detail_to_pipeline(self, mock_pipeline, mock_cfg_mgr):
        """不帶 flag → AnalyzeConfig.context_mode == 'detail'."""
        # ConfigManager 須回 API-key 已設定狀態，跳過 FlowGuard 分支
        mock_cfg_mgr.load.return_value = MagicMock(
            anthropic_api_key="fake", openai_api_key=None,
        )
        runner = CliRunner()
        with runner.isolated_filesystem():
            from pathlib import Path
            Path("project").mkdir()
            result = runner.invoke(analyze_cmd, ["project"])
        # 取出傳給 run_analyze_pipeline 的 config 第二個參數
        assert mock_pipeline.called
        config_arg = mock_pipeline.call_args.args[1] \
            if len(mock_pipeline.call_args.args) > 1 \
            else mock_pipeline.call_args.kwargs.get("config")
        assert isinstance(config_arg, AnalyzeConfig)
        assert config_arg.context_mode == "detail"

    @patch("the_door.cli.analyze_cmd.ConfigManager")
    @patch("the_door.cli.analyze_cmd.run_analyze_pipeline")
    def test_minimal_context_flag_passes_minimal(self, mock_pipeline, mock_cfg_mgr):
        mock_cfg_mgr.load.return_value = MagicMock(
            anthropic_api_key="fake", openai_api_key=None,
        )
        runner = CliRunner()
        with runner.isolated_filesystem():
            from pathlib import Path
            Path("project").mkdir()
            result = runner.invoke(analyze_cmd, ["--minimal-context", "project"])
        config_arg = mock_pipeline.call_args.args[1] \
            if len(mock_pipeline.call_args.args) > 1 \
            else mock_pipeline.call_args.kwargs.get("config")
        assert config_arg.context_mode == "minimal"
```

- [ ] **Step 6: Test update_cmd flag**

Create `the_door/tests/unit/cli/test_update_cmd_context_mode.py`:

```python
"""Tests for `--minimal-context` Click option in `the-door update`."""
from __future__ import annotations

from click.testing import CliRunner

from the_door.cli.update_cmd import update_cmd


class TestUpdateMinimalContextOption:
    def test_help_shows_minimal_context_flag(self):
        runner = CliRunner()
        result = runner.invoke(update_cmd, ["--help"])
        assert result.exit_code == 0
        assert "--minimal-context" in result.output
```

> 「flag 流入 config / pipeline」的測試在 Step 1 step 3 確認 update_cmd 接點後補；可能 mock `run_analyze_pipeline` 或 `PipelineOrchestrator`，依實際呼叫者決定。**先把 help 顯示測試寫好**，flow 測試在 Step 8 補。

- [ ] **Step 7: Test pipeline forwards config.context_mode to BatchReader**

Create `the_door/tests/unit/core/pipeline/test_analyze_pipeline_context_mode.py`:

```python
"""Tests that run_analyze_pipeline forwards config.context_mode to BatchReader."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest


@patch("the_door.core.pipeline.analyze_pipeline.BatchReader")
@patch("the_door.core.pipeline.analyze_pipeline.create_provider")
@patch("the_door.core.pipeline.analyze_pipeline.ASTExtractor")
def test_pipeline_passes_context_mode_to_batch_reader(
    mock_extractor, mock_provider, mock_br_class, tmp_path
):
    """When AnalyzeConfig.context_mode='minimal', BatchReader is constructed
    with context_mode='minimal'."""
    from the_door.core.pipeline.analyze_pipeline import run_analyze_pipeline
    from the_door.models import AnalyzeConfig

    # Setup minimal mocks so pipeline reaches BatchReader construction
    mock_extractor.return_value.extract.return_value = MagicMock(
        files=[], nodes=[], edges=[],
    )
    mock_provider.return_value = MagicMock()
    mock_br_instance = MagicMock()
    mock_br_instance.read = MagicMock()
    mock_br_class.return_value = mock_br_instance

    config = AnalyzeConfig(context_mode="minimal", skip_cost_confirm=True)
    try:
        run_analyze_pipeline(tmp_path, config, progress_callback=lambda m: None)
    except Exception:
        # 流程中其他 mock 不全可能讓後續步驟 fail，這沒關係 —
        # 我們只 assert BatchReader 建構時 context_mode 已傳入。
        pass

    kwargs = mock_br_class.call_args.kwargs if mock_br_class.call_args else {}
    assert kwargs.get("context_mode") == "minimal"
```

> 此測試需就地調整 patch target 與 mock 樹深度，因 pipeline 內部呼叫鏈不完全可預知。**重點**：`mock_br_class.call_args.kwargs.get("context_mode")` 必須是 `"minimal"`。

- [ ] **Step 8: Run all new tests to verify they fail**

Run: `pytest the_door/tests/unit/test_models_analyze_config.py the_door/tests/unit/cli/test_analyze_cmd_context_mode.py the_door/tests/unit/cli/test_update_cmd_context_mode.py the_door/tests/unit/core/pipeline/test_analyze_pipeline_context_mode.py -v`

Expected: 多數 FAIL — `AnalyzeConfig` 缺欄位、Click options 缺、pipeline 未傳 context_mode。

### Step 3 — Implement changes

- [ ] **Step 9: Add `context_mode` field to AnalyzeConfig**

Open `the_door/src/the_door/models.py`. Locate `class AnalyzeConfig:` (~line 801). Add `context_mode` field at the end:

```python
@dataclass
class AnalyzeConfig:
    # ... existing fields ...
    context_mode: str = "detail"
```

**不要**在 `__post_init__` 驗證 `context_mode` 值 — 驗證在 `BatchReader.__init__` 已存在（前置任務），保持單一驗證點（DRY）。

- [ ] **Step 10: Add Click option to analyze_cmd**

Open `the_door/src/the_door/cli/analyze_cmd.py`. After the existing `@click.option("--offline", ...)`:

```python
@click.option(
    "--minimal-context",
    "minimal_context",
    is_flag=True,
    default=False,
    help=(
        "使用原本只送 node_id 的 prompt 模式。預設為 detail 模式，"
        "會把節點 signature/docstring 等完整資訊送給 LLM 以提升翻譯品質。"
        "啟用此 flag 可節省 token，但翻譯品質會回到 v1.3.6 之前的水準。"
    ),
)
def analyze_cmd(codebase_path, provider, model, yes, output, offline, minimal_context):
    ...
```

並把 `minimal_context` 加進 `def analyze_cmd(...)` 的參數清單。

In the function body, construct `AnalyzeConfig` with `context_mode`:

```python
config = AnalyzeConfig(
    provider=provider,
    model=model,
    skip_cost_confirm=yes,
    offline_vuln=offline,
    context_mode="minimal" if minimal_context else "detail",
)
```

- [ ] **Step 11: Add Click option to update_cmd**

Open `the_door/src/the_door/cli/update_cmd.py`. After the existing `@click.option("--force-reanalyze", ...)`:

```python
@click.option(
    "--minimal-context",
    "minimal_context",
    is_flag=True,
    default=False,
    help=(
        "使用原本只送 node_id 的 prompt 模式。預設為 detail 模式。"
        "啟用此 flag 可節省 token，但翻譯品質會回到 v1.3.6 之前的水準。"
    ),
)
def update_cmd(path_a, path_b, from_snapshot, ..., minimal_context):
    ...
```

依 Step 3 step 1-3 確認的接點，把 `context_mode="minimal" if minimal_context else "detail"` 傳入該流程的 config 物件（可能是 `AnalyzeConfig` 或其他）。

- [ ] **Step 12: Read config.context_mode in run_analyze_pipeline**

Open `the_door/src/the_door/core/pipeline/analyze_pipeline.py`. Locate line ~173:

```python
# BEFORE
reader = BatchReader(llm_provider=llm_provider, structure=structure)

# AFTER
reader = BatchReader(
    llm_provider=llm_provider,
    structure=structure,
    context_mode=getattr(config, "context_mode", "detail"),
)
```

> 用 `getattr(..., "detail")` 防呆：若呼叫者傳入非 `AnalyzeConfig` 的設定物件（無此欄位），仍走 detail 預設，不 crash。

- [ ] **Step 13: Run new tests to verify they pass**

Run:
```bash
pytest the_door/tests/unit/test_models_analyze_config.py \
       the_door/tests/unit/cli/test_analyze_cmd_context_mode.py \
       the_door/tests/unit/cli/test_update_cmd_context_mode.py \
       the_door/tests/unit/core/pipeline/test_analyze_pipeline_context_mode.py -v
```

Expected: ALL PASS。如某些 mock target 在實際 codebase 不對位（例如 `the_door.cli.analyze_cmd.run_analyze_pipeline` 是 lazy import），調整 patch path 即可（不改實作）。

- [ ] **Step 14: Coverage check**

Run:
```bash
pytest the_door/tests/unit/cli/ the_door/tests/unit/core/pipeline/ \
  --cov=the_door.cli.analyze_cmd \
  --cov=the_door.cli.update_cmd \
  --cov=the_door.core.pipeline.analyze_pipeline \
  --cov=the_door.models \
  --cov-report=term-missing
```

Expected: 本任務新增的行 100% line coverage（新 Click option、AnalyzeConfig 新欄位、`run_analyze_pipeline` 的 BatchReader 建構）。

如 `models.py` / `analyze_pipeline.py` 整檔 100% 已超出範圍，至少 `--cov-report=term-missing` 確認**本任務新增的行**未列為 missing。

- [ ] **Step 15: Manual smoke test**

Run:
```bash
the-door analyze --help | grep -A 3 "minimal-context"
the-door update --help | grep -A 3 "minimal-context"
```

Expected: 兩個 help output 皆顯示 `--minimal-context` flag 與描述。

- [ ] **Step 16: Full regression**

Run: `pytest the_door/tests/ -x -q`
Expected: 無新 failure。

- [ ] **Step 17: Commit**

```bash
git add the_door/src/the_door/models.py the_door/src/the_door/cli/analyze_cmd.py the_door/src/the_door/cli/update_cmd.py the_door/src/the_door/core/pipeline/analyze_pipeline.py the_door/tests/unit/test_models_analyze_config.py the_door/tests/unit/cli/test_analyze_cmd_context_mode.py the_door/tests/unit/cli/test_update_cmd_context_mode.py the_door/tests/unit/core/pipeline/test_analyze_pipeline_context_mode.py
git commit -m "feat(cli): add --minimal-context Click flag wired through AnalyzeConfig

AnalyzeConfig gains context_mode field (default 'detail'). analyze + update
Click commands expose --minimal-context is_flag, mapping to
context_mode='minimal'. run_analyze_pipeline reads config.context_mode and
forwards to BatchReader at its existing construction point in
analyze_pipeline.py. No new orchestrator helper introduced — wiring uses
the config dataclass already flowing through the pipeline."
```

---

## Acceptance Criteria

- [ ] `AnalyzeConfig.context_mode` 欄位存在，預設 `"detail"`
- [ ] `the-door analyze --help` 顯示 `--minimal-context` flag 與 trade-off 描述
- [ ] `the-door update --help` 顯示 `--minimal-context` flag 與描述
- [ ] `analyze_cmd` 不帶 flag → `AnalyzeConfig(context_mode="detail")`
- [ ] `analyze_cmd --minimal-context` → `AnalyzeConfig(context_mode="minimal")`
- [ ] `update_cmd --minimal-context` 同樣將 minimal 流入該指令的 config 物件
- [ ] `run_analyze_pipeline` 在建構 `BatchReader` 時讀 `config.context_mode`（用 `getattr(..., "detail")` 防呆）
- [ ] **未引入** `PipelineOrchestrator._build_batch_reader` helper（既有 PipelineOrchestrator 經由 `run_analyze_pipeline` 自動受益，無需新增間接層）
- [ ] 新增測試 + 既有 pytest 套件全綠
- [ ] 本任務新增行 100% line coverage
