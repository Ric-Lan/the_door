# Task 07 — CLI + Pipeline Plumbing for `--minimal-context`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `the-door analyze` 與 `the-door update` 兩個 CLI 子命令加入 `--minimal-context` flag（opt-out flag，預設不啟用即等於 detail 模式）。讓 `PipelineOrchestrator` 接受 `context_mode` 並轉發給 `BatchReader`。

**Architecture:**
- CLI 層：argparse 加 `--minimal-context` boolean flag；不指定 = detail；指定 = minimal
- Orchestrator 層：新增 `context_mode` 參數，預設 `"detail"`，傳給 BatchReader
- 不引入任何 config file 機制（YAGNI — flag 已足夠）

**Tech Stack:** Python 3.11+ argparse, pytest, pytest-asyncio.

**Test Coverage Requirement:** `analyze_cmd.py`、`update_cmd.py`、`pipeline_orchestrator.py`（本任務修改的範圍）達 100% line coverage。新增測試覆蓋 flag 解析、orchestrator 轉發、預設值三條路徑。

---

## Background（自含）

`BatchReader` 已在前置任務支援 `context_mode: Literal["detail", "minimal"]`，預設 `"detail"`。本任務把這個參數一路接到 CLI flag。

涉及檔案：

1. **`the_door/src/the_door/cli/analyze_cmd.py`** — `the-door analyze <path>` 的 argparse 設定與主流程。
2. **`the_door/src/the_door/cli/update_cmd.py`** — `the-door update --from-snapshot <ref> <path>` 的 argparse 設定與主流程。
3. **`the_door/src/the_door/core/pipeline/pipeline_orchestrator.py`** — orchestrator 是分析流程的中心點，建立 BatchReader。

CLI flag 命名（spec §5.1）：

```
--minimal-context     使用原本只送 node_id 的 prompt 模式（預設為 detail 模式，
                      會把節點 signature/docstring 等完整資訊送給 LLM 以提升翻譯品質）
```

CLI 內部把 flag 轉成字串 `"minimal"` / `"detail"` 後傳入 orchestrator。

---

## Files

- Modify: `the_door/src/the_door/cli/analyze_cmd.py`
- Modify: `the_door/src/the_door/cli/update_cmd.py`
- Modify: `the_door/src/the_door/core/pipeline/pipeline_orchestrator.py`
- Test (new): `the_door/tests/unit/cli/test_analyze_cmd_context_mode.py`
- Test (new): `the_door/tests/unit/cli/test_update_cmd_context_mode.py`
- Test (new section in existing or new file): `the_door/tests/unit/core/pipeline/test_pipeline_orchestrator_context_mode.py`

---

## Steps

### Step 1 — Write failing tests for CLI flag parsing

- [ ] **Step 1: Test analyze_cmd flag parsing**

Create `the_door/tests/unit/cli/test_analyze_cmd_context_mode.py`:

```python
"""Tests for `--minimal-context` flag in `the-door analyze`."""
from __future__ import annotations

import argparse

import pytest

from the_door.cli import analyze_cmd


def _build_parser() -> argparse.ArgumentParser:
    """Get the argparse parser used by analyze_cmd.

    If analyze_cmd defines a top-level `build_parser()` helper, use it.
    Otherwise, replicate the argparse setup by calling whatever function
    register flags. Adjust import if helper has different name.
    """
    parser = argparse.ArgumentParser()
    analyze_cmd.add_arguments(parser)
    return parser


class TestMinimalContextFlag:
    def test_default_is_no_minimal_context(self):
        parser = _build_parser()
        args = parser.parse_args(["./fixture-project"])
        assert getattr(args, "minimal_context", False) is False

    def test_minimal_context_flag_sets_true(self):
        parser = _build_parser()
        args = parser.parse_args(["--minimal-context", "./fixture-project"])
        assert args.minimal_context is True

    def test_flag_help_mentions_token_savings(self):
        parser = _build_parser()
        help_text = parser.format_help()
        assert "--minimal-context" in help_text
        # 提示 trade-off
        assert "minimal" in help_text.lower() or "節省" in help_text or "token" in help_text.lower()


class TestArgsToContextMode:
    def test_args_to_context_mode_default_detail(self):
        """argparse Namespace -> 'detail' when --minimal-context absent."""
        parser = _build_parser()
        args = parser.parse_args(["./fixture-project"])
        assert analyze_cmd._resolve_context_mode(args) == "detail"

    def test_args_to_context_mode_minimal_when_flag_set(self):
        parser = _build_parser()
        args = parser.parse_args(["--minimal-context", "./fixture-project"])
        assert analyze_cmd._resolve_context_mode(args) == "minimal"
```

- [ ] **Step 2: Test update_cmd flag parsing**

Create `the_door/tests/unit/cli/test_update_cmd_context_mode.py`:

```python
"""Tests for `--minimal-context` flag in `the-door update`."""
from __future__ import annotations

import argparse

import pytest

from the_door.cli import update_cmd


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    update_cmd.add_arguments(parser)
    return parser


class TestMinimalContextFlagUpdate:
    def test_default_is_no_minimal_context(self):
        parser = _build_parser()
        args = parser.parse_args(["--from-snapshot", "v1.0.0", "./fixture-project"])
        assert getattr(args, "minimal_context", False) is False

    def test_minimal_context_flag_sets_true(self):
        parser = _build_parser()
        args = parser.parse_args([
            "--from-snapshot", "v1.0.0", "--minimal-context", "./fixture-project"
        ])
        assert args.minimal_context is True

    def test_args_to_context_mode_default_detail(self):
        parser = _build_parser()
        args = parser.parse_args(["--from-snapshot", "v1.0.0", "./fixture-project"])
        assert update_cmd._resolve_context_mode(args) == "detail"

    def test_args_to_context_mode_minimal_when_flag_set(self):
        parser = _build_parser()
        args = parser.parse_args([
            "--from-snapshot", "v1.0.0", "--minimal-context", "./fixture-project"
        ])
        assert update_cmd._resolve_context_mode(args) == "minimal"
```

- [ ] **Step 3: Test orchestrator parameter wiring**

Create `the_door/tests/unit/core/pipeline/test_pipeline_orchestrator_context_mode.py`:

```python
"""Tests for context_mode parameter forwarding in PipelineOrchestrator."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from the_door.core.pipeline.pipeline_orchestrator import PipelineOrchestrator


class TestOrchestratorContextMode:
    def test_orchestrator_accepts_context_mode_kwarg(self):
        # 建構不該 raise
        orch = PipelineOrchestrator(context_mode="detail")
        assert orch._context_mode == "detail"

    def test_orchestrator_default_context_mode_is_detail(self):
        orch = PipelineOrchestrator()
        assert orch._context_mode == "detail"

    def test_orchestrator_accepts_minimal(self):
        orch = PipelineOrchestrator(context_mode="minimal")
        assert orch._context_mode == "minimal"

    def test_orchestrator_rejects_invalid_mode(self):
        with pytest.raises(ValueError):
            PipelineOrchestrator(context_mode="foo")

    def test_orchestrator_passes_context_mode_to_batch_reader(self):
        """When orchestrator builds a BatchReader, context_mode is forwarded."""
        with patch("the_door.core.pipeline.pipeline_orchestrator.BatchReader") as MockBR:
            orch = PipelineOrchestrator(context_mode="minimal")
            orch._build_batch_reader(provider=MagicMock(), structure=MagicMock())
            kwargs = MockBR.call_args.kwargs
            assert kwargs.get("context_mode") == "minimal"
```

> **Note**: If `PipelineOrchestrator` 在當前 codebase 沒有 `_build_batch_reader` helper，本任務需新增此 helper 作為集中建構點。若 `BatchReader` 是在 `orch.run()` 內 inline 建構，把它抽出來方便測試。

- [ ] **Step 4: Run all new tests to verify they fail**

Run: `pytest the_door/tests/unit/cli/test_analyze_cmd_context_mode.py the_door/tests/unit/cli/test_update_cmd_context_mode.py the_door/tests/unit/core/pipeline/test_pipeline_orchestrator_context_mode.py -v`
Expected: FAIL — flag 與 method 不存在。

### Step 2 — Implement orchestrator change

- [ ] **Step 5: Modify PipelineOrchestrator**

Open `the_door/src/the_door/core/pipeline/pipeline_orchestrator.py`:

```python
from typing import Literal

_VALID_CONTEXT_MODES = ("detail", "minimal")


class PipelineOrchestrator:
    def __init__(
        self,
        *,
        context_mode: Literal["detail", "minimal"] = "detail",
        # ... existing parameters ...
    ) -> None:
        if context_mode not in _VALID_CONTEXT_MODES:
            raise ValueError(
                f"context_mode must be one of {_VALID_CONTEXT_MODES}, got {context_mode!r}"
            )
        self._context_mode = context_mode
        # ... existing init ...

    def _build_batch_reader(self, *, provider, structure, max_context_tokens=None):
        """Centralized BatchReader construction so context_mode is forwarded uniformly."""
        from the_door.core.reading.batch_reader import BatchReader
        return BatchReader(
            provider,
            structure,
            max_context_tokens=max_context_tokens,
            context_mode=self._context_mode,
        )
```

Then in any `run()` / `analyze()` method that previously did `BatchReader(provider, structure)`, replace with `self._build_batch_reader(provider=provider, structure=structure, ...)`.

### Step 3 — Implement CLI changes

- [ ] **Step 6: Modify analyze_cmd.py**

Open `the_door/src/the_door/cli/analyze_cmd.py`.

**6a. In `add_arguments(parser)` (or whatever function registers argparse flags):**

```python
def add_arguments(parser):
    # ... existing argument additions ...
    parser.add_argument(
        "--minimal-context",
        action="store_true",
        default=False,
        dest="minimal_context",
        help=(
            "使用原本只送 node_id 的 prompt 模式。預設為 detail 模式，會把節點 "
            "signature/docstring 等完整資訊送給 LLM 以提升翻譯品質。"
            "啟用 --minimal-context 可節省 token 但翻譯品質會回到 v1.3.6 之前的水準。"
        ),
    )
```

**6b. Add resolver helper:**

```python
def _resolve_context_mode(args) -> str:
    """Map argparse Namespace to context_mode string."""
    return "minimal" if getattr(args, "minimal_context", False) else "detail"
```

**6c. In main entry (e.g. `main(args)` or wherever PipelineOrchestrator is constructed), pass context_mode:**

```python
context_mode = _resolve_context_mode(args)
orchestrator = PipelineOrchestrator(
    # ... existing kwargs ...
    context_mode=context_mode,
)
```

- [ ] **Step 7: Modify update_cmd.py**

Apply the same 3 changes (6a / 6b / 6c) to `the_door/src/the_door/cli/update_cmd.py`. Same flag name, same resolver helper name (per-module copy is OK — small enough not to warrant a shared util).

```python
# In add_arguments:
parser.add_argument(
    "--minimal-context",
    action="store_true",
    default=False,
    dest="minimal_context",
    help=(
        "使用原本只送 node_id 的 prompt 模式。預設為 detail 模式，會把節點 "
        "signature/docstring 等完整資訊送給 LLM 以提升翻譯品質。"
        "啟用 --minimal-context 可節省 token 但翻譯品質會回到 v1.3.6 之前的水準。"
    ),
)


def _resolve_context_mode(args) -> str:
    return "minimal" if getattr(args, "minimal_context", False) else "detail"
```

In `update_cmd` main, pass `context_mode=_resolve_context_mode(args)` to `PipelineOrchestrator(...)`.

- [ ] **Step 8: Run all new tests**

Run: `pytest the_door/tests/unit/cli/test_analyze_cmd_context_mode.py the_door/tests/unit/cli/test_update_cmd_context_mode.py the_door/tests/unit/core/pipeline/test_pipeline_orchestrator_context_mode.py -v`
Expected: ALL PASS.

- [ ] **Step 9: Coverage check**

Run:
```
pytest the_door/tests/unit/cli/ the_door/tests/unit/core/pipeline/ \
  --cov=the_door.cli.analyze_cmd \
  --cov=the_door.cli.update_cmd \
  --cov=the_door.core.pipeline.pipeline_orchestrator \
  --cov-report=term-missing
```

Expected: 三個檔案 100%。如 orchestrator 整檔 100% 已超出本任務範圍，至少 **本任務修改的行** 100% 覆蓋（pytest-cov 的 `--cov-report=term-missing` 會列出未覆蓋行；確認本任務新增的 `_build_batch_reader` 與 `__init__` context_mode 驗證皆綠）。

- [ ] **Step 10: Manual smoke test**

Run:
```
the-door analyze --help | grep -A 3 "minimal-context"
the-door update --help | grep -A 3 "minimal-context"
```

Expected: 兩個 help output 皆顯示 `--minimal-context` flag 與描述。

- [ ] **Step 11: Full regression**

Run: `pytest the_door/tests/ -x -q`
Expected: 無新 failure。

- [ ] **Step 12: Commit**

```bash
git add the_door/src/the_door/cli/analyze_cmd.py the_door/src/the_door/cli/update_cmd.py the_door/src/the_door/core/pipeline/pipeline_orchestrator.py the_door/tests/unit/cli/test_analyze_cmd_context_mode.py the_door/tests/unit/cli/test_update_cmd_context_mode.py the_door/tests/unit/core/pipeline/test_pipeline_orchestrator_context_mode.py
git commit -m "feat(cli): add --minimal-context opt-out flag to analyze + update

Default is detail mode (richer LLM context). --minimal-context retains
the original node_id-only behavior for token-conscious users.
PipelineOrchestrator gains a centralized _build_batch_reader helper so
context_mode is forwarded uniformly."
```

---

## Acceptance Criteria

- [ ] `the-door analyze --minimal-context <path>` flag 解析正確
- [ ] `the-door update --minimal-context --from-snapshot <ref> <path>` flag 解析正確
- [ ] 不指定 flag 時，context_mode 為 `"detail"`
- [ ] CLI `--help` 輸出包含 `--minimal-context` flag 與 trade-off 說明
- [ ] `PipelineOrchestrator` 接受 `context_mode` kwarg，預設 `"detail"`，非法值 raise `ValueError`
- [ ] `PipelineOrchestrator._build_batch_reader` 把 `context_mode` 傳給 `BatchReader`
- [ ] 三個修改檔案的新增邏輯 100% line coverage
- [ ] `pytest the_door/tests/` 無新增 failure
