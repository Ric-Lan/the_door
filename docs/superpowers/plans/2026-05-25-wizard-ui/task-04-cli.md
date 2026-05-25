# Task 04 — CLI 入口：`ui_cmd.py` 啟動時開 `wizard.html`

> **依賴：** Task 01（server 已有 `/api/analyze` 路由）

**Files:**
- Modify: `the_door/src/the_door/cli/ui_cmd.py`
- Create: `the_door/tests/unit/cli/test_ui_cmd_wizard.py`

---

## Task 04.1 — `ui_cmd.py` 改開 `wizard.html`

- [ ] **Step 1: 寫失敗測試**

建立 `the_door/tests/unit/cli/test_ui_cmd_wizard.py`：

```python
"""Tests for ui_cmd wizard.html entry point."""
from __future__ import annotations
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest


def test_ui_cmd_opens_wizard_html(tmp_path):
    """ui_cmd should open /wizard.html instead of the root URL."""
    from the_door.cli.ui_cmd import ui_cmd
    from click.testing import CliRunner

    # Create minimal viewer dir with wizard.html
    viewer_path = tmp_path / "viewer"
    viewer_path.mkdir()
    (viewer_path / "wizard.html").write_text("<html></html>", encoding="utf-8")
    (viewer_path / "index.html").write_text("<html></html>", encoding="utf-8")

    opened_urls = []

    mock_server = MagicMock()
    mock_server.url = f"http://127.0.0.1:19999"
    mock_server.start.side_effect = KeyboardInterrupt  # stop immediately

    with patch("the_door.cli.ui_cmd.UIServer", return_value=mock_server), \
         patch("the_door.cli.ui_cmd._resolve_viewer_dir", return_value=viewer_path), \
         patch("the_door.cli.ui_cmd.ProjectRegistry"), \
         patch("webbrowser.open", side_effect=lambda url: opened_urls.append(url)):
        runner = CliRunner()
        result = runner.invoke(ui_cmd, [str(tmp_path)])

    assert any("wizard.html" in url for url in opened_urls), \
        f"Expected wizard.html in opened URLs, got: {opened_urls}"


def test_ui_cmd_wizard_url_contains_server_base(tmp_path):
    """The wizard URL must use the server's base URL."""
    from the_door.cli.ui_cmd import ui_cmd
    from click.testing import CliRunner

    viewer_path = tmp_path / "viewer"
    viewer_path.mkdir()
    (viewer_path / "wizard.html").write_text("<html></html>", encoding="utf-8")
    (viewer_path / "index.html").write_text("<html></html>", encoding="utf-8")

    opened_urls = []
    mock_server = MagicMock()
    mock_server.url = "http://127.0.0.1:8765"
    mock_server.start.side_effect = KeyboardInterrupt

    with patch("the_door.cli.ui_cmd.UIServer", return_value=mock_server), \
         patch("the_door.cli.ui_cmd._resolve_viewer_dir", return_value=viewer_path), \
         patch("the_door.cli.ui_cmd.ProjectRegistry"), \
         patch("webbrowser.open", side_effect=lambda url: opened_urls.append(url)):
        runner = CliRunner()
        runner.invoke(ui_cmd, [str(tmp_path)])

    assert any(url.startswith("http://127.0.0.1:8765") for url in opened_urls)
    assert any("wizard.html" in url for url in opened_urls)
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd the_door && pytest tests/unit/cli/test_ui_cmd_wizard.py -v
```
期望：FAILED — `webbrowser.open` 被呼叫的是 `http://127.0.0.1:8765`（沒有 `wizard.html`）。

- [ ] **Step 3: 修改 `ui_cmd.py`**

開啟 `the_door/src/the_door/cli/ui_cmd.py`，找到：

```python
if not no_browser:
    threading.Timer(0.5, webbrowser.open, [server.url]).start()
```

改為：

```python
if not no_browser:
    wizard_url = server.url.rstrip("/") + "/wizard.html"
    threading.Timer(0.5, webbrowser.open, [wizard_url]).start()
```

- [ ] **Step 4: 確認測試通過**

```bash
cd the_door && pytest tests/unit/cli/test_ui_cmd_wizard.py -v
```
期望：2 PASSED。

- [ ] **Step 5: 確認全套測試不破壞**

```bash
cd the_door && pytest tests/ -x -q 2>&1 | tail -5
```
期望：0 failed。

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/cli/ui_cmd.py the_door/tests/unit/cli/test_ui_cmd_wizard.py
git commit -m "feat(wizard): ui_cmd opens wizard.html as entry point instead of root"
```

---

## Task 04.2 — 端對端驗收

> 此 step 為手動驗收，不是自動測試。

- [ ] **Step 1: 啟動伺服器**

```bash
the-door ui "C:\Users\Ric\Desktop\test-targets\the-door-v105" --port 8765
```

- [ ] **Step 2: 確認瀏覽器開啟 `wizard.html`**

瀏覽器應自動開啟 `http://127.0.0.1:8765/wizard.html`，顯示「歡迎使用 The Door」或操作選擇頁。

- [ ] **Step 3: 測試「查看快照」路徑**

若 test target 有 snapshot：
- 點「直接查看現有快照」
- 應 redirect 到 `http://127.0.0.1:8765/index.html`
- Viewer 正常顯示快照

- [ ] **Step 4: 確認 agent 模式顯示參數區塊**

若無 API key：
- 走完問卷（首次分析 → 排除 → 標籤 → 確認）
- 應顯示 `extract_structure(...)` + `snapshot_write(...)` 參數區塊
- 「複製」按鈕可點擊

- [ ] **Step 5: 最終 Python 測試**

```bash
cd the_door && pytest tests/ -q 2>&1 | tail -5
```
期望：全部通過，與 v1.3.1 基準相比 passed 數量只增不減。

- [ ] **Step 6: 最終 JS 測試 + coverage**

```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run --coverage 2>&1 | tail -10
```
期望：100% coverage（lines/functions/branches/statements），0 failed。
