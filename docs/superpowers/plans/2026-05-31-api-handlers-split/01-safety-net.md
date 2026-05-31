# Phase 01 — 行為安全網（Task 1）

> 讀本檔 + README 即可執行。先做，作為後續 rewire 的網。

## Task 1: router 綁定整合測試（補 8 個未被 e2e 覆蓋的端點）

**目的:** 在動任何結構前，先用真 HTTP 釘住目前這 8 個端點的「path→正確回應」，作為 rewire 的網。對**現行 server** 跑，必須立即 GREEN。

**8 個未被 `test_e2e_ui_server.py` 覆蓋的端點:** `POST /api/analyze`、`POST /api/set-project`、`GET /api/status`、`GET /api/diff`、`GET /api/diff-explanations/<fid>`、`POST /api/diff-explanations/<fid>/generate`、`GET /api/notes`、`POST /api/notes`。

**Files:**
- Create: `the_door/tests/integration/test_router_binding.py`

- [ ] **Step 1: 參考既有 e2e 的 server 啟動樣板**

Read `the_door/tests/integration/test_e2e_ui_server.py` 開頭（free-port、起 server thread、`urllib.request` 發請求的 helper）。沿用同樣板，不要自創新起法。若 e2e **無**「送原始 bytes body」的 helper（`_post_raw`），於本測試檔自建一個（`urllib.request.Request(url, data=raw_bytes, method="POST")` + 捕 `HTTPError` 取 status/body）。

- [ ] **Step 2: 寫整合測試（對現行 server，斷言現況行為）**

對每個端點發一次請求，斷言 HTTP status 與回應 body 的「形狀關鍵欄位」符合現況（不是內容值，是契約）。範例骨架（沿用 e2e 的 `_get`/`_post` helper 名稱）：

```python
"""Router-binding safety net: pins behavior of the 8 endpoints NOT covered by
test_e2e_ui_server.py, so the api/ package rewire cannot silently mis-route them.
"""
def test_get_status_returns_state_envelope(live_server):
    status, body = _get(live_server, "/api/status")
    assert status == 200
    assert "state" in body or "status" in body   # 以現行回應實際鍵為準（先跑現況確認）

def test_get_diff_requires_params(live_server):
    status, body = _get(live_server, "/api/diff")
    assert status == 400
    assert body["error"]["code"] == "missing_params"

def test_post_set_project_invalid_json(live_server):
    status, body = _post_raw(live_server, "/api/set-project", b"{not json")
    assert status == 400
    assert body["error"]["code"] == "invalid_json"

def test_post_notes_roundtrip(live_server):
    status, _ = _post(live_server, "/api/notes", {"feature_id": "feat-x", "text": "n"})
    assert status in (200, 201)
    status, body = _get(live_server, "/api/notes?feature_id=feat-x")
    assert status == 200
# …analyze / diff-explanations(讀+生成) 各補一條
```

> 斷言的確切鍵名以**現況回應為準**：先在實作機跑一次該端點、把實際回應鍵填進斷言，避免臆測。

- [ ] **Step 3: 跑測試，必須 GREEN（釘住現況）**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/integration/test_router_binding.py -v`
Expected: 全 PASS（這是現況基準，非 TDD red）。若紅，表示斷言鍵名臆測錯 → 依實際回應修正，不是改 server。

- [ ] **Step 4: Commit**

```bash
cd the_door && git add tests/integration/test_router_binding.py
git commit -m "test: router-binding safety net for 8 endpoints uncovered by e2e"
```
