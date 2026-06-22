# Phase 1 — Planner feasibility 守衛

> 父計畫：[../2026-06-23-chunk-dispatch-merge-plan.md](../2026-06-23-chunk-dispatch-merge-plan.md)。先讀其「關鍵事實」。
> pytest 從 repo root 跑：`python -m pytest the_door/tests/... -v`；Windows 必要時 `PYTHONUTF8=1`；hook 擋 `python -c`/`python x.py`/`grep`/`cat`/`find`/`head`/`tail`/`rg` → 用 `python -m pytest` 與 Read/Grep/Glob；commit 用 `git commit -F` heredoc。

對既有 `chunk_planner.py` **純加法**：`plan()`/`_plan_from_views()` 新增 `max_total_tokens` 參數；`total_est_tokens > max_total_tokens` → 短路回 `regime="too_large"` / `feasible=False`（不切分）；其餘路徑一律帶 `feasible=True`。

---

### Task 1: feasibility 守衛 + `feasible` 欄位

**Files:**
- Modify: `the_door/src/the_door/core/structure_view/chunk_planner.py`
- Test: `the_door/tests/unit/core/structure_view/test_chunk_planner.py`（既有檔，新增測試）

- [ ] **Step 1: 寫失敗測試**

加到 `test_chunk_planner.py` 末端（檔內已有 `_node` helper 與 `cp` import）：

```python
def test_plan_from_views_feasible_true_on_normal():
    views = {f"f.py::n{i}": _node(f"f.py::n{i}") for i in range(3)}
    out = cp._plan_from_views(views)          # 預設 max_total_tokens=2M、small
    assert out["feasible"] is True
    assert out["regime"] == "small"


def test_plan_from_views_too_large_short_circuits():
    views = {"a.py::f": _node("a.py::f")}      # 單節點估值 > 10
    out = cp._plan_from_views(views, target_tokens=100, max_total_tokens=10)
    assert out["regime"] == "too_large"
    assert out["feasible"] is False
    assert out["needs_split"] is False
    assert out["chunks"] == []
    assert out["total_est_tokens"] > 10
    assert "reason" in out


def test_plan_from_views_split_path_feasible_true():
    # 強制切分（小 target）仍 feasible（total 未超預設 2M）
    views = {f"f.py::n{i}": _node(f"f.py::n{i}") for i in range(6)}
    out = cp._plan_from_views(views, target_tokens=60)
    assert out["feasible"] is True
    assert out["needs_split"] is True
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_planner.py -k "feasible or too_large" -v`
Expected: FAIL（`feasible` 鍵不存在 / `max_total_tokens` 非法參數 TypeError）

- [ ] **Step 3: 實作（純加法改）**

在 `chunk_planner.py`：

(a) 常數區（`DEFAULT_LARGE_RATIO = 8` 之後）加：
```python
DEFAULT_MAX_TOTAL_TOKENS = 2_000_000  # feasibility 上限：超過則 too_large、回饋無法翻譯
```

(b) `_assemble(...)` 回傳的 dict 加一鍵 `"feasible": True`（正常路徑皆可行）：
```python
    return {
        "target_tokens": target,
        "regime": regime,
        "needs_split": needs_split,
        "feasible": True,
        "total_est_tokens": total,
        "chunks": out_chunks,
        "rollup": {
            "chunk_count": len(out_chunks),
            "cross_chunk_edges": cross,
            "oversized_node_warnings": sorted(set(warnings)),
        },
    }
```

(c) `plan()` 簽章加參數並下傳：
```python
def plan(codebase_path, target_tokens: int = DEFAULT_TARGET_TOKENS,
         large_ratio: int = DEFAULT_LARGE_RATIO,
         max_total_tokens: int = DEFAULT_MAX_TOTAL_TOKENS) -> dict:
    """讀既有 structure-view，triage 後切成 ≤ target_tokens 的 chunk 計畫。
    structure-view 缺失 → load_views 拋 LocateError（自然向上拋）。"""
    return _plan_from_views(load_views(codebase_path), target_tokens, large_ratio, max_total_tokens)
```

(d) `_plan_from_views()` 簽章加參數，並在 `total = sum(...)` **之後、triage 之前**短路：
```python
def _plan_from_views(views: dict, target_tokens: int = DEFAULT_TARGET_TOKENS,
                     large_ratio: int = DEFAULT_LARGE_RATIO,
                     max_total_tokens: int = DEFAULT_MAX_TOTAL_TOKENS) -> dict:
    """純核心：吃 {node_id: view}，回 chunk 計畫。無 IO，便於合成測試。"""
    est = {nid: estimate_tokens(v) for nid, v in views.items()}
    total = sum(est.values())

    if total > max_total_tokens:
        return {
            "target_tokens": target_tokens,
            "regime": "too_large",
            "needs_split": False,
            "feasible": False,
            "total_est_tokens": total,
            "reason": (f"total_est_tokens {total} exceeds max_total_tokens "
                       f"{max_total_tokens}; project too large for chunked LLM translation"),
            "chunks": [],
            "rollup": {"chunk_count": 0, "cross_chunk_edges": 0,
                       "oversized_node_warnings": []},
        }

    regime, needs_split = triage(total, target_tokens, large_ratio)
    # …（以下既有邏輯不變：small 短路 / 連通分量 → Tier1/2 → _assemble）…
```
（其餘 `_plan_from_views` 內容**保持不變**——只在 `total` 後插入上面的守衛區塊、並改簽章。）

- [ ] **Step 4: 跑測試確認通過 + 既有不回歸**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_planner.py -v`
Expected: 全 PASS（新 3 個 + 既有 triage/plan 測試皆綠；`feasible` 純加不破壞既有斷言）

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/chunk_planner.py the_door/tests/unit/core/structure_view/test_chunk_planner.py
git commit -F - <<'EOF'
feat(chunk-planner): add feasibility guard (max_total_tokens -> too_large)

純加法：plan()/_plan_from_views() 加 max_total_tokens 參數；total 超過即短路回
regime=too_large/feasible=False（不切分），供協定回饋使用者「專案過大無法翻譯」。
正常路徑一律帶 feasible=True。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

## Phase 1 自審
- spec §5（單一 `max_total_tokens`、total 短路、`feasible` 一律輸出、`too_large` + reason、不切分）→ Task 1。✓
- 純加法：只加常數/參數/一鍵/一短路區塊；既有 small/medium/large 邏輯與測試不動。✓
- 型別：`plan`/`_plan_from_views` 新參數有預設值（既有呼叫不破）；`feasible` bool；`too_large` dict 形狀與正常輸出相容（多 `reason`、`chunks=[]`）。✓
- 無 placeholder。✓
