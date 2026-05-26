# Task 02 — APIHandlers: callable 注入（backward compatible）

> **依賴：** 無（可與 Task 01 平行）

**Files:**
- Modify: `the_door/src/the_door/core/ui/api_handlers.py`

---

## 背景

`APIHandlers.__init__` 目前接受 `project_root: Path` 和 `job_store: JobStore` 並固定儲存。為了支援動態切換，需要改為「呼叫 callable 取得最新值」。

**關鍵設計：** 用 Python `@property` 在 `_project_root` 和 `_job_store` 名稱上包裝 callable，使 class 內 48 個既有用法全部不需修改。`__init__` 同時接受舊式（直接值）和新式（callable），完全 backward compatible。

---

## Task 02.1 — 修改 `__init__` + 加入 properties

- [ ] **Step 1: 加測試確認 backward compatibility**

在 `test_api_handlers_set_project.py` 加：

```python
from the_door.core.ui.api_handlers import APIHandlers


def test_api_handlers_backward_compatible_with_direct_values(tmp_path):
    """Old call style still works."""
    store = JobStore()
    handlers = APIHandlers(project_root=tmp_path, job_store=store)
    assert handlers._project_root == tmp_path
    assert handlers._job_store is store


def test_api_handlers_callable_injection_returns_current_value(tmp_path):
    """project_root_fn is called each time _project_root is accessed."""
    store = JobStore()
    path_holder = [tmp_path]
    handlers = APIHandlers(
        project_root_fn=lambda: path_holder[0],
        job_store_fn=lambda: store,
    )
    assert handlers._project_root == tmp_path
    new_path = tmp_path / "sub"
    new_path.mkdir()
    path_holder[0] = new_path
    assert handlers._project_root == new_path   # sees updated value


def test_api_handlers_switch_project_fn_is_called(tmp_path):
    """switch_project_fn is stored and callable."""
    called_with = []
    def my_switch(path, force):
        called_with.append((path, force))
        return {"status": "switched", "path": str(path)}

    handlers = APIHandlers(
        project_root=tmp_path,
        job_store=JobStore(),
        switch_project_fn=my_switch,
    )
    handlers._switch_project_fn(tmp_path, False)
    assert called_with == [(tmp_path, False)]
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd the_door && pytest tests/unit/core/ui/test_api_handlers_set_project.py -k "backward_compatible or callable_injection or switch_project_fn" -v
```
期望：3 FAILED。

- [ ] **Step 3: 修改 `api_handlers.py` 的 `__init__`**

開啟 `the_door/src/the_door/core/ui/api_handlers.py`，找到：

```python
    def __init__(self, project_root: Path, job_store: JobStore) -> None:
        self._project_root = project_root
        self._job_store = job_store
```

改為：

```python
    def __init__(
        self,
        project_root: Path | None = None,
        job_store: JobStore | None = None,
        *,
        project_root_fn=None,
        job_store_fn=None,
        switch_project_fn=None,
    ) -> None:
        self.__project_root_fn = project_root_fn if project_root_fn is not None else (lambda: project_root)
        self.__job_store_fn = job_store_fn if job_store_fn is not None else (lambda: job_store)
        self._switch_project_fn = switch_project_fn or (lambda path, force: {"status": "error", "message": "not configured"})

    @property
    def _project_root(self) -> Path:
        return self.__project_root_fn()

    @property
    def _job_store(self) -> JobStore:
        return self.__job_store_fn()
```

**注意：** `_project_root` 和 `_job_store` 從 instance 變數變成 property，class 內其他 48 個 `self._project_root` / `self._job_store` 用法**不需要修改**。

- [ ] **Step 4: 確認新測試通過**

```bash
cd the_door && pytest tests/unit/core/ui/test_api_handlers_set_project.py -k "backward_compatible or callable_injection or switch_project_fn" -v
```
期望：3 PASSED。

- [ ] **Step 5: 確認全套測試不破壞**

```bash
cd the_door && pytest tests/ -x -q 2>&1 | tail -5
```
期望：0 failed（現有所有 APIHandlers 測試用 `project_root=..., job_store=...` keyword 形式，完全相容）。

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/core/ui/api_handlers.py the_door/tests/unit/core/ui/test_api_handlers_set_project.py
git commit -m "feat(switch): refactor APIHandlers.__init__ to callable injection (backward compatible)"
```
