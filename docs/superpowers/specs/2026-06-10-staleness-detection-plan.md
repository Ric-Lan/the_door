# staleness-detection plan：inline TDD task 分解

> 承 spec `2026-06-10-staleness-detection-spec.md`。流程＝inline TDD（先寫 red 測 → 實作 → green）。
> 每 task 先跑新測見 red，再實作見 green，最後全套 0 failed 才 ff-merge。
> **環境**：pytest cwd＝worktree 內層 `the_door/`；`PYTHONUTF8=1`；`python -m pytest`（不用 live CLI/MCP）。
> **C4 hook**：Bash 勿含 `python -c`/`python x.py`（用 `python -m pytest`）；commit 用 `git commit -F`。

---

## Task 0 — 回歸地基：更新測試 fake 形狀（先做，避免後續 task 假 red）
**動機**（spec §0 spike）：新增 `for fi in extraction.files` 會讓 monkeypatched edge_residue 測
（T-1/T-2/T-5/C2-5/C2-5b）`AttributeError`。先讓 fake 誠實鏡像真實 `ExtractionResult` 形狀。

- 檔：`the_door/tests/unit/mcp/tools/test_edge_residue_tool.py:28-34` `_fake_extraction`。
- 改：`SimpleNamespace(edges=[...], nodes=[...], files=[])`（加 `files=[]`）。
- 驗：此 task **不改 production**，故先確認既有測仍綠（`files=[]` 對現有 code 無影響——現有 code 不讀 files）。
  跑 `python -m pytest the_door/tests/unit/mcp/tools/test_edge_residue_tool.py -q` → 全綠。
- **此 task 故意先行**：production 改完後這些測才不會因 AttributeError 假 red。

---

## Task 1 — checklist 寫入側：`source_files` 參數 + read_ledger strip（TDD）
**red 測**（`the_door/tests/unit/core/test_checklist.py`）：
- S-1 `stamp_stage(tmp, STAGE_EDGE_RESIDUE, covered_nodes=["a"], source_files={"f.py":[111,222]}, contract_version="1")`
  → `read_checklist` 的 `stages.edge_residue.source_files == {"f.py":[111,222]}`；`covered_nodes`/`node_count` 仍在。
- S-2 stamp 兩 stage（其一帶 source_files）→ `read_ledger` 結果中該 stage **無 `source_files` 鍵**、
  **有 `node_count`**、有 `stage` 名；不拋 KeyError。
- S-3 `stamp_stage(..., covered_nodes=["a"], contract_version="1")`（不給 source_files）→ entry **無 `source_files` 鍵**。

**實作**（`the_door/src/the_door/core/checklist.py`）：
- 加常數 `FIELD_SOURCE_FILES = "source_files"`（放在欄位名常數區）。
- `stamp_stage` 簽章加 `source_files: dict | None = None`（置於 `covered_nodes` 後、`details` 前，保持 kw-only）。
  邏輯：`if source_files is not None: entry[FIELD_SOURCE_FILES] = source_files`（原樣，不排序——key 已是路徑、value 是指紋）。
- `read_ledger`：在既有 `entry.pop(FIELD_COVERED_NODES, None)` 旁加 `entry.pop(FIELD_SOURCE_FILES, None)`。
- green：`python -m pytest the_door/tests/unit/core/test_checklist.py -q`。

**模組 docstring**：更新提及 source_files（edge_residue 記檔案指紋供 staleness gate）。

---

## Task 2 — edge_residue 蓋章記指紋（TDD）
**red 測**（`the_door/tests/unit/mcp/tools/test_edge_residue_tool.py`）：
- S-4：用既有真實 codebase fixture（參 line 173 `test_real_codebase` 或 copytree fixture→tmp）跑
  `edge_residue_tool.execute`，斷言 `stages.edge_residue.source_files` 非空，且對其中一個 key `rel`：
  `source_files[rel] == [ (tmp/rel).stat().st_mtime_ns, (tmp/rel).stat().st_size ]`。
  （E2E 守 fixture-input-only：copytree 到 tmp 再跑。）
  - **若既有 real-codebase 測用的是 repo-internal fixture**：沿用同一 fixture 路徑、copytree 到 tmp_path。

**實作**（`the_door/src/the_door/mcp/tools/edge_residue_tool.py`）：
- 在 `covered_nodes = sorted(...)` 之後、`stamp_stage(...)` 之前插入：
  ```python
  root = Path(codebase_path)
  source_files = {}
  for fi in extraction.files:          # production 直讀 .files（不 getattr；ExtractionResult 恆有）
      try:
          st = (root / fi.path).stat()
      except OSError:
          continue                     # 發現後到 stat 間消失：跳過（fail-soft）
      source_files[fi.path] = [st.st_mtime_ns, st.st_size]
  ```
- `stamp_stage(...)` 呼叫加 `source_files=source_files`。
- green：`python -m pytest the_door/tests/unit/mcp/tools/test_edge_residue_tool.py -q`（含 Task 0 的 fake，
  monkeypatched 測 `files=[]` → source_files={} → 不拋）。

---

## Task 3 — C3 hook staleness 檢查（TDD，黑箱 subprocess）
**red 測**（`the_door/tests/unit/hooks/test_execution_gates.py`，新區塊）：
helper：建真實檔 + 用真實 `stamp_stage` 蓋指紋。
```python
def _stamp_with_files(codebase, files: dict, covered):  # files: {rel: bytes}
    for rel, content in files.items():
        p = codebase / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(content)
    src = {}
    for rel in files:
        st = (codebase / rel).stat(); src[rel] = [st.st_mtime_ns, st.st_size]
    stamp_stage(codebase, STAGE_EDGE_RESIDUE, covered_nodes=covered,
                source_files=src, contract_version=SNAPSHOT_CONTRACT_VERSION)
```
- S-5 蓋 `{"f.py": b"x=1\n"}`、covered=["a"]，**不動檔** → `_write({}, codebase, source_nodes=["a"])` → rc0。
- S-6 同上後 `(codebase/"f.py").write_bytes(b"x=1\ny=2\n")`（size 變）→ deny rc2，stderr 含 "變動" 或 "edge_residue"。
- S-7 同 S-5 後 `(codebase/"f.py").unlink()` → deny rc2，stderr 含 "刪除" 或 "edge_residue"。
- S-8 **明確新增**：`stamp_stage(codebase, STAGE_EDGE_RESIDUE, covered_nodes=["a"], contract_version=CURRENT)`
  （**不帶 source_files**）+ source_nodes=["a"] → rc0。**與 C2-7 的區別＝本測釘的是「staleness
  skip-when-absent」語義不回歸**（C2-7 釘的是 coverage 通過；本測證舊形狀 checklist 不被新 staleness 檢查誤擋）。
- S-9 用 **`stamp_stage(codebase, STAGE_EDGE_RESIDUE, covered_nodes=["a"], source_files={"f.py": "bad"},
  contract_version=CURRENT)`**（stamp_stage 原樣寫值、不驗形狀＝producer↔reader honesty，不手寫整份 checklist）
  ＋建真實 `f.py` ＋ source_nodes=["a"] → stat 成功、`fp="bad"` 非 list → 該筆跳過 → rc0（fail-soft 不誤 deny）。
- S-10 蓋 `{"f.py": b"x=1\n"}` 後改檔，呼叫**不帶 source_nodes**（inherit-only）→ deny rc2。
- S-12 蓋 `{"f.py": b"x=1\n"}` 後改檔，以 `_patch(codebase, by_feature={"feat-a":["a"]})`（snapshot_patch）→ deny rc2。
- S-11 釘樁：`_c3_source()` 含 `the_door.core.checklist.FIELD_SOURCE_FILES` 值；延伸既有 C2-15 清單
  （把 `ck.FIELD_SOURCE_FILES` 加進迴圈斷言）。

**實作**（`.claude/hooks/c3_gate_snapshot_write.py`）：
- 加常數 `FIELD_SOURCE_FILES = "source_files"`（pinned 區，註明對齊 checklist 模組）。
- 在 coverage 檢查（#3）**之後**加 #4 staleness：
  ```python
  src_files = stage.get(FIELD_SOURCE_FILES)
  if isinstance(src_files, dict):
      for rel, fp in src_files.items():
          full = os.path.join(codebase_path, rel)
          try:
              st = os.stat(full)
          except OSError:
              return _deny("⛔ " + label + " 被擋（丙案 staleness）：edge_residue 涵蓋的檔案已刪除/移動/"
                           "無法存取：" + rel + "\n" + teach)
          if not (isinstance(fp, list) and len(fp) >= 2):
              continue   # 壞筆／未知形狀：fail-soft 跳過（forward-compat: 容忍 >2 元素）
          if st.st_mtime_ns != fp[0] or st.st_size != fp[1]:
              return _deny("⛔ " + label + " 被擋（丙案 staleness）：edge_residue 涵蓋的檔案自蓋章後"
                           "已變動：" + rel + "\n" + teach)
  ```
- docstring：把「Deferred ... deletion / in-place modification staleness」段更新為「現由 source_files
  指紋偵測（mtime_ns+size）；仍 deferred＝新增未追蹤檔未被引用、對抗式 mtime 重置」。
- green：`python -m pytest the_door/tests/unit/hooks/test_execution_gates.py -q`。

**注意**：`len(fp) >= 2`（非 `== 2`）＝forward-compat（未來 `[mtime,size,sha]`）；spec §5 已述、S-9 釘 fail-soft。

---

## Task 4 — 全套回歸 + 護欄
- `PYTHONUTF8=1 python -m pytest -q`（worktree `the_door/`）→ **0 failed**（baseline 1395 + 新測 S-1..S-12 共 11 個淨增）。
- 確認既有 C2/C3/C4/C5/C6/水平推廣測全綠（Task 0 的 fake 修正 + skip-when-absent 向後相容）。
- 文件：spec §2.5 殘餘 deferred 已文件化；**CHANGELOG `[Unreleased]` 不在本刀補**（沿用 campaign：出版時統一補，與 C6/C5/水平推廣同批）。
- **契約版號不 bump**（純加法，`SNAPSHOT_CONTRACT_VERSION` 仍 `"1"`；釘樁 S-11/既有 C2-14 對齊）。

---

## ff-merge
- 全綠後（使用者連跑授權下）：worktree commit（`git commit -F <repo外訊息檔>`）→ 切回 main → ff-merge。
- commit message slug：`feat(c-staleness): mtime+size fingerprint — gate detects edge_residue staleness (deletion/in-place mod)`。
- **ff-merge 前查 main working tree 乾淨**（不覆蓋 WIP）。**不主動 push。**

---

## 風險 / 既知（plan 層）
- mtime false-positive（git checkout 重置）→ 過度 deny → 重跑零-key edge_residue 自癒（fail-safe，spec §0）。
- 大 codebase：gate 每次 snapshot_write 做 N 次 stat（無 byte-read/AST）→ <100ms 量級，可接受（spec §0 cost）。
- S-6 改檔以 **size 變化**確保確定性 red（不依賴 mtime tick 解析度）；production 對 mtime_ns OR size 任一變即 deny。
- 自我 gate：本 repo C3/C4 hook active，但本刀不呼叫 `mcp__the-door__snapshot_*`（純改 Python+pytest）→ 無自擋；
  C4 僅需避免 Bash 含 `python -c`/`python x.py`。
